#!/usr/bin/env python3
"""s45 (claude-einhander-s45, EIN-S4/S5-WHOLE-CELL-20261114): transparency PROBE renders + strict whole-cell audit.

Why: none of the 23 selected review CLUTs has a cutout (word 0) entry, so the frozen exports never exercise cutout class
edges or R5 fringe. clut-coverage 20261114T135254Z shows 2-15 static candidate CLUTs per selected page that DO create
cutout texels. This job renders, per selected page (and per effects alternative), the candidate key with the largest
cutout share among multi-class keys, from the FROZEN palette-independent master of that set, with that set's own builder
code (frozen/<set>/builder/w7lib.py + build_w7.py: render -> export_rgba -> energy gate for effect pages -> re-export, the
same path build_w7 uses), then runs the frozen proto-v2b validator (cm_validate strict s/2 + cm_flags_ex connectivity-only
+ R5 fringe) on the 2048 and 1024 exports.

Outputs are AUDIT PROBES, not deliverables: the key is predicted-static and unconfirmed; nothing here may be installed.
READ-ONLY on every lane. Writes ONLY s45/probe-audit/<UTC>-s<stage>/. Below normal, one CPU, OMP/BLAS 1.

    python -I -B tools/s45_probe_audit.py --stage 4 [--pages TEX,TEX] [--max-seconds 80]"""
import argparse
import ctypes
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(v, "1")
import numpy as np  # noqa: E402

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
READINESS_SHA = "07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8"
COVERAGE = S45 / "clut-coverage/20261114T135254Z/coverage.json"
COVERAGE_SHA = "26f22df2dbd9ae1ee2796e5586597f67fde24393c495f0cdcfea02bd3b073be0"
STATIC = RA / "fullgame-prep/static-extraction/stages"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
FIELDS = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
          "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in FIELDS]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def load_builder(set_dir):
    """the set's own frozen builder code, isolated per set (module names keyed by the set)."""
    bdir = set_dir / "builder"
    spec = importlib.util.spec_from_file_location(f"w7lib_{set_dir.name}", bdir / "w7lib.py")
    L7 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L7)
    saved = sys.modules.get("w7lib")
    sys.modules["w7lib"] = L7
    sys.path.insert(0, str(bdir))
    try:
        spec_b = importlib.util.spec_from_file_location(f"build_w7_{set_dir.name}", bdir / "build_w7.py")
        B = importlib.util.module_from_spec(spec_b)
        spec_b.loader.exec_module(B)
    finally:
        sys.path.remove(str(bdir))
        if saved is not None:
            sys.modules["w7lib"] = saved
        else:
            sys.modules.pop("w7lib", None)
    job = json.loads(next(bdir.glob("*.json")).read_text(encoding="utf-8"))
    return L7, B, job


