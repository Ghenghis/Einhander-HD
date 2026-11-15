#!/usr/bin/env python3
"""s67 R-B r0: native-fill whole-cell class repair of ONE 95A3BCF8 E exact-region crop (plan 6780484c §4 R-B).
SOURCE ONLY until a CPU grant. Read-only on every input; writes ONLY a new exclusive folder
s67/repairs/eregion-classrepair-r0-<KEY>-<UTC>/ (never the staging pack, w2-v2 frozen folder or any runtime file).

First (and default) target 22D9BF19-00A1D33C: uv [160,0,192,32] of the 95A3BCF8 page at 4bpp, HD crop 256x256 (scale 8).
Inputs, all pinned and verified before any decode:
  * HD crop = staged raw37c-r6 pack file einhander-texture-replacements/22D9BF19-<PAL>.png (sha = staging png_pins entry) and
    byte-identical to w2-v2 runtime/95A3BCF8-<PAL>-Eregion-uv160_0_192_32-256.png;
  * crop native words = the 8-word x 32-row slice (word columns 40..47, rows 0..31) of the shared w2-v2 page words 29706a63,
    derived in-process; for 00A1D33C its sha must be 9b21bf88 (512 B) as in the plan;
  * CLUT = w2-v2 source/95A3BCF8-<PAL>.clut.bin (32 B; 00A1D33C: 9e3e9d56);
  * class_mip.dll = PREBUILT s67 r2b dll 509a2bb1; its folder's class_mip.c/.h must equal frozen proto-v2b; no compiler.
Method = s6_fx_classrepair.py (b7d6757a) --fill=native, unchanged in substance:
  COPY -> cm_repair (native class from crop words + CLUT) -> restore v1 RGB on every pixel that is cutout after repair ->
  newly visible pixels take their native texel RGB -> cm_validate (whole-cell strict on the 1024-cell crop) and cm_flags_ex
  bits 2|4|16 before/after at 0.5 and 1e9. Reports became_visible, became_cutout, stp_toggled, visible_rgb_changed.
NOT an acceptance (a live look still follows) and NOT staged anywhere: integration is codex-einhander's.
Usage: python -I -B s67_eregion_classrepair_r0.py [--dry-run] [--pal=00A1D33C] [--cpu=N] [--budget-s=50]"""
import ctypes
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
RA = ROOT / "remaster-audit"
S67 = RA / "parallel-stages-20261114/s67"
sys.path.insert(0, str(S67 / "tools"))
import s67_strict_audit as A  # noqa: E402  (native_class, CmReport, PROTO; import is side-effect-free)

