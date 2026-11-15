"""W7 stage 4/5 art (claude-einhander; s45 merged copy tools/w7m, see make_w7m.py): index-space HD masters on exact-static disc sources.

Sources are the shared immutable static export (fullgame-prep/static-extraction/stages/stageN). Every page is the
member's own exact-static strips (CRC32(words) == TEX re-checked on load). Nothing here is a live capture: every key is
'predicted-static; import only after live capture' (validate_predicted.py confirm + gate on the stage-N run).

Master (palette-independent, M = 16 px per texel):
  * labels L (3, H, W) uint8 + weights Wt (2, H, W) uint8 (third weight = 255 - w0 - w1): categorical soft labels.
    One-hot masks of each native index are blurred (at 4x, then texel-centred bilinear to 16x), mixed between a crisp
    setting (clean areas) and a blending setting (dithered/noisy areas, 'busy'), power-normalised, top-3 kept.
    The native index is forced at every texel centre (label-exact centres, palette-independent).
  * glow t (H, W) float16 (effects only): continuous index, normalised convolution inside the opaque silhouette.
  * logD (H/2, W/2) float16: palette-independent log-luminance material layer (relief, groove AO, swatch detail),
    band-limited for motion and zero-mean per label (colours stay native on average).
Render for one CLUT P: rgb = sum_k w_k P[l_k] over the labels sharing the dominant label's class, x exp(logD) on opaque
classes; class = class of the dominant label; class 0 keeps raw black. Runtime = box-down of the 4096 render (majority
class, RGB averaged inside the class), then native class (and class-0 colour) stamped at every texel centre
floor((i+0.5)*scale). Validation: class at every texel centre of every export == class(P[native index]).
"""
import hashlib
import json
import os
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, 'C:/github/Einhander/remaster-audit/comfy-authoring')
from gpu_queue import cpu_yield  # noqa: E402

EXPORT = Path('C:/github/Einhander/remaster-audit/fullgame-prep/static-extraction/stages')
REVIEWDIR = Path('C:/github/Einhander/remaster-audit/fullgame-prep/stage-review')
CA = Path('C:/github/Einhander/remaster-audit/comfy-authoring')
M = 16
ZERO_PAL = '190A55AD'
SWATCHES = {
    'painted_steel': CA / 't7-enemies/swatches/painted_steel-tileable-1024.png',
    'gunmetal_worn': CA / 't7-enemies/swatches/gunmetal_worn-tileable-1024.png',
    'navy_armour': CA / 't7-enemies/swatches/navy_armour-tileable-1024.png',
    'rusted_beam': CA / 'facade-v3-architecture/swatches/rusted_beam-tileable-1024.png',
    'concrete': CA / 'w3-canyon/assets/concrete-tileable-1024.png',
    'grime': CA / 'w3-canyon/assets/grime-tileable-1024.png',
    # lane-s5 stage-5 swatches (frozen sets; graphs + history beside them)
    'sandblasted_concrete': CA / 'w7-stage5/frozen/s5-swatches-v1/sandblasted_concrete-tileable-1024.png',
    'camo_paint_worn_a': CA / 'w7-stage5/frozen/s5-swatches-v2/camo_paint_worn_a-tileable-1024.png',
    'camo_paint_worn_b': CA / 'w7-stage5/frozen/s5-swatches-v2/camo_paint_worn_b-tileable-1024.png',
    'sandworn_steel_a': CA / 'w7-stage5/frozen/s5-swatches-v2/sandworn_steel_a-tileable-1024.png',
    'sandworn_steel_b': CA / 'w7-stage5/frozen/s5-swatches-v2/sandworn_steel_b-tileable-1024.png',
    # stage-4 sea-base swatches (lane-s4, 2026-11-13; frozen/s4-swatches-v1, candidate). Added keys only.
    's4_salt_corroded_steel': CA / 'w7-stage4/frozen/s4-swatches-v1/s4_salt_corroded_steel-tileable-1024.png',
    's4_wet_painted_steel': CA / 'w7-stage4/frozen/s4-swatches-v1/s4_wet_painted_steel-tileable-1024.png',
    's4_salt_streaks': CA / 'w7-stage4/frozen/s4-swatches-v1/s4_salt_streaks-tileable-1024.png',
    's4_sea_faded_paint': CA / 'w7-stage4/frozen/s4-swatches-v1/s4_sea_faded_paint-tileable-1024.png',
}


