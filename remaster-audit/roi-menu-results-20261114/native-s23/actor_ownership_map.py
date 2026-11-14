"""s23: Stage 2/3 enemy / boss / mid-boss / player-pod (gunpod) source-ownership map (light; JSON only).

  python -I actor_ownership_map.py <out_dir>

Per TEX of those families (from the pinned s23 full-stage coverage + stage-review): member, VRAM page, the stage-review
identity basis, keys drawn (live) / with complete live source / predicted only, keys authored in any frozen lane or s23
proposal, Stage-1-pack imports, the CLUT positions seen, and the exact capture trigger that closes the gap. Identity
statements are copied from the stage review (confidence kept); nothing is inferred beyond them.
"""
import hashlib, json, os, sys
from collections import defaultdict
from datetime import datetime, timezone
RA = "C:/github/Einhander/remaster-audit"; SR = RA + "/fullgame-prep/stage-review"
COV = RA + "/parallel-stages-20261114/s23/runs/fullstage-20261114T171029Z/fullstage-coverage.json"
FAMS = ("enemies / vehicles", "boss", "mid-boss", "player/pods/HUD globals (common 0/14, 0/11)")
TRIG = {"stage2": {"enemies / vehicles": "S2.md S2-1 stock-first dump P..S3s+600 incl. post-Drache window + S2-4 complete sources (119 post-Drache keys)",
                   "boss": "S2 boss window (Spinne candidate 1/36): AQ-03 boss marks + stock-first dump of 320-576,0 rewrites; full-rate draws",
                   "mid-boss": "Garnele: AQ-03 mid-boss marks; candidates 1/30 832/896,0 and 1/26 384,0",
                   "player/pods/HUD globals (common 0/14, 0/11)": "S2-1 dump (player/pod keys with Stage 2 CLUT phases) + S2-4 for 3955512F gunpod page / 8BA3BB4D HUD fades"},
        "stage3": {"enemies / vehicles": "S3.md S3-1 draw rows for 2/1 + 2/6 pages + stage3-source dump; S3-2 CLUT snapshots",
                   "boss": "Gecko/Gustav: AQ-03 boss marks with 2/8 320-576,0 rewrites + dump; separates the two bosses",
                   "mid-boss": "Gecko vs Gustav separation needs AQ-03 marks",
                   "player/pods/HUD globals (common 0/14, 0/11)": "S3 stage3-source dump of 0/14 player/pod keys with Stage 3 CLUTs"}}
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def main(out):
    os.makedirs(out, exist_ok=True)
    cov = json.load(open(COV, encoding="utf-8"))
    res = dict(owner="claude-einhander-s23", created_utc=datetime.now(timezone.utc).isoformat(), coverage=dict(path=COV, sha256=sha(COV)), stages={})
    for st in ("stage2", "stage3"):
        fams = {f["family"]: f for f in json.load(open(f"{SR}/{st}/families.json", encoding="utf-8"))["families"]}
        live = json.load(open(f"{SR}/{st}/keys-live.json", encoding="utf-8"))["keys"] if os.path.exists(f"{SR}/{st}/keys-live.json") else {}
        pred = json.load(open(f"{SR}/{st}/keys-predicted-static.json", encoding="utf-8"))["keys"]
        pred = pred if isinstance(pred, dict) else {e["key"]: e for e in pred}
        tex = defaultdict(lambda: dict(keys=0, drawn=0, complete=0, predicted=0, authored=0, imported=0, authored_in=set(), clut_xy=set(), members=set(), pages=set()))
        for k, r in cov["stages"][st]["rows"].items():
            if r["family"] not in FAMS:
                continue
            t = tex[(r["family"], k[:8])]
            t["keys"] += 1
            t["drawn"] += r["source"] in ("live_drawn", "complete_live_source")
            t["complete"] += r["source"] == "complete_live_source"
            t["predicted"] += r["source"] == "predicted_static"
            t["authored"] += bool(r["authored"]); t["imported"] += bool(r.get("imported"))
            t["authored_in"].update(r["authored"])
            e = live.get(k) or pred.get(k) or {}
            for c in (e.get("clut_xy") if isinstance(e.get("clut_xy"), list) and e.get("clut_xy") and isinstance(e["clut_xy"][0], list) else [e.get("clut_xy")]):
                if c: t["clut_xy"].add(tuple(c))
            m = (e.get("tex_static") or {}).get("member") or e.get("tex_member")
            if m: t["members"].add(m)
            pxy = e.get("page_xy")
            if pxy: t["pages"].add(tuple(pxy[0] if isinstance(pxy[0], list) else pxy))
        rows = []
        for (fam, tx), t in sorted(tex.items(), key=lambda x: (x[0][0], -x[1]["drawn"], -x[1]["keys"])):
            rows.append(dict(family=fam, tex=tx, members=sorted(t["members"]), pages=sorted(map(list, t["pages"])), keys=t["keys"], drawn=t["drawn"],
                             complete_live_source=t["complete"], predicted_only=t["predicted"], authored=t["authored"], imported=t["imported"],
                             authored_in=sorted(t["authored_in"]), clut_positions=len(t["clut_xy"])))
        res["stages"][st] = dict(family_basis={f: dict(members=fams[f].get("members"), pages=fams[f].get("vram_pages"), basis=fams[f].get("basis"), note=fams[f].get("note")) for f in FAMS if f in fams},
                                 capture_trigger=TRIG[st], tex=rows,
                                 totals={f: dict(tex=sum(1 for r in rows if r["family"] == f), keys=sum(r["keys"] for r in rows if r["family"] == f),
                                                 drawn=sum(r["drawn"] for r in rows if r["family"] == f), authored=sum(r["authored"] for r in rows if r["family"] == f))
                                         for f in FAMS})
    p = out + "/actor-ownership.json"; json.dump(res, open(p, "w", encoding="utf-8"), indent=1)
    md = ["# Stage 2/3 enemy, boss and player-pod source ownership (claude-einhander-s23)", "", f"Generated {res['created_utc']}. Identities are the stage review's (confidence kept); live/E2E none.", ""]
    for st, s in res["stages"].items():
        md += [f"## {st}", "", "| Family | TEX | Member | Pages | Keys | Drawn | Complete src | Predicted | Authored (where) | CLUT positions |", "|---|---|---|---|---:|---:|---:|---:|---|---:|"]
        for r in s["tex"]:
            if r["drawn"] or r["authored"] or r["keys"] >= 8:
                md.append(f"| {r['family']} | {r['tex']} | {','.join(r['members'])} | {r['pages'][:2]} | {r['keys']} | {r['drawn']} | {r['complete_live_source']} | {r['predicted_only']} | {r['authored']} {r['authored_in'][:2]} | {r['clut_positions']} |")
        md += ["", "Capture triggers: " + "; ".join(f"{k}: {v}" for k, v in s["capture_trigger"].items()), ""]
    open(out + "/ACTOR-OWNERSHIP.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(json.dumps(dict(out=p, sha256=sha(p), totals={st: s["totals"] for st, s in res["stages"].items()})))
if __name__ == "__main__":
    main(sys.argv[1])
