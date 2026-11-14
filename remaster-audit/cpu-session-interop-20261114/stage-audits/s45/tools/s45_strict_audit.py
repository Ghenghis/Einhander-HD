#!/usr/bin/env python3
"""s45 step 2 (claude-einhander-s45, EIN-S4/S5-WHOLE-CELL-20261114): strict whole-cell class audit of the Stage 4 / Stage 5
selected candidate keys (lane-readiness 07cd9358...: S4 world v3, enemies v2, effects v2 AND v3 alternatives; S5 world v2,
Duerer armour v2, effects 3/6 v1). READ-ONLY on the stage lanes; CPU only, below normal, one CPU. Writes ONLY
remaster-audit/parallel-stages-20261114/s45/strict-audit/<UTC>-s<stage>/.

Per rendered key (w7 schema: manifest pages[TEX].rendered_keys[] with png_2048 / png_1024):
  * native words = pages[TEX].source (sha256 vs manifest, CRC32 == TEX); CLUT words = static keys/<KEY>.clut.bin (CRC32 == PAL);
    native class: index (4bpp low nibble first) -> CLUT word 0 = cutout 0, STP bit 15 = 255, else 127;
  * every HD file: sha256 vs manifest; frozen proto-v2b cm_validate (strict s/2: R1 centre, R2 displacement, R3 uniform
    cells (diagnostic), R4 islands, R5 fringe) and cm_flags_ex connectivity-only (R1|R2|R4 bits), with violations also
    counted inside the lane's special regions (FX contract boxes, glyph de-stair, 8bpp pass-through blocks) when listed.
strict_pass = R1 = R2 = R3 = R4 = 0; primary_pass (root policy) = R1 = 0 and connectivity-only = 0; R5 reported separately.
Centre-only lane results (centre_class_mismatch) are recorded next to it; they do not establish whole-cell correctness."""
import argparse
import ctypes
import datetime
import hashlib
import json
import shutil
import subprocess
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
RA = Path("C:/github/Einhander/remaster-audit")
OUT = RA / "parallel-stages-20261114/s45/strict-audit"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
READINESS_SHA = "07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8"
STATIC = RA / "fullgame-prep/static-extraction/stages"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
REPORT_FIELDS = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
                 "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in REPORT_FIELDS]


def sha_b(b):
    return hashlib.sha256(b).hexdigest()


def sha_f(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def native_class(words, clut_b):
    clut = np.frombuffer(clut_b, "<u2")
    w16 = np.frombuffer(words, "<u2").reshape(256, 64)
    if len(clut) != 16:
        raise ValueError(f"CLUT of {len(clut)} entries on a 4bpp page")
    idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], axis=-1).reshape(256, 256)
    lut = np.array([0 if c == 0 else (255 if c & 0x8000 else 127) for c in clut], np.uint8)
    return np.ascontiguousarray(lut[idx]), idx