W2 = RA / "comfy-authoring/w2-polish/frozen/atlas-95A3BCF8-w2-v2"
PIN = {
    "audit_module": (S67 / "tools/s67_strict_audit.py", "9ba1ef4d92d693482f6c855e136950dfbe734df8e18c22767a955c7c3313faf0"),
    "method_lineage": (S67 / "tools/s6_fx_classrepair.py", "b7d6757a6c96b54a05c976c76301216356e414bf5428cfba7f53a9ce9086697d"),
    "staging": (RA / "dev-center-evidence/stage1-completion-20261112/raw37c-r6-20261114T2331Z/hd-on_rewind-off/raw37c-staging.json",
                "2710782ef5627a16f9c1528ac1f662d80bd03a1cb5985365c5ef1db04f809c79"),
    "dll": (S67 / "repairs/stage6-fx-classrepair-r2b-nativefill/class_mip.dll",
            "509a2bb1f4db2ee191c8509429d55c4bb5194ff04767ac0bfa8fa6da96c18420"),
    "proto_c": (A.PROTO / "class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    "proto_h": (A.PROTO / "class_mip.h", "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"),
}
PAGE_WORDS_SHA = "29706a6386158ab3f4b5f08de5c0ca6cf509c6d7436ed3bf5402d69f7b8658d2"
UV = (160, 0, 192, 32)                  # u0, v0, u1, v1 native texels (ExactRegions.tsv x=744 y=0 w=8 h=32, 4bpp)
PAGE_WW, PAGE_HH = 64, 256              # page words per row, rows
EXPECT = {"00A1D33C": dict(crop_words="9b21bf8804747f33fbe9e68ae20adaa5292cd55a367f25e231b674f0837abeb2",
                           clut="9e3e9d567ec1919ce8284e5ce48400547f502dbb508e4891e023e7788aed3dd7",
                           hd="5e1ab56d6783ea3f885f35221f7d0f431b553ec6147835e9e14529113598e6fa")}
BITS = 2 | 4 | 16


class CmRepairStats(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("class_changed", "became_visible", "became_cutout", "rgb_from_cell",
                                               "rgb_from_native", "cutout_rgb_filled", "visible_rgb_changed", "passes",
                                               "residual_violations")]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_pins():
    for name, (p, want) in PIN.items():
        got = sha(p)
        assert got == want, f"pin {name} {p}: {got} != {want}"
    for n in ("class_mip.c", "class_mip.h"):
        assert sha(PIN["dll"][0].parent / n) == sha(A.PROTO / n), f"prebuilt dll folder {n} differs from proto-v2b"
    log = (PIN["dll"][0].parent / "compile.log").read_text(encoding="utf-8", errors="replace")
    assert log.startswith("exit 0"), "prebuilt dll compile.log does not start with 'exit 0'"


def inputs(pal, staging):
    key = f"22D9BF19-{pal}"
    rel = f"einhander-texture-replacements/{key}.png"
    pins = staging["pack"]["png_pins"]
    assert rel in pins, f"{key} not staged"
    staged = Path(staging["pack"]["root"]) / rel
    w2 = W2 / "runtime" / f"95A3BCF8-{pal}-Eregion-uv{UV[0]}_{UV[1]}_{UV[2]}_{UV[3]}-256.png"
    hd_sha = sha(staged)
    assert hd_sha == pins[rel], f"{staged} sha {hd_sha} != staging pin {pins[rel]}"
    assert sha(w2) == hd_sha, f"staged {key} is not byte-identical to w2-v2 {w2.name}"
    words_p, clut_p = W2 / "source" / f"95A3BCF8-{pal}.words.bin", W2 / "source" / f"95A3BCF8-{pal}.clut.bin"
    assert sha(words_p) == PAGE_WORDS_SHA, f"{words_p} is not the shared page words 29706a63"
    page = words_p.read_bytes()
    assert len(page) == PAGE_WW * PAGE_HH * 2, len(page)
    c0, c1 = UV[0] // 4, UV[2] // 4          # 4 texels per u16 at 4bpp
    crop = b"".join(page[r * PAGE_WW * 2 + c0 * 2: r * PAGE_WW * 2 + c1 * 2] for r in range(UV[1], UV[3]))
    clut = clut_p.read_bytes()
    assert len(clut) == 32, f"{clut_p} not 32 B (4bpp)"
    got = dict(crop_words=hashlib.sha256(crop).hexdigest(), clut=sha(clut_p), hd=hd_sha)
    if pal in EXPECT:
        for k, v in EXPECT[pal].items():
            assert got[k] == v, f"{key} {k} {got[k]} != plan pin {v}"
    return dict(key=key, staged=staged, w2_runtime=w2, crop=crop, crop_ww=c1 - c0, crop_hh=UV[3] - UV[1],
                clut=clut, words_path=words_p, clut_path=clut_p, shas=got)


def native_rgb(crop, ww, hh, clut):
    cw = np.frombuffer(clut, "<u2").astype(np.int64)
    w16 = np.frombuffer(crop, "<u2").reshape(hh, ww)
    idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], -1).reshape(hh, ww * 4)
    rgb = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
    return np.ascontiguousarray(rgb[idx])


