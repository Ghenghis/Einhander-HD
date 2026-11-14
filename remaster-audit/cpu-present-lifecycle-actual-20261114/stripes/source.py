#!/usr/bin/env python3
"""s45 (EIN-S45-STRIPE-R3-SOURCE-20261114) diag_bands r4: FAIL-CLOSED, direction-aware two-key hazard-stripe preview.
SOURCE ONLY until a grant. r4 = r3 (76adfdc7; --fixtures ran once 22:38Z, 16/16 OK, receipt 681e255c) + root decisions
msg_2616783f / msg_31d576f5 + the quality controls root asked for (msg_e0a919f8):
  * CENTRE POLICY (option b, an explicit, intended exception to r2/r3's "texel-centre pixel RGB byte-identical" rule): a
    texel-centre pixel (S/2, S/2) inside the authorised edge band takes the RGB of the nearest deep donor on ITS native
    alpha-majority side, same class, <= 2 texels, cross-faded like every other pixel in the feather; never a cross-side
    blend; alpha never written. Every changed centre is logged (old/new RGBA, native index, side, donor, distance) and
    re-verified; the r3 rule's own outcome is reported unchanged beside it (centre_byte_exact_r3_rule). r3 measured why:
    kept blurred centres deviated up to 73.5 (S=8) / 147.9 (S=4) from their re-rendered neighbourhood (dots);
  * centre-PIXEL feasibility: the per-row edge interval now keeps every texel's whole centre pixel (a 0.25-texel square
    below-right of the centre point at S=4, which also covers S=8's) on its native side for the chain's slope, so a
    re-rendered centre is never cut by the edge (no notch); measured as centre_side_dev (gate <= 0.25);
  * edges between row centres follow a Catmull-Rom spline through the clamped row-centre positions (r3: linear), so a
    native bend is spread over the row instead of one pixel row;
  * quality is gated PER CHAIN (no chain's staircase may exceed max(its input, 0.15 px); continuity: |step - model step|
    <= 0.75 px; 0 missing) for family, straight and native chains, plus the aggregate (<= input, < r2 / stepped, width
    < input), the band's top BORDER (per-column area position: |resid| <= 0.5 px, staircase <= max(input, 0.15)), the
    CORNER texel (mean orange-dark projection within 0.25 of native alpha) and DOT contrast at every edge-band texel
    centre (unexplained local contrast <= 0.25; a kept-blurred-centre output must fail it);
  * new negative fixtures: wrong-side donor, cross-class donor, protected-pixel, outside-band centre and outside-ROI
    mutations, and r3-style kept centres failing the dot gate.
Where this paragraph differs from the r3 text below, r4 governs. Output folder: s45/repairs/<UTC>-diagbands-r4-<KEY|fixtures>/.
--- r3 docstring (design base) ---
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
Writes ONLY a new exclusive folder s45/repairs/<UTC>-diagbands-r4-<KEY|fixtures>/. Inputs are never modified."""
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
CENTRE_MARGIN_TEX = 0.02          # r4: epsilon only; the centre-PIXEL rule below is the real margin
PIX_TEX = 0.25                    # centre pixel extent at S=4 (covers S=8's 0.125)
EDGE_BAND_TEX = 0.75
DONOR_MAX_TEX = 2.0
FEATHER_TEX = 0.5
SS = 4
STAIR_FLOOR_PX = 0.15
CONT_MAX_PX = 0.75
DOT_MAX = 0.25
CENTRE_SIDE_DEV_MAX = 0.25
BORDER_RESID_MAX_PX = 0.5
CORNER_TOL = 0.25
CENTRE_POLICY = "option (b): same-side same-class bounded donor RGB at edge-band texel centres (msg_2616783f, msg_31d576f5)"
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
            left_u, right_u = prev_u, u               # texels whose centre pixel must stay left / right of the edge
            for k, am in enumerate(mixed):            # a shade texel stays on the side of its alpha majority
                um = prev_u + 1 + k
                if (kind == 1) == (am >= 0.5):
                    right_u = min(right_u, um)
                else:
                    left_u = max(left_u, um)
            need(left_u < right_u, f"contradictory shade texels before u{u}")
            e = dict(kind=kind, x=float(x), u_a=prev_u, u_b=u, left_u=left_u, right_u=right_u)
            e["lo"], e["hi"] = interval(e, 0.0)
            edges.append(e)
        else:
            need(not mixed, f"shade texels inside a same-colour run before u{u}")
        prev_t, prev_u, mixed = t, u, []
    return edges, len(mixed)


