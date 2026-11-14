"""s23: Scale2x (AdvMAME2x) on palette indices with a SCALE-AWARE right-angle CORNER GUARD. Light module: no I/O.

Fix for runs/look-review-20261114T183612Z/corner-rounding-defect.json (73ad6b47...): j5_s3_scale2x.scale2x() fires
E0 = D whenever B == D (with B != H and D != F), i.e. on EVERY convex corner, so a true square corner of a large flat
region (tile plates, panel frames, stepped blocks) is bevelled inside its corner texel; cascaded 3x for 8x this reads as
a quarter-round of ~1 native texel (21 of 64 HD pixels of the corner texel; J5 docstring unit test).

scale2x_cg(a, m) is one Scale2x pass on an image whose native texel is m pixels wide (m = 2**(pass-1): 1, 2, 4).
Rule (A B C / D E F / G H I around E, edge padding as in J5): identical to j5_s3_scale2x.scale2x except that a
sub-pixel keeps E when E is the convex corner of a TRUE RIGHT ANGLE AT NATIVE SCALE, i.e. both outside edges and both
inside edges continue straight for m pixels (one native texel) past the corner. With p(dy, dx) = pixel at (y+dy, x+dx):
  E0 (top-left)     guard: for k = 1..m  p(-1, k) == B, p(k, -1) == D, p(0, k) == E, p(k, 0) == E
  E1 (top-right)    guard: for k = 1..m  p(-1,-k) == B, p(k,  1) == F, p(0,-k) == E, p(k, 0) == E
  E2 (bottom-left)  guard: for k = 1..m  p(-k,-1) == D, p(1,  k) == H, p(-k,0) == E, p(0, k) == E
  E3 (bottom-right) guard: for k = 1..m  p(-k, 1) == F, p(1, -k) == H, p(-k,0) == E, p(0,-k) == E
  E0 = D if act and D == B and not guard_tl else E   (E1 = F if act and B == F ..., E2 = D if act and D == H ...,
  E3 = F if act and H == F ...),  act = B != H and D != F.
With m = 1 the guard is exactly C == B, G == D, F == E, H == E (E0) and its mirror images.
Why scale-aware (review 2026-11-14 ~18:55Z): an m = 1 guard re-applied on the 2x / 4x passes sees every 1-texel feature
as a 2x2 / 4x4 block with right angles, so it froze 45-degree edges and dither at the 2x staircase (blockier than J5).
Requiring one NATIVE texel of continuation keeps the guard to corners that are right angles in the native art.
Properties (j10_corner_guard.py selftest, run only under a CPU grant):
  * per pass, the guard only ever turns a Scale2x replacement back into E (wherever it differs from scale2x it equals E);
  * square blocks and stepped L regions with sides >= 2 texels stay exactly nearest-neighbour at 8x;
  * 45-degree and 2:1 edges, checkerboard dither and single texels / 1-texel lines come out identical to the J5 cascade
    (the guard needs an inside run of one native texel, so 1-texel features keep J5's rounding: J10 changes ONLY the
    right angles of features >= 2 texels; J5's docstring claim that dither stays exactly native holds for one pass only);
  * a guarded native corner stays guarded on every later pass (its outside/inside runs stay >= m pixels).
"""
import numpy as np


def _shifted(a, m):
    p = np.pad(a, m, mode="edge")
    h, w = a.shape
    return lambda dy, dx: p[m + dy:m + dy + h, m + dx:m + dx + w]


def right_angle_corners(a, m=1):
    """Boolean maps (tl, tr, bl, br) of texels whose Scale2x replacement the guard suppresses at native texel width m."""
    at = _shifted(a, m)
    B, D, E, F, H = at(-1, 0), at(0, -1), a, at(0, 1), at(1, 0)
    act = (B != H) & (D != F)
    tl, tr, bl, br = act & (D == B), act & (B == F), act & (D == H), act & (H == F)
    for k in range(1, m + 1):
        tl &= (at(-1, k) == B) & (at(k, -1) == D) & (at(0, k) == E) & (at(k, 0) == E)
        tr &= (at(-1, -k) == B) & (at(k, 1) == F) & (at(0, -k) == E) & (at(k, 0) == E)
        bl &= (at(-k, -1) == D) & (at(1, k) == H) & (at(-k, 0) == E) & (at(0, k) == E)
        br &= (at(-k, 1) == F) & (at(1, -k) == H) & (at(-k, 0) == E) & (at(0, -k) == E)
    return tl, tr, bl, br


def scale2x_cg(a, m=1):
    at = _shifted(a, 1)
    B, D, E, F, H = at(-1, 0), at(0, -1), a, at(0, 1), at(1, 0)
    act = (B != H) & (D != F)
    tl, tr, bl, br = right_angle_corners(a, m)
    e0 = np.where(act & (D == B) & ~tl, D, E)
    e1 = np.where(act & (B == F) & ~tr, F, E)
    e2 = np.where(act & (D == H) & ~bl, D, E)
    e3 = np.where(act & (H == F) & ~br, F, E)
    out = np.empty((a.shape[0] * 2, a.shape[1] * 2), a.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out


def cascade(a, times):
    """times passes of scale2x_cg with the native texel width doubling each pass (1, 2, 4, ...)."""
    for k in range(times):
        a = scale2x_cg(a, 2 ** k)
    return a
