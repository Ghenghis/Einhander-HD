#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114), job J-K2: class-snap ALTERNATIVE of the legacy v13 hit-gauge art B24C6DA2.

J-K (gauge-B24C6DA2-v1/20261114T154853Z) built a class-valid EPX candidate (primary 66/66) whose chevrons are lumpy; the
legacy v13 HUD-origin PNGs (4096x128 only, title-e-20261112-v13 pack) have clean bevelled chevrons but fail primary 0/11
(R4 islands 1886 px each, R1 0). This job applies the frozen proto-v2b cm_repair (cell snap, as J-I) to read-only copies:
  * pack (16x): the v13 file itself;
  * runtime-2048 / runtime-1024: even-pixel subsample of the v13 file (8x pixel X <- 16x pixel 2X; 4x X <- 16x 4X), which
    maps every R1 centre floor((i+0.5)s) onto the 16x centre; then cm_repair at that size;
  * variants: snap-cell (cm_repair as is) and snap-nearest (newly visible RGB from the nearest originally visible pixel).
Measured per file before/after: R1 / s2 / conn-only / R4 / R5, primary; became visible / cutout, STP<->opaque flips;
visible RGB changed on common-visible pixels (must be 0); newly visible colour vs native CLUT colour (mean / p95). Review
sheets over drawn uv [0,64,63,71], every size at 9 px/texel (matched-screen-size ATLAS SIMULATION): native | v13 | J-K EPX
crisp | v13 snap-cell | v13 snap-nearest, one column per size. Source pins per key: words / CLUT / source.json / v13 sha256. v13 and J-K files are read-only. Writes ONLY s45/menu-hud/gauge-v13snap/<UTC>/. Proposal only.
One process; the CPU is chosen by the launcher (affinity inherited)."""
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
JK = S45 / "menu-hud/gauge-B24C6DA2-v1/20261114T154853Z"
STOCK = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
TYPO = RA / "comfy-authoring/t9-title-menus/inventory/typography-inventory.json"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
SIZES = {"pack": 1, "runtime-2048": 2, "runtime-1024": 4}      # subsample step from the 16x v13 file
REVIEW = ("D2D9B701", "EE4896FB", "D6B2BFF7")
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")
SF = ("class_changed", "became_visible", "became_cutout", "rgb_from_cell", "rgb_from_native", "cutout_rgb_filled",
      "visible_rgb_changed", "passes", "residual_violations")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


class CmRepairStats(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in SF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/gauge-v13snap" / stamp
    for sub in [f"{v}/{s}" for v in ("snap-cell", "snap-nearest") for s in SIZES] + ["review"]:
        (rd / sub).mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    lib.cm_repair.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmRepairStats)]
    lib.cm_repair.restype = ctypes.c_int

    def check(img, ncls, s):
        H, W = img.shape[:2]
        rep = CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, ctypes.byref(rep))
        o = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, bound, 0, fl.ctypes.data)
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
        o["s2_strict_pass"] = all(o[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        return o

    typo = json.loads(TYPO.read_text(encoding="utf-8"))["keys"]
    jk = json.loads((JK / "result.json").read_text(encoding="utf-8"))
    words = (STOCK / f"{jk['keys'][0]['key']}.words.bin").read_bytes()
    w = np.frombuffer(words, "<u2").reshape(8, 64)
    idx = np.stack([(w >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(8, 256).astype(np.uint8)
    rows, review = [], {}
    for jr in jk["keys"]:
        k = jr["key"]
        assert (STOCK / f"{k}.words.bin").read_bytes() == words
        cw = np.fromfile(STOCK / f"{k}.clut.bin", dtype="<u2")
        cls = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in cw], np.uint8)
        rgb = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
        ncls = np.ascontiguousarray(cls[idx])
        nrgb = np.ascontiguousarray(rgb[idx])
        v13p = Path(typo[k]["v13"]["pack_png"])
        with Image.open(v13p) as im:
            v13 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
        assert v13.shape == (128, 4096, 4), v13.shape
        row = dict(key=k, v13=str(v13p), v13_sha256=sha(v13p), clut=str(STOCK / f"{k}.clut.bin"), clut_sha256=sha(STOCK / f"{k}.clut.bin"),
                   words=str(STOCK / f"{k}.words.bin"), words_sha256=sha(STOCK / f"{k}.words.bin"),
                   source_json=json.loads((STOCK / f"{k}.source.json").read_text(encoding="utf-8")),
                   native_authority="this key's own stock CLUT: class 0 = word 0x0000, 255 = STP bit, else 127; RGB = 5-bit << 3",
                   files={})
        for size, step in SIZES.items():
            before = np.ascontiguousarray(v13[::step, ::step]) if step > 1 else v13.copy()
            s = before.shape[1] // 256
            img = before.copy()
            st = CmRepairStats()
            rc = lib.cm_repair(img.ctypes.data, img.shape[1], img.shape[0], ncls.ctypes.data, nrgb.ctypes.data, 256, 8, s, ctypes.byref(st))
            near = img.copy()
            ov = (before[..., 3] != 0) & (img[..., 3] != 0)
            newv = (before[..., 3] == 0) & (img[..., 3] != 0)
            if newv.any() and ov.any():
                _, (iy, ix) = ndi.distance_transform_edt(~ov, return_indices=True)
                near[newv, :3] = near[iy[newv], ix[newv], :3]
            natpix = np.repeat(np.repeat(nrgb, s, 0), s, 1)
            row["files"][f"before/{size}"] = dict(audit=check(before, ncls, s), subsample_step=step)
            for var, out in (("snap-cell", img), ("snap-nearest", near)):
                fn = rd / var / size / f"{k}.png"
                Image.fromarray(out).save(fn, compress_level=6)
                d_nat = np.abs(out[..., :3][newv].astype(np.int32) - natpix[newv].astype(np.int32)).mean(-1) if newv.any() else np.zeros(0)
                row["files"][f"{var}/{size}"] = dict(
                    path=str(fn.relative_to(rd)), sha256=sha(fn), repair_rc=rc, audit=check(out, ncls, s),
                    texel_centre_class_mismatch=int((out[s // 2::s, s // 2::s, 3] != ncls).sum()),
                    became_visible=int(newv.sum()), became_cutout=int(((before[..., 3] != 0) & (out[..., 3] == 0)).sum()),
                    stp_opaque_flips=int((((before[..., 3] == 127) & (out[..., 3] == 255)) | ((before[..., 3] == 255) & (out[..., 3] == 127))).sum()),
                    visible_rgb_changed_on_common_visible=int(((before[..., :3] != out[..., :3]).any(-1) & ov).sum()),
                    newly_visible_vs_native_mean=round(float(d_nat.mean()), 2) if d_nat.size else None,
                    newly_visible_vs_native_p95=round(float(np.percentile(d_nat, 95)), 2) if d_nat.size else None)
            if k[9:] in REVIEW:
                with Image.open(JK / jr["files"][f"crisp/{size}"]["path"]) as im:
                    epx = np.asarray(im.convert("RGBA"))
                review.setdefault(k, {})[size] = [("legacy v13" + (f" (1/{step} subsample)" if step > 1 else ""), before),
                                                  ("J-K EPX crisp", epx), ("v13 snap-cell", img), ("v13 snap-nearest", near)]
                review[k]["native"] = np.dstack([np.repeat(np.repeat(rgb[idx], 16, 0), 16, 1), np.repeat(np.repeat(cls[idx], 16, 0), 16, 1)])
        rows.append(row)
        f = row["files"]
        print(k, {x: (f[x]["audit"]["primary_pass"], f[x].get("visible_rgb_changed_on_common_visible")) for x in f}, flush=True)
    # matched screen size: every variant of every size shown over drawn uv [0,64,63,71] at 9 px/texel (2160p simulation)

    def tile(a):
        sc = a.shape[1] // 256
        a = a[:, :64 * sc].astype(np.float32)
        v = np.where(a[..., 3:4] > 0, a[..., :3], 24.0)
        return Image.fromarray(v.astype(np.uint8)).resize((64 * 9, 8 * 9), Image.BOX)
    for k, rv in review.items():
        cols = list(SIZES)
        nrow = 1 + len(rv[cols[0]])
        sheet = Image.new("RGB", (len(cols) * (64 * 9 + 16), nrow * (72 + 18) + 4), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for ci, size in enumerate(cols):
            x = ci * (64 * 9 + 16)
            items = [("native nearest", rv["native"])] + rv[size]
            for ri, (n, a) in enumerate(items):
                y = ri * (72 + 18) + 18
                sheet.paste(tile(a), (x, y))
                dr.text((x + 2, y - 15), f"{n} | {size}", fill=(255, 255, 0))
        dr.text((4, sheet.height - 12), f"{k}: ATLAS SIMULATION, 9 px/texel for every size (not a screen capture)", fill=(160, 160, 160))
        sheet.save(rd / "review" / f"{k}-v13snap-matched.png")
    summ = {}
    for x in [f"{v}/{s}" for v in ("before", "snap-cell", "snap-nearest") for s in SIZES]:
        fs = [r["files"][x] for r in rows]
        summ[x] = dict(files=len(fs), primary_pass=sum(f["audit"]["primary_pass"] for f in fs),
                       s2_strict_pass=sum(f["audit"]["s2_strict_pass"] for f in fs),
                       r5_max=max(f["audit"]["r5_fringe_px"] for f in fs),
                       common_visible_rgb_changed_max=max((f.get("visible_rgb_changed_on_common_visible") or 0) for f in fs),
                       became_visible=[min(f.get("became_visible", 0) for f in fs), max(f.get("became_visible", 0) for f in fs)],
                       stp_flips_max=max((f.get("stp_opaque_flips") or 0) for f in fs))
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", job="J-K2",
               status="PROPOSAL ONLY: class-snapped copies of the legacy v13 gauge; v13 and J-K files untouched; nothing installed",
               size_strategy=("pack = the v13 4096x128 file (16x); runtime-2048 = v13[::2, ::2] (8x), runtime-1024 = v13[::4, ::4] (4x): "
                              "pixel X at scale s takes 16x pixel X*16/s, so every R1 centre floor((i+0.5)s) samples the 16x centre "
                              "floor((i+0.5)16); cm_repair then runs at that size against the same native class map"),
               tool_sha256=sha(Path(__file__)), class_mip_c_sha256=sha(PROTO / "class_mip.c"), jk_result_sha256=sha(JK / "result.json"),
               summary=summ, keys=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ), flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
