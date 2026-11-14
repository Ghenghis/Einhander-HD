#!/usr/bin/env python3
"""claude-einhander-ui (EIN-MENU-HUD-20261114), job J-R3: CENSUS-DRIVEN BATCH of the J-R2 (00abc2be) method.
Cases come from census fff7a1c8 (units = CLUT-twin groups), cheapest first (R1+conn), one representative per unit
unless --all-members; --dirs/--max-r1/--max-conn filter, --budget-seconds stops between files (remaining listed),
--resume-from skips files already repaired; per-file sha256 pins come from J-L1/J-L2/J-L3 (themselves pinned by the
census). Review sheets are built inline for the first --review-max groups (no per-group arrays retained).
Original J-R2 description follows (its fixed CASES list is replaced by the census selection): REPRESENTATIVE class-faithful repair proposals for failing
menu/HUD gate files, chosen from the pinned s45 primary audit J-L2 (result 9278a2ea; tool v2 ddf2443c, same primary()).

Cases (default; each with its CLUT twin to exercise shape/palette dedup):
  near-pass   w4-menus/menu-class-exact-v1  runtime-2048/BDAE4156-4C1DD349 (+ -DDD3D3CF)  R1 0,     conn 150
  substantial w2-hud/selection-labels-1AD90FC9-v4 runtime-2048/1AD90FC9-02491337 (+ -79902A90) R1 11559, conn 286304
Native authority: the w6 classcheck Finder (imported READ-ONLY from comfy-authoring/w6-hud-fades/tools, hashed), i.e. the
key's own words (crc32 == RAW) and CLUT (crc32 == CLUT) from the folder's source/, manifest paths or standard native dirs.
Class (alpha authority) = 0 raw 0x0000 / 255 STP set / 127 opaque, exactly as the audit; native RGB = 5-bit << 3 of the
CLUT entry (or the 16bpp word). Repair = frozen proto-v2b cm_repair (c84efa60): R1/R2/R4 violators take their cell's
native class; pixels that STAY visible keep their authored RGB (visible_rgb_changed must be 0); STP/opaque comes only from
the native class, never invented. Variants:
  snap-cell     cm_repair as is (newly visible RGB = cell mean of correct-class pixels);
  snap-nearest  newly visible RGB from the nearest originally visible pixel (as s45 J-I/J-K2);
  snap-native   newly visible RGB = its own cell's bound native texel colour (exact palette entry, no blending; root:
                retain the native visible panel, msg_730e7f09). Limit: a pixel visible before and after whose class
                flips STP<->opaque keeps its authored RGB (common-visible rule), which need not be a palette entry;
  *-noR5        same pixels, but every cutout pixel's RGB restored to the authored value, so the R5 cutout-RGB fill that
                cm_repair performs (root: R5 belongs to the pack composer, msg_80aa44e1) is separated and labelled.
Dedup (shape/palette): files are grouped by (words sha256, native class-map sha256). A group's class decisions depend
only on its authored alpha plane and the class map; the tool records whether every member's authored alpha plane and
repaired alpha plane are identical (shape built/validated once, palettes differ in RGB only) and reports the group, so
pack integration can build one shape per group. Each member is still repaired and validated (cheap) as proof.
Measured: before/after R1..R5, s2, conn-only, primary; class changes (became visible / cutout, STP<->opaque flips);
visible RGB changed on common-visible pixels; newly visible RGB vs native texel colour; R5 fill count.
Review: per group one crop (64x16 texels around the most-changed area), native | authored | snap-nearest | snap-native, 9 px/texel
ATLAS SIMULATION (not a screen capture; no look acceptance). Frozen inputs are read-only (sha256 checked against J-L2).
Writes ONLY <--out-root>/<UTC>/ inside the registered claude-einhander-ui output. Proposal only; nothing installed.
One process; the CPU is chosen by the launcher (affinity inherited)."""
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
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = 64_000_000
RA = Path("C:/github/Einhander/remaster-audit")
CA = RA / "comfy-authoring"
W6T = CA / "w6-hud-fades/tools"
UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
CENSUS = UI_OUT / "census/failure-census-20261114T170036Z.json"
CENSUS_SHA256 = "fff7a1c811c92ed5a6999220ddad641f06712605248736a79d14adf27e80c5b0"
AUDITS = {  # census inputs; every audited file's sha256 pin comes from one of these
    "J-L1": RA / "parallel-stages-20261114/s45/menu-hud/primary-audit/20261114T155808Z/result.json",
    "J-L2": RA / "parallel-stages-20261114/s45/menu-hud/primary-audit/20261114T160358Z/result.json",
    "J-L3": UI_OUT / "primary-audit/20261114T165725Z/result.json",
}
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLASS_MIP_C_SHA256 = "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"
CLASS_MIP_H_SHA256 = "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"
sys.dont_write_bytecode = True   # never write __pycache__ next to the read-only finder modules
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


