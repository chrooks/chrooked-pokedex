"""Scale pre-evo stats to match a reworked final evo.

Enforces step 3 of the evolution-line default in CLAUDE.md: when a final evo's
stats are redesigned, every pre-evo takes the **same BST delta** against its own
canon BST, redistributed in the final evo's stat proportions so the whole line
reads as one role (the dump stat stays the dump stat).

"Reworked" means the ledger records a deliberate `stats` edit for that species.
A bare `stats:` override in the YAML is not enough — most of those were seeded
by diffing the Rejuv fork against base and are not Chris's designs.

  pre_new[k] = round((canon_BST + delta) * final_new[k] / final_new_BST)

Rounding drift lands on the largest stat so the target BST is exact.

Editorial tool over the Ruleset, stdlib only, no app import surface.

  python scripts/preevo_stats.py audit             # lines whose pre-evos lag
  python scripts/preevo_stats.py plan [id...]      # dry-run spread table
  python scripts/preevo_stats.py write [id...]     # rewrite ruleset/species/*.yaml

`id` is a FINAL EVO chrooked_id. With no ids, plan/write act on every line audit
reports.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_SNAPSHOT = ROOT / "ruleset" / ".base" / "1.11.2.json"
LEDGER = ROOT / "ruleset" / "ledger.ndjson"
SPECIES_DIR = ROOT / "ruleset" / "species"

KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
STAT_LINE = re.compile(r"^stats:\s*\{(.*)\}\s*$", re.M)
MAX_STAT = 255


def load_base() -> dict:
    return json.loads(BASE_SNAPSHOT.read_text())["species"]


def stat_edited_ids() -> set[str]:
    """Species whose stats were deliberately redesigned (ledger-recorded)."""
    out = set()
    for line in LEDGER.read_text().splitlines():
        row = json.loads(line)
        if row.get("kind") == "species" and "stats" in (row.get("fields") or {}):
            if row.get("chrooked_id"):
                out.add(row["chrooked_id"])
    return out


def species_path(cid: str) -> Path:
    return SPECIES_DIR / f"{cid}.yaml"


def read_override(cid: str) -> dict[str, int]:
    path = species_path(cid)
    if not path.exists():
        return {}
    match = STAT_LINE.search(path.read_text())
    if not match:
        return {}
    return {
        k.strip(): int(v)
        for k, v in (part.split(":") for part in match.group(1).split(","))
    }


def effective(base: dict, cid: str) -> dict[str, int]:
    """Canon stats with the Ruleset override laid on top."""
    stats = {k: base[cid]["stats"][k] for k in KEYS}
    stats.update(read_override(cid))
    return stats


def bst(stats: dict[str, int]) -> int:
    return sum(stats[k] for k in KEYS)


def preevo_chain(base: dict, cid: str) -> list[str]:
    """Every earlier stage, nearest first."""
    chain, cur = [], base.get(cid)
    while cur and (cur.get("evolution") or {}).get("from"):
        prev = cur["evolution"]["from"]
        cur = base.get(prev)
        if not cur:
            break
        chain.append(prev)
    return chain


def scale(canon: dict[str, int], delta: int, shape: dict[str, int]) -> dict[str, int]:
    """Give `canon` the shape of `shape`, at canon's BST plus `delta`, with every
    stat FLOORED at its canon value.

    A pre-evo is being upgraded, so no stat should come out worse than it started
    — without the floor, a slow bulky final evo drags its pre-evo's speed through
    the floor (Barboach 60 -> 20). Floored stats are pinned and the remaining
    budget re-spreads over the rest, repeatedly, until nothing else sinks below
    canon.
    """
    target = bst(canon) + delta
    if target <= bst(canon):  # the floors already spend the whole budget
        return dict(canon)

    free = list(KEYS)
    pinned: dict[str, int] = {}
    alloc: dict[str, float] = {}
    while free:
        budget = target - sum(pinned.values())
        weight = sum(shape[k] for k in free)
        if weight <= 0:
            break
        alloc = {k: budget * shape[k] / weight for k in free}
        sinking = [k for k in free if alloc[k] < canon[k]]
        if not sinking:
            break
        for k in sinking:
            pinned[k] = canon[k]
            free.remove(k)

    out = {k: canon[k] for k in KEYS}
    for k in free:
        out[k] = min(MAX_STAT, max(canon[k], round(alloc[k])))

    # Rounding drift rides on stats that still have room above their own floor.
    order = sorted(free, key=lambda k: out[k], reverse=True) or list(KEYS)
    drift = target - bst(out)
    for i in range(len(order) * MAX_STAT):
        if drift == 0:
            break
        k = order[i % len(order)]
        if drift > 0 and out[k] < MAX_STAT:
            out[k] += 1
            drift -= 1
        elif drift < 0 and out[k] > canon[k]:
            out[k] -= 1
            drift += 1
    return out


def reworked_lines(base: dict, edited: set[str]) -> list[tuple[str, int, list[str]]]:
    """(final evo, BST delta, its pre-evos) for every deliberately restatted line."""
    lines = []
    for cid in sorted(edited):
        entry = base.get(cid)
        if not entry or not entry.get("fully_evolved"):
            continue
        delta = bst(effective(base, cid)) - bst(entry["stats"])
        preevos = [
            pid
            for pid in preevo_chain(base, cid)
            if pid not in edited and species_path(pid).exists()
        ]
        if preevos:
            lines.append((cid, delta, preevos))
    return lines


def lagging_lines(base: dict, edited: set[str]) -> list[tuple[str, int, list[str]]]:
    """`reworked_lines`, narrowed to pre-evos not yet carrying the line's delta."""
    lines = []
    for cid, delta, preevos in reworked_lines(base, edited):
        behind = [
            pid
            for pid in preevos
            if bst(effective(base, pid)) - bst(base[pid]["stats"]) != delta
        ]
        if behind:
            lines.append((cid, delta, behind))
    return lines