def crc(b):
    return '%08X' % (zlib.crc32(b) & 0xFFFFFFFF)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def jload(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


# ------------------------------------------------------------------------------------------------ sources
def load_page(stage, tex):
    """Exact-static 4bpp page words from the export; CRC32 re-checked. Returns (idx (256,256) uint8, info)."""
    p = EXPORT / f'stage{stage}' / 'textures' / f'{tex}.words.bin'
    b = p.read_bytes()
    assert crc(b) == tex, f'CRC32(words) {crc(b)} != TEX {tex}'
    assert len(b) == 64 * 256 * 2, f'{tex}: not a 64x256-word 4bpp page'
    w = np.frombuffer(b, '<u2').reshape(256, 64).astype(np.int64)
    idx = np.zeros((256, 256), np.uint8)
    for i in range(4):
        idx[:, i::4] = (w >> (4 * i)) & 15
    return idx, dict(path=str(p).replace('\\', '/'), sha256=sha256(p), crc32=crc(b), bytes=len(b))


def stage_cluts(stage):
    """{(x, y, pal): words(16 uint16)} for every static CLUT of the stage export (CRC32 re-checked)."""
    out = {}
    for c in jload(EXPORT / f'stage{stage}' / 'cluts.json'):
        b = bytes.fromhex(c['words_hex'])
        assert crc(b) == c['pal']
        out[(c['x'], c['y'], c['pal'])] = np.frombuffer(b, '<u2').copy()
    return out


def clut_rgba(words):
    c = words.astype(np.int64)
    rgb = np.stack([(c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8], -1).astype(np.float32)
    cls = np.where(c == 0, 0, np.where(c & 0x8000, 255, 127)).astype(np.uint8)
    return rgb, cls


def texel_centres(n, scale):
    return np.floor((np.arange(n) + 0.5) * scale).astype(np.int64)


# ------------------------------------------------------------------------------------------------ master
def busy_map(idx):
    """Fraction of the 8 neighbours with another index (wrap off), smoothed; 0 = clean, 1 = dither/noise."""
    p = np.pad(idx, 1, mode='edge')
    d = np.zeros(idx.shape, np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                d += p[1 + dy:1 + dy + idx.shape[0], 1 + dx:1 + dx + idx.shape[1]] != idx
    return ndi.gaussian_filter(d / 8.0, 1.0, mode='nearest')


def up16(a):
    """Texel-centred bilinear x4 of a 4x field (to 16x)."""
    return ndi.zoom(a, 4, order=1, mode='nearest', grid_mode=True)


def soft_labels(idx, clean=(0.42, 4.0), busy=(0.85, 1.2), busy_lo=0.35, busy_hi=0.65, no_busy=False, band=32, margin=4):
    """Categorical soft labels at 16x: returns labels (3,H,W) uint8, weights (2,H,W) uint8, stats."""
    H, W = idx.shape
    beta_n = np.zeros(idx.shape, np.float32) if no_busy else np.clip((busy_map(idx) - busy_lo) / (busy_hi - busy_lo), 0, 1)
    L = np.zeros((3, H * M, W * M), np.uint8)
    Wt = np.zeros((2, H * M, W * M), np.uint8)
    for y0 in range(0, H, band):
        cpu_yield()
        a, b = max(0, y0 - margin), min(H, y0 + band + margin)
        sub = idx[a:b]
        beta = np.clip(up16(np.repeat(np.repeat(beta_n[a:b], 4, 0), 4, 1)), 0, 1)
        pw = clean[1] + (busy[1] - clean[1]) * beta
        labs = np.unique(sub)
        E = np.zeros((max(3, len(labs)),) + beta.shape, np.float32)
        for j, lab in enumerate(labs):
            oh = np.repeat(np.repeat((sub == lab).astype(np.float32), 4, 0), 4, 1)
            mc = up16(ndi.gaussian_filter(oh, clean[0] * 4, mode='nearest'))
            if no_busy or beta_n[a:b].max() <= 0:
                m = mc
            else:
                mb = up16(ndi.gaussian_filter(oh, busy[0] * 4, mode='nearest'))
                m = mc * (1 - beta) + mb * beta
            E[j] = np.clip(m, 0, 1) ** pw
        lab_of = np.zeros(E.shape[0], np.uint8)
        lab_of[:len(labs)] = labs
        S = np.maximum(E.sum(0), 1e-8)
        order = np.argsort(-E, axis=0)[:3]                     # top-3 label slots per pixel
        top_v = np.take_along_axis(E, order, 0)
        top_l = lab_of[order]
        del E
        w0 = top_v[0] / S; w1 = top_v[1] / S; w2 = top_v[2] / S
        tot = np.maximum(w0 + w1 + w2, 1e-8)
        w0, w1 = w0 / tot, w1 / tot
        q0 = np.rint(w0 * 255).astype(np.int32); q1 = np.minimum(np.rint(w1 * 255).astype(np.int32), 255 - q0)
        r0, r1 = (y0 - a) * M, (min(H, y0 + band) - a) * M
        L[:, y0 * M:min(H, y0 + band) * M] = top_l[:, r0:r1]
        Wt[0, y0 * M:min(H, y0 + band) * M] = q0[r0:r1]
        Wt[1, y0 * M:min(H, y0 + band) * M] = q1[r0:r1]
    # label-exact texel centres (palette-independent): native index, full weight
    ys, xs = texel_centres(H, M), texel_centres(W, M)
    before = L[0][np.ix_(ys, xs)] != idx
    sub = L[0][np.ix_(ys, xs)]; sub[:] = idx; L[0][np.ix_(ys, xs)] = sub
    w = Wt[0][np.ix_(ys, xs)]; w[:] = 255; Wt[0][np.ix_(ys, xs)] = w
    w = Wt[1][np.ix_(ys, xs)]; w[:] = 0; Wt[1][np.ix_(ys, xs)] = w
    stats = dict(centre_labels_forced=int(before.sum()), busy_texel_share=float((beta_n > 0.5).mean()),
                 clean=list(clean), busy=list(busy), busy_window=[busy_lo, busy_hi], no_busy=bool(no_busy))
    return L, Wt, stats


def near_matrix(cluts, T=48.0, quorum=1.0):
    """N[i, j] = indices i and j share the class under every candidate CLUT of the page and are close in colour
    (RGB distance <= T) under at least `quorum` of them (most predicted pairings are 'likely' and many are wrong, so a
    unanimous rule would forbid almost all blending)."""
    same = np.ones((16, 16), bool)
    near = np.zeros((16, 16), np.float32)
    for rgb, cls in cluts:
        d = np.sqrt(((rgb[:, None, :] - rgb[None, :, :]) ** 2).sum(-1))
        same &= cls[:, None] == cls[None, :]
        near += d <= T
    return same & (near >= quorum * max(len(cluts), 1) - 1e-6)


def soft_labels_toned(idx, N, crisp=(0.42, 4.0), blend_sigma=0.9, beta_lo=0.3, beta_hi=0.65, no_busy=False,
                      band=16, margin=4, cores=True, force_centres=True, strokes=False, stroke_min_len=3):
    """Categorical soft labels at 16x with tone-group blending (v2).
    w = (1 - beta) * crisp_weights + beta * blend_weights, where the blend weights only mix labels that are N-near the
    pixel's dominant crisp label, and beta (native res) is the share of 8-neighbours that differ but are N-near
    (dither / noise between close tones). Edges between distinct tones keep the crisp contour."""
    H, W = idx.shape
    if no_busy:
        beta_n = np.zeros(idx.shape, np.float32)
    else:
        p = np.pad(idx, 1, mode='edge')
        d = np.zeros(idx.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    nb = p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
                    d += (nb != idx) & N[idx, nb]
        beta_n = np.clip((ndi.gaussian_filter(d / 8.0, 0.7, mode='nearest') - beta_lo) / (beta_hi - beta_lo), 0, 1)
    L = np.zeros((3, H * M, W * M), np.uint8)
    Wt = np.zeros((2, H * M, W * M), np.uint8)
    for y0 in range(0, H, band):
        cpu_yield()
        a, b = max(0, y0 - margin), min(H, y0 + band + margin)
        sub = idx[a:b]
        labs = np.unique(sub)
        n = max(3, len(labs))
        shape = ((b - a) * M, W * M)
        Ec = np.zeros((n,) + shape, np.float32)
        Eb = np.zeros((n,) + shape, np.float32) if not no_busy else None
        for j, lab in enumerate(labs):
            oh = np.repeat(np.repeat((sub == lab).astype(np.float32), 4, 0), 4, 1)
            Ec[j] = np.clip(up16(ndi.gaussian_filter(oh, crisp[0] * 4, mode='nearest')), 0, 1) ** crisp[1]
            if Eb is not None:
                Eb[j] = np.clip(up16(ndi.gaussian_filter(oh, blend_sigma * 4, mode='nearest')), 0, 1)
        lab_of = np.zeros(n, np.uint8); lab_of[:len(labs)] = labs
        Wc = Ec / np.maximum(Ec.sum(0), 1e-8)
        if Eb is not None and beta_n[a:b].max() > 0:
            dom = lab_of[np.argmax(Ec, 0)]
            near = N[lab_of][:, dom]                      # (n, h, w): is label j near the dominant label?
            near[len(labs):] = False
            Eb *= near
            Wb = Eb / np.maximum(Eb.sum(0), 1e-8)
            beta = np.clip(up16(np.repeat(np.repeat(beta_n[a:b], 4, 0), 4, 1)), 0, 1)
            Wf = Wc * (1 - beta) + Wb * beta
            del Wb, near, dom
        else:
            Wf = Wc
        del Ec, Eb
        order = np.argsort(-Wf, axis=0)[:3]
        top_v = np.take_along_axis(Wf, order, 0)
        top_l = lab_of[order]
        del Wf
        tot = np.maximum(top_v.sum(0), 1e-8)
        w0, w1 = top_v[0] / tot, top_v[1] / tot
        q0 = np.rint(w0 * 255).astype(np.int32); q1 = np.minimum(np.rint(w1 * 255).astype(np.int32), 255 - q0)
        r0, r1 = (y0 - a) * M, (min(H, y0 + band) - a) * M
        L[:, y0 * M:min(H, y0 + band) * M] = top_l[:, r0:r1]
        Wt[0, y0 * M:min(H, y0 + band) * M] = q0[r0:r1]
        Wt[1, y0 * M:min(H, y0 + band) * M] = q1[r0:r1]
    ys, xs = texel_centres(H, M), texel_centres(W, M)
    before = L[0][np.ix_(ys, xs)] != idx
    cores = core_lost_texels(L, Wt, idx, np.argwhere(before)) if cores else 0   # lane-s5: FX regions skip cores
    sk = None
    if strokes:   # s45 merge: lane-s4 world v3 1-texel line strokes (opt-in; after the cores, before the centres)
        runs = thin_line_runs(idx, stroke_min_len)
        sk = stroke_lines(L, Wt, idx, runs)
        sk.update(min_len=stroke_min_len, multi_tone_only=True, bg_change_max=0.25)
    if force_centres:   # lane-s5: FX regions skip it (a forced 1-px native dot inside a blended fade); exports still
        sub = L[0][np.ix_(ys, xs)]; sub[:] = idx; L[0][np.ix_(ys, xs)] = sub          # stamp the native class there
        w = Wt[0][np.ix_(ys, xs)]; w[:] = 255; Wt[0][np.ix_(ys, xs)] = w
        w = Wt[1][np.ix_(ys, xs)]; w[:] = 0; Wt[1][np.ix_(ys, xs)] = w
    stats = dict(version='toned-v2-cores', centre_labels_forced=int(before.sum()), lost_texel_cores=cores,
                 core_radius_texel=[CORE_R_IN, CORE_R_OUT], dither_texel_share=float((beta_n > 0.5).mean()),
                 crisp=list(crisp), blend_sigma=blend_sigma, beta_window=[beta_lo, beta_hi], no_busy=bool(no_busy),
                 near_pairs=int(N.sum() - 16) // 2)
    if sk is not None:
        stats.update(version='toned-v3-strokes', strokes=sk)
    return L, Wt, stats


CORE_R_IN, CORE_R_OUT, CORE_P = 0.5, 0.62, 6.0   # superellipse (p=6) radius in texels: full weight to mid-edges


def core_lost_texels(L, Wt, idx, lost):
    """Texels whose native index lost dominance at their own centre (isolated rivets, lamp dots, 1-texel lines)
    keep a rounded-square core of that index (superellipse p=6: full weight out to the cell's mid-edges, corners
    fading by CORE_R_OUT), so single-texel details survive the box-down and a chain of lost texels stays a continuous
    straight line instead of a 1-pixel speck or a dotted chain. Only these texels are touched."""
    if len(lost) == 0:
        return 0
    o = np.abs((np.arange(M) + 0.5) / M - 0.5)
    dist = (o[:, None] ** CORE_P + o[None, :] ** CORE_P) ** (1.0 / CORE_P)
    c = np.clip((CORE_R_OUT - dist) / (CORE_R_OUT - CORE_R_IN), 0, 1).astype(np.float32)
    for n, (ty, tx) in enumerate(lost):
        if n % 2000 == 0:
            cpu_yield()
        sy, sx = slice(ty * M, (ty + 1) * M), slice(tx * M, (tx + 1) * M)
        lab = L[:, sy, sx].astype(np.int64)
        w = np.stack([Wt[0, sy, sx], Wt[1, sy, sx]]).astype(np.float32) / 255
        w = np.concatenate([w, np.clip(1 - w.sum(0, keepdims=True), 0, 1)], 0)
        nl = int(idx[ty, tx])
        w = w * (1 - c)
        has = lab == nl
        add = c * (~has.any(0))
        w = w + has * c
        # where the native label is not among the top-3, it replaces the weakest slot
        weakest = np.argmin(w, 0)
        rep = add > 0
        for k in range(3):
            m = rep & (weakest == k)
            lab[k][m] = nl
            w[k][m] = add[m]
        order = np.argsort(-w, 0)
        lab = np.take_along_axis(lab, order, 0)
        w = np.take_along_axis(w, order, 0)
        tot = np.maximum(w.sum(0), 1e-8)
        q0 = np.rint(w[0] / tot * 255).astype(np.int32)
        q1 = np.minimum(np.rint(w[1] / tot * 255).astype(np.int32), 255 - q0)
        L[:, sy, sx] = lab.astype(np.uint8)
        Wt[0, sy, sx] = q0
        Wt[1, sy, sx] = q1
    return int(len(lost))


def glow_field(idx, opaque_idx, sigma=0.55):
    """Continuous index t at 16x: normalised convolution of the native index inside the opaque silhouette."""
    mask = np.isin(idx, opaque_idx).astype(np.float32)
    num = ndi.gaussian_filter(np.repeat(np.repeat(idx.astype(np.float32) * mask, 4, 0), 4, 1), sigma * 4, mode='nearest')
    den = ndi.gaussian_filter(np.repeat(np.repeat(mask, 4, 0), 4, 1), sigma * 4, mode='nearest')
    t4 = num / np.maximum(den, 1e-4)
    return up16(t4).astype(np.float32)


# ------------------------------------------------------------------------------------------------ material
def swatch_source(name):
    """The generated raw swatch if it exists (no tiling seam), else the tileable one; centre 60% only."""
    p = SWATCHES[name]
    raw = p.parent / p.name.replace('-tileable-1024.png', '-raw.png')
    src = raw if raw.exists() else p
    im = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
    h, w = im.shape[:2]
    im = im[int(h * 0.2):int(h * 0.8), int(w * 0.2):int(w * 0.8)]
    y = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2] + 4.0
    ld = np.log(y)
    return ld - ndi.gaussian_filter(ld, 48, mode='reflect'), str(src).replace('\\', '/')


def swatch_detail(names, size, seed, amp, sigma_px, patch=192):
    """Zero-mean band-limited log-luminance detail synthesised from Stage 1 generated swatches (size x size):
    overlapping Hann-windowed patches at random offsets of the swatch centre (horizontal flips only, so weathering keeps
    its vertical axis), no tiling seam, no repeat; high-passed (sigma 48 px) and band-limited for motion."""
    rng = np.random.default_rng(zlib.crc32(seed.encode()))
    acc = np.zeros((size, size), np.float32)
    win = np.outer(np.hanning(patch), np.hanning(patch)).astype(np.float32) + 1e-4
    for name, wgt in names:
        ld, _ = swatch_source(name)
        num = np.zeros((size + 2 * patch, size + 2 * patch), np.float32)
        den = np.zeros_like(num)
        step = patch // 2
        for y in range(-step, size, step):
            for x in range(-step, size, step):
                oy = rng.integers(0, ld.shape[0] - patch); ox = rng.integers(0, ld.shape[1] - patch)
                pp = ld[oy:oy + patch, ox:ox + patch]
                if rng.random() < 0.5:
                    pp = pp[:, ::-1]
                yy, xx = y + step, x + step
                num[yy:yy + patch, xx:xx + patch] += pp * win
                den[yy:yy + patch, xx:xx + patch] += win
        f = (num / np.maximum(den, 1e-6))[step:step + size, step:step + size]
        f = (f - f.mean()) / max(f.std(), 1e-6)
        acc += wgt * f
    acc = ndi.gaussian_filter(acc, sigma_px, mode='nearest')      # band-limit for motion (no mips at runtime)
    acc -= acc.mean()
    return (acc / max(acc.std(), 1e-6) * amp).astype(np.float32)


def material_logD(L, Wt, ref_rgb, ref_cls, idx, params, seed):
    """Palette-independent material at 8 px/texel (H*8): relief + groove AO + swatch detail, zero-mean per label."""
    if not params:
        return None
    H, W = idx.shape
    f = 2  # 16x -> 8x
    lab0 = L[0, ::f, ::f]
    w0 = Wt[0, ::f, ::f].astype(np.float32) / 255; w1 = Wt[1, ::f, ::f].astype(np.float32) / 255; w2 = np.clip(1 - w0 - w1, 0, 1)
    Y = 0.2126 * ref_rgb[:, 0] + 0.7152 * ref_rgb[:, 1] + 0.0722 * ref_rgb[:, 2]
    Yf = (w0 * Y[lab0] + w1 * Y[L[1, ::f, ::f]] + w2 * Y[L[2, ::f, ::f]]) / 255.0
    s = 8.0  # px per texel at this resolution
    logD = np.zeros(Yf.shape, np.float32)
    if params.get('relief', 0):
        Hh = ndi.gaussian_filter(Yf, params.get('relief_sigma_tex', 0.9) * s, mode='nearest')
        gy, gx = np.gradient(Hh)
        logD += -params['relief'] * (gx + gy) * s / np.sqrt(2)
    if params.get('groove', 0):
        Ys = ndi.gaussian_filter(Yf, params.get('groove_sigma_tex', 0.3) * s, mode='nearest')
        gy, gx = np.gradient(Ys)
        gm = np.hypot(gx, gy) * s
        logD += -params['groove'] * np.clip(gm / params.get('groove_ref', 0.35), 0, 1)
    if params.get('swatch'):
        logD += swatch_detail(params['swatch'], Yf.shape[0], seed, params.get('swatch_amp', 0.1),
                              params.get('swatch_sigma_px', 1.2))
    if params.get('grime', 0):
        rng = np.random.default_rng(zlib.crc32((seed + 'grime').encode()))
        g = ndi.gaussian_filter(rng.standard_normal(Yf.shape).astype(np.float32), params.get('grime_sigma_tex', 2.5) * s, mode='wrap')
        logD += params['grime'] * g / max(g.std(), 1e-6)
    logD = ndi.gaussian_filter(logD, params.get('final_sigma_px', 0.8), mode='nearest')
    # lane-s5: no material inside 'exclude_boxes' (texel boxes [x0, y0, x1, y1) of FX sprites on world/armour pages:
    # smoke, bursts, shock rings get no steel detail, relief or groove outline); 1-texel feather at the box edge
    keep = np.ones(logD.shape, np.float32)
    for x0, y0, x1, y1 in params.get('exclude_boxes', []):
        keep[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)] = 0
    if params.get('exclude_boxes'):
        keep = np.clip(ndi.gaussian_filter(keep, 0.5 * s, mode='nearest'), 0, 1)
    # lane-s5 glyph lock: 'exclude_index_boxes' [x0, y0, x1, y1, index] = no material on the texels of that native
    # index inside the box (painted numerals keep their flat native paint colour; the plate around them keeps its
    # material up to the glyph edge); tight feather (0.25 texel)
    if params.get('exclude_index_boxes'):
        gm = np.zeros(idx.shape, np.float32)
        for x0, y0, x1, y1, gi in params['exclude_index_boxes']:
            gm[y0:y1, x0:x1] = np.maximum(gm[y0:y1, x0:x1], (idx[y0:y1, x0:x1] == gi).astype(np.float32))
        gm8 = np.kron(gm, np.ones((int(s), int(s)), np.float32))
        keep = keep * (1 - np.clip(ndi.gaussian_filter(gm8, 0.25 * s, mode='nearest'), 0, 1))
    if params.get('_exclude_texels') is not None:            # native-res bool mask (8bpp pass-through regions)
        km = np.kron(params['_exclude_texels'].astype(np.float32), np.ones((int(s), int(s)), np.float32))
        keep = keep * (1 - np.clip(ndi.gaussian_filter(km, 0.5 * s, mode='nearest'), 0, 1))
    if params.get('exclude_boxes') or params.get('exclude_index_boxes') or params.get('_exclude_texels') is not None:
        logD *= keep
    # zero-mean per dominant label: every native colour keeps its average brightness (over the material area only)
    flat = lab0.ravel()
    kf = keep.ravel().astype(np.float64)
    cnt = np.bincount(flat, weights=kf, minlength=16)
    mean = np.bincount(flat, weights=logD.ravel().astype(np.float64) * kf, minlength=16) / np.maximum(cnt, 1e-6)
    logD -= mean[lab0].astype(np.float32) * keep
    lo, hi = params.get('clamp', (-0.6, 0.35))
    return np.clip(logD, lo, hi).astype(np.float16)


# ------------------------------------------------------------------------------------------------ render
def render(L, Wt, rgb, cls, logD=None, glow=None, glow_mask=None):
    """Render the 16x master through one CLUT -> rgb float32 (H,W,3), class uint8 (H,W)."""
    w = [Wt[0].astype(np.float32) / 255, Wt[1].astype(np.float32) / 255]
    w.append(np.clip(1 - w[0] - w[1], 0, 1))
    c = cls[L[0]]
    out = np.zeros(L.shape[1:] + (3,), np.float32)
    den = np.zeros(L.shape[1:], np.float32)
    for k in range(3):
        same = (cls[L[k]] == c).astype(np.float32) * w[k]
        out += same[..., None] * rgb[L[k]]
        den += same
    out /= np.maximum(den, 1e-6)[..., None]
    if glow is not None:
        t = np.clip(glow, 0, 15)
        lo = np.floor(t).astype(np.int64); hi = np.minimum(lo + 1, 15); fr = (t - lo)[..., None]
        g = rgb[lo] * (1 - fr) + rgb[hi] * fr
        if glow_mask.dtype == bool:
            gm = (glow_mask & (c != 0))[..., None]
            out = np.where(gm, g, out)
        else:   # float glow weight (glow_break_weight): blend glow and categorical labels (lane-s4 port)
            gw = (np.clip(glow_mask, 0, 1) * (c != 0))[..., None]
            out = out * (1 - gw) + g * gw
    if logD is not None:
        D = np.exp(ndi.zoom(logD.astype(np.float32), L.shape[1] / logD.shape[0], order=1, mode='nearest', grid_mode=True))
        out = np.where((c != 0)[..., None], out * D[..., None], out)
    out[c == 0] = 0
    return np.clip(out, 0, 255), c


def box_down_rgbc(rgb, c, f):
    H, W = c.shape
    r = rgb.reshape(H // f, f, W // f, f, 3)
    cc = c.reshape(H // f, f, W // f, f)
    out_c = np.zeros((H // f, W // f), np.uint8); best = np.zeros((H // f, W // f), np.int32)
    for k in (0, 127, 255):
        n = (cc == k).sum(axis=(1, 3))
        upd = n > best; out_c[upd] = k; best[upd] = n[upd]
    m = (cc == out_c[:, None, :, None]).astype(np.float32)
    s = np.maximum(m.sum(axis=(1, 3)), 1)
    out_rgb = (r * m[..., None]).sum(axis=(1, 3)) / s[..., None]
    return out_rgb, out_c


def export_rgba(rgb16, c16, idx, rgb, cls, size):
    """Box-down the 4096 render to size, stamp native class (and the native colour where the class had to change)."""
    f = rgb16.shape[0] // size
    r, c = (rgb16, c16) if f == 1 else box_down_rgbc(rgb16, c16, f)
    a = np.dstack([np.clip(np.rint(r), 0, 255).astype(np.uint8), c])
    H, W = idx.shape
    ys, xs = texel_centres(H, size / H), texel_centres(W, size / W)
    want = cls[idx]
    sub = a[np.ix_(ys, xs)]
    changed = sub[..., 3] != want
    sub[changed, :3] = np.clip(rgb[idx][changed], 0, 255).astype(np.uint8)
    sub[..., 3] = want
    sub[want == 0, :3] = 0
    a[np.ix_(ys, xs)] = sub
    return a, int(changed.sum())


def validate(a, idx, cls):
    H, W = idx.shape
    ys, xs = texel_centres(H, a.shape[0] / H), texel_centres(W, a.shape[1] / W)
    got = a[np.ix_(ys, xs)][..., 3]
    want = cls[idx]
    bad = np.argwhere(got != want)
    vals = sorted(set(np.unique(a[..., 3]).tolist()))
    return dict(size=[a.shape[1], a.shape[0]], centre_class_mismatch=int(len(bad)), alpha_values=vals,
                alpha_values_ok=set(vals) <= {0, 127, 255},
                examples=[[int(x), int(y), int(want[y, x]), int(got[y, x])] for y, x in bad[:6]])


def save_png(a, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(path, compress_level=6)
    return sha256(path)


# ------------------------------------------------------------------------------------------------ review
def native_rgba(idx, rgb, cls):
    return np.dstack([rgb[idx].astype(np.uint8), cls[idx]])


def on_bg(a, bg=(24, 26, 34)):
    """Composite RGBA (class alpha) on a dark background for viewing: class 0 shows the background."""
    out = np.empty(a.shape[:2] + (3,), np.uint8)
    out[:] = bg
    vis = a[..., 3] != 0
    out[vis] = a[..., :3][vis]
    return out


def bilinear_resample(img, scale):
    """Display-scale bilinear (texel-centred), as the renderer samples a 2048 runtime texture (no mips)."""
    return np.stack([ndi.zoom(img[..., k].astype(np.float32), scale, order=1, mode='nearest', grid_mode=True)
                     for k in range(img.shape[2])], -1)


def label(im, text, xy=(6, 4), fill=(255, 220, 120)):
    d = ImageDraw.Draw(im)
    d.rectangle([xy[0] - 3, xy[1] - 2, xy[0] + 7 * len(text) + 3, xy[1] + 12], fill=(0, 0, 0))
    d.text(xy, text, fill=fill)


# ------------------------------------------------------------------------------------------------ lane-s5 v2 regions
# ---- s45 merge: ported verbatim from lane-s4 w7lib.py (opt-in features)
def thin_line_runs(idx, min_len=3, multi_tone_only=True, bg_change_max=0.25):
    """1-texel line runs whose tone changes along the line (lane-s4 2026-11-13, world v3; the v2 bead chain).
    A texel is h-thin when its index differs from both vertical neighbours (v-thin: both horizontal neighbours).
    Checkerboard dither (thin both ways with >= 2 diagonal neighbours of its own index) is never a line texel.
    Runs of >= min_len consecutive h-thin (v-thin) line texels are kept when they hold >= 2 distinct indices
    (multi_tone_only: same-tone 1-texel lines already render continuously) and the rows (columns) on both sides are
    calm around each texel: index changes along them within +-3 texels / pairs <= bg_change_max (a line on a
    background, not a noise row); runs are split where the background gets busy.
    Returns ('h', row, x0, x1) / ('v', col, y0, y1) with inclusive ends."""
    H, W = idx.shape
    p = np.pad(idx.astype(np.int16), 1, mode='constant', constant_values=-1)
    c = p[1:-1, 1:-1]
    up, dn, lf, rt = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
    hthin = (c != up) & (c != dn)
    vthin = (c != lf) & (c != rt)
    diag = ((p[:-2, :-2] == c).astype(np.int8) + (p[:-2, 2:] == c) + (p[2:, :-2] == c) + (p[2:, 2:] == c))
    checker = hthin & vthin & (diag >= 2)
    runs = []
    k = np.ones(2 * BG_HALF, np.float32)
    for o, cand, A in (('h', hthin & ~checker, idx), ('v', (vthin & ~checker).T, idx.T)):
        R, Lr = A.shape
        for r in range(R):
            # calm background: index changes along the neighbour rows within +-BG_HALF texels of each texel
            ch = np.zeros(Lr, np.float32); n = np.zeros(Lr, np.float32)
            for rr in (r - 1, r + 1):
                if 0 <= rr < R:
                    pairs = np.concatenate([[0], (A[rr, 1:] != A[rr, :-1]).astype(np.float32), [0]])
                    valid = np.concatenate([[0], np.ones(Lr - 1, np.float32), [0]])
                    ch += np.convolve(pairs, k)[BG_HALF:BG_HALF + Lr]
                    n += np.convolve(valid, k)[BG_HALF:BG_HALF + Lr]
            calm = (ch / np.maximum(n, 1)) <= bg_change_max
            row = np.concatenate([[False], cand[r] & calm, [False]]).astype(np.int8)
            d = np.diff(row)
            for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1):
                if b - a + 1 < min_len:
                    continue
                if multi_tone_only and len(np.unique(A[r, a:b + 1])) < 2:
                    continue
                runs.append((o, int(r), int(a), int(b)))
    return runs


BG_HALF = 3


STROKE_R_IN, STROKE_R_OUT, STROKE_P = 0.5, 0.62, 6.0


def stroke_lines(L, Wt, idx, runs):
    """Rebuild 1-texel line runs as continuous strokes (lane-s4 2026-11-13, world v3). Each run is a superellipse
    capsule (p=6) of half-width 0.5 texel around the segment joining its first and last texel centres: full weight
    inside the native row/column, fading over 0.12 texel outside (the same profile as the lost-texel cores), with
    rounded-square end caps. Along the run every pixel takes the native index of the texel it lies in, so tones change
    exactly at the native texel boundaries and the stroke never pinches where the tone changes (the v2 bead chain).
    Coverage is resolved globally first (highest coverage wins, so stacked or crossing runs keep their own rows), then
    blended into the top-3 labels like the cores. Texel centres are forced by the caller afterwards."""
    if not runs:
        return dict(runs=0, texels=0, multi_tone_runs=0)
    H, W = idx.shape
    cov = np.zeros((H * M, W * M), np.float16)
    lab = np.zeros((H * M, W * M), np.uint8)
    t = (np.arange(M, dtype=np.float32) + 0.5) / M
    multi = texels = 0
    for n, (o, r, a, b) in enumerate(runs):
        if n % 200 == 0:
            cpu_yield()
        texels += b - a + 1
        tones = idx[r, a:b + 1] if o == 'h' else idx[a:b + 1, r]
        multi += len(np.unique(tones)) > 1
        a0, a1 = max(0, a - 1), min((W if o == 'h' else H), b + 2)          # along the run (texels), 1 texel margin
        p0, p1 = max(0, r - 1), min((H if o == 'h' else W), r + 2)          # across the run
        along = (np.arange(a0 * M, a1 * M) + 0.5) / M
        across = (np.arange(p0 * M, p1 * M) + 0.5) / M
        oa = np.maximum(0, np.maximum((a + 0.5) - along, along - (b + 0.5)))
        oc = np.abs(across - (r + 0.5))
        d = (oc[:, None] ** STROKE_P + oa[None, :] ** STROKE_P) ** (1.0 / STROKE_P)       # (across, along)
        c = np.clip((STROKE_R_OUT - d) / (STROKE_R_OUT - STROKE_R_IN), 0, 1).astype(np.float16)
        ti = np.clip(np.floor(along).astype(np.int64), a, b)
        lb = (idx[r, ti] if o == 'h' else idx[ti, r]).astype(np.uint8)
        lb = np.broadcast_to(lb[None, :], c.shape)
        if o == 'h':
            sl = (slice(p0 * M, p1 * M), slice(a0 * M, a1 * M)); cc, ll = c, lb
        else:
            sl = (slice(a0 * M, a1 * M), slice(p0 * M, p1 * M)); cc, ll = c.T, lb.T
        cur = cov[sl]
        upd = cc > cur
        cur[upd] = cc[upd]
        lab[sl][upd] = ll[upd]
    # blend into the labels, band by band
    band = 64 * M // 16
    for y0 in range(0, H * M, band):
        cpu_yield()
        ys = slice(y0, min(H * M, y0 + band))
        cb = cov[ys].astype(np.float32)
        if not (cb > 0).any():
            continue
        nl = lab[ys].astype(np.int64)
        lb3 = L[:, ys].astype(np.int64)
        w = np.stack([Wt[0, ys], Wt[1, ys]]).astype(np.float32) / 255
        w = np.concatenate([w, np.clip(1 - w.sum(0, keepdims=True), 0, 1)], 0)
        w = w * (1 - cb)
        has = lb3 == nl[None]
        add = cb * (~has.any(0))
        w = w + has * cb
        weakest = np.argmin(w, 0)
        rep_ = add > 0
        for k in range(3):
            m = rep_ & (weakest == k)
            lb3[k][m] = nl[m]
            w[k][m] = add[m]
        order = np.argsort(-w, 0)
        lb3 = np.take_along_axis(lb3, order, 0)
        w = np.take_along_axis(w, order, 0)
        tot = np.maximum(w.sum(0), 1e-8)
        q0 = np.rint(w[0] / tot * 255).astype(np.int32)
        q1 = np.minimum(np.rint(w[1] / tot * 255).astype(np.int32), 255 - q0)
        L[:, ys] = lb3.astype(np.uint8)
        Wt[0, ys] = q0
        Wt[1, ys] = q1
    return dict(runs=len(runs), texels=int(texels), multi_tone_runs=int(multi), min_len=None,
                profile=[STROKE_R_IN, STROKE_R_OUT, STROKE_P])


def glow_break_pairs(rgbs, T=48.0):
    """B[i, j] = interpolating the index from i to j leaves the straight colour segment P[i]-P[j] by more than T (RGB)
    under at least one of the given palettes (an off-ramp entry such as a grey filler next to a red ramp, or a path
    that overshoots both ends). Added 2026-11-13 (lane-s4); used only when a job sets glow_break_T."""
    B = np.zeros((16, 16), bool)
    for rgb in rgbs:
        P = rgb.astype(np.float64)
        for i in range(16):
            for j in range(i + 2, 16):
                a, b = P[i], P[j]
                ab = b - a
                L2 = float(ab @ ab)
                ks = P[i + 1:j]
                t = np.clip(((ks - a) @ ab) / L2, 0, 1) if L2 > 0 else np.zeros(len(ks))
                d = np.sqrt((((a + t[:, None] * ab) - ks) ** 2).sum(1)).max()
                if d > T:
                    B[i, j] = B[j, i] = True
    return B


def glow_break_weight(idx, B, sigma=0.35):
    """Glow weight at 16x in [0, 1]: 0 on and around texels that touch a broken pair (8-neighbourhood), so the render
    uses the crisp categorical labels there instead of interpolating through unrelated palette entries; 1 elsewhere.
    Returns (weight float32 (16H, 16W), broken texel count)."""
    H, W = idx.shape
    p = np.pad(idx, 1, mode='edge')
    brk = np.zeros(idx.shape, bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                brk |= B[idx, p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]]
    b4 = ndi.gaussian_filter(np.repeat(np.repeat(brk.astype(np.float32), 4, 0), 4, 1), sigma * 4, mode='nearest')
    w = 1.0 - np.clip(2.0 * up16(b4), 0, 1)
    return w.astype(np.float32), int(brk.sum())


# ------------------------------------------------------------------------------------------------ material
# ---- end of lane-s4 port


def _crop(box, H, W, m):
    x0, y0, x1, y1 = box[:4]
    return max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)


def _paste(L, Wt, Lc, Wc, box, crop):
    x0, y0, x1, y1 = box[:4]
    cx0, cy0 = crop[0], crop[1]
    L[:, y0 * M:y1 * M, x0 * M:x1 * M] = Lc[:, (y0 - cy0) * M:(y1 - cy0) * M, (x0 - cx0) * M:(x1 - cx0) * M]
    Wt[:, y0 * M:y1 * M, x0 * M:x1 * M] = Wc[:, (y0 - cy0) * M:(y1 - cy0) * M, (x0 - cx0) * M:(x1 - cx0) * M]


def fx_region(L, Wt, idx, cluts, box, blend_sigma=1.0, crisp=(0.42, 4.0), beta=(0.15, 0.4), margin=4):
    """FX contract inside a box of an armour page (shock rings, bursts, flames): tone-group soft labels where 'near' is
    'same class under every renderable static CLUT of the page' (colour distance ignored, because the native fades are
    high-contrast dithers), low dither threshold, no lost-texel cores, so dithered fades blend into intermediate tones
    instead of dots. Palette-independent (labels + weights); centres stay label-exact."""
    H, W = idx.shape
    N = np.ones((16, 16), bool)        # any pair may blend: render() keeps only the labels of the dominant label's
    cr = _crop(box, H, W, margin)      # class under the CLUT in use, so classes stay exact per CLUT
    sub = idx[cr[1]:cr[3], cr[0]:cr[2]]
    Lc, Wc, st = soft_labels_toned(sub, N, crisp=crisp, blend_sigma=blend_sigma, beta_lo=beta[0], beta_hi=beta[1],
                                   cores=False, force_centres=False)
    _paste(L, Wt, Lc, Wc, box, cr)
    return dict(kind='fx', box=list(box[:4]), blend_sigma=blend_sigma, crisp=list(crisp), beta_window=list(beta),
                near='any index pair (render keeps only labels of the dominant class per CLUT)',
                centres='not forced in the master (no 1-px native dots in the fades); every export stamps the native '
                        'class at every texel centre', dither_texel_share=st['dither_texel_share'],
                centre_labels_differing=st['centre_labels_forced'])


def native_region(L, Wt, idx, box):
    """8bpp sub-image read as 4bpp: native pass-through (nearest labels, weight 1), NOT HD; pending an 8bpp master."""
    x0, y0, x1, y1 = box[:4]
    nn = np.kron(idx[y0:y1, x0:x1], np.ones((M, M), np.uint8))
    L[:, y0 * M:y1 * M, x0 * M:x1 * M] = nn[None]
    Wt[0, y0 * M:y1 * M, x0 * M:x1 * M] = 255
    Wt[1, y0 * M:y1 * M, x0 * M:x1 * M] = 0
    return dict(kind='native-8bpp-pending', box=list(box[:4]))


def staircase_map(gm):
    """Native-res indicator of staircase corner texels of a binary mask: a texel whose two orthogonal neighbours of one
    quadrant both differ from it (a corner) AND whose boundary continues diagonally (the next or previous step of a
    1:1, 1:2 or 2:1 staircase has the texel's own value). Real stroke corners (no diagonal continuation) are 0."""
    H, W = gm.shape
    p = np.pad(gm, 3, mode='edge')

    def at(dy, dx):
        return p[3 + dy:3 + dy + H, 3 + dx:3 + dx + W]
    S = np.zeros(gm.shape, bool)
    for dy, dx in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        corner = (at(dy, 0) != gm) & (at(0, dx) != gm)
        cont = np.zeros(gm.shape, bool)
        for (a, b) in ((dy, -dx), (dy, -2 * dx), (2 * dy, -dx), (-dy, dx), (-dy, 2 * dx), (-2 * dy, dx)):
            cont |= at(a, b) == gm
        S |= corner & cont
    return S


def destair_glyph(L, Wt, idx, box, crisp=(0.32, 6.0), smooth_sigma=0.6, reach=0.8, margin=4):
    """Soften the scalloped staircase diagonals of a painted glyph without changing its native shape: inside the box,
    per-index weights = (1 - a) * tight (crisp contour, as the armour master) + a * smooth (sigma smooth_sigma, same
    power), where a = staircase-corner indicator of the glyph mask (staircase_map) blurred by `reach` texels, so
    staircases become straight edges while real stroke corners keep the tight contour. Centres forced to the native
    index. Acceptance is checked by glyph_check.py (every native texel keeps its majority label)."""
    H, W = idx.shape
    gi = box[4]
    cr = _crop(box, H, W, margin)
    sub = idx[cr[1]:cr[3], cr[0]:cr[2]]
    h, w = sub.shape
    S = staircase_map(sub == gi).astype(np.float32)
    a4 = ndi.gaussian_filter(np.repeat(np.repeat(S, 4, 0), 4, 1), reach * 4, mode='nearest')
    peak = 1.0 / (2 * np.pi * (reach * 4) ** 2) * 16          # one isolated staircase texel (16 px at 4x)
    a = np.clip(up16(a4) / max(peak * 0.6, 1e-6), 0, 1)
    labs = np.unique(sub)
    n = max(3, len(labs))
    Ec = np.zeros((n, h * M, w * M), np.float32)
    Es = np.zeros_like(Ec)
    for j, lab in enumerate(labs):
        oh = np.repeat(np.repeat((sub == lab).astype(np.float32), 4, 0), 4, 1)
        Ec[j] = np.clip(up16(ndi.gaussian_filter(oh, crisp[0] * 4, mode='nearest')), 0, 1) ** crisp[1]
        Es[j] = np.clip(up16(ndi.gaussian_filter(oh, smooth_sigma * 4, mode='nearest')), 0, 1) ** crisp[1]
    Wc_ = Ec / np.maximum(Ec.sum(0), 1e-8)
    Ws_ = Es / np.maximum(Es.sum(0), 1e-8)
    del Ec, Es
    # native-shape guard: every native texel must keep its own index as the majority (>= 0.5 of its area) and no
    # texel may become majority of another index; where the smooth term breaks that, a is withdrawn there (2 passes)
    own = np.kron(sub, np.ones((M, M), np.uint8))
    jown = np.searchsorted(labs, own)
    guard_texels = 0
    for _ in range(3):
        Wf = (1 - a) * Wc_ + a * Ws_
        cov_own = np.take_along_axis(Wf, jown[None].astype(np.int64), 0)[0].reshape(h, M, w, M).mean(axis=(1, 3))
        cov_max_other = np.where(np.arange(n)[:, None, None] == jown[None], 0, Wf).max(0).reshape(h, M, w, M).mean(axis=(1, 3))
        bad = (cov_own < 0.5 + 0.05) | (cov_max_other >= 0.5 - 0.05)
        if not bad.any():
            break
        guard_texels += int(bad.sum())
        badm = ndi.binary_dilation(bad, iterations=1)
        a = a * (1 - np.kron(badm.astype(np.float32), np.ones((M, M), np.float32)))
    del Wc_, Ws_
    lab_of = np.zeros(n, np.uint8); lab_of[:len(labs)] = labs
    order = np.argsort(-Wf, axis=0)[:3]
    top_v = np.take_along_axis(Wf, order, 0)
    Lc = lab_of[order]
    tot = np.maximum(top_v.sum(0), 1e-8)
    q0 = np.rint(top_v[0] / tot * 255).astype(np.int32)
    q1 = np.minimum(np.rint(top_v[1] / tot * 255).astype(np.int32), 255 - q0)
    Wc = np.stack([q0, q1]).astype(np.uint8)
    ys, xs = texel_centres(h, M), texel_centres(w, M)
    before = int((Lc[0][np.ix_(ys, xs)] != sub).sum())
    t = Lc[0][np.ix_(ys, xs)]; t[:] = sub; Lc[0][np.ix_(ys, xs)] = t
    t = Wc[0][np.ix_(ys, xs)]; t[:] = 255; Wc[0][np.ix_(ys, xs)] = t
    t = Wc[1][np.ix_(ys, xs)]; t[:] = 0; Wc[1][np.ix_(ys, xs)] = t
    _paste(L, Wt, Lc, Wc, box, cr)
    return dict(kind='glyph-destair', box=list(box[:4]), glyph_index=int(gi), staircase_corner_texels=int(S.sum()),
                smooth_sigma=smooth_sigma, reach=reach, crisp=list(crisp), centre_labels_forced=before,
                guard_withdrawn_texels=guard_texels, guard_ok=not bad.any())


def alt8_mask(idx, threshold=0.35, closing=1, min_blocks=4):
    """8bpp-read-as-4bpp detector: share of texels whose left and right neighbours are equal and differ from them
    (1-texel vertical stripes = alternating hi/lo nibbles), per 8x8 block > threshold and vertical alternation < half
    of it (excludes checkerboard dither), binary closing, components of < min_blocks dropped. Returns the
    native-res bool mask and the flagged 8-texel blocks [[bx, by], ...] (u = 8 * bx, v = 8 * by)."""
    alt = np.zeros(idx.shape, np.float32)
    alt[:, 1:-1] = (idx[:, 2:] == idx[:, :-2]) & (idx[:, 1:-1] != idx[:, :-2])
    altv = np.zeros(idx.shape, np.float32)       # checkerboard dither alternates vertically too; nibble stripes do not
    altv[1:-1, :] = (idx[2:, :] == idx[:-2, :]) & (idx[1:-1, :] != idx[:-2, :])
    bh = alt.reshape(idx.shape[0] // 8, 8, idx.shape[1] // 8, 8).mean(axis=(1, 3))
    bv = altv.reshape(idx.shape[0] // 8, 8, idx.shape[1] // 8, 8).mean(axis=(1, 3))
    b = (bh > threshold) & (bv < 0.5 * bh)
    if closing:
        b = ndi.binary_closing(b, iterations=closing)
    lab, n = ndi.label(b)
    for i in range(1, n + 1):                    # isolated blocks are dither, not an image
        if (lab == i).sum() < min_blocks:
            b[lab == i] = False
    return np.kron(b, np.ones((8, 8), bool)), [[int(x), int(y)] for y, x in np.argwhere(b)]


def native_mask_region(L, Wt, idx, mask):
    """Native pass-through (nearest labels, weight 1) on a native-res mask: NOT HD, pending an 8bpp-mode master."""
    m16 = np.kron(mask, np.ones((M, M), bool))
    nn = np.kron(idx, np.ones((M, M), np.uint8))
    for k in range(3):
        L[k][m16] = nn[m16]
    Wt[0][m16] = 255
    Wt[1][m16] = 0
    return int(mask.sum())
