#!/usr/bin/env python3
"""s67 (claude-einhander-s67): strict WHOLE-CELL class audit of the Stage 6 (101) and Stage 7 (26) selected candidate keys.
READ-ONLY on w7-stage6 / w7-stage7 / w2-effects; writes ONLY s67/runs/<UTC>/. CPU only: one core, below-normal priority.

Inputs are taken from the pinned s67 selection maps (stage6/selection-map-*.json, stage7/selection-map-*.json), whose source
proofs this re-derives independently before testing pixels:
  * native words: Stage 6 frozen folder source/<TEX>.words.bin (64x256 words, 4bpp); Stage 7 static-export words named by
    the manifest; CRC32(words) must equal TEX (CRC-proven) or the key is reported, not tested;
  * native CLUT: Stage 6 source/<TEX>-<PAL>.clut.bin (or the Stage 1 w2-effects copy for the four byte-for-byte reused
    10932164 keys); Stage 7 manifest clut.hex; CRC32 must equal PAL;
  * native class map: word 0x0000 -> 0 cutout, STP bit 15 -> 255, else 127 (same rule as s6_verify / audit_s23).
Per HD file (2048 and 1024): frozen proto-v2b cm_validate (R1 centre, R2 displacement > s/2, R3 uniform, R4 islands, R5 fringe,
non-class alpha) and cm_flags_ex (bound s/2 Euclidean) for connectivity-only (bits 2|4|16), plus a per-native-cell violation
map (worst cells as texel u,v) so isolated repair proposals can target exact cells.
  whole_cell_strict_pass = R1 == R2 == R3 == R4 == 0 and nonclass == 0;   primary_pass = R1 == 0 and connectivity == 0.
The lane's own centre-only gate is recorded next to it; the two are NOT interchangeable.
usage: python -B -I s67_strict_audit.py [--dry-run] [--no-alternates] [--budget-s=270]
  --budget-s: stop starting new keys after this many seconds (partial result is written, complete=false)
  --dry-run: input/proof/PNG-header checks only (no compile, no decode) - safe without a CPU slot."""
import ctypes
import datetime
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
S67 = ROOT / "remaster-audit/parallel-stages-20261114/s67"
PROTO = ROOT / "remaster-audit/claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
S6 = ROOT / "remaster-audit/comfy-authoring/w7-stage6"
S7 = ROOT / "remaster-audit/comfy-authoring/w7-stage7"
ALT6 = {  # alternates retained by the lane (not selected, not additive): audited separately for reference
    "stage6-smoke-exhaust-D552405C-v1": "D552405C",
    "stage6-vram704-0-20961255-E0849F81-v1": "20961255",
    "stage6-vram384-0-8F498326-F07625EE-v1": "8F498326",
}


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                               "r4_island_px", "r5_fringe_px", "cells_bad", "pinhole_cells", "nonclass_px")]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def png_dims(p):
    with open(p, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    w, h, bd, ct = struct.unpack(">IIBB", head[16:26])
    return dict(w=w, h=h, bit_depth=bd, colour_type=ct)


def latest(stage):
    c = sorted((S67 / f"stage{stage}").glob("selection-map-*.json"))
    assert c, f"no stage{stage} selection map"
    return c[-1]


def native_class(words, ww, hh, clut_words):
    w16 = np.frombuffer(words, "<u2")[:ww * hh].reshape(hh, ww)
    n = len(clut_words)
    if n == 16:
        idx = np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], axis=-1).reshape(hh, ww * 4)
    elif n == 256:
        idx = np.stack([w16 & 0xFF, w16 >> 8], axis=-1).reshape(hh, ww * 2)
    else:
        raise ValueError(f"CLUT of {n} entries")
    rr = np.array(clut_words, np.int64)
    lut = np.where(rr == 0, 0, np.where(rr & 0x8000, 255, 127)).astype(np.uint8)
    return np.ascontiguousarray(lut[idx])


