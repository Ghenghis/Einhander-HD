#!/usr/bin/env python3
"""claude-einhander-ui (EIN-MENU-HUD-20261114), job J-K3: class-aware smaller sizes for the hit gauge B24C6DA2.

s45 J-K2 (gauge-v13snap/20261114T155803Z, result 0bbdf6c7) passes primary 11/11 at every size, but its runtime-2048 and
runtime-1024 files are snaps of an EVEN-PIXEL SUBSAMPLE of the 16x v13 art (v13[::2,::2], v13[::4,::4]); s45 recorded the
1024 as aliased. This job keeps J-K2's class-valid 16x snap packs as level 0 (read-only; sha256 checked against J-K2's own
result) and derives the smaller sizes with the frozen proto-v2b cm_build_level (DESIGN: a level never crosses a native
cell; RGB = mean of visible level-0 pixels in the footprint; coverage-preserving visibility per cell; the last level equals
the native classes; cutout texels R5-filled):
  * runtime-2048 = cm_build_level(pack, L=1) (8x), runtime-1024 = cm_build_level(pack, L=2) (4x);
  * variants snap-cell and snap-nearest (J-K2's two 16x packs).
Measured per file, against the same native class map as J-K2 (stock words + this key's stock CLUT): R1 / s2 / conn-only /
R4 / R5, primary, texel-centre class mismatch; and an aliasing measure for BOTH the J-K2 subsample file and the new file:
per visible output pixel, |RGB - mean RGB of the visible 16x pixels in its footprint| (mean, p95), plus visible output
pixels with no visible footprint pixel and cutout output pixels whose footprint is mostly visible.
Review sheets: native | J-K2 subsample | class-mip, at 2048 and 1024, drawn uv [0,64,63,71], 9 px/texel ATLAS SIMULATION
(not a screen capture; no look acceptance). R5 is reported, not claimed: root assigns R5 fill to the pack composer.
Writes ONLY <--out-root>/<UTC>/ inside the registered claude-einhander-ui output. Proposal only; nothing installed.
One process; the CPU is chosen by the launcher (affinity inherited)."""
import argparse
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

