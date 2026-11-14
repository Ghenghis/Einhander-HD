"""s23 shared helpers (claude-einhander-s23). Independent numpy implementation of the class-ownership rules.

Rules follow remaster-audit/claude-backlog/class-mip/DESIGN.md + DESIGN-V2.md and the frozen proto-v2b semantics
(class_mip.c sha256 c84efa60...):
  native class: CLUT word 0 -> 0 (cutout), STP bit 15 -> 255, else 127
  deviant     : HD alpha != native class of its own cell (cell = floor(p / s))
  R1          : pixel (cy*s + s//2, cx*s + s//2) must equal the native class
  R2          : a deviant pixel of class X must lie within bound*s (Euclidean, pixel centre) of one of the 8 neighbouring
                native cells whose class is X (own cell excluded; out-of-image cells skipped)
  R3 (diag)   : deviant pixel whose clamped 3x3 native neighbourhood is uniform
  R4          : a deviant pixel's 4-connected same-alpha component (across cells) must contain a non-deviant pixel
  R5          : a cutout pixel 4-adjacent to a visible pixel must carry the RGB of the deterministic bleed fill. For layer-1
                pixels the proto-v2b multi-source BFS winner is the first visible 4-neighbour in raster order: up, left,
                right, down. That rule is reproduced exactly here.
This module is written from the rule text, not from the C code paths, so it is an independent cross-check.
Nothing here writes outside the caller's output folder.
"""
import hashlib
import json
import os
import time
import zlib

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = "C:/github/Einhander"
S23 = ROOT + "/remaster-audit/parallel-stages-20261114/s23"


def below_normal():
    try:
        import psutil
        me = psutil.Process()
        me.cpu_affinity([me.cpu_affinity()[-1]])  # one logical CPU
    except Exception:
        pass
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))
    except Exception:
        return False


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def clut_words(clut_hex):
    b = bytes.fromhex(clut_hex)
    return np.frombuffer(b, "<u2").astype(np.int64)


def clut_classes(c):
    c = np.asarray(c, np.int64)
    return np.where(c == 0, 0, np.where(c & 0x8000, 255, 127)).astype(np.uint8)


