#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114), job J-L: proto-v2b PRIMARY-policy audit of frozen menu/HUD deliveries.

The state register counts a key as delivered when a frozen candidate folder carries it; w6's own "class-exact" checks are
texel-centre only, and the s45 w6-primary-probe showed centre-forced files fail the root primary policy. This audit applies
the root policy to every key-export and exact-region PNG of the given frozen folders:
  * native class map per file resolved with the w6 classcheck source finder (words crc32 == RAW, CLUT crc32 == CLUT, the
    folder's source/, manifest-cited paths, the standard native-source folders; exact regions via the manifest uv);
    classcheck.py / w6lib.py are imported READ-ONLY from comfy-authoring/w6-hud-fades/tools and hashed;
  * frozen proto-v2b class_mip (compiled into the run folder): R1..R5, s/2 (bound 0.5, diagnostic) and connectivity-only
    (bound 1e9); primary = R1 == 0 and conn-only == 0; plus the w6 texel-centre check for comparison.
Read-only on every audited file. Batches: --lanes / --folders / --dirs, --resume-from a previous result.json (files with the
same folder, path and sha256 are skipped and counted), --no-s2 (primary only), and --budget-seconds stops cleanly between
files and lists every unprocessed file (status partial). v3: one global queue over all selected folders, ordered by export
dir priority (runtime-2048, region-8x, runtime-1024, region-4x, region, pack, region-16x); optional --shard k/n. (v3 wrote s45/menu-hud/primary-audit/<UTC>/; v4 output: see below.)
One process; the CPU is chosen by the launcher (affinity inherited).
ui v4 (claude-einhander-ui, EIN-MENU-HUD-20261114): copy of s45 v3 (sha256 8d20c548...) with ONLY the write location and the
owner/job labels changed. It writes ONLY <--out-root>/<UTC>/ (pid.txt, tool/class_mip copies, class_mip.dll, plan.json or
result.json); --out-root must lie inside the registered claude-einhander-ui output. Audit logic, inputs and policy unchanged."""
import argparse
import ctypes
import datetime
import glob
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
from PIL import Image

Image.MAX_IMAGE_PIXELS = 64_000_000
RA = Path("C:/github/Einhander/remaster-audit")
CA = RA / "comfy-authoring"
UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")
V3_SHA256 = "8d20c54860d20bf31a15b776b8fe07fe43f0ba04655377aa72f48bc1b0b28678"
W6T = CA / "w6-hud-fades/tools"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
DEFAULT_LANES = ("w4-signs-hud", "w3-hud", "w6-hud-fades", "w4-menus", "w5-cleanup", "w2-hud", "w6-livepack-classfix", "t9-title-menus")
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", nargs="*", default=list(DEFAULT_LANES))
    ap.add_argument("--folders", nargs="*", default=None, help="frozen folder names to include (default all in the lanes)")
    ap.add_argument("--budget-seconds", type=float, default=25.0)
    ap.add_argument("--dirs", nargs="*", default=None,
                    help="only these export sub-dirs (e.g. runtime-2048 region-8x); default all key/region dirs")
    ap.add_argument("--resume-from", nargs="*", default=None,
                    help="previous primary-audit result.json file(s): skip files they audited (same folder + path + sha256)")
    ap.add_argument("--dir-priority", nargs="*", default=["runtime-2048", "region-8x", "runtime-1024", "region-4x", "region",
                                                          "pack", "region-16x"],
                    help="global processing order of export dirs across all folders (unlisted dirs last)")
    ap.add_argument("--shard", default=None, help="k/n: process only queue items with index modulo n == k")
    ap.add_argument("--plan-only", action="store_true", help="build the queue (no image decode, no DLL), write plan.json, exit")
    ap.add_argument("--no-s2", action="store_true", help="skip the s/2 diagnostic pass (primary needs only R1 + conn-only)")
    ap.add_argument("--out-root", default=str(UI_OUT / "primary-audit"),
                    help="run folders are created here; must be inside the registered claude-einhander-ui output")
    a = ap.parse_args()
    out_root = Path(a.out_root).resolve()
    if os.path.commonpath([str(out_root).lower(), str(UI_OUT.resolve()).lower()]) != str(UI_OUT.resolve()).lower():
        raise SystemExit(f"--out-root {out_root} is outside the registered output {UI_OUT}")
    t0 = time.time()
    if a.plan_only:   # light mode: one CPU other than 13/15, below normal
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = out_root / stamp
    rd.mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    for p in ((Path(__file__),) if a.plan_only else (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h")):
        shutil.copy2(p, rd / p.name)
    lib = None
    if not a.plan_only:
        c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                           capture_output=True, text=True, timeout=60, creationflags=0x4000)
        assert c.returncode == 0, c.stderr
        lib = ctypes.CDLL(str(rd / "class_mip.dll"))
        lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.POINTER(CmReport)]
        lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    sys.path[:0] = [str(W6T), str(CA)]
    spec = importlib.util.spec_from_file_location("w6_classcheck", W6T / "classcheck.py")
    CC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CC)
    tool_hashes = {str(p): sha(p) for p in (W6T / "classcheck.py", W6T / "w6lib.py", W6T / "w2lib.py", CA / "gpu_queue.py") if p.is_file()}

    def primary(im, nat, s):
        img = np.ascontiguousarray(im)
        ncls = np.ascontiguousarray(nat.astype(np.uint8))
        H, W = img.shape[:2]
        rep = CmReport()
        lib.cm_validate(img.ctypes.data, W, H, ncls.ctypes.data, nat.shape[1], nat.shape[0], s, ctypes.byref(rep))
        o = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in ((("s2_viol_px", 0.5),) if not a.no_s2 else ()) + (("conn_viol_px", 1.0e9),):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, nat.shape[1], nat.shape[0], s, bound, 0, fl.ctypes.data)
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
        o["s2_strict_pass"] = None if a.no_s2 else all(o[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        return o

    done = {}
    for rf in (a.resume_from or []):
        prev = json.loads(Path(rf).read_text(encoding="utf-8"))
        for fk, fr0 in prev.get("folders", {}).items():
            for rel, v in fr0.get("files", {}).items():
                done[(fk, rel)] = v.get("sha256")
    folders = []
    for lane in a.lanes:
        for mp in sorted((CA / lane / "frozen").glob("*/manifest.json")):
            if a.folders is None or mp.parent.name in a.folders:
                folders.append((lane, mp.parent))
    # global queue: every PNG of every selected folder, ordered by export-dir priority, then folder order, then path
    prio = {d: i for i, d in enumerate(a.dir_priority)}
    queue = []
    for fi, (lane, fd) in enumerate(folders):
        folder = str(fd).replace("\\", "/")
        for p in sorted(glob.glob(f"{folder}/**/*.png", recursive=True)):
            rel = os.path.relpath(p, folder).replace("\\", "/")
            d = os.path.dirname(rel)
            if a.dirs is not None and d not in a.dirs:
                continue
            if not (CC.KEY_DIRS.match(d) or CC.REGION_DIRS.match(d)):
                continue
            queue.append((prio.get(d, len(prio)), fi, rel, lane, fd, p))
    queue.sort(key=lambda t: t[:3])
    if a.shard:
        k, n = (int(x) for x in a.shard.split("/"))
        queue = [q for i, q in enumerate(queue) if i % n == k]
    if a.plan_only:
        todo = [q for q in queue if not ((f"{q[3]}/{q[4].name}", q[2]) in done and done[(f"{q[3]}/{q[4].name}", q[2])] == sha(q[5]))]
        per = {}
        for q in todo:
            per.setdefault(f"{q[3]}/{q[4].name}", {}).setdefault(os.path.dirname(q[2]), 0)
            per[f"{q[3]}/{q[4].name}"][os.path.dirname(q[2])] += 1
        plan = dict(run=stamp, mode="plan-only", args=vars(a), queue=len(queue), already_audited=len(queue) - len(todo),
                    to_audit=len(todo), mpix_to_audit=None, per_folder_dir=per,
                    files=[f"{q[3]}/{q[4].name}/{q[2]}" for q in todo])
        (rd / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")
        print("plan queue", len(queue), "already", plan["already_audited"], "to_audit", len(todo), "plan", sha(rd / "plan.json"))
        return
    results, ctx, remaining, partial = {}, {}, [], False
    for qi, (_, fi, rel, lane, fd, p) in enumerate(queue):
        fk = f"{lane}/{fd.name}"
        if time.time() - t0 > a.budget_seconds:
            partial = True
            remaining = [f"{q[3]}/{q[4].name}/{q[2]}" for q in queue[qi:]]
            break
        if fk not in ctx:
            folder = str(fd).replace("\\", "/")
            man = json.loads((fd / "manifest.json").read_text(encoding="utf-8"))
            ctx[fk] = (CC.Finder(folder, man), CC.regions_of(man, folder))
            results[fk] = dict(lane=lane, folder=fd.name, manifest_sha256=sha(fd / "manifest.json"), files={}, already_audited=0, unresolved=[])
        F, regs = ctx[fk]
        fr = results[fk]
        if (fk, rel) in done and done[(fk, rel)] == sha(p):
            fr["already_audited"] += 1
            continue
        d, stem = os.path.dirname(rel), os.path.basename(rel)[:-4]
        m = CC.KEYRX.match(stem)
        if CC.KEY_DIRS.match(d) and m:
            raw, cc = m.groups()
            wd = F.words(raw)
            cl = None if (wd and wd["depth"] == 2) else F.clut(cc)
            if wd is None or (wd["depth"] != 2 and cl is None):
                fr["unresolved"].append(dict(file=rel, words=bool(wd), clut=bool(cl)))
                continue
            nat = CC.native_cls(wd, cl)
        elif stem in regs:
            rg = regs[stem]
            x0, y0, x1, y1 = rg["uv"]
            wd = cl = None
            for q in (q for q in rg["paths"] if q.endswith(".words.bin")):
                if os.path.exists(q):
                    b = open(q, "rb").read()
                    mt = CC.meta_for(q)
                    if mt and CC.crc(b) == os.path.basename(q)[:8]:
                        wd = dict(words=np.frombuffer(b, "<u2").reshape(mt["height"], mt["width_words"]), depth=mt["depth"])
                        break
            for q in (q for q in rg["paths"] if q.endswith(".clut.bin")):
                if os.path.exists(q) and CC.crc(open(q, "rb").read()) == os.path.basename(q)[9:17] == stem[9:]:
                    cl = dict(clut=np.fromfile(q, "<u2"))
                    break
            if wd is None or (wd["depth"] != 2 and cl is None):
                fr["unresolved"].append(dict(file=rel, region=stem, words=bool(wd), clut=bool(cl)))
                continue
            nat = CC.native_cls(wd, cl)[y0:y1, x0:x1]
        else:
            fr["unresolved"].append(dict(file=rel, reason="not a key export and not a manifest exact region"))
            continue
        with Image.open(p) as imf:
            im = np.asarray(imf.convert("RGBA"))
        H, W = nat.shape
        if im.shape[1] % W or im.shape[0] % H or im.shape[1] // W != im.shape[0] // H:
            fr["unresolved"].append(dict(file=rel, reason=f"size {im.shape[1]}x{im.shape[0]} not an integer multiple of {W}x{H}"))
            continue
        s = im.shape[1] // W
        cen = CC.check(im, nat)
        o = primary(im, nat, s)
        o.update(scale=s, dims=[int(im.shape[1]), int(im.shape[0])], sha256=sha(p), w6_centre_mismatches=cen["mismatches"],
                 alpha_values_ok=cen["alpha_values_ok"])
        fr["files"][rel] = o
    for fk, fr in results.items():
        fs = fr["files"].values()
        fr["summary"] = dict(files=len(fr["files"]), primary_pass=sum(v["primary_pass"] for v in fs),
                             s2_strict_pass=None if a.no_s2 else sum(bool(v["s2_strict_pass"]) for v in fs),
                             already_audited=fr["already_audited"],
                             w6_centre_exact=sum(v["w6_centre_mismatches"] == 0 for v in fs),
                             centre_exact_but_primary_fail=sum(v["w6_centre_mismatches"] == 0 and not v["primary_pass"] for v in fs),
                             unresolved=len(fr["unresolved"]))
        print(fk, fr["summary"], flush=True)
    by_dir = {}
    for fr in results.values():
        for rel, v in fr["files"].items():
            dd = by_dir.setdefault(os.path.dirname(rel), dict(files=0, primary_pass=0))
            dd["files"] += 1
            dd["primary_pass"] += int(v["primary_pass"])
    tot = dict(queue=len(queue), folders=len(results), files=sum(r["summary"]["files"] for r in results.values()),
               already_audited=sum(r["summary"]["already_audited"] for r in results.values()),
               primary_pass=sum(r["summary"]["primary_pass"] for r in results.values()),
               w6_centre_exact=sum(r["summary"]["w6_centre_exact"] for r in results.values()),
               centre_exact_but_primary_fail=sum(r["summary"]["centre_exact_but_primary_fail"] for r in results.values()),
               unresolved=sum(r["summary"]["unresolved"] for r in results.values()), by_dir=by_dir, remaining_files=len(remaining))
    out = dict(run=stamp, owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114",
               job="J-L3 ui v4 (= s45 v3 8d20c548 logic; own output root)", derived_from_tool_sha256=V3_SHA256,
               status="partial" if partial else "complete", remaining=remaining, args=vars(a),
               policy="primary = R1 == 0 and conn-only(bound 1e9) == 0; s2 (bound 0.5) diagnostic; w6 centre check for comparison",
               tool_sha256=sha(Path(__file__)), w6_tools_read_only=tool_hashes, class_mip_c_sha256=sha(PROTO / "class_mip.c"),
               totals=tot, folders=results, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("totals", tot, "status", out["status"], "remaining", len(remaining), flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
