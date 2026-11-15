#!/usr/bin/env python3
"""s67 isolated REPAIR PROPOSAL r1: 30BB2999 (Stage 7 space backdrop, VRAM 576,0) star bursts as analytic radial shapes.

Defect (lane LEDGER w7-stage7 + review/native-vs-hd-16x-and-page-01.png): the four star-burst sprites (u0-127, v218-247)
'became soft blobs' in v1 (index master sigma 0.6). The lane names 'CPU analytic shapes' as the next step.
Evidence (s67 repairs/30BB2999-burst-fit-*.json): each burst is a Euclidean digital disc centred at (16/48/80/112, 231); off the
axis band the native index falls monotonically with radius (<= 8 order violations of 344-507 ring texels).
Method (CPU, deterministic, no AI, no new palette, CLUT-free):
  * per sprite, from off-axis-band native texels only: a monotone piecewise-linear radial index field g(r) through the median
    radius of each index (isotonic), and a silhouette radius R_out with the background index outside;
  * EXCEPTION cells keep v1 bytes (per key CLUT): the axis band (|du| <= BAND or |dv| <= BAND texels: the spikes and the '+'
    core); every texel whose model CLASS differs from the native class at its centre or straddling pixels; and every texel
    whose model index differs from the native index by >= 2 (a real feature; +-1 is ring quantisation jitter, which is what
    the smooth rebuild intentionally removes). Elsewhere in the sprite box:
      class = class of round(g) under the key's CLUT (cutout/STP/opaque); the class at every texel centre (and its straddling
      pixels) equals the native class by construction; RGB = linear interpolation between the CLUT colours of floor(g) and ceil(g) when both have the same
      class, else the colour of round(g); cutout pixels keep their v1 RGB;
  * outside the four sprite boxes every byte stays v1.
Whole-cell strict validation (frozen proto-v2b cm_validate, DLL already compiled in the s67 audit run) gates the output.
Not an acceptance: drawn CLUTs, motion and live A/B are still unknown (CR7-1..5).
usage: python -B -I s7_burst_rebuild.py preview   (LIGHT: native-region render at 8x for both CLUTs, centre check, review PNG)
       python -B -I s7_burst_rebuild.py build     (HEAVY: 2 keys x 2 sizes from the frozen v1 PNGs; needs a granted CPU slot)
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/repairs/(30BB2999-burst-preview-<UTC>.png|
stage7-space-backdrop-30BB2999-bursts-r1/)."""
import ctypes
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
V1 = ROOT / "remaster-audit/comfy-authoring/w7-stage7/frozen/stage7-space-backdrop-30BB2999-v1"
S67 = ROOT / "remaster-audit/parallel-stages-20261114/s67"
OUT = S67 / "repairs/stage7-space-backdrop-30BB2999-bursts-r1"
DLL = S67 / "runs/20261114T135603Z/class_mip.dll"
TEX = "30BB2999"
CENTRES = [(16, 231), (48, 231), (80, 231), (112, 231)]
BOX = (16, 13, 16, 16)          # left, up, right, down texels from the centre -> u c-16..c+15, v 218..246
BAND = 1


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load():
    m = json.loads((V1 / "manifest.json").read_text(encoding="utf-8"))
    pg = m["pages"][TEX]
    wb = Path(pg["words"]["path"]).read_bytes()
    assert "%08X" % (__import__("zlib").crc32(wb) & 0xFFFFFFFF) == TEX
    w = np.frombuffer(wb, "<u2").reshape(256, 64)
    idx = np.stack([(w >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)
    cluts = {}
    for key, k in m["keys"].items():
        cw = np.array([int.from_bytes(bytes.fromhex(k["clut"]["hex"][i:i + 4]), "little") for i in range(0, 64, 4)], np.int64)
        assert "%08X" % (__import__("zlib").crc32(bytes.fromhex(k["clut"]["hex"])) & 0xFFFFFFFF) == key[9:]
        cls = np.where(cw == 0, 0, np.where(cw & 0x8000, 255, 127)).astype(np.uint8)
        rgb = np.stack([(cw & 31) * 255 / 31, ((cw >> 5) & 31) * 255 / 31, ((cw >> 10) & 31) * 255 / 31], -1).astype(np.float32)
        cluts[key] = dict(cw=cw, cls=cls, rgb=rgb, files=k["files"])
    return m, idx, cluts


def fit_sprite(idx, cx, cy):
    l, u, r, d = BOX
    ys, xs = np.mgrid[cy - u:cy + d, cx - l:cx + r]
    v = idx[ys, xs]
    rr = np.hypot(xs - cx, ys - cy)
    band = (np.abs(xs - cx) <= BAND) | (np.abs(ys - cy) <= BAND)
    bg = int(np.bincount(idx[cy - u, cx - l:cx + r]).argmax())          # background index on the box's top row
    inside = ~band & (v != bg)
    pts = []
    for i in sorted(set(v[inside].tolist())):
        sel = inside & (v == i)
        pts.append((float(np.median(rr[sel])), i, int(sel.sum())))
    # radius must fall as the index rises (index 1 at the rim, high indices at the centre): isotonic by index
    pts.sort(key=lambda t: t[1])
    rs = [p[0] for p in pts]
    for k in range(1, len(rs)):
        rs[k] = min(rs[k], rs[k - 1] - 1e-3)
    knots_r = np.array(rs[::-1])
    knots_i = np.array([p[1] for p in pts][::-1], np.float32)
    ring = ~band & (v != bg)
    out = ~band & (v == bg)
    cand = np.linspace(rr[ring].max() - 2, rr[ring].max() + 1, 61)
    errs = [int((rr[ring] > c).sum() + (rr[out] <= c).sum()) for c in cand]
    r_out = float(cand[int(np.argmin(errs))])
    return dict(centre=[cx, cy], bg=bg, knots_r=knots_r.tolist(), knots_i=knots_i.tolist(), r_out=r_out,
                silhouette_misclassified=int(min(errs)), points=pts)


def g_of(rr, f):
    g = np.interp(rr, np.array(f["knots_r"]), np.array(f["knots_i"]))
    return np.where(rr > f["r_out"], float(f["bg"]), g)


def model_index_at_centres(idx, f, cls=None):
    """Exception (keep-v1) texels for one sprite under one CLUT class table `cls` (None = exact-index rule):
    the axis band; any texel whose MODEL CLASS differs from the native class at its centre or at the pixels that straddle it
    on the 2048 (+-1/16) and 1024 (+-1/8) grids (so R1 holds at both sizes by construction); and any texel whose model index
    differs from the native index by >= 2 at its centre (a real feature such as a ray, not +-1 quantisation jitter)."""
    cx, cy = f["centre"]
    l, u, r, d = BOX
    ys, xs = np.mgrid[cy - u:cy + d, cx - l:cx + r]
    nat = idx[ys, xs]
    band = (np.abs(xs - cx) <= BAND) | (np.abs(ys - cy) <= BAND)
    exc = band.copy()
    for ox, oy in [(0, 0)] + [(sx * o, sy * o) for o in (0.0625, 0.125) for sx in (-1, 1) for sy in (-1, 1)]:
        rr = np.hypot(xs + ox - cx, ys + oy - cy)
        g = g_of(rr, f)
        mi = np.where(rr > f["r_out"], f["bg"], np.clip(np.rint(g), 0, 15)).astype(int)
        if cls is None:
            exc |= mi != nat
        else:
            exc |= cls[mi] != cls[nat]
            if ox == 0 and oy == 0:
                exc |= np.abs(mi - nat) >= 2
    return ys, xs, exc


def render_region(f, exc, ys, xs, s, clut):
    """HD pixels for the sprite box at scale s: returns rgb (float), alpha (uint8), keep-mask (True = use v1)."""
    cx, cy = f["centre"]
    h, w = ys.shape
    py, px = np.mgrid[0:h * s, 0:w * s]
    tx = xs[0, 0] + (px + 0.5) / s - 0.5
    ty = ys[0, 0] + (py + 0.5) / s - 0.5
    rr = np.hypot(tx - cx, ty - cy)
    g = g_of(rr, f)
    gi = np.clip(np.rint(g), 0, 15).astype(int)
    lo, hi = np.clip(np.floor(g), 0, 15).astype(int), np.clip(np.ceil(g), 0, 15).astype(int)
    fr = (g - np.floor(g))[..., None]
    rgb_l = clut["rgb"][lo] * (1 - fr) + clut["rgb"][hi] * fr
    same = clut["cls"][lo] == clut["cls"][hi]
    rgb = np.where(same[..., None], rgb_l, clut["rgb"][gi])
    a = clut["cls"][gi]
    keep = np.kron(exc, np.ones((s, s), bool))
    return rgb, a, keep


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    t0 = time.time()
    m, idx, cluts = load()
    fits = [fit_sprite(idx, cx, cy) for cx, cy in CENTRES]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ex_counts = []
    for f in fits:
        ys, xs, exc = model_index_at_centres(idx, f)
        f["exception_texels"] = int(exc.sum())
        f["box_texels"] = int(exc.size)
        ex_counts.append(f["exception_texels"])
    if mode == "preview":
        from PIL import Image
        s = 8
        rows = []
        for key, cl in cluts.items():
            tiles = []
            for f in fits:
                ys, xs, exc = model_index_at_centres(idx, f, cl["cls"])
                f.setdefault("exception_texels_by_clut", {})[key] = int(exc.sum())
                rgb, a, keep = render_region(f, exc, ys, xs, s, cl)
                nat = idx[ys, xs]
                nat_rgb = np.kron(cl["rgb"][nat], np.ones((s, s, 1)))
                nat_a = np.kron(cl["cls"][nat], np.ones((s, s), np.uint8))
                # centre class check on modelled (non-exception) cells
                c = s // 2
                ctr = a[c::s, c::s]
                f.setdefault("centre_class_mismatch", {})[key] = int(((ctr != cl["cls"][nat]) & ~exc).sum())
                show_m = np.where(keep[..., None], nat_rgb * 0.35, rgb)       # exception cells dimmed (v1 is kept there)
                show_m = np.where((a == 0)[..., None] & ~keep[..., None], 0, show_m)
                show_n = np.where((nat_a == 0)[..., None], 0, nat_rgb)
                pair = np.concatenate([show_n, np.full((show_n.shape[0], 6, 3), 20.0), show_m], 1)
                tiles.append(np.clip(pair, 0, 255).astype(np.uint8))
            row = np.concatenate([np.concatenate([t, np.full((t.shape[0], 10, 3), 40, np.uint8)], 1) for t in tiles], 1)
            rows.append(row)
        sheet = np.concatenate([np.concatenate([r, np.full((10, r.shape[1], 3), 40, np.uint8)], 0) for r in rows], 0)
        dst = S67 / "repairs" / f"30BB2999-burst-preview-{stamp}.png"
        Image.fromarray(sheet).save(dst, optimize=True)
        info = dict(run=stamp, mode="preview (native-region render, no v1 decode)", fits=fits, review=dst.name,
                    note="each tile pair: native at 8x (cutout black) | r1 model (exception cells dimmed = v1 kept there)")
        (S67 / "repairs" / f"30BB2999-burst-preview-{stamp}.json").write_text(json.dumps(info, indent=1, default=float) + "\n",
                                                                           encoding="utf-8")
        for f in fits:
            print(f["centre"], "bg", f["bg"], "r_out %.2f" % f["r_out"], "sil_mis", f["silhouette_misclassified"],
                  "exact-index exceptions", f["exception_texels"], "/", f["box_texels"], "class-rule exceptions",
                  f.get("exception_texels_by_clut"), "centre_mismatch", f.get("centre_class_mismatch"))
        print("preview", dst, sha(dst), "elapsed %.1fs" % (time.time() - t0))
        return
    assert mode == "build", mode
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cpu=")), me.cpu_affinity()[-1]))])
        prio = dict(pid=me.pid, nice="below_normal", affinity=me.cpu_affinity())
    except Exception as e:
        prio = dict(error=repr(e))
    from PIL import Image
    sys.path.insert(0, str(S67 / "tools"))
    import s67_strict_audit as A
    lib = ctypes.CDLL(str(DLL))
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(A.CmReport)]
    assert not OUT.exists(), "output exists (immutable): bump the revision"
    OUT.mkdir(parents=True)
    rows = []
    for key, cl in cluts.items():
        ncls = np.ascontiguousarray(cl["cls"][idx])
        for tag, f_ in sorted(cl["files"].items()):
            src = V1 / f_["path"]
            assert sha(src) == f_["sha256"], f"v1 hash mismatch {src}"
            with Image.open(src) as im:
                v1 = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            s = v1.shape[1] // 256
            new = v1.copy()
            changed = 0
            for f in fits:
                ys, xs, exc = model_index_at_centres(idx, f, cl["cls"])
                rgb, a, keep = render_region(f, exc, ys, xs, s, cl)
                y0, x0 = ys[0, 0] * s, xs[0, 0] * s
                blk = new[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
                v1b = v1[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
                put = ~keep
                blk[..., 3] = np.where(put, a, v1b[..., 3])
                rgb8 = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
                vis = put & (a != 0)
                for ch in range(3):
                    blk[..., ch] = np.where(vis, rgb8[..., ch], v1b[..., ch])
                changed += int((blk != v1b).any(-1).sum())
            rep = A.CmReport()
            lib.cm_validate(new.ctypes.data, new.shape[1], new.shape[0], ncls.ctypes.data, 256, 256, s, ctypes.byref(rep))
            v2 = {n: int(getattr(rep, n)) for n, _ in A.CmReport._fields_}
            dst = OUT / f_["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(new, "RGBA").save(dst, optimize=True)
            rows.append(dict(key=key, file=tag, src_sha256=f_["sha256"], out=f_["path"], out_sha256=sha(dst), scale=s,
                             pixels_changed=changed, alpha_changed_px=int((new[..., 3] != v1[..., 3]).sum()), v2_after=v2,
                             whole_cell_strict_pass=all(v2[x] == 0 for x in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                                                               "r4_island_px", "nonclass_px"))))
            print(key, tag, "changed", changed, "alpha_changed", rows[-1]["alpha_changed_px"], "strict", rows[-1]["whole_cell_strict_pass"], flush=True)
            del v1, new
    man = dict(name=OUT.name, status="proposal (s67 repair r1; NOT frozen lane art; NOT accepted)", owner="claude-einhander-s67",
               task="EIN-S7-WHOLE-CELL-20261114", created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               base=dict(folder=str(V1.relative_to(ROOT)).replace("\\", "/"), manifest_sha256=sha(V1 / "manifest.json")),
               method=__doc__, fits=fits, priority=prio, elapsed_s=round(time.time() - t0, 2), rows=rows,
               validator_dll=dict(path=str(DLL), sha256=sha(DLL)), builder=dict(path=str(Path(__file__)), sha256=sha(Path(__file__))))
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1, default=float) + "\n", encoding="utf-8")
    print("out", OUT, "manifest", sha(OUT / "manifest.json"), "elapsed", man["elapsed_s"])


if __name__ == "__main__":
    main()
