#!/usr/bin/env python3
"""s45 (claude-einhander-s45): READ-ONLY reuse analysis for the unauthored stage-specific Stage 4 / Stage 5 4bpp pages.

For each UNAUTHORED stage-specific 4bpp page (backlog run, depth-0 'page' kind, a non-common member) and each AUTHORED page
(any frozen w7-stage4/5 set, selected or superseded) of the same stage, compare the 64x256-word pages in 32 strips of 64x8
words (the disc upload unit): identical strips, identical 8x8-texel blocks, and identical texels (4bpp indices). A page whose
words mostly equal an authored page can reuse that master's labels / material in the identical blocks (same index layout ->
the same soft labels away from the changed blocks), and only the changed blocks need authoring. Also compares unauthored pages
with each other (alternate member versions of one page). Writes ONLY s45/page-reuse/<UTC>/reuse.json. numpy on 32 KiB inputs."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
STATIC = RA / "fullgame-prep/static-extraction/stages"
COMFY = RA / "comfy-authoring"


def page_idx(st, tex):
    p = STATIC / f"stage{st}/textures/{tex}.words.bin"
    b = p.read_bytes() if p.is_file() else b""
    if len(b) != 32768:
        return None
    w = np.frombuffer(b, "<u2").reshape(256, 64)
    return np.stack([(w >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)


def cmp(a, b):
    same_t = a == b
    strips = same_t.reshape(32, 8, 256).all(axis=(1, 2))
    blocks = same_t.reshape(32, 8, 32, 8).all(axis=(1, 3))
    return dict(texels=round(float(same_t.mean()), 4), strips=int(strips.sum()), blocks8=int(blocks.sum()),
                differing_strip_rows=[int(i) * 8 for i in np.where(~strips)[0]][:32])


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "page-reuse" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    bl_path = sorted((S45 / "backlog").glob("*/backlog.json"))[-1]
    bl = json.loads(bl_path.read_text(encoding="utf-8"))
    res = dict(run=stamp, owner="claude-einhander-s45", backlog=str(bl_path), backlog_sha256=hashlib.sha256(bl_path.read_bytes()).hexdigest(),
               stages={}, status="DATA ONLY; static words; reuse is a build plan input, not an identity proof")
    for st in ("4", "5"):
        rows = bl["stages"][st]["rows"]
        authored = {}
        for mf in sorted((COMFY / f"w7-stage{st}/frozen").glob("*/manifest.json")):
            m = json.loads(mf.read_text(encoding="utf-8"))
            for t, pg in (m.get("pages") or {}).items():
                authored.setdefault(t, dict(sets=[], page_xy=pg.get("page_xy"), member=pg.get("member")))["sets"].append(mf.parent.name)
        A = {t: page_idx(int(st), t) for t in authored}
        A = {t: v for t, v in A.items() if v is not None}
        un = [r for r in rows if r["cls"] == "UNAUTHORED" and r["depths"] == [0] and "page" in r["kinds"]
              and any(not m.startswith("0/") for m in r["members"])]
        U = {r["tex"]: page_idx(int(st), r["tex"]) for r in un}
        out = []
        for r in un:
            u = U[r["tex"]]
            if u is None:
                out.append(dict(tex=r["tex"], error="no 32 KiB words file"))
                continue
            best = None
            for t, a in A.items():
                c = cmp(u, a)
                if best is None or c["texels"] > best["texels"]:
                    best = dict(c, tex=t, sets=authored[t]["sets"], page_xy=authored[t]["page_xy"], member=authored[t]["member"])
            peers = []
            for r2 in un:
                if r2["tex"] == r["tex"] or U.get(r2["tex"]) is None:
                    continue
                c = cmp(u, U[r2["tex"]])
                if c["texels"] >= 0.5:
                    peers.append(dict(c, tex=r2["tex"], members=r2["members"]))
            peers.sort(key=lambda x: -x["texels"])
            out.append(dict(tex=r["tex"], members=r["members"], page_xy=r["page_xy"], nonzero_keys=r["nonzero_keys"],
                            best_pair=r["best_pair"], tex_confidence=r["tex_confidence"], best_authored=best, unauthored_peers=peers[:6]))
        out.sort(key=lambda x: -(x.get("best_authored") or {}).get("texels", 0))
        res["stages"][st] = out
    f = rd / "reuse.json"
    f.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for st, out in res["stages"].items():
        print("==== S" + st)
        for x in out:
            b = x.get("best_authored") or {}
            pe = ", ".join(f"{p['tex']}({p['texels']:.2f}/{p['strips']})" for p in x.get("unauthored_peers", [])[:3])
            print(f"  {x['tex']} {x.get('members')} {x.get('page_xy')} nz {x.get('nonzero_keys')} | best authored {b.get('tex')} "
                  f"{b.get('page_xy')} texels {b.get('texels')} strips {b.get('strips')}/32 blocks {b.get('blocks8')}/1024 | peers {pe}")
    print("run", stamp, "reuse.json", hashlib.sha256(f.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
