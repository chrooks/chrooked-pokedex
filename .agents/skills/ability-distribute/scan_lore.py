"""Scan real dex text for an ecological theme and print each hit line's ability slots.

    .venv/bin/python .claude/skills/ability-distribute/scan_lore.py \
        --keywords "nocturnal,at night,darkness,dusk" id1 id2 ...
    .venv/bin/python .claude/skills/ability-distribute/scan_lore.py --all --keywords "..."

Fetches lore for each id through scripts/lore_probe.py (cached under .cache/lore/,
parallel), greps every dex sentence for the keywords, and prints one block per
species: types, current primary / secondary / hidden, hit count, the sentences.
Read-only. ponytail: --all walks the whole dex; the first run is a long fetch,
every later run is offline.
"""
import argparse, glob, json, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "http://localhost:8000"
CACHE = Path(".cache/lore")

def probe(cid: str) -> str:
    out = subprocess.run([sys.executable, "scripts/lore_probe.py", cid, "--cap", "20000"],
                         capture_output=True, text=True)
    return out.stdout + out.stderr

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--keywords", required=True, help="comma-separated, case-insensitive")
    ap.add_argument("--all", action="store_true", help="scan every base-form species in the dex")
    ap.add_argument("--min-hits", type=int, default=1)
    a = ap.parse_args()
    dex = {s["chrooked_id"]: s for s in json.load(urllib.request.urlopen(API + "/api/dex"))}
    ids = a.ids or ([c for c in dex if re.fullmatch(r"[a-z]+", c)] if a.all else [])
    if not ids:
        sys.exit("give ids or --all")
    pat = re.compile(r"[^.\n]*\b(" + "|".join(re.escape(k.strip()) for k in a.keywords.split(",")) + r")\b[^.\n]*[.]", re.I)
    with ThreadPoolExecutor(8) as ex:
        texts = dict(zip(ids, ex.map(probe, ids)))
    for cid in ids:
        t = texts[cid]
        if "found        : False" in t or "FETCH FAILED" in t:
            print(f"MISSING {cid}"); continue
        hits = [m.group(0).strip() for m in pat.finditer(t)]
        if len(hits) < a.min_hits:
            continue
        ab = dex.get(cid, {}).get("abilities") or {}
        print(f"## {cid} | {dex.get(cid, {}).get('types')} | {ab.get('primary')} / {ab.get('secondary')} / {ab.get('hidden')} | hits={len(hits)}")
        for h in hits[:4]:
            print("   -", h[:160])

if __name__ == "__main__":
    main()
