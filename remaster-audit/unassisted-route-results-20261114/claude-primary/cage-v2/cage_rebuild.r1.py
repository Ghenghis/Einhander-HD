#!/usr/bin/env python3
"""95A3BCF8 region C (barred window cage), palette 857DB48E: mean-exact edge-aware rebuild (claude-einhander), r1.
r1 (CG2 failure 18:04:55Z, preserved at frozen/95A3BCF8-C-cage-v1 without a marker): the builder copy in a frozen set
is made with shutil.copyfile, not copy2, so a read-only source no longer makes the durability fsync fail; the set
name is 95A3BCF8-C-cage-v2. Algorithm, bindings and gates are unchanged from r0 (f8d42501).
CPU only, below normal, one logical CPU, threads 1 (set before numpy is imported). No GPU, no ComfyUI, no generated
imagery, no fonts. Versioned file: a later revision is a NEW file cage_rebuild.rN.py; this one never changes.

Why: C_barred_window_cage (uv [64,0]-[112,64]) is drawn in Stage 1 only with palette 857DB48E (148 draws, all
semi -1, t3-green-lights draw-census). The live parent page (frozen-w3-lit-v1, sha 59e799b4, unchanged in root's
eight-ROI candidate 903bd84a) came from a smoothed upscale: the bright bars (index 0) average 71 levels too dark,
the saturated blue lit panels (index 5) 67 levels off, and the texel-cell mean error reaches 196. 490 of the 506
STP-black void texels carry alpha 127 instead of their native class 255 and 16 blocks have non-uniform alpha. The
region is an inverted lattice (no wall index), so the ramp-window builder window_ramp_rebuild.r1.py does not apply.

Rebuild (ROI = region bbox x 8 px), palette 857DB48E:
  * Void texels (colour exactly black; here index 15, STP black) keep the exact native colour, uniform per block.
  * Every other texel is rendered as an edge-aware bilinear field of NATIVE COLOURS between texel centres. A
    neighbour contributes only if it lies inside the region, is not void, and its colour differs from the texel's
    own colour by less than TAU (max over channels). Larger steps (bars against shadows, panels against bars,
    anything against a void) stay crisp; small steps (glow gradient, dithered wall) are smoothed. A diagonal
    neighbour also needs both edge neighbours.
  * Per texel block and channel the block MEAN is made exactly the native colour: an additive pass, then a
    headroom-proportional residual that cannot clip, then exact-sum rounding to 8 bits (block sum = 64 x colour).
    No texel is added, removed or moved, and every block mean is its native palette colour.
  * ALPHA = the native class of each texel (127 opaque, 255 STP), uniform per block, inside the ROI only.
  * Every pixel outside the ROI is byte-identical to the parent.

Bindings checked before any output: indices-256 equals the decoded stock words (all 16,384 valid, 4-bit, low nibble
first); the raw CLUT decodes to palettes.json; no CLUT entry is raw 0x0000 (no transparent class); classes are within
{127, 255}; the region bbox equals regions.json; the draw census binds the key to region C only and region C to this
palette only, with uv_union inside the bbox; the parent is RGBA 2048x2048. --freeze also requires the parent sha256
prefix recorded below.

Outputs:
  --preview OUTDIR   region-only RGBA render, review sheets and preview-stats.json in OUTDIR (must not exist); no page.
  --freeze           frozen/95A3BCF8-C-cage-v2 next to this file (exist_ok=False; one region, manifest.region in the
                     ROI composer's format, keys[key].live = parent):
      page2048/95A3BCF8-857DB48E.png  the parent with ONLY the ROI RGBA replaced;
      review/C-857DB48E-review.png    native x8 | current | new, raw and x2.5 brightened, box views at 1/2 and 1/4;
      review/C-857DB48E-alpha.png     native class | current alpha | new alpha | current centre mismatches;
      manifest.json, validation.json, SHA256SUMS.txt, a copy of this builder, and READY.json (all gates pass) or
      FAILED.json (any gate fails). Every file is fsynced and re-hashed against SHA256SUMS before the marker."""
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

REVISION = "r1"
HERE = Path(__file__).resolve().parent
T3 = Path("C:/github/Einhander/remaster-audit/comfy-authoring/t3-green-lights")
IDX = T3 / "indices-256.npy"
PALS = T3 / "palettes.json"
REGJ = T3 / "regions.json"
CENSUS = T3 / "draw-census.json"
SRC = T3 / "frozen/atlas-95A3BCF8-t3-v1/source"
LIVE = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/pack/"
            "einhander-texture-replacements")
