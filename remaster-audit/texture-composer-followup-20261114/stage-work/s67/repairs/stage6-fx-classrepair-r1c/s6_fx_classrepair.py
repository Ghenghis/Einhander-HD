#!/usr/bin/env python3
"""s67 isolated REPAIR PROPOSAL r1: whole-cell class ownership for the Stage 6 FX keys that fail the strict audit.

Input: the s67 strict audit result (runs/<UTC>/result.json): every SELECTED file with whole_cell_strict_pass == False
(10932164 x5, E653AA46 x3, D552405C v4 x4 = 24 files at run 20261114T135603Z). All of them pass the lane's texel-centre gate
(R1 = 0) but break R2 (alpha deviates farther than s/2 from any native cell of that class) and R4 (islands).
Method (CPU, deterministic, frozen proto-v2b, no AI, no new palette):
  * start from a COPY of the frozen file (sha256 must equal the manifest);
  * cm_repair: R1/R2/R4 violators take the native class of their cell; a pixel that becomes visible takes the mean colour of
    the cell's correct-class pixels, else the native texel colour from the CRC-proven CLUT (nrgb);
  * then every pixel that is cutout AFTER the repair gets its v1 RGB back (cm_repair's R5 cutout fill is undone, so the
    only byte changes are the class flips and the RGB of newly visible pixels; visible_rgb_changed must be 0);
  * cm_validate on the result: whole-cell strict must pass; R5 fringe is reported as a diagnostic;
  * cm_flags_ex bits 2|4|16 before and after at two EXPLICIT bounds: 0.5 (s/2 diagnostic) and 1e9 (root connectivity-only);
  * alpha changes are reported explicitly: became_visible_px, became_cutout_px, stp_toggled_px (the class plane DOES change).
Frozen v1/v4 folders and the Stage 1 w2-effects files are never modified. Review sheets: native class / v1 / r1 at the worst
cells (class shown as grey levels 0/127/255 over RGB). Not an acceptance: look judgement and live A/B are still required
(the lane rejected a blocky native-class silhouette for the Stage 7 explosion; R2 allows soft contours within s/2).
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/repairs/stage6-fx-classrepair-r1/.
usage: python -B -I s6_fx_classrepair.py [--dry-run] [--budget-s=28] [--cpu=N] [--only=KEY[,KEY]] [--out-name=stage6-fx-classrepair-rX]
  (granted cap: 30 s). r1c follow-up: --only=D552405C-C12DB7DC --out-name=stage6-fx-classrepair-r1c (the 2 files r1b did not reach)."""
import ctypes
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s67_strict_audit as A  # noqa: E402

S67 = A.S67
OUT = S67 / "repairs" / "stage6-fx-classrepair-r1b"   # r1 (14:17Z) failed on a Windows-invalid review filename; kept as evidence
_out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out-name=")), None)
if _out:   # e.g. stage6-fx-classrepair-r1c for a targeted follow-up; must be a new folder name under s67/repairs
    assert _out.startswith("stage6-fx-classrepair-") and "/" not in _out and "\\" not in _out and ".." not in _out, _out
    OUT = S67 / "repairs" / _out
ONLY = {k for a in sys.argv if a.startswith("--only=") for k in a.split("=", 1)[1].split(",") if k}
AUDIT_RUN = S67 / "runs" / "20261114T135603Z"


class CmRepairStats(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("class_changed", "became_visible", "became_cutout", "rgb_from_cell",
                                               "rgb_from_native", "cutout_rgb_filled", "visible_rgb_changed", "passes",
                                               "residual_violations")]


def failing_jobs():
    res = json.loads((AUDIT_RUN / "result.json").read_text(encoding="utf-8"))
    bad = {(r["folder"], r["key"]) for r in res["rows"] if r["group"] == "selected" and "error" not in r
           and not r["whole_cell_strict_pass"]}
    js, maps = A.jobs(alternates=False)
    sel = [j for j in js if (j["folder"], j["key"]) in bad]
    if ONLY:
        missing = ONLY - {j["key"] for j in sel}
        assert not missing, f"--only keys not among the failing selected keys: {sorted(missing)}"
        sel = [j for j in sel if j["key"] in ONLY]
    return sel, res, maps


def native_rgb(j, ncls_shape):
    """tw*th*3 native colours from the CRC-proven words + CLUT (same proof path as the audit)."""
    wb = Path(j["words"]).read_bytes()
    cb = bytes.fromhex(j["clut_hex"]) if j.get("clut_hex") else Path(j["clut_path"]).read_bytes()
    cw = np.frombuffer(cb, "<u2").astype(np.int64)
    th, tw = ncls_shape
    w16 = np.frombuffer(wb, "<u2")[:j["rect"][2] * j["rect"][3]].reshape(j["rect"][3], j["rect"][2])
    idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], -1).reshape(th, tw)
    rgb = np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)
    return np.ascontiguousarray(rgb[idx])


