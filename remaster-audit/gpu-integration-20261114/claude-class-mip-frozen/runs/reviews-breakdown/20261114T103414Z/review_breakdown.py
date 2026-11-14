#!/usr/bin/env python3
"""Review sheets for a breakdown_v2b run (claude-einhander). Read-only, CPU only, below normal, one image at a time.
For the top-N keys ranked by visible-transparency pixels it renders, at most 1024 px wide:
  left   the HD replacement over a checkerboard (cutout shows as checkerboard)
  right  the same with violations (v2 default policy) coloured by kind: red = hole (native visible, HD cutout),
         cyan = added (native cutout, HD visible), yellow = STP-only; texels never drawn in the captures are dimmed.
Writes ONLY reviews-breakdown/<UTC>/ (exist_ok=False): one PNG per key, index.json, a copy of this script."""
import argparse
import ctypes
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "class-audit"))
import audit_native_classes_v2 as A  # noqa: E402
import breakdown_v2b as B  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def checker(h, w, n=8):
    y, x = np.mgrid[0:h, 0:w]
    c = (((x // n) + (y // n)) % 2).astype(np.uint8)
    return np.where(c[..., None] == 1, 200, 140).astype(np.uint8).repeat(3, axis=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, help="runs-breakdown-v2b/<UTC> folder")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    A.below()
    res = json.loads((a.run / "result.json").read_text(encoding="utf-8"))
    lib = ctypes.CDLL(str(a.run / "class_mip.dll"))
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    lib.cm_flags_ex.restype = ctypes.c_int
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    od = HERE / "reviews-breakdown" / stamp
    od.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), od / Path(__file__).name)
    rows = {(r["group"], r["key"]): r for g in res["rows"].values() for r in g}
    pack = Path(res["pack"])
    regions = {}
    for line in (pack / "pack/ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    logs = [Path(m["path"]) for m in res["capture_logs"]]
    best = {}                                           # one sheet per (group, texture page): its worst key
    for (g, k), r in rows.items():
        if "visibility" not in r or not r["visibility"]["visible-transparency"]:
            continue
        pk = (g, k[:8])
        if r["visibility"]["visible-transparency"] > best.get(pk, (0, None))[0]:
            best[pk] = (r["visibility"]["visible-transparency"], k)
    want = [(pk[0], v[1]) for pk, v in sorted(best.items(), key=lambda kv: -kv[1][0])[:a.top]]
    stats = __import__("collections").Counter()
    draws = B.load_draws(logs, stats, regions)
    index = []
    order = [A.STOCK, A.UHU] + sorted(A.CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in A.E.glob("*/hd-on_rewind-off/*") if p.is_dir())

    def source(key):                                    # identical lookup order to breakdown_v2 / f6_real_data_v2
        for d in ([pack / "pack"] if key in regions else order):
            s, c = A.try_dump(d, key, regions)
            if s:
                return s, c
        if key not in regions:
            for d in cap_dirs:
                s, c = A.try_dump(d, key, regions)
                if s:
                    return s, c
        return None, None

    for grp, key in want:
        r = rows[(grp, key)]
        s_, cls = source(key)
        if s_ is None:
            index.append(dict(group=grp, key=key, error="native dump not found"))
            continue
        with Image.open(r["png"]) as im:
            rgba = np.ascontiguousarray(np.asarray(im.convert("RGBA")), dtype=np.uint8)
        if sha(r["png"]) != r["png_sha256"]:
            index.append(dict(group=grp, key=key, error="png changed since the breakdown run"))
            continue
        th, tw = cls.shape
        H, W = rgba.shape[:2]
        s = W // tw
        ncls = np.ascontiguousarray(cls, dtype=np.uint8)
        fl = np.zeros((H, W), np.uint8)
        lib.cm_flags_ex(rgba.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, 0.5, 0, fl.ctypes.data)
        X = rgba[..., 3]
        C = np.repeat(np.repeat(ncls, s, 0), s, 1)
        v = (fl & B.VIOL) != 0
        dk = draws.get(key)
        if dk and not dk["unmapped"] and dk["dims"] == (tw, th):
            D, _ = B.raster(dk["tris"], tw, th)
        else:
            D = np.ones((th, tw), bool) if dk else np.zeros((th, tw), bool)
        Dp = np.repeat(np.repeat(D, s, 0), s, 1)
        base = checker(H, W, max(2, s // 4))
        vis = X != 0
        left = np.where(vis[..., None], rgba[..., :3], base)
        right = left.copy()
        right[v & (C != 0) & (X == 0)] = (255, 0, 0)
        right[v & (C == 0) & (X != 0)] = (0, 255, 255)
        right[v & (C != 0) & (X != 0)] = (255, 220, 0)
        right = np.where(Dp[..., None], right, (right * 0.35).astype(np.uint8))
        sheet = np.concatenate([left, np.full((H, max(4, W // 64), 3), 255, np.uint8), right], axis=1)
        img = Image.fromarray(sheet)
        if img.width > 2048:
            img = img.resize((2048, max(1, round(img.height * 2048 / img.width))), Image.NEAREST)
        out = od / f"{grp}-{key}.png"                       # keys can appear in more than one group
        img.save(out)
        index.append(dict(group=grp, key=key, provenance=r.get("provenance"), png=str(out), sha256=sha(out),
                          visible_transparency_px=r["visibility"]["visible-transparency"], kinds=r["kinds"]))
        del rgba, fl, X, C, v, Dp, sheet
    (od / "index.json").write_text(json.dumps(dict(run=stamp, breakdown_run=str(a.run),
                                                   breakdown_result_sha256=sha(a.run / "result.json"), sheets=index),
                                              indent=1) + "\n", encoding="utf-8")
    print(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