def clut_rgb(c):
    c = np.asarray(c, np.int64)
    return np.stack([(c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3], -1).astype(np.uint8)


def load_words(path, rect, tex):
    """Read a <TEX>.words.bin, prove crc32 == TEX, return (index map, sha256, crc_ok). 4bpp only for S2/S3 pages."""
    b = open(path, "rb").read()
    crc = "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)
    w16 = np.frombuffer(b, "<u2")
    ww, hh = int(rect[2]), int(rect[3])
    w16 = w16[: ww * hh].reshape(hh, ww)
    idx = np.empty((hh, ww * 4), np.uint8)
    for k in range(4):
        idx[:, k::4] = (w16 >> (4 * k)) & 0xF
    return idx, sha256_bytes(b), crc == tex.upper()


def load_rgba(p):
    with Image.open(p) as im:
        return np.ascontiguousarray(np.asarray(im.convert("RGBA")))


def save_png(p, a):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp.png"
    Image.fromarray(a, "RGBA").save(tmp, optimize=False, compress_level=6)
    os.replace(tmp, p)
    return sha256_file(p)


def up(a, s):
    return np.repeat(np.repeat(a, s, 0), s, 1)


def _shift(a, dy, dx, fill):
    """b[y, x] = a[y + dy, x + dx] with out-of-range = fill."""
    h, w = a.shape[:2]
    b = np.full_like(a, fill)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    if ys1 > ys0 and xs1 > xs0:
        b[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    return b


def validate(rgba, ncls, s, bound=0.5, want_flags=False):
    """Independent R1-R5 counts. rgba (H,W,4) uint8, ncls (th,tw) uint8 in {0,127,255}."""
    from scipy import ndimage
    H, W = rgba.shape[:2]
    th, tw = ncls.shape
    assert H == th * s and W == tw * s, (H, W, th, tw, s)
    A = rgba[..., 3]
    C = up(ncls, s)
    nonclass = int((~np.isin(A, (0, 127, 255))).sum())
    dev = A != C
    # R1
    cy = np.arange(th) * s + s // 2
    cx = np.arange(tw) * s + s // 2
    r1_cells = A[np.ix_(cy, cx)] != ncls
    # R2: distance from pixel centre to the 8 neighbouring native cells of class X
    lx = (np.arange(W) % s + 0.5)[None, :]
    ly = (np.arange(H) % s + 0.5)[:, None]
    ok = np.zeros((H, W), bool)
    lim = (bound * s) ** 2
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            ddx = lx if dx == -1 else (s - lx if dx == 1 else np.zeros_like(lx))
            ddy = ly if dy == -1 else (s - ly if dy == 1 else np.zeros_like(ly))
            d2 = ddx ** 2 + ddy ** 2
            if d2.min() > lim:
                continue
            nb = _shift(ncls.astype(np.int16), dy, dx, -1)  # neighbour cell class, -1 outside the image
            nbh = up(nb, s)
            ok |= (nbh == A.astype(np.int16)) & (d2 <= lim)
    r2 = dev & ~ok
    # R3 (diagnostic): clamped 3x3 native neighbourhood uniform
    pad = np.pad(ncls, 1, mode="edge")
    uni = np.ones_like(ncls, bool)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            uni &= pad[dy:dy + th, dx:dx + tw] == ncls
    r3 = dev & up(uni, s)
    # R4: components of equal alpha (4-connected) must contain a non-deviant pixel
    r4 = np.zeros((H, W), bool)
    st = ndimage.generate_binary_structure(2, 1)
    for X in (0, 127, 255):
        m = A == X
        if not (m & dev).any():
            continue
        lab, n = ndimage.label(m, st)
        good = np.zeros(n + 1, bool)
        good[np.unique(lab[m & ~dev])] = True
        good[0] = True
        r4 |= dev & m & ~good[lab]
    # cell-level summaries
    r1px = np.zeros((H, W), bool)
    r1px[np.ix_(cy, cx)] = r1_cells
    other = (r2 | r4).reshape(th, s, tw, s).any(axis=(1, 3))
    cells_bad = int((r1_cells | other).sum())
    pinhole_cells = int((~r1_cells & other).sum())
    out = dict(pixels=H * W, cells=th * tw, r1_centre_bad=int(r1_cells.sum()), r2_displaced_px=int(r2.sum()),
               r3_uniform_bad_px=int(r3.sum()), r4_island_px=int(r4.sum()), cells_bad=cells_bad, pinhole_cells=pinhole_cells,
               nonclass_px=nonclass, deviant_px=int(dev.sum()))
    fill = edge_fill(rgba)
    edge = fill["edge"]
    out["r5_fringe_px"] = int((edge & (np.abs(rgba[..., :3].astype(np.int16) - fill["rgb"].astype(np.int16)).max(-1) > 0)).sum())
    out["edge_cutout_px"] = int(edge.sum())
    if want_flags:
        return out, dict(r1=r1px, r2=r2, r3=r3, r4=r4, dev=dev)
    return out


def edge_fill(rgba):
    """Exact proto-v2b BFS winner for layer-1 cutout pixels: first visible 4-neighbour in raster order (up, left, right,
    down). Returns {'edge': mask of cutout pixels with a visible 4-neighbour, 'rgb': fill colour (valid on edge)}."""
    A = rgba[..., 3] != 0
    rgb = rgba[..., :3]
    H, W = A.shape
    fill = np.zeros_like(rgb)
    got = np.zeros((H, W), bool)
    cut = ~A
    for dy, dx in ((-1, 0), (0, -1), (0, 1), (1, 0)):
        nv = _shift(A, dy, dx, False)
        nr = _shift(rgb, dy, dx, 0)
        take = cut & nv & ~got
        fill[take] = nr[take]
        got |= take
    return dict(edge=got, rgb=fill)


def bleed_fill(rgba):
    """Alpha-preserving cutout RGB fill: layer-1 exact BFS winner (so proto-v2b R5 == 0), deeper cutout pixels from the
    Euclidean-nearest visible pixel. Visible pixels and alpha are byte-identical. Returns (new rgba, pixels written)."""
    from scipy import ndimage
    out = rgba.copy()
    A = rgba[..., 3] != 0
    if A.all() or not A.any():
        return out, 0
    _, (iy, ix) = ndimage.distance_transform_edt(~A, return_indices=True)
    deep = ~A
    out[deep, :3] = rgba[iy[deep], ix[deep], :3]
    e = edge_fill(rgba)
    out[e["edge"], :3] = e["rgb"][e["edge"]]
    written = int((np.abs(out[..., :3].astype(np.int16) - rgba[..., :3].astype(np.int16)).max(-1)[~A] > 0).sum())
    return out, written


def bilinear(rgb, u, v):
    """GL_LINEAR, clamp to edge; u, v in pixel units (texel centres at +0.5)."""
    H, W = rgb.shape[:2]
    x = u - 0.5
    y = v - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    x1 = np.clip(x0 + 1, 0, W - 1)
    y1 = np.clip(y0 + 1, 0, H - 1)
    x0 = np.clip(x0, 0, W - 1)
    y0 = np.clip(y0, 0, H - 1)
    f = rgb.astype(np.float64)
    return (f[y0, x0] * (1 - fx) * (1 - fy) + f[y0, x1] * fx * (1 - fy) + f[y1, x0] * (1 - fx) * fy + f[y1, x1] * fx * fy)


def sampled_fringe(rgba, n=200000, seed=23, edge_only=True):
    """Sampled fringe metric following HD_FS filter mode: the fragment survives when the level-0 pixel under it is
    visible; its colour is GL_LINEAR RGB. Error = max-channel |RGB(current) - RGB(bleed-filled)| over surviving
    samples. With edge_only the samples are drawn inside visible pixels that touch a cutout pixel (where fringe can
    appear); the share of all visible pixels that are such edge pixels is reported, so totals can be weighted."""
    A = rgba[..., 3] != 0
    H, W = A.shape
    filled, _ = bleed_fill(rgba)
    rng = np.random.default_rng(seed)
    if edge_only:
        near_cut = np.zeros_like(A)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            near_cut |= _shift(~A, dy, dx, False)
        cand = A & near_cut
    else:
        cand = A
    ys, xs = np.nonzero(cand)
    if len(ys) == 0:
        return dict(samples=0, visible_px=int(A.sum()), edge_visible_px=int(cand.sum()))
    pick = rng.integers(0, len(ys), n)
    u = xs[pick] + rng.random(n)
    v = ys[pick] + rng.random(n)
    e = np.abs(bilinear(rgba[..., :3], u, v) - bilinear(filled[..., :3], u, v)).max(-1)
    lum_cur = bilinear(rgba[..., :3], u, v) @ np.array([0.2126, 0.7152, 0.0722])
    lum_fil = bilinear(filled[..., :3], u, v) @ np.array([0.2126, 0.7152, 0.0722])
    return dict(samples=int(n), visible_px=int(A.sum()), edge_visible_px=int(cand.sum()),
                edge_share_of_visible=round(float(cand.sum() / max(1, A.sum())), 5),
                err_mean=round(float(e.mean()), 3), err_p95=round(float(np.percentile(e, 95)), 3), err_max=round(float(e.max()), 3),
                share_err_gt_8=round(float((e > 8).mean()), 5), share_err_gt_24=round(float((e > 24).mean()), 5),
                dark_bias_mean=round(float((lum_cur - lum_fil).mean()), 3))


class Budget:
    def __init__(self, seconds):
        self.t0 = time.monotonic()
        self.seconds = seconds

    def left(self):
        return self.seconds - (time.monotonic() - self.t0)


def append_jsonl(p, rec):
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