def stage1_clut_copy(key, stage1_file):
    """Stage 1 reused key: locate <TEX>-<PAL>.clut.bin in the Stage 1 frozen folder that holds the reused PNG."""
    if not stage1_file:
        return None
    p = Path(stage1_file)
    for d in [p.parent.parent, p.parent.parent.parent]:
        for c in (d / "source" / f"{key}.clut.bin", d / "source" / f"{key[:8]}-{key[9:]}.clut.bin"):
            if c.exists():
                return c
        hits = list(d.glob(f"**/{key}.clut.bin"))
        if hits:
            return hits[0]
    return None


def jobs(alternates=True):
    """Yield one job per key: dict(stage, group, key, words_path, rect, clut_words, clut_src, files{tag: path}, lane_gate)."""
    m6p, m7p = latest(6), latest(7)
    m6, m7 = json.loads(m6p.read_text(encoding="utf-8")), json.loads(m7p.read_text(encoding="utf-8"))
    out = []
    for r in m6["rows"]:
        d = ROOT / r["selected_folder"]
        if r.get("clut_file"):
            cp = ROOT / r["clut_file"]
        else:
            cp = stage1_clut_copy(r["key"], (r["files"].get("2048") or {}).get("stage1_file"))
        out.append(dict(stage=6, group="selected", folder=d.name, key=r["key"], words=ROOT / r["words"], rect=[0, 0, 64, 256],
                        clut_path=cp, files={t: d / f["path"] for t, f in r["files"].items() if "path" in f},
                        file_sha={t: f["manifest_sha256"] for t, f in r["files"].items() if "path" in f},
                        lane_gate=r.get("recorded_gates")))
    if alternates:
        for fname, tex in ALT6.items():
            d = S6 / "frozen" / fname
            m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            for k in m["keys"]:
                if k["key"][:8] != tex:
                    continue
                files = {t: d / k[f"png_{t}"]["path"] for t in ("2048", "1024") if k.get(f"png_{t}")}
                out.append(dict(stage=6, group="alternate", folder=fname, key=k["key"], words=d / "source" / f"{tex}.words.bin",
                                rect=[0, 0, 64, 256], clut_path=d / "source" / f"{k['key']}.clut.bin", files=files,
                                file_sha={t: k[f"png_{t}"]["sha256"] for t in files}, lane_gate=k.get("gates")))
    for r in m7["rows"]:
        d = S7 / "frozen" / r["folder"]
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        k = m["keys"][r["key"]]
        pg = m["pages"][r["tex"]]
        out.append(dict(stage=7, group="selected", folder=r["folder"], key=r["key"], words=Path(pg["words"]["path"]),
                        rect=pg["vram_rect_words"], clut_hex=k["clut"]["hex"],
                        files={t: d / f["path"] for t, f in k["files"].items()},
                        file_sha={t: f["sha256"] for t, f in k["files"].items()},
                        lane_gate={t: dict(forced_texel_centres=f.get("forced_texel_centres"), class_mismatches=f.get("class_mismatches"))
                                   for t, f in k["files"].items()}))
    return out, dict(stage6=dict(path=str(m6p), sha256=sha(m6p)), stage7=dict(path=str(m7p), sha256=sha(m7p)))


def prove(j, cache):
    """Independent source proof; returns (ncls, proof dict) or (None, proof)."""
    wp = Path(j["words"])
    if str(wp) not in cache:
        b = wp.read_bytes()
        cache[str(wp)] = (b, crc(b), sha(wp))
    b, wcrc, wsha = cache[str(wp)]
    tex, pal = j["key"][:8], j["key"][9:]
    pr = dict(words=str(wp), words_sha256=wsha, words_crc_proven=wcrc == tex)
    if j.get("clut_hex"):
        cb = bytes.fromhex(j["clut_hex"])
        pr.update(clut_src="manifest clut.hex")
    elif j.get("clut_path") and Path(j["clut_path"]).exists():
        cb = Path(j["clut_path"]).read_bytes()
        pr.update(clut_src=str(j["clut_path"]), clut_sha256=sha(j["clut_path"]))
    else:
        pr.update(clut_src=None, error="no CLUT words available")
        return None, pr
    pr["clut_crc_proven"] = crc(cb) == pal
    if not (pr["words_crc_proven"] and pr["clut_crc_proven"]):
        pr["error"] = "source not CRC-proven; key not tested"
        return None, pr
    cw = [int.from_bytes(cb[i:i + 2], "little") for i in range(0, len(cb), 2)]
    ncls = native_class(b, j["rect"][2], j["rect"][3], cw)
    pr.update(native_dims=[ncls.shape[1], ncls.shape[0]], clut_entries=len(cw), cutout_texels=int((ncls == 0).sum()),
              stp_texels=int((ncls == 255).sum()))
    return ncls, pr