def region_masks(page):
    """texel-space boolean masks of the lane's listed special regions (FX / glyph boxes [x0,y0,x1,y1] exclusive end, as
    in the w7 manifests, e.g. 1A2ACF78 [0,128,256,192]; 8bpp blocks8 [bx,by] in 8x8-texel units)."""
    out = {}
    for i, r in enumerate(page.get("regions") or []):
        m = np.zeros((256, 256), bool)
        kind = r.get("kind") or f"region{i}"
        boxes = r.get("boxes") or r.get("box") or r.get("rects")
        if isinstance(boxes, list) and boxes and isinstance(boxes[0], (int, float)):
            boxes = [boxes]
        for b in boxes or []:
            if isinstance(b, list) and len(b) == 4:
                x0, y0, x1, y1 = (int(v) for v in b)
                m[max(y0, 0):min(y1, 256), max(x0, 0):min(x1, 256)] = True
        for bx, by in r.get("blocks8") or []:
            m[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8] = True
        if m.any():
            out[f"{kind}#{i}"] = m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, choices=(4, 5), required=True)
    ap.add_argument("--max-seconds", type=float, default=85.0, help="stop starting new files after this wall time")
    a = ap.parse_args()
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / f"{stamp}-s{a.stage}"
    rd.mkdir(parents=True, exist_ok=False)
    import os
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    assert sha_f(READINESS) == READINESS_SHA, "lane-readiness changed"
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    lane = next(s for s in readiness["stages"] if s["stage"] == a.stage)
    dll = rd / "class_mip.dll"
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    compile_rec = dict(returncode=c.returncode, stderr=c.stderr[-2000:], seconds=round(time.time() - t0, 2),
                       class_mip_c_sha256=sha_f(rd / "class_mip.c"), class_mip_h_sha256=sha_f(rd / "class_mip.h"))
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(dll))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    sd = STATIC / f"stage{a.stage}"
    rows, skipped = [], []
    for f in lane["candidate_folders"]:
        mf = Path(f["manifest"])
        assert sha_f(mf) == f["manifest_sha256"], f"manifest changed: {mf}"
        d = mf.parent
        m = json.loads(mf.read_text(encoding="utf-8"))
        for tex, page in (m.get("pages") or {}).items():
            src = page["source"]
            words = Path(src["path"]).read_bytes()
            masks = region_masks(page)
            for rk in page.get("rendered_keys") or []:
                key = rk["key"]
                clut_b = (sd / "keys" / f"{key}.clut.bin").read_bytes()
                base = dict(stage=a.stage, set=d.name, tex=tex, key=key, mode=page.get("mode"),
                            words_sha_ok=sha_b(words) == src["sha256"], tex_crc_proven=crc(words) == tex,
                            clut_crc_proven=crc(clut_b) == key[9:])
                ncls, idx = native_class(words, clut_b)
                base.update(cutout_texels=int((ncls == 0).sum()), stp_texels=int((ncls == 255).sum()))
                for fk in ("png_2048", "png_1024"):
                    fr = rk.get(fk) or {}
                    fp = d / fr.get("path", "?")
                    row = dict(base, file=fk, path=str(fp))
                    if time.time() - t0 > a.max_seconds:
                        skipped.append(dict(key=key, file=fk, set=d.name, reason="time budget"))
                        continue
                    if not fp.is_file():
                        rows.append(dict(row, error="missing file"))
                        continue
                    fsha = sha_f(fp)
                    with Image.open(fp) as im:
                        rgba = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
                    H, W = rgba.shape[:2]
                    if W % 256 or H % 256 or W // 256 != H // 256:
                        rows.append(dict(row, error=f"dims {W}x{H} not a native multiple"))
                        continue
                    s = W // 256
                    rep = CmReport()
                    lib.cm_validate(rgba.ctypes.data, W, H, ncls.ctypes.data, 256, 256, s, ctypes.byref(rep))
                    fl = np.zeros((H, W), np.uint8)
                    lib.cm_flags_ex(rgba.ctypes.data, W, H, ncls.ctypes.data, 256, 256, s, 0.5, 0, fl.ctypes.data)
                    conn = (fl & (2 | 4 | 16)) != 0
                    dev = (fl & 1) != 0
                    v2 = {n: int(getattr(rep, n)) for n in REPORT_FIELDS}
                    # per native cell: any connectivity violation -> bad cell map (texel space)
                    cellbad = conn.reshape(256, s, 256, s).any(axis=(1, 3))
                    inreg = {}
                    for rn, msk in masks.items():
                        mh = np.repeat(np.repeat(msk, s, 0), s, 1)
                        inreg[rn] = dict(texels=int(msk.sum()), conn_viol_px=int((conn & mh).sum()), bad_cells=int((cellbad & msk).sum()))
                    alpha = np.unique(rgba[..., 3])
                    worst = np.argwhere(cellbad)
                    rows.append(dict(row, sha256=fsha, sha_ok=fsha == fr.get("sha256"), scale=s, v2=v2,
                                     conn_viol_px=int(conn.sum()), deviant_px=int(dev.sum()), conn_bad_cells=int(cellbad.sum()),
                                     bad_cell_examples=[[int(u), int(v)] for v, u in worst[:12]],
                                     alpha_values=[int(x) for x in alpha[:8]], regions=inreg,
                                     strict_pass=all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px")),
                                     primary_pass=v2["r1_centre_bad"] == 0 and int(conn.sum()) == 0,
                                     lane_centre_class_mismatch=(fr.get("validation") or {}).get("centre_class_mismatch")))
                    del rgba, fl, conn, dev
    summ = {}
    for r in rows:
        g = summ.setdefault(r["set"], dict(files=0, errors=0, sha_ok=0, strict_pass=0, primary_pass=0, r5_files=0, keys=set(), worst=[]))
        g["keys"].add(r["key"])
        if "error" in r:
            g["errors"] += 1
            continue
        g["files"] += 1
        g["sha_ok"] += int(r["sha_ok"])
        g["strict_pass"] += int(r["strict_pass"])
        g["primary_pass"] += int(r["primary_pass"])
        g["r5_files"] += int(r["v2"]["r5_fringe_px"] > 0)
        g["worst"].append([r["key"], r["file"], r["v2"]["r1_centre_bad"], r["conn_viol_px"], r["conn_bad_cells"], r["v2"]["r5_fringe_px"]])
    for g in summ.values():
        g["keys"] = sorted(g["keys"])
        g["worst"] = sorted(g["worst"], key=lambda x: -x[3])[:12]
    res = dict(run=f"{stamp}-s{a.stage}", owner="claude-einhander-s45", stage=a.stage, readiness_sha256=READINESS_SHA, compile=compile_rec,
               rule="frozen proto-v2b cm_validate strict s/2 + cm_flags_ex(0.5, Euclidean) connectivity-only R1|R2|R4 "
                    "(root policy: R1 + connectivity primary; s/2 strict and R3 diagnostic; R5 fringe separate)",
               summary=summ, rows=rows, skipped=skipped, seconds=round(time.time() - t0, 1),
               status="DATA ONLY; read-only on the stage lanes; no art edits; not visual or live acceptance")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for n, g in summ.items():
        print(f'S{a.stage} {n:24s} keys={len(g["keys"])} files={g["files"]} err={g["errors"]} sha_ok={g["sha_ok"]} strict={g["strict_pass"]}/{g["files"]} '
              f'primary={g["primary_pass"]}/{g["files"]} r5_files={g["r5_files"]} worst={g["worst"][:3]}')
    print("skipped", len(skipped), "seconds", res["seconds"], "run", res["run"], "result", sha_f(rd / "result.json"))


if __name__ == "__main__":
    main()
