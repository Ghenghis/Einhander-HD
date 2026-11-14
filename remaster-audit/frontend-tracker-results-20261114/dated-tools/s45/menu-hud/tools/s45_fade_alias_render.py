#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114): render the recovered historical HUD fade-alias strips as a NEW candidate.

Inputs (read-only): the frozen W3 HUD label-font set hud-label-font-BDAE4156-v1 (its builder-snapshot libraries and the
fade-strip method of build_hudfont.py: base = native nearest of the strip through the fade CLUT, then both font regions
rendered from the font masters through the same CLUT) and the CRC-proven CLUT words from
s45/menu-hud/fade-recovery/<run>/ (each file's CRC32 equals its key's PAL).

EQUIVALENCE GATE first: three fade keys that the frozen set already built (5C02D3C1-0995EC09, D050AD1B-*, 913A6603-*)
are re-rendered through their frozen CLUT sidecars and must equal the frozen runtime-2048 / runtime-1024 PNGs byte for
byte. Master source: 'retrace' (psf.render_font, the builder's own deterministic call) and, if that does not reproduce,
'saved' (frozen float16 masters). If neither reproduces, nothing new is rendered (exit 2).
Then every recovered key whose drawn UVs lie inside the font regions (the builder's own rule) is rendered with the same
method and audited with the frozen proto-v2b validator (R1 + connectivity-only bound 1e9 = primary; s/2 bound 0.5
diagnostic; R5). Nothing installed; status candidate; new folder only.
Writes ONLY s45/menu-hud/fade-aliases-v1/<UTC>/."""
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

RA = Path("C:/github/Einhander/remaster-audit")
FROZEN = RA / "comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1"
BUILDER = FROZEN / "builder-snapshot"
S45 = RA / "parallel-stages-20261114/s45"
REC = S45 / "menu-hud/fade-recovery/20261114T150008Z"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
OUT = S45 / "menu-hud/fade-aliases-v1"
# constants copied verbatim from the frozen build_hudfont.py
REGIONS = {'lower': [0, 32, 64, 64], 'upper': [192, 64, 256, 128]}
STRIPS = {'E1F18F98': 32, '786B98BF': 40, '2C781811': 48, '921FC559': 56, 'D050AD1B': 64, '5C02D3C1': 72, '913A6603': 80,
          '913FE978': 88, '5F101F62': 96, 'AAA5C104': 112}
FACE, SOFT, SHADOW, BG = [0, 1, 2, 3, 4], [5], [10], 15
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    t0 = time.time()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    (rd / "gate").mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp} affinity {me.cpu_affinity()}\n", encoding="utf-8")
    print("PID", os.getpid(), "affinity", me.cpu_affinity(), "run", rd, flush=True)
    shutil.copy2(Path(__file__), rd / Path(__file__).name)
    sys.path.insert(0, str(BUILDER))
    import w3lib as W            # noqa: E402  frozen, import-safe (in-memory SOURCE_DIRS only)
    from w3lib import L, S       # noqa: E402
    import psf                   # noqa: E402
    # the snapshot resolves W.SCAN relative to itself (frozen-set/work/, absent); use the frozen copy of the draw-log scan
    W.SCAN = str(BUILDER / "scan_logs.json")
    assert Path(W.SCAN).is_file(), W.SCAN
    frozen_man = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
    page = L.load_words('BDAE4156-B88C038E')
    IDX = page['idx']
    words = page['words']
    for raw, y in STRIPS.items():
        assert crc(words[y:y + 8].tobytes()) == raw, raw

    def masters_from(mode):
        ms = {}
        for name, (x0, y0, x1, y1) in REGIONS.items():
            if mode == "retrace":
                r = psf.render_font(IDX[y0:y1, x0:x1], FACE, SOFT, SHADOW, S)
            else:
                z = np.load(FROZEN / f"masters/label-font-{name}-r{x0}_{y0}_{x1}_{y1}.npz")
                r = dict(Cf=z["face_cov"].astype(np.float64), Cs=z["shadow_cov"].astype(np.float64),
                         stats=dict(face_index=int(z["face_index"]), shadow_index=int(z["shadow_index"])))
            r['rect'] = [x0, y0, x1, y1]
            ms[name] = r
        return ms

    def render_regions(masters, out, clut, row0, nrows):
        rgb, cls = L.clut_rgb(clut)
        for name, r in masters.items():
            x0, y0, x1, y1 = r['rect']
            a, b = max(y0, row0), min(y1, row0 + nrows)
            if a >= b:
                continue
            ys = slice((a - y0) * S, (b - y0) * S)
            shp = r['Cf'][ys].shape
            tile = psf.render_clut(r['Cf'][ys], r['Cs'][ys], np.full(shp, r['stats']['face_index'], np.int64),
                                   np.full(shp, r['stats']['shadow_index'], np.int64), rgb, cls, BG)
            out[(a - row0) * S:(b - row0) * S, x0 * S:x1 * S] = tile

    def strip(masters, key, clut):
        y = STRIPS[key[:8]]
        base = L.nearest_up(L.native_rgba(IDX[y:y + 8], clut), S)
        new = base.copy()
        render_regions(masters, new, clut, y, 8)
        assert new.shape == (128, 4096, 4)
        return new

    # ---------------- equivalence gate
    sib = {}
    for e in frozen_man["keys"]:
        if e.get("kind") == "strip" and str(e.get("base", {}).get("origin", "")).startswith("native nearest") and e["key"][:8] in ("5C02D3C1", "D050AD1B", "913A6603"):
            sib.setdefault(e["key"][:8], e)
    gate = dict(siblings=[e["key"] for e in sib.values()], modes={})
    masters = None
    for mode in ("retrace", "saved"):
        ms = masters_from(mode)
        ok, rows = True, []
        for e in sib.values():
            clut = np.fromfile(e["clut"]["path"].replace("\\", "/"), dtype="<u2")
            assert crc(clut.tobytes()) == e["key"][9:]
            new = strip(ms, e["key"], clut)
            gd = rd / "gate" / mode
            W.save_rt(new, str(gd), e["key"])
            for size in ("2048", "1024"):
                got = sha(gd / f"runtime-{size}/{e['key']}.png")
                want = e["runtime"][size]["sha256"]
                rows.append(dict(key=e["key"], size=size, identical=got == want))
                ok = ok and got == want
        gate["modes"][mode] = dict(pass_=ok, rows=rows)
        print("gate", mode, "PASS" if ok else "FAIL", flush=True)
        if ok:
            masters, gate["mode_used"] = ms, mode
            break
    if masters is None:
        (rd / "result.json").write_text(json.dumps(dict(run=stamp, gate=gate, status="GATE FAILED: nothing new rendered"), indent=1) + "\n", encoding="utf-8")
        print("GATE FAILED; nothing rendered", flush=True)
        sys.exit(2)
    # ---------------- render recovered keys
    rec = json.loads((REC / "recovery.json").read_text(encoding="utf-8"))
    L.SOURCE_DIRS.insert(0, str(REC))
    keys_out, skipped = [], []
    for k, info in sorted(rec["files"].items()):
        raw = k[:8]
        aliases = W.drawn_aliases(raw)
        uvs = (aliases.get(k) or {}).get("uv") or []
        y = STRIPS[raw]
        inside = bool(uvs) and all((u['uv'][0] < 64 and y < 64) or (u['uv'][0] >= 192 and y >= 64) for u in uvs)
        clc = L.load_clut(k[9:])
        if not clc or Path(clc["path"]).parent.resolve() != REC.resolve():
            skipped.append(dict(key=k, reason="CLUT not taken from the recovery folder"))
            continue
        if not inside:
            skipped.append(dict(key=k, reason="drawn UVs not all inside the font regions (builder rule)", uvs=uvs[:4]))
            continue
        new = strip(masters, k, clc["clut"])
        W.save_rt(new, str(rd), k)
        keys_out.append(dict(key=k, kind="strip", page_rows=[y, y + 8], clut=dict(path=clc["path"], sha256=clc["sha256"]),
                             recovery_evidence=info["evidence"], drawn_uv=uvs,
                             runtime={s_: dict(path=f"runtime-{s_}/{k}.png", sha256=sha(rd / f"runtime-{s_}/{k}.png")) for s_ in ("2048", "1024")}))
    # ---------------- strict audit
    shutil.copy2(PROTO / "class_mip.c", rd / "class_mip.c")
    shutil.copy2(PROTO / "class_mip.h", rd / "class_mip.h")
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(rd / "class_mip.dll")],
                       capture_output=True, text=True, timeout=60, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(rd / "class_mip.dll"))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    npass = ns2 = 0
    for e in keys_out:
        y = e["page_rows"][0]
        clut = np.fromfile(e["clut"]["path"], dtype="<u2")
        lut = np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in clut], np.uint8)
        ncls = np.ascontiguousarray(lut[IDX[y:y + 8]])
        e["audit"] = {}
        for s_ in ("2048", "1024"):
            with Image.open(rd / e["runtime"][s_]["path"]) as im:
                a = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            H, Wd = a.shape[:2]
            sc = Wd // 256
            rep = CmReport()
            lib.cm_validate(a.ctypes.data, Wd, H, ncls.ctypes.data, 256, 8, sc, ctypes.byref(rep))
            v2 = {n: int(getattr(rep, n)) for n in RF}
            out = {}
            for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
                fl = np.zeros((H, Wd), np.uint8)
                lib.cm_flags_ex(a.ctypes.data, Wd, H, ncls.ctypes.data, 256, 8, sc, bound, 0, fl.ctypes.data)
                out[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
            prim = v2["r1_centre_bad"] == 0 and out["conn_viol_px"] == 0
            strict = all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))
            npass += prim
            ns2 += strict
            e["audit"][s_] = dict(v2=v2, **out, primary_pass=prim, s2_strict_pass=strict, alpha_values=sorted(int(x) for x in np.unique(a[..., 3])))
    res = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", status="candidate (not installed, not live-accepted)",
               method="frozen hud-label-font-BDAE4156-v1 fade-strip method (build_hudfont.py) with CRC-proven recovered CLUTs",
               inputs=dict(frozen_manifest_sha256=sha(FROZEN / "manifest.json"), recovery_json_sha256=sha(REC / "recovery.json"),
                           builder_snapshot={p.name: sha(p) for p in sorted(BUILDER.glob("*.py"))}),
               gate=gate, keys=keys_out, skipped=skipped, rendered=len(keys_out),
               audit_summary=dict(files=2 * len(keys_out), primary_pass=npass, s2_strict_pass=ns2,
                                  bounds=dict(s2=0.5, conn_only=1.0e9, cm_validate_R2="0.5*s Euclidean")),
               seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(res, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)) + "\n", encoding="utf-8")
    print("rendered", len(keys_out), "skipped", len(skipped), "primary", npass, "/", 2 * len(keys_out), "s2", ns2, "seconds", res["seconds"],
          "result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
