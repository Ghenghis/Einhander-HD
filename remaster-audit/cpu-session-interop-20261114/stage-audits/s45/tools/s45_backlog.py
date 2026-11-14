#!/usr/bin/env python3
"""s45 (claude-einhander-s45): READ-ONLY Stage 4 / Stage 5 authoring backlog at texture-page level.

For every TEX that the static model predicts keys for (stages/stage{4,5}/keys.json), group: kind(s) (page / raw), depth(s)
(0 = 4bpp, 1 = 8bpp, 2 = 15bpp, 3 = raw any), member(s), page_xy, key counts (all / non-zero CLUT), best static pair count,
texture confidence (textures.json), and where an HD master exists (pages listed by any w7-stage{4,5}/frozen set, with the set
status). Classes: SELECTED (in the lane-readiness selection), AUTHORED-OTHER (in a frozen set that is not selected:
superseded / failed / swatch), SHARED-UNBUILT (05E1881C), UNAUTHORED. This is the real remaining page denominator for
Stages 4/5 at static-prediction level; runtime-only keys (animated CLUTs, MoveImage cells, unread code paths) are outside it
by construction (static manifest runtime_needs_capture). Writes ONLY s45/backlog/<UTC>/backlog.json. JSON only."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

RA = Path("C:/github/Einhander/remaster-audit")
OUT = RA / "parallel-stages-20261114/s45/backlog"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
STATIC = RA / "fullgame-prep/static-extraction/stages"
COMFY = RA / "comfy-authoring"


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    rd.mkdir(parents=True, exist_ok=False)
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    res = dict(run=stamp, owner="claude-einhander-s45", stages={},
               status="DATA ONLY; static predictions; boss/route identity of a TEX is not on the disc in a readable form")
    for st in (4, 5):
        sd = STATIC / f"stage{st}"
        keys = json.loads((sd / "keys.json").read_text(encoding="utf-8"))
        tex_conf = {e["tex"]: e for e in json.loads((sd / "textures.json").read_text(encoding="utf-8"))}
        lane = next(s for s in readiness["stages"] if s["stage"] == st)
        selected_sets = {Path(f["path"]).name for f in lane["candidate_folders"]}
        authored = collections.defaultdict(list)
        for mf in sorted((COMFY / f"w7-stage{st}/frozen").glob("*/manifest.json")):
            m = json.loads(mf.read_text(encoding="utf-8"))
            for t in (m.get("pages") or {}):
                authored[t].append(dict(set=mf.parent.name, status=m.get("status"), selected=mf.parent.name in selected_sets))
        pages = {}
        for e in keys:
            t = e["key"][:8]
            p = pages.setdefault(t, dict(tex=t, kinds=set(), depths=set(), members=set(), page_xy=set(), keys=0, nonzero=0,
                                         best_pair=0, exact_static_keys=0))
            p["kinds"].add(e.get("kind"))
            p["depths"].add(e.get("depth"))
            p["members"].add(e.get("tex_member"))
            p["page_xy"].add(tuple(e.get("page_xy") or ()))
            p["keys"] += 1
            p["nonzero"] += int(not e.get("pal_all_zero"))
            p["best_pair"] = max(p["best_pair"], e.get("pair_count") or 0)
            p["exact_static_keys"] += int(e.get("confidence") == "exact-static")
        rows = []
        for t, p in pages.items():
            a = authored.get(t, [])
            if any(x["selected"] for x in a):
                cls = "SELECTED"
            elif t == "05E1881C":
                cls = "SHARED-UNBUILT"
            elif a:
                cls = "AUTHORED-OTHER"
            else:
                cls = "UNAUTHORED"
            rows.append(dict(tex=t, cls=cls, kinds=sorted(p["kinds"]), depths=sorted(p["depths"]), members=sorted(p["members"]),
                             page_xy=sorted(list(x) for x in p["page_xy"]), keys=p["keys"], nonzero_keys=p["nonzero"],
                             exact_static_keys=p["exact_static_keys"], best_pair=p["best_pair"],
                             tex_confidence=(tex_conf.get(t) or {}).get("confidence"), authored_in=a))
        rows.sort(key=lambda r: (r["cls"] != "UNAUTHORED", -r["nonzero_keys"]))
        by_cls = collections.Counter(r["cls"] for r in rows)
        un = [r for r in rows if r["cls"] == "UNAUTHORED"]
        by_member = collections.Counter(m for r in un for m in r["members"])
        by_depth = collections.Counter(tuple(r["depths"]) for r in un)
        res["stages"][st] = dict(tex_total=len(rows), by_class=dict(by_cls),
                                 unauthored_nonzero_keys=sum(r["nonzero_keys"] for r in un),
                                 selected_nonzero_keys=sum(r["nonzero_keys"] for r in rows if r["cls"] == "SELECTED"),
                                 unauthored_by_member=dict(by_member.most_common()),
                                 unauthored_by_depths={str(k): v for k, v in by_depth.most_common()},
                                 unauthored_with_exact_static_keys=sum(1 for r in un if r["exact_static_keys"]),
                                 rows=rows)
    out = rd / "backlog.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for st, s in res["stages"].items():
        print(f"S{st}: TEX {s['tex_total']} {s['by_class']} unauthored non-zero keys {s['unauthored_nonzero_keys']} "
              f"(selected {s['selected_nonzero_keys']}); with exact-static keys {s['unauthored_with_exact_static_keys']}")
        print("   by member", s["unauthored_by_member"])
        print("   by depths", s["unauthored_by_depths"])
        for r in s["rows"][:12]:
            print("   ", r["tex"], r["cls"], r["kinds"], r["depths"], r["members"], r["page_xy"][:2], "keys", r["keys"], "nz", r["nonzero_keys"], "pair", r["best_pair"])
    print("run", stamp, "backlog.json", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