def pick_probe(page_cov):
    cands = [k for k in page_cov["keys"] if "error" not in k and not k["all_zero"] and k["cutout_share"] > 0
             and k["classes_present"] >= 2 and k["role"] != "rendered"]
    if not cands:
        return None
    return max(cands, key=lambda k: (k["cutout_share"] if k["cutout_share"] < 0.99 else -1, k["pair_count"] or 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, choices=(4, 5), required=True)
    ap.add_argument("--pages", default="")
    ap.add_argument("--max-seconds", type=float, default=80.0)
    a = ap.parse_args()
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "probe-audit" / f"{stamp}-s{a.stage}"
    rd.mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    assert sha(READINESS) == READINESS_SHA and sha(COVERAGE) == COVERAGE_SHA
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    dll = rd / "class_mip.dll"
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(dll))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    cov = json.loads(COVERAGE.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    lane = next(s for s in readiness["stages"] if s["stage"] == a.stage)
    sd = STATIC / f"stage{a.stage}"
    cl_words = {(e["x"], e["y"], e["pal"]): e["words_hex"] for e in json.loads((sd / "cluts.json").read_text(encoding="utf-8"))}
    want = set(x for x in a.pages.split(",") if x)
    rows, skipped = [], []
    for f in lane["candidate_folders"]:
        d = Path(f["path"])
        assert sha(d / "manifest.json") == f["manifest_sha256"]
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        L7 = B = job = None
        for tex, pg in m["pages"].items():
            if want and tex not in want:
                continue
            pc = cov["pages"][f"S{a.stage}:{tex}"]
            pk = pick_probe(pc)
            base = dict(set=d.name, tex=tex, mode=pg.get("mode"))
            if pk is None:
                rows.append(dict(base, error="no multi-class cutout candidate"))
                continue
            if time.time() - t0 > a.max_seconds:
                skipped.append(dict(base, key=pk["key"], reason="time budget"))
                continue
            if L7 is None:
                L7, B, job = load_builder(d)
            key = pk["key"]
            xy = pk["clut_xy"]
            cb = bytes.fromhex(cl_words[(xy[0], xy[1], key[9:])])
            assert crc(cb) == key[9:]
            words = np.frombuffer(cb, "<u2").copy()
            rgb, cls = L7.clut_rgba(words)
            md = d / "master"
            idx = np.load(md / f"{tex}-native-idx.npy")
            z = np.load(md / f"{tex}-labels16.npz")
            Lb, Wt = z["labels"], z["weights"]
            logD = np.load(md / f"{tex}-logD8-f16.npy") if (md / f"{tex}-logD8-f16.npy").is_file() else None
            glow = np.load(md / f"{tex}-glow16-f16.npy").astype(np.float32) if (md / f"{tex}-glow16-f16.npy").is_file() else None
            glow_mask, glow_used = None, None
            if glow is not None:
                opaque = [i for i in range(16) if cls[i] != 0]
                used = [i for i in np.unique(idx).tolist() if i in opaque]
                rho = B.monotone(rgb, used)
                if rho >= job.get("ramp_min", 0.85):
                    gw = md / f"{tex}-glowweight16-u8.npy"
                    glow_mask = (np.load(gw).astype(np.float32) / 255) if gw.is_file() else np.ones(glow.shape, bool)
                    glow_used = f"glow (rho {rho:.3f})"
                else:
                    glow, glow_used = None, f"shape (probe CLUT not a ramp, rho {rho:.3f})"
            rgb16, c16 = L7.render(Lb, Wt, rgb, cls, logD=logD, glow=glow, glow_mask=glow_mask)
            ncls = np.ascontiguousarray(cls[idx])
            for size in (2048, 1024):
                ex, changed = L7.export_rgba(rgb16, c16, idx, rgb, cls, size)
                en = None
                if pg.get("mode") == "effect" or job.get("mode") == "effect":
                    gate = B.energy_gate_smooth if (job.get("energy_smooth") and hasattr(B, "energy_gate_smooth")) else B.energy_gate
                    en = gate(ex, idx, rgb, cls, size)
                    ex, _ = L7.export_rgba(ex[..., :3].astype(np.float32), ex[..., 3], idx, rgb, cls, size)
                v = L7.validate(ex, idx, cls)
                p = rd / d.name / f"{key}-PROBE-{size}.png"
                h = L7.save_png(ex, p)
                rgba = np.ascontiguousarray(ex)
                s = size // 256
                rep = CmReport()
                lib.cm_validate(rgba.ctypes.data, size, size, ncls.ctypes.data, 256, 256, s, ctypes.byref(rep))
                fl = np.zeros((size, size), np.uint8)
                lib.cm_flags_ex(rgba.ctypes.data, size, size, ncls.ctypes.data, 256, 256, s, 0.5, 0, fl.ctypes.data)
                conn = (fl & (2 | 4 | 16)) != 0
                cellbad = conn.reshape(256, s, 256, s).any(axis=(1, 3))
                v2 = {n: int(getattr(rep, n)) for n in FIELDS}
                # R5 magnitude: cutout px whose RGB is not black next to a visible px (the export writes raw black)
                cut = rgba[..., 3] == 0
                rows.append(dict(base, key=key, role="probe", clut_xy=xy, pair_count=pk["pair_count"], palette_hold=pk["palette_hold"],
                                 cutout_share=pk["cutout_share"], stp_share=pk["stp_share"], size=size, scale=s, png=str(p), sha256=h,
                                 centre_classes_stamped=changed, lane_validate=v, glow=glow_used, energy=bool(en), v2=v2,
                                 conn_viol_px=int(conn.sum()), deviant_px=int(((fl & 1) != 0).sum()), conn_bad_cells=int(cellbad.sum()),
                                 bad_cell_examples=[[int(u), int(vv)] for vv, u in np.argwhere(cellbad)[:12]],
                                 cutout_px=int(cut.sum()), cutout_nonblack_px=int((cut & (rgba[..., :3].max(-1) > 0)).sum()),
                                 strict_pass=all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px")),
                                 primary_pass=v2["r1_centre_bad"] == 0 and int(conn.sum()) == 0))
                print(f"{d.name:22s} {key} {size} R1 {v2['r1_centre_bad']} R2 {v2['r2_displaced_px']} R3 {v2['r3_uniform_bad_px']} "
                      f"R4 {v2['r4_island_px']} R5 {v2['r5_fringe_px']} conn {int(conn.sum())} badcells {int(cellbad.sum())} "
                      f"cut {int(cut.sum())} centre {v['centre_class_mismatch']} {time.time() - t0:.1f}s", flush=True)
                del ex, rgba, fl, conn
            del rgb16, c16, Lb, Wt
    res = dict(run=f"{stamp}-s{a.stage}", owner="claude-einhander-s45", stage=a.stage, coverage_sha256=COVERAGE_SHA,
               rule="frozen proto-v2b cm_validate strict s/2 + cm_flags_ex(0.5) connectivity-only R1|R2|R4; R5 fringe separate",
               rows=rows, skipped=skipped, seconds=round(time.time() - t0, 1),
               status="AUDIT PROBES ONLY (predicted-static candidate CLUTs, unconfirmed keys); not deliverables, not acceptance")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    ok = [r for r in rows if "error" not in r]
    print("probes", len(ok), "strict", sum(r["strict_pass"] for r in ok), "primary", sum(r["primary_pass"] for r in ok),
          "r5_files", sum(r["v2"]["r5_fringe_px"] > 0 for r in ok), "skipped", len(skipped), "seconds", res["seconds"],
          "result", sha(rd / "result.json"))


if __name__ == "__main__":
    main()
