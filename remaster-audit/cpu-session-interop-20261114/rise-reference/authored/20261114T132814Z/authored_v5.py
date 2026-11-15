#!/usr/bin/env python3
"""RISE (82831823) AUTHORED hand-vector lettering v5, ONE palette (claude-einhander). CPU only, below normal, one
process. Writes ONLY rise-native-vector/authored/<UTC>/ (exist_ok=False) + INDEX.jsonl.

v5 vs v4 (authored/20261114T132614Z): the chevron body is hand-authored too (CHEV_OUTER minus CHEV_HOLE, AND the inset
silhouette) instead of following the stepped silhouette; class, tiles and glyphs unchanged.
--- v4 docstring follows ---
"""
"""RISE (82831823) AUTHORED hand-vector lettering v4, ONE palette (claude-einhander). CPU only, below normal, one
process. Writes ONLY rise-native-vector/authored/<UTC>/ (exist_ok=False) + INDEX.jsonl.

v4 vs v2 (authored/20261114T132208Z): identical CLASS (the strict-valid polygonized native silhouette, DP tolerance =
largest passing value of the sweep) and identical glyphs; RGB only changes. In the native the silhouette's steps,
nubs and inter-tile joins are dark OUTLINE cells (CLUT 1/2/11) around clean green tile bodies, while v2 painted the
whole silhouette green (green bumps). v4 hand-authors the green BODIES as rounded rectangles (TILES, native texels)
intersected with the silhouette inset by BODY_INSET; everything between body and silhouette is outline (1 -> 2,
teal 11/13 on R's left, 11/10 toward the chevron); the chevron body is its zone inset by CHEV_INSET with the native
symmetric ramp 13 -> 12 -> 14. v3 (curved silhouette, authored/20261114T132332Z) failed the primary gate and is kept.
--- v2 docstring follows ---
"""
"""RISE (82831823) AUTHORED hand-vector lettering v2, ONE palette first (claude-einhander; root msg_4b67b05f,
msg_1125c47e, msg_0bfe8ac1). CPU only, below normal, one process. Writes ONLY rise-native-vector/authored/<UTC>/
(exist_ok=False) + INDEX.jsonl.

v1 (authored/20261114T131711Z) review, kept as REJECTED: clean glyph geometry and valid class, but (a) the Gaussian
-smoothed silhouette is wavy/bumpy with blob-shaped gaps, (b) the engraving (floor 4 on body 5) is far too faint.
v2 changes: (a) silhouette = the native class boundary POLYGONIZED (cell-edge contour, Douglas-Peucker <= 0.45 texel,
i.e. inside the s/2 band) and corner-rounded by a 4-px morphological open/close: straight edges, clean diagonals, crisp
small gaps; (b) dark engraving (floor 3, shadow wall 2, lit wall 5) with a thin lit lip (9) on the lower-right rim;
(c) a crisper outline ring and a thin crisp bevel highlight (9) on top-left inner edges (existing ramps only, no static
index-0 glint); (d) cutout RGB = the prototype's own R5 fill (cm_fill_cutout_rgb), so R5 fringe is 0 by construction.

Not auto-vectorized interior and no native dither enlarged as shading. Every geometric element below is written by
hand in native texel coordinates (0..64 x 0..32, HD = x16) from the CRC-proven native facts (native/<run>/result.json):
  * silhouette (class): native class boundary polygonized (above); every cell centre keeps its native class (R1,
    forced and counted); the class is identical for all 33 palettes (index 15 = the only cutout);
  * tiles: outline ring (CLUT 1 -> 2), bevel (shadow toward 4, thin lit highlight 9), native teal tints kept where the
    native has them (R's left edge 11/13, E's right edge 9 -> 12 toward the chevron);
  * glyphs: explicit vector centrelines (lines, arcs, cubic Beziers) for upright R, I, S, E with butt terminals and
    round joins, rendered as ENGRAVED grooves (floor 3, shadow wall 2, lit wall 5, lip 9), light from the top left;
  * chevron: the native symmetric ramp 11 -> 13 -> 12 -> 14 by distance from its edge, interior hole kept;
  * colour: every pixel is a convex mix of CLUT INDICES (role weights), so each of the 33 palettes is rendered
    exactly (palette animation intact); only the reference palette is rendered and reviewed in v1;
  * cutout RGB = nearest visible (R5).
Validation: frozen proto-v2b cm_validate (strict s/2) + cm_flags_ex connectivity-only (R1/R2/R4 must be 0).
Review: stock (native x16) | authored world-v4 (old) | vector draft (rejected) | NEW, + class difference vs native.
NOT composed into any pack."""
import ctypes
import datetime
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter
from skimage import measure

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PROTO = CM / "frozen/class-mip-v2b-breakdown-v1/proto-v2b"
BREAKDOWN = CM / "frozen/class-mip-v2b-breakdown-v1/runs/runs-breakdown-v2b/20261114T102254Z/result.json"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
S = 16
DP_TOL = 0.3                  # Douglas-Peucker tolerance, native texels: 4.8 px + rounding 1.7 px < s/2 = 8 px
# (run 20261114T132004Z used 0.45 and dropped find_contours' +0.5 grid offset: ~2 px shift; R2/R3 failed, kept)
ROUND_PX = 4                  # corner rounding radius (morphological open + close), HD px
PALETTE = "82831823-06BDD2F5"
SW = 1.6                      # glyph groove width, native texels (25.6 HD px)
LIGHT = np.array([-1.0, -1.0]) / math.sqrt(2.0)   # toward the light (up-left; image y grows down)


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px",
                                               "r4_island_px", "r5_fringe_px", "cells_bad", "pinhole_cells", "nonclass_px")]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------------- hand-authored glyph geometry (native texel coordinates) ----------------
