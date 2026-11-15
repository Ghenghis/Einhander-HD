"""s23: Stage 3 capture -> real UV rects per key, checked against the inferred atlas cells. Light (JSONL + small
native-size arrays; no HD pixel work).

  python -I s3_draws_vs_cells.py <out.json> <capture.jsonl> [<capture.jsonl> ...]

For the five Stage 3 2/1 pages (B53A4C57, 59B55BC8, 66A350AA, E49BC3F1, AA5DBEF2) and the 39 predicted keys of the s23
selection map:
  * collects every source_draw_query_matched row: key, frame, uv_bounds, clut_xy, semi, depth, xy;
  * per key: drawn = yes/no, distinct uv rects, frames span, clut_xy seen vs the predicted CLUT position, semi modes;
  * per TEX page: drawn CLUTs that are NOT among the 39 predicted keys (another phase or a wrong PAL pairing),
    with their clut_xy, so the lane can re-render them from the index master;
  * per drawn rect: which inferred cells (frozen <TEX>-cells-32grid.npy) it overlaps. A rect spanning several inferred
    cells, or an inferred cell boundary crossing a rect, means the cell isolation must be rebuilt from the real rect
    (S3.md section 5). A rect fully inside one cell confirms that cell.
  * per key: whether the J2 replaced texels (D masks of the newest complete s23 J2 run, when present) are actually drawn.
Output only <out.json>. A predicted key never drawn is an answer, not a capture defect (S3.md).
"""
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

ROOT = "C:/github/Einhander"
S23 = ROOT + "/remaster-audit/parallel-stages-20261114/s23"
SEL = S23 + "/runs/selection-20261114T133254Z/selection-map.json"
S3 = ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen"
PAGES = ("B53A4C57", "59B55BC8", "66A350AA", "E49BC3F1", "AA5DBEF2")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(out, logs):
    sel = json.load(open(SEL, encoding="utf-8"))["stages"]["3"]["keys"]
    cells, cells_src = {}, {}
    for setname in ("stage3-machinery-walls-v1", "stage3-signage-props-v1"):
        m = json.load(open(f"{S3}/{setname}/manifest.json", encoding="utf-8"))
        for tex, pg in m["pages"].items():
            p = f"{S3}/{setname}/{pg['cells']['file']}"
            assert sha(p) == pg["cells"]["sha256"]
            cells[tex] = np.load(p)
            cells_src[tex] = dict(path=p, sha256=pg["cells"]["sha256"])
    dmask = {}
    for p in sorted(glob.glob(S23 + "/proposals/s3-dither-hybrid-a-*/STATUS.json")) + sorted(glob.glob(S23 + "/proposals/s3-dither-hybrid-a-*/manifest.json")):
        d = os.path.dirname(p)
        for tex in ("E49BC3F1", "AA5DBEF2"):
            mp = f"{d}/{tex}-D-native.png"
            if os.path.exists(mp):
                from PIL import Image
                dmask[tex] = (np.asarray(Image.open(mp)) > 0, mp)
    rows = []
    for lg in logs:
        with open(lg, encoding="utf-8") as f:
            for line in f:
                if '"source_draw_query_matched"' not in line:
                    continue
                r = json.loads(line)
                if r.get("key", "")[:8] in PAGES:
                    rows.append(dict(r, _log=lg))
    per_key, extra = {}, {}
    for r in rows:
        k = r["key"]
        tgt = per_key if k in sel else extra
        e = tgt.setdefault(k, dict(rows=0, frames=[None, None], uv=set(), clut_xy=set(), semi=set(), depth=set()))
        e["rows"] += 1
        fr = r.get("frame")
        e["frames"] = [fr if e["frames"][0] is None else min(e["frames"][0], fr), fr if e["frames"][1] is None else max(e["frames"][1], fr)]
        e["uv"].add(tuple(r["uv_bounds"]))
        e["clut_xy"].add(tuple(r.get("clut_xy") or ()))
        e["semi"].add(r.get("semi"))
        e["depth"].add(r.get("depth"))
    res = dict(owner="claude-einhander-s23", created_utc=datetime.now(timezone.utc).isoformat(), logs=[dict(path=l, sha256=sha(l)) for l in logs],
               selection_map=sha(SEL), cells=cells_src, keys={}, undrawn_predicted=[], extra_drawn_keys={})
    for k, kr in sel.items():
        tex = kr["tex"]
        e = per_key.get(k)
        if not e:
            res["undrawn_predicted"].append(k)
            res["keys"][k] = dict(drawn=False, predicted_clut_xy=kr["clut"].get("vram_xy"))
            continue
        lab = cells[tex]
        rects = []
        for u0, v0, u1, v1 in sorted(e["uv"]):
            sub = lab[max(v0, 0):v1 + 1, max(u0, 0):u1 + 1]
            ids = sorted(int(x) for x in np.unique(sub))
            rect = dict(uv=[u0, v0, u1, v1], inferred_cells=ids, single_cell=len(ids) == 1)
            if tex in dmask:
                D = dmask[tex][0][max(v0, 0):v1 + 1, max(u0, 0):u1 + 1]
                rect["j2_replaced_texels_drawn"] = int(D.sum())
            rects.append(rect)
        res["keys"][k] = dict(drawn=True, rows=e["rows"], frames=e["frames"], clut_xy_seen=sorted(e["clut_xy"]),
                              predicted_clut_xy=kr["clut"].get("vram_xy"),
                              clut_xy_matches_prediction=[list(x) for x in e["clut_xy"]] == [kr["clut"].get("vram_xy")],
                              semi=sorted(x for x in e["semi"] if x is not None), depth=sorted(x for x in e["depth"] if x is not None),
                              rects=rects, rects_spanning_cells=sum(not r["single_cell"] for r in rects))
    for k, e in extra.items():
        res["extra_drawn_keys"][k] = dict(rows=e["rows"], frames=e["frames"], clut_xy=sorted(e["clut_xy"]), uv=sorted(e["uv"])[:16])
    res["summary"] = dict(rows=len(rows), predicted=len(sel), drawn=sum(1 for v in res["keys"].values() if v["drawn"]),
                          undrawn=len(res["undrawn_predicted"]), extra_keys=len(extra),
                          keys_with_cell_spanning_rects=sum(1 for v in res["keys"].values() if v.get("rects_spanning_cells")))
    json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res["summary"]), "sha256", sha(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
