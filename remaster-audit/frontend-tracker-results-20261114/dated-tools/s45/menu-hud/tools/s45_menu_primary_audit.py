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
Read-only on every audited file. Batches: --lanes / --folders, and --budget-seconds stops cleanly between files and lists
what remains (status partial). Writes ONLY s45/menu-hud/primary-audit/<UTC>/result.json (+ class_mip copy).
One process; the CPU is chosen by the launcher (affinity inherited)."""
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
S45 = RA / "parallel-stages-20261114/s45"
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
    a = ap.parse_args()
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/primary-audit" / stamp
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
        for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(img.ctypes.data, W, H, ncls.ctypes.data, nat.shape[1], nat.shape[0], s, bound, 0, fl.ctypes.data)
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
        o["s2_strict_pass"] = all(o[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
        return o

    folders = []
    for lane in a.lanes:
        for mp in sorted((CA / lane / "frozen").glob("*/manifest.json")):
            if a.folders is None or mp.parent.name in a.folders:
                folders.append((lane, mp.parent))
    results, remaining, partial = {}, [], False
    for i, (lane, fd) in enumerate(folders):
        if time.time() - t0 > a.budget_seconds:
            partial = True
            remaining = [f"{ln}/{f.name}" for ln, f in folders[i:]]
            break
        folder = str(fd).replace("\\", "/")
        man = json.loads((fd / "manifest.json").read_text(encoding="utf-8"))
        F = CC.Finder(folder, man)
        regs = CC.regions_of(man, folder)
        fr = dict(lane=lane, folder=fd.name, manifest_sha256=sha(fd / "manifest.json"), files={}, skipped=0, unresolved=[])
        for p in sorted(glob.glob(f"{folder}/**/*.png", recursive=True)):
            if time.time() - t0 > a.budget_seconds:
                partial = True
                fr["stopped_at"] = os.path.relpath(p, folder).replace("\\", "/")
                break
            rel = os.path.relpath(p, folder).replace("\\", "/")
            d, stem = os.path.dirname(rel), os.path.basename(rel)[:-4]
            m = CC.KEYRX.match(stem)
            nat = None
            if CC.KEY_DIRS.match(d) and m:
                raw, cc = m.groups()
                wd = F.words(raw)
                cl = None if (wd and wd["depth"] == 2) else F.clut(cc)
                if wd is None or (wd["depth"] != 2 and cl is None):
                    fr["unresolved"].append(dict(file=rel, words=bool(wd), clut=bool(cl)))
                    continue
                nat = CC.native_cls(wd, cl)
            elif CC.REGION_DIRS.match(d) and stem in regs:
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
                fr["skipped"] += 1
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
        fs = fr["files"].values()
        fr["summary"] = dict(files=len(fr["files"]), primary_pass=sum(v["primary_pass"] for v in fs),
                             s2_strict_pass=sum(v["s2_strict_pass"] for v in fs),
                             w6_centre_exact=sum(v["w6_centre_mismatches"] == 0 for v in fs),
                             centre_exact_but_primary_fail=sum(v["w6_centre_mismatches"] == 0 and not v["primary_pass"] for v in fs),
                             unresolved=len(fr["unresolved"]), skipped=fr["skipped"])
        results[f"{lane}/{fd.name}"] = fr
        print(f"{lane}/{fd.name}", fr["summary"], round(time.time() - t0, 1), "s", flush=True)
        if partial:
            remaining = [f"{lane}/{fd.name} (from {fr.get('stopped_at')})"] + [f"{ln}/{f.name}" for ln, f in folders[i + 1:]]
            break
    tot = dict(folders=len(results), files=sum(r["summary"]["files"] for r in results.values()),
               primary_pass=sum(r["summary"]["primary_pass"] for r in results.values()),
               w6_centre_exact=sum(r["summary"]["w6_centre_exact"] for r in results.values()),
               centre_exact_but_primary_fail=sum(r["summary"]["centre_exact_but_primary_fail"] for r in results.values()),
               unresolved=sum(r["summary"]["unresolved"] for r in results.values()))
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", job="J-L",
               status="partial" if partial else "complete", remaining=remaining, args=vars(a),
               policy="primary = R1 == 0 and conn-only(bound 1e9) == 0; s2 (bound 0.5) diagnostic; w6 centre check for comparison",
               tool_sha256=sha(Path(__file__)), w6_tools_read_only=tool_hashes, class_mip_c_sha256=sha(PROTO / "class_mip.c"),
               totals=tot, folders=results, seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("totals", tot, "status", out["status"], "remaining", len(remaining), flush=True)
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