ATLAS = "95A3BCF8"
REGION = dict(R="C", id="C_barred_window_cage", bbox=(64, 0, 112, 64), palette="857DB48E",
              parent_sha256_prefix="59e799b4")
NAME = "95A3BCF8-C-cage-v2"
S = 8
PAGE = 256 * S
TAU = 64.0                   # max-channel colour step below which neighbouring texels are smoothed
CLASSES_ALLOWED = {127, 255}
GATES = ("readback_equals_written", "outside_roi_identical_to_parent", "centre_alpha_equals_native_class",
         "alpha_uniform_per_block", "block_sums_equal_native_exactly", "void_blocks_exact_native",
         "rounding_in_range")
LUMA = np.array([0.299, 0.587, 0.114])


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pin():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    return dict(priority=int(me.nice()), affinity=me.cpu_affinity(), threads_env=os.environ.get("OMP_NUM_THREADS"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def up(a, s=S):
    return np.repeat(np.repeat(a, s, axis=0), s, axis=1)


def roi_slices(bbox, s=S):
    u0, v0, u1, v1 = bbox
    return slice(v0 * s, v1 * s), slice(u0 * s, u1 * s)


# ---------------------------------------------------------------- native bindings

def decode_words(words):
    """4-bit page: 64 uint16 words per row, 4 texels per word, low nibble = leftmost texel."""
    w = np.asarray(words, np.uint16).reshape(256, 64)
    out = np.empty((256, 256), np.uint8)
    for k in range(4):
        out[:, k::4] = (w >> (4 * k)) & 15
    return out


def decode_clut(raw):
    """PS1 15-bit colour words: R bits 0-4, G 5-9, B 10-14 (x8 to 8 bits), STP bit 15."""
    raw = np.asarray(raw, np.uint16).astype(np.int64)
    rgb = np.stack([(raw & 31) << 3, ((raw >> 5) & 31) << 3, ((raw >> 10) & 31) << 3], axis=-1)
    return rgb, ((raw >> 15) & 1).astype(bool)


def class_of(pal):
    return np.array([0 if (r == 0 and g == 0 and b == 0 and not s) else (255 if s else 127)
                     for (r, g, b), s in zip(pal["rgb"], pal["stp"])], np.uint8)


def palette_classes(pk, pal, clut_raw=None):
    """Native class per CLUT entry. Refuses classes outside {127, 255} and, when the raw CLUT is given, any raw
    0x0000 entry (transparent) or a decode that differs from palettes.json."""
    rgb = np.array(pal["rgb"], np.int64)
    stp = np.array(pal["stp"]).astype(bool)
    if rgb.shape != (16, 3) or stp.shape != (16,):
        raise RuntimeError(f"{pk}: palette shapes rgb {rgb.shape} stp {stp.shape}")
    cls = class_of(pal)
    classes = sorted(set(cls.tolist()))
    if not set(classes) <= CLASSES_ALLOWED:
        raise RuntimeError(f"{pk}: native classes {classes} not within {sorted(CLASSES_ALLOWED)}")
    if clut_raw is not None:
        raw = np.asarray(clut_raw, np.uint16)
        if raw.shape != (16,):
            raise RuntimeError(f"{pk}: CLUT shape {raw.shape}")
        zero = [i for i in range(16) if int(raw[i]) == 0]
        if zero:
            raise RuntimeError(f"{pk}: raw-0x0000 (transparent) CLUT entries {zero}")
        drgb, dstp = decode_clut(raw)
        if not (np.array_equal(drgb, rgb) and np.array_equal(dstp, stp)):
            raise RuntimeError(f"{pk}: raw CLUT decode differs from palettes.json")
    return cls


def load_native(pk, idx):
    def sp(ext):
        return SRC / f"{ATLAS}-{pk}.{ext}"
    meta = json.loads(sp("source.json").read_text(encoding="utf-8"))
    require(meta.get("key") == f"{ATLAS}-{pk}", f"{pk}: source key {meta.get('key')}")
    require(meta.get("width_words") == 64 and meta.get("height") == 256 and meta.get("depth") == 0,
            f"{pk}: not a 4-bit 64x256-word page: {meta}")
    require(meta.get("known_words") == meta.get("total_words") == 16384, f"{pk}: words known/total {meta}")
    words = np.fromfile(sp("words.bin"), dtype="<u2")
    valid = np.fromfile(sp("valid.bin"), dtype=np.uint8)
    clut = np.fromfile(sp("clut.bin"), dtype="<u2")
    require(words.size == 16384 and valid.size == 16384 and clut.size == 16,
            f"{pk}: sizes words {words.size} valid {valid.size} clut {clut.size}")
    require(bool((valid == 1).all()), f"{pk}: {int((valid != 1).sum())} invalid stock words")
    dec = decode_words(words)
    require(np.array_equal(dec, idx), f"{pk}: stock words differ from indices-256 at {int((dec != idx).sum())} texels")
    return clut, dict(words=int(words.size), words_valid=int(valid.sum()), indices_equal_indices256=True,
                      clut_raw_hex=[f"{int(w):04X}" for w in clut], frame=meta.get("frame"),
                      clut_xy=meta.get("clut_xy"), files={e: dict(path=str(sp(e)), sha256=sha(sp(e)))
                                                          for e in ("words.bin", "valid.bin", "clut.bin", "source.json")})


def load_parent(path):
    with Image.open(path) as im:
        mode, size = im.mode, im.size
        if mode != "RGBA" or size != (PAGE, PAGE):
            raise RuntimeError(f"{path}: parent mode {mode} size {size}, expected RGBA {PAGE}x{PAGE}")
        arr = np.array(im)
    require(arr.dtype == np.uint8 and arr.shape == (PAGE, PAGE, 4), f"parent array {arr.shape} {arr.dtype}")
    return arr, dict(path=str(path), sha256=sha(path), mode=mode, shape=list(arr.shape))


def prepare(idx, pals, regj, census):
    """All bindings for region C; refuses before any output is written."""
    reg = REGION
    pk, bbox = reg["palette"], tuple(reg["bbox"])
    key = f"{ATLAS}-{pk}"
    rj = {r["id"]: tuple(r["bbox"]) for r in regj}
    require(rj.get(reg["id"]) == bbox, f"{reg['id']}: regions.json bbox {rj.get(reg['id'])} != {bbox}")
    rp = census[ATLAS]["region_palettes"].get(reg["id"], {})
    require(set(rp) == {pk}, f"{reg['id']}: census palettes {sorted(rp)} != [{pk}]")
    pc = census[ATLAS]["per_key"].get(key)
    require(pc is not None and set(pc.get("regions", {})) == {reg["id"]},
            f"{key}: census regions {None if pc is None else sorted(pc.get('regions', {}))} != [{reg['id']}]")
    uv = pc["uv_union"]
    u0, v0, u1, v1 = bbox
    require(u0 <= uv[0] and v0 <= uv[1] and uv[2] <= u1 and uv[3] <= v1, f"{key}: uv_union {uv} outside {bbox}")
    require(pk in pals, f"{pk}: palette missing from palettes.json")
    clut, native = load_native(pk, idx)
    cls = palette_classes(pk, pals[pk], clut)
    P = np.array(pals[pk]["rgb"], np.int64)
    O = idx[v0:v1, u0:u1].astype(np.int64)
    parent, pinfo = load_parent(LIVE / f"{key}.png")
    return dict(R=reg["R"], region_id=reg["id"], key=key, palette=pk, bbox=bbox, O=O, cls=cls, P=P,
                void=void_mask(O, P), parent=parent, parent_info=pinfo, native=native,
                census=dict(region_draws=rp[pk], draws=pc.get("draws"), uv_union=uv, semi=pc.get("semi"),
                            max_quad_area=pc.get("max_quad_area"), median_quad_area=pc.get("median_quad_area"),
                            top_uv=pc.get("top_uv")))


# ---------------------------------------------------------------- rebuild

def void_mask(O, P):
    """Texels whose native colour is exactly black (STP black here). They are kept exact and never blended."""
    black = np.all(np.asarray(P) == 0, axis=1)
    return black[O]


def render_field(O, P, void, s=S, tau=TAU):
    """Float RGB (H*s, W*s, 3): edge-aware bilinear field of native colours, before mean correction. A neighbour
    counts only if it is inside the region, not void, and max|colour step| < tau; diagonals also need both edge
    neighbours. Void texels are their exact colour."""
    O = np.asarray(O)
    H, W = O.shape
    col = np.asarray(P, np.float64)[O]
    Cp = np.pad(col, ((1, 1), (1, 1), (0, 0)))
    Ip = np.pad(~void, 1, constant_values=False)
    f = (np.arange(s) + 0.5) / s
    t = np.abs(f - 0.5)
    d = np.where(f < 0.5, -1, 1)
    ys, xs = np.arange(H * s), np.arange(W * s)
    R, Cc = (ys // s + 1)[:, None], (xs // s + 1)[None, :]
    DY, DX = d[ys % s][:, None], d[xs % s][None, :]
    TY, TX = t[ys % s][:, None], t[xs % s][None, :]
    own = Cp[R, Cc]
    hn, vn, dn = Cp[R, Cc + DX], Cp[R + DY, Cc], Cp[R + DY, Cc + DX]
    ok_h = Ip[R, Cc + DX] & (np.abs(hn - own).max(-1) < tau)
    ok_v = Ip[R + DY, Cc] & (np.abs(vn - own).max(-1) < tau)
    ok_d = Ip[R + DY, Cc + DX] & (np.abs(dn - own).max(-1) < tau) & ok_h & ok_v
    ws = (1 - TX) * (1 - TY)
    wh, wv, wd = TX * (1 - TY) * ok_h, (1 - TX) * TY * ok_v, TX * TY * ok_d
    F = (ws[..., None] * own + wh[..., None] * hn + wv[..., None] * vn + wd[..., None] * dn) \
        / (ws + wh + wv + wd)[..., None]
    vpx = up(void, s)
    F[vpx] = own[vpx]
    return F


def edge_stats(O, P, void, tau=TAU):
    """Counts of 4-neighbour texel edges inside the region that are smoothed vs kept crisp."""
    c = np.asarray(P, np.float64)[O]
    out = {}
    for name, a, b, va, vb in (("horizontal", c[:, 1:], c[:, :-1], void[:, 1:], void[:, :-1]),
                               ("vertical", c[1:, :], c[:-1, :], void[1:, :], void[:-1, :])):
        same = np.abs(a - b).max(-1) == 0
        smooth = ~va & ~vb & (np.abs(a - b).max(-1) < tau) & ~same
        crisp_step = ~va & ~vb & (np.abs(a - b).max(-1) >= tau)
        void_edge = (va ^ vb)
        out[name] = dict(identical=int(same.sum()), smoothed=int(smooth.sum()), crisp_colour_step=int(crisp_step.sum()),
                         crisp_void_border=int(void_edge.sum()))
    return out


def mean_exact(F, O, P, void, s=S):
    """Per texel block and channel: additive pass, then a headroom-proportional residual (cannot clip).
    Float result whose block means equal the native colour (to float precision). Void blocks are exact."""
    H, W = O.shape
    blk = np.asarray(F, np.float64).reshape(H, s, W, s, 3).copy()
    tgt = np.asarray(P, np.float64)[O]
    blk = np.clip(blk + (tgt - blk.mean(axis=(1, 3)))[:, None, :, None, :], 0, 255)
    resid = tgt - blk.mean(axis=(1, 3))
    room = np.where(resid[:, None, :, None, :] > 0, 255.0 - blk, blk)
    tot = room.sum(axis=(1, 3))
    lam = np.where(tot > 0, resid * (s * s) / np.where(tot > 0, tot, 1.0), 0.0)
    blk = np.clip(blk + room * lam[:, None, :, None, :], 0, 255)
    blk = np.where(void[:, None, :, None, None], tgt[:, None, :, None, :], blk)
    return blk.reshape(H * s, W * s, 3)


def round_exact(X, O, P, s=S):
    """8-bit rounding with an exact block sum: floor, then +1 on the k pixels with the largest fractions, where
    k = 64 x colour - sum(floor) per block and channel (stable order: ties by raster position)."""
    H, W = O.shape
    n = s * s
    blk = np.asarray(X, np.float64).reshape(H, s, W, s, 3).transpose(0, 2, 4, 1, 3).reshape(H, W, 3, n)
    fl = np.floor(blk)
    fr = blk - fl
    tgt = np.asarray(P, np.int64)[O][..., None] * n
    k = np.rint(tgt - fl.sum(-1, keepdims=True)).astype(np.int64)
    order = np.argsort(-fr, axis=-1, kind="stable")
    rank = np.argsort(order, axis=-1, kind="stable")
    out = fl + (rank < k)
    out = out.reshape(H, W, 3, s, s).transpose(0, 3, 1, 4, 2).reshape(H * s, W * s, 3)
    return np.clip(out, 0, 255).astype(np.uint8), int(((out < 0) | (out > 255)).sum())


def render_roi(O, P, cls, void, s=S, tau=TAU):
    F = render_field(O, P, void, s, tau)
    X = mean_exact(F, O, P, void, s)
    rgb, out_of_range = round_exact(X, O, P, s)
    alpha = up(np.asarray(cls)[O].astype(np.uint8), s)
    st = dict(tau=tau, edges=edge_stats(O, P, void, tau), rounding_out_of_range=out_of_range,
              void_texels=int(void.sum()), texels=int(O.size),
              field_pre_correction_cell_mean_max_abs=round(float(np.abs(
                  F.reshape(O.shape[0], s, O.shape[1], s, 3).mean(axis=(1, 3)) - np.asarray(P)[O]).max()), 3))
    return np.dstack([rgb, alpha]).astype(np.uint8), st


def apply_page(parent, bbox, roi_rgba, s=S):
    require(parent.ndim == 3 and parent.shape[2] == 4 and parent.dtype == np.uint8,
            f"parent shape {parent.shape} {parent.dtype}")
    u0, v0, u1, v1 = bbox
    require(roi_rgba.shape == ((v1 - v0) * s, (u1 - u0) * s, 4), f"ROI {roi_rgba.shape} != bbox {bbox} x{s}")
    require(0 <= u0 < u1 and 0 <= v0 < v1 and u1 * s <= parent.shape[1] and v1 * s <= parent.shape[0],
            f"ROI {bbox} x{s} outside parent {parent.shape}")
    page = parent.copy()
    page[roi_slices(bbox, s)] = roi_rgba
    return page


# ---------------------------------------------------------------- statistics and gates

def cell_stats(rgb, O, P, s=S):
    H, W = O.shape
    m = np.asarray(rgb, np.float64).reshape(H, s, W, s, 3).mean(axis=(1, 3))
    dd = np.abs(m - np.asarray(P, np.float64)[O]).max(-1)
    per_index = {}
    for i in np.unique(O):
        sel = O == i
        per_index[int(i)] = dict(texels=int(sel.sum()), mean=round(float(dd[sel].mean()), 3),
                                 max=round(float(dd[sel].max()), 3))
    return dict(max_abs=round(float(dd.max()), 4), mean_abs=round(float(dd.mean()), 4),
                cells_over_2=int((dd > 2).sum()), cells_over_16=int((dd > 16).sum()),
                cells_over_32=int((dd > 32).sum()), per_index=per_index)


def alpha_stats(alpha, O, cls, s=S):
    H, W = O.shape
    C = np.asarray(cls)[O]
    cen = alpha[s // 2::s, s // 2::s][:H, :W]
    blk = alpha.reshape(H, s, W, s)
    mism = cen != C
    pairs = {}
    for c, a in zip(C[mism].tolist(), cen[mism].tolist()):
        pairs[f"{c}->{a}"] = pairs.get(f"{c}->{a}", 0) + 1
    return dict(texels=int(H * W), centre_class_mismatches=int(mism.sum()),
                mismatch_native_to_centre_alpha=dict(sorted(pairs.items())),
                nonuniform_alpha_blocks=int((blk.min(axis=(1, 3)) != blk.max(axis=(1, 3))).sum()))


def validate(parent, written, readback, bbox, O, P, cls, void, rebuild_stats, s=S):
    """rebuild_stats: render_roi() stats; rounding_in_range needs rounding_out_of_range == 0 there."""
    if not (parent.shape == written.shape == readback.shape and parent.dtype == written.dtype == readback.dtype
            == np.uint8 and parent.ndim == 3 and parent.shape[2] == 4):
        return {g: False for g in GATES}, dict(shapes=[list(a.shape) for a in (parent, written, readback)],
                                               dtypes=[str(a.dtype) for a in (parent, written, readback)])
    H, W = O.shape
    roi = roi_slices(bbox, s)
    outside = np.ones(parent.shape[:2], bool)
    outside[roi] = False
    r = readback[roi]
    ast = alpha_stats(r[..., 3], O, cls, s)
    sums = r[..., :3].astype(np.int64).reshape(H, s, W, s, 3).sum(axis=(1, 3))
    tgt = np.asarray(P, np.int64)[O] * (s * s)
    sum_bad = int((sums != tgt).any(-1).sum())
    blk = r[..., :3].reshape(H, s, W, s, 3)
    void_bad = int(((blk.min(axis=(1, 3)) != blk.max(axis=(1, 3))).any(-1) & void).sum()
                   + ((sums != tgt).any(-1) & void).sum())
    out_diff = int((readback[outside] != parent[outside]).any(-1).sum())
    gates = dict(readback_equals_written=bool(np.array_equal(readback, written)),
                 outside_roi_identical_to_parent=out_diff == 0,
                 centre_alpha_equals_native_class=ast["centre_class_mismatches"] == 0,
                 alpha_uniform_per_block=ast["nonuniform_alpha_blocks"] == 0,
                 block_sums_equal_native_exactly=sum_bad == 0,
                 void_blocks_exact_native=void_bad == 0,
                 rounding_in_range=(rebuild_stats or {}).get("rounding_out_of_range") == 0)
    details = dict(roi_alpha=ast, outside_pixels=int(outside.sum()), outside_differing_pixels=out_diff,
                   blocks_with_sum_error=sum_bad, void_blocks_not_exact=void_bad,
                   readback_differing_pixels=int((readback != written).any(-1).sum()),
                   new_cells=cell_stats(r[..., :3], O, P, s),
                   roi_rgb_changed_pixels_vs_parent=int((r[..., :3] != parent[roi][..., :3]).any(-1).sum()),
                   roi_alpha_changed_pixels_vs_parent=int((r[..., 3] != parent[roi][..., 3]).sum()))
    return gates, details


# ---------------------------------------------------------------- review sheets

def gray(a):
    return np.dstack([a, a, a]).astype(np.uint8)


def bright(a, k=2.5):
    return np.clip(np.rint(a.astype(np.float64) * k), 0, 255).astype(np.uint8)


def box(a, f):
    h, w = a.shape[:2]
    return np.asarray(Image.fromarray(np.ascontiguousarray(a)).resize((w // f, h // f), Image.BOX))


def sheet(dst, title, rows):
    pad, lab = 8, 14
    tw = max(sum(t.shape[1] for _, t in row) + pad * (len(row) + 1) for row in rows)
    th = lab + pad + sum(max(t.shape[0] for _, t in row) + lab + pad for row in rows) + pad
    img = Image.new("RGB", (max(tw, 6 * len(title) + 2 * pad), th), (30, 30, 30))
    dr = ImageDraw.Draw(img)
    dr.text((pad, pad // 2), title, fill=(255, 255, 255))
    y = lab + pad
    for row in rows:
        x = pad
        for label, t in row:
            dr.text((x, y), label, fill=(255, 255, 0))
            img.paste(Image.fromarray(np.ascontiguousarray(t)), (x, y + lab))
            x += t.shape[1] + pad
        y += max(t.shape[0] for _, t in row) + lab + pad
    img.save(dst, format="PNG")


def review_sheets(ctx, cur, new, review_dst, alpha_dst, s=S):
    O, P, cls = ctx["O"], ctx["P"], ctx["cls"]
    nat = up(P[O].astype(np.uint8), s)
    title = f"{ctx['key']} {ctx['region_id']} bbox {list(ctx['bbox'])} cage_rebuild {REVISION} tau {TAU:g}"
    sheet(review_dst, title, [
        [("native x8", nat), ("current", cur[..., :3]), ("new", new[..., :3])],
        [("native x2.5 bright", bright(nat)), ("current x2.5", bright(cur[..., :3])), ("new x2.5", bright(new[..., :3]))],
        [("native box 1/2", box(nat, 2)), ("current box 1/2", box(cur[..., :3], 2)), ("new box 1/2", box(new[..., :3], 2)),
         ("native box 1/4", box(nat, 4)), ("current box 1/4", box(cur[..., :3], 4)), ("new box 1/4", box(new[..., :3], 4))]])
    C = cls[O]
    cen = cur[..., 3][s // 2::s, s // 2::s]
    mism = up(np.where((cen != C)[..., None], np.array([255, 0, 0], np.uint8), np.array([0, 0, 0], np.uint8)), s)
    sheet(alpha_dst, title + " alpha", [[("native class", gray(up(C.astype(np.uint8), s))), ("current alpha", gray(cur[..., 3])),
                                         ("new alpha", gray(new[..., 3])), ("cur centre mismatch", mism)]])


# ---------------------------------------------------------------- modes

def save_png(arr, path):
    Image.fromarray(np.ascontiguousarray(arr)).save(path, format="PNG", compress_level=6)


def read_png(path):
    with Image.open(path) as im:
        return np.array(im)


def fsync_write(path, text):
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def preview(ctx, outdir, pinned):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=False)
    roi = roi_slices(ctx["bbox"])
    cur = ctx["parent"][roi]
    new, st = render_roi(ctx["O"], ctx["P"], ctx["cls"], ctx["void"])
    page = apply_page(ctx["parent"], ctx["bbox"], new)
    gates, det = validate(ctx["parent"], page, page, ctx["bbox"], ctx["O"], ctx["P"], ctx["cls"], ctx["void"], st)
    save_png(new, outdir / f"C-{ctx['palette']}-roi.png")
    review_sheets(ctx, cur, new, outdir / f"C-{ctx['palette']}-review.png", outdir / f"C-{ctx['palette']}-alpha.png")
    rep = dict(tool=str(Path(__file__)), revision=REVISION, builder_sha256=sha(Path(__file__)), mode="preview",
               wrote_pages=False, pin=pinned, region=ctx["region_id"], key=ctx["key"], bbox=list(ctx["bbox"]),
               classes=ctx["cls"].tolist(), census=ctx["census"], native=ctx["native"],
               parent=dict(ctx["parent_info"], expected_sha256_prefix=REGION["parent_sha256_prefix"],
                           sha256_prefix_matches=ctx["parent_info"]["sha256"].startswith(REGION["parent_sha256_prefix"])),
               current=dict(cells=cell_stats(cur[..., :3], ctx["O"], ctx["P"]),
                            roi_alpha=alpha_stats(cur[..., 3], ctx["O"], ctx["cls"])),
               rebuild=st, gates_in_memory=gates, gate_details=det,
               roi_png_sha256=sha(outdir / f"C-{ctx['palette']}-roi.png"))
    fsync_write(outdir / "preview-stats.json", json.dumps(rep, indent=1) + "\n")
    print(json.dumps(dict(out=str(outdir), gates=gates, current_max=rep["current"]["cells"]["max_abs"],
                          new_max=det.get("new_cells", {}).get("max_abs")), indent=1))
    return 0 if all(gates.values()) else 1


def freeze(ctx, F, meta, s=S, builder=None):
    """Writes the frozen candidate into F (must not exist). Returns 0 on READY, 1 on FAILED."""
    import datetime
    import shutil
    builder = Path(__file__) if builder is None else Path(builder)
    F = Path(F)
    F.parent.mkdir(parents=True, exist_ok=True)
    F.mkdir(exist_ok=False)
    for sub in ("page2048", "review"):
        (F / sub).mkdir()
    key, pk = ctx["key"], ctx["palette"]
    roi = roi_slices(ctx["bbox"], s)
    cur = ctx["parent"][roi]
    new, st = render_roi(ctx["O"], ctx["P"], ctx["cls"], ctx["void"], s)
    page = apply_page(ctx["parent"], ctx["bbox"], new, s)
    out = F / "page2048" / f"{key}.png"
    save_png(page, out)
    rb = read_png(out)
    gates, det = validate(ctx["parent"], page, rb, ctx["bbox"], ctx["O"], ctx["P"], ctx["cls"], ctx["void"], st, s)
    ok = all(gates.values()) and bool(gates)
    review_sheets(ctx, cur, rb[roi], F / "review" / f"C-{pk}-review.png", F / "review" / f"C-{pk}-alpha.png", s)
    val = dict(passed=ok, gates=list(GATES), checks={key: gates},
               keys={key: dict(gates=gates, details=det, rebuild=st,
                               current=dict(cells=cell_stats(cur[..., :3], ctx["O"], ctx["P"], s),
                                            roi_alpha=alpha_stats(cur[..., 3], ctx["O"], ctx["cls"], s)))})
    (F / "validation.json").write_text(json.dumps(val, indent=1) + "\n", encoding="utf-8")
    u0, v0, u1, v1 = ctx["bbox"]
    doc = __doc__
    man = dict(
        name=F.name, revision=REVISION,
        status="candidate (private; not integrated, not live-tested)" if ok else "FAILED validation (preserved)",
        owner="claude-einhander",
        region=f"{ctx['region_id']} uv [{u0},{v0}]-[{u1},{v1}] half-open (t3-green-lights/regions.json)",
        gpu="none: CPU-only deterministic rebuild from native palette colours; no generated imagery",
        why=doc.split("Why: ", 1)[1].split("Rebuild (ROI", 1)[0].strip(),
        method=doc.split("Rebuild (ROI = region bbox x 8 px), palette 857DB48E:", 1)[1].split(
            "Bindings checked", 1)[0].strip(" :\n"),
        bindings=doc.split("Bindings checked before any output: ", 1)[1].split("Outputs:", 1)[0].strip(),
        params=dict(px_per_texel=s, tau=TAU, classes_allowed=sorted(CLASSES_ALLOWED), gates=list(GATES)),
        keys={key: dict(region=ctx["region_id"], bbox=list(ctx["bbox"]), census=ctx["census"],
                        parent=ctx["parent_info"],
                        live=dict(path=ctx["parent_info"]["path"], sha256=ctx["parent_info"]["sha256"]),
                        native=ctx["native"], classes=ctx["cls"].tolist())},
        validation_passed=ok,
        integration="ROI-only: overlay the region ROI (RGBA) of page2048 onto the same parent page; every other pixel "
                    "is the parent's, byte for byte.",
        known_limits=[
            "correctness candidate: every texel block mean is the native colour; within-block detail is only the "
            "edge-aware interpolation of native colours (no authored HD texture, no bevel)",
            "the STP class (255) of void texels is restored, but all 148 Stage 1 draws are semi -1, so STP is "
            "expected to be inert there (not verified live)",
            "the 84 other parent pages that contain region C are not touched (no Stage 1 draws)",
            "SIMULATION only: not integrated, not seen live"],
        sources=meta.get("sources", {}), pin=meta.get("pin"),
        built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (F / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    shutil.copyfile(builder, F / builder.name)        # r1: no attribute copy (read-only source)
    files = sorted(p for p in F.rglob("*") if p.is_file())
    for p in files:
        with open(p, "rb+") as fh:
            os.fsync(fh.fileno())
    sums = [f"{sha(p)}  {p.relative_to(F).as_posix()}" for p in files]
    (F / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    with open(F / "SHA256SUMS.txt", "rb+") as fh:
        os.fsync(fh.fileno())
    for line in (F / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        b = (F / rel).read_bytes()
        require(hashlib.sha256(b).hexdigest() == h, f"read-back mismatch {rel}")
        require(not (b and b.count(0) == len(b)), f"all-NUL {rel}")
    status = dict(name=F.name, revision=REVISION, validation_passed=ok, files=len(sums),
                  sha256sums=sha(F / "SHA256SUMS.txt"), manifest_sha256=sha(F / "manifest.json"),
                  durability="every file fsynced and re-hashed",
                  failed_checks=[n for n, g in gates.items() if not g], status=man["status"],
                  at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    marker = F / ("READY.json" if ok else "FAILED.json")
    fsync_write(marker, json.dumps(status, indent=1) + "\n")
    print(json.dumps(dict(marker=marker.name, marker_sha256=sha(marker), status=status,
                          page2048=sha(out), checks=gates), indent=1))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview", type=Path)
    g.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    pinned = pin()
    idx = np.load(IDX)
    require(idx.shape == (256, 256), f"index map shape {idx.shape}")
    pals = json.loads(PALS.read_text(encoding="utf-8"))
    regj = json.loads(REGJ.read_text(encoding="utf-8"))
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    ctx = prepare(idx, pals, regj, census)
    if a.preview:
        return preview(ctx, a.preview, pinned)
    pre = REGION["parent_sha256_prefix"]
    require(ctx["parent_info"]["sha256"].startswith(pre),
            f"{ctx['key']}: parent sha256 {ctx['parent_info']['sha256']} does not start with {pre}")
    srcs = dict(indices=IDX, palettes=PALS, regions=REGJ, census=CENSUS, builder=Path(__file__))
    meta = dict(pin=pinned, sources={k: dict(path=str(p), sha256=sha(p)) for k, p in srcs.items()})
    return freeze(ctx, HERE / "frozen" / NAME, meta)


if __name__ == "__main__":
    raise SystemExit(main())
