#!/usr/bin/env python3
"""s45 R-D (claude-einhander-s45, EIN-S5-WHOLE-CELL-20261114): whole-cell class-ownership REPAIR COPIES of frozen exports.

Input: one frozen set + key (w7 schema). For each export (png_2048, png_1024) of that key: copy the frozen PNG (sha256
re-checked against the manifest), run the frozen proto-v2b cm_repair (R1/R2/R4 violators take their cell's native class,
iterated until clean; visible RGB of pixels that stay visible is never modified, proof field visible_rgb_changed must be 0)
with the native class map (CRC-proven words + CLUT) and the native colours, then validate before/after: cm_validate (s/2
strict), cm_flags_ex connectivity-only (root policy, bound 1e9) and s/2 flags, centre classes, alpha values, and the pixel
diff (class-changed / RGB-changed counts). The frozen file is never modified. Output = candidate repair copies for review,
not acceptance and not installable (predicted-static key).
Writes ONLY s45/repairs/<UTC>-cmrepair-<KEY>/. Below normal, one CPU.

    python -I -B tools/s45_cm_repair.py --set <frozen set dir> --key <TEX-PAL>
    python -I -B tools/s45_cm_repair.py --probe-run <s45 probe-audit run dir> --key <TEX-PAL>
The second form repairs copies of AUDIT-ONLY probe exports (option 2 of REPAIR-PROPOSALS 'FX class-ownership plan':
any-pair masters + per-key post-render class snap), CLUT words from cluts.json at the probe's clut_xy."""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time
import zlib
from pathlib import Path

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
STATIC = RA / "fullgame-prep/static-extraction/stages"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
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


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="", help="frozen set dir (rendered key of its manifest)")
    ap.add_argument("--probe-run", default="", help="s45 probe-audit run dir (audit-only probe exports of --key)")
    ap.add_argument("--key", required=True)
    ap.add_argument("--fill", default="cell", choices=("cell", "nearest"),
                    help="colour of pixels that become visible: 'cell' = frozen cm_repair cell mean (default); 'nearest' = "
                         "s45 post-pass, RGB of the nearest originally visible pixel (continues the soft gradient; review "
                         "jf-20261114T144943Z found flat cell-mean blocks on soft FX edges)")
    a = ap.parse_args()
    assert bool(a.set) != bool(a.probe_run), "give exactly one of --set / --probe-run"
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    t0 = time.time()
    tex, pal = a.key.split("-")
    if a.set:   # frozen deliverable: files and source from its manifest
        d = Path(a.set)
        src_manifest = d / "manifest.json"
        m = json.loads(src_manifest.read_text(encoding="utf-8"))
        pg = m["pages"][tex]
        rk = next(r for r in pg["rendered_keys"] if r["key"] == a.key)
        stage = int(m.get("stage") or (4 if "w7-stage4" in d.as_posix() else 5))
        words_path, words_sha = Path(pg["source"]["path"]), pg["source"]["sha256"]
        files = [(fk, d / rk[fk]["path"], rk[fk]["sha256"]) for fk in ("png_2048", "png_1024")]
        clut_xy = rk.get("clut_xy")
    else:       # audit probe: files and CLUT position from the probe run's result.json
        d = Path(a.probe_run)
        src_manifest = d / "result.json"
        pr = json.loads(src_manifest.read_text(encoding="utf-8"))
        prow = [r for r in pr["rows"] if r.get("key") == a.key and "error" not in r]
        assert prow, f"{a.key} not in {d}"
        stage = int(pr["stage"])
        words_path = STATIC / f"stage{stage}" / "textures" / f"{tex}.words.bin"
        words_sha = hashlib.sha256(words_path.read_bytes()).hexdigest()
        files = [(f"png_{r['size']}", Path(r["png"]), r["sha256"]) for r in prow]
        clut_xy = prow[0].get("clut_xy")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "repairs" / (f"{stamp}-cmrepair-{a.key}" + ("-nearest" if a.fill == "nearest" else ""))
    rd.mkdir(parents=True, exist_ok=False)
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
    words = words_path.read_bytes()
    assert crc(words) == tex and hashlib.sha256(words).hexdigest() == words_sha
    kp = STATIC / f"stage{stage}" / "keys" / f"{a.key}.clut.bin"
    if kp.is_file():
        cb = kp.read_bytes()
    else:   # most static keys have no per-key file: CLUT words from cluts.json at the key's clut_xy
        cl = {(e["x"], e["y"], e["pal"]): e["words_hex"] for e in json.loads((STATIC / f"stage{stage}" / "cluts.json").read_text(encoding="utf-8"))}
        cb = bytes.fromhex(cl[(clut_xy[0], clut_xy[1], pal)])
    assert crc(cb) == pal
    clut = np.frombuffer(cb, "<u2")
    w16 = np.frombuffer(words, "<u2").reshape(256, 64)
    idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)
    lut = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in clut], np.uint8)
    ncls = np.ascontiguousarray(lut[idx])
    rgb = np.stack([(clut & 31) * 8, ((clut >> 5) & 31) * 8, ((clut >> 10) & 31) * 8], -1).astype(np.uint8)
    nrgb = np.ascontiguousarray(rgb[idx])

    def check(img, s):
        H, W = img.shape[:2]
        rep = CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, 256, 256, s, ctypes.byref(rep))
        out = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, 256, 256, s, bound, 0, fl.ctypes.data)
            out[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        ys = (np.arange(256) * s + s // 2)
        out["centre_class_mismatch"] = int((img[np.ix_(ys, ys)][..., 3] != ncls).sum())
        out["alpha_values"] = sorted(int(x) for x in np.unique(img[..., 3]))
        return out

    rows = []
    for fk, src, want_sha in files:
        fr = dict(sha256=want_sha)
        assert sha(src) == want_sha, f"input file changed: {src}"
        with Image.open(src) as im:
            before = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
        s = before.shape[1] // 256
        img = before.copy()
        pre = check(before, s)
        st = CmRepairStats()
        rc = lib.cm_repair(img.ctypes.data, img.shape[1], img.shape[0], ncls.ctypes.data, nrgb.ctypes.data, 256, 256, s, ctypes.byref(st))
        stats = {n: int(getattr(st, n)) for n in SF}
        if a.fill == "nearest":   # recolour only pixels that became visible; classes and originally visible RGB unchanged
            from scipy import ndimage as ndi
            orig_vis = (before[..., 3] != 0) & (img[..., 3] != 0)
            newv = (before[..., 3] == 0) & (img[..., 3] != 0)
            if newv.any() and orig_vis.any():
                _, (iy, ix) = ndi.distance_transform_edt(~orig_vis, return_indices=True)
                img[newv, :3] = img[iy[newv], ix[newv], :3]
            stats["s45_nearest_fill_px"] = int(newv.sum())
        post = check(img, s)
        vis_both = (before[..., 3] != 0) & (img[..., 3] != 0)
        diff = dict(class_changed_px=int((before[..., 3] != img[..., 3]).sum()),
                    rgb_changed_px=int((before[..., :3] != img[..., :3]).any(-1).sum()),
                    rgb_changed_on_visible_both=int(((before[..., :3] != img[..., :3]).any(-1) & vis_both).sum()))
        out = rd / f"{a.key}-{fk[4:]}-cmrepair.png"
        Image.fromarray(img).save(out, compress_level=6)
        rows.append(dict(file=fk, source=str(src), source_sha256=fr["sha256"], scale=s, repair_rc=rc, repair_stats=stats,
                         before=pre, after=post, diff=diff, output=out.name, output_sha256=sha(out),
                         clean_after=post["r1_centre_bad"] == 0 and post["s2_viol_px"] == 0 and post["conn_viol_px"] == 0,
                         proof_visible_rgb_unchanged=stats["visible_rgb_changed"] == 0 and diff["rgb_changed_on_visible_both"] == 0))
        print(fk, "rc", rc, "before s2", pre["s2_viol_px"], "conn", pre["conn_viol_px"], "-> after s2", post["s2_viol_px"],
              "conn", post["conn_viol_px"], "R1", post["r1_centre_bad"], "class_changed", diff["class_changed_px"],
              "rgb_changed_visible", diff["rgb_changed_on_visible_both"], stats, flush=True)
    res = dict(run=rd.name, owner="claude-einhander-s45", fill=a.fill, input=str(d), input_kind="frozen set" if a.set else "audit probe run",
               key=a.key, clut_xy=clut_xy, input_record_sha256=sha(src_manifest),
               rows=rows, seconds=round(time.time() - t0, 1),
               status="CANDIDATE REPAIR COPY for review; frozen originals untouched; predicted-static key, not installable")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print("seconds", res["seconds"], "result", sha(rd / "result.json"))


if __name__ == "__main__":
    main()
