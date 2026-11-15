#!/usr/bin/env python3
"""s67: radial fit of the four 30BB2999 star-burst sprites (Stage 7 space backdrop), LIGHT CPU, native words only.

Lane LEDGER (w7-stage7) says the v1 star bursts 'became soft blobs' and names 'CPU analytic shapes' as the next step. Before
any analytic rebuild this records what the native data supports:
  * per sprite (centres searched on a 0.5-texel grid, metric Lp p in {1, 1.5, 2, 3, inf}) the best centre and metric, with the
    count of radial-order violations (off-axis ring texels whose index rises outward);
  * per ring index 1..6 the native radius interval and the fitted iso-radius threshold between neighbouring indices
    (midpoint of the gap, or of the overlap when the native quantisation overlaps), the transparent-hole radius and the outer
    silhouette radius (classes under 30BB2999-418C69D6: index >= 7 cutout, 0..6 opaque; FBFE075D: all opaque);
  * the axis spikes (1-texel lines on the centre row/column) as native index profiles, which a radial model cannot express.
A sprite qualifies for an analytic rebuild only if its violations are <= 2 % of its ring texels.
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/repairs/30BB2999-burst-fit-<UTC>.json."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
WORDS = ROOT / "remaster-audit/fullgame-prep/static-extraction/stages-v4/stage7/textures/30BB2999.words.bin"
OUT = ROOT / "remaster-audit/parallel-stages-20261114/s67/repairs"
X0S, CY0, Y0, Y1 = (16, 48, 80, 112), 231, 218, 248


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dist(xs, ys, cx, cy, p):
    dx, dy = np.abs(xs - cx), np.abs(ys - cy)
    return np.maximum(dx, dy) if p == "inf" else (dx ** p + dy ** p) ** (1 / p)


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    w = np.frombuffer(WORDS.read_bytes(), "<u2").reshape(256, 64)
    idx = np.stack([(w >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)
    sprites = []
    for x0 in X0S:
        ys, xs = np.mgrid[Y0:Y1, max(0, x0 - 17):x0 + 17]
        v = idx[ys, xs]
        best = None
        for cx in np.arange(x0 - 1.5, x0 + 1.51, 0.5):
            for cy in np.arange(CY0 - 1.5, CY0 + 1.51, 0.5):
                for p in (1.0, 1.5, 2.0, 3.0, "inf"):
                    d = dist(xs, ys, cx, cy, p)
                    axis = (np.abs(xs - round(cx)) < 1) | (np.abs(ys - round(cy)) < 1)
                    m = (v >= 1) & (v <= 6) & ~axis & (d < 17)
                    o = np.argsort(d[m], kind="stable")
                    iv = v[m][o]
                    viol = int((iv > np.minimum.accumulate(iv)).sum())
                    if best is None or viol < best[0]:
                        best = (viol, int(m.sum()), float(cx), float(cy), p)
        viol, n, cx, cy, p = best
        d = dist(xs, ys, cx, cy, p)
        axis = (np.abs(xs - round(cx)) < 1) | (np.abs(ys - round(cy)) < 1)
        rings = {}
        for i in range(1, 7):
            m = (v == i) & ~axis & (d < 17)
            rings[i] = [round(float(d[m].min()), 3), round(float(d[m].max()), 3), int(m.sum())] if m.any() else None
        thr = {}
        for i in range(1, 6):   # boundary between index i (outer) and i+1 (inner)
            a, b = rings[i], rings[i + 1]
            if a and b:
                thr[f"{i}|{i + 1}"] = round((a[0] + b[1]) / 2, 3)
        hole = (v >= 7) & (d < 8)
        ring_any = (v >= 1) & (v <= 6) & (d < 17)
        outside = (v >= 7) & (d >= 8) & (d < 17) & ~axis
        r_hole_max = float(d[hole].max()) if hole.any() else None
        r_ring_min = float(d[ring_any & ~axis].min())
        r_ring_max = float(d[ring_any & ~axis].max())
        r_out_min = float(d[outside].min()) if outside.any() else None
        cxr, cyr = int(round(cx)), int(round(cy))
        spikes = dict(up=[int(idx[y, cxr]) for y in range(cyr, Y0 - 1, -1)], down=[int(idx[y, cxr]) for y in range(cyr, Y1)],
                      left=[int(idx[cyr, x]) for x in range(cxr, max(-1, x0 - 18), -1)],
                      right=[int(idx[cyr, x]) for x in range(cxr, min(256, x0 + 18))])
        core = [[int(idx[y, x]) for x in range(cxr - 2, cxr + 3)] for y in range(cyr - 2, cyr + 3)]
        sprites.append(dict(x0=x0, centre=[cx, cy], metric_p=p, violations=viol, ring_texels=n,
                            violation_share=round(viol / max(1, n), 4), qualifies=viol <= 0.02 * n, ring_r=rings, thresholds=thr,
                            hole_r_max=r_hole_max, ring_r_min=round(r_ring_min, 3), ring_r_max=round(r_ring_max, 3),
                            outside_r_min=r_out_min,
                            hole_edge_separable=(r_hole_max is not None and r_hole_max < r_ring_min),
                            silhouette_separable=(r_out_min is not None and r_ring_max < r_out_min),
                            spikes=spikes, core_5x5=core))
    res = dict(run=stamp, owner="claude-einhander-s67", task="EIN-S7-WHOLE-CELL-20261114",
               words=dict(path=str(WORDS.relative_to(ROOT)).replace("\\", "/"), sha256=sha(WORDS)),
               region=dict(u=[0, 127], v=[Y0, Y1 - 1]), sprites=sprites,
               status="DATA ONLY; analytic-rebuild feasibility for the 30BB2999 star bursts; no art produced")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"30BB2999-burst-fit-{stamp}.json"
    dst.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for s in sprites:
        print(s["x0"], s["centre"], "p", s["metric_p"], "viol", s["violations"], "/", s["ring_texels"], "qual", s["qualifies"],
              "hole<ring", s["hole_edge_separable"], (s["hole_r_max"], s["ring_r_min"]), "ring<out", s["silhouette_separable"],
              (s["ring_r_max"], s["outside_r_min"]), "thr", s["thresholds"])
        print("   spikes up", s["spikes"]["up"][:18], "right", s["spikes"]["right"][:18])
    print("out", dst, sha(dst))


if __name__ == "__main__":
    main()