def hb(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(UI_OUT / "classsnap-batch"))
    ap.add_argument("--max-r1", type=int, default=0, help="only census units with R1 <= this (0 = near-pass units)")
    ap.add_argument("--max-conn", type=int, default=1_000_000_000)
    ap.add_argument("--dirs", nargs="*", default=["runtime-2048", "runtime-1024"], help="export dirs to include")
    ap.add_argument("--all-members", action="store_true", help="repair every CLUT twin, not one representative per unit")
    ap.add_argument("--budget-seconds", type=float, default=70.0, help="stop cleanly between files; remaining units listed")
    ap.add_argument("--review-max", type=int, default=12, help="review sheets for the first N groups only")
    ap.add_argument("--resume-from", nargs="*", default=[], help="earlier J-R3 result.json: skip files already repaired")
    a = ap.parse_args()
    out_root = Path(a.out_root).resolve()
    if os.path.commonpath([str(out_root).lower(), str(UI_OUT.resolve()).lower()]) != str(UI_OUT.resolve()).lower():
        raise SystemExit(f"--out-root {out_root} is outside the registered output {UI_OUT}")
    t0 = time.time()
    assert sha(CENSUS) == CENSUS_SHA256, "census changed"
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    pins = {}
    for job, path in AUDITS.items():
        assert sha(path) == census["inputs"][job], (job, "audit result differs from the census pin")
        for fk, fr in json.loads(path.read_text(encoding="utf-8"))["folders"].items():
            for rel, v in fr["files"].items():
                pins[(fk, rel)] = v
    done = set()
    for rf in a.resume_from:
        for r in json.loads(Path(rf).read_text(encoding="utf-8"))["rows"]:
            done.add((f"{r['lane']}/{r['folder']}", r["file"], r["input_sha256"]))
    units = sorted((u for u in census["units"] if u["r1"] <= a.max_r1 and u["conn"] <= a.max_conn and u["dir"] in a.dirs),
                   key=lambda u: (u["r1"] + u["conn"], u["folder"], u["dir"], u["raw"]))
    CASES = []
    for ui, u in enumerate(units):
        lane, folder = u["folder"].split("/", 1)
        for rel in (u["members"] if a.all_members else u["members"][:1]):
            CASES.append((f"unit{ui:03d} r1={u['r1']} conn={u['conn']} twins={len(u['members'])}", lane, folder, rel))
    assert sha(PROTO / "class_mip.c") == CLASS_MIP_C_SHA256, "frozen class_mip.c changed"
    assert sha(PROTO / "class_mip.h") == CLASS_MIP_H_SHA256, "frozen class_mip.h changed"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = out_root / stamp
    (rd / "review").mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    assert sha(rd / "class_mip.c") == CLASS_MIP_C_SHA256 and sha(rd / "class_mip.h") == CLASS_MIP_H_SHA256
    compiled = dict(class_mip_c=CLASS_MIP_C_SHA256, class_mip_h=CLASS_MIP_H_SHA256, dll=sha(rd / "class_mip.dll"))
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.restype = ctypes.c_int
    lib.cm_flags_ex.restype = ctypes.c_int
    lib.cm_fill_cutout_rgb.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.cm_fill_cutout_rgb.restype = ctypes.c_int64
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    lib.cm_repair.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.POINTER(CmRepairStats)]
    lib.cm_repair.restype = ctypes.c_int
    sys.path[:0] = [str(W6T), str(CA)]
    spec = importlib.util.spec_from_file_location("w6_classcheck", W6T / "classcheck.py")
    CC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CC)
    tool_hashes = {str(p): sha(p) for p in (W6T / "classcheck.py", W6T / "w6lib.py") if p.is_file()}

    def check(img, ncls, s):
        img = np.ascontiguousarray(img)
        H, W = img.shape[:2]
        rep = CmReport()
        assert lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, ncls.shape[1], ncls.shape[0], s, ctypes.byref(rep)) == 0
        o = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            assert lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, ncls.shape[1], ncls.shape[0], s, bound, 0,
                                   fl.ctypes.data) == 0
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
        o["s2_strict_pass"] = all(o[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        return o

    def review_sheet(gid, g, before, near, ncls, nrgb, s, stem, natv):
        changed = (before[..., 3] != near[..., 3]).reshape(ncls.shape[0], s, ncls.shape[1], s).any(axis=(1, 3))
        TH, TW = ncls.shape
        ch, cw = min(16, TH), min(64, TW)
        cs = ndi.uniform_filter(changed.astype(np.float32), size=(ch, cw), mode="constant")
        cy0, cx0 = np.unravel_index(int(np.argmax(cs)), cs.shape)
        y0 = int(min(max(cy0 - ch // 2, 0), TH - ch)); x0 = int(min(max(cx0 - cw // 2, 0), TW - cw))
        g["review_crop_texels"] = [x0, y0, x0 + cw, y0 + ch]

        def sim(arr, sc):
            crop = arr[y0 * sc:(y0 + ch) * sc, x0 * sc:(x0 + cw) * sc].astype(np.float32)
            rgbv = np.where(crop[..., 3:4] > 0, crop[..., :3], 24.0)
            return Image.fromarray(rgbv.astype(np.uint8)).resize((cw * 9, ch * 9), Image.BOX if sc > 1 else Image.NEAREST)
        nat = np.dstack([nrgb, ncls])
        tiles = [("native nearest", nat, 1), ("authored", before, s), ("snap-nearest", near, s), ("snap-native", natv, s)]
        sheet = Image.new("RGB", (cw * 9, len(tiles) * (ch * 9 + 16) + 14), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for i, (lab, arr, sc) in enumerate(tiles):
            sheet.paste(sim(arr, sc), (0, i * (ch * 9 + 16) + 16))
            dr.text((4, i * (ch * 9 + 16) + 2), f"{lab} | {stem} texels {g['review_crop_texels']}", fill=(255, 255, 0))
        dr.text((4, sheet.height - 12), "ATLAS SIMULATION, 9 px/texel (not a screen capture; no look acceptance)", fill=(160, 160, 160))
        fn = rd / "review" / f"{gid}-{stem}.png"
        sheet.save(fn)
        g["review_sheet"] = dict(path=fn.relative_to(rd).as_posix(), sha256=sha(fn))

    rows, groups, finders, remaining, skipped = [], {}, {}, [], 0
    for ci, (role, lane, folder, rel) in enumerate(CASES):
        if time.time() - t0 > a.budget_seconds:
            remaining = [f"{c[1]}/{c[2]}/{c[3]}" for c in CASES[ci:]]
            break
        CC.cy()   # honour the shared CPU-QUIET marker between cases
        fk = f"{lane}/{folder}"
        fd = CA / lane / "frozen" / folder
        pin = pins[(fk, rel)]
        if (fk, rel, pin["sha256"]) in done:
            skipped += 1
            continue
        p = fd / rel
        assert sha(p) == pin["sha256"], (fk, rel, "input differs from its audit pin")
        if fk not in finders:
            man = json.loads((fd / "manifest.json").read_text(encoding="utf-8"))
            finders[fk] = (CC.Finder(str(fd).replace("\\", "/"), man), sha(fd / "manifest.json"))
        F, man_sha = finders[fk]
        raw, cc = CC.KEYRX.match(os.path.basename(rel)[:-4]).groups()
        wd = F.words(raw)
        cl = None if (wd and wd["depth"] == 2) else F.clut(cc)
        assert wd is not None and (wd["depth"] == 2 or cl is not None), (rel, "native authority not resolved")
        ncls = np.ascontiguousarray(CC.native_cls(wd, cl).astype(np.uint8))
        if wd["depth"] == 2:
            v = wd["words"].astype(np.uint16)
        else:
            v = cl["clut"][CC.L.decode_words(wd["words"], wd["depth"])].astype(np.uint16)
        nrgb = np.ascontiguousarray(np.stack([(v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3], -1).astype(np.uint8))
        with Image.open(p) as im:
            before = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
        TH, TW = ncls.shape
        s = before.shape[1] // TW
        assert before.shape[:2] == (TH * s, TW * s), (rel, before.shape, ncls.shape)
        gkey = (wd["sha256"], hb(ncls))
        audit_before = check(before, ncls, s)
        img = before.copy()
        st = CmRepairStats()
        rc = lib.cm_repair(img.ctypes.data, img.shape[1], img.shape[0], ncls.ctypes.data, nrgb.ctypes.data, TW, TH, s,
                           ctypes.byref(st))
        stats = {n: int(getattr(st, n)) for n in SF}
        assert rc >= 0, (rel, "cm_repair error")          # rc 1 (residual violations) is kept as data
        assert stats["visible_rgb_changed"] == 0, (rel, "authored visible RGB modified")
        near = img.copy()
        ov = (before[..., 3] != 0) & (img[..., 3] != 0)
        newv = (before[..., 3] == 0) & (img[..., 3] != 0)
        if newv.any() and ov.any():
            _, (iy, ix) = ndi.distance_transform_edt(~ov, return_indices=True)
            near[newv, :3] = near[iy[newv], ix[newv], :3]
        # re-run the deterministic R5 fill so snap-nearest's cutout fringe follows ITS new visible colours
        assert lib.cm_fill_cutout_rgb(near.ctypes.data, near.shape[1], near.shape[0]) >= 0
        # J-R2 snap-native: newly visible pixels take their OWN cell's bound native texel colour (an exact CLUT/palette
        # entry, nearest per cell, no blending, so no colour bleed from neighbouring glyph texels); RGB only, the
        # class map from cm_repair is untouched. Pixels that stayed visible keep authored RGB; then the R5 refill.
        natpix = np.repeat(np.repeat(nrgb, s, 0), s, 1)
        natv = img.copy()
        natv[newv, :3] = natpix[newv]
        assert lib.cm_fill_cutout_rgb(natv.ctypes.data, natv.shape[1], natv.shape[0]) >= 0
        assert (natv[..., 3] == img[..., 3]).all(), (rel, "snap-native alpha must equal cm_repair class alpha")
        assert (natv[newv, :3] == natpix[newv]).all(), (rel, "snap-native newly visible RGB must be the bound native colour")
        stem = os.path.basename(rel)[:-4]
        row = dict(role=role, lane=lane, folder=folder, file=rel, input_sha256=pin["sha256"], manifest_sha256=man_sha,
                   audit_pin=dict(primary_pass=pin["primary_pass"], r1=pin["r1_centre_bad"], conn=pin["conn_viol_px"]),
                   native=dict(words=wd["path"], words_sha256=wd["sha256"], depth=int(wd["depth"]),
                               clut=(cl or {}).get("path"), clut_sha256=(cl or {}).get("sha256"),
                               class_map_sha256=gkey[1], texels=[int(TW), int(TH)]),
                   scale=int(s), before=audit_before, repair_rc=rc, repair_stats=stats,
                   alpha_before_sha256=hb(before[..., 3]), alpha_after_sha256=hb(img[..., 3]), variants={})
        for name, out in (("snap-cell", img), ("snap-nearest", near), ("snap-native", natv)):
            nor5 = out.copy()
            cut = out[..., 3] == 0
            nor5[cut, :3] = before[cut, :3]
            for vname, arr in ((name, out), (name + "-noR5", nor5)):
                fn = rd / vname / f"{lane}__{folder}__{stem}.png"
                fn.parent.mkdir(exist_ok=True)
                Image.fromarray(arr).save(fn, compress_level=6)
                d_nat = np.abs(arr[..., :3][newv].astype(np.int32) - natpix[newv].astype(np.int32)).mean(-1) if newv.any() else np.zeros(0)
                vis_changed = int(((before[..., :3] != arr[..., :3]).any(-1) & ov).sum())
                assert vis_changed == 0, (rel, vname, "common-visible RGB changed")
                row["variants"][vname] = dict(
                    path=fn.relative_to(rd).as_posix(), sha256=sha(fn), after=check(arr, ncls, s),
                    r5_fill_applied=not vname.endswith("-noR5"),
                    cutout_rgb_changed_vs_authored=int(((arr[..., :3] != before[..., :3]).any(-1) & cut).sum()),
                    became_visible=int(newv.sum()), became_cutout=int(((before[..., 3] != 0) & (arr[..., 3] == 0)).sum()),
                    stp_opaque_flips=int((((before[..., 3] == 127) & (arr[..., 3] == 255)) |
                                          ((before[..., 3] == 255) & (arr[..., 3] == 127))).sum()),
                    visible_rgb_changed_on_common_visible=vis_changed,
                    newly_visible_vs_native_mean=round(float(d_nat.mean()), 2) if d_nat.size else None,
                    newly_visible_vs_native_p95=round(float(np.percentile(d_nat, 95)), 2) if d_nat.size else None)
        rows.append(row)
        gkey_id = f"{gkey[0][:16]}-{gkey[1][:16]}"
        g = groups.setdefault(gkey_id, dict(words_sha256=gkey[0], class_map_sha256=gkey[1], members=[]))
        g["members"].append(f"{fk}/{rel}")
        if len(g["members"]) == 1 and sum("review_sheet" in x for x in groups.values()) < a.review_max:
            review_sheet(gkey_id, g, before, near, ncls, nrgb, s, stem, natv)   # inline: no arrays retained per group
        print(role, fk, rel, "before", (audit_before["primary_pass"], audit_before["r1_centre_bad"], audit_before["conn_viol_px"]),
              "after", {k: v["after"]["primary_pass"] for k, v in row["variants"].items()}, "rc", rc, flush=True)

    for gid, g in groups.items():
        mem = [r for r in rows if f"{r['lane']}/{r['folder']}/{r['file']}" in g["members"]]
        g["authored_alpha_identical"] = len({r["alpha_before_sha256"] for r in mem}) == 1
        g["repaired_alpha_identical"] = len({r["alpha_after_sha256"] for r in mem}) == 1
        g["dedup"] = ("one shape (alpha/class plane) per group; palettes differ in RGB only"
                      if g["authored_alpha_identical"] and g["repaired_alpha_identical"]
                      else "NOT dedupable: members differ in authored or repaired alpha; build each")

    out = dict(run=stamp, owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114", job="J-R3 near-pass batch (J-R2 00abc2be method, census-driven)",
               status="PROPOSAL ONLY: representative class-faithful repairs; frozen inputs read-only; nothing installed; "
                      "review sheets are atlas simulations; R5 fill separated in -noR5 variants (composer owns R5); "
                      "snap-native newly visible pixels use bound native palette RGB; class-valid != look-accepted",
               tool_sha256=sha(Path(__file__)), compiled=compiled, census_sha256=CENSUS_SHA256, audit_pins={k: census["inputs"][k] for k in AUDITS},
               args=vars(a), status_run="partial" if remaining else "complete", remaining=remaining, skipped_resumed=skipped,
               finder_tools_read_only=tool_hashes, groups=groups, rows=rows, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("groups", {k: (len(v["members"]), v["dedup"]) for k, v in groups.items()}, flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
