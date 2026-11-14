#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114): REPRESENTATIVE class-snap proposal for the HUD label-font fade strips.

J-H (fade-aliases-v1/20261114T150907Z) reproduced the frozen w3 font method; its traced glyph silhouettes fail the
whole-cell class rules (as the frozen siblings do). Codex: no blanket exception; compare a faithful-native alternative.
For one key per strip TEX (6 keys, J-H candidates, DERIVED CRC-matched CLUTs) plus one frozen captured-CLUT sibling as a
control, at runtime-2048 and runtime-1024:
  * variant 'authored' = the J-H / frozen export as is;
  * variant 'snap-cell' = frozen proto-v2b cm_repair (violators take their cell's native class; newly visible RGB = cell
    mean of correct-class pixels; cutout RGB filled);
  * variant 'snap-nearest' = cm_repair + newly visible RGB from the nearest originally visible pixel.
Measured per file: R1 / s/2 R2 R3 / R4 / conn-only (bounds 0.5 and 1e9) / R5 before and after; class changes split into
cutout->visible, visible->cutout and STP<->opaque (alpha-only); visible RGB unchanged on pixels visible before and after
(proof); newly visible pixel colour vs the native texel colour and vs the nearest originally visible pixel.
A review sheet per key shows native nearest | authored | snap-cell | snap-nearest at an in-game HUD SIMULATION size
(2160p: 9 px per native texel, area-resampled from runtime-2048) and at 16x. Nothing installed; proposal only.
Writes ONLY s45/menu-hud/classsnap/<UTC>/. One process; the CPU is chosen by the launcher (affinity inherited)."""
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
JH = S45 / "menu-hud/fade-aliases-v1/20261114T150907Z"
FROZEN = RA / "comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
STRIPS = {'D050AD1B': 64, '5C02D3C1': 72, '913A6603': 80, '913FE978': 88, '5F101F62': 96, 'AAA5C104': 112}
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
    rd = S45 / "menu-hud/classsnap" / stamp
    (rd / "review").mkdir(parents=True, exist_ok=False)
    try:
        import psutil
        aff = psutil.Process().cpu_affinity()
    except Exception:  # noqa: BLE001
        aff = None
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp} affinity {aff}\n", encoding="utf-8")
    print("PID", os.getpid(), "affinity", aff, "run", rd, flush=True)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    lib.cm_repair.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmRepairStats)]
    lib.cm_repair.restype = ctypes.c_int
    sys.path.insert(0, str(FROZEN / "builder-snapshot"))
    import w2lib as L  # noqa: E402  frozen, import-safe
    IDX = L.load_words('BDAE4156-B88C038E')['idx']
    jh = json.loads((JH / "result.json").read_text(encoding="utf-8"))
    labels = json.loads((JH / "LABELS.json").read_text(encoding="utf-8"))["labels"]
    picks = []
    for tex in STRIPS:     # one J-H key per strip TEX: the most-drawn A/B key
        cands = [e for e in jh["keys"] if e["key"][:8] == tex]
        cands.sort(key=lambda e: (labels[e["key"]]["confidence"], -len(e.get("drawn_uv") or [])))
        if cands:
            e = cands[0]
            picks.append(dict(key=e["key"], source="J-H candidate (DERIVED CRC-matched CLUT, confidence %s)" % labels[e["key"]]["confidence"],
                              clut_path=e["clut"]["path"], files={s: JH / e["runtime"][s]["path"] for s in ("2048", "1024")}))
    fm = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
    ctl = next(e for e in fm["keys"] if e["key"] == "5C02D3C1-0995EC09")
    picks.append(dict(key=ctl["key"], source="CONTROL: frozen w3 strip with a byte-captured CLUT sidecar",
                      clut_path=ctl["clut"]["path"].replace("\\", "/"), files={s: FROZEN / ctl["runtime"][s]["path"] for s in ("2048", "1024")}))

    def check(img, ncls, s):
        H, W = img.shape[:2]
        rep = CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, ctypes.byref(rep))
        out = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, bound, 0, fl.ctypes.data)
            out[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        out["primary_pass"] = out["r1_centre_bad"] == 0 and out["conn_viol_px"] == 0
        out["s2_strict_pass"] = all(out[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        return out

    rows = []
    for pk in picks:
        key = pk["key"]
        y = STRIPS[key[:8]]
        clut = np.fromfile(pk["clut_path"], dtype="<u2")
        lut = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in clut], np.uint8)
        ncls = np.ascontiguousarray(lut[IDX[y:y + 8]])
        crgb = np.stack([(clut & 31) << 3, ((clut >> 5) & 31) << 3, ((clut >> 10) & 31) << 3], -1).astype(np.uint8)
        nrgb = np.ascontiguousarray(crgb[IDX[y:y + 8]])
        variants = {}
        for size, fp in pk["files"].items():
            with Image.open(fp) as im:
                before = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            s = before.shape[1] // 256
            res = dict(input=str(fp), input_sha256=sha(fp), authored=check(before, ncls, s))
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
            for name, out in (("snap-cell", img), ("snap-nearest", near)):
                fn = rd / f"{key}-{size}-{name}.png"
                Image.fromarray(out).save(fn, compress_level=6)
                stp_flip = int(((before[..., 3] == 127) & (out[..., 3] == 255) | (before[..., 3] == 255) & (out[..., 3] == 127)).sum())
                d_nat = np.abs(out[..., :3][newv].astype(np.int32) - natpix[newv].astype(np.int32)).mean(-1) if newv.any() else np.zeros(0)
                res[name] = dict(output=fn.name, output_sha256=sha(fn), repair_rc=rc, after=check(out, ncls, s),
                                 became_visible=int(newv.sum()), became_cutout=int(((before[..., 3] != 0) & (out[..., 3] == 0)).sum()),
                                 stp_opaque_flips=stp_flip,
                                 visible_rgb_changed_on_common_visible=int(((before[..., :3] != out[..., :3]).any(-1) & ov).sum()),
                                 newly_visible_vs_native_mean=round(float(d_nat.mean()), 2) if d_nat.size else None,
                                 newly_visible_vs_native_p95=round(float(np.percentile(d_nat, 95)), 2) if d_nat.size else None)
            variants[size] = res
            if size == "2048":   # review sheet: native | authored | snap-cell | snap-nearest at 2160p sim (9 px/texel) and 16x crop
                def sim(a):
                    rgba = a.astype(np.float32)
                    vis = rgba[..., 3:4] > 0
                    rgb = np.where(vis, rgba[..., :3], 18.0)
                    return Image.fromarray(rgb.astype(np.uint8)).resize((256 * 9, 8 * 9), Image.LANCZOS)
                nat = np.dstack([np.repeat(np.repeat(nrgb, 8, 0), 8, 1), np.repeat(np.repeat(ncls, 8, 0), 8, 1)])
                tiles = [("native nearest", nat), ("authored (J-H/frozen)", before), ("snap-cell", img), ("snap-nearest", near)]
                sheet = Image.new("RGB", (256 * 9, 4 * (8 * 9 + 16)), (0, 0, 0))
                dr = ImageDraw.Draw(sheet)
                for i, (lab, a) in enumerate(tiles):
                    sheet.paste(sim(a), (0, i * (8 * 9 + 16) + 16))
                    dr.text((4, i * (8 * 9 + 16) + 2), f"{lab}  {key}  HUD SIMULATION 9 px/texel", fill=(255, 255, 0))
                sheet.save(rd / "review" / f"{key}-hud-sim.png")
        rows.append(dict(key=key, source=pk["source"], clut_path=pk["clut_path"], variants=variants))
        print(key, {s: (v["authored"]["primary_pass"], v["snap-cell"]["after"]["primary_pass"], v["snap-nearest"]["after"]["primary_pass"],
                        v["snap-cell"]["became_visible"], v["snap-cell"]["became_cutout"], v["snap-cell"]["stp_opaque_flips"],
                        v["snap-nearest"]["visible_rgb_changed_on_common_visible"]) for s, v in variants.items()}, flush=True)
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114",
               status="PROPOSAL ONLY: representative class-snap alternatives; authored candidates preserved; nothing installed; "
                      "CLUTs of J-H keys are DERIVED CRC-matched candidates; the control uses a byte-captured sidecar",
               inputs=dict(jh_result_sha256=sha(JH / "result.json"), jh_labels_sha256=sha(JH / "LABELS.json"), frozen_manifest_sha256=sha(FROZEN / "manifest.json")),
               bounds=dict(s2=0.5, conn_only=1.0e9), rows=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
