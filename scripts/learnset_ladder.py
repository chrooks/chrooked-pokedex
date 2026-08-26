"""Audit and fix learnset ladder ORDER across all species.

A species' STAB ladder for a (type, split) should teach its damaging rungs in
ascending base-power band as level rises. The one defect this pass repairs:

  * INVERSION  — a later-level rung sits in a LOWER power band than an earlier one.

Scope (decided with Chris):
  * Full ladder: canon + custom rungs are sorted together.
  * L0/L1 are FIXED ANCHORS (starting / on-evolution kit) — never moved, never
    dropped. Only EARNED rungs (level >= 2) are resequenced.
  * Reorder reuses the ladder's own existing level slots (no new levels invented;
    non-ladder moves keep their levels).
  * NOTHING is ever deleted. The old same-band dedup was RETIRED (2026-08-26,
    Chris's ruling): it was built for mass-distributed filler, but after the
    multi-hit rebanding it aimed at hand-placed customs (it wanted to delete
    Gauss Cannon from Vikavolt because canon Discharge shared the cell).
    Redundant rungs are a makeover-time editorial call, not a script's.

Read-only editorial tool over the Ruleset, like scripts/move_coverage.py:
stdlib + PyYAML, no import surface into the app.

  python scripts/learnset_ladder.py audit          # report violations, exit 1 if any
  python scripts/learnset_ladder.py fix             # dry-run: show what would change
  python scripts/learnset_ladder.py fix --write     # rewrite ruleset/species/*.yaml
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import move_coverage as mc  # noqa: E402

RANK = {label: i for i, label in enumerate(mc.BAND_LABELS)}
ANCHOR_MAX = 1  # levels <= this are fixed pre-load kit
ROW_RE = re.compile(r"^(\s*)-\s*\{\s*level:\s*(\d+),\s*move:\s*(.+?)\s*\}\s*$")


class Ctx:
    """Resolved move universe, built once.

    A rung is NET-NEW when we invented it: it carries a ruleset/moves file
    (pool.custom) and has no base-game entry. A merely *rebalanced* canon move
    (Body Slam, Energy Ball) also has a ruleset file but IS in the base — it
    counts as canon for keep/drop, so dedup never strips it.
    """

    def __init__(self) -> None:
        base = json.loads(
            (mc.RULESET / ".base" / "1.11.2.json").read_text("utf-8")
        )
        base_ids = set(base["moves"])
        pool = mc.build_pool()
        self.by_name = {
            m["name"].casefold(): m for m in pool.moves.values() if m.get("name")
        }
        self.net_new = {
            pool.moves[c]["name"].casefold()
            for c in pool.custom
            if c not in base_ids and pool.moves.get(c, {}).get("name")
        }

    def rung(self, move_name: str):
        """Return (type, split, band, is_net_new) for a ladder rung, else None."""
        mv = self.by_name.get(move_name.casefold())
        if not mv or not mc.is_ladder_eligible(mv):
            return None
        band = mc.band_of(mc.effective_power(mv))
        if band is None:
            return None
        return mv["type"], mv["category"], band, move_name.casefold() in self.net_new


def parse_learnset(text: str):
    """Return (pre_lines, indent, rows, post_lines) or None if no learnset block.

    rows are [(level:int, move:str)] in file order; the block is the contiguous
    run of ``- { level, move }`` lines following ``learnset:``.
    """
    lines = text.splitlines()
    try:
        head = next(i for i, ln in enumerate(lines) if ln.rstrip() == "learnset:")
    except StopIteration:
        return None
    rows: list[tuple[int, str]] = []
    indent = "  "
    end = head + 1
    for i in range(head + 1, len(lines)):
        m = ROW_RE.match(lines[i])
        if not m:
            break
        indent = m.group(1)
        rows.append((int(m.group(2)), m.group(3)))
        end = i + 1
    if not rows:
        return None
    return lines[: head + 1], indent, rows, lines[end:]


def transform(rows: list[tuple[int, str]], ctx: Ctx) -> list[tuple[int, str]] | None:
    """Reorder inverted ladders in place. Return new rows, or None if unchanged.

    Never deletes a row — the dedup half was retired (see module docstring).
    """
    # Tag each row with its ladder identity (or None for non-ladder moves).
    tagged = [(lvl, mv, ctx.rung(mv)) for lvl, mv in rows]

    # Only touch (type, split) ladders we actually modified — those carrying at
    # least one custom rung. Pure-canon vanilla ladders are out of scope.
    ours = {
        (r[0], r[1]) for _, _, r in tagged if r is not None and r[3]
    }
    if not ours:
        return None

    kept = tagged

    # --- reorder: earned ladder rungs, per (type, split), reuse level slots ---
    groups: dict[tuple, list[int]] = {}
    for idx, (lvl, mv, r) in enumerate(kept):
        if r is not None and lvl > ANCHOR_MAX and (r[0], r[1]) in ours:
            groups.setdefault((r[0], r[1]), []).append(idx)
    new_level = {idx: lvl for idx, (lvl, _, _) in enumerate(kept)}
    for members in groups.values():
        if len(members) < 2:
            continue
        slots = sorted(kept[i][0] for i in members)
        order = sorted(members, key=lambda i: (RANK[kept[i][2][2]], kept[i][0]))
        for slot, i in zip(slots, order):
            new_level[i] = slot

    out = sorted(
        ((new_level[i], kept[i][1]) for i in range(len(kept))),
        key=lambda t: t[0],
    )
    return out if out != rows else None


def violations(rows: list[tuple[int, str]], ctx: Ctx):
    """Return inversions for one species' earned ladder (level >= 2)."""
    groups: dict[tuple, list] = {}
    for lvl, mv in rows:
        r = ctx.rung(mv)
        if r is None or lvl <= ANCHOR_MAX:
            continue
        groups.setdefault((r[0], r[1]), []).append((lvl, mv, r[2], r[3]))
    inv = []
    for (typ, split), items in groups.items():
        if not any(isc for _, _, _, isc in items):  # only ladders we touched
            continue
        items.sort(key=lambda t: (t[0], RANK[t[2]]))
        peak = -1
        for lvl, mv, band, _ in items:
            if RANK[band] < peak:
                inv.append((typ, split, items))
                break
            peak = max(peak, RANK[band])
    return inv