def interval(e, s):
    """Row-centre edge positions keeping the whole centre pixel [u+.5, u+.5+PIX_TEX] x [v+.5, v+.5+PIX_TEX] of the last
    'left' texel left of the edge and of the first 'right' texel right of it, for an edge of slope s (texel x per row)."""
    lo = e["left_u"] + 0.5 + PIX_TEX + max(0.0, -s * PIX_TEX) + CENTRE_MARGIN_TEX
    hi = e["right_u"] + 0.5 - max(0.0, s * PIX_TEX) - CENTRE_MARGIN_TEX
    return lo, hi


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
        es = [rows[r][i] for r, i in ch]
        if st:                                  # straight where the native is straight; native rows elsewhere (corners)
            med = float(np.median(x))
            kind, slope, model = "straight", 0.0, np.where(x == med, med, x)
        elif sf is not None and len(ch) >= 3 and abs(float(np.polyfit(y, x, 1)[0]) - sf) <= SLOPE_TOL:
            kind = "family"
            slope, off = best_line(np, y, x, es, sf)
            model = off + slope * y
        else:
            kind, slope, model = "native", None, x.copy()
        clamped = 0
        for k, (r, i) in enumerate(ch):
            e = rows[r][i]
            lo_k, hi_k = interval(e, slope if slope is not None else 0.0)
            need(lo_k <= hi_k, f"no feasible centre-pixel edge position in row v{bv0 + r}")
            e["lo"], e["hi"] = lo_k, hi_k
            e["xc"] = float(min(max(float(model[k]), lo_k), hi_k))
            clamped += int(e["xc"] != float(model[k]))
            e["chain"], e["ckind"], e["slope"] = c, kind, slope
        summary.append(dict(chain=c, kind=kind, kind_edge="rising" if rows[ch[0][0]][ch[0][1]]["kind"] > 0 else "falling",
                            slope=None if slope is None else round(float(slope), 4),
                            rows=[bv0 + r for r, _ in ch], x=[round(float(v), 3) for v in x],
                            xc=[round(rows[r][i]["xc"], 3) for r, i in ch], clamped=clamped))
    return summary, sf


def best_line(np, y, x, es, sf):
    """Straightest line for one family chain: slope in sf +- SLOPE_TOL (0.005 steps). Minimises the total distance by which
    the line leaves the per-row native-centre intervals [lo, hi]; ties -> slope nearest the shared stripe direction sf,
    then the offset nearest the chain's own least-squares offset. Returns (slope, offset), x = offset + slope * y."""
    best = None
    for s in np.arange(sf - SLOPE_TOL, sf + SLOPE_TOL + 1e-9, 0.005):
        s = float(s)
        lh = np.array([interval(e, s) for e in es])
        if (lh[:, 0] > lh[:, 1]).any():
            continue
        lo, hi = lh[:, 0], lh[:, 1]
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
    need(best is not None, "no feasible slope for a family chain")
    return best[1], best[2]


def chain_x(rows, r, e, k):
    """xc of the chain element k rows below (k > 0) / above (k < 0) edge e of band row r, or None."""
    rr, ee = r, e
    step = 1 if k > 0 else -1
    for _ in range(abs(k)):
        nb = ee.get("down" if step > 0 else "up")
        if nb is None:
            return None
        rr += step
        ee = rows[rr][nb]
    return ee["xc"]