def cubic(p0, p1, p2, p3, n=24):
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    p0, p1, p2, p3 = (np.array(p, float) for p in (p0, p1, p2, p3))
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


def arc(c, r, a0, a1, n=24):
    a = np.radians(np.linspace(a0, a1, n + 1))
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], axis=1)


def chain(*parts):
    pts = []
    for p in parts:
        p = np.asarray(p, float)
        if pts and np.allclose(pts[-1], p[0]):
            p = p[1:]
        pts.extend(p.tolist())
    return np.array(pts)


TOP, BOT, MID = 10.3, 21.6, 15.95
GLYPHS = {
    # R: stem, D-bowl (lines + half circle), diagonal leg
    "R": [dict(name="R stem", pts=chain([(3.6, TOP), (3.6, BOT)]), butt=(False, True)),
          dict(name="R bowl", pts=chain([(3.6, TOP), (7.3, TOP)], arc((7.3, 12.65), 2.35, -90, 90), [(7.3, 15.0), (3.6, 15.0)]),
               butt=(False, False)),
          dict(name="R leg", pts=chain([(6.4, 15.0), (9.9, BOT)]), butt=(False, True))],
    # I: bar + two serifs
    "I": [dict(name="I bar", pts=chain([(17.5, TOP), (17.5, BOT)]), butt=(False, False)),
          dict(name="I top serif", pts=chain([(16.2, TOP), (18.8, TOP)]), butt=(True, True)),
          dict(name="I bottom serif", pts=chain([(16.2, BOT), (18.8, BOT)]), butt=(True, True))],
    # S: one cubic Bezier spine
    "S": [dict(name="S spine", pts=chain(cubic((31.2, 11.5), (30.4, 10.6), (29.3, TOP), (28.0, TOP)),
                                         cubic((28.0, TOP), (26.3, TOP), (24.9, 11.3), (24.9, 12.9)),
                                         cubic((24.9, 12.9), (24.9, 14.6), (26.4, 15.3), (28.0, MID)),
                                         cubic((28.0, MID), (29.6, 16.6), (31.1, 17.3), (31.1, 19.0)),
                                         cubic((31.1, 19.0), (31.1, 20.6), (29.7, BOT), (28.0, BOT)),
                                         cubic((28.0, BOT), (26.7, BOT), (25.6, 21.2), (24.8, 20.4))),
               butt=(True, True))],
    # E: top arm + stem + bottom arm as one path (rounded outer corners), middle arm
    "E": [dict(name="E frame", pts=chain([(43.6, TOP), (38.0, TOP), (38.0, BOT), (43.6, BOT)]), butt=(True, True)),
          dict(name="E middle arm", pts=chain([(38.0, MID), (42.7, MID)]), butt=(False, True))],
}


