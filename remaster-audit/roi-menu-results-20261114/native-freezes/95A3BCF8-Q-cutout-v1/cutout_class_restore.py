#!/usr/bin/env python3
"""95A3BCF8 regions P (antenna tower) and Q (ladder and tank): native cut-out class restore (claude-einhander), r1.
r1 (parent review of r0 8e5f5f0d): pixels that the parent hid (alpha 0) inside natively OPAQUE texels are revealed
when the class is restored. Their RGB is filled from that block's visible pixels, or the native palette colour if the
block had none, instead of showing invisible parent filler (Q: 275 near-black px, P: 5 px). The opaque-RGB gate now
covers the pixels the parent showed; revealed pixels are counted.
CPU only, below normal, one logical CPU, threads 1 (set before numpy is imported). No GPU, no ComfyUI, no generated
imagery, no re-authored opaque colour.

Why: atlas 95A3BCF8 is a 4-bit native page. P_antenna_tower is drawn only with palette 397FBE8A and Q_ladder_and_tank
only with palette 79B18A47 (t3-green-lights draw-census). In both palettes CLUT entry 15 is raw 0x0000, the only
transparent entry; every other entry is opaque (class 127, no STP). The live parent pages (frozen-w3-lit-v1) came
from a smoothed float index field, so index 15 rounded to 14 at many cut-out texels. Those texels are opaque
(alpha 127) with dark RGB where the native art is see-through.

Restore, per region and palette (ROI = region bbox x 8 px):
  * ALPHA = the native class of each texel (0 transparent, 127 opaque), uniform per 8x8 block, inside the ROI only.
    Classes outside {0, 127}, or a transparent set other than exactly CLUT entry 15 (by palettes.json and by the raw
    stock CLUT words), are refused.
  * Opaque texels keep the parent RGB exactly for every pixel the parent showed. Nothing is re-authored. Pixels the
    parent hid (alpha 0) inside an opaque texel take the mean of the block's visible pixels, or the native colour.
  * Transparent texels get an edge-fill RGB, so bilinear filtering at cut-out edges shows no dark fringe. A texel's
    colour is the mean RGB of its 8x8 parent block. A layer-synchronous breadth-first dilation over the ROI texel
    grid starts at the opaque texels; each transparent texel takes the mean of its 4-neighbours assigned in earlier
    layers. Texels unreachable within the ROI take the ROI's mean opaque colour. Each block is filled uniformly
    (rounded to 8 bits).
  * Every pixel outside the ROI is byte-identical to the parent.

Bindings checked before any output: indices-256 equals the decoded stock words (all 16,384 valid, 4-bit, low nibble
first); the raw CLUT decodes to palettes.json; region bboxes equal regions.json; the draw census binds each key to
its region only, with uv_union inside the bbox; each parent is RGBA 2048x2048. --freeze also requires the parent
sha256 prefix recorded below.

Outputs:
  --check --report PATH   decode the two parents and write a JSON stats report to PATH (must not exist); no pages.
  --freeze                frozen/95A3BCF8-P-cutout-v1 and frozen/95A3BCF8-Q-cutout-v1 next to this file (each
                          exist_ok=False; one region per set, manifest.region in the ROI composer's format):
      page2048/95A3BCF8-397FBE8A.png (P), page2048/95A3BCF8-79B18A47.png (Q): the parent with ONLY the ROI RGBA
                                                                             replaced;
      review/<R>-<palette>-review.png: native nearest x8 | current | new, as raw RGB, cut-out view and a bilinear
                                       x4 simulation over grey;
      review/<R>-<palette>-alpha.png:  native class x8 | current alpha | new alpha | current centre mismatches;
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
NAME = "95A3BCF8-PQ-cutout-v1"
S = 8
PAGE = 256 * S
TRANSPARENT_ENTRY = 15
CLASSES_ALLOWED = {0, 127}
REGIONS = {
    "P": dict(id="P_antenna_tower", bbox=(240, 112, 256, 176), palette="397FBE8A", parent_sha256_prefix="b0c419bb"),
    "Q": dict(id="Q_ladder_and_tank", bbox=(0, 128, 48, 192), palette="79B18A47", parent_sha256_prefix="5fd58547"),
}
GATES = ("readback_equals_written", "outside_roi_identical_to_parent", "centre_alpha_equals_native_class",
         "alpha_uniform_per_block", "opaque_rgb_identical_to_parent", "transparent_alpha_zero",
         "transparent_rgb_uniform_per_block")
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
    """Native class per CLUT entry. Refuses classes outside {0, 127} and any transparent set other than exactly
    {TRANSPARENT_ENTRY}, by palettes.json and (when given) by the raw CLUT words (raw 0x0000 = transparent)."""
    rgb = np.array(pal["rgb"], np.int64)
    stp = np.array(pal["stp"]).astype(bool)
    if rgb.shape != (16, 3) or stp.shape != (16,):
        raise RuntimeError(f"{pk}: palette shapes rgb {rgb.shape} stp {stp.shape}")
    cls = class_of(pal)
    classes = sorted(set(cls.tolist()))
    if not set(classes) <= CLASSES_ALLOWED:
        raise RuntimeError(f"{pk}: native classes {classes} not within {sorted(CLASSES_ALLOWED)}")
    tset = [i for i in range(16) if cls[i] == 0]
    if tset != [TRANSPARENT_ENTRY]:
        raise RuntimeError(f"{pk}: transparent entries {tset} (palettes.json) are not exactly [{TRANSPARENT_ENTRY}]")
    if clut_raw is not None:
        raw = np.asarray(clut_raw, np.uint16)
        if raw.shape != (16,):
            raise RuntimeError(f"{pk}: CLUT shape {raw.shape}")
        rset = [i for i in range(16) if int(raw[i]) == 0]
        if rset != [TRANSPARENT_ENTRY]:
            raise RuntimeError(f"{pk}: raw-0x0000 CLUT entries {rset} are not exactly [{TRANSPARENT_ENTRY}]")
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
    require(int(clut[TRANSPARENT_ENTRY]) == 0, f"{pk}: CLUT entry {TRANSPARENT_ENTRY} raw {int(clut[15]):04X} != 0000")
    return clut, dict(words=int(words.size), words_valid=int(valid.sum()), indices_equal_indices256=True,
                      clut_raw_hex=[f"{int(w):04X}" for w in clut], frame=meta.get("frame"),
                      clut_xy=meta.get("clut_xy"), files={e: dict(path=str(sp(e)), sha256=sha(sp(e)))
                                                          for e in ("words.bin", "valid.bin", "clut.bin", "source.json")})


def check_parent_array(arr, shape):
    if not (isinstance(arr, np.ndarray) and arr.dtype == np.uint8 and arr.shape == tuple(shape)):
        raise RuntimeError(f"parent shape/dtype {getattr(arr, 'shape', None)} {getattr(arr, 'dtype', None)}, "
                           f"expected {tuple(shape)} uint8")


def load_parent(path):
    with Image.open(path) as im:
        mode, size = im.mode, im.size
        if mode != "RGBA" or size != (PAGE, PAGE):
            raise RuntimeError(f"{path}: parent mode {mode} size {size}, expected RGBA {PAGE}x{PAGE}")
        arr = np.array(im)
    check_parent_array(arr, (PAGE, PAGE, 4))
    return arr, dict(path=str(path), sha256=sha(path), mode=mode, shape=list(arr.shape))


def prepare(R, idx, pals, regj, census):
    """All bindings for one region; refuses before any output is written."""
    reg = REGIONS[R]
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
    O = idx[v0:v1, u0:u1].astype(np.int64)
    parent, pinfo = load_parent(LIVE / f"{key}.png")
    return dict(R=R, region_id=reg["id"], key=key, palette=pk, bbox=bbox, O=O, C=cls[O].astype(np.uint8),
                classes=cls.tolist(), P_rgb=np.array(pals[pk]["rgb"], np.int64), parent=parent, parent_info=pinfo,
                native=native, census=dict(region_draws=rp[pk], draws=pc.get("draws"), uv_union=uv,
                                           semi=pc.get("semi"), max_quad_area=pc.get("max_quad_area")))


# ---------------------------------------------------------------- restore

def block_means(rgb, s=S):
    h, w = rgb.shape[0] // s, rgb.shape[1] // s
    return rgb.astype(np.float64).reshape(h, s, w, s, 3).mean(axis=(1, 3))


def edge_fill(C, means):
    """Layer-synchronous BFS dilation from opaque texels over the 4-neighbour texel grid, inside the ROI only."""
    H, W = C.shape
    opaque = C != 0
    if not opaque.any():
        raise RuntimeError("ROI has no opaque texel: edge fill is undefined")
    col = np.zeros((H, W, 3))
    col[opaque] = means[opaque]
    assigned = opaque.copy()
    depth = np.where(opaque, 0, -1)
    k = 0
    while True:
        k += 1
        Ap = np.pad(assigned, 1, constant_values=False)
        Cp = np.pad(col, ((1, 1), (1, 1), (0, 0)))
        nsum, ncnt = np.zeros((H, W, 3)), np.zeros((H, W))
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            a = Ap[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
            nsum += np.where(a[..., None], Cp[1 + dy:1 + dy + H, 1 + dx:1 + dx + W], 0.0)
            ncnt += a
        front = ~assigned & (ncnt > 0)
        if not front.any():
            break
        col[front] = nsum[front] / ncnt[front][:, None]
        assigned |= front
        depth[front] = k
    unreached = ~assigned
    fallback = means[opaque].mean(axis=0)
    col[unreached] = fallback
    hist = {int(d): int(n) for d, n in zip(*np.unique(depth[depth > 0], return_counts=True))}
    return col, depth, dict(texels=int(H * W), opaque=int(opaque.sum()), transparent=int((~opaque).sum()),
                            reached=int((depth > 0).sum()), unreachable=int(unreached.sum()),
                            max_depth=int(depth.max()), depth_histogram=hist,
                            roi_mean_opaque_rgb=[round(float(x), 3) for x in fallback])


def build_roi(cur, C, s=S, native_rgb=None):
    H, W = C.shape
    require(cur.shape == (H * s, W * s, 4) and cur.dtype == np.uint8, f"ROI shape {cur.shape} {cur.dtype}")
    means = block_means(cur[..., :3], s)
    fill, depth, st = edge_fill(C, means)
    fill8 = np.clip(np.rint(fill), 0, 255).astype(np.uint8)
    tpx = up(C == 0, s)
    new = cur.copy()
    new[..., :3] = np.where(tpx[..., None], up(fill8, s), cur[..., :3])
    # r1: pixels the parent hid (alpha 0) inside natively OPAQUE texels become visible once the class is restored.
    # Their parent RGB is invisible filler, so fill them from the block's visible pixels (else the native colour).
    hidden = ~tpx & (cur[..., 3] == 0)
    vis = (cur[..., 3] != 0).reshape(H, s, W, s)
    vcnt = vis.sum(axis=(1, 3))
    if hidden.any():
        rgbb = cur[..., :3].astype(np.float64).reshape(H, s, W, s, 3)
        vmean = (rgbb * vis[..., None]).sum(axis=(1, 3)) / np.maximum(vcnt, 1)[..., None]
        fb = native_rgb.astype(np.float64) if native_rgb is not None else means
        src8 = np.clip(np.rint(np.where((vcnt > 0)[..., None], vmean, fb)), 0, 255).astype(np.uint8)
        new[..., :3] = np.where(hidden[..., None], up(src8, s), new[..., :3])
    st["revealed_opaque_pixels"] = int(hidden.sum())
    st["revealed_opaque_blocks_without_visible_pixels"] = int(((vcnt == 0) & (C != 0)).sum())
    st["revealed_fallback"] = "native palette colour" if native_rgb is not None else "block mean"
    new[..., 3] = up(C, s)
    d1 = depth == 1
    if d1.any():
        st["depth1_current_block_mean_luma"] = round(float((means[d1] @ LUMA).mean()), 3)
        st["depth1_new_fill_luma"] = round(float((fill8[d1].astype(np.float64) @ LUMA).mean()), 3)
    return new, st


def apply_page(parent, bbox, C, s=S, native_rgb=None):
    require(parent.ndim == 3 and parent.shape[2] == 4 and parent.dtype == np.uint8,
            f"parent shape {parent.shape} {parent.dtype}")
    u0, v0, u1, v1 = bbox
    H, W = C.shape
    require((v1 - v0, u1 - u0) == (H, W), f"class map {C.shape} != bbox {bbox}")
    require(0 <= u0 < u1 and 0 <= v0 < v1 and u1 * s <= parent.shape[1] and v1 * s <= parent.shape[0],
            f"ROI {bbox} x{s} outside parent {parent.shape}")
    roi = roi_slices(bbox, s)
    new_roi, st = build_roi(parent[roi], C, s, native_rgb)
    page = parent.copy()
    page[roi] = new_roi
    return page, st


# ---------------------------------------------------------------- statistics and gates

def alpha_stats(alpha, C, s=S):
    H, W = C.shape
    require(alpha.shape == (H * s, W * s), f"alpha shape {alpha.shape}")
    cen = alpha[s // 2::s, s // 2::s]
    blk = alpha.reshape(H, s, W, s)
    nonuni = blk.min(axis=(1, 3)) != blk.max(axis=(1, 3))
    mism = cen != C
    pairs = {}
    for c, a in zip(C[mism].tolist(), cen[mism].tolist()):
        pairs[f"{c}->{a}"] = pairs.get(f"{c}->{a}", 0) + 1
    return dict(texels=int(H * W), transparent_texels=int((C == 0).sum()), opaque_texels=int((C != 0).sum()),
                centre_class_mismatches=int(mism.sum()),
                transparent_texels_not_zero_at_centre=int(((C == 0) & (cen != 0)).sum()),
                opaque_texels_wrong_at_centre=int(((C != 0) & mism).sum()),
                mismatch_native_to_centre_alpha=dict(sorted(pairs.items())),
                nonuniform_alpha_blocks=int(nonuni.sum()),
                nonuniform_alpha_blocks_transparent=int((nonuni & (C == 0)).sum()),
                nonuniform_alpha_blocks_opaque=int((nonuni & (C != 0)).sum()))


def current_rgb_stats(cur, C, P_rgb, s=S):
    """Centre RGB of natively transparent texels that the parent draws opaque, and its nearest palette entry."""
    cen = cur[s // 2::s, s // 2::s].astype(np.int64)
    bad = (C == 0) & (cen[..., 3] != 0)
    if not bad.any():
        return dict(count=0)
    rgb = cen[..., :3][bad]
    near = np.argmin(((rgb[:, None, :] - P_rgb[None, :, :]) ** 2).sum(-1), axis=1)
    hist = {int(i): int(n) for i, n in zip(*np.unique(near, return_counts=True))}
    return dict(count=int(bad.sum()), centre_mean_rgb=[round(float(x), 2) for x in rgb.mean(axis=0)],
                centre_mean_luma=round(float((rgb @ LUMA).mean()), 2), nearest_palette_entry_histogram=hist)


def validate(parent, written, readback, bbox, C, s=S):
    if not (parent.shape == written.shape == readback.shape and parent.dtype == written.dtype == readback.dtype
            and parent.ndim == 3 and parent.shape[2] == 4):
        return {g: False for g in GATES}, dict(shapes=[list(a.shape) for a in (parent, written, readback)],
                                               dtypes=[str(a.dtype) for a in (parent, written, readback)])
    H, W = C.shape
    roi = roi_slices(bbox, s)
    outside = np.ones(parent.shape[:2], bool)
    outside[roi] = False
    r, p = readback[roi], parent[roi]
    ast = alpha_stats(r[..., 3], C, s)
    opx = up(C != 0, s)
    vis_opx = opx & (p[..., 3] != 0)          # r1: opaque pixels the parent actually showed must be byte-exact
    blk = r[..., :3].reshape(H, s, W, s, 3)
    nonuni_rgb = (blk.min(axis=(1, 3)) != blk.max(axis=(1, 3))).any(-1) & (C == 0)
    out_diff = int((readback[outside] != parent[outside]).any(-1).sum())
    opq_diff = int((r[..., :3][vis_opx] != p[..., :3][vis_opx]).any(-1).sum())
    tr_alpha = int((r[..., 3][~opx] != 0).sum())
    gates = dict(readback_equals_written=bool(np.array_equal(readback, written)),
                 outside_roi_identical_to_parent=out_diff == 0,
                 centre_alpha_equals_native_class=ast["centre_class_mismatches"] == 0,
                 alpha_uniform_per_block=ast["nonuniform_alpha_blocks"] == 0,
                 opaque_rgb_identical_to_parent=opq_diff == 0,
                 transparent_alpha_zero=tr_alpha == 0,
                 transparent_rgb_uniform_per_block=int(nonuni_rgb.sum()) == 0)
    details = dict(roi_alpha=ast, outside_pixels=int(outside.sum()), outside_differing_pixels=out_diff,
                   opaque_rgb_differing_pixels=opq_diff, revealed_opaque_pixels=int((opx & (p[..., 3] == 0)).sum()),
                   transparent_nonzero_alpha_pixels=tr_alpha,
                   transparent_nonuniform_rgb_blocks=int(nonuni_rgb.sum()),
                   readback_differing_pixels=int((readback != written).any(-1).sum()),
                   roi_rgb_changed_pixels_vs_parent=int((r[..., :3] != p[..., :3]).any(-1).sum()),
                   roi_alpha_changed_pixels_vs_parent=int((r[..., 3] != p[..., 3]).sum()))
    return gates, details


# ---------------------------------------------------------------- review sheets

def checker(h, w, cell=4):
    yy, xx = np.indices((h, w))
    out = np.empty((h, w, 3), np.uint8)
    out[:] = (88, 88, 88)
    out[((yy // cell + xx // cell) % 2).astype(bool)] = (168, 168, 168)
    return out


def cutout(rgba):
    return np.where((rgba[..., 3] > 0)[..., None], rgba[..., :3], checker(*rgba.shape[:2]))


def bilinear_sim(rgba, f=4, bg=(128, 128, 128)):
    """SIM: straight-alpha bilinear magnification (RGB and alpha sampled separately, as a GPU does), alpha/127
    blended over grey. A dark RGB under transparent texels shows here as a dark fringe at cut-out edges."""
    h, w = rgba.shape[:2]
    rgb = np.asarray(Image.fromarray(np.ascontiguousarray(rgba[..., :3])).resize((w * f, h * f), Image.BILINEAR),
                     np.float64)
    a = np.asarray(Image.fromarray(np.ascontiguousarray(rgba[..., 3])).resize((w * f, h * f), Image.BILINEAR),
                   np.float64)
    wgt = np.clip(a / 127.0, 0, 1)[..., None]
    return np.clip(np.rint(rgb * wgt + np.array(bg, np.float64) * (1 - wgt)), 0, 255).astype(np.uint8)


def best_crop(C, n=16, step=4):
    H, W = C.shape
    t = C == 0
    e = np.zeros((H, W), int)
    e[:, 1:] += t[:, 1:] != t[:, :-1]
    e[1:, :] += t[1:, :] != t[:-1, :]
    best = (-1, 0, 0)
    for y in sorted(set(list(range(0, max(H - n, 0) + 1, step)) + [max(H - n, 0)])):
        for x in sorted(set(list(range(0, max(W - n, 0) + 1, step)) + [max(W - n, 0)])):
            v = int(e[y:y + n, x:x + n].sum())
            if v > best[0]:
                best = (v, y, x)
    return best[1], best[2], min(n, H), min(n, W)


def gray(a):
    return np.dstack([a, a, a]).astype(np.uint8)


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


def review_sheets(ctx, new_roi, review_dst, alpha_dst, s=S):
    C, O, Prgb = ctx["C"], ctx["O"], ctx["P_rgb"]
    cur = ctx["parent"][roi_slices(ctx["bbox"], s)]
    nat = np.dstack([up(Prgb[O].astype(np.uint8), s), up(C, s)])
    y, x, h, w = best_crop(C)
    cr = (slice(y * s, (y + h) * s), slice(x * s, (x + w) * s))
    title = f"{ctx['key']} {ctx['region_id']} bbox {list(ctx['bbox'])}"
    sheet(review_dst, title, [
        [("native x8", nat[..., :3]), ("current", cur[..., :3]), ("new", new_roi[..., :3])],
        [("native cutout", cutout(nat)), ("current cutout", cutout(cur)), ("new cutout", cutout(new_roi))],
        [(f"SIM bilinear x4 native t[{x},{y}]", bilinear_sim(nat[cr])), ("SIM current", bilinear_sim(cur[cr])),
         ("SIM new", bilinear_sim(new_roi[cr]))]])
    cen = cur[..., 3][s // 2::s, s // 2::s]
    mism = up(np.where((cen != C)[..., None], np.array([255, 0, 0], np.uint8), np.array([0, 0, 0], np.uint8)), s)
    sheet(alpha_dst, title + " alpha", [[("native class", gray(up(C, s))), ("current alpha", gray(cur[..., 3])),
                                         ("new alpha", gray(new_roi[..., 3])), ("cur centre mismatch", mism)]])


# ---------------------------------------------------------------- modes

def save_png(arr, path):
    Image.fromarray(np.ascontiguousarray(arr)).save(path, format="PNG", compress_level=6)


def read_png(path):
    with Image.open(path) as im:
        return np.array(im)


def check_report(jobs, pinned, report):
    rep = {}
    for ctx in jobs:
        roi = roi_slices(ctx["bbox"], S)
        cur = ctx["parent"][roi]
        page, st = apply_page(ctx["parent"], ctx["bbox"], ctx["C"], native_rgb=ctx["P_rgb"][ctx["O"]])
        gates, det = validate(ctx["parent"], page, page, ctx["bbox"], ctx["C"])
        rep[ctx["R"]] = dict(
            region=ctx["region_id"], key=ctx["key"], bbox=list(ctx["bbox"]), roi_px=[b * S for b in ctx["bbox"]],
            classes=ctx["classes"], census=ctx["census"], native=ctx["native"],
            parent=dict(ctx["parent_info"], expected_sha256_prefix=REGIONS[ctx["R"]]["parent_sha256_prefix"],
                        sha256_prefix_matches=ctx["parent_info"]["sha256"].startswith(
                            REGIONS[ctx["R"]]["parent_sha256_prefix"])),
            current=dict(roi_alpha=alpha_stats(cur[..., 3], ctx["C"]),
                         transparent_opaque_at_centre_rgb=current_rgb_stats(cur, ctx["C"], ctx["P_rgb"])),
            planned_in_memory=dict(note="nothing written; readback gate is trivially true in memory",
                                   edge_fill=st, gates=gates, gate_details=det))
    out = dict(tool=str(Path(__file__)), builder_sha256=sha(Path(__file__)), mode="check", wrote_pages=False,
               pin=pinned, regions=rep)
    with open(report, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


def freeze_jobs(F, jobs, meta, s=S, builder=None):
    """Writes the frozen candidate for the prepared jobs into F (must not exist). Returns 0 on READY, 1 on FAILED."""
    import datetime
    import shutil
    builder = Path(__file__) if builder is None else Path(builder)
    F = Path(F)
    F.parent.mkdir(parents=True, exist_ok=True)
    F.mkdir(exist_ok=False)
    for sub in ("page2048", "review"):
        (F / sub).mkdir()
    checks, val, keys = {}, {}, {}
    for ctx in jobs:
        key, pk, R = ctx["key"], ctx["palette"], ctx["R"]
        page, st = apply_page(ctx["parent"], ctx["bbox"], ctx["C"], s, native_rgb=ctx["P_rgb"][ctx["O"]])
        out = F / "page2048" / f"{key}.png"
        save_png(page, out)
        rb = read_png(out)
        gates, det = validate(ctx["parent"], page, rb, ctx["bbox"], ctx["C"], s)
        checks[key] = gates
        cur = ctx["parent"][roi_slices(ctx["bbox"], s)]
        val[key] = dict(gates=gates, details=det, edge_fill=st, current_roi_alpha=alpha_stats(cur[..., 3], ctx["C"], s))
        review_sheets(ctx, page[roi_slices(ctx["bbox"], s)], F / "review" / f"{R}-{pk}-review.png",
                      F / "review" / f"{R}-{pk}-alpha.png", s)
        keys[key] = dict(region=ctx["region_id"], bbox=list(ctx["bbox"]), census=ctx["census"], parent=ctx["parent_info"],
                         live=dict(path=ctx["parent_info"]["path"], sha256=ctx["parent_info"]["sha256"]),
                         native=ctx["native"], classes=ctx["classes"])
        del page, rb
    ok = all(all(g.values()) for g in checks.values()) and bool(checks)
    (F / "validation.json").write_text(json.dumps(dict(passed=ok, gates=list(GATES), checks=checks, keys=val),
                                                  indent=1) + "\n", encoding="utf-8")
    doc = __doc__
    # One region per frozen set: the ROI composer binds policy uv to this exact string (and keys[key].live baseline).
    region = None
    if len(jobs) == 1:
        u0, v0, u1, v1 = jobs[0]["bbox"]
        region = f"{jobs[0]['region_id']} uv [{u0},{v0}]-[{u1},{v1}] half-open (t3-green-lights/regions.json)"
    man = dict(
        name=F.name, status="candidate (private; not integrated, not live-tested)" if ok else "FAILED validation (preserved)",
        owner="claude-einhander", region=region,
        gpu="none: CPU-only alpha class restore; opaque RGB copied from the parent, no generated imagery",
        why=doc.split("Why: ", 1)[1].split("Restore, per", 1)[0].strip(),
        method=doc.split("Restore, per region and palette", 1)[1].split("Bindings checked", 1)[0].strip(" :\n"),
        bindings=doc.split("Bindings checked before any output: ", 1)[1].split("Outputs:", 1)[0].strip(),
        params=dict(px_per_texel=s, transparent_entry=TRANSPARENT_ENTRY, classes_allowed=sorted(CLASSES_ALLOWED),
                    gates=list(GATES)),
        keys=keys, validation_passed=ok,
        integration="ROI-only: overlay the region ROI (RGBA) of page2048 onto the same parent page; every other pixel "
                    "is the parent's, byte for byte.",
        known_limits=[
            "alpha follows the native CLUT class per texel (0 or 127); opaque RGB the parent showed is unchanged; pixels "
            "the parent hid (alpha 0) inside opaque texels are filled from that block's visible pixels",
            "the edge-fill RGB under alpha 0 is never shown directly; it only affects bilinear samples at cut-out edges",
            "Q bbox [0,128,48,192] overlaps the R_tall_cylinder bbox in u 44..47; the 79B18A47 page is drawn only by Q "
            "(draw census), so the ROI is replaced on that page only",
            "SIMULATION only: not integrated, not seen live"],
        sources=meta.get("sources", {}), pin=meta.get("pin"),
        built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (F / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    shutil.copy2(builder, F / builder.name)
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
    status = dict(name=F.name, validation_passed=ok, files=len(sums), sha256sums=sha(F / "SHA256SUMS.txt"),
                  manifest_sha256=sha(F / "manifest.json"), durability="every file fsynced and re-hashed",
                  failed_checks={k: [n for n, g in c.items() if not g] for k, c in checks.items()} if not ok else {},
                  status=man["status"], at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    marker = F / ("READY.json" if ok else "FAILED.json")
    with open(marker, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(status, indent=1) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    print(json.dumps(dict(marker=marker.name, marker_sha256=sha(marker), status=status,
                          outputs={p.relative_to(F).as_posix(): sha(p) for p in files if p.parent.name == "page2048"},
                          checks=checks), indent=1))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--freeze", action="store_true")
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    if a.check and a.report is None:
        raise RuntimeError("--check requires --report PATH")
    pinned = pin()
    idx = np.load(IDX)
    require(idx.shape == (256, 256), f"index map shape {idx.shape}")
    pals = json.loads(PALS.read_text(encoding="utf-8"))
    regj = json.loads(REGJ.read_text(encoding="utf-8"))
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    jobs = [prepare(R, idx, pals, regj, census) for R in REGIONS]
    if a.check:
        return check_report(jobs, pinned, a.report)
    for ctx in jobs:
        pre = REGIONS[ctx["R"]]["parent_sha256_prefix"]
        require(ctx["parent_info"]["sha256"].startswith(pre),
                f"{ctx['key']}: parent sha256 {ctx['parent_info']['sha256']} does not start with {pre}")
    srcs = dict(indices=IDX, palettes=PALS, regions=REGJ, census=CENSUS, builder=Path(__file__))
    meta = dict(pin=pinned, sources={k: dict(path=str(p), sha256=sha(p)) for k, p in srcs.items()})
    rc = 0
    for ctx in jobs:                      # one frozen set per region (binds to the ROI composer's region check)
        rc |= freeze_jobs(HERE / "frozen" / f"{ATLAS}-{ctx['R']}-cutout-v1", [ctx], meta)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