def emit_block(indent: str, rows: list[tuple[int, str]]) -> list[str]:
    return [f"{indent}- {{ level: {lvl}, move: {mv} }}" for lvl, mv in rows]


def species_files() -> list[Path]:
    return sorted((mc.RULESET / "species").glob("*.yaml"))


def cmd_audit(ctx: Ctx) -> int:
    total_inv = affected = 0
    for path in species_files():
        parsed = parse_learnset(path.read_text(encoding="utf-8"))
        if not parsed:
            continue
        _, _, rows, _ = parsed
        inv = violations(rows, ctx)
        if inv:
            affected += 1
            total_inv += len(inv)
            for typ, split, items in inv:
                seq = " ".join(f"L{l}:{m}[{b}]" for l, m, b, _ in items)
                print(f"INV  {path.stem:20} {typ:8} {split:8} {seq}")
    print(f"\n{total_inv} inversions, {affected} species")
    return 1 if total_inv else 0


def cmd_fix(ctx: Ctx, write: bool) -> int:
    changed = 0
    for path in species_files():
        text = path.read_text(encoding="utf-8")
        parsed = parse_learnset(text)
        if not parsed:
            continue
        pre, indent, rows, post = parsed
        new_rows = transform(rows, ctx)
        if new_rows is None:
            continue
        changed += 1
        print(f"{'WRITE' if write else 'PLAN '} {path.stem}")
        if write:
            body = pre + emit_block(indent, new_rows) + post
            path.write_text("\n".join(body) + "\n", encoding="utf-8")
    verb = "rewrote" if write else "would change"
    print(f"\n{verb} {changed} species files")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit", help="report ladder violations; exit 1 if any")
    fix = sub.add_parser("fix", help="dedup + resequence learnset ladders")
    fix.add_argument("--write", action="store_true", help="rewrite files in place")
    args = ap.parse_args()
    ctx = Ctx()
    if args.cmd == "audit":
        return cmd_audit(ctx)
    return cmd_fix(ctx, args.write)


if __name__ == "__main__":
    raise SystemExit(main())