def cell_map(fl, s, th, tw, bits):
    """Per native cell count of flagged pixels; returns worst cells [u, v, px] and the count of bad cells."""
    m = ((fl & bits) != 0).reshape(th, s, tw, s).sum(axis=(1, 3))
    bad = np.argwhere(m > 0)
    order = np.argsort(-m[bad[:, 0], bad[:, 1]])[:25] if len(bad) else []
    return int(len(bad)), [[int(bad[i][1]), int(bad[i][0]), int(m[bad[i][0], bad[i][1]])] for i in order]


def main():
    dry = "--dry-run" in sys.argv
    alts = "--no-alternates" not in sys.argv
    t0 = time.time()
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([me.cpu_affinity()[-1]])
        prio = dict(nice="below_normal", affinity=me.cpu_affinity(), pid=me.pid)
    except Exception as e:  # report, never silently claim a priority we did not set
        prio = dict(error=f"psutil priority/affinity not applied: {e!r}")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S67 / "runs" / (stamp + ("-dry" if dry else ""))
    rd.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), rd / Path(__file__).name)
    js, maps = jobs(alts)
    lib = None
    if not dry:
        for p in (PROTO / "class_mip.c", PROTO / "class_mip.h"):
            shutil.copy2(p, rd / p.name)
        dll = rd / "class_mip.dll"
        c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(rd / "class_mip.c"), "-o", str(dll)],
                           capture_output=True, text=True, timeout=300, creationflags=0x4000)
        (rd / "compile.log").write_text(f"exit {c.returncode}\n{c.stdout}\n{c.stderr}\n", encoding="utf-8")
        assert c.returncode == 0, c.stderr
        lib = ctypes.CDLL(str(dll))
        lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.POINTER(CmReport)]
        lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
    rows, cache = [], {}
    budget = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--budget-s=")), "270"))
    aborted = None
    prog = rd / "progress.json"
    for ji, j in enumerate(js):
        if time.time() - t0 > budget:
            aborted = dict(reason=f"time budget {budget}s reached", at_job=ji, jobs=len(js))
            break
        if ji % 10 == 0:
            prog.write_text(json.dumps(dict(job=ji, jobs=len(js), rows=len(rows), elapsed_s=round(time.time() - t0, 1),
                                            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())) + "\n",
                            encoding="utf-8")
        ncls, pr = prove(j, cache)
        base = dict(stage=j["stage"], group=j["group"], folder=j["folder"], key=j["key"], proof=pr)
        for tag, fp in sorted(j["files"].items()):
            row = dict(base, file=tag, path=str(fp), lane_gate=(j.get("lane_gate") or {}).get(tag))
            if not fp.exists():
                rows.append(dict(row, error="missing file"))
                continue
            hd = png_dims(fp)
            row["png_header"] = hd
            if ncls is None:
                rows.append(dict(row, error=pr.get("error")))
                continue
            th, tw = ncls.shape
            if not hd or hd["w"] % tw or hd["h"] % th or hd["w"] // tw != hd["h"] // th:
                rows.append(dict(row, error=f"dims {hd} not a native multiple of {tw}x{th}"))
                continue
            s = hd["w"] // tw
            if dry:
                rows.append(dict(row, scale=s, dry_run=True))
                continue
            row["sha256"] = sha(fp)
            row["sha256_matches_manifest"] = row["sha256"] == j["file_sha"].get(tag)
            with Image.open(fp) as im:
                a = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            H, W = a.shape[:2]
            rep = CmReport()
            lib.cm_validate(a.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, ctypes.byref(rep))
            fl = np.zeros((H, W), np.uint8)
            lib.cm_flags_ex(a.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, 0.5, 0, fl.ctypes.data)
            v2 = {f_: int(getattr(rep, f_)) for f_, _ in CmReport._fields_}
            conn = int(((fl & (2 | 4 | 16)) != 0).sum())
            bad_cells, worst = cell_map(fl, s, th, tw, 2 | 4 | 16)
            r3_cells, r3_worst = cell_map(fl, s, th, tw, 8)
            alpha_vals = sorted(int(x) for x in np.unique(a[..., 3]))
            rows.append(dict(row, scale=s, v2=v2, conn_viol_px=conn, conn_bad_cells=bad_cells, conn_worst_cells_uv_px=worst,
                             r3_cells=r3_cells, r3_worst_cells_uv_px=r3_worst[:10], alpha_values=alpha_vals[:8],
                             whole_cell_strict_pass=all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px",
                                                                               "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                             primary_pass=v2["r1_centre_bad"] == 0 and conn == 0 and v2["nonclass_px"] == 0))
            del a, fl
    summ = {}
    for r in rows:
        g = summ.setdefault(f'S{r["stage"]} {r["group"]} {r["folder"]}', dict(keys=set(), files=0, errors=0, strict_pass=0,
                                                                           primary_pass=0, r5_fringe_px=0, sha_ok=0, worst=[]))
        g["keys"].add(r["key"])
        if "error" in r:
            g["errors"] += 1
            continue
        g["files"] += 1
        if r.get("dry_run"):
            continue
        g["strict_pass"] += int(r["whole_cell_strict_pass"])
        g["primary_pass"] += int(r["primary_pass"])
        g["r5_fringe_px"] += r["v2"]["r5_fringe_px"]
        g["sha_ok"] += int(r["sha256_matches_manifest"])
        if not r["whole_cell_strict_pass"]:
            g["worst"].append([r["key"], r["file"], r["v2"]["r1_centre_bad"], r["v2"]["r2_displaced_px"],
                               r["v2"]["r3_uniform_bad_px"], r["v2"]["r4_island_px"], r["conn_viol_px"]])
    for g in summ.values():
        g["keys"] = len(g["keys"])
        g["worst"] = sorted(g["worst"], key=lambda x: -(x[6] + x[4]))[:12]
    res = dict(run=rd.name, owner="claude-einhander-s67", tasks=["EIN-S6-WHOLE-CELL-20261114", "EIN-S7-WHOLE-CELL-20261114"],
               dry_run=dry, priority=prio, elapsed_s=round(time.time() - t0, 2), selection_maps=maps, aborted=aborted,
               jobs_total=len(js), complete=aborted is None,
               validator=dict(path=str(PROTO / "class_mip.c"), sha256=sha(PROTO / "class_mip.c"), h_sha256=sha(PROTO / "class_mip.h")),
               rule=("frozen proto-v2b cm_validate strict s/2 (R1-R4 + non-class alpha = whole-cell strict) + cm_flags_ex "
                     "connectivity-only bits 2|4|16 (primary); R3/R5 diagnostic; lane centre-only gates recorded separately"),
               summary=summ, rows=rows, status="DATA ONLY; read-only on the stage lanes; no art edits")
    (rd / "result.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    for n, g in summ.items():
        print(f'{n:60s} keys={g["keys"]} files={g["files"]} err={g["errors"]} strict={g["strict_pass"]} primary={g["primary_pass"]} '
              f'r5={g["r5_fringe_px"]} sha_ok={g["sha_ok"]} worst={g["worst"][:2]}')
    print("run", rd, "elapsed", res["elapsed_s"], "result", sha(rd / "result.json"))


if __name__ == "__main__":
    main()
