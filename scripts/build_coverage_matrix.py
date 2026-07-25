"""Regenerate the interactive move-coverage matrix from the harness's data.

Writes .table-exports/move-coverage.html. Single source of truth for merge,
filters, bands, and learner counts is scripts/move_coverage.py — this script
only renders. Run after any batch:

    .venv/bin/python scripts/build_coverage_matrix.py
"""

from __future__ import annotations

import json
from pathlib import Path

from move_coverage import (
    BAND_LABELS,
    COMMON_THRESHOLD,
    band_of,
    build_pool,
    is_body_specific,
    is_ladder_eligible,
)

OUT = Path(__file__).resolve().parent.parent / ".table-exports" / "move-coverage.html"

TYPE_COLORS = {
    "Normal": "#9099a1", "Fire": "#ff9d55", "Water": "#4d90d5",
    "Electric": "#f4d23c", "Grass": "#63bc5a", "Ice": "#73cec0",
    "Fighting": "#ce4069", "Poison": "#ab6ac8", "Ground": "#d97845",
    "Flying": "#8fa8dd", "Psychic": "#f97176", "Bug": "#90c12c",
    "Rock": "#c7b78b", "Ghost": "#5269ac", "Dragon": "#0b6dc3",
    "Dark": "#5a5366", "Steel": "#5a8ea1", "Fairy": "#ec8fe6",
}

TEMPLATE = """<title>Move Ladder Coverage — Type × Split × BP</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--line:#e2e2e6;--muted:#6b7280;--empty:#e35b5b;--star:#b8860b;}
@media (prefers-color-scheme:dark){:root{--bg:#16171b;--fg:#e8e8ea;--line:#2c2e35;--muted:#9aa0ab;--empty:#ff6b6b;--star:#ffd34d;}}
:root[data-theme=dark]{--bg:#16171b;--fg:#e8e8ea;--line:#2c2e35;--muted:#9aa0ab;--empty:#ff6b6b;--star:#ffd34d}
:root[data-theme=light]{--bg:#fff;--fg:#1a1a1a;--line:#e2e2e6;--muted:#6b7280;--empty:#e35b5b;--star:#b8860b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
#wrap{padding:20px;max-width:1280px;margin:0 auto}
h1{font-size:19px;margin:0 0 4px}
p.sub{margin:0 0 14px;color:var(--muted);font-size:13px}
#controls{display:flex;gap:16px;align-items:center;margin-bottom:12px;flex-wrap:wrap;font-size:13px}
#controls label{display:flex;gap:6px;align-items:center;cursor:pointer;color:var(--muted)}
#thv{font-variant-numeric:tabular-nums;min-width:70px;color:var(--fg)}
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
td.empty{background:color-mix(in srgb,var(--empty) 16%,transparent)}
td.empty::after{content:'—';color:var(--empty);font-weight:700}
td.bodyonly{background:color-mix(in srgb,var(--star) 18%,transparent)}
.bd{color:var(--star);font-size:10px;vertical-align:super}
tr[data-cat=special] td:not(.type){background:color-mix(in srgb,var(--rowc) 7%,var(--bg))}
tr[data-cat=special] td.empty{background:color-mix(in srgb,var(--empty) 16%,var(--bg))}
</style>
<div id=wrap>
<h1 id=title-heading>Move Ladder Coverage — Type × Split × BP Band</h1>
<p class=sub>Rendered from <code>scripts/move_coverage.py</code> (base 1.11.2 ⊕ ruleset;
<span class=custom>★ = ruleset/moves/</span>, threshold-exempt). Ladder moves only.
<i>n</i> = species with the move at level-up. Red <b>—</b> = gap at the current threshold.
Amber cell = <b>body-only</b>: every common move needs a body plan (fang/punch/tail/blade<span class=bd>b</span>…) — wants a neutral companion.</p>
<div id=controls>
<label>Common = learned by ≥ <input id=th type=range min=0 max=40 value=__FLOOR__ step=1> <span id=thv></span></label>
<label><input type=checkbox id=gaps> Only rows with gaps</label>
<label><input type=checkbox id=phys checked> Physical</label>
<label><input type=checkbox id=spec checked> Special</label>
</div>
<div id=scroll><table id=coverage-table><thead></thead><tbody></tbody></table></div>
</div>
<script>
const P=__PAYLOAD__;
const {colors,bands,rows}=P;
const types=[...new Set(rows.map(r=>r.type))].sort();
const thead=document.querySelector('thead'),tbody=document.querySelector('tbody');
thead.innerHTML='<tr><th>Type</th><th>Split</th>'+bands.map(b=>'<th>'+b+'</th>').join('')+'</tr>';
function render(){
  const th=+document.getElementById('th').value;
  document.getElementById('thv').textContent=th+' mons';
  const gapsOnly=document.getElementById('gaps').checked;
  const cats=[];
  if(document.getElementById('phys').checked)cats.push('physical');
  if(document.getElementById('spec').checked)cats.push('special');
  const keep=rows.filter(r=>r.custom||r.n>=th);
  let out='';
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
        const bodyOnly=c.every(m=>m.body);
        return '<td'+(bodyOnly?' class=bodyonly':'')+'>'+c.map(m=>
        '<span class=mv>'+(m.custom?'<span class=custom>★</span> ':'')+m.name+(m.body?'<span class=bd>b</span>':'')+' <span class=bp>'+m.power+'</span> <span class=ln>n='+m.n+'</span></span>').join('')+'</td>'}).join('');
      out+=r+'</tr>';
    });
  }
  tbody.innerHTML=out||'<tr><td colspan=7 style="text-align:center;color:var(--muted);padding:20px">No rows.</td></tr>';
}
document.querySelectorAll('#controls input').forEach(el=>el.addEventListener('input',render));
render();
</script>"""


def main() -> None:
    """Render the matrix HTML from the harness's merged pool."""
    pool = build_pool()
    rows = [
        {
            "id": mid,
            "name": move["name"],
            "type": move["type"],
            "cat": move["category"],
            "power": move["power"],
            "band": band_of(move["power"]),
            "n": pool.learners.get(mid, 0),
            "custom": mid in pool.custom,
            "body": is_body_specific(move),
        }
        for mid, move in sorted(pool.moves.items())
        if is_ladder_eligible(move)
    ]
    payload = {"colors": TYPE_COLORS, "bands": list(BAND_LABELS), "rows": rows}

    # Cross-check: blanks in this payload at the floor must equal the harness's gaps.
    blanks = sum(
        1
        for t in {r["type"] for r in rows}
        for cat in ("physical", "special")
        for band in BAND_LABELS
        if not any(
            r
            for r in rows
            if r["type"] == t and r["cat"] == cat and r["band"] == band
            and (r["custom"] or r["n"] >= COMMON_THRESHOLD)
        )
    )
    html = (
        TEMPLATE
        .replace("__FLOOR__", str(COMMON_THRESHOLD))
        .replace("__PAYLOAD__", json.dumps(payload).replace("</script>", "<\\/script>"))
    )
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, "utf-8")
    print(f"wrote {OUT} ({len(rows)} ladder moves, {blanks} blank cells at n>={COMMON_THRESHOLD})")


if __name__ == "__main__":
    main()
