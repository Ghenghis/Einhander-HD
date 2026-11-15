#!/usr/bin/env python3
"""RISE (82831823) authored v5 -> all 33 palettes (claude-einhander; root approval msg_3c9ce9d1: private expansion +
animation strip + per-palette strict class / fade checks; no composition, no install, no live acceptance).
CPU only, below normal, ONE logical CPU, one process, bounded (< 90 s). Writes ONLY rise-native-vector/expand33/<UTC>/.

Input: the APPROVED shared role map authored/20261114T132814Z/role-weights.npz (per-pixel convex CLUT-index weights +
the class mask), sha-checked against that run's result.json. For every palette key in the CRC-proven native dump:
  * RGB = weights . CLUT(palette) (indices 0..14), class alpha 127 inside the mask / 0 outside (the native class map is
    identical for all 33 palettes: index 15 is the only transparent entry, no STP - re-checked here per palette);
  * cutout RGB = frozen proto-v2b cm_fill_cutout_rgb (R5 by construction);
  * frozen proto-v2b cm_validate (strict s/2) + cm_flags_ex connectivity-only: must be 0 for every palette;
  * the reference palette must reproduce the approved v5 PNG byte for byte;
  * fade/hue check: per palette, mean RGB over the opaque mask of NEW vs the native page rendered with the same CLUT
    (x16 nearest, same mask cells); luminance ratio, Spearman rank correlation over the 33 palettes, hue agreement.
Outputs: palettes/<KEY>.png (33), strip-new.png + strip-native.png (thumbnails ordered by native luminance, the fade
order proxy), result.json."""
import ctypes
import datetime
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PROTO = CM / "frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
SRC_RUN = HERE / "authored/20261114T132814Z"
REF = "82831823-06BDD2F5"
S = 16


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                               "r4_island_px", "r5_fringe_px", "cells_bad", "pinhole_cells", "nonclass_px")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lum(rgb):
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    ra -= ra.mean()
    rb -= rb.mean()
    return float((ra * rb).sum() / np.sqrt((ra * ra).sum() * (rb * rb).sum()))


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    t_start = time.perf_counter()
    src_res = json.loads((SRC_RUN / "result.json").read_text(encoding="utf-8"))
    assert sha(SRC_RUN / "role-weights.npz") == src_res["outputs"]["role-weights.npz"], "role map changed"
    assert sha(SRC_RUN / f"authored-{REF}.png") == src_res["outputs"][f"authored-{REF}.png"], "reference PNG changed"
    nat_path = sorted((HERE / "native").glob("*/result.json"))[-1]
    nat = json.loads(nat_path.read_text(encoding="utf-8"))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "expand33" / stamp
    (rd / "palettes").mkdir(parents=True, exist_ok=False)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    dll = rd / "class_mip.dll"
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(PROTO / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=120, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(dll))
    lib.cm_fill_cutout_rgb.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.cm_fill_cutout_rgb.restype = ctypes.c_int64
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    z = np.load(SRC_RUN / "role-weights.npz")
    Wt = z["weights"].astype(np.float32)                           # (H, W, 16)
    opq = z["opaque"].astype(bool)
    H, W = opq.shape
    idx = np.array([[int(ch, 16) for ch in row] for row in nat["index_map_rows"]], np.uint8)
    th, tw = idx.shape
    assert (H, W) == (th * S, tw * S)
    C16 = np.repeat(np.repeat(idx, S, 0), S, 1)
    rows = []
    for key in sorted(nat["palettes"]):
        pe = nat["palettes"][key]["entries"]
        cls_of = np.array([e["cls"] for e in pe], np.uint8)
        clut = np.array([e["rgb"] for e in pe], np.float32)
        same_class = bool(set(cls_of[:15].tolist()) == {127} and cls_of[15] == 0)
        ncls = np.ascontiguousarray(cls_of[idx])
        rgb = np.clip(np.rint(np.tensordot(Wt[..., :15], clut[:15], axes=([2], [0]))), 0, 255).astype(np.uint8)
        a = np.ascontiguousarray(np.dstack([rgb, np.where(opq, 127, 0).astype(np.uint8)]))
        assert lib.cm_fill_cutout_rgb(a.ctypes.data, W, H) >= 0
        rep = CmReport()
        lib.cm_validate(a.ctypes.data, W, H, ncls.ctypes.data, tw, th, S, ctypes.byref(rep))
        fl = np.zeros((H, W), np.uint8)
        lib.cm_flags_ex(a.ctypes.data, W, H, ncls.ctypes.data, tw, th, S, 1.0e9, 0, fl.ctypes.data)
        f = rd / "palettes" / f"{key}.png"
        Image.fromarray(a).save(f)
        native_rgb = clut.astype(np.uint8)[C16]
        m = opq & (C16 != 15)                                       # opaque in both
        new_mean = a[..., :3][m].astype(np.float64).mean(axis=0)
        nat_mean = native_rgb[m].astype(np.float64).mean(axis=0)
        rows.append(dict(key=key, same_class_map=same_class, png=f.name, sha256=sha(f),
                         v2={k: getattr(rep, k) for k, _ in CmReport._fields_},
                         conn_viol_px=int(((fl & (2 | 4 | 16)) != 0).sum()),
                         new_mean_rgb=[round(x, 2) for x in new_mean], native_mean_rgb=[round(x, 2) for x in nat_mean],
                         new_lum=round(float(lum(new_mean)), 2), native_lum=round(float(lum(nat_mean)), 2)))
        del a, fl, rgb
    ref_row = next(r for r in rows if r["key"] == REF)
    ref_identical = ref_row["sha256"] == src_res["outputs"][f"authored-{REF}.png"]
    nl = np.array([r["native_lum"] for r in rows])
    wl = np.array([r["new_lum"] for r in rows])
    ratio = wl / np.maximum(nl, 1e-6)
    nm = np.array([r["native_mean_rgb"] for r in rows])
    wm = np.array([r["new_mean_rgb"] for r in rows])
    cos = (nm * wm).sum(1) / np.maximum(np.linalg.norm(nm, axis=1) * np.linalg.norm(wm, axis=1), 1e-9)
    order = np.argsort(nl)
    tiles_new, tiles_nat = [], []
    for i in order:
        r = rows[i]
        with Image.open(rd / "palettes" / r["png"]) as im:
            x = np.asarray(im.convert("RGBA"))
        yy, xx = np.indices(x.shape[:2])
        chk = np.where(((xx // 8 + yy // 8) % 2 == 0)[..., None], 200, 140).astype(np.uint8)
        tiles_new.append(np.asarray(Image.fromarray(np.where(x[..., 3:4] != 0, x[..., :3], chk)).resize((256, 128), Image.LANCZOS)))
        pe = nat["palettes"][r["key"]]["entries"]
        clut = np.array([e["rgb"] for e in pe], np.uint8)
        nimg = np.where((C16 != 15)[..., None], clut[C16], chk)
        tiles_nat.append(np.asarray(Image.fromarray(nimg.astype(np.uint8)).resize((256, 128), Image.NEAREST)))

    def grid(tiles):
        cols = 6
        rows_ = (len(tiles) + cols - 1) // cols
        g = np.full((rows_ * 132, cols * 260, 3), 255, np.uint8)
        for k, t in enumerate(tiles):
            gy, gx = divmod(k, cols)
            g[gy * 132:gy * 132 + 128, gx * 260:gx * 260 + 256] = t[..., :3]
        return g
    Image.fromarray(grid(tiles_new)).save(rd / "strip-new.png")
    Image.fromarray(grid(tiles_nat)).save(rd / "strip-native.png")
    secs = round(time.perf_counter() - t_start, 2)
    summary = dict(palettes=len(rows), all_same_class_map=all(r["same_class_map"] for r in rows),
                   strict_all_zero=all(all(r["v2"][k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                                                    "r4_island_px", "r5_fringe_px", "cells_bad",
                                                                    "pinhole_cells", "nonclass_px")) for r in rows),
                   connectivity_all_zero=all(r["conn_viol_px"] == 0 for r in rows),
                   reference_palette_identical_to_approved_v5=ref_identical,
                   fade_spearman_new_vs_native=round(spearman(nl, wl), 4),
                   lum_ratio_min=round(float(ratio.min()), 3), lum_ratio_max=round(float(ratio.max()), 3),
                   hue_cosine_min=round(float(cos.min()), 4), seconds=secs)
    res = dict(run=stamp, source_role_map=str(SRC_RUN / "role-weights.npz"), source_sha256=sha(SRC_RUN / "role-weights.npz"),
               native_source=str(nat_path), native_sha256=sha(nat_path), summary=summary,
               strip_order="ascending native luminance (fade-order proxy; the in-game cycle order is not known)",
               outputs={p.name: sha(p) for p in sorted(rd.iterdir()) if p.suffix == ".png"}, rows=rows,
               status="PRIVATE; 33-palette expansion of the approved v5 role map; not composed, not installed, no live acceptance")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dict(run=stamp, summary=summary, result_sha256=sha(rd / "result.json")), indent=1))


if __name__ == "__main__":
    main()
