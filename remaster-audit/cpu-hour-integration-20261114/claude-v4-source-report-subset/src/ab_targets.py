#!/usr/bin/env python3
"""Where would class-aware levels visibly change the minified result? (claude-einhander) Read-only, CPU only, below
normal, one logical CPU, one image at a time. Writes ONLY runs-ab/<UTC>/ (exist_ok=False) + INDEX.jsonl.

Root msg_28928d65: region O pages look fully opaque, so the class chain may equal ordinary RGB mips; show a real A/B
and rank the keys where class levels matter. For every whole-cell PASS key of the world-v4 pack (frozen breakdown,
v2 default policy) plus the two region-O keys, using the exact runtime decode (stb, hdcm_tool.dll of host run
20261114T110919Z) and the CRC-proven native map, on DRAWN cells (breakdown_v2b draw mapping):
  * cutout_fraction             level-0 cutout pixels / all pixels;
  * mixed_drawn_cells           drawn cells holding both visible and cutout HD pixels (class can alias there);
  * class_flicker_rate          mean over drawn cells of (HD pixels whose class != native class) / s^2: the chance that
                                the v61 path (texelFetch level 0 under the fragment) shows a class other than the
                                native one when a screen pixel covers about one native texel (m ~ s); class levels
                                show the native class there (M4) - this is what they remove;
  * bleed_L1_mean / _p99        on drawn level-1 footprints that mix visible and cutout children: |box RGB (all
                                four children, what glGenerateMipmap averages) - class RGB (visible children only)|,
                                mean over channels; class levels remove it;
  * opaque_rgb_diff_L1..Ls      mean / max |class chain RGB - iterative 2x2 box chain RGB| over visible texels
                                (glGenerateMipmap is implementation-defined; the box chain with round-half-up is the
                                common behaviour and is used only as a proxy).
Census size (p90 height px, size proxy) is attached where the sign census has it."""
import collections
import ctypes
import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CM = HERE.parent
HOST = HERE / "runs/20261114T110919Z"
BREAKDOWN = CM / "frozen/class-mip-v2b-breakdown-v1/runs/runs-breakdown-v2b/20261114T102254Z/result.json"
CENSUS = CM.parent / "sign-census/census-v2.json"
O_KEYS = ["95A3BCF8-60245B3A", "95A3BCF8-07A9568D"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def box_chain(a, levels):
    out, cur = [], a.astype(np.uint32)
    for _ in range(levels):
        h, w = cur.shape[0] // 2, cur.shape[1] // 2
        s4 = cur[0:2 * h:2, 0:2 * w:2] + cur[1:2 * h:2, 0:2 * w:2] + cur[0:2 * h:2, 1:2 * w:2] + cur[1:2 * h:2, 1:2 * w:2]
        cur = (s4 + 2) // 4
        out.append(cur.astype(np.uint8))
    return out


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "runs-ab" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    (rd / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    T = ctypes.CDLL(str(HOST / "hdcm_tool.dll"))
    T.hdcm_tool_decode.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    T.hdcm_tool_build_level.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_void_p]
    sys.path.insert(0, str(CM.parent / "class-audit"))
    sys.path.insert(0, str(CM))
    import audit_native_classes_v2 as A  # noqa: E402
    import breakdown_v2b as B  # noqa: E402
    bd = json.loads(BREAKDOWN.read_text(encoding="utf-8"))
    packroot = Path(bd["pack"]) / "pack"
    regions = {}
    for line in (packroot / "ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    draws = B.load_draws([Path(m["path"]) for m in bd["capture_logs"]], collections.Counter(), regions)
    census = {r["key"]: r for r in json.loads(CENSUS.read_text(encoding="utf-8"))["rows"]}
    order = [A.STOCK, A.UHU] + sorted(A.CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in A.E.glob("*/hd-on_rewind-off/*") if p.is_dir())

    def native_source(key):                             # identical lookup order to breakdown_v2b
        for d in ([packroot] if key in regions else order):
            s, c = A.try_dump(d, key, regions)
            if s:
                return s, c
        if key not in regions:
            for d in cap_dirs:
                s, c = A.try_dump(d, key, regions)
                if s:
                    return s, c
        return None, None

    rows = [r for r in bd["rows"]["pack"] if r.get("status") == "PASS" or r["key"] in O_KEYS]
    out = []
    for n, r in enumerate(rows):
        key = r["key"]
        raw = Path(r["png"]).read_bytes()
        W, H = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        buf = np.zeros(W * H * 4, np.uint8)
        w_, h_ = ctypes.c_int(), ctypes.c_int()
        if T.hdcm_tool_decode(raw, len(raw), buf.ctypes.data, buf.nbytes, ctypes.byref(w_), ctypes.byref(h_)):
            out.append(dict(key=key, error="decode"))
            continue
        a = buf.reshape(H, W, 4)
        src, cls = native_source(key)
        if src is None:
            out.append(dict(key=key, error="no native dump"))
            continue
        th, tw = cls.shape
        s = W // tw
        nl = s.bit_length() - 1
        if s < 2 or (s & (s - 1)) or W != tw * s or H != th * s:
            out.append(dict(key=key, error=f"scale {W}/{tw}"))
            continue
        ncls = np.ascontiguousarray(cls, dtype=np.uint8)
        dk = draws.get(key)
        if dk and not dk["unmapped"] and dk["dims"] == (tw, th):
            D, _ = B.raster(dk["tris"], tw, th)
        elif dk:
            D = np.ones((th, tw), bool)
        else:
            D = np.zeros((th, tw), bool)
        al = a[..., 3]
        vis = al != 0
        hcls = np.where(al == 0, 0, np.where(al >= 128, 255, 127)).astype(np.uint8)
        visc = vis.reshape(th, s, tw, s).sum(axis=(1, 3))
        mixed = (visc > 0) & (visc < s * s)
        disagree = (hcls != np.repeat(np.repeat(ncls, s, 0), s, 1)).reshape(th, s, tw, s).sum(axis=(1, 3)) / float(s * s)
        # level 1: class chain vs box chain
        lw, lh = W // 2, H // 2
        c1 = np.zeros((lh, lw, 4), np.uint8)
        q = np.zeros(lw * lh, np.int32)
        dn = np.zeros(lw * lh, np.uint8)
        T.hdcm_tool_build_level(a.ctypes.data, W * 4, W, H, ncls.ctypes.data, tw, th, s, 1, c1.ctypes.data, q.ctypes.data, dn.ctypes.data)
        bx = box_chain(a, nl)
        v4 = vis.reshape(lh, 2, lw, 2).sum(axis=(1, 3))
        mixfp = (v4 > 0) & (v4 < 4) & np.repeat(np.repeat(D, s // 2, 0), s // 2, 1)
        bleed = np.abs(bx[0][..., :3].astype(int) - c1[..., :3].astype(int)).mean(axis=2)[mixfp]
        op = []
        for L in range(1, nl + 1):
            cL = c1 if L == 1 else np.zeros((H >> L, W >> L, 4), np.uint8)
            if L > 1:
                qq = np.zeros((W >> L) * (H >> L), np.int32)
                dd = np.zeros((W >> L) * (H >> L), np.uint8)
                T.hdcm_tool_build_level(a.ctypes.data, W * 4, W, H, ncls.ctypes.data, tw, th, s, L, cL.ctypes.data, qq.ctypes.data, dd.ctypes.data)
            m = cL[..., 3] != 0
            d = np.abs(cL[..., :3].astype(int) - bx[L - 1][..., :3].astype(int))[m] if m.any() else np.zeros((0, 3), int)
            op.append(dict(L=L, mean=round(float(d.mean()), 3) if d.size else None, max=int(d.max()) if d.size else None,
                           p99=round(float(np.percentile(d, 99)), 2) if d.size else None))
        c = census.get(key, {})
        dr = c.get("draws") or {}
        out.append(dict(key=key, provenance=r.get("provenance"), status=r.get("status"), scale=s, native=[tw, th],
                        drawn_cells=int(D.sum()), draw_status=r.get("draw_status"),
                        cutout_fraction=round(float((~vis).mean()), 4),
                        mixed_cells=int(mixed.sum()), mixed_drawn_cells=int((mixed & D).sum()),
                        class_flicker_rate=round(float(disagree[D].mean()), 5) if D.any() else None,
                        bleed_L1_mean=round(float(bleed.mean()), 3) if bleed.size else 0.0,
                        bleed_L1_p99=round(float(np.percentile(bleed, 99)), 2) if bleed.size else 0.0,
                        bleed_L1_footprints=int(bleed.size), opaque_rgb_diff=op,
                        census_p90_height_px=dr.get("p90_height_px"), census_size=dr.get("size_proxy"),
                        census_layer=c.get("layer")))
        del a, buf
        if (n + 1) % 100 == 0:
            print(f"{n + 1}/{len(rows)}", flush=True)
    good = [x for x in out if "error" not in x]
    o = [x for x in good if x["key"] in O_KEYS]
    rank = sorted((x for x in good if x["drawn_cells"]),
                  key=lambda x: -(x["mixed_drawn_cells"] * (x["class_flicker_rate"] or 0) + x["bleed_L1_footprints"] * x["bleed_L1_mean"] / 255.0))
    res = dict(run=stamp, host_run=str(HOST), tool_dll_sha256=sha(HOST / "hdcm_tool.dll"), breakdown_sha256=sha(BREAKDOWN),
               keys=len(rows), measured=len(good), errors=[x for x in out if "error" in x], region_o=o,
               rank_top40=[{k: x[k] for k in ("key", "provenance", "scale", "drawn_cells", "mixed_drawn_cells", "class_flicker_rate",
                                             "bleed_L1_mean", "bleed_L1_p99", "bleed_L1_footprints", "cutout_fraction",
                                             "census_p90_height_px", "census_size", "census_layer")} for x in rank[:40]],
               rows=out)
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "runs-ab" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, measured=len(good), result_sha256=sha(rd / "result.json"))) + "\n")
    print(json.dumps(dict(region_o=o, top10=res["rank_top40"][:10]), indent=1)[:5000])


if __name__ == "__main__":
    main()