def main():
    dry = "--dry-run" in sys.argv
    pal = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--pal=")), "00A1D33C").upper()
    assert len(pal) == 8 and all(c in "0123456789ABCDEF" for c in pal), pal
    budget = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--budget-s=")), "50"))
    t0 = time.time()
    verify_pins()
    staging = json.loads(PIN["staging"][0].read_bytes())
    inp = inputs(pal, staging)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = S67 / "repairs" / f"eregion-classrepair-r0-{inp['key']}-{stamp}{'-dry' if dry else ''}"
    out.mkdir(parents=True, exist_ok=False)
    rec = dict(tool=Path(__file__).name, tool_sha256=sha(Path(__file__)), owner="claude-einhander-s67", started_utc=stamp,
               dry_run=dry, key=inp["key"], uv=UV, pins={k: dict(path=str(p), sha256=w) for k, (p, w) in PIN.items()},
               inputs=dict(staged=str(inp["staged"]), w2_runtime=str(inp["w2_runtime"]), words=str(inp["words_path"]),
                           clut=str(inp["clut_path"]), crop_words_bytes=len(inp["crop"]), **inp["shas"]),
               fill_policy="native", status="proposal only; NOT staged; NOT accepted (live look still required)")
    if not dry:
        try:
            import psutil
            me = psutil.Process()
            me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            cpu = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--cpu=")), None)
            if cpu is not None:
                me.cpu_affinity([cpu])
            rec["process"] = dict(pid=me.pid, affinity=me.cpu_affinity(), nice="below_normal")
        except Exception as e:  # recorded, never silently claimed
            rec["process"] = dict(error=repr(e))

        def _no_child(*a, **k):
            raise RuntimeError("child processes are disabled in this tool")
        subprocess.run = subprocess.Popen = subprocess.call = subprocess.check_call = subprocess.check_output = _no_child
        try:
            rec.update(repair(inp, out, t0, budget))
        except Exception as e:  # record and preserve; never silent
            import traceback
            rec["error"] = dict(type=e.__class__.__name__, message=str(e), traceback=traceback.format_exc()[-4000:])
    rec["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec["elapsed_s"] = round(time.time() - t0, 3)
    with open(out / "result.json", "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(dict(out=str(out), dry_run=dry, strict=rec.get("whole_cell_strict_pass"),
                          error=(rec.get("error") or {}).get("message"))))
    return 1 if rec.get("error") else 0


def repair(inp, out, t0, budget):
    from PIL import Image
    lib = ctypes.CDLL(str(PIN["dll"][0]))
    assert sha(PIN["dll"][0]) == PIN["dll"][1], "dll changed after verification"
    lib.cm_repair.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmRepairStats)]
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(A.CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    clut_words = list(np.frombuffer(inp["clut"], "<u2"))
    ncls = A.native_class(inp["crop"], inp["crop_ww"], inp["crop_hh"], clut_words)
    th, tw = ncls.shape
    assert (tw, th) == (UV[2] - UV[0], UV[3] - UV[1]), ncls.shape
    nrgb = native_rgb(inp["crop"], inp["crop_ww"], inp["crop_hh"], inp["clut"])
    with Image.open(inp["staged"]) as im:
        v1 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
    H, W = v1.shape[:2]
    assert W % tw == 0 and H % th == 0 and W // tw == H // th, f"dims {W}x{H} vs {tw}x{th}"
    s = W // tw

    def validate(img):
        rep = A.CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, ctypes.byref(rep))
        return {f: int(getattr(rep, f)) for f, _ in A.CmReport._fields_}

    def flags(img):
        o = {}
        for name, bf in (("s2_px", 0.5), ("conn_only_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, bf, 0, fl.ctypes.data)
            o[name] = int(((fl & BITS) != 0).sum())
        return o
    before, fb = validate(v1), flags(v1)
    assert time.time() - t0 < budget, "time budget reached before repair"
    r1 = v1.copy()
    st = CmRepairStats()
    rc = lib.cm_repair(r1.ctypes.data, W, H, ncls.ctypes.data, nrgb.ctypes.data, tw, th, s, ctypes.byref(st))
    cut = r1[..., 3] == 0
    r1[cut, :3] = v1[cut, :3]                       # undo the R5 cutout fill: minimal diff
    newvis = (v1[..., 3] == 0) & (r1[..., 3] != 0)
    if newvis.any():                                # --fill=native
        r1[newvis, :3] = np.kron(nrgb, np.ones((s, s, 1), np.uint8))[newvis]
    after, fa = validate(r1), flags(r1)
    vis_both = (v1[..., 3] != 0) & (r1[..., 3] != 0)
    dst = out / f"{inp['key']}.png"
    Image.fromarray(r1, "RGBA").save(dst, optimize=True)
    return dict(scale=s, repair_rc=rc, repair={f: int(getattr(st, f)) for f, _ in CmRepairStats._fields_},
                v2_before=before, v2_after=after, flags_before=fb, flags_after=fa,
                whole_cell_strict_pass=all(after[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                                                   "r4_island_px", "nonclass_px")),
                became_visible_px=int(newvis.sum()), became_cutout_px=int(((v1[..., 3] != 0) & cut).sum()),
                stp_toggled_px=int((vis_both & (v1[..., 3] != r1[..., 3])).sum()),
                visible_rgb_changed=int((vis_both & (r1[..., :3] != v1[..., :3]).any(-1)).sum()),
                alpha_changed_px=int((r1[..., 3] != v1[..., 3]).sum()),
                out=dict(path=str(dst), sha256=sha(dst), bytes=dst.stat().st_size))


if __name__ == "__main__":
    sys.exit(main())
