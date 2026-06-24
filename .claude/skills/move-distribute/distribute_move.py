#!/usr/bin/env python3
"""Distribute one existing move across many species' level-up learnsets by rule.

Thin CLI over the shared engine in ``chrooked_pokedex.distribute`` (the same code
the web distributor uses, so the two can't drift). Picks recipients by type +
attack split, then drops the move into the widest gap of a level window so it
never lands on an occupied level and keeps spacing. Append-only — it asserts no
existing learnset move is ever dropped. Renders through the project's own writer
so formatting and other Override fields are preserved.

Run with --dry-run first; it prints the full recipient table and writes nothing.

Examples:
  distribute_move.py "Clod Toss" --types Ground --split physical --levels 4-14
  distribute_move.py surf --types Water --split special --preset mid
  distribute_move.py "Mach Punch" --types Fighting --preset early --evolved-at-1
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/move-distribute/ -> <repo>
sys.path.insert(0, str(REPO_ROOT / "src"))

from chrooked_pokedex import distribute as engine  # noqa: E402
from chrooked_pokedex.model.schema import SpeciesOverride, LearnsetMove  # noqa: E402
from chrooked_pokedex.model.loader import load_species  # noqa: E402
from chrooked_pokedex.seed.writer import species_yaml  # noqa: E402


def load_snapshot(root: Path) -> dict:
    return json.load(open(root / "ruleset" / ".base" / "1.11.2.json"))


def resolve_move_name(root: Path, snap: dict, move_arg: str) -> str:
    import yaml
    moves_dir = root / "ruleset" / "moves"
    ov_path = moves_dir / f"{move_arg.lower().replace(' ', '')}.yaml"
    if ov_path.exists():
        return yaml.safe_load(ov_path.read_text())["name"]
    for _cid, m in snap.get("moves", {}).items():
        if move_arg in (m.get("name"), _cid):
            return m["name"]
    for f in moves_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        if data.get("name") == move_arg:
            return data["name"]
    raise SystemExit(
        f"Move {move_arg!r} not found in the Ruleset or base snapshot. "
        "Create it first (e.g. via /move-design)."
    )


def build_records(snap: dict, move_name: str) -> dict[str, engine.SpeciesRecord]:
    """SpeciesRecords from the base snapshot, flagged with whether they already
    learn the move."""
    out: dict[str, engine.SpeciesRecord] = {}
    for cid, v in snap["species"].items():
        st = v.get("stats") or {}
        learn = v.get("learnset") or []
        out[cid] = engine.SpeciesRecord(
            chrooked_id=cid,
            name=v.get("name", cid),
            dex=v.get("dex"),
            types=tuple(v.get("types") or []),
            atk=st.get("atk", 0),
            spa=st.get("spa", 0),
            levels=tuple(m["level"] for m in learn),
            bst=sum(st.values()),
            has_move=any(m.get("move") == move_name for m in learn),
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("move", help="Move display name or chrooked_id (must already exist)")
    ap.add_argument("--types", required=True,
                    help="Comma-separated type(s); a species matches if it has any of them")
    ap.add_argument("--split", default="physical", choices=sorted(engine.SPLITS),
                    help="Attack-split filter over base atk/spa (default: physical)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--levels", help="Explicit window MIN-MAX, e.g. 4-14")
    g.add_argument("--preset", choices=sorted(engine.PRESETS), default="early",
                   help="Named window shorthand (default: early)")
    ap.add_argument("--no-evolutions", action="store_true",
                    help="Only the matched species; don't pull in their evolution lines")
    ap.add_argument("--evolved-at-1", action="store_true",
                    help="Park the move at level 1 on evolved forms (Move Reminder access)")
    ap.add_argument("--rarity", default="common", choices=sorted(engine.RARITY),
                    help="Breadth tier: narrows recipients by BST + lands rarer "
                         "moves later in the window (default: common)")
    ap.add_argument("--include-legendaries", action="store_true")
    ap.add_argument("--include-megas", action="store_true")
    ap.add_argument("--exclude", default="", help="Comma-separated chrooked_ids to drop")
    ap.add_argument("--root", default=str(REPO_ROOT), help="Repo root override")
    ap.add_argument("--dry-run", action="store_true", help="Print the table; write nothing")
    args = ap.parse_args()

    root = Path(args.root)
    snap = load_snapshot(root)
    species_dir = root / "ruleset" / "species"

    move_name = resolve_move_name(root, snap, args.move)
    window = engine.parse_window(
        levels=tuple(int(x) for x in args.levels.split("-")) if args.levels else None,
        preset=args.preset)
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    drop = {x.strip() for x in args.exclude.split(",") if x.strip()}

    records = build_records(snap, move_name)
    evo = engine.build_evolution_index(snap["species"])
    matched = [cid for cid in engine.select_by_rule(
        records.values(), types=types, split=args.split,
        include_legendaries=args.include_legendaries,
        include_megas=args.include_megas) if cid not in drop]
    matched = engine.apply_breadth(records, matched, args.rarity)
    rows = [r for r in engine.distribute(
        records, evo, matched_ids=matched, window=window,
        include_evolutions=not args.no_evolutions,
        evolved_at_1=args.evolved_at_1,
        level_bias=engine.RARITY[args.rarity]["bias"]) if r.chrooked_id not in drop]

    table, wrote = [], 0
    for row in rows:
        path = species_dir / f"{row.chrooked_id}.yaml"
        if path.exists():
            ov = load_species(path)
            learn = list(ov.learnset) if ov.learnset is not None else _base_ls(snap, row.chrooked_id)
        else:
            ov = SpeciesOverride(name=row.name, chrooked_id=row.chrooked_id)
            learn = _base_ls(snap, row.chrooked_id)

        if any(m.move == move_name for m in learn):
            table.append((row.dex, row.chrooked_id, "—", "already has it"))
            continue

        new_learn = sorted(learn + [LearnsetMove(level=row.level, move=move_name)],
                           key=lambda m: m.level)
        assert {m.move for m in new_learn} == {m.move for m in learn} | {move_name}, \
            f"move loss on {row.chrooked_id}"
        table.append((row.dex, row.chrooked_id, f"L{row.level}",
                      row.stage + ("" if row.matched else " (line)")))
        if not args.dry_run:
            path.write_text(species_yaml(dataclasses.replace(ov, learnset=tuple(new_learn))),
                            encoding="utf-8")
            wrote += 1

    table.sort(key=lambda r: (r[0] or 10**6))
    lo, hi = window
    print(f"Move:  {move_name}   Types: {', '.join(sorted(types))}   "
          f"Split: {args.split}   Window: {lo}-{hi}")
    print(f"{'DEX':>4}  {'SPECIES':<20} {'LEVEL':<6} NOTE")
    for dex, cid, lvl, note in table:
        print(f"{dex if dex is not None else '?':>4}  {cid:<20} {lvl:<6} {note}")
    verb = "Would write" if args.dry_run else "Wrote"
    print(f"\n{verb}: {len([r for r in table if r[2] != '—'])} species")
    if args.dry_run:
        print("Dry run — nothing written. Re-run without --dry-run to apply.")


def _base_ls(snap: dict, cid: str) -> list[LearnsetMove]:
    return [LearnsetMove(level=e["level"], move=e["move"])
            for e in (snap["species"][cid].get("learnset") or [])]


if __name__ == "__main__":
    main()
