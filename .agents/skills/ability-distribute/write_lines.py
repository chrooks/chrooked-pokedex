"""Write one ability into a slot for many species, then apply and read back.

    .venv/bin/python .claude/skills/ability-distribute/write_lines.py "Night Stalker" \
        murkrow=primary honchkrow=primary zubat=hidden ... [--target PATH] [--no-apply]

Each species gets a merge-PUT through /api/species/{id} (whole lines are the
caller's job: list every stage). Then the host CLI apply runs against the Rejuv
target (the container image lags the harness — never apply from the web API)
and every written slot is read back from patch/Definitions/montext.rb.
Exit 1 on any mismatch. Chris commits himself.
"""
import argparse, json, re, subprocess, sys, urllib.error, urllib.request

API = "http://localhost:8000"

def get(p): return json.load(urllib.request.urlopen(API + p))
def put(p, b):
    r = urllib.request.Request(API + p, data=json.dumps(b).encode(),
                               headers={"content-type": "application/json"}, method="PUT")
    return json.load(urllib.request.urlopen(r))

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ability")
    ap.add_argument("assign", nargs="+", help="species=primary|secondary|hidden")
    ap.add_argument("--target", default="/home/chrooks/projects/rejuv-game")
    ap.add_argument("--no-apply", action="store_true")
    a = ap.parse_args()
    dex = {s["chrooked_id"]: s for s in get("/api/dex")}
    plan = dict(x.split("=", 1) for x in a.assign)
    for cid, slot in plan.items():
        try:
            s = {k: v for k, v in get("/api/species/" + cid).items() if v is not None}
        except urllib.error.HTTPError:
            s = {"name": dex[cid]["name"], "chrooked_id": cid}
        cur = dict(dex[cid]["abilities"]); before = cur.get(slot); cur[slot] = a.ability
        s["abilities"] = cur; put("/api/species/" + cid, s)
        print(f"{cid:12} {slot:9} {before} -> {a.ability}")
    if a.no_apply:
        return
    subprocess.run([".venv/bin/chrooked-pokedex", "apply", "--target", a.target, "--engine", "rejuv"], check=True)
    src = open(f"{a.target}/patch/Definitions/montext.rb", encoding="utf-8").read()
    sym = re.sub(r"[^A-Z0-9]", "", a.ability.upper()); ok = True
    idx = {0: "primary", 1: "secondary"}
    for cid, slot in plan.items():
        m = re.search(r'if MONHASH\.dig\(:%s, "[^"]+"\)(.*?)\nelse' % cid.upper(), src, re.S)
        blk = m.group(1) if m else ""
        pat = r"\[:HiddenAbility\] = :(\w+)" if slot == "hidden" else r"\[:Abilities\]\[%d\] = :(\w+)" % [k for k, v in idx.items() if v == slot][0]
        g = re.search(pat, blk); hit = g and g.group(1) == sym; ok &= bool(hit)
        print(f"{cid:12} {slot:9} {'MATCH' if hit else 'MISMATCH: ' + (g.group(1) if g else 'not written')}")
    print("ALL OK" if ok else "READBACK FAILED"); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