RA = Path("C:/github/Einhander/remaster-audit")
UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
JK2 = RA / "parallel-stages-20261114/s45/menu-hud/gauge-v13snap/20261114T155803Z"
JK2_RESULT_SHA256 = "0bbdf6c780038bd594e0d68cae7702978348063634f68ea4f96b0305bf52007f"
STOCK = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLASS_MIP_C_SHA256 = "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
LEVELS = {"runtime-2048": 1, "runtime-1024": 2}       # mip level from the 16x pack
VARIANTS = ("snap-cell", "snap-nearest")
REVIEW = ("D2D9B701", "EE4896FB", "D6B2BFF7")          # the same three keys J-K2 reviewed
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")
TW, TH, S0 = 256, 8, 16


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def footprint_fidelity(out, lvl0, f):
    """Aliasing measure: per visible output pixel, |RGB - mean RGB of the visible level-0 pixels in its f x f footprint|."""
    H, W = out.shape[:2]
    blk = lvl0.reshape(H, f, W, f, 4).astype(np.float64)
    vis = blk[..., 3] > 0
    cnt = vis.sum(axis=(1, 3))
    rgb_sum = (blk[..., :3] * vis[..., None]).sum(axis=(1, 3))
    ov = out[..., 3] > 0
    both = ov & (cnt > 0)
    dev = np.abs(out[..., :3].astype(np.float64) - rgb_sum / np.maximum(cnt, 1)[..., None]).mean(-1)[both]
    return dict(visible_px=int(ov.sum()), measured_px=int(both.sum()),
                dev_mean=round(float(dev.mean()), 3) if dev.size else None,
                dev_p95=round(float(np.percentile(dev, 95)), 3) if dev.size else None,
                visible_without_visible_footprint=int((ov & (cnt == 0)).sum()),
                cutout_with_majority_visible_footprint=int((~ov & (cnt * 2 > f * f)).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(UI_OUT / "gauge-classmip"))
    a = ap.parse_args()
    out_root = Path(a.out_root).resolve()
    if os.path.commonpath([str(out_root).lower(), str(UI_OUT.resolve()).lower()]) != str(UI_OUT.resolve()).lower():
        raise SystemExit(f"--out-root {out_root} is outside the registered output {UI_OUT}")
    t0 = time.time()
    assert sha(JK2 / "result.json") == JK2_RESULT_SHA256, "J-K2 result changed"
    assert sha(PROTO / "class_mip.c") == CLASS_MIP_C_SHA256, "frozen class_mip.c changed"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = out_root / stamp
    for sub in [f"{v}/{s}" for v in VARIANTS for s in LEVELS] + ["review"]:
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
    lib.cm_build_level.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    lib.cm_build_level.restype = ctypes.c_int

    def check(img, ncls, s):
        img = np.ascontiguousarray(img)
        H, W = img.shape[:2]
        rep = CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, TW, TH, s, ctypes.byref(rep))
        o = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, TW, TH, s, bound, 0, fl.ctypes.data)
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
        o["s2_strict_pass"] = all(o[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        o["texel_centre_class_mismatch"] = int((img[s // 2::s, s // 2::s, 3] != ncls).sum())
        return o

    jk2 = json.loads((JK2 / "result.json").read_text(encoding="utf-8"))
    rows, review = [], {}
    for jr in jk2["keys"]:
        k = jr["key"]
        assert sha(STOCK / f"{k}.words.bin") == jr["words_sha256"] and sha(STOCK / f"{k}.clut.bin") == jr["clut_sha256"], k
        w = np.frombuffer((STOCK / f"{k}.words.bin").read_bytes(), "<u2").reshape(TH, 64)
        idx = np.stack([(w >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(TH, TW).astype(np.uint8)
        cw = np.fromfile(STOCK / f"{k}.clut.bin", dtype="<u2")
        cls = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in cw], np.uint8)
        rgb = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
        ncls = np.ascontiguousarray(cls[idx])
        row = dict(key=k, words_sha256=jr["words_sha256"], clut_sha256=jr["clut_sha256"], files={})
        for var in VARIANTS:
            src = jr["files"][f"{var}/pack"]
            p0 = JK2 / src["path"].replace("\\", "/")
            assert sha(p0) == src["sha256"], (k, var, "pack")
            with Image.open(p0) as im:
                lvl0 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            assert lvl0.shape == (TH * S0, TW * S0, 4), lvl0.shape
            row["files"][f"{var}/pack"] = dict(level0=str(p0), sha256=src["sha256"], audit=check(lvl0, ncls, S0))
            for size, L in LEVELS.items():
                f = 1 << L
                s = S0 >> L
                dst = np.zeros((TH * s, TW * s, 4), np.uint8)
                rc = lib.cm_build_level(lvl0.ctypes.data, lvl0.shape[1], lvl0.shape[0], ncls.ctypes.data, TW, TH, S0, L,
                                        dst.ctypes.data)
                fn = rd / var / size / f"{k}.png"
                Image.fromarray(dst).save(fn, compress_level=6)
                prev = jr["files"][f"{var}/{size}"]
                pp = JK2 / prev["path"].replace("\\", "/")
                assert sha(pp) == prev["sha256"], (k, var, size)
                with Image.open(pp) as im:
                    sub = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
                row["files"][f"{var}/{size}"] = dict(
                    path=str(fn.relative_to(rd)), sha256=sha(fn), build_rc=rc, mip_level=L, audit=check(dst, ncls, s),
                    aliasing_classmip=footprint_fidelity(dst, lvl0, f),
                    jk2_subsample=dict(path=str(pp), sha256=prev["sha256"], primary_pass=prev["audit"]["primary_pass"],
                                       aliasing=footprint_fidelity(sub, lvl0, f)))
                if var == "snap-nearest" and k[9:] in REVIEW:
                    review.setdefault(k, {})[size] = [("J-K2 subsample snap-nearest", sub), ("class-mip snap-nearest", dst)]
                    review[k]["native"] = np.dstack([np.repeat(np.repeat(rgb[idx], 16, 0), 16, 1),
                                                     np.repeat(np.repeat(cls[idx], 16, 0), 16, 1)])
        rows.append(row)
        print(k, {x: (v["audit"]["primary_pass"], (v.get("aliasing_classmip") or {}).get("dev_mean"),
                      ((v.get("jk2_subsample") or {}).get("aliasing") or {}).get("dev_mean")) for x, v in row["files"].items()},
              flush=True)

    def tile(a):
        sc = a.shape[1] // TW
        a = a[:, :64 * sc].astype(np.float32)
        v = np.where(a[..., 3:4] > 0, a[..., :3], 24.0)
        return Image.fromarray(v.astype(np.uint8)).resize((64 * 9, 8 * 9), Image.BOX)
    for k, rv in review.items():
        cols = list(LEVELS)
        nrow = 1 + len(rv[cols[0]])
        sheet = Image.new("RGB", (len(cols) * (64 * 9 + 16), nrow * (72 + 18) + 16), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for ci, size in enumerate(cols):
            x = ci * (64 * 9 + 16)
            for ri, (n, arr) in enumerate([("native nearest", rv["native"])] + rv[size]):
                y = ri * (72 + 18) + 18
                sheet.paste(tile(arr), (x, y))
                dr.text((x + 2, y - 15), f"{n} | {size}", fill=(255, 255, 0))
        dr.text((4, sheet.height - 12), f"{k}: ATLAS SIMULATION, 9 px/texel (not a screen capture)", fill=(160, 160, 160))
        sheet.save(rd / "review" / f"{k}-classmip-vs-subsample.png")
    summ = {}
    for var in VARIANTS:
        for size in LEVELS:
            fs = [r["files"][f"{var}/{size}"] for r in rows]
            summ[f"{var}/{size}"] = dict(
                files=len(fs), build_rc_nonzero=sum(f_["build_rc"] != 0 for f_ in fs),
                primary_pass=sum(f_["audit"]["primary_pass"] for f_ in fs),
                s2_strict_pass=sum(f_["audit"]["s2_strict_pass"] for f_ in fs),
                texel_centre_class_mismatch_max=max(f_["audit"]["texel_centre_class_mismatch"] for f_ in fs),
                r5_max=max(f_["audit"]["r5_fringe_px"] for f_ in fs),
                classmip_dev_mean_max=max(f_["aliasing_classmip"]["dev_mean"] or 0 for f_ in fs),
                subsample_dev_mean_max=max(f_["jk2_subsample"]["aliasing"]["dev_mean"] or 0 for f_ in fs),
                classmip_dev_p95_max=max(f_["aliasing_classmip"]["dev_p95"] or 0 for f_ in fs),
                subsample_dev_p95_max=max(f_["jk2_subsample"]["aliasing"]["dev_p95"] or 0 for f_ in fs))
    out = dict(run=stamp, owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114", job="J-K3",
               status="PROPOSAL ONLY: class-aware mips of J-K2's 16x snap packs; J-K2/v13 files read-only; nothing installed; "
                      "review sheets are atlas simulations; R5 reported, not claimed (composer owns R5)",
               tool_sha256=sha(Path(__file__)), class_mip_c_sha256=sha(PROTO / "class_mip.c"),
               jk2_result_sha256=JK2_RESULT_SHA256, summary=summ, keys=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ), flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
