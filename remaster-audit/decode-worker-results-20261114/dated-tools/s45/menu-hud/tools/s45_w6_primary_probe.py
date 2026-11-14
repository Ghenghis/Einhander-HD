#!/usr/bin/env python3
"""s45 menu/HUD light read-only probe: do the w6 centre-forced HUD files (hud-fades-v1, w3-hud-classfix-v1) pass the
proto-v2b primary policy (R1 + connectivity-only at bound 1e9)? 10 small files. Uses the frozen class_mip.dll compiled in
the J-H run folder. Writes ONLY s45/menu-hud/w6-primary-probe/<UTC>/probe.json. One CPU (not 13/15), below normal."""
import ctypes
import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import psutil
from PIL import Image

me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
JH = S45 / "menu-hud/fade-aliases-v1/20261114T150907Z"
W6 = RA / "comfy-authoring/w6-hud-fades/frozen"
F = RA / "comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1"
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")
STRIPS = {"D050AD1B": 64, "5C02D3C1": 72, "913A6603": 80, "913FE978": 88, "5F101F62": 96, "AAA5C104": 112}


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


lib = ctypes.CDLL(str(JH / "class_mip.dll"))
lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.POINTER(CmReport)]
lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
sys.path.insert(0, str(F / "builder-snapshot"))
import w2lib as L  # noqa: E402  frozen, import-safe
IDX = L.load_words("BDAE4156-B88C038E")["idx"]


def check(path, clut_words):
    y = STRIPS[Path(path).stem[:8]]
    lut = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in clut_words], np.uint8)
    ncls = np.ascontiguousarray(lut[IDX[y:y + 8]])
    with Image.open(path) as im:
        a = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
    H, W = a.shape[:2]
    s = W // 256
    rep = CmReport()
    lib.cm_validate(a.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, ctypes.byref(rep))
    o = {n: int(getattr(rep, n)) for n in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px")}
    for nm, b in (("s2_viol_px", 0.5), ("conn_viol_px", 1e9)):
        fl = np.zeros((H, W), np.uint8)
        lib.cm_flags_ex(a.ctypes.data, W, H, ncls.ctypes.data, 256, 8, s, b, 0, fl.ctypes.data)
        o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
    o["primary_pass"] = o["r1_centre_bad"] == 0 and o["conn_viol_px"] == 0
    return o


def main():
    rows = []
    m = json.loads((W6 / "hud-fades-v1/manifest.json").read_text(encoding="utf-8"))
    for e in m["keys"][:2] + m["keys"][9:10]:
        cw = np.array([int(h, 16) for h in e["clut_used"]["hex"]], np.uint16)
        for size in ("2048", "1024"):
            p = W6 / f"hud-fades-v1/runtime-{size}/{e['key']}.png"
            rows.append(dict(set="w6 hud-fades-v1 (centre-forced)", key=e["key"], size=size, path=str(p), sha256=sha(p), **check(p, cw)))
    fm = json.loads((F / "manifest.json").read_text(encoding="utf-8"))
    ctl = next(e for e in fm["keys"] if e["key"] == "5C02D3C1-0995EC09")
    cw = np.fromfile(ctl["clut"]["path"].replace("\\", "/"), dtype="<u2")
    for size in ("2048", "1024"):
        for nm, p in (("w3 parent hud-label-font-BDAE4156-v1", F / ctl["runtime"][size]["path"]),
                      ("w6 w3-hud-classfix-v1 (centre-forced successor)",
                       W6 / f"w3-hud-classfix-v1/hud-label-font-BDAE4156-v1/runtime-{size}/{ctl['key']}.png")):
            rows.append(dict(set=nm, key=ctl["key"], size=size, path=str(p), sha256=sha(p), **check(p, cw)))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/w6-primary-probe" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", tool_sha256=sha(__file__),
               dll_sha256=sha(JH / "class_mip.dll"),
               policy="primary = R1 == 0 and conn-only(bound 1e9) == 0; s2 (bound 0.5) is a diagnostic",
               note="read-only probe of frozen deliveries; nothing changed",
               rows=rows,
               summary=dict(files=len(rows), primary_pass=sum(r["primary_pass"] for r in rows),
                            r1_zero=sum(r["r1_centre_bad"] == 0 for r in rows)))
    (rd / "probe.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(r["set"][:30], r["key"], r["size"], "R1", r["r1_centre_bad"], "conn", r["conn_viol_px"], "R4", r["r4_island_px"],
              "primary", r["primary_pass"])
    print(out["summary"], "run", stamp, sha(rd / "probe.json"))


if __name__ == "__main__":
    main()
