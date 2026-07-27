"""Guarantee every Pokemon a paced STAB movepool as it levels.

For each species, on the split of its highest attack stat, fill every band of
each STAB ladder with a move, spaced across level windows so a scaling STAB
option exists at each stage. STAB = effective types + ability-granted types
(Full Moon -> Dark/Fairy, High Noon -> Fire/Psychic; Mystic Power grants "all
moves STAB" but is treated as own-types-only — filling 18 ladders is nonsense).

Rules (approved with Chris):
  * Expected range = five level windows, one per power band (Scheme A, even
    fifths of L1-70). A gap is filled with the canonical rung for that
    (type, split, band) cell at a free level inside the band's window.
  * Fill the HIGHEST attack-stat split fully; the other split is left as-is
    (existing moves kept, not force-filled).
  * <= 4 moves at L1: keep the 4 lowest-band (status first), bump the rest to
    early levels. No move learned past L70.
  * Only ADD — never remove an existing STAB move (dedup/order is the sibling
    learnset_ladder pass, run afterward).

Editorial tool over the Ruleset, stdlib + PyYAML, no app import surface.

  python scripts/stab_pacing.py plan [id...]   # dry-run: show adds/moves per species
  python scripts/stab_pacing.py write [id...]   # rewrite ruleset/species/*.yaml
  python scripts/stab_pacing.py audit           # report species still missing rungs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import move_coverage as mc  # noqa: E402
import learnset_ladder as ll  # noqa: E402

BANDS = ["≤50", "51-75", "76-90", "91-110", ">110"]
WINDOWS = {  # Scheme A — even fifths of L1-70
    "≤50": (1, 14),
    "51-75": (15, 28),
    "76-90": (29, 42),
    "91-110": (43, 56),
    ">110": (57, 70),
}
ABILITY_STAB = {  # ability name -> extra STAB types it grants
    "Full Moon": ["Dark", "Fairy"],
    "High Noon": ["Fire", "Psychic"],
    # "Mystic Power" grants all-move STAB — deliberately omitted (own types only).
}
MAX_L1 = 4
MAX_LEVEL = 70
BALANCED_DELTA = 10  # |atk - spa| <= this counts as a balanced dual-attacker


def build_rung_map(pool: mc.Pool, base_ids: set[str]) -> dict[tuple, str]:
    """One canonical rung move per (type, split, band): prefer our net-new
    design, then most-learned, then name."""
    import collections

    cells: dict[tuple, list] = collections.defaultdict(list)
    for mid, mv in pool.moves.items():
        if not mc.is_ladder_eligible(mv):
            continue
        band = mc.band_of(mv.get("power"))
        if band is None:
            continue
        net_new = mid in pool.custom and mid not in base_ids
        cells[(mv["type"], mv["category"], band)].append(
            (not net_new, -pool.learners.get(mid, 0), mv["name"])
        )
    return {k: sorted(v)[0][2] for k, v in cells.items()}


def merged_species(base: dict, species_dir: Path) -> dict[str, dict]:
    """Base species merged with each override YAML (non-None fields win)."""
    out = {sid: dict(sp) for sid, sp in base["species"].items()}
    for path in sorted(species_dir.glob("*.yaml")):
        y = ll.mc._load_yaml(path) if hasattr(ll.mc, "_load_yaml") else None
        if y is None:
            import yaml

            y = yaml.safe_load(path.read_text("utf-8")) or {}
        sid = y.get("chrooked_id") or path.stem
        entry = dict(out.get(sid, {}))
        for k, v in y.items():
            if v is not None:
                if k == "abilities" and isinstance(v, dict):
                    ab = dict(entry.get("abilities") or {})
                    ab.update({kk: vv for kk, vv in v.items() if vv is not None})
                    entry["abilities"] = ab
                elif k == "stats" and isinstance(v, dict):
                    st = dict(entry.get("stats") or {})
                    st.update({kk: vv for kk, vv in v.items() if vv is not None})
                    entry["stats"] = st
                else:
                    entry[k] = v
        out[sid] = entry
    return out


def stab_types(sp: dict) -> list[str]:
    types = list(sp.get("types") or [])
    ab = sp.get("abilities") or {}
    for name in (ab.get("primary"), ab.get("secondary"), ab.get("hidden")):
        for t in ABILITY_STAB.get(name or "", []):
            if t not in types:
                types.append(t)
    return types


def chosen_splits(sp: dict) -> list[str]:
    """The split(s) to force-fill: highest attack stat; the other is left as-is."""
    st = sp.get("stats") or {}
    atk, spa = st.get("atk", 0), st.get("spa", 0)
    return ["physical"] if atk >= spa else ["special"]


def existing_cells(ctx: ll.Ctx, rows: list[tuple[int, str]]) -> set[tuple]:
    cells = set()
    for _, mv in rows:
        r = ctx.rung(mv)
        if r is not None:
            cells.add((r[0], r[1], r[2]))
    return cells


def plan_species(
    sp: dict, rows: list[tuple[int, str]], ctx: ll.Ctx, rung_map: dict
) -> list[tuple[int, str]]:
    """Return [(level, move)] additions to fill missing STAB rungs.

    `sp` supplies types/stats/abilities; `rows` is the mon's learnset as
    (level, move) tuples.
    """
    have = existing_cells(ctx, rows)
    used_levels = [lvl for lvl, _ in rows]
    splits = chosen_splits(sp)
    types = stab_types(sp)
    adds: list[tuple[int, str]] = []
    # per band, fill each STAB type/split missing that cell, spacing within window
    for band in BANDS:
        lo, hi = WINDOWS[band]
        needers = [
            (typ, split)
            for split in splits
            for typ in types
            if (typ, split, band) in rung_map and (typ, split, band) not in have
        ]
        for i, (typ, split) in enumerate(needers):
            move = rung_map[(typ, split, band)]
            # first free-ish level in the window, offset per needer
            target = min(hi, lo + i * 2)
            while target in used_levels and target < hi:
                target += 1
            used_levels.append(target)
            adds.append((target, move))
            have.add((typ, split, band))
    return adds


def band_key(ctx: ll.Ctx, move: str) -> int:
    """Sort rank for L1 keep-priority: status/non-ladder (0) then band index+1."""
    r = ctx.rung(move)
    return 0 if r is None else BANDS.index(r[2]) + 1


def normalize(rows: list[tuple[int, str]], ctx: ll.Ctx) -> list[tuple[int, str]]:
    """Enforce <=4 L1 moves (keep lowest-band, bump rest) and no move past L70."""
    rows = [(min(lvl, MAX_LEVEL), mv) for lvl, mv in rows]
    l1 = [(lvl, mv) for lvl, mv in rows if lvl == 1]
    if len(l1) > MAX_L1:
        l1_sorted = sorted(l1, key=lambda t: band_key(ctx, t[1]))
        bump = l1_sorted[MAX_L1:]
        rows = [(lvl, mv) for lvl, mv in rows if lvl != 1]
        rows += [(1, mv) for _, mv in l1_sorted[:MAX_L1]]
        used = {lvl for lvl, _ in rows}
        nxt = 2
        for _, mv in bump:
            while nxt in used and nxt < MAX_LEVEL:
                nxt += 1
            rows.append((nxt, mv))
            used.add(nxt)
            nxt += 1
    return sorted(rows, key=lambda t: t[0])


def cmd(action: str, ids: list[str]) -> int:
    base = json.loads((mc.RULESET / ".base" / "1.11.2.json").read_text("utf-8"))
    pool = mc.build_pool()
    rung_map = build_rung_map(pool, set(base["moves"]))
    ctx = ll.Ctx()
    merged = merged_species(base, mc.RULESET / "species")

    total_adds = changed = 0
    for path in ll.species_files():
        text = path.read_text("utf-8")
        parsed = ll.parse_learnset(text)
        if not parsed:
            continue
        sid = path.stem
        if ids and sid not in ids:
            continue
        sp = merged.get(sid)
        if not sp:
            continue
        pre, indent, rows, post = parsed
        adds = plan_species(sp, rows, ctx, rung_map)
        # normalize runs even with no adds — the L1/L70 caps are universal.
        new_rows = normalize(rows + adds, ctx)
        if new_rows == rows:
            continue
        changed += 1
        total_adds += len(adds)
        if action == "plan":
            addstr = ", ".join(f"L{l}:{m}" for l, m in sorted(adds))
            print(f"{sid:20} +{len(adds):2}  {addstr}")
        elif action == "write":
            body = pre + ll.emit_block(indent, new_rows) + post
            path.write_text("\n".join(body) + "\n", encoding="utf-8")
    verb = {"plan": "would add", "write": "added"}[action]
    print(f"\n{verb} {total_adds} rungs across {changed} species")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "write"):
        p = sub.add_parser(name)
        p.add_argument("ids", nargs="*", help="limit to these chrooked_ids")
    args = ap.parse_args()
    return cmd(args.cmd, args.ids)


if __name__ == "__main__":
    raise SystemExit(main())
