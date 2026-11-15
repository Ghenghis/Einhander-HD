#!/usr/bin/env python3
"""s45 (EIN-S4-WHOLE-CELL-20261114) diag_bands r3: FAIL-CLOSED, direction-aware two-key hazard-stripe preview.
SOURCE ONLY until a grant. r2 (df5dcc3a) ran once under grant msg_75ed6a3e and was VISUALLY REJECTED by root (msg_9a159f8b):
its generic 45-degree Scale2x donor boundary added a conspicuous stepped diagonal edge. r3 keeps r2's frame (version gate,
pins read once and the same bytes used, private verified DLL copy, class_mip audit, review crops, fail-closed receipts)
and replaces the repair core with a model of the ACTUAL stripe geometry of this ROI. EPX is no longer used or pinned.

Scope is fixed: Stage 4, keys E8769E55-8F297232 and 9B8107D2-8F297232 only; native ROI half-open [72,64,100,72] (pinned
index bytes ROI_SHA; byte-identical in both keys); stripe field BAND = [76,65,100,72] inside it (v64 = dark frame row,
u72-75 = the 7DD / 66CC fittings). Nothing is generic.

Model (native data only, before any image is touched):
  * orange coverage alpha of each CLUT colour = projection onto the orange(0x0) - dark(0xF) axis; per BAND texel:
    pure orange (alpha >= 0.9), pure dark (<= 0.2) or shade (between; e.g. 3/5/8/9/A);
  * per BAND row, every dark->orange (rising) / orange->dark (falling) transition gives a sub-texel edge position from the
    area of its shade texels (x = u_b - sum(alpha) rising, u_a + 1 + sum(alpha) falling), plus the interval in which the
    edge may sit at the row centre without moving any texel centre to the other side (margin 0.125 texel): pure
    texels by their colour, shade texels by their alpha majority (>= 0.5 orange). A shade texel inside a same-colour run
    (no transition) is rejected, never silently absorbed;
  * edges are linked row to row (same kind, nearest, <= 2.5 texels) into chains. A chain is 'straight' (vertical: integer
    median, >= 60 % of rows on it; rows off the median keep their native position, e.g. the bevelled corner),
    'family' (>= 3 rows; least-squares slope within 0.35 of the median slope of all non-straight chains: the real repeated
    stripe direction, ~ -0.54 texel/row here, NOT 45 degrees; its line is the straightest one, slope within that band,
    that stays inside the per-row native-centre intervals, ties -> slope nearest the shared direction) or 'native' (the
    measured per-row positions themselves). Each row-centre position is clamped into its interval; edges between row
    centres are linear between linked row positions (chain ends extend with the chain slope);
  * gates: every BAND index is a stripe-family index; no trailing / same-run / contradictory shade texels; edge order
    never crosses at any sample height. The alternation and centre-side checks are kept as defensive re-checks only: by
    construction (rows start dark; positions clamped) they cannot fail on their own.
Render (per export size S = 8 or 4):
  * coverage = 4x4 supersampled area of the model per output pixel (outside BAND = dark);
  * a pixel is re-rendered only if it is editable (inside BAND, or a pure-dark 0xF texel of the ROI; fittings and all other
    indices are PROTECTED), lies within 0.75 texel of a model edge and is not a texel-centre pixel (S/2, S/2);
  * colour = coverage * O + (1 - coverage) * D, O / D = the input's own colour at the nearest 'deep' pure-orange / pure-dark
    editable pixel (>= 0.75 texel from every edge) within 2.0 texels; otherwise the pixel stays unchanged (fallback);
  * the ROI's right (u100) and bottom (v72) sides cut through stripes that continue outside: over the last 0.5 texel the
    result is cross-faded back to the input; RGB only, alpha never written.
Gates (all fatal): pins + versions; IHDR; ROI native bytes == pin; ROI single-class; outside-ROI RGBA identical; alpha
identical; texel-centre pixels identical; non-target and protected pixels identical; cm_validate / cm_flags_ex rc 0,
primary (R1 == 0, conn-only == 0), s/2 strict, R5 == 0 (NOTE: class_mip classifies by alpha only and r3 never writes alpha,
so this audit re-checks class integrity of the copy; it does not judge the RGB repair). QUALITY (exit 5, evidence crops
native | input | r2 REJECTED | r3 still written, no art PNG): no donor fallback pixel outside the feather; along every
FAMILY edge (rows >= 1 texel from the band top/bottom, windows outside the feather and the band's left side) the edge
position per pixel row is measured by AREA (locally normalised orange-dark projection summed over a +-1 texel window;
unbiased for any area-sampled step) on input, the rejected r2 output (pinned) and r3: r3 RMS second difference
('staircase', px) must be <= input and < r2, and the r3 mean transition width must be < input. Straight / native chains,
the band top edge and the corner are covered by the fixtures, not by this metric.
--fixtures (pins are hash-checked; no DLL load, no page data): the ACTUAL ROI pattern (embedded, checked against ROI_SHA)
at S=8 and S=4 on a softened nearest render, a synthetic steep two-row and a shallow two-texel staircase (both with stripes
continuing past the ROI's right and bottom sides), straight vertical/horizontal edges (crisp input must stay
byte-identical), protected fittings, the top-left corner endpoint, and negatives that must fail WITH THE EXPECTED MESSAGE
(ROI out of bounds, scale 16, cross-class CLUT, edited CLUT via the real PAL CRC check, alpha change, foreign index in the
band, shade inside a same-colour run, a stepped r2-like output against the soft input). No 45-degree synthetic fixture is
used as evidence. Exit codes: 0 ok, 3 gate failure, 4 unexpected exception, 5 quality-gate failure.
Writes ONLY a new exclusive folder s45/repairs/<UTC>-diagbands-r3-<KEY|fixtures>/. Inputs are never modified."""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
import argparse  # noqa: E402
import ctypes  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import importlib.metadata  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import struct  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
import zlib  # noqa: E402
from pathlib import Path  # noqa: E402

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
ST4 = RA / "fullgame-prep/static-extraction/stages/stage4"
FZ = RA / "comfy-authoring/w7-stage4/frozen/s4-world-2-13-v3"
JW1 = S45 / "repairs/s4-world-ext-9B8107D2-v1-s45"
R2E = S45 / "repairs/20261114T215351Z-diagbands-r2-E8769E55-8F297232"
R2B = S45 / "repairs/20261114T215354Z-diagbands-r2-9B8107D2-8F297232"
PROTO = RA / "claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b"
ROI = (72, 64, 100, 72)
BAND = (76, 65, 100, 72)
FAMILY = (0x0, 0x1, 0x3, 0x5, 0x8, 0x9, 0xA, 0xC, 0xF)
DARK_EDITABLE = (0xF,)
A_O, A_D = 0.9, 0.2
MAX_MIXED = 2
LINK_MAX_TEX = 2.5
SLOPE_TOL = 0.35
STRAIGHT_FRAC = 0.6
CENTRE_MARGIN_TEX = 0.125
EDGE_BAND_TEX = 0.75
DONOR_MAX_TEX = 2.0
FEATHER_TEX = 0.5
SS = 4
PINS = dict(
    dll=(S45 / "probe-audit/20261114T171539Z-s4/class_mip.dll", "ede9a8f1d9847bb534f26d894bc15b2054fa4123aae12f82157cd1e4b5bf524e"),
    dll_c=(PROTO / "class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    dll_h=(PROTO / "class_mip.h", "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"),
    dll_c_copy=(S45 / "probe-audit/20261114T171539Z-s4/class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
)
CLUT_HEX = "1f12df15df11f239d6299a157811721d8c3113112a21cb10a7188610640c630c"   # 8F297232 at (208,493)
ROI_SHA = "fbd056b9edd7dd62560bd4c2899c077e55a2c29cb34af07151500f30850a1137"     # ROI native index bytes (both keys)
ROI_ROWS = ("FFFFFFFFFFFFFFFFFFFFFFFFFFFF", "FFFFC1000FFF0001FF103FF011FF", "7DDF50001FF1001FF100FFF009FF",
            "FFFF0001FFF001FFF001FF000FFF", "FFFF000FFF000AFF100FFF000FF0", "66CC000FFF000FF1001FF100FFF0",
            "FFFF00FFF1001FF0008FF000FF10", "FFFF01FF1000FF1000FF1001FF00")   # u72..99, v64..71 (== ROI_SHA)
KEYS = {
    "E8769E55-8F297232": dict(
        words=(ST4 / "textures/E8769E55.words.bin", "68df20c0abcc3a8c9f744f2d12fb7d12729620f61cab47f1e5c745a4c4f8167d"),
        png={2048: (FZ / "runtime-2048/E8769E55-8F297232.png", "42da302c43b6208f2fbdd228ed30816aefbc5aa1df9ac7760ea6bb5d1db15c38"),
             1024: (FZ / "runtime-1024/E8769E55-8F297232.png", "e85c2d87c6d2e9f21109819b21785506eb38702a17d975c92a095f7e27d71e81")},
        r2={2048: (R2E / "E8769E55-8F297232-2048-diagbands-r2.png", "f763f8bab78bdb95c0cbb6c238effa15524a0eab6c6686921a00ab11f1c8e4b3"),
            1024: (R2E / "E8769E55-8F297232-1024-diagbands-r2.png", "e4aa616c5bcd976bcbe5fa83e878007e36dde35e3664d7019993196f661b320b")}),
    "9B8107D2-8F297232": dict(
        words=(ST4 / "textures/9B8107D2.words.bin", "ac97a2970ebedc45ea049fe4209a1ccbf100efbc5f18879f171ad291ec645816"),
        png={2048: (JW1 / "runtime-2048/9B8107D2-8F297232.png", "ad3355a83c67f74b95389129ef20cac9884eab05877a3377ebdc59db9c88ae0a"),
             1024: (JW1 / "runtime-1024/9B8107D2-8F297232.png", "283077e52487b6e05baa233fec1f4e2aa9f1e7458ab416de328d73361e3784cd")},
        r2={2048: (R2B / "9B8107D2-8F297232-2048-diagbands-r2.png", "49b04ce509e468fd54e35ee8a46fbe9a0b1180b8630797a4efdb5a0442b85ae1"),
            1024: (R2B / "9B8107D2-8F297232-1024-diagbands-r2.png", "6e37e2163f55d920ad0b114275097134c67b03d137cb70e4a0b3d6e269882b04")}),
}
VERSIONS = dict(python="3.14.5", numpy="2.5.2", scipy="1.17.1", pillow="12.3.0")
RF = ("pixels", "cells", "r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px",
      "cells_bad", "pinhole_cells", "nonclass_px")


class Fail(Exception):
    pass


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def ihdr_size(b, name):
    need(b[:8] == b"\x89PNG\r\n\x1a\n" and b[12:16] == b"IHDR", f"not a PNG: {name}")
    return struct.unpack(">II", b[16:24])


def versions_ok():
    got = dict(python=sys.version.split()[0], numpy=importlib.metadata.version("numpy"),
               scipy=importlib.metadata.version("scipy"), pillow=importlib.metadata.version("pillow"))
    return got, got == VERSIONS


def classes(cw):
    import numpy as np
    return np.array([0 if v == 0 else (255 if v & 0x8000 else 127) for v in cw], np.uint8)


def clut_rgb(np, cw):
    return np.stack([(cw & 31) << 3, ((cw >> 5) & 31) << 3, ((cw >> 10) & 31) << 3], -1).astype(np.uint8)


def alpha_of(np, rgbc):
    """Orange coverage of each CLUT colour: projection onto the orange(0x0) - dark(0xF) axis, clipped to 0..1."""
    o, d = rgbc[0x0].astype(np.float64), rgbc[0xF].astype(np.float64)
    ax = o - d
    return np.clip(((rgbc.astype(np.float64) - d) @ ax) / float(ax @ ax), 0.0, 1.0)


# ---------------------------------------------------------------- native geometry model
def row_edges(al, u0):
    """al: orange coverage per texel of one BAND row (index 0 = column u0); left of the band is dark.
    Returns (edges in x order, trailing shade count). kind +1 = rising (dark->orange), -1 = falling."""
    typ = ["O" if a >= A_O else ("D" if a <= A_D else "M") for a in al]
    edges, mixed = [], []
    prev_t, prev_u = "D", u0 - 1
    for i, t in enumerate(typ):
        u = u0 + i
        if t == "M":
            mixed.append(float(al[i]))
            continue
        need(len(mixed) <= MAX_MIXED, f"more than {MAX_MIXED} shade texels between pure texels before u{u}")
        if t != prev_t:
            s = sum(mixed)
            kind = 1 if t == "O" else -1
            x = (u - s) if kind == 1 else (prev_u + 1 + s)
            lo, hi = prev_u + 0.5 + CENTRE_MARGIN_TEX, u + 0.5 - CENTRE_MARGIN_TEX
            for k, am in enumerate(mixed):            # a shade texel's centre stays on the side of its alpha majority
                cu = prev_u + 1 + k + 0.5
                if (kind == 1) == (am >= 0.5):        # its centre must lie right of the edge
                    hi = min(hi, cu - CENTRE_MARGIN_TEX)
                else:
                    lo = max(lo, cu + CENTRE_MARGIN_TEX)
            need(lo <= hi, f"contradictory shade texels before u{u}")
            edges.append(dict(kind=kind, x=float(x), u_a=prev_u, u_b=u, lo=lo, hi=hi))
        else:
            need(not mixed, f"shade texels inside a same-colour run before u{u}")
        prev_t, prev_u, mixed = t, u, []
    return edges, len(mixed)


def link(rows):
    """Link each edge to the nearest same-kind edge of the next row (<= LINK_MAX_TEX), greedy by distance, one-to-one."""
    for r in range(len(rows) - 1):
        cand = sorted((abs(f["x"] - e["x"]), i, j) for i, e in enumerate(rows[r]) for j, f in enumerate(rows[r + 1])
                      if e["kind"] == f["kind"] and abs(f["x"] - e["x"]) <= LINK_MAX_TEX)
        ui, uj = set(), set()
        for _, i, j in cand:
            if i in ui or j in uj:
                continue
            rows[r][i]["down"], rows[r + 1][j]["up"] = j, i
            ui.add(i)
            uj.add(j)


def fit(np, rows, bv0):
    """Chains, classification (straight / family / native), clamped row-centre positions xc. Returns (chains, family slope)."""
    chains = []
    for r, edges in enumerate(rows):
        for i, e in enumerate(edges):
            if "up" in e:
                continue
            ch, rr, ii = [], r, i
            while ii is not None:
                ch.append((rr, ii))
                ii, rr = rows[rr][ii].get("down"), rr + 1
            chains.append(ch)

    def pts(ch):
        return (np.array([bv0 + r + 0.5 for r, _ in ch]), np.array([rows[r][i]["x"] for r, i in ch]))

    straight = []
    for ch in chains:
        _, x = pts(ch)
        med = float(np.median(x))
        straight.append(len(ch) >= 3 and med == round(med) and float(np.mean(x == med)) >= STRAIGHT_FRAC)
    slopes = [float(np.polyfit(*pts(ch), 1)[0]) for ch, st in zip(chains, straight) if len(ch) >= 3 and not st]
    sf = float(np.median(slopes)) if slopes else None
    summary = []
    for c, (ch, st) in enumerate(zip(chains, straight)):
        y, x = pts(ch)
        lo = np.array([rows[r][i]["lo"] for r, i in ch])
        hi = np.array([rows[r][i]["hi"] for r, i in ch])
        if st:                                  # straight where the native is straight; native rows elsewhere (corners)
            med = float(np.median(x))
            kind, slope, model = "straight", 0.0, np.where(x == med, med, x)
        elif sf is not None and len(ch) >= 3 and abs(float(np.polyfit(y, x, 1)[0]) - sf) <= SLOPE_TOL:
            kind = "family"
            slope, off = best_line(np, y, x, lo, hi, sf)
            model = off + slope * y
        else:
            kind, slope, model = "native", None, x.copy()
        clamped = 0
        for k, (r, i) in enumerate(ch):
            e = rows[r][i]
            e["xc"] = float(min(max(float(model[k]), e["lo"]), e["hi"]))
            clamped += int(e["xc"] != float(model[k]))
            e["chain"], e["ckind"], e["slope"] = c, kind, slope
        summary.append(dict(chain=c, kind=kind, kind_edge="rising" if rows[ch[0][0]][ch[0][1]]["kind"] > 0 else "falling",
                            slope=None if slope is None else round(float(slope), 4),
                            rows=[bv0 + r for r, _ in ch], x=[round(float(v), 3) for v in x],
                            xc=[round(rows[r][i]["xc"], 3) for r, i in ch], clamped=clamped))
    return summary, sf


def best_line(np, y, x, lo, hi, sf):
    """Straightest line for one family chain: slope in sf +- SLOPE_TOL (0.005 steps). Minimises the total distance by which
    the line leaves the per-row native-centre intervals [lo, hi]; ties -> slope nearest the shared stripe direction sf,
    then the offset nearest the chain's own least-squares offset. Returns (slope, offset), x = offset + slope * y."""
    best = None
    for s in np.arange(sf - SLOPE_TOL, sf + SLOPE_TOL + 1e-9, 0.005):
        s = float(s)
        a, b = lo - s * y, hi - s * y                      # offset c must lie in [a_k, b_k] for row k
        ls = float(np.mean(x - s * y))
        if a.max() <= b.min():
            v, c = 0.0, min(max(ls, float(a.max())), float(b.min()))
        else:
            cands = np.concatenate([a, b])
            viol = [float(np.sum(np.maximum(0.0, a - q) + np.maximum(0.0, q - b))) for q in cands]
            k = int(np.argmin(viol))
            v, c = viol[k], float(cands[k])
        key = (round(v, 9), round(abs(s - sf), 9))
        if best is None or key < best[0]:
            best = (key, s, c)
    return best[1], best[2]


def edge_x(rows, r, e, Y, bv0):
    """Model edge position (texels) of edge e of band row r at height Y (texels) inside that row."""
    yc = bv0 + r + 0.5
    nb, nr = (e.get("down"), r + 1) if Y >= yc else (e.get("up"), r - 1)
    if nb is not None:
        return e["xc"] + (rows[nr][nb]["xc"] - e["xc"]) * abs(Y - yc)
    s = e["slope"]
    if s is None:                         # native chain end: slope of its other link, else vertical
        ob, orr = (e.get("up"), r - 1) if Y >= yc else (e.get("down"), r + 1)
        s = (e["xc"] - rows[orr][ob]["xc"]) / (yc - (bv0 + orr + 0.5)) if ob is not None else 0.0
    return e["xc"] + s * (Y - yc)


def build_model(np, idx, rgbc, band):
    bu0, bv0, bu1, bv1 = band
    bidx = idx[bv0:bv1, bu0:bu1]
    need(bool(np.isin(bidx, FAMILY).all()), "non-stripe index inside BAND")
    al = alpha_of(np, rgbc)[bidx]
    rows = []
    for r in range(bv1 - bv0):
        edges, trailing = row_edges(al[r].tolist(), bu0)
        need(trailing == 0, f"trailing shade texels in row v{bv0 + r}")
        need(all(e["kind"] == (1 if k % 2 == 0 else -1) for k, e in enumerate(edges)), f"edges do not alternate in row v{bv0 + r}")
        rows.append(edges)
    link(rows)
    chains, sf = fit(np, rows, bv0)
    mism = []
    for r, edges in enumerate(rows):
        xs = np.array([e["xc"] for e in edges])
        need(bool(np.all(np.diff(xs) > 0.05)), f"row-centre edge order crossing in row v{bv0 + r}")
        for i in range(bu1 - bu0):              # every texel centre (pure and shade) on its alpha-majority side
            a = al[r, i]
            inside = int(np.searchsorted(xs, bu0 + i + 0.5, side="right")) % 2 == 1
            if inside != (a >= 0.5):
                mism.append([bu0 + i, bv0 + r])
    need(not mism, f"model disagrees with native texel centres at {mism[:6]}")
    return dict(rows=rows, band=band, family_slope=sf, chains=chains, alpha=al)


def coverage(np, model, roi, S):
    """ROI-local per-pixel orange coverage of the model (SS x SS area samples); outside BAND = 0."""
    u0, v0, u1, v1 = roi
    rows, (bu0, bv0, bu1, bv1) = model["rows"], model["band"]
    H, W = (v1 - v0) * S, (u1 - u0) * S
    acc = np.zeros((H, W))
    offs = (np.arange(SS) + 0.5) / SS
    X = u0 + (np.arange(W)[:, None] + offs[None, :]).ravel() / S
    inx = (X >= bu0) & (X < bu1)
    for py in range(H):
        for oy in offs:
            Y = v0 + (py + oy) / S
            if not (bv0 <= Y < bv1):
                continue
            r = int(math.floor(Y)) - bv0
            xs = np.array([edge_x(rows, r, e, Y, bv0) for e in rows[r]])
            need(bool(np.all(np.diff(xs) > 0.05)), f"edge order crossing at y {Y:.4f}")
            o = (np.searchsorted(xs, X, side="right") % 2 == 1) & inx
            acc[py] += o.reshape(W, SS).sum(1)
    return acc / (SS * SS)


# ---------------------------------------------------------------- repair
def repair_roi(np, idx, img, S, rgbc, roi=ROI, band=BAND):
    """Returns (out, stats, model). Raises Fail on any gate."""
    from scipy import ndimage as ndi
    u0, v0, u1, v1 = roi
    bu0, bv0, bu1, bv1 = band
    need(0 <= u0 < u1 <= idx.shape[1] and 0 <= v0 < v1 <= idx.shape[0], f"ROI out of bounds {roi}")
    need(u0 <= bu0 < bu1 <= u1 and v0 <= bv0 < bv1 <= v1, f"BAND {band} not inside ROI {roi}")
    need(S in (4, 8), f"scale {S} not allowed")
    need(img.shape[:2] == (idx.shape[0] * S, idx.shape[1] * S), "image size != native size x scale")
    model = build_model(np, idx, rgbc, band)
    C = coverage(np, model, roi, S)
    old = img[v0 * S:v1 * S, u0 * S:u1 * S].copy()
    H, W = C.shape
    nat = np.repeat(np.repeat(idx[v0:v1, u0:u1], S, 0), S, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    inband = (yy >= (bv0 - v0) * S) & (yy < (bv1 - v0) * S) & (xx >= (bu0 - u0) * S) & (xx < (bu1 - u0) * S)
    editable = inband | np.isin(nat, DARK_EDITABLE)
    p1, p0 = C >= 1.0, C <= 0.0
    edge = ~(p1 | p0)
    for a, b in ((p1, p0), (p0, p1)):
        nb = np.zeros_like(a)
        nb[1:] |= b[:-1]
        nb[:-1] |= b[1:]
        nb[:, 1:] |= b[:, :-1]
        nb[:, :-1] |= b[:, 1:]
        edge |= a & nb
    need(bool(edge.any()), "model has no edge inside the ROI")
    dist = ndi.distance_transform_edt(~edge)
    centre = ((yy % S) == S // 2) & ((xx % S) == S // 2)
    near = dist < EDGE_BAND_TEX * S
    target = editable & near & ~centre
    deepO, deepD = editable & ~near & p1, editable & ~near & p0
    need(bool(deepO.any()) and bool(deepD.any()), "no deep donor pixels for one side")
    dO, (oy, ox) = ndi.distance_transform_edt(~deepO, return_indices=True)
    dD, (dy, dx) = ndi.distance_transform_edt(~deepD, return_indices=True)
    lim = DONOR_MAX_TEX * S
    ok = target & ((C <= 0) | (dO <= lim)) & ((C >= 1) | (dD <= lim))
    rgb = old[..., :3].astype(np.float64)
    blend = C[..., None] * rgb[oy, ox] + (1.0 - C[..., None]) * rgb[dy, dx]
    w = np.clip(np.minimum((W - xx - 0.5) / (FEATHER_TEX * S), (H - yy - 0.5) / (FEATHER_TEX * S)), 0.0, 1.0)
    val = rgb + w[..., None] * (blend - rgb)
    new = old.copy()
    new[..., :3][ok] = np.clip(np.rint(val[ok]), 0, 255).astype(np.uint8)
    need(np.array_equal(new[centre], old[centre]), "texel-centre pixel changed")
    need(np.array_equal(new[..., 3], old[..., 3]), "alpha changed inside ROI")
    need(np.array_equal(new[~target], old[~target]), "non-target pixel changed")
    need(np.array_equal(new[~editable], old[~editable]), "protected pixel changed")
    out = img.copy()
    out[v0 * S:v1 * S, u0 * S:u1 * S] = new
    used = np.concatenate([dO[ok & (C > 0)], dD[ok & (C < 1)]])
    cand_c = editable & near & centre
    model["oref"] = np.median(rgb[deepO], 0)
    model["dref"] = np.median(rgb[deepD], 0)
    stats = dict(changed_px=int((new != old).any(-1).sum()), target_px=int(target.sum()),
                 fallback_unchanged=int((target & ~ok).sum()),
                 fallback_outside_feather=int((target & ~ok & (w >= 1.0)).sum()), mixed_coverage_px=int((~(p1 | p0)).sum()),
                 donor_dist_px_max=round(float(used.max()), 2) if used.size else None,
                 donor_dist_px_mean=round(float(used.mean()), 2) if used.size else None,
                 protected_px_in_roi=int((~editable).sum()),
                 kept_centre_px_near_edges=int(cand_c.sum()),
                 kept_centre_dev_max=round(float(np.abs(val[cand_c] - rgb[cand_c]).max()), 1) if cand_c.any() else None,
                 family_slope_tex_per_row=None if model["family_slope"] is None else round(model["family_slope"], 4),
                 chains=model["chains"])
    return out, stats, model


# ---------------------------------------------------------------- quality metric
def stair_metrics(np, img, S, model, roi=ROI):
    """Along every family edge, per pixel row, in a +-1 texel window: t = orange-dark projection (model's input refs),
    normalised by the window's own dark / orange plateaus (S/4 px at each end); edge = window end - sum(t) (rising) or
    window start + sum(t) (falling), i.e. by area. stair_px = RMS 2nd difference of consecutive edge positions,
    resid_px = RMS(edge - model), width_px = mean count of pixels with 0.1 < t < 0.9. Rows < 1 texel from the band
    top/bottom and windows touching the band's left side or the feather zone are excluded."""
    u0, v0, u1, v1 = roi
    rows, (bu0, bv0, bu1, bv1) = model["rows"], model["band"]
    o, d = model["oref"], model["dref"]
    ax = o - d
    t = ((img[v0 * S:v1 * S, u0 * S:u1 * S, :3].astype(np.float64) - d) @ ax) / float(ax @ ax)
    H = t.shape[0]
    seq, widths, res, missing = {}, [], [], 0
    for py in range(H):
        Y = v0 + (py + 0.5) / S
        if not (bv0 + 1 <= Y < bv1 - 1):
            continue
        r = int(math.floor(Y)) - bv0
        for e in rows[r]:
            if e.get("ckind") != "family":
                continue
            xm = (edge_x(rows, r, e, Y, bv0) - u0) * S
            lo, hi = int(math.floor(xm - S)), int(math.ceil(xm + S))
            if lo < (bu0 - u0) * S or hi > (bu1 - u0 - FEATHER_TEX) * S - 1:
                continue
            seg = t[py, lo:hi]
            pl = max(2, S // 4)                     # plateau pixels at each window end, >= 0.75 texel from the edge
            dark_lv, org_lv = (seg[:pl].mean(), seg[-pl:].mean()) if e["kind"] > 0 else (seg[-pl:].mean(), seg[:pl].mean())
            if org_lv - dark_lv < 0.5:
                missing += 1
                seq.setdefault(e["chain"], []).append((py, None))
                continue
            un = np.clip((seg - dark_lv) / (org_lv - dark_lv), 0.0, 1.0)
            area = float(un.sum())                  # orange length in px; exact for any area-sampled step
            c = (hi - area) if e["kind"] > 0 else (lo + area)
            seq.setdefault(e["chain"], []).append((py, c))
            res.append(c - xm)
            widths.append(int(((un > 0.1) & (un < 0.9)).sum()))
    d2 = []
    for pts in seq.values():
        for (pa, a), (pb, b), (pc_, c) in zip(pts, pts[1:], pts[2:]):
            if None not in (a, b, c) and pb == pa + 1 and pc_ == pb + 1:
                d2.append(c - 2 * b + a)

    def rms(v):
        return round(float(np.sqrt(np.mean(np.square(v)))), 4) if len(v) else None
    return dict(stair_px=rms(d2), resid_px=rms(res), width_px=round(float(np.mean(widths)), 3) if widths else None,
                samples=len(res), missing=missing, d2_n=len(d2))


def quality_gate(q_out, q_in, q_ref, fallback_outside_feather=0):
    need(fallback_outside_feather == 0, f"{fallback_outside_feather} target px left unchanged (no donor) outside the feather")
    need(q_out["samples"] >= 20 and q_out["stair_px"] is not None, "too few quality samples on the output")
    need(q_out["missing"] <= max(2, q_out["samples"] // 20), "edge crossings missing on the output")
    need(q_in["stair_px"] is not None and q_out["stair_px"] <= q_in["stair_px"], "output staircase not <= input")
    need(q_in["width_px"] is not None and q_out["width_px"] < q_in["width_px"], "output edge not sharper than input")
    need(q_ref["stair_px"] is not None and q_out["stair_px"] < q_ref["stair_px"], "output staircase not < stepped reference")


def write_receipt(rd, rec, name="receipt.json"):
    (rd / name).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- fixtures
def clut_check(cw, key):
    need(zlib.crc32(cw.tobytes()) & 0xFFFFFFFF == int(key[9:], 16), "CLUT words CRC != PAL")


def fixtures(rd, np):
    from scipy import ndimage as ndi
    res = []
    cw = np.frombuffer(bytes.fromhex(CLUT_HEX), "<u2")
    rgbc = clut_rgb(np, cw)

    def case(name, fn, expect_msg=None):
        """expect_msg None: must pass. Otherwise must raise Fail whose message contains expect_msg."""
        try:
            info = fn()
            res.append(dict(name=name, expect_fail=expect_msg is not None, failed=False, ok=expect_msg is None,
                            info=info if isinstance(info, dict) else None))
        except Fail as e:
            res.append(dict(name=name, expect_fail=expect_msg is not None, failed=True, msg=str(e),
                            ok=expect_msg is not None and expect_msg in str(e)))

    def render(idx, S, soft):
        img = np.zeros((idx.shape[0] * S, idx.shape[1] * S, 4), np.uint8)
        rgb = np.repeat(np.repeat(rgbc[idx], S, 0), S, 1).astype(np.float64)
        if soft:
            rgb = ndi.uniform_filter(rgb, size=(S, S, 1), mode="nearest")
        img[..., :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
        img[..., 3] = 127
        return img
    froi, fband = (4, 4, 32, 12), (8, 5, 32, 12)          # fixture page 40 x 16: same ROI/BAND layout as the real ROI

    def page():
        return np.full((16, 40), 0xF, np.uint8)

    def actual():
        a = np.array([[int(c, 16) for c in row] for row in ROI_ROWS], np.uint8)
        need(hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest() == ROI_SHA, "embedded ROI pattern != ROI_SHA")
        p = page()
        p[4:12, 4:32] = a
        return p

    def stripes(fn):
        """Synthetic stripes in the band rows that CONTINUE past the ROI's right side and below its bottom side."""
        p = page()
        for r in range(11):
            for x in range(8, 40):
                p[5 + r, x] = 0x0 if fn(r, x - 8) else 0xF
        return p

    def run_quality(idx, S):
        soft, crisp = render(idx, S, True), render(idx, S, False)
        out, st, m = repair_roi(np, idx, soft, S, rgbc, froi, fband)
        need(np.array_equal(out[..., 3], soft[..., 3]), "alpha changed")
        mask = np.zeros(out.shape[:2], bool)
        mask[froi[1] * S:froi[3] * S, froi[0] * S:froi[2] * S] = True
        need(np.array_equal(out[~mask], soft[~mask]), "outside ROI changed")
        q = dict(input=stair_metrics(np, soft, S, m, froi), stepped=stair_metrics(np, crisp, S, m, froi),
                 r3=stair_metrics(np, out, S, m, froi))
        quality_gate(q["r3"], q["input"], q["stepped"])
        need(q["r3"]["stair_px"] < 0.5 * q["stepped"]["stair_px"], "r3 staircase not < half of the stepped render")
        return out, soft, st, m, q

    def p_actual(S):
        def f():
            idx = actual()
            out, soft, st, m, q = run_quality(idx, S)
            need(m["family_slope"] is not None and -0.9 <= m["family_slope"] <= -0.3,
                 f"actual family slope {m['family_slope']} not the real ~-0.54 direction")
            need(st["changed_px"] > 0, "no change on the actual pattern")
            need(st["fallback_outside_feather"] == 0, f"{st['fallback_outside_feather']} fallback px outside the feather")
            return dict(family_slope=m["family_slope"], quality=q, changed_px=st["changed_px"],
                        fallback=st["fallback_unchanged"], kept_centre_dev_max=st["kept_centre_dev_max"],
                        kinds=sorted({c["kind"] for c in m["chains"]}), chains=m["chains"])
        return f
    case("positive: ACTUAL ROI stripe pattern (ROI_SHA) at S=8, soft input: real direction, centres, quality", p_actual(8))
    case("positive: ACTUAL ROI stripe pattern (ROI_SHA) at S=4, soft input: real direction, centres, quality", p_actual(4))

    def p_fittings():
        idx = actual()
        S = 8
        soft = render(idx, S, True)
        out, _, _ = repair_roi(np, idx, soft, S, rgbc, froi, fband)
        for (u, v) in [(4, 6), (5, 6), (6, 6), (4, 9), (5, 9), (6, 9), (7, 9)]:   # 7DD / 66CC fittings (real u72-75)
            need(np.array_equal(out[v * S:(v + 1) * S, u * S:(u + 1) * S], soft[v * S:(v + 1) * S, u * S:(u + 1) * S]),
                 f"protected fitting texel ({u},{v}) changed")
        return dict(checked=7)
    case("positive: protected 7DD / 66CC fittings of the actual ROI unchanged", p_fittings)

    def p_corner():
        idx = actual()
        S = 8
        m = build_model(np, idx, rgbc, fband)
        C = coverage(np, m, froi, S)
        need(float(C[:S].max()) == 0.0, "orange coverage leaks into the frame row above the band")
        y0, x0 = (5 - 4) * S, (8 - 4) * S                # top-left corner texel (real u76 v65, index C, alpha .148)
        cov = float(C[y0:y0 + S, x0:x0 + S].mean())
        need(cov <= 0.25, f"corner texel renders {cov:.3f} orange (native alpha .148)")
        need(float(C[y0 + S // 2, x0 + S // 2]) == 0.0, "corner texel centre pixel not dark")
        return dict(corner_texel_coverage=round(cov, 4))
    case("positive: top-left corner endpoint (index C) stays mostly dark; no leak above the band", p_corner)

    def p_steep():
        idx = stripes(lambda r, x: (x + r // 2) % 6 < 3)
        _, _, st, m, q = run_quality(idx, 8)
        need(m["family_slope"] is not None and abs(m["family_slope"] + 0.5) <= 0.1, f"steep slope {m['family_slope']} != -0.5")
        return dict(family_slope=m["family_slope"], quality=q, fallback=st["fallback_unchanged"],
                    fallback_outside_feather=st["fallback_outside_feather"])
    case("positive: steep two-row staircase (1 texel per 2 rows), stripes continue outside: slope -0.5, quality", p_steep)

    def p_shallow():
        idx = stripes(lambda r, x: (x + 2 * r) % 8 < 4)
        _, _, st, m, q = run_quality(idx, 8)
        need(m["family_slope"] is not None and abs(m["family_slope"] + 2.0) <= 0.1, f"shallow slope {m['family_slope']} != -2")
        return dict(family_slope=m["family_slope"], quality=q, fallback=st["fallback_unchanged"],
                    fallback_outside_feather=st["fallback_outside_feather"])
    case("positive: shallow staircase (2 texels per row), stripes continue outside: slope -2, quality", p_shallow)

    def p_straight(S):
        def f():
            idx = stripes(lambda r, x: x % 6 < 3)
            crisp = render(idx, S, False)
            out, st, m = repair_roi(np, idx, crisp, S, rgbc, froi, fband)
            need(all(c["kind"] == "straight" for c in m["chains"]), "vertical edges not classified straight")
            need(np.array_equal(out, crisp), f"crisp straight vertical/horizontal edges changed ({st['changed_px']} px)")
            return dict(chains=len(m["chains"]))
        return f
    case("positive: straight vertical + horizontal edges, crisp input byte-identical (S=8)", p_straight(8))
    case("positive: straight vertical + horizontal edges, crisp input byte-identical (S=4)", p_straight(4))

    base = actual()
    soft8 = render(base, 8, True)

    def neg_oob():
        repair_roi(np, base, soft8, 8, rgbc, (30, 4, 44, 12), (31, 5, 44, 12))
    case("negative: ROI out of bounds", neg_oob, "ROI out of bounds")

    def neg_scale():
        repair_roi(np, base, np.zeros((256, 640, 4), np.uint8), 16, rgbc, froi, fband)
    case("negative: scale 16 not allowed", neg_scale, "scale 16 not allowed")

    def neg_crossclass():
        cw2 = cw.copy()
        cw2[0] = 0
        need(len(set(classes(cw2)[np.unique(base[4:12, 4:32])].tolist())) == 1, "ROI not single-class under the CLUT")
    case("negative: cross-class ROI (edited CLUT) rejected", neg_crossclass, "ROI not single-class")

    def neg_wrong_clut():
        cw2 = cw.copy()
        cw2[0] ^= 1                            # one bit of the pinned 8F297232 words
        clut_check(cw2, "E8769E55-8F297232")   # the same check main() applies before any decode
    case("negative: edited CLUT words rejected by the PAL CRC check", neg_wrong_clut, "CLUT words CRC != PAL")

    def neg_alpha():
        out, _, _ = repair_roi(np, base, soft8, 8, rgbc, froi, fband)
        out[60, 70, 3] = 255
        need(np.array_equal(out[..., 3], soft8[..., 3]), "alpha changed")
    case("negative: alpha change detected", neg_alpha, "alpha changed")

    def neg_foreign():
        b2 = base.copy()
        b2[8, 20] = 0x6                     # a fitting index inside the stripe band
        repair_roi(np, b2, render(b2, 8, True), 8, rgbc, froi, fband)
    case("negative: foreign (fitting) index inside the stripe band rejected", neg_foreign, "non-stripe index inside BAND")

    def neg_same_run_shade():
        b2 = base.copy()
        b2[8, 27] = 0x3                     # real (u95,v68) is orange inside an orange run: a shade there has no edge
        repair_roi(np, b2, render(b2, 8, True), 8, rgbc, froi, fband)
    case("negative: shade texel inside a same-colour run rejected", neg_same_run_shade, "shade texels inside a same-colour run")

    def neg_stepped():
        _, _, m = repair_roi(np, base, soft8, 8, rgbc, froi, fband)
        qs = stair_metrics(np, render(base, 8, False), 8, m, froi)
        qi = stair_metrics(np, soft8, 8, m, froi)
        quality_gate(qs, qi, qi)            # a stepped (r2-like) result must fail against the soft input
    case("negative: stepped r2-like output fails the quality gate", neg_stepped, "output staircase not <= input")
    allok = all(r["ok"] for r in res)
    write_receipt(rd, dict(mode="fixtures", cases=res, all_ok=allok), "fixtures-receipt.json")
    for r in res:
        print("FIXTURE", "OK " if r["ok"] else "BAD", r["name"], r.get("msg", ""), flush=True)
    if not allok:
        raise Fail("fixture mismatch")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--key", choices=sorted(KEYS))
    g.add_argument("--fixtures", action="store_true")
    a = ap.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "repairs" / f"{stamp}-diagbands-r3-{a.key or 'fixtures'}"
    rd.mkdir(parents=True, exist_ok=False)
    rec = dict(run=stamp, owner="claude-einhander-s45", tool_sha256=sha(Path(__file__)), mode=a.key or "fixtures",
               roi_half_open=list(ROI), band_half_open=list(BAND), params=dict(
                   a_o=A_O, a_d=A_D, link_max_tex=LINK_MAX_TEX, slope_tol=SLOPE_TOL, straight_frac=STRAIGHT_FRAC,
                   centre_margin_tex=CENTRE_MARGIN_TEX, edge_band_tex=EDGE_BAND_TEX, donor_max_tex=DONOR_MAX_TEX,
                   feather_tex=FEATHER_TEX, supersample=SS), status="STARTED", stage_reached="pins")
    write_receipt(rd, rec)
    try:
        vers, vok = versions_ok()
        rec["versions"] = vers
        need(vok, f"library versions {vers} != pinned {VERSIONS}")
        pins = dict(PINS)
        if a.key:
            pins["words"] = KEYS[a.key]["words"]
            for s_, v in KEYS[a.key]["png"].items():
                pins[f"png_{s_}"] = v
            for s_, v in KEYS[a.key]["r2"].items():
                pins[f"r2_{s_}"] = v
        got, blob = {}, {}
        for name, (p, want) in pins.items():
            b = Path(p).read_bytes()
            h = hashlib.sha256(b).hexdigest()
            got[name] = dict(path=str(p), sha256=h, ok=h == want)
            blob[name] = b
        rec["pins"] = got
        need(all(v["ok"] for v in got.values()), "pin mismatch: " + ", ".join(k for k, v in got.items() if not v["ok"]))
        rec["stage_reached"] = "imports"
        import numpy as np
        if a.fixtures:
            rec["stage_reached"] = "fixtures"
            fixtures(rd, np)
            rec["status"] = "FIXTURES OK"
            write_receipt(rd, rec)
            return 0
        dll_copy = rd / "class_mip.dll"
        dll_copy.write_bytes(blob["dll"])
        need(sha(dll_copy) == PINS["dll"][1], "private DLL copy hash mismatch")
        lib = ctypes.CDLL(str(dll_copy))
        for fn, args in (("cm_validate", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_void_p]),
                         ("cm_flags_ex", [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p])):
            getattr(lib, fn).argtypes = args
            getattr(lib, fn).restype = ctypes.c_int

        class CmReport(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in RF]
        rec["stage_reached"] = "sources"
        wb = blob["words"]
        need(zlib.crc32(wb) & 0xFFFFFFFF == int(a.key[:8], 16), "words CRC != TEX")
        w = np.frombuffer(wb, "<u2")
        need(w.size == 256 * 64, "words are not a 4bpp 256x256 page")
        idx = np.stack([(w.reshape(256, 64) >> s) & 15 for s in (0, 4, 8, 12)], -1).reshape(256, 256).astype(np.uint8)
        cw = np.frombuffer(bytes.fromhex(CLUT_HEX), "<u2")
        clut_check(cw, a.key)
        cls = classes(cw)
        rgbc = clut_rgb(np, cw)
        u0, v0, u1, v1 = ROI
        need(hashlib.sha256(np.ascontiguousarray(idx[v0:v1, u0:u1]).tobytes()).hexdigest() == ROI_SHA, "ROI native indices != pin")
        need(len(set(cls[np.unique(idx[v0:v1, u0:u1])].tolist())) == 1, "ROI not single-class under the CLUT")
        ncls = np.ascontiguousarray(cls[idx])
        from PIL import Image

        def decode(name, size):
            pb = blob[name]
            need(ihdr_size(pb, name) == (size, size), f"IHDR of {name} is not {size}x{size}")
            with Image.open(io.BytesIO(pb)) as im:
                arr = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
            need(arr.shape == (size, size, 4), f"decoded shape mismatch {name}")
            return arr
        outs, qfail = {}, []
        rec["files"] = {}
        for size in (2048, 1024):
            rec["stage_reached"] = f"decode {size}"
            src, r2img = decode(f"png_{size}", size), decode(f"r2_{size}", size)
            S = size // 256
            rec["stage_reached"] = f"repair {size}"
            out, st, model = repair_roi(np, idx, src, S, rgbc)
            mask = np.zeros((size, size), bool)
            mask[v0 * S:v1 * S, u0 * S:u1 * S] = True
            need(np.array_equal(out[~mask], src[~mask]), "outside-ROI RGBA changed")
            need(np.array_equal(out[..., 3], src[..., 3]), "alpha changed")
            rec["stage_reached"] = f"audit {size}"
            o = np.ascontiguousarray(out)
            rep = CmReport()
            rc = lib.cm_validate(o.ctypes.data, size, size, ncls.ctypes.data, 256, 256, S, ctypes.byref(rep))
            need(rc == 0, f"cm_validate rc {rc}")
            aud = {n: int(getattr(rep, n)) for n in RF}
            for nm, bound in (("s2_viol_px", 0.5), ("conn_viol_px", 1.0e9)):
                fl = np.zeros((size, size), np.uint8)
                rc = lib.cm_flags_ex(o.ctypes.data, size, size, ncls.ctypes.data, 256, 256, S, bound, 0, fl.ctypes.data)
                need(rc == 0, f"cm_flags_ex({bound}) rc {rc}")
                aud[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
            q = dict(input=stair_metrics(np, src, S, model), r2_rejected=stair_metrics(np, r2img, S, model),
                     r3=stair_metrics(np, out, S, model))
            rec["files"][str(size)] = dict(input=KEYS[a.key]["png"][size][0].as_posix(), stats=st, audit=aud, quality=q)
            need(aud["r1_centre_bad"] == 0 and aud["conn_viol_px"] == 0, "primary policy fails")
            need(all(aud[x] == 0 for x in ("r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "s2_viol_px")), "s/2 strict fails")
            need(aud["r5_fringe_px"] == 0, "R5 fringe > 0")
            need(st["changed_px"] > 0, "no pixel changed in the ROI")
            rec["stage_reached"] = f"quality {size}"
            try:
                quality_gate(q["r3"], q["input"], q["r2_rejected"], st["fallback_outside_feather"])
            except Fail as e:                 # evidence crops are still written below; no art PNG; exit 3
                qfail.append(f"{size}: {e}")
            outs[size] = (out, src, r2img, S)
        rec["stage_reached"] = "write"
        from PIL import ImageDraw
        (rd / "review").mkdir()
        for size, (out, src, r2img, S) in outs.items():
            if not qfail:
                fn = rd / f"{a.key}-{size}-diagbands-r3.png"
                Image.fromarray(out).save(fn, compress_level=6)
                rec["files"][str(size)]["output"] = fn.name
                rec["files"][str(size)]["output_sha256"] = sha(fn)
            zoom = 16 // S
            tw, th = (u1 - u0) * 16, (v1 - v0) * 16

            def crop(im):
                return np.repeat(np.repeat(im[v0 * S:v1 * S, u0 * S:u1 * S, :3], zoom, 0), zoom, 1)
            tiles = [("native nearest", np.repeat(np.repeat(rgbc[idx[v0:v1, u0:u1]], 16, 0), 16, 1)),
                     (f"input {size}", crop(src)), (f"r2 {size} (REJECTED)", crop(r2img)), (f"diag_bands r3 {size}", crop(out))]
            sheet = Image.new("RGB", (tw, len(tiles) * (th + 16)), (0, 0, 0))
            dr = ImageDraw.Draw(sheet)
            for j, (lab_, t) in enumerate(tiles):
                y = j * (th + 16)
                sheet.paste(Image.fromarray(np.ascontiguousarray(t)), (0, y + 16))
                dr.text((2, y + 2), f"{lab_}  {a.key}  ROI u{u0}-{u1 - 1} v{v0}-{v1 - 1}  16 px/texel", fill=(255, 255, 0))
            rv = rd / "review" / f"{a.key}-{size}-roi.png"
            sheet.save(rv)
            rec["files"][str(size)]["review"] = dict(path=rv.relative_to(rd).as_posix(), sha256=sha(rv))
        if qfail:
            rec["status"] = "FAILED (quality gate); evidence crops only, no art written"
            rec["reason"] = "; ".join(qfail)
            write_receipt(rd, rec)
            print("FAILED (quality):", rec["reason"], flush=True)
            return 5
        rec["status"] = ("OK: candidate preview (copies); native-class audit + quality gate passed; NOT a look acceptance; "
                         "not installed, not admitted")
        write_receipt(rd, rec)
        print(json.dumps({k: v["quality"] for k, v in rec["files"].items()}), flush=True)
        return 0
    except Fail as e:
        rec["status"] = "FAILED"
        rec["reason"] = str(e)
        write_receipt(rd, rec)
        print("FAILED:", e, "at", rec["stage_reached"], flush=True)
        return 3
    except Exception as e:  # noqa: BLE001  any unexpected error also finalises a FAILED receipt
        rec["status"] = "FAILED (unexpected exception)"
        rec["reason"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-4000:]
        write_receipt(rd, rec)
        print("FAILED (unexpected):", type(e).__name__, e, "at", rec["stage_reached"], flush=True)
        return 4


if __name__ == "__main__":
    sys.exit(main())
