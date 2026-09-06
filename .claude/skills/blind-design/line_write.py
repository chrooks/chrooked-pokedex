"""Write a final-stage learnset (and optional abilities/stats) to a whole evolution line,
apply to Rejuv from the host CLI, check the Apply Report for partials, and read every
stage back from the target. Exit 1 on any mismatch — commit only on 0.

    .venv/bin/python .claude/skills/blind-design/line_write.py garchomp \
        --rows "0:Draconic Fang,1:Sand Attack,5:Twister,..." \
        [--abilities "Rough Skin,Sand Rush,Apex Predator"] [--stats hp=65,atk=95,...] \
        [--skip-pre gible] [--target PATH]

Line rules (CLAUDE.md "Evolution-line default"): pre-evos get the list minus L0 rows;
megas/forms of the final stage mirror it with L0 kept; abilities/stats go to every
stage unless a stage is --skip-pre'd (branch-shared pre-evos are opt-in).
"""
import argparse, json, re, subprocess, sys, urllib.error, urllib.request

API = "http://localhost:8000"
def get(p): return json.load(urllib.request.urlopen(API + p))
def put(p, b):
    r = urllib.request.Request(API + p, data=json.dumps(b).encode(),
                               headers={"content-type": "application/json"}, method="PUT")
    return json.load(urllib.request.urlopen(r))
def sym(n): return re.sub(r"[^A-Z0-9]", "", (n or "").upper()).replace("HIGHJUMPKICK", "HIJUMPKICK")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("final"); ap.add_argument("--rows", required=True)
    ap.add_argument("--abilities"); ap.add_argument("--stats"); ap.add_argument("--skip-pre", default="")
    ap.add_argument("--target", default="/home/chrooks/projects/rejuv-game")
    a = ap.parse_args()
    dex = {s["chrooked_id"]: s for s in get("/api/dex")}
    rows = [(int(l), m.strip()) for l, m in (x.split(":", 1) for x in a.rows.split(","))]
    # walk the line
    cur = a.final
    while dex[cur].get("evolution"): cur = dex[cur]["evolution"]["from"].lower().replace(" ", "")
    line = [cur]
    while dex[line[-1]].get("evolves_into"): line.append(dex[line[-1]]["evolves_into"][0]["to"])
    pre = [c for c in line if c != a.final and c not in a.skip_pre.split(",")]
    forms = [c for c in dex if c.startswith(a.final) and c != a.final and ("mega" in c or "gmax" in c)]
    plan = {a.final: rows, **{c: rows for c in forms}, **{c: [r for r in rows if r[0]] for c in pre}}
    for cid, ls in plan.items():
        try: s = {k: v for k, v in get("/api/species/" + cid).items() if v is not None}
        except urllib.error.HTTPError: s = {"name": dex[cid]["name"], "chrooked_id": cid}
        s["learnset"] = [{"level": l, "move": m} for l, m in ls]
        if a.abilities and cid not in forms:
            p, sec, h = [x.strip() for x in a.abilities.split(",")]
            s["abilities"] = {"primary": p, "secondary": sec, "hidden": h}
        if a.stats and cid == a.final:
            s["stats"] = {k: int(v) for k, v in (x.split("=") for x in a.stats.split(","))}
        put("/api/species/" + cid, s); print(f"wrote {cid}: {len(ls)} rows")
    subprocess.run([".venv/bin/chrooked-pokedex", "apply", "--target", a.target, "--engine", "rejuv"], check=True)
    report = open(f"{a.target}/apply-report.md", encoding="utf-8").read()
    bad = [l for l in report.splitlines() if re.search(r"\|\s*(partial|blocked)\s*\|", l) and any(c in l for c in plan)]
    if bad:
        print("APPLY REPORT PARTIAL/BLOCKED:"); print("\n".join(bad)); sys.exit(1)
    src = open(f"{a.target}/patch/Definitions/montext.rb", encoding="utf-8").read()
    ok = True
    for cid, ls in plan.items():
        base = dex[cid]["name"].split()[0].upper()
        blocks = re.findall(r'if MONHASH\.dig\(:%s, "([^"]+)"\)(.*?)\nelse' % base, src, re.S)
        exp = sorted((l, sym(m)) for l, m in ls)
        hit = any(sorted((int(l), x) for l, x in re.findall(r"\[(\d+), :(\w+)\]", (re.search(r"\[:Moveset\] = (.*)", b) or [None, ""])[1])) == exp for _, b in blocks)
        ok &= hit; print(f"readback {cid:14} {'MATCH' if hit else 'MISMATCH'}")
    print("ALL OK" if ok else "READBACK FAILED"); sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
