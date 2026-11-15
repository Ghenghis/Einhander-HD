#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114): NEW CANDIDATE for the undelivered HUD hit-gauge arrow strip B24C6DA2.

The state register (menu-hud/state-register) finds B24C6DA2-* (11 hit-gauge ramp CLUTs at 256,501; 8-row upload of the
player page 832,256 rows 64-71; drawn uv [0,64,63,71] in research runs) in no frozen lane. Only the legacy v13 pack has an
authored HUD-origin PNG. Method (same family as w4-signs-hud hud-lives-glyphs, which renders the gauge digits on the same
page with the same CLUTs):
  * native 4bpp words + CLUT from the archived stock source (byte inputs hashed);
  * index-space EPX / Scale2x from the FROZEN w4 builder snapshot (epx.py.txt), k = 4/3/2 passes for 16x/8x/4x:
    1-texel staircases become 45-degree edges, straight runs stay straight, no new index values, CLUT independent;
  * crisp = exact CLUT colours per upscaled index; alpha class per CLUT (0 cutout, 255 STP, 127 opaque);
  * soft alternative = RGB anti-aliased ONLY among indices of the same class (alpha classes untouched).
No fonts, no generated imagery. Every output is validated with the frozen proto-v2b class_mip (R1 + conn-only primary;
s/2 diagnostic; R5 reported), plus an independent texel-centre label check. The legacy v13 PNGs are validated read-only.
Writes ONLY s45/menu-hud/gauge-B24C6DA2-v1/<UTC>/. Status: CANDIDATE, not installed, not live-tested.
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
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
STOCK = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
TYPO = RA / "comfy-authoring/t9-title-menus/inventory/typography-inventory.json"
EPX = RA / "comfy-authoring/w4-signs-hud/frozen/hud-lives-glyphs-832p256-w4-v1/builder-snapshot/epx.py.txt"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
TEX = "B24C6DA2"
SIZES = {"pack": 4, "runtime-2048": 3, "runtime-1024": 2}       # EPX passes -> 16x / 8x / 4x
REVIEW_CLUTS = ("D2D9B701", "EE4896FB", "D6B2BFF7")             # all lit / half lit / none lit
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/gauge-B24C6DA2-v1" / stamp
    for sub in list(SIZES) + [f"alt-soft/{s}" for s in SIZES] + ["review"]:
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
    typo = json.loads(TYPO.read_text(encoding="utf-8"))["keys"]
    keys = sorted(k for k in typo if k.startswith(TEX + "-"))
    words = {}
    for k in keys:
        words[k] = (STOCK / f"{k}.words.bin").read_bytes()
    assert len(set(words.values())) == 1, "strip words differ between CLUT aliases"
    w = np.frombuffer(words[keys[0]], "<u2").reshape(8, 64)
    idx = np.stack([(w >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(8, 256).astype(np.uint8)
    U = {sz: E.upscale(idx, k) for sz, k in SIZES.items()}
    centre_ok = {}
    for sz, k in SIZES.items():
        s = 2 ** k
        centre_ok[sz] = int(sum((U[sz][o::s, o::s] != idx).sum() for o in {s // 2 - 1, s // 2}))
    assert all(v == 0 for v in centre_ok.values()), centre_ok

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

    rows, review = [], {}
    for k in keys:
        cw = np.fromfile(STOCK / f"{k}.clut.bin", dtype="<u2")
        assert len(cw) == 16
        cls = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in cw], np.uint8)
        rgb = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
        ncls = np.ascontiguousarray(cls[idx])
        row = dict(key=k, clut_words_hex=[f"0x{v:04x}" for v in cw], classes_per_entry=cls.tolist(),
                   inputs=dict(words=str(STOCK / f"{k}.words.bin"), words_sha256=sha(STOCK / f"{k}.words.bin"),
                               clut=str(STOCK / f"{k}.clut.bin"), clut_sha256=sha(STOCK / f"{k}.clut.bin"),
                               source_json=json.loads((STOCK / f"{k}.source.json").read_text(encoding="utf-8"))),
                   files={})
        for sz, kk in SIZES.items():
            s = 2 ** kk
            u = U[sz]
            crisp = np.ascontiguousarray(np.dstack([rgb[u], cls[u]]))
            wts = E.aa_weights(u, present=np.unique(u), sigma=0.6)          # (16,H,W) categorical weights
            same = (cls[:, None, None] == cls[u][None])                     # only same-class indices may mix
            wts = wts * same
            wts /= np.maximum(wts.sum(0, keepdims=True), 1e-6)
            soft_rgb = np.clip(np.einsum("ihw,ic->hwc", wts, rgb.astype(np.float32)) + 0.5, 0, 255).astype(np.uint8)
            soft = np.ascontiguousarray(np.dstack([soft_rgb, cls[u]]))
            for var, img, sub in (("crisp", crisp, sz), ("soft", soft, f"alt-soft/{sz}")):
                fn = rd / sub / f"{k}.png"
                Image.fromarray(img).save(fn, compress_level=6)
                with Image.open(fn) as im:
                    back = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
                assert np.array_equal(back, img)
                cen = int(sum((back[o::s, o::s, 3] != ncls).sum() for o in {s // 2 - 1, s // 2}))
                row["files"][f"{var}/{sz}"] = dict(path=str(fn.relative_to(rd)), sha256=sha(fn), dims=list(img.shape[1::-1]),
                                                   texel_centre_class_mismatch=cen, audit=check(back, ncls, s))
            if sz == "pack" and k[9:] in REVIEW_CLUTS:
                review[k] = (crisp, soft, rgb, cls)
        v13 = typo[k].get("v13") or {}
        if v13.get("exists") and Path(v13["pack_png"]).is_file():
            with Image.open(v13["pack_png"]) as im:
                a = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            row["legacy_v13"] = dict(path=v13["pack_png"], sha256=sha(v13["pack_png"]), dims=list(a.shape[1::-1]),
                                     alpha_values=sorted(int(x) for x in np.unique(a[..., 3]))[:12],
                                     audit=check(a, ncls, a.shape[1] // 256) if a.shape[1] % 256 == 0 and a.shape[0] == 8 * (a.shape[1] // 256) else None)
            if k in review:
                review[k] = review[k] + (a,)
        rows.append(row)
        f = row["files"]
        print(k, {v: (f[v]["audit"]["primary_pass"], f[v]["audit"]["s2_strict_pass"], f[v]["audit"]["r5_fringe_px"]) for v in f},
              "v13", (row.get("legacy_v13") or {}).get("audit", {}) and row["legacy_v13"]["audit"]["primary_pass"], flush=True)
    # review: drawn region x 0..63 (uv [0,64,63,71]) at 2160p HUD simulation (9 px/texel) and at 16x
    for k, tup in review.items():
        crisp, soft, rgb, cls = tup[:4]
        v13 = tup[4] if len(tup) > 4 else None
        nat = np.dstack([np.repeat(np.repeat(rgb[idx], 16, 0), 16, 1), np.repeat(np.repeat(cls[idx], 16, 0), 16, 1)])
        tiles = [("native nearest", nat), ("legacy v13 (HUD origin)", v13), ("candidate crisp", crisp), ("alt soft", soft)]
        tiles = [(n, a) for n, a in tiles if a is not None]

        def flat(a, w_px, h_px):
            a = a[:, :64 * 16].astype(np.float32)
            vis = a[..., 3:4] > 0
            rgbv = np.where(vis, a[..., :3], 24.0)
            return Image.fromarray(rgbv.astype(np.uint8)).resize((w_px, h_px), Image.BOX)
        pad = 18
        sheet = Image.new("RGB", (64 * 16 + 64 * 9 + 24, len(tiles) * (128 + pad)), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for i, (n, a) in enumerate(tiles):
            y = i * (128 + pad) + pad
            sheet.paste(flat(a, 64 * 16, 128), (0, y))
            sheet.paste(flat(a, 64 * 9, 72), (64 * 16 + 24, y))
            dr.text((4, y - pad + 3), f"{n}  {k}  16x | HUD SIMULATION 9 px/texel (2160p)", fill=(255, 255, 0))
        sheet.save(rd / "review" / f"{k}-gauge-review.png")
    summ = {}
    for v in ("crisp/pack", "crisp/runtime-2048", "crisp/runtime-1024", "soft/pack", "soft/runtime-2048", "soft/runtime-1024"):
        summ[v] = dict(files=len(rows), primary_pass=sum(r["files"][v]["audit"]["primary_pass"] for r in rows),
                       s2_strict_pass=sum(r["files"][v]["audit"]["s2_strict_pass"] for r in rows),
                       r5_fringe_px_max=max(r["files"][v]["audit"]["r5_fringe_px"] for r in rows),
                       centre_mismatch=sum(r["files"][v]["texel_centre_class_mismatch"] for r in rows))
    leg = [r["legacy_v13"]["audit"] for r in rows if (r.get("legacy_v13") or {}).get("audit")]
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", texture=TEX,
               status="CANDIDATE: not installed, not live-tested, not accepted; crisp = primary candidate, soft = alternative",
               method="index-space EPX (frozen w4 epx.py.txt) of native stock words; exact CLUT colours; per-CLUT alpha classes",
               draw_evidence="typography-inventory draw_evidence: uv [0,64,63,71] at clut_xy (256,501), page (832,256), semi 0",
               tool_sha256=sha(Path(__file__)), epx_sha256=sha(EPX), class_mip_c_sha256=sha(PROTO / "class_mip.c"),
               typography_inventory_sha256=sha(TYPO), words_identical_across_cluts=True,
               epx_texel_centre_label_mismatch=centre_ok, summary=summ,
               legacy_v13=dict(files=len(leg), primary_pass=sum(a["primary_pass"] for a in leg)),
               keys=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ), "v13", out["legacy_v13"], flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