def edge_x(rows, r, e, Y, bv0):
    """Model edge position (texels) of edge e of band row r at height Y inside that row: a Catmull-Rom spline through the
    chain's clamped row-centre positions; a chain end extends along the chain slope (r3 rule)."""
    yc = bv0 + r + 0.5
    if Y >= yc:
        p1, p2, p0, p3, t = e["xc"], chain_x(rows, r, e, 1), chain_x(rows, r, e, -1), chain_x(rows, r, e, 2), Y - yc
    else:
        p1, p2, p0, p3, t = chain_x(rows, r, e, -1), e["xc"], chain_x(rows, r, e, -2), chain_x(rows, r, e, 1), Y - yc + 1.0
    if p1 is None or p2 is None:
        s = e["slope"]
        if s is None:                     # native chain end: slope of its other link, else vertical
            ob, orr = (e.get("up"), r - 1) if Y >= yc else (e.get("down"), r + 1)
            s = (e["xc"] - rows[orr][ob]["xc"]) / (yc - (bv0 + orr + 0.5)) if ob is not None else 0.0
        return e["xc"] + s * (Y - yc)
    if p0 is None:
        p0 = 2 * p1 - p2
    if p3 is None:
        p3 = 2 * p2 - p1
    return 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3)


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
def repair_roi(np, idx, img, S, rgbc, cls_idx, roi=ROI, band=BAND):
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
    ctarget = editable & near & centre
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
    side_o = alpha_of(np, rgbc)[nat] >= 0.5                  # native alpha-majority side per pixel
    pcls = np.asarray(cls_idx)[nat]
    side_dev = np.abs(C - side_o.astype(np.float64))         # how much of each centre pixel the model gives the other side
    clog, cfall = [], 0
    for py, px in zip(*np.nonzero(ctarget)):
        py, px = int(py), int(px)
        so = bool(side_o[py, px])
        sy, sx, sd = ((int(oy[py, px]), int(ox[py, px]), float(dO[py, px])) if so
                      else (int(dy[py, px]), int(dx[py, px]), float(dD[py, px])))
        if sd > lim or pcls[sy, sx] != pcls[py, px]:
            cfall += 1
            continue
        nv = np.clip(np.rint(rgb[py, px] + w[py, px] * (rgb[sy, sx] - rgb[py, px])), 0, 255).astype(np.uint8)
        if np.array_equal(nv, old[py, px, :3]):
            continue
        new[py, px, :3] = nv
        clog.append(dict(py=py, px=px, u=u0 + px // S, v=v0 + py // S, native_index=int(nat[py, px]),
                         side="orange" if so else "dark", old_rgba=[int(c) for c in old[py, px]],
                         new_rgba=[int(c) for c in new[py, px]], donor_py=sy, donor_px=sx, donor_dist_px=round(sd, 3)))
    ctx = dict(target=target, ctarget=ctarget, centre=centre, editable=editable, deepO=deepO, deepD=deepD,
               side_o=side_o, pcls=pcls, w=w, lim=lim)
    verify(np, old, new, ctx, clog)
    sdmax = float(side_dev[ctarget].max()) if ctarget.any() else 0.0
    need(sdmax <= CENTRE_SIDE_DEV_MAX, f"a re-rendered centre pixel is cut by the edge (side dev {sdmax:.3f})")
    out = img.copy()
    out[v0 * S:v1 * S, u0 * S:u1 * S] = new
    used = np.concatenate([dO[ok & (C > 0)], dD[ok & (C < 1)]])
    model["oref"] = np.median(rgb[deepO], 0)
    model["dref"] = np.median(rgb[deepD], 0)
    Cr = C.copy()
    Cr[ctarget] = side_o[ctarget].astype(np.float64)
    model["C"], model["Cr"], model["ctarget"], model["ctx"], model["clog"] = C, Cr, ctarget, ctx, clog
    r3_rule = "PASS" if np.array_equal(new[centre], old[centre]) else "FAIL (intended option-b exception, see centre_log)"
    stats = dict(changed_px=int((new != old).any(-1).sum()), target_px=int(target.sum()),
                 fallback_unchanged=int((target & ~ok).sum()),
                 fallback_outside_feather=int((target & ~ok & (w >= 1.0)).sum()), mixed_coverage_px=int((~(p1 | p0)).sum()),
                 donor_dist_px_max=round(float(used.max()), 2) if used.size else None,
                 donor_dist_px_mean=round(float(used.mean()), 2) if used.size else None,
                 protected_px_in_roi=int((~editable).sum()),
                 centre_policy=CENTRE_POLICY,
                 centre_byte_exact_r3_rule=dict(result=r3_rule, changed_centre_px=len(clog)),
                 centre_candidates=int(ctarget.sum()), centre_changed=len(clog), centre_fallback_unchanged=cfall,
                 centre_side_dev_max=round(sdmax, 4),
                 r3_style_kept_centre_dev_max=round(float(np.abs(val[ctarget] - rgb[ctarget]).max()), 1) if ctarget.any() else None,
                 family_slope_tex_per_row=None if model["family_slope"] is None else round(model["family_slope"], 4),
                 chains=model["chains"], centre_log=clog)
    return out, stats, model


def verify(np, old, new, ctx, clog):
    """Re-check every invariant of one repaired ROI from the arrays and the centre log alone."""
    need(np.array_equal(new[..., 3], old[..., 3]), "alpha changed inside ROI")
    changed = (new != old).any(-1)
    need(not (changed & ~ctx["editable"]).any(), "protected pixel changed")
    need(not (changed & ~(ctx["target"] | ctx["ctarget"])).any(), "pixel outside the authorised edge band changed")
    need(not (changed & ctx["centre"] & ~ctx["ctarget"]).any(), "centre pixel outside the edge band changed")
    logged = {(e["py"], e["px"]) for e in clog}
    for py, px in zip(*np.nonzero(changed & ctx["centre"])):
        need((int(py), int(px)) in logged, "changed centre pixel missing from the centre log")
    for e in clog:
        py, px, sy, sx = e["py"], e["px"], e["donor_py"], e["donor_px"]
        so = bool(ctx["side_o"][py, px])
        need(e["side"] == ("orange" if so else "dark"), "logged side != native alpha-majority side")
        need(bool((ctx["deepO"] if so else ctx["deepD"])[sy, sx]), "donor not on the centre's native side")
        need(ctx["pcls"][sy, sx] == ctx["pcls"][py, px], "cross-class donor")
        need(math.hypot(sy - py, sx - px) <= ctx["lim"] + 1e-9, "donor beyond the distance bound")
        o = old[py, px, :3].astype(np.float64)
        exp = np.clip(np.rint(o + ctx["w"][py, px] * (old[sy, sx, :3].astype(np.float64) - o)), 0, 255).astype(np.uint8)
        need(np.array_equal(new[py, px, :3], exp), "centre RGB != same-side donor value")
        need(list(new[py, px]) == e["new_rgba"] and list(old[py, px]) == e["old_rgba"], "centre log RGBA mismatch")


# ---------------------------------------------------------------- quality metric
def tmap(np, img, S, model, roi=ROI):
    u0, v0, u1, v1 = roi
    o, d = model["oref"], model["dref"]
    ax = o - d
    return ((img[v0 * S:v1 * S, u0 * S:u1 * S, :3].astype(np.float64) - d) @ ax) / float(ax @ ax)