def stroke_field(paths, H, W, sw):
    """Max-coverage union of thick polylines (round joins, optional butt terminals), 1-px analytic AA.
    Returns coverage, unit offset (nx, ny) from the closest centreline point, and normalized distance t = d / r."""
    r = sw * S / 2.0
    cov = np.zeros((H, W), np.float32)
    best = np.full((H, W), np.inf, np.float32)
    nx = np.zeros((H, W), np.float32)
    ny = np.zeros((H, W), np.float32)
    for p in paths:
        P = p["pts"] * S
        x0, y0 = np.floor(P.min(0) - r - 2).astype(int)
        x1, y1 = np.ceil(P.max(0) + r + 2).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        px, py = xx + 0.5, yy + 0.5
        n = len(P) - 1
        for i in range(n):
            a, b = P[i], P[i + 1]
            ab = b - a
            L2 = float(ab @ ab)
            if L2 <= 1e-12:
                continue
            traw = ((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / L2
            t = np.clip(traw, 0.0, 1.0)
            cx, cy = a[0] + t * ab[0], a[1] + t * ab[1]
            dx, dy = px - cx, py - cy
            d = np.sqrt(dx * dx + dy * dy)
            c = np.clip(0.5 - (d - r), 0.0, 1.0)
            L = math.sqrt(L2)
            if i == 0 and p["butt"][0]:                  # butt start: cut at the start plane, perpendicular distance
                perp = np.abs((px - a[0]) * ab[1] - (py - a[1]) * ab[0]) / L
                e = -traw * L
                c = np.where(traw < 0, np.clip(0.5 - (perp - r), 0, 1) * np.clip(0.5 - e, 0, 1), c)
            if i == n - 1 and p["butt"][1]:              # butt end
                perp = np.abs((px - a[0]) * ab[1] - (py - a[1]) * ab[0]) / L
                e = (traw - 1.0) * L
                c = np.where(traw > 1, np.clip(0.5 - (perp - r), 0, 1) * np.clip(0.5 - e, 0, 1), c)
            sl = (slice(y0, y1), slice(x0, x1))
            closer = d < best[sl]
            best[sl] = np.where(closer, d, best[sl])
            inv = 1.0 / np.maximum(d, 1e-6)
            nx[sl] = np.where(closer, dx * inv, nx[sl])
            ny[sl] = np.where(closer, dy * inv, ny[sl])
            cov[sl] = np.maximum(cov[sl], c)
    return cov, nx, ny, np.clip(best / r, 0.0, 2.0)


TOL_SWEEP = (0.49, 0.47, 0.45, 0.43, 0.41, 0.39, 0.37, 0.35, 0.33, 0.30)   # largest strict-passing one is used
# hand-authored green tile bodies (x0, y0, x1, y1, corner radius), native texels, from the native body cells:
# R cols 1-11 rows 9-23; I cols 15-19 (rounded top/bottom); S cols 23-32 rows 8-23 (round tile); E cols 36-45
TILES = {"R": (0.95, 8.95, 12.0, 24.05, 1.4), "I": (15.0, 9.0, 20.0, 24.05, 1.5),
         "S": (23.0, 8.5, 33.0, 24.05, 3.0), "E": (35.95, 8.95, 46.1, 24.05, 1.2)}
BODY_INSET = 0.62             # body edge at least this far inside the silhouette (texels): the outline width
CHEV_INSET = 0.55
# v5 hand-authored chevron (native texels). Native mask rows: outer right ends x 52,53,55,57,58,60,61,63,64 (rows 6-14),
# tip x 64 rows 14-17, lower x 63,61,60,59,57,55,53,52 (rows 18-25); hole right ends x 49,51,52,54,56,56,54,53,51,50
# (rows 11-20). Edges placed >= CHEV_INSET inside the outer staircase and outside the hole staircase.
CHEV_OUTER = [(48.7, 6.75), (51.6, 6.75), (63.25, 14.5), (63.25, 17.5), (51.2, 24.75), (48.7, 24.75)]
CHEV_HOLE = [(46.0, 10.0), (47.0, 10.0), (57.3, 16.0), (48.0, 22.2), (46.0, 22.2)]


def polygon_silhouette(opaque_cells, H, W, tol=DP_TOL):
    """Native class boundary -> polygons -> HD binary mask. The cell-edge contour (find_contours on a x4 nearest grid at
    0.5) is simplified with Douglas-Peucker (tol texels), filled even-odd at 4x supersampling, then corner-rounded."""
    from PIL import ImageDraw
    from scipy.ndimage import binary_closing, binary_opening
    g = 4
    m = np.pad(np.repeat(np.repeat(opaque_cells.astype(np.float32), g, 0), g, 1), 1)
    polys = []
    for c in measure.find_contours(m, 0.5):
        c = measure.approximate_polygon(c, tolerance=tol * g)
        # array index i of the padded x4 grid is the CENTRE of cell i-1, i.e. native (i - 1 + 0.5) / g
        polys.append([((x - 0.5) / g, (y - 0.5) / g) for y, x in c])     # native texel coordinates
    SS = 4
    acc = np.zeros((H * SS, W * SS), bool)
    for pts in polys:
        im = Image.new("1", (W * SS, H * SS), 0)
        # PIL samples pixel (i, j) at integer coordinates: shift by -0.5 so subpixel centres are at (i + 0.5)
        ImageDraw.Draw(im).polygon([(x * S * SS - 0.5, y * S * SS - 0.5) for x, y in pts], fill=1)
        acc ^= np.asarray(im, bool)                                       # even-odd: holes cancel
    mask = acc.reshape(H, SS, W, SS).mean(axis=(1, 3)) >= 0.5
    yy, xx = np.mgrid[-ROUND_PX:ROUND_PX + 1, -ROUND_PX:ROUND_PX + 1]
    disk = xx * xx + yy * yy <= ROUND_PX * ROUND_PX
    # edge-replicated padding: scipy morphology treats outside the array as 0, which eroded every opaque cell on the
    # page border (runs 20261114T132004Z / 132040Z: identical R2 1024 / R3 896 px, 18 pinhole cells; kept)
    p = ROUND_PX + 2
    mp = np.pad(mask, p, mode="edge")
    mask = binary_closing(binary_opening(mp, disk), disk)[p:-p, p:-p]
    return mask, polys


def proto_fill(lib, rgba):
    """R5 fill exactly as the frozen prototype (cm_fill_cutout_rgb), in place on a contiguous RGBA copy."""
    a = np.ascontiguousarray(rgba.copy())
    rc = lib.cm_fill_cutout_rgb(a.ctypes.data, a.shape[1], a.shape[0])
    assert rc >= 0, rc
    return a


def main():
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    nat_path = sorted((HERE / "native").glob("*/result.json"))[-1]
    nat = json.loads(nat_path.read_text(encoding="utf-8"))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "authored" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h"):
        shutil.copy2(p, rd / p.name)
    idx = np.array([[int(c, 16) for c in row] for row in nat["index_map_rows"]], np.uint8)
    th, tw = idx.shape
    H, W = th * S, tw * S
    pe = nat["palettes"][PALETTE]["entries"]
    cls_of = np.array([e["cls"] for e in pe], np.uint8)
    clut = np.array([e["rgb"] for e in pe], np.float32)            # (16, 3)
    ncls = cls_of[idx]
    # 0 the frozen prototype (R5 fill here, validation below)
    dll = rd / "class_mip.dll"
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(PROTO / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=600, creationflags=0x4000)
    assert c.returncode == 0, c.stderr
    lib = ctypes.CDLL(str(dll))
    lib.cm_fill_cutout_rgb.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.cm_fill_cutout_rgb.restype = ctypes.c_int64

    # 1 silhouette: native class boundary polygonized + corner-rounded; the Douglas-Peucker tolerance is the LARGEST of
    # TOL_SWEEP whose class mask passes the strict whole-cell rules (s/2) AND connectivity-only (every value recorded)
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    nc0 = np.ascontiguousarray(ncls)
    cy = (np.arange(th) * S + S // 2)[:, None]
    cx = (np.arange(tw) * S + S // 2)[None, :]

    def class_check(mask):
        a0 = np.zeros((H, W, 4), np.uint8)
        a0[..., 3] = np.where(mask, 127, 0)
        r = CmReport()
        lib.cm_validate(a0.ctypes.data, W, H, nc0.ctypes.data, tw, th, S, ctypes.byref(r))
        f0 = np.zeros((H, W), np.uint8)
        lib.cm_flags_ex(a0.ctypes.data, W, H, nc0.ctypes.data, tw, th, S, 1.0e9, 0, f0.ctypes.data)
        strict = dict(r1=r.r1_centre_bad, r2=r.r2_displaced_px, r3=r.r3_uniform_bad_px, r4=r.r4_island_px,
                      cells_bad=r.cells_bad)
        conn = int(((f0 & (2 | 4 | 16)) != 0).sum())
        return strict, conn
    sweep, chosen = [], None
    for tol in TOL_SWEEP:
        m_, p_ = polygon_silhouette(ncls != 0, H, W, tol)
        forced = int((m_[cy, cx] != (ncls != 0)).sum())
        m_[cy, cx] = ncls != 0
        st_, cn_ = class_check(m_)
        ok = all(v == 0 for v in st_.values()) and cn_ == 0
        sweep.append(dict(tol=tol, r1_forced=forced, strict=st_, conn_viol_px=cn_, passes=ok,
                          vertices=sum(len(q) for q in p_)))
        if ok and chosen is None:
            chosen = (tol, m_, p_, forced)
    assert chosen is not None, sweep
    dp_tol, opq, sil_polys, r1_forced = chosen

    # 2 fields. v4: the GREEN BODIES are hand-authored rounded rectangles (native texels) inside the silhouette; the
    # silhouette ring outside them is dark OUTLINE (as in the native, whose steps/nubs are outline cells 1/2/11).
    pad = np.pad(opq, 1)
    d_in = distance_transform_edt(pad)[1:-1, 1:-1].astype(np.float32) / S            # texels inside the silhouette
    X = (np.arange(W, dtype=np.float32)[None, :] + 0.5) / S         # native x of each pixel column
    X = np.broadcast_to(X, (H, W))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    PX, PY = xx + 0.5, yy + 0.5
    chev_zone = smoothstep(46.5, 47.2, X)                           # 0 = tiles, 1 = chevron (by x)

    def rrect(x0, y0, x1, y1, r):
        """signed inside distance (px, > 0 inside) of a rounded rectangle given in native texels"""
        cxm, cym = (x0 + x1) / 2 * S, (y0 + y1) / 2 * S
        hx, hy = (x1 - x0) / 2 * S - r * S, (y1 - y0) / 2 * S - r * S
        qx, qy = np.abs(PX - cxm) - hx, np.abs(PY - cym) - hy
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r * S
        return -d
    rect_in = np.max(np.stack([rrect(*TILES[k]) for k in TILES]), axis=0)
    db_px = np.minimum(rect_in, d_in * S - BODY_INSET * S)          # body = rect AND inset silhouette
    db_px = np.where(chev_zone >= 0.5, -1e3, db_px)
    body = np.clip(db_px + 0.5, 0, 1) * (1.0 - chev_zone)          # AA body coverage
    db = db_px / S                                                  # texels (> 0 inside the body)
    # v5: hand-authored chevron body = clean outer '>' polygon minus the clean hole triangle (native texels, derived
    # from the native mask rows, inset/expanded so the edges sit inside the inset silhouette), AND the inset
    # silhouette (class unchanged). 4x supersampled coverage; the ramp distance is measured inside this body.
    from PIL import ImageDraw
    SSC = 4
    im = Image.new("L", (W * SSC, H * SSC), 0)
    dr = ImageDraw.Draw(im)
    dr.polygon([(x * S * SSC - 0.5, y * S * SSC - 0.5) for x, y in CHEV_OUTER], fill=255)
    dr.polygon([(x * S * SSC - 0.5, y * S * SSC - 0.5) for x, y in CHEV_HOLE], fill=0)
    poly_cov = np.asarray(im, np.float32).reshape(H, SSC, W, SSC).mean(axis=(1, 3)) / 255.0
    sil_cov = np.clip(d_in * S - CHEV_INSET * S + 0.5, 0, 1)
    chev_body = np.minimum(poly_cov, sil_cov) * chev_zone
    dc = (distance_transform_edt(np.pad(chev_body >= 0.5, 1))[1:-1, 1:-1].astype(np.float32) - 0.5) / S
    dc = np.where(chev_body >= 0.5, dc, -(distance_transform_edt(np.pad(chev_body < 0.5, 1, constant_values=True))
                                          [1:-1, 1:-1].astype(np.float32) - 0.5) / S)
    sm = gaussian_filter(np.clip(db, -1.0, 3.0), 2.0)               # body normals (2 px smoothing)
    gy, gx = np.gradient(sm)
    gn = np.sqrt(gx * gx + gy * gy) + 1e-6
    lit = -((gx / gn) * LIGHT[0] + (gy / gn) * LIGHT[1])           # outward body normal . light: > 0 faces the light

    # 3 role weights over CLUT indices (convex mixes), painted bottom-up
    Wt = np.zeros((H, W, 16), np.float32)

    def paint(a, k):
        a = np.clip(a, 0, 1).astype(np.float32)
        Wt[...] *= (1.0 - a)[..., None]
        Wt[..., k] += a

    def paint_mix(a, k1, k2, t):
        a = np.clip(a, 0, 1).astype(np.float32)
        t = np.clip(t, 0, 1).astype(np.float32)
        Wt[...] *= (1.0 - a)[..., None]
        Wt[..., k1] += a * (1.0 - t)
        Wt[..., k2] += a * t

    # outline everywhere in the silhouette: 1 far from the body, 2 against it; teal (11/13) on R's left edge,
    # teal (11/10) toward / around the chevron (native b/a/d cells)
    ot = smoothstep(-0.6, -0.05, np.maximum(db, dc))
    teal_l = 1.0 - smoothstep(1.2, 2.2, X)
    teal_r = smoothstep(44.4, 46.0, X)
    plain = 1.0 - np.maximum(teal_l, teal_r)
    Wt[..., 1] = plain * (1 - ot)
    Wt[..., 2] = plain * ot
    Wt[..., 11] = (teal_l + teal_r) * (1 - ot)
    Wt[..., 13] = teal_l * ot
    Wt[..., 10] = teal_r * ot
    paint(body, 5)                                                  # tile bodies
    band = (1.0 - smoothstep(0.05, 0.95, db)) * body                # bevel band just inside the body edge
    paint(band * np.clip(-lit, 0, 1) * 0.5, 4)                      # shadow side (bottom right)
    hi = (smoothstep(0.03, 0.12, db) - smoothstep(0.25, 0.5, db)) * np.clip(lit, 0, 1) * body   # thin crisp highlight
    paint(hi * 0.75, 9)
    e_grad = smoothstep(42.0, 44.0, X) * body                       # E's right edge toward the chevron (native 9, 12)
    paint_mix(e_grad, 9, 12, smoothstep(44.0, 45.8, X))
    rl = (1.0 - smoothstep(1.9, 2.8, X)) * smoothstep(0.05, 0.3, db) * body   # R's left highlight column (native 7)
    paint(rl * 0.8, 7)

    # glyph grooves (engraved): lit lip 9 just outside the lower-right rim, floor 3, shadow wall 2, lit wall 5
    paths = [p for g in GLYPHS.values() for p in g]
    cov, gx_, gy_, tn = stroke_field(paths, H, W, SW)
    covw, wx_, wy_, _ = stroke_field(paths, H, W, SW + 0.32)        # 2.6 px wider on each side
    cov *= body
    lip = np.clip(covw * body - cov, 0, 1) * np.clip(-(wx_ * LIGHT[0] + wy_ * LIGHT[1]), 0, 1)
    paint(lip * 0.8, 9)
    wall = smoothstep(0.40, 0.92, tn)
    facing = gx_ * LIGHT[0] + gy_ * LIGHT[1]                        # >0: pixel on the light side of the centreline
    tgt = np.zeros((H, W, 16), np.float32)
    sh = wall * np.clip(facing, 0, 1)
    li = wall * np.clip(-facing, 0, 1)
    tgt[..., 3] = 1.0 - sh * 0.9 - li * 0.7
    tgt[..., 2] = sh * 0.9
    tgt[..., 5] = li * 0.7
    Wt[...] = Wt * (1.0 - cov)[..., None] + tgt * cov[..., None]

    # chevron body: native symmetric ramp from its edge 13 -> 12 -> 14 (its dark 11/10 rim is the outline above)
    ch = np.zeros((H, W, 16), np.float32)
    s2, s3 = smoothstep(0.0, 0.6, dc), smoothstep(0.6, 1.3, dc)
    ch[..., 13] = 1 - s2
    ch[..., 12] = s2 * (1 - s3)
    ch[..., 14] = s3
    Wt[...] = Wt * (1.0 - chev_body)[..., None] + ch * chev_body[..., None]

    Wt *= opq[..., None]
    Wt[..., 15] = (~opq).astype(np.float32)                         # cutout role (class 0)
    sums = Wt.sum(-1)
    assert np.allclose(sums, 1.0, atol=1e-4), float(np.abs(sums - 1).max())
    np.savez_compressed(rd / "role-weights.npz", weights=Wt.astype(np.float16), opaque=opq)

    # 4 colour for the reference palette; class alpha from the native class of the cutout role only
    rgb = np.tensordot(Wt[..., :15], clut[:15], axes=([2], [0]))
    rgb = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    alpha = np.where(opq, 127, 0).astype(np.uint8)
    assert set(np.unique(cls_of[:15])) == {127} and cls_of[15] == 0
    out = proto_fill(lib, np.dstack([rgb, alpha]).astype(np.uint8))   # R5 exactly as the prototype
    png = rd / f"authored-{PALETTE}.png"
    Image.fromarray(out).save(png)

    # 5 SVG source: silhouette (evenodd fill) + glyph centrelines (engraving strokes), HD pixel units
    sil = ["M" + " L".join(f"{x * S:.1f},{y * S:.1f}" for x, y in pts) + " Z" for pts in sil_polys]
    gl = []
    for p in paths:
        P = p["pts"] * S
        gl.append(f'  <path data-name="{p["name"]}" data-butt="{int(p["butt"][0])}{int(p["butt"][1])}" fill="none" '
                  f'stroke="#{int(clut[4][0]):02x}{int(clut[4][1]):02x}{int(clut[4][2]):02x}" stroke-width="{SW * S:.1f}" '
                  f'stroke-linejoin="round" d="M' + " L".join(f"{x:.2f},{y:.2f}" for x, y in P) + '"/>')
    body = "#%02x%02x%02x" % tuple(int(v) for v in clut[5])
    svg = rd / f"authored-{PALETTE}.svg"
    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
                   f'  <!-- RISE 82831823 authored hand-vector lettering v2 (claude-einhander). Silhouette = native class '
                   f'boundary polygons (Douglas-Peucker {dp_tol} texel; the raster also rounds corners by {ROUND_PX} px); '
                   f'glyph centrelines hand-authored in native texel units x{S}; shading = CLUT index roles '
                   f'(role-weights.npz). PRIVATE, not composed. -->\n'
                   f'  <path data-name="silhouette (class 127)" fill="{body}" fill-rule="evenodd" d="{" ".join(sil)}"/>\n'
                   + "\n".join(gl) + "\n</svg>\n", encoding="utf-8")

    # 6 validation (frozen proto-v2b) of the final RGBA
    a = np.ascontiguousarray(out)
    nc = np.ascontiguousarray(ncls)
    rep = CmReport()
    lib.cm_validate(a.ctypes.data, W, H, nc.ctypes.data, tw, th, S, ctypes.byref(rep))
    v2 = {f: getattr(rep, f) for f, _ in CmReport._fields_}
    fl = np.zeros((H, W), np.uint8)
    lib.cm_flags_ex(a.ctypes.data, W, H, nc.ctypes.data, tw, th, S, 1.0e9, 0, fl.ctypes.data)
    conn = dict(viol_px=int(((fl & (2 | 4 | 16)) != 0).sum()), r1=int(((fl & 16) != 0).sum()), r4=int(((fl & 4) != 0).sum()))

    # 7 review sheet: stock | authored world-v4 (old) | vector draft (rejected) | NEW | class diff
    bd = json.loads(BREAKDOWN.read_text(encoding="utf-8"))
    auth_png = next(r["png"] for r in bd["rows"]["pack"] if r["key"] == PALETTE)
    with Image.open(auth_png) as im:
        auth = np.asarray(im.convert("RGBA"))
    drafts = [HERE / "authored/20261114T132614Z" / f"authored-{PALETTE}.png"]   # authored v4
    with Image.open(drafts[-1]) as im:
        draft = np.asarray(im.convert("RGBA"))

    def show(x):
        yy, xx = np.indices(x.shape[:2])
        chk = np.where(((xx // 8 + yy // 8) % 2 == 0)[..., None], 200, 140).astype(np.uint8)
        return np.where(x[..., 3:4] != 0, x[..., :3], chk)
    stock = np.dstack([np.repeat(np.repeat(clut.astype(np.uint8)[idx], S, 0), S, 1), np.repeat(np.repeat(ncls, S, 0), S, 1)])
    C = np.repeat(np.repeat(ncls, S, 0), S, 1)
    diffc = (show(out) * 0.35).astype(np.uint8)
    diffc[(C != 0) & (alpha == 0)] = (255, 40, 40)
    diffc[(C == 0) & (alpha != 0)] = (40, 220, 255)
    gap = np.full((H, 8, 3), 255, np.uint8)
    top = np.concatenate([show(stock), gap, show(auth if auth.shape[:2] == (H, W) else
                                                 np.asarray(Image.fromarray(auth).resize((W, H), Image.LANCZOS)))], axis=1)
    bot = np.concatenate([show(draft), gap, show(out)], axis=1)
    sheet = np.concatenate([top, np.full((8, top.shape[1], 3), 255, np.uint8), bot], axis=0)
    rv = rd / f"review-{PALETTE}.png"
    Image.fromarray(sheet).save(rv)
    Image.fromarray(diffc).save(rd / f"classdiff-{PALETTE}.png")
    z = np.concatenate([show(stock)[96:432, 0:560], gap[:336], show(out)[96:432, 0:560]], axis=1)
    zoom = rd / f"zoom-{PALETTE}.png"
    Image.fromarray(z).resize((z.shape[1] * 2, z.shape[0] * 2), Image.NEAREST).save(zoom)
    z2 = np.concatenate([show(out)[96:432, 512:1024], gap[:336], show(stock)[96:432, 512:1024]], axis=1)
    Image.fromarray(z2).resize((z2.shape[1] * 2, z2.shape[0] * 2), Image.NEAREST).save(rd / f"zoom-right-{PALETTE}.png")
    res = dict(run=stamp, palette=PALETTE, native_source=str(nat_path), native_sha256=sha(nat_path), scale=S,
               silhouette=dict(method="native class boundary polygonized", dp_tolerance_texels=dp_tol,
                               corner_round_px=ROUND_PX, polygons=len(sil_polys), r1_forced_cell_centres=r1_forced,
                               tolerance_sweep=sweep),
               groove_width_texels=SW,
               glyph_paths=[dict(name=p["name"], points=len(p["pts"]), butt=p["butt"]) for p in paths],
               validation_v2_default=v2, validation_connectivity_only=conn,
               class_diff_vs_native_px=dict(native_opaque_now_cutout=int(((C != 0) & (alpha == 0)).sum()),
                                            native_cutout_now_opaque=int(((C == 0) & (alpha != 0)).sum())),
               review=dict(stock="native x16 (top left)", old_authored=str(auth_png) + " (top right)",
                           v4=str(drafts[-1]) + " (bottom left)", new="v5 + hand chevron (bottom right)"),
               chevron_outer=CHEV_OUTER, chevron_hole=CHEV_HOLE,
               tiles=TILES, body_inset_texels=BODY_INSET, chevron_inset_texels=CHEV_INSET,
               outputs={p.name: sha(p) for p in sorted(rd.iterdir()) if p.suffix in (".png", ".svg", ".npz")},
               status="PRIVATE AUTHORED v5, ONE palette; not composed; needs review before the other 32 palettes")
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "authored" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, v2=v2, conn=conn, result_sha256=sha(rd / "result.json"))) + "\n")
    print(json.dumps({k: res[k] for k in ("run", "silhouette", "validation_v2_default", "validation_connectivity_only",
                                          "class_diff_vs_native_px")}, indent=1))


if __name__ == "__main__":
    main()