def sheet(ncls, v1, r1, s, worst, path):
    from PIL import Image
    tiles = []
    for u, v, _ in worst[:4]:
        u0, v0 = max(0, u - 6), max(0, v - 6)
        u1, v1_ = min(ncls.shape[1], u0 + 12), min(ncls.shape[0], v0 + 12)
        nat = np.kron(ncls[v0:v1_, u0:u1], np.ones((s, s), np.uint8))
        a1 = v1[v0 * s:v1_ * s, u0 * s:u1 * s, 3]
        a2 = r1[v0 * s:v1_ * s, u0 * s:u1 * s, 3]
        c1 = v1[v0 * s:v1_ * s, u0 * s:u1 * s, :3]
        c2 = r1[v0 * s:v1_ * s, u0 * s:u1 * s, :3]
        row = [Image.fromarray(x).resize((288, 288), Image.NEAREST) for x in (nat, a1, a2)]
        row += [Image.fromarray(np.where(a[..., None] > 0, x, 0).astype(np.uint8)).resize((288, 288), Image.NEAREST)
                for x, a in ((c1, a1), (c2, a2))]
        t = Image.new("RGB", (5 * 294, 288), (12, 12, 16))
        for i, im in enumerate(row):
            t.paste(im.convert("RGB"), (i * 294, 0))
        tiles.append(t)
    if not tiles:
        return None
    sh = Image.new("RGB", (tiles[0].width, len(tiles) * 294), (12, 12, 16))
    for i, t in enumerate(tiles):
        sh.paste(t, (0, i * 294))
    sh.save(path, optimize=True)
    return path.name


