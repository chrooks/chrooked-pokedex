"""Dump the merged move and ability pools (customs tagged) for the blind-design agent.

    .venv/bin/python .claude/skills/blind-design/pool_dump.py <out-dir>

Writes <out-dir>/moves-pool.txt and <out-dir>/abilities-pool.txt. Re-run after
creating a move or ability mid-session so the agent sees it.
"""
import sys
from pathlib import Path

from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.web import dex as dexmod
from chrooked_pokedex.web import snapshot as snapmod
from chrooked_pokedex.web.learnset_skeleton import is_battle_gimmick


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    snapshot = snapmod.load_snapshot(Path("ruleset/.base/1.11.2.json"))
    ruleset = Ruleset.load(Path("ruleset"))

    pool = [r for r in dexmod.build_move_pool(snapshot, ruleset) if not is_battle_gimmick(r)]
    lines = []
    for r in sorted(pool, key=lambda r: r["move"]):
        eff = (r.get("effect") or "").replace("\n", " ")
        desc = (r.get("description") or "").replace("\n", " ")[:90]
        tag = " [CUSTOM]" if r.get("custom") else ""
        lines.append(f"{r['move']} | {r.get('type')} | {r.get('category')} | BP {r.get('power')} | acc {r.get('accuracy')} | {eff} | {desc}{tag}")
    (out / "moves-pool.txt").write_text("\n".join(lines) + "\n")

    abilities = dexmod.build_abilities(snapshot, ruleset)
    alines = []
    for a in sorted(abilities, key=lambda a: a["name"]):
        tag = " [CUSTOM]" if a.get("custom") else ""
        alines.append(f"{a['name']} | {(a.get('description') or '').strip()}{tag}")
    (out / "abilities-pool.txt").write_text("\n".join(alines) + "\n")
    print(f"{len(lines)} moves, {len(alines)} abilities -> {out}")


if __name__ == "__main__":
    main()
