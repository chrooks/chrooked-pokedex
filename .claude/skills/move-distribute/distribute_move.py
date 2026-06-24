#!/usr/bin/env python3
"""Distribute one existing move across many species' level-up learnsets by rule.

Deterministic roster-wide distribution: pick recipients by type + attack split,
then drop the move into the widest gap of a chosen level window so it never lands
on an occupied level and keeps spacing where the learnset allows. Append-only —
it asserts no existing learnset move is ever dropped. Renders through the
project's own writer so formatting and other Override fields are preserved.

This is the engine behind the `move-distribute` skill. Run it with --dry-run
first; it prints the full recipient table and writes nothing.

Examples:
  # The Clod Toss run, reproduced:
  distribute_move.py "Clod Toss" --types Ground --split physical --levels 4-14

  # A mid-game special Water move, evolved forms included in-window:
  distribute_move.py surf --types Water --split special --preset mid

  # Early-game move that a caught-evolved mon should also have:
  distribute_move.py "Mach Punch" --types Fighting --split physical \
      --preset early --evolved-at-1
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

# --- Repo wiring: resolve the repo root from this file's location and import the
#     project model so the writer/loader stay the single source of formatting. ---
SKILL_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/move-distribute/ -> <repo>
sys.path.insert(0, str(REPO_ROOT / "src"))

from chrooked_pokedex.model.schema import SpeciesOverride, LearnsetMove  # noqa: E402
from chrooked_pokedex.model.loader import load_species  # noqa: E402
from chrooked_pokedex.seed.writer import species_yaml  # noqa: E402

# Named windows are shorthand that expand to (min, max) level ranges. Override any
# of them with explicit --levels MIN-MAX. Level numbers are the real metric.
PRESETS = {
    "early": (4, 15),
    "mid": (16, 35),
    "late": (36, 55),
}

# Attack-split predicates over a species' base stats. atk/spa comparison only.
SPLITS = {
    "physical": lambda atk, spa: atk >= spa,
    "special": lambda atk, spa: spa >= atk,
    "strong-physical": lambda atk, spa: atk > spa,
    "strong-special": lambda atk, spa: spa > atk,
    "any": lambda atk, spa: True,
}

# Legendaries / mythicals / paradox / ultra beasts, by national dex number.
# Excluded by default (a weak early move on a box legendary is just clutter).
# Curated best-effort — top it up if a straggler slips through; the recipient
# report prints what was excluded so you can eyeball it. Override with
# --include-legendaries.
LEGENDARY_DEX = frozenset(
    {144, 145, 146, 150, 151}
    | {243, 244, 245, 249, 250, 251}
    | {377, 378, 379, 380, 381, 382, 383, 384, 385, 386}
    | set(range(480, 494))
    | {494}
    | set(range(638, 650))
    | set(range(716, 722))
    | {772, 773}
    | set(range(785, 810))
    | set(range(888, 899))
    | {905}
    | set(range(984, 996))  # gen 9 paradox
    | set(range(1001, 1026))  # treasures of ruin, box legends, DLC legends, paradox
)


def parse_levels(args) -> tuple[int, int]:
    if args.levels:
        lo, hi = args.levels.split("-")
        return int(lo), int(hi)
    return PRESETS[args.preset]


def load_snapshot(root: Path) -> dict:
    snap = json.load(open(root / "ruleset" / ".base" / "1.11.2.json"))
    return snap


def resolve_move_name(root: Path, snap: dict, move_arg: str) -> str:
    """Accept a display name or a chrooked_id; return the display name the
    learnset stores. Verify the move actually exists (ruleset Override or base)."""
    moves_dir = root / "ruleset" / "moves"
    # by chrooked_id in the Ruleset
    ov_path = moves_dir / f"{move_arg.lower().replace(' ', '')}.yaml"
    if ov_path.exists():
        import yaml
        return yaml.safe_load(ov_path.read_text())["name"]
    # by display name or id in the base snapshot
    for cid, m in snap.get("moves", {}).items():
        if move_arg in (m.get("name"), cid):
            return m["name"]
    # by display name across Ruleset move files
    import yaml
    for f in moves_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        if data.get("name") == move_arg:
            return data["name"]
    raise SystemExit(
        f"Move {move_arg!r} not found in the Ruleset or base snapshot. "
        "Create it first (e.g. via /move-design)."
    )


def best_level(other_levels: set[int], lo: int, hi: int) -> int:
    """Earliest level in [lo, hi] whose nearest existing move is farthest away."""
    existing = sorted(other_levels)
    best_L, best_score = None, None
    for L in range(lo, hi + 1):
        score = min((abs(L - e) for e in existing), default=99)
        if best_score is None or score > best_score:
            best_L, best_score = L, score
    return best_L


def evolved_set(species: dict) -> set[str]:
    evolved = set()
    for v in species.values():
        for e in (v.get("evolves_into") or []):
            evolved.add(e["to"])
    return evolved


def is_alt_battle_form(cid: str, name: str) -> bool:
    """Mega / Primal forms share the base species' learnset, so distributing onto
    them is redundant. Detected by name so it needs no curated list."""
    n = name.lower()
    return "mega" in n or "primal" in n


def select_recipients(snap: dict, types: set[str], split, *, include_legendaries: bool,
                      include_megas: bool) -> list[str]:
    out = []
    for cid, v in snap["species"].items():
        vtypes = set(v.get("types") or [])
        if not (vtypes & types):
            continue
        st = v.get("stats") or {}
        if not split(st.get("atk", 0), st.get("spa", 0)):
            continue
        if not include_legendaries and v.get("dex") in LEGENDARY_DEX:
            continue
        if not include_megas and is_alt_battle_form(cid, v.get("name", "")):
            continue
        out.append(cid)
    return out


def base_learnset(snap: dict, cid: str) -> list[LearnsetMove]:
    return [LearnsetMove(level=e["level"], move=e["move"])
            for e in (snap["species"][cid].get("learnset") or [])]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("move", help="Move display name or chrooked_id (must already exist)")
    ap.add_argument("--types", required=True,
                    help="Comma-separated type(s); a species matches if it has any of them")
    ap.add_argument("--split", default="physical", choices=sorted(SPLITS),
                    help="Attack-split filter over base atk/spa (default: physical)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--levels", help="Explicit window MIN-MAX, e.g. 4-14")
    g.add_argument("--preset", choices=sorted(PRESETS), default="early",
                   help="Named window shorthand (default: early)")
    ap.add_argument("--evolved-at-1", action="store_true",
                    help="Park the move at level 1 on evolved forms (Move Reminder "
                         "access) instead of gap-placing it in the window")
    ap.add_argument("--include-legendaries", action="store_true",
                    help="Don't exclude legendaries/paradox/mythicals")
    ap.add_argument("--include-megas", action="store_true",
                    help="Don't skip Mega/Primal forms (they share base learnsets)")
    ap.add_argument("--exclude", default="",
                    help="Comma-separated chrooked_ids to drop from recipients")
    ap.add_argument("--root", default=str(REPO_ROOT), help="Repo root override")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the recipient table; write nothing")
    args = ap.parse_args()

    root = Path(args.root)
    snap = load_snapshot(root)
    species_dir = root / "ruleset" / "species"

    move_name = resolve_move_name(root, snap, args.move)
    lo, hi = parse_levels(args)
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    split = SPLITS[args.split]
    drop = {x.strip() for x in args.exclude.split(",") if x.strip()}

    evolved = evolved_set(snap["species"])
    recipients = [c for c in select_recipients(
        snap, types, split,
        include_legendaries=args.include_legendaries,
        include_megas=args.include_megas) if c not in drop]

    rows, wrote = [], 0
    for cid in recipients:
        path = species_dir / f"{cid}.yaml"
        if path.exists():
            ov = load_species(path)
            learn = list(ov.learnset) if ov.learnset is not None else base_learnset(snap, cid)
        else:
            ov = SpeciesOverride(name=snap["species"][cid]["name"], chrooked_id=cid)
            learn = base_learnset(snap, cid)

        if any(m.move == move_name for m in learn):
            rows.append((snap["species"][cid]["dex"], cid, "—", "already has it"))
            continue

        is_evo = cid in evolved
        level = 1 if (is_evo and args.evolved_at_1) else best_level(
            {m.level for m in learn}, lo, hi)
        new_learn = sorted(learn + [LearnsetMove(level=level, move=move_name)],
                           key=lambda m: m.level)

        # Append-only invariant: never drop a move. This is the guardrail that the
        # original two-pass Clod Toss attempt lacked.
        assert {m.move for m in new_learn} == {m.move for m in learn} | {move_name}, \
            f"move loss on {cid}"

        kind = "evolved" if is_evo else "first"
        rows.append((snap["species"][cid]["dex"], cid, f"L{level}", kind))
        if not args.dry_run:
            path.write_text(species_yaml(dataclasses.replace(ov, learnset=tuple(new_learn))),
                            encoding="utf-8")
            wrote += 1

    rows.sort()
    print(f"Move:   {move_name}")
    print(f"Types:  {', '.join(sorted(types))}   Split: {args.split}   Window: {lo}-{hi}"
          + ("   evolved@L1" if args.evolved_at_1 else ""))
    print(f"{'DEX':>4}  {'SPECIES':<20} {'LEVEL':<6} NOTE")
    for dex, cid, lvl, note in rows:
        print(f"{dex:>4}  {cid:<20} {lvl:<6} {note}")
    verb = "Would write" if args.dry_run else "Wrote"
    print(f"\n{verb}: {len([r for r in rows if r[2] != '—'])} species "
          f"({len(recipients)} matched the filter)")
    if args.dry_run:
        print("Dry run — nothing written. Re-run without --dry-run to apply.")


if __name__ == "__main__":
    main()