def _rms(np, v):
    return round(float(np.sqrt(np.mean(np.square(v)))), 4) if len(v) else None


def stair_metrics(np, img, S, model, roi=ROI):
    """Every chain (family / straight / native), per pixel row, in a +-1 texel window: t = orange-dark projection
    (model's input refs) normalised by the window's own plateaus (S/4 px at each end); edge = window end - sum(t)
    (rising) or window start + sum(t) (falling), i.e. by area. Per chain and aggregate: stair_px = RMS 2nd difference,
    resid_px = RMS(edge - model), jump_max_px = max |step - model step| (continuity), width_px, missing. Rows < 1 texel
    from the band top/bottom and windows leaving the ROI or touching the feather zone are excluded."""
    u0, v0, u1, v1 = roi
    rows, (bu0, bv0, bu1, bv1) = model["rows"], model["band"]
    t = tmap(np, img, S, model, roi)
    H, W = t.shape
    seq, kinds = {}, {}
    for py in range(H):
        Y = v0 + (py + 0.5) / S
        if not (bv0 + 1 <= Y < bv1 - 1):
            continue
        r = int(math.floor(Y)) - bv0
        for e in rows[r]:
            xm = (edge_x(rows, r, e, Y, bv0) - u0) * S
            lo, hi = int(math.floor(xm - S)), int(math.ceil(xm + S))
            if lo < 0 or hi > (bu1 - u0 - FEATHER_TEX) * S - 1:
                continue
            kinds[e["chain"]] = e["ckind"]
            seg = t[py, lo:hi]
            pl = max(2, S // 4)
            dark_lv, org_lv = (seg[:pl].mean(), seg[-pl:].mean()) if e["kind"] > 0 else (seg[-pl:].mean(), seg[:pl].mean())
            if org_lv - dark_lv < 0.5:
                seq.setdefault(e["chain"], []).append((py, None, xm, None))
                continue
            un = np.clip((seg - dark_lv) / (org_lv - dark_lv), 0.0, 1.0)
            area = float(un.sum())
            c = (hi - area) if e["kind"] > 0 else (lo + area)
            seq.setdefault(e["chain"], []).append((py, c, xm, int(((un > 0.1) & (un < 0.9)).sum())))
    per, all_d2, all_res, all_w, all_miss = {}, [], [], [], 0
    for cid, pts in seq.items():
        d2, res, jumps, wid = [], [], [], []
        miss = sum(1 for p in pts if p[1] is None)
        for py, c, xm, wd in pts:
            if c is not None:
                res.append(c - xm)
                wid.append(wd)
        for (pa, a, ma, _), (pb, b, mb, _) in zip(pts, pts[1:]):
            if a is not None and b is not None and pb == pa + 1:
                jumps.append(abs((b - a) - (mb - ma)))
        for (pa, a, _, _), (pb, b, _, _), (pc_, c, _, _) in zip(pts, pts[1:], pts[2:]):
            if None not in (a, b, c) and pb == pa + 1 and pc_ == pb + 1:
                d2.append(c - 2 * b + a)
        per[str(cid)] = dict(kind=kinds[cid], stair_px=_rms(np, d2), d2_n=len(d2), resid_px=_rms(np, res),
                             jump_max_px=round(float(max(jumps)), 4) if jumps else None, missing=miss,
                             width_px=round(float(np.mean(wid)), 3) if wid else None)
        all_d2 += d2
        all_res += res
        all_w += wid
        all_miss += miss
    return dict(stair_px=_rms(np, all_d2), resid_px=_rms(np, all_res),
                width_px=round(float(np.mean(all_w)), 3) if all_w else None, samples=len(all_res), missing=all_miss,
                d2_n=len(all_d2), chains=per)


def border_metrics(np, img, S, model, roi=ROI):
    """Band top border (horizontal edge at v = band top) per pixel column whose first band texel row is fully orange in
    the model and whose texel row above is fully dark: vertical area position (dark above, orange below) in a +-1 texel
    window. resid vs the exact border, RMS 2nd difference along consecutive columns."""
    u0, v0, u1, v1 = roi
    (bu0, bv0, bu1, bv1), C = model["band"], model["C"]
    t = tmap(np, img, S, model, roi)
    yb = (bv0 - v0) * S
    if yb < S:
        return dict(n=0, resid_max_px=None, stair_px=None, missing=0)
    cols, miss = [], 0
    for px in range((bu0 - u0) * S, int((bu1 - u0 - FEATHER_TEX - 1) * S)):
        if float(C[yb:yb + S, px].min()) < 1.0 or float(C[yb - S:yb, px].max()) > 0.0:
            continue
        seg = t[yb - S:yb + S, px]
        pl = max(2, S // 4)
        dark_lv, org_lv = seg[:pl].mean(), seg[-pl:].mean()
        if org_lv - dark_lv < 0.5:
            miss += 1
            continue
        un = np.clip((seg - dark_lv) / (org_lv - dark_lv), 0.0, 1.0)
        cols.append((px, (yb + S) - float(un.sum())))
    res = [c - yb for _, c in cols]
    d2 = [c - 2 * b + a for (pa, a), (pb, b), (pc_, c) in zip(cols, cols[1:], cols[2:]) if pb == pa + 1 and pc_ == pb + 1]
    return dict(n=len(cols), resid_max_px=round(float(max(abs(x) for x in res)), 4) if res else None,
                stair_px=_rms(np, d2), missing=miss)


def corner_metrics(np, img, S, model, roi=ROI):
    """Top-left band texel: mean orange-dark projection of the output against the texel's native alpha."""
    u0, v0, u1, v1 = roi
    (bu0, bv0, bu1, bv1) = model["band"]
    t = tmap(np, img, S, model, roi)
    blk = t[(bv0 - v0) * S:(bv0 - v0 + 1) * S, (bu0 - u0) * S:(bu0 - u0 + 1) * S]
    return dict(alpha=round(float(model["alpha"][0, 0]), 4), t_mean=round(float(blk.mean()), 4))


def dot_metrics(np, img, S, model, roi=ROI):
    """Unexplained local contrast at every edge-band texel-centre pixel: |(t(p) - mean t(4-nbrs)) - (Cr(p) - mean
    Cr(4-nbrs))|, Cr = model coverage with the centre pixels at their native side (the option-b target)."""
    t = tmap(np, img, S, model, roi)
    Cr, m = model["Cr"], model["ctarget"]
    H, W = Cr.shape
    vals = []
    for py, px in zip(*np.nonzero(m)):
        if 0 < py < H - 1 and 0 < px < W - 1:
            nt = (t[py - 1, px] + t[py + 1, px] + t[py, px - 1] + t[py, px + 1]) / 4.0
            nc = (Cr[py - 1, px] + Cr[py + 1, px] + Cr[py, px - 1] + Cr[py, px + 1]) / 4.0
            vals.append(abs((t[py, px] - nt) - (Cr[py, px] - nc)))
    return dict(n=len(vals), max_dc=round(float(max(vals)), 4) if vals else None,
                p95_dc=round(float(np.percentile(vals, 95)), 4) if vals else None)


def quality_gate(q_out, q_in, q_ref, fallback_outside_feather=0, dots=None, border=None, border_in=None, corner=None):
    need(fallback_outside_feather == 0, f"{fallback_outside_feather} target px left unchanged (no donor) outside the feather")
    need(q_out["samples"] >= 20 and q_out["stair_px"] is not None, "too few quality samples on the output")
    need(q_out["missing"] <= max(2, q_out["samples"] // 20), "edge crossings missing on the output")
    need(q_in["stair_px"] is not None and q_out["stair_px"] <= q_in["stair_px"], "output staircase not <= input")
    need(q_in["width_px"] is not None and q_out["width_px"] < q_in["width_px"], "output edge not sharper than input")
    need(q_ref["stair_px"] is not None and q_out["stair_px"] < q_ref["stair_px"], "output staircase not < stepped reference")
    for cid, c in q_out["chains"].items():                       # per chain: one bad edge cannot hide in the aggregate
        if c["d2_n"] < 8:
            continue
        ci = q_in["chains"].get(cid, {})
        lim = max(ci.get("stair_px") or 0.0, STAIR_FLOOR_PX)
        need(c["stair_px"] <= lim, f"chain {cid} ({c['kind']}) staircase {c['stair_px']} > {lim:.4f}")
        need(c["missing"] == 0, f"chain {cid} ({c['kind']}) has {c['missing']} missing crossings")
        need(c["jump_max_px"] is not None and c["jump_max_px"] <= CONT_MAX_PX,
             f"chain {cid} ({c['kind']}) continuity jump {c['jump_max_px']} > {CONT_MAX_PX}")
    if dots is not None:
        need(dots["max_dc"] is not None and dots["max_dc"] <= DOT_MAX, f"dot contrast {dots['max_dc']} > {DOT_MAX}")
    if border is not None:
        need(border["n"] >= 4, f"only {border['n']} border columns measured")
        need(border["resid_max_px"] <= BORDER_RESID_MAX_PX, f"border residual {border['resid_max_px']} > {BORDER_RESID_MAX_PX}")
        lim = max((border_in or {}).get("stair_px") or 0.0, STAIR_FLOOR_PX)
        need(border["stair_px"] is None or border["stair_px"] <= lim, f"border staircase {border['stair_px']} > {lim:.4f}")
    if corner is not None:
        need(abs(corner["t_mean"] - corner["alpha"]) <= CORNER_TOL,
             f"corner texel {corner['t_mean']} vs native alpha {corner['alpha']} > {CORNER_TOL}")


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
    cls = classes(cw)

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

    def roi_of(img, S):
        return img[froi[1] * S:froi[3] * S, froi[0] * S:froi[2] * S]

    def outside_equal(a, b, S, msg="outside ROI changed"):
        mask = np.zeros(a.shape[:2], bool)
        mask[froi[1] * S:froi[3] * S, froi[0] * S:froi[2] * S] = True
        need(np.array_equal(a[~mask], b[~mask]), msg)

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

    def run_quality(idx, S, real):
        soft, crisp = render(idx, S, True), render(idx, S, False)
        out, st, m = repair_roi(np, idx, soft, S, rgbc, cls, froi, fband)
        need(np.array_equal(out[..., 3], soft[..., 3]), "alpha changed")
        outside_equal(out, soft, S)
        q = dict(input=stair_metrics(np, soft, S, m, froi), stepped=stair_metrics(np, crisp, S, m, froi),
                 r4=stair_metrics(np, out, S, m, froi), dots_r4=dot_metrics(np, out, S, m, froi),
                 dots_input=dot_metrics(np, soft, S, m, froi), border_input=border_metrics(np, soft, S, m, froi),
                 border_r4=border_metrics(np, out, S, m, froi), corner_input=corner_metrics(np, soft, S, m, froi),
                 corner_r4=corner_metrics(np, out, S, m, froi))
        quality_gate(q["r4"], q["input"], q["stepped"], st["fallback_outside_feather"] if real else 0, q["dots_r4"],
                     q["border_r4"], q["border_input"], q["corner_r4"] if real else None)
        need(q["r4"]["stair_px"] < 0.5 * q["stepped"]["stair_px"], "r4 staircase not < half of the stepped render")
        return out, soft, st, m, q

    def summary(st):
        return {k: st[k] for k in ("changed_px", "fallback_unchanged", "fallback_outside_feather", "centre_candidates",
                                   "centre_changed", "centre_fallback_unchanged", "centre_side_dev_max",
                                   "r3_style_kept_centre_dev_max", "centre_byte_exact_r3_rule", "family_slope_tex_per_row")}

    def p_actual(S):
        def f():
            idx = actual()
            out, soft, st, m, q = run_quality(idx, S, True)
            need(m["family_slope"] is not None and -0.9 <= m["family_slope"] <= -0.3,
                 f"actual family slope {m['family_slope']} not the real ~-0.54 direction")
            need(st["changed_px"] > 0, "no change on the actual pattern")
            need(st["fallback_outside_feather"] == 0, f"{st['fallback_outside_feather']} fallback px outside the feather")
            need(st["centre_changed"] > 0, "option (b) changed no centre pixel on the actual pattern")
            return dict(quality=q, stats=summary(st), chains=m["chains"])
        return f
    case("positive: ACTUAL ROI stripe pattern (ROI_SHA) at S=8: direction, centres (b), per-chain/border/corner/dot gates",
         p_actual(8))
    case("positive: ACTUAL ROI stripe pattern (ROI_SHA) at S=4: direction, centres (b), per-chain/border/corner/dot gates",
         p_actual(4))

    def p_fittings():
        idx = actual()
        S = 8
        soft = render(idx, S, True)
        out, _, _ = repair_roi(np, idx, soft, S, rgbc, cls, froi, fband)
        for (u, v) in [(4, 6), (5, 6), (6, 6), (4, 9), (5, 9), (6, 9), (7, 9)]:   # 7DD / 66CC fittings (real u72-75)
            need(np.array_equal(out[v * S:(v + 1) * S, u * S:(u + 1) * S], soft[v * S:(v + 1) * S, u * S:(u + 1) * S]),
                 f"protected fitting texel ({u},{v}) changed")
        return dict(checked=7)
    case("positive: protected 7DD / 66CC fittings of the actual ROI unchanged (incl. their centre pixels)", p_fittings)

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
        _, _, st, m, q = run_quality(idx, 8, False)
        need(m["family_slope"] is not None and abs(m["family_slope"] + 0.5) <= 0.1, f"steep slope {m['family_slope']} != -0.5")
        return dict(quality=q, stats=summary(st))
    case("positive: steep two-row staircase (1 texel per 2 rows), stripes continue outside: slope -0.5, gates", p_steep)

    def p_shallow():
        idx = stripes(lambda r, x: (x + 2 * r) % 8 < 4)
        _, _, st, m, q = run_quality(idx, 8, False)
        need(m["family_slope"] is not None and abs(m["family_slope"] + 2.0) <= 0.1, f"shallow slope {m['family_slope']} != -2")
        return dict(quality=q, stats=summary(st))
    case("positive: shallow staircase (2 texels per row), stripes continue outside: slope -2, gates", p_shallow)

    def p_straight(S):
        def f():
            idx = stripes(lambda r, x: x % 6 < 3)
            crisp = render(idx, S, False)
            out, st, m = repair_roi(np, idx, crisp, S, rgbc, cls, froi, fband)
            need(all(c["kind"] == "straight" for c in m["chains"]), "vertical edges not classified straight")
            need(np.array_equal(out, crisp), f"crisp straight vertical/horizontal edges changed ({st['changed_px']} px)")
            return dict(chains=len(m["chains"]), centre_changed=st["centre_changed"])
        return f
    case("positive: straight vertical + horizontal edges, crisp input byte-identical incl. centres (S=8)", p_straight(8))
    case("positive: straight vertical + horizontal edges, crisp input byte-identical incl. centres (S=4)", p_straight(4))

    base = actual()
    soft8 = render(base, 8, True)

    def neg_oob():
        repair_roi(np, base, soft8, 8, rgbc, cls, (30, 4, 44, 12), (31, 5, 44, 12))
    case("negative: ROI out of bounds", neg_oob, "ROI out of bounds")

    def neg_scale():
        repair_roi(np, base, np.zeros((256, 640, 4), np.uint8), 16, rgbc, cls, froi, fband)
    case("negative: scale 16 not allowed", neg_scale, "scale 16 not allowed")

    def neg_crossclass_clut():
        cw2 = cw.copy()
        cw2[0] = 0
        need(len(set(classes(cw2)[np.unique(base[4:12, 4:32])].tolist())) == 1, "ROI not single-class under the CLUT")
    case("negative: cross-class ROI (edited CLUT) rejected", neg_crossclass_clut, "ROI not single-class")

    def neg_wrong_clut():
        cw2 = cw.copy()
        cw2[0] ^= 1                            # one bit of the pinned 8F297232 words
        clut_check(cw2, "E8769E55-8F297232")   # the same check main() applies before any decode
    case("negative: edited CLUT words rejected by the PAL CRC check", neg_wrong_clut, "CLUT words CRC != PAL")

    def neg_foreign():
        b2 = base.copy()
        b2[8, 20] = 0x6                     # a fitting index inside the stripe band
        repair_roi(np, b2, render(b2, 8, True), 8, rgbc, cls, froi, fband)
    case("negative: foreign (fitting) index inside the stripe band rejected", neg_foreign, "non-stripe index inside BAND")

    def neg_same_run_shade():
        b2 = base.copy()
        b2[8, 27] = 0x3                     # real (u95,v68) is orange inside an orange run: a shade there has no edge
        repair_roi(np, b2, render(b2, 8, True), 8, rgbc, cls, froi, fband)
    case("negative: shade texel inside a same-colour run rejected", neg_same_run_shade, "shade texels inside a same-colour run")

    mb = {}

    def mbase():
        """Repaired actual pattern at S=8 for the mutation negatives (a failure here makes each of them BAD)."""
        if not mb:
            o8, _, mm = repair_roi(np, base, soft8, 8, rgbc, cls, froi, fband)
            need(len(mm["clog"]) > 0, "no centre log on the actual pattern")
            mb.update(out=o8, m=mm, old=roi_of(soft8, 8).copy(), new=roi_of(o8, 8).copy(), ctx=mm["ctx"], log=mm["clog"])
        return mb

    def neg_alpha():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        n2 = new8.copy()
        n2[20, 40, 3] ^= 1
        verify(np, old8, n2, ctx8, log8)
    case("negative: alpha change detected", neg_alpha, "alpha changed")

    def neg_wrong_side():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        e = dict(log8[0])
        opp = ctx8["deepD"] if e["side"] == "orange" else ctx8["deepO"]
        oys, oxs = np.nonzero(opp)
        k = int(np.argmin((oys - e["py"]) ** 2 + (oxs - e["px"]) ** 2))
        e["donor_py"], e["donor_px"] = int(oys[k]), int(oxs[k])
        n2 = new8.copy()
        o = old8[e["py"], e["px"], :3].astype(np.float64)
        w_ = ctx8["w"][e["py"], e["px"]]
        n2[e["py"], e["px"], :3] = np.clip(np.rint(o + w_ * (old8[e["donor_py"], e["donor_px"], :3] - o)), 0, 255).astype(np.uint8)
        e["new_rgba"] = [int(c) for c in n2[e["py"], e["px"]]]
        verify(np, old8, n2, ctx8, [e] + log8[1:])
    case("negative: centre recoloured from the OTHER side's donor", neg_wrong_side, "donor not on the centre's native side")

    def neg_cross_class_donor():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        e = log8[0]
        c2 = dict(ctx8)
        pc = ctx8["pcls"].copy()
        pc[e["donor_py"], e["donor_px"]] = 255 if pc[e["py"], e["px"]] != 255 else 127
        c2["pcls"] = pc
        verify(np, old8, new8, c2, log8)
    case("negative: centre recoloured from a CROSS-CLASS donor", neg_cross_class_donor, "cross-class donor")

    def neg_protected():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        ys, xs = np.nonzero(~ctx8["editable"])
        n2 = new8.copy()
        n2[int(ys[0]), int(xs[0]), 0] ^= 1
        verify(np, old8, n2, ctx8, log8)
    case("negative: protected (fitting) pixel mutation detected", neg_protected, "protected pixel changed")

    def neg_outside_band_centre():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        ys, xs = np.nonzero(ctx8["centre"] & ctx8["editable"] & ~ctx8["ctarget"])
        n2 = new8.copy()
        n2[int(ys[0]), int(xs[0]), 0] ^= 1
        verify(np, old8, n2, ctx8, log8)
    case("negative: centre pixel OUTSIDE the edge band mutated", neg_outside_band_centre, "outside the authorised edge band")

    def neg_unlogged_centre():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        verify(np, old8, new8, ctx8, log8[1:])
    case("negative: changed centre missing from the centre log", neg_unlogged_centre, "missing from the centre log")

    def neg_outside_roi():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        o2 = out8.copy()
        o2[2, 2, 0] ^= 1
        outside_equal(o2, soft8, 8)
    case("negative: pixel OUTSIDE the ROI mutated", neg_outside_roi, "outside ROI changed")

    def neg_kept_centres():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        o3 = out8.copy()
        reg = roi_of(o3, 8)
        reg[ctx8["ctarget"]] = old8[ctx8["ctarget"]]          # r3 behaviour: blurred centres kept byte-exact
        d = dot_metrics(np, o3, 8, m8, froi)
        need(d["max_dc"] is not None and d["max_dc"] <= DOT_MAX, f"dot contrast {d['max_dc']} > {DOT_MAX}")
    case("negative: r3-style kept blurred centres fail the dot gate", neg_kept_centres, "dot contrast")

    def neg_stepped():
        b = mbase()
        old8, new8, ctx8, log8, out8, m8 = b['old'], b['new'], b['ctx'], b['log'], b['out'], b['m']
        qs = stair_metrics(np, render(base, 8, False), 8, m8, froi)
        qi = stair_metrics(np, soft8, 8, m8, froi)
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
    rd = S45 / "repairs" / f"{stamp}-diagbands-r4-{a.key or 'fixtures'}"
    rd.mkdir(parents=True, exist_ok=False)
    rec = dict(run=stamp, owner="claude-einhander-s45", tool_sha256=sha(Path(__file__)), mode=a.key or "fixtures",
               roi_half_open=list(ROI), band_half_open=list(BAND), params=dict(
                   a_o=A_O, a_d=A_D, link_max_tex=LINK_MAX_TEX, slope_tol=SLOPE_TOL, straight_frac=STRAIGHT_FRAC,
                   centre_margin_tex=CENTRE_MARGIN_TEX, edge_band_tex=EDGE_BAND_TEX, donor_max_tex=DONOR_MAX_TEX,
                   feather_tex=FEATHER_TEX, supersample=SS, pix_tex=PIX_TEX, stair_floor_px=STAIR_FLOOR_PX,
                   cont_max_px=CONT_MAX_PX, dot_max=DOT_MAX, centre_side_dev_max=CENTRE_SIDE_DEV_MAX,
                   border_resid_max_px=BORDER_RESID_MAX_PX, corner_tol=CORNER_TOL), centre_policy=CENTRE_POLICY,
               status="STARTED", stage_reached="pins")
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
            out, st, model = repair_roi(np, idx, src, S, rgbc, cls)
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
                     r4=stair_metrics(np, out, S, model), dots_r4=dot_metrics(np, out, S, model),
                     dots_input=dot_metrics(np, src, S, model), border_input=border_metrics(np, src, S, model),
                     border_r4=border_metrics(np, out, S, model), corner_input=corner_metrics(np, src, S, model),
                     corner_r4=corner_metrics(np, out, S, model))
            rec["files"][str(size)] = dict(input=KEYS[a.key]["png"][size][0].as_posix(), stats=st, audit=aud, quality=q)
            need(aud["r1_centre_bad"] == 0 and aud["conn_viol_px"] == 0, "primary policy fails")
            need(all(aud[x] == 0 for x in ("r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "s2_viol_px")), "s/2 strict fails")
            need(aud["r5_fringe_px"] == 0, "R5 fringe > 0")
            need(st["changed_px"] > 0, "no pixel changed in the ROI")
            rec["stage_reached"] = f"quality {size}"
            try:
                quality_gate(q["r4"], q["input"], q["r2_rejected"], st["fallback_outside_feather"], q["dots_r4"],
                             q["border_r4"], q["border_input"], q["corner_r4"])
            except Fail as e:                 # evidence crops are still written below; no art PNG; exit 5
                qfail.append(f"{size}: {e}")
            outs[size] = (out, src, r2img, S)
        rec["stage_reached"] = "write"
        from PIL import ImageDraw
        (rd / "review").mkdir()
        for size, (out, src, r2img, S) in outs.items():
            if not qfail:
                fn = rd / f"{a.key}-{size}-diagbands-r4.png"
                Image.fromarray(out).save(fn, compress_level=6)
                rec["files"][str(size)]["output"] = fn.name
                rec["files"][str(size)]["output_sha256"] = sha(fn)
            zoom = 16 // S
            tw, th = (u1 - u0) * 16, (v1 - v0) * 16

            def crop(im):
                return np.repeat(np.repeat(im[v0 * S:v1 * S, u0 * S:u1 * S, :3], zoom, 0), zoom, 1)
            tiles = [("native nearest", np.repeat(np.repeat(rgbc[idx[v0:v1, u0:u1]], 16, 0), 16, 1)),
                     (f"input {size}", crop(src)), (f"r2 {size} (REJECTED)", crop(r2img)), (f"diag_bands r4 {size}", crop(out))]
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