def main():
    dry = "--dry-run" in sys.argv
    budget = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--budget-s=")), "28"))
    t0 = time.time()
    js, audit, maps = failing_jobs()
    plan = [dict(folder=j["folder"], key=j["key"], files={t: str(p) for t, p in j["files"].items()}) for j in js]
    if dry:
        cache = {}
        for j in js:
            ncls, pr = A.prove(j, cache)
            assert ncls is not None, pr
            for p in j["files"].values():
                assert p.exists(), p
        print("dry-run OK:", len(js), "keys,", sum(len(j["files"]) for j in js), "files;", sorted({j["folder"] for j in js}),
              "keys", [j["key"] for j in js], "out", OUT, "exists", OUT.exists())
        return
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cpu=")), me.cpu_affinity()[-1]))])
        prio = dict(pid=me.pid, nice="below_normal", affinity=me.cpu_affinity())
    except Exception as e:
        prio = dict(error=repr(e))
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    assert not OUT.exists(), "output exists (immutable): bump the revision"
    OUT.mkdir(parents=True)
    (OUT / "start.json").write_text(json.dumps(dict(pid=os.getpid(), started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                                    priority=prio, budget_s=budget, argv=sys.argv)) + "\n", encoding="utf-8")
    for p in (Path(__file__), HERE / "s67_strict_audit.py", A.PROTO / "class_mip.c", A.PROTO / "class_mip.h"):
        shutil.copy2(p, OUT / p.name)
    dll = OUT / "class_mip.dll"
    c = subprocess.run([A.CLANG, "-shared", "-O2", "-std=c11", str(OUT / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=300, creationflags=0x4000)
    (OUT / "compile.log").write_text(f"exit {c.returncode}\n{c.stdout}\n{c.stderr}\n", encoding="utf-8")
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(dll))
    lib.cm_repair.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmRepairStats)]
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(A.CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]

    def bounds(img, W, H, ncls, tw, th, s):
        """bits 2|4|16 px at bound_frac 0.5 (s/2 diagnostic) and 1e9 (root connectivity-only policy)."""
        out = {}
        for name, bf in (("s2_px", 0.5), ("conn_only_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, bf, 0, fl.ctypes.data)
            out[name] = int(((fl & (2 | 4 | 16)) != 0).sum())
        return out
    audit_rows = {(r["folder"], r["key"], r["file"]): r for r in audit["rows"]}
    rows, cache, aborted, error = [], {}, None, None
    try:
        run_jobs(js, A, lib, bounds, native_rgb, audit_rows, rows, cache, t0, budget, Image)
    except BudgetStop as b:
        aborted = dict(reason=f"budget {budget}s", at_key=str(b))
    except Exception as e:   # record and preserve partial outputs; never silent
        import traceback
        error = dict(type=e.__class__.__name__, message=str(e), traceback=traceback.format_exc()[-4000:])
    man = dict(name=OUT.name, status="proposal (s67 repair r1b; NOT frozen lane art; NOT accepted)" if not error else "FAILED (partial)",
               owner="claude-einhander-s67",
               task="EIN-S6-WHOLE-CELL-20261114", created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               audit_run=dict(path=str(AUDIT_RUN), result_sha256=A.sha(AUDIT_RUN / "result.json")), selection_maps=maps,
               method=__doc__, priority=prio, elapsed_s=round(time.time() - t0, 2), aborted=aborted, error=error,
               complete=aborted is None and error is None, files=len(rows), strict_pass=sum(r["whole_cell_strict_pass"] for r in rows),
               visible_rgb_changed_total=sum(r["visible_rgb_changed_after_restore"] for r in rows),
               alpha_changed_total=sum(r["alpha_changed_px"] for r in rows),
               became_visible_total=sum(r["became_visible_px"] for r in rows), became_cutout_total=sum(r["became_cutout_px"] for r in rows),
               stp_toggled_total=sum(r["stp_toggled_px"] for r in rows), rows=rows,
               previous_failed_attempt="repairs/stage6-fx-classrepair-r1 (OSError 22 on a review filename with '|'; partial, preserved)",
               stage1_note="10932164-0386F43A/-5F4DE3D3/-66175427/-AF93AEF2 sources are Stage 1 frozen files reused byte for byte; "
                           "these repaired copies are a Stage 6 proposal only and do not modify the Stage 1 deliverable")
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print("out", OUT, "files", man["files"], "strict", man["strict_pass"], "vis_rgb_changed", man["visible_rgb_changed_total"],
          "elapsed", man["elapsed_s"], "error", (error or {}).get("message"), "manifest", A.sha(OUT / "manifest.json"))
    if error:
        sys.exit(1)


class BudgetStop(Exception):
    pass


def run_jobs(js, A, lib, bounds, native_rgb, audit_rows, rows, cache, t0, budget, Image):
    for j in js:
        if time.time() - t0 > budget:
            raise BudgetStop(j["key"])
        ncls, pr = A.prove(j, cache)
        nrgb = native_rgb(j, ncls.shape)
        th, tw = ncls.shape
        for tag, fp in sorted(j["files"].items()):
            assert A.sha(fp) == j["file_sha"][tag], f"frozen hash mismatch {fp}"
            with Image.open(fp) as im:
                v1 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            H, W = v1.shape[:2]
            s = W // tw
            fb = bounds(v1, W, H, ncls, tw, th, s)
            r1 = v1.copy()
            st = CmRepairStats()
            rc = lib.cm_repair(r1.ctypes.data, W, H, ncls.ctypes.data, nrgb.ctypes.data, tw, th, s, ctypes.byref(st))
            cut = r1[..., 3] == 0
            r1[cut, :3] = v1[cut, :3]                      # undo the R5 cutout fill: minimal diff
            rep = A.CmReport()
            lib.cm_validate(r1.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, ctypes.byref(rep))
            v2 = {f_: int(getattr(rep, f_)) for f_, _ in A.CmReport._fields_}
            fa = bounds(r1, W, H, ncls, tw, th, s)
            vis_both = (v1[..., 3] != 0) & (r1[..., 3] != 0)
            vis_rgb_changed = int((vis_both & (r1[..., :3] != v1[..., :3]).any(-1)).sum())
            dst = OUT / j["folder"] / f"runtime-{tag}" / f"{j['key']}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(r1, "RGBA").save(dst, optimize=True)
            before = audit_rows.get((j["folder"], j["key"], tag)) or {}
            row = dict(folder=j["folder"], key=j["key"], file=tag, src=str(fp), src_sha256=j["file_sha"][tag],
                       out=str(dst.relative_to(OUT)).replace("\\", "/"), out_sha256=A.sha(dst), scale=s, repair_rc=rc,
                       repair={f_: int(getattr(st, f_)) for f_, _ in CmRepairStats._fields_},
                       visible_rgb_changed_after_restore=vis_rgb_changed,
                       alpha_changed_px=int((r1[..., 3] != v1[..., 3]).sum()),
                       bytes_changed_px=int((r1 != v1).any(-1).sum()),
                       v2_after=v2, whole_cell_strict_pass=all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px",
                                                                                      "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                       v2_before=before.get("v2"), flags_before=fb, flags_after=fa,
                       became_visible_px=int(((v1[..., 3] == 0) & (r1[..., 3] != 0)).sum()),
                       became_cutout_px=int(((v1[..., 3] != 0) & (r1[..., 3] == 0)).sum()),
                       stp_toggled_px=int(((v1[..., 3] != 0) & (r1[..., 3] != 0) & (v1[..., 3] != r1[..., 3])).sum()))
            if tag == "2048" and j["key"] == next(k["key"] for k in js if k["folder"] == j["folder"] and k["key"][:8] == j["key"][:8]):
                (OUT / "review").mkdir(exist_ok=True)
                row["review"] = sheet(ncls, v1, r1, s, before.get("conn_worst_cells_uv_px") or [],
                                      OUT / "review" / f"{j['key']}-worst-cells_native_v1class_r1class_v1rgb_r1rgb.png")
            rows.append(row)
            print(j["key"], tag, "rc", rc, "strict", row["whole_cell_strict_pass"], "alpha_px", row["alpha_changed_px"],
                  "vis_rgb_changed", vis_rgb_changed, flush=True)
            del v1, r1


if __name__ == "__main__":
    main()