def render_stats(stats: dict[str, int]) -> str:
    body = ", ".join(f"{k}: {stats[k]}" for k in KEYS)
    return f"stats: {{ {body} }}"


def write_stats(cid: str, stats: dict[str, int], canon: dict[str, int]) -> None:
    """Write only the fields that differ from canon — the Ruleset stores Overrides."""
    override = {k: stats[k] for k in KEYS if stats[k] != canon[k]}
    path = species_path(cid)
    text = path.read_text()
    if not override:
        path.write_text(STAT_LINE.sub("", text))
        return
    body = ", ".join(f"{k}: {v}" for k, v in override.items())
    line = f"stats: {{ {body} }}"
    if STAT_LINE.search(text):
        text = STAT_LINE.sub(line, text, count=1)
    elif "\nlearnset:" in text:
        text = text.replace("\nlearnset:", f"\n{line}\nlearnset:", 1)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text)


def plan_line(base: dict, cid: str, delta: int, preevos: list[str]) -> list[tuple]:
    shape = effective(base, cid)
    rows = []
    for pid in preevos:
        canon = {k: base[pid]["stats"][k] for k in KEYS}
        rows.append((pid, canon, scale(canon, delta, shape)))
    return rows


def print_plan(base: dict, cid: str, delta: int, rows: list[tuple]) -> None:
    shape = effective(base, cid)
    print(f"\n{cid}  (BST {bst(base[cid]['stats'])} -> {bst(shape)}, {delta:+})")
    header = " " * 22 + "".join(f"{k:>6}" for k in KEYS) + f"{'BST':>7}"
    print(header)
    print(f"  {cid + ' (final)':20}" + "".join(f"{shape[k]:>6}" for k in KEYS) + f"{bst(shape):>7}")
    for pid, canon, new in rows:
        print(f"  {pid + ' canon':20}" + "".join(f"{canon[k]:>6}" for k in KEYS) + f"{bst(canon):>7}")
        print(f"  {pid + ' NEW':20}" + "".join(f"{new[k]:>6}" for k in KEYS) + f"{bst(new):>7}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "plan", "write"))
    parser.add_argument("ids", nargs="*", help="final evo chrooked_ids")
    args = parser.parse_args()

    base = load_base()
    edited = stat_edited_ids()
    # Named ids act on the WHOLE line, lagging or not — that is how an already
    # scaled line gets re-derived after the formula changes. Bare plan/write
    # falls back to the lagging set.
    lines = reworked_lines(base, edited) if args.ids else lagging_lines(base, edited)

    if args.ids:
        wanted = set(args.ids)
        unknown = wanted - {cid for cid, _, _ in lines}
        if unknown:
            print(f"not a restatted line: {', '.join(sorted(unknown))}", file=sys.stderr)
        lines = [ln for ln in lines if ln[0] in wanted]

    if args.mode == "audit":
        print(f"{len(lines)} lines with pre-evos behind their final evo\n")
        print(f"{'final evo':24}{'BSTd':>6}  pre-evos")
        for cid, delta, preevos in lines:
            print(f"{cid:24}{delta:+6}  {', '.join(preevos)}")
        return 0

    for cid, delta, preevos in lines:
        rows = plan_line(base, cid, delta, preevos)
        print_plan(base, cid, delta, rows)
        if args.mode == "write":
            for pid, canon, new in rows:
                write_stats(pid, new, canon)
    if args.mode == "write":
        print(f"\nwrote {sum(len(p) for _, _, p in lines)} pre-evos across {len(lines)} lines")
    return 0


def _selftest() -> None:
    shape = {"hp": 100, "atk": 50, "def": 50, "spa": 50, "spd": 50, "spe": 50}
    canon = {"hp": 20, "atk": 20, "def": 20, "spa": 20, "spd": 20, "spe": 20}
    out = scale(canon, 30, shape)
    assert bst(out) == 150, out            # exact target BST after rounding fixup
    assert out["hp"] == max(out.values())  # role emphasis carried down
    assert scale(canon, 0, canon) == canon

    # The floor: a fast pre-evo under a slow final evo keeps its speed, and the
    # cost comes out of the stats that were gaining.
    slow = {"hp": 120, "atk": 85, "def": 80, "spa": 105, "spd": 95, "spe": 30}
    fast = {"hp": 50, "atk": 48, "def": 43, "spa": 46, "spd": 41, "spe": 60}
    floored = scale(fast, 47, slow)
    assert all(floored[k] >= fast[k] for k in KEYS), floored
    assert floored["spe"] == 60, floored
    assert bst(floored) == bst(fast) + 47, floored

    # Floors that swallow the whole budget degrade to canon, never below it.
    assert scale(fast, 0, slow) == fast
    print("ok")


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
