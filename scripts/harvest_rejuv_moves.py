"""Gated harvest of Rejuv-native moves into the Ruleset move pool.

Rejuv ships bespoke moves (Wake-Up Shock, Aquabatics, ...) that exist only as
engine symbols in its movetext, so the design pool, the learnset editor, and
the loader all reject them. This script proposes them; it NEVER writes without
an explicit pick — the harvesting decision stays with the human.

  .venv/bin/python scripts/harvest_rejuv_moves.py            # list candidates
  .venv/bin/python scripts/harvest_rejuv_moves.py --write wakeupshock aquabatics

A written move lands as ruleset/moves/<slug>.yaml with an ``aka: {rejuv: SYM}``
hint, so a Rejuv apply resolves the existing symbol instead of creating one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from chrooked_pokedex.seed.neutralize import slug  # noqa: E402

MOVETEXT_SUBPATH = "Scripts/Rejuv/Definitions/movetext.rb"
# Story/boss/animation entries that must never enter the design pool.
JUNK_SYMBOL = re.compile(r"PROMISED|ANIMATION")

_BLOCK = re.compile(
    r"^  :(?P<sym>[A-Za-z0-9_]+) => \{(?P<body>.*?)^  \},", re.M | re.S
)
_FIELD = re.compile(r":(?P<key>\w+) => (?P<val>\"[^\"]*\"|:\w+|[\d.]+|true|false)")


def _rejuv_movetext() -> Path:
    targets = json.loads((ROOT / "targets.json").read_text())
    for t in targets:
        if t.get("engine") == "rejuv":
            return Path(t["path"]) / MOVETEXT_SUBPATH
    raise SystemExit("no rejuv target in targets.json")


def parse_moves(movetext: Path) -> list[dict]:
    moves = []
    for m in _BLOCK.finditer(movetext.read_text(encoding="utf-8")):
        fields = {f["key"]: f["val"] for f in _FIELD.finditer(m["body"])}
        name = fields.get("name", "").strip('"')
        if not name:
            continue
        moves.append(
            {
                "symbol": m["sym"],
                "name": name,
                "type": fields.get("type", ":NORMAL").lstrip(":").capitalize(),
                "category": fields.get("category", ":status").lstrip(":"),
                "power": int(float(fields.get("basedamage", "0"))),
                "accuracy": int(float(fields.get("accuracy", "0"))),
                "pp": int(float(fields.get("maxpp", "0"))),
                "description": fields.get("desc", "").strip('"'),
                "contact": fields.get("contact") == "true",
            }
        )
    return moves


def known_slugs() -> set[str]:
    snap = json.loads((ROOT / "ruleset/.base/1.11.2.json").read_text())
    return set(snap["moves"]) | {p.stem for p in (ROOT / "ruleset/moves").glob("*.yaml")}


def candidates() -> list[dict]:
    known = known_slugs()
    out = []
    for mv in parse_moves(_rejuv_movetext()):
        is_junk = (
            JUNK_SYMBOL.search(mv["symbol"])
            or "ANIMATION" in mv["name"]
            or "Z-Power" in mv["description"]
        )
        if is_junk or slug(mv["name"]) in known:
            continue
        out.append({**mv, "slug": slug(mv["name"])})
    return sorted(out, key=lambda m: m["slug"])


def write_move(mv: dict) -> Path:
    path = ROOT / "ruleset/moves" / f"{mv['slug']}.yaml"
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    lines = [
        f"name: {mv['name']}",
        f"chrooked_id: {mv['slug']}",
        f"aka: {{ rejuv: {mv['symbol']} }}",
        f"type: {mv['type']}",
        f"category: {mv['category']}",
        f"power: {mv['power']}",
        f"accuracy: {mv['accuracy']}",
        f"pp: {mv['pp']}",
        f"description: \"{mv['description']}\"",
    ]
    if mv["contact"]:
        lines.append("flags: [contact]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", nargs="+", metavar="SLUG",
                    help="write these candidate slugs into ruleset/moves/ (explicit picks only)")
    args = ap.parse_args()
    cands = candidates()

    if not args.write:
        print(f"{len(cands)} Rejuv-native move(s) not in the pool (nothing written):\n")
        for mv in cands:
            print(f"  {mv['slug']:<22} {mv['name']:<22} {mv['type']:<9} "
                  f"{mv['category']:<9} BP {mv['power']:<4} acc {mv['accuracy']:<4} "
                  f"{mv['description'][:60]}")
        print("\nharvest with: --write <slug> [<slug> ...]")
        return

    by_slug = {mv["slug"]: mv for mv in cands}
    unknown = [s for s in args.write if s not in by_slug]
    if unknown:
        raise SystemExit(f"not harvestable candidates: {', '.join(unknown)}")
    for s in args.write:
        print("wrote", write_move(by_slug[s]))


if __name__ == "__main__":
    main()
