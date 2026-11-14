#!/usr/bin/env python3
"""Has-cutout / lod-0 fringe census for RGB edges (claude-einhander). DATA ONLY: no admission or pack change. CPU only,
below normal, one logical CPU, one image at a time; inputs read-only. Writes ONLY runs-census/<UTC>/ + INDEX.jsonl.

For every replacement of the world-v4 pack (decoded RGBA, the same images the runtime decodes):
  * has_cutout / cutout_fraction (level 0);
  * on DRAWN cells (breakdown_v2b draw mapping; keys without a CRC-proven native dump or without draws are counted as
    "draw unknown" and measured on the whole image), over every 2x2 bilinear footprint whose taps mix visible and
    cutout pixels: fringe = mean over channels |plain 4-tap mean RGB - visible-tap mean RGB| (the colour shift a lod-0
    bilinear tap takes from cutout RGB, which RGB edges remove), mean / p99, and the fraction of drawn footprints that
    are mixed;
  * opaque pages (no cutout) would pay the RGB-edge fetches for nothing under a global switch (root v62).
Summary: counts, opaque drawn keys, and the keys ranked by drawn mixed footprints x fringe."""
import collections
import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
CM = HERE.parent
BREAKDOWN = CM / "frozen/class-mip-v2b-breakdown-v1/runs/runs-breakdown-v2b/20261114T102254Z/result.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "runs-census" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    (rd / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0, str(CM))
    import breakdown_v2b as B  # noqa: E402
    bd = json.loads(BREAKDOWN.read_text(encoding="utf-8"))
    packroot = Path(bd["pack"]) / "pack"
    regions = {}
    for line in (packroot / "ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    draws = B.load_draws([Path(m["path"]) for m in bd["capture_logs"]], collections.Counter(), regions)
    rows = bd["rows"]["pack"]
    out = []
    for n, r in enumerate(rows):
        key = r["key"]
        with Image.open(r["png"]) as im:
            a = np.asarray(im.convert("RGBA"))
        H, W = a.shape[:2]
        vis = a[..., 3] != 0
        row = dict(key=key, provenance=r.get("provenance"), size=[W, H], has_cutout=bool((~vis).any()),
                   cutout_fraction=round(float((~vis).mean()), 5))
        D = None
        if "native" in r:
            tw, th = r["native"]
            s = W // tw if tw else 0
            dk = draws.get(key)
            if s and W == tw * s and H == th * s and dk:
                if not dk["unmapped"] and dk["dims"] == (tw, th):
                    Dc, _ = B.raster(dk["tris"], tw, th)
                else:
                    Dc = np.ones((th, tw), bool)
                D = np.repeat(np.repeat(Dc, s, 0), s, 1)
                row["drawn_cells"] = int(Dc.sum())
        row["draw"] = "mapped" if D is not None else ("not drawn in captures" if key not in draws else "draw unknown")
        if row["has_cutout"]:
            v = vis.astype(np.int16)
            cnt = v[:-1, :-1] + v[1:, :-1] + v[:-1, 1:] + v[1:, 1:]
            mixed = (cnt > 0) & (cnt < 4)
            if D is not None:
                mixed &= D[:-1, :-1]
            rgb = a[..., :3].astype(np.int32)
            plain = rgb[:-1, :-1] + rgb[1:, :-1] + rgb[:-1, 1:] + rgb[1:, 1:]
            vsum = (rgb[:-1, :-1] * v[:-1, :-1, None] + rgb[1:, :-1] * v[1:, :-1, None] +
                    rgb[:-1, 1:] * v[:-1, 1:, None] + rgb[1:, 1:] * v[1:, 1:, None])
            m = mixed
            if m.any():
                c = cnt[m][:, None].astype(np.float32)
                diff = np.abs(plain[m] / 4.0 - vsum[m] / c).mean(axis=1)
                row.update(mixed_footprints=int(m.sum()), fringe_mean=round(float(diff.mean()), 3),
                           fringe_p99=round(float(np.percentile(diff, 99)), 2))
            else:
                row.update(mixed_footprints=0, fringe_mean=0.0, fringe_p99=0.0)
            base = D[:-1, :-1].sum() if D is not None else (H - 1) * (W - 1)
            row["mixed_fraction_of_drawn_footprints"] = round(float(m.sum()) / float(max(base, 1)), 5)
        out.append(row)
        del a
        if (n + 1) % 200 == 0:
            print(f"{n + 1}/{len(rows)}", flush=True)
    drawn = [x for x in out if x["draw"] == "mapped" and x.get("drawn_cells")]
    benefit = sorted((x for x in drawn if x.get("mixed_footprints")),
                     key=lambda x: -(x["mixed_footprints"] * x["fringe_mean"]))
    summary = dict(keys=len(out), has_cutout=sum(1 for x in out if x["has_cutout"]),
                   fully_opaque=sum(1 for x in out if not x["has_cutout"]),
                   drawn_mapped=len(drawn), drawn_opaque=sum(1 for x in drawn if not x["has_cutout"]),
                   drawn_with_mixed_footprints=len(benefit),
                   drawn_fringe_mean_ge_8=sum(1 for x in benefit if x["fringe_mean"] >= 8),
                   drawn_fringe_mean_ge_32=sum(1 for x in benefit if x["fringe_mean"] >= 32),
                   draw_unknown=sum(1 for x in out if x["draw"] == "draw unknown"),
                   not_drawn=sum(1 for x in out if x["draw"] == "not drawn in captures"))
    res = dict(run=stamp, pack=str(Path(bd["pack"])), breakdown_sha256=sha(BREAKDOWN), summary=summary,
               rank_top50=[{k: x.get(k) for k in ("key", "provenance", "size", "drawn_cells", "cutout_fraction", "mixed_footprints",
                                                  "mixed_fraction_of_drawn_footprints", "fringe_mean", "fringe_p99")} for x in benefit[:50]],
               rows=out, status="DATA ONLY; no admission or pack change")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "runs-census" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, summary=summary, result_sha256=sha(rd / "result.json"))) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
