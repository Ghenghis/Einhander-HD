#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114), job J-M: FAITHFUL NATIVE-INDEX EPX RETRACE alternative for the HUD label font.

J-I showed that class-snapping the traced w3/J-H glyphs passes the primary policy but leaves squared cell blocks on curves
(Codex: no look acceptance; consider a faithful native index/EPX retrace). This job builds that alternative for the SAME 7
representative keys (6 J-H keys with DERIVED CRC-matched CLUTs + control 5C02D3C1-0995EC09 with a byte-captured CLUT):
  * native index rows of BDAE4156 (frozen w3 builder-snapshot w2lib, as J-I) for the strip's 8 rows;
  * frozen w4 EPX / Scale2x (hud-lives-glyphs builder-snapshot epx.py.txt), 3 passes -> 2048 (8x); 1024 (4x) = even-pixel
    subsample of that 8x map (keeps every R1 centre floor((i+0.5)s)):
    1-texel staircases -> 45-degree edges, straight runs stay straight, no new index values;
  * crisp = exact CLUT colours; alpha class per CLUT entry (0 cutout, 255 STP, 127 opaque);
  * soft = RGB anti-aliased only among indices of the same class (alpha classes untouched).
Validated with the frozen proto-v2b class_mip (primary = R1 + conn-only; s/2 diagnostic; R5) and an independent texel-centre
check. Compared per key with the authored file and the J-I snap-cell file: visible-mask IoU / XOR, colour on common visible
pixels. Review sheets at a 9 px/texel ATLAS SIMULATION (not an actual screen): native | authored | J-I snap-cell | EPX crisp
| EPX soft. Writes ONLY s45/menu-hud/epx-retrace/<UTC>/. CANDIDATE ALTERNATIVE only; nothing installed.
One process; the CPU is chosen by the launcher (affinity inherited)."""
import ctypes
import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
JI = S45 / "menu-hud/classsnap/20261114T152840Z"
FROZEN = RA / "comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1"
EPX = RA / "comfy-authoring/w4-signs-hud/frozen/hud-lives-glyphs-832p256-w4-v1/builder-snapshot/epx.py.txt"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
STRIPS = {'D050AD1B': 64, '5C02D3C1': 72, '913A6603': 80, '913FE978': 88, '5F101F62': 96, 'AAA5C104': 112}
SIZES = {"2048": 3, "1024": 2}
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/epx-retrace" / stamp
    for sub in ("crisp", "alt-soft", "review"):
        (rd / sub).mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    shutil.copy2(EPX, rd / "epx.py.txt")
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    ld = importlib.machinery.SourceFileLoader("epx_w4", str(rd / "epx.py.txt"))
    E = importlib.util.module_from_spec(importlib.util.spec_from_loader("epx_w4", ld))
    ld.exec_module(E)
    sys.path.insert(0, str(FROZEN / "builder-snapshot"))
    import w2lib as L  # noqa: E402  frozen, import-safe
    IDX = L.load_words('BDAE4156-B88C038E')['idx']
    ji = json.loads((JI / "result.json").read_text(encoding="utf-8"))

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

    def compare(a, b):
        va, vb = a[..., 3] > 0, b[..., 3] > 0
        both = va & vb
        d = np.abs(a[..., :3].astype(np.int32) - b[..., :3].astype(np.int32)).mean(-1)[both]
        return dict(visible_iou=round(float(both.sum() / max(1, (va | vb).sum())), 4), visible_xor_px=int((va ^ vb).sum()),
                    common_visible_rgb_mean_absdiff=round(float(d.mean()), 2) if d.size else None)

    rows = []
    for jr in ji["rows"]:
        key = jr["key"]
        y = STRIPS[key[:8]]
        idx = np.ascontiguousarray(IDX[y:y + 8]).astype(np.uint8)
        clut = np.fromfile(jr["clut_path"], dtype="<u2")
        cls = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in clut], np.uint8)
        rgb = np.stack([(clut & 31) << 3, ((clut >> 5) & 31) << 3, ((clut >> 10) & 31) << 3], -1).astype(np.uint8)
        ncls = np.ascontiguousarray(cls[idx])
        row = dict(key=key, source=jr["source"], clut_path=jr["clut_path"], clut_sha256=sha(jr["clut_path"]), files={})
        u8 = E.upscale(idx, 3)
        for size, kk in SIZES.items():
            s = 2 ** kk
            # 1024 = even-pixel subsample of the 8x EPX map (pixel X <- 8x pixel 2X): R1 centre floor((i+0.5)*4) maps to the 8x
            # centre floor((i+0.5)*8); a direct 2-pass EPX misses 4-14 R1 centres on these strips (in-memory pre-check)
            u = u8 if size == "2048" else np.ascontiguousarray(u8[0::2, 0::2])
            assert int((u[s // 2::s, s // 2::s] != idx).sum()) == 0, (key, size)
            crisp = np.ascontiguousarray(np.dstack([rgb[u], cls[u]]))
            wts = E.aa_weights(u, present=np.unique(u), sigma=0.6) * (cls[:, None, None] == cls[u][None])
            wts /= np.maximum(wts.sum(0, keepdims=True), 1e-6)
            soft = np.ascontiguousarray(np.dstack([np.clip(np.einsum("ihw,ic->hwc", wts, rgb.astype(np.float32)) + 0.5, 0, 255).astype(np.uint8),
                                                   cls[u]]))
            with Image.open(jr["variants"][size]["input"]) as im:
                authored = np.asarray(im.convert("RGBA"))
            with Image.open(JI / jr["variants"][size]["snap-cell"]["output"]) as im:
                snapcell = np.asarray(im.convert("RGBA"))
            for var, img, sub in (("crisp", crisp, "crisp"), ("soft", soft, "alt-soft")):
                fn = rd / sub / f"{key}-{size}.png"
                Image.fromarray(img).save(fn, compress_level=6)
                with Image.open(fn) as im:
                    back = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
                assert np.array_equal(back, img)
                row["files"][f"{var}/{size}"] = dict(
                    path=str(fn.relative_to(rd)), sha256=sha(fn), dims=list(img.shape[1::-1]), audit=check(back, ncls, s),
                    texel_centre_class_mismatch=int((back[s // 2::s, s // 2::s, 3] != ncls).sum()),
                    vs_authored=compare(back, authored), vs_ji_snap_cell=compare(back, snapcell))
            if size == "2048":
                nat = np.dstack([np.repeat(np.repeat(rgb[idx], 8, 0), 8, 1), np.repeat(np.repeat(cls[idx], 8, 0), 8, 1)])
                tiles = [("native nearest", nat), ("authored (J-H/frozen)", authored), ("J-I snap-cell", snapcell),
                         ("EPX retrace crisp", crisp), ("EPX retrace soft", soft)]

                def sim(a):
                    a = a.astype(np.float32)
                    v = np.where(a[..., 3:4] > 0, a[..., :3], 18.0)
                    return Image.fromarray(v.astype(np.uint8)).resize((256 * 9, 8 * 9), Image.BOX)
                sheet = Image.new("RGB", (256 * 9, len(tiles) * (8 * 9 + 16)), (0, 0, 0))
                dr = ImageDraw.Draw(sheet)
                for i, (lab, a) in enumerate(tiles):
                    sheet.paste(sim(a), (0, i * (8 * 9 + 16) + 16))
                    dr.text((4, i * (8 * 9 + 16) + 2), f"{lab}  {key}  ATLAS SIMULATION 9 px/texel (not a screen capture)", fill=(255, 255, 0))
                sheet.save(rd / "review" / f"{key}-retrace-sim.png")
        rows.append(row)
        f = row["files"]
        print(key, {v: (f[v]["audit"]["primary_pass"], f[v]["audit"]["s2_strict_pass"], f[v]["vs_authored"]["visible_iou"]) for v in f}, flush=True)
    summ = {}
    for v in ("crisp/2048", "crisp/1024", "soft/2048", "soft/1024"):
        fs = [r["files"][v] for r in rows]
        summ[v] = dict(files=len(fs), primary_pass=sum(x["audit"]["primary_pass"] for x in fs), s2_strict_pass=sum(x["audit"]["s2_strict_pass"] for x in fs),
                       r5_max=max(x["audit"]["r5_fringe_px"] for x in fs), centre_mismatch=sum(x["texel_centre_class_mismatch"] for x in fs),
                       iou_vs_authored=[min(x["vs_authored"]["visible_iou"] for x in fs), max(x["vs_authored"]["visible_iou"] for x in fs)],
                       iou_vs_snap_cell=[min(x["vs_ji_snap_cell"]["visible_iou"] for x in fs), max(x["vs_ji_snap_cell"]["visible_iou"] for x in fs)])
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", job="J-M",
               status="CANDIDATE ALTERNATIVE: not installed, not live-tested, no look acceptance; J-H CLUTs are DERIVED CRC-matched candidates",
               method="frozen w4 EPX of native BDAE4156 strip indices; exact CLUT colours; per-CLUT alpha classes; soft = same-class RGB AA",
               tool_sha256=sha(Path(__file__)), epx_sha256=sha(EPX), class_mip_c_sha256=sha(PROTO / "class_mip.c"),
               ji_result_sha256=sha(JI / "result.json"), summary=summ, rows=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ), flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
