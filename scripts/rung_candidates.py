"""Render the rung-candidate matrix: what the suggest UI can ACTUALLY pick.

``scripts/move_coverage.py`` answers an editorial question — which (type, split,
band) cells hold a *curated* ladder rung, i.e. a mechanically ordinary move that
at least ``COMMON_THRESHOLD`` species learn. That is not the same set the
learnset suggestor offers the model. The suggestor's slot builder
(``web/learnset_skeleton.py``) draws from the whole merged move pool
(``web/dex.py::build_move_pool``) and drops only three things:

    * status moves and power<=1 sentinels (the ``attacking`` filter),
    * signature / species-locked moves (``SIGNATURE_MOVES``),
    * Chris's curated non-rungs (``learnset_rubric.json: rung_exclusions``),
    * Z-moves and Dynamax/G-Max moves (``is_battle_gimmick``).

No learner-count threshold, no multi-hit/charge/priority filter. So a cell the
coverage audit calls a gap can still have candidates here, and a cell it calls
filled usually has many more.

This script imports both sides on purpose — the app's real pool builder and the
real slot rules — so the export cannot drift from the UI:

    python scripts/rung_candidates.py            # rewrite .table-exports/move-coverage.html
    python scripts/rung_candidates.py --stdout   # print the HTML instead
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import move_coverage as mc  # noqa: E402  (sibling script: learner counts + ladder filter)
from chrooked_pokedex.model.ruleset import Ruleset  # noqa: E402
from chrooked_pokedex.web import dex, learnset_skeleton as sk  # noqa: E402
from chrooked_pokedex.web.snapshot import load_snapshot  # noqa: E402

OUT_PATH = ROOT / ".table-exports" / "move-coverage.html"

TYPE_COLORS: dict[str, str] = {
    "Normal": "#9099a1", "Fire": "#ff9d55", "Water": "#4d90d5",
    "Electric": "#f4d23c", "Grass": "#63bc5a", "Ice": "#73cec0",
    "Fighting": "#ce4069", "Poison": "#ab6ac8", "Ground": "#d97845",
    "Flying": "#8fa8dd", "Psychic": "#f97176", "Bug": "#90c12c",
    "Rock": "#c7b78b", "Ghost": "#5269ac", "Dragon": "#0b6dc3",
    "Dark": "#5a5366", "Steel": "#5a8ea1", "Fairy": "#ec8fe6",
}


def rung_candidates() -> list[dict[str, Any]]:
    """Every pool move a band rung could offer, with its cell and provenance.

    One row per move: the same row the skeleton would hand the model, plus the
    learner count and the ladder-eligibility verdict from the coverage audit so
    the export can show curated-vs-available side by side.
    """
    snapshot = load_snapshot(mc.BASE_SNAPSHOT)
    pool = dex.build_move_pool(snapshot, Ruleset.load(mc.RULESET))

    bands = sk._bands()
    exclusions = sk._rung_exclusions()
    audit = mc.build_pool(mc.RULESET)
    learners = {
        (move.get("name") or "").casefold(): audit.learners.get(mid, 0)
        for mid, move in audit.moves.items()
    }
    ladder_ok = {
        (move.get("name") or "").casefold(): mc.is_ladder_eligible(move)
        for mid, move in audit.moves.items()
    }

    rows: list[dict[str, Any]] = []
    for row in pool:
        name = row["move"]
        key = name.casefold()
        # The skeleton's rung filter, in the same order it applies it.
        if row["category"].casefold() not in ("physical", "special"):
            continue
        power = row["power"]
        if not isinstance(power, int) or power <= 1:
            continue
        if key in sk.SIGNATURE_MOVES or sk._slug(name) in exclusions:
            continue
        if sk.is_battle_gimmick(row):
            continue
        if row["type"] not in TYPE_COLORS:
            continue
        rows.append({
            "name": name,
            "type": row["type"],
            "cat": row["category"].casefold(),
            "power": power,
            "band": sk._band_of(power, bands)["label"],
            "n": learners.get(key, 0),
            "custom": bool(row["custom"]),
            "body": bool(mc.BODY_SPECIFIC_RE.search(name)),
            # False = the coverage audit would NOT call this a curated rung
            # (multi-hit, charge, priority, Z/Max...) yet suggest still offers it.
            "ladder": ladder_ok.get(key, False),
        })
    rows.sort(key=lambda r: (r["type"], r["cat"], r["power"], r["name"]))
    return rows


TEMPLATE = """<title>Rung Candidates — what the suggest UI can actually pick</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--line:#e2e2e6;--muted:#6b7280;--empty:#e35b5b;--star:#b8860b;--off:#7c8aa5;}
@media (prefers-color-scheme:dark){:root{--bg:#16171b;--fg:#e8e8ea;--line:#2c2e35;--muted:#9aa0ab;--empty:#ff6b6b;--star:#ffd34d;--off:#93a4c1;}}
:root[data-theme=dark]{--bg:#16171b;--fg:#e8e8ea;--line:#2c2e35;--muted:#9aa0ab;--empty:#ff6b6b;--star:#ffd34d;--off:#93a4c1}
:root[data-theme=light]{--bg:#fff;--fg:#1a1a1a;--line:#e2e2e6;--muted:#6b7280;--empty:#e35b5b;--star:#b8860b;--off:#7c8aa5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
#wrap{padding:20px;max-width:1280px;margin:0 auto}
h1{font-size:19px;margin:0 0 4px}
p.sub{margin:0 0 14px;color:var(--muted);font-size:13px}
#controls{display:flex;gap:16px;align-items:center;margin-bottom:12px;flex-wrap:wrap;font-size:13px}
#controls label{display:flex;gap:6px;align-items:center;cursor:pointer;color:var(--muted)}
#count{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}
#scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:860px}
th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}
thead th{position:sticky;top:0;background:var(--bg);font-size:12px;color:var(--muted);white-space:nowrap;z-index:2}
td.type{font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.35);white-space:nowrap}
.split{font-size:11px;color:var(--muted)}
.mv{display:block;font-size:12px;white-space:nowrap}
.bp{color:var(--muted);font-variant-numeric:tabular-nums}
.ln{color:var(--muted);font-size:10px}
.custom{color:var(--star);font-weight:700}
.mv.offladder{color:var(--off)}
td.empty{background:color-mix(in srgb,var(--empty) 16%,transparent)}
td.empty::after{content:'\\2014';color:var(--empty);font-weight:700}
td.bodyonly{background:color-mix(in srgb,var(--star) 18%,transparent)}
.bd{color:var(--star);font-size:10px;vertical-align:super}
tr[data-cat=special] td:not(.type){background:color-mix(in srgb,var(--rowc) 7%,var(--bg))}
tr[data-cat=special] td.empty{background:color-mix(in srgb,var(--empty) 16%,var(--bg))}
</style>
<div id=wrap>
<h1 id=title-heading>Rung Candidates — Type &times; Split &times; BP Band</h1>
<p class=sub>Every move the <b>suggest UI</b> can actually offer at each rung. Generated by
<code>scripts/rung_candidates.py</code>, which reads the real pool
(<code>web/dex.py::build_move_pool</code>, base 1.11.2 &oplus; ruleset) through the real slot rules
(<code>web/learnset_skeleton.py</code>). The suggestor applies <b>no learner threshold</b> — it drops only
status moves, power&le;1 sentinels, signature moves, the curated
<code>rung_exclusions</code>, and Z / Dynamax / G-Max moves.
<span class=custom>&#9733; = ruleset/moves/</span>.
<span class="mv offladder" style="display:inline">Grey</span> = offered here but NOT a curated ladder rung in
<code>scripts/move_coverage.py</code> (multi-hit, charge, priority&hellip;).
<i>n</i> = species with the move at level-up (informational only).
Red <b>&mdash;</b> = the suggestor has nothing for that rung and drops the slot.
Amber cell = <b>body-only</b>: every candidate needs a specific anatomy
(fang/punch/tail/blade<span class=bd>b</span>&hellip;).</p>
<div id=controls>
<label><input type=checkbox id=gaps> Only rows with gaps</label>
<label><input type=checkbox id=ladder> Curated ladder rungs only</label>
<label><input type=checkbox id=custom> Custom (&#9733;) only</label>
<label><input type=checkbox id=phys checked> Physical</label>
<label><input type=checkbox id=spec checked> Special</label>
<span id=count></span>
</div>
<div id=scroll><table id=coverage-table><thead></thead><tbody></tbody></table></div>
</div>
<script>
const P=__DATA__;
const {colors,bands,rows}=P;
const types=[...new Set(rows.map(r=>r.type))].sort();
const thead=document.querySelector('thead'),tbody=document.querySelector('tbody');
thead.innerHTML='<tr><th>Type</th><th>Split</th>'+bands.map(b=>'<th>'+b+'</th>').join('')+'</tr>';
function render(){
  const gapsOnly=document.getElementById('gaps').checked;
  const ladderOnly=document.getElementById('ladder').checked;
  const customOnly=document.getElementById('custom').checked;
  const cats=[];
  if(document.getElementById('phys').checked)cats.push('physical');
  if(document.getElementById('spec').checked)cats.push('special');
  const keep=rows.filter(r=>(!ladderOnly||r.ladder)&&(!customOnly||r.custom));
  let out='',shown=0;
  for(const t of types){
    const col=colors[t]||'#888';
    const built=[];
    for(const cat of cats){
      const cells=Object.fromEntries(bands.map(b=>[b,[]]));
      keep.filter(r=>r.type===t&&r.cat===cat).forEach(r=>{if(r.band)cells[r.band].push(r)});
      Object.values(cells).forEach(c=>c.sort((a,b)=>a.power-b.power||b.n-a.n));
      const hasGap=bands.some(b=>!cells[b].length);
      if(gapsOnly&&!hasGap) continue;
      built.push({cat,cells});
    }
    built.forEach((b,i)=>{
      let r='<tr data-cat='+b.cat+' style="--rowc:'+col+'">';
      if(i===0) r+='<td class=type rowspan='+built.length+' style="background:'+col+'">'+t+'</td>';
      r+='<td class=split>'+(b.cat==='physical'?'Phys':'Spec')+'</td>';
      r+=bands.map(k=>{const c=b.cells[k];if(!c.length)return '<td class=empty></td>';
        shown+=c.length;
        const bodyOnly=c.every(m=>m.body);
        return '<td'+(bodyOnly?' class=bodyonly':'')+'>'+c.map(m=>
        '<span class="mv'+(m.ladder?'':' offladder')+'">'+(m.custom?'<span class=custom>\\u2605</span> ':'')+m.name+(m.body?'<span class=bd>b</span>':'')+' <span class=bp>'+m.power+'</span> <span class=ln>n='+m.n+'</span></span>').join('')+'</td>'}).join('');
      out+=r+'</tr>';
    });
  }
  document.getElementById('count').textContent=shown+' candidates shown of '+rows.length;
  tbody.innerHTML=out||'<tr><td colspan=7 style="text-align:center;color:var(--muted);padding:20px">No rows.</td></tr>';
}
document.querySelectorAll('#controls input').forEach(el=>el.addEventListener('input',render));
render();
</script>
"""


def render_html(rows: list[dict[str, Any]]) -> str:
    payload = {
        "colors": TYPE_COLORS,
        "bands": [b["label"] for b in sk._bands()],
        "rows": rows,
    }
    return TEMPLATE.replace("__DATA__", json.dumps(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args(argv)

    rows = rung_candidates()
    html = render_html(rows)
    if args.stdout:
        print(html)
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    cells = {(r["type"], r["cat"], r["band"]) for r in rows}
    print(
        f"{OUT_PATH.relative_to(ROOT)}: {len(rows)} rung candidates, "
        f"{len(cells)}/{18 * 2 * 5} cells filled"
    )
    return 0


def demo() -> None:
    """Self-check: the export must be a superset of the curated ladder."""
    rows = rung_candidates()
    names = {r["name"].casefold() for r in rows}
    audit = mc.build_pool(mc.RULESET)
    exclusions = sk._rung_exclusions()
    for mid, move in audit.moves.items():
        if not mc.is_ladder_eligible(move):
            continue
        key = (move.get("name") or "").casefold()
        if key in sk.SIGNATURE_MOVES or sk._slug(move.get("name") or "") in exclusions:
            continue
        assert key in names, f"curated rung {move.get('name')!r} missing from the export"
    assert any(not r["ladder"] for r in rows), "no off-ladder candidates — filter is too tight"
    assert all(r["power"] > 1 for r in rows), "power<=1 sentinel leaked in"
    gimmicks = [
        r["name"] for r in rows
        if r["name"].startswith(("Max ", "G-Max ")) or r["name"] in (
            "Catastropika", "Malicious Moonsault", "Clangorous Soulblaze",
            "10,000,000 Volt Thunderbolt", "Let's Snuggle Forever",
        )
    ]
    assert not gimmicks, f"Z/Max moves still offered: {gimmicks}"
    print(f"ok: {len(rows)} candidates, superset of the curated ladder")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        raise SystemExit(main())
