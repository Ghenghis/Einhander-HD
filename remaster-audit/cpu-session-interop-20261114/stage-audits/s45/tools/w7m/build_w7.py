#!/usr/bin/env python3
"""Build one W7 stage-4/5 deliverable (all pages of one family) from a job spec; writes everything except manifest.json.

    python -I build_w7.py <job.json>

Then review the sheets and run  freeze_w7.py <job.json> <honest.json>  (writes manifest.json, immutable).
Per page: exact-static words (CRC32 re-checked) -> 16x categorical index master (+ glow field for effects, + material
logD for world/enemy/armour) -> renders through the chosen predicted CLUT(s) (CRC32 re-checked) -> 2048/1024 exports with
native classes stamped at every texel centre -> validation -> review sheet (native | HD tile, 16x close, in-game-size
SIMULATION). CPU only; cpu_yield() in every loop; never runs while CPU-QUIET is set.

lane-s5 copy (w7-stage5/tools, copied from w7-stage4/tools 2026-11-13; the w7-stage4 original is lane-s4's and stays
untouched): adds job['shared_pages'] = pages owned by another lane, referenced only (words CRC re-checked, stage keys
listed in build-record.json), never built here. Run with  python -I -B.

s45 merged copy (parallel-stages-20261114/s45/tools/w7m, make_w7m.py): lane-s5 base + lane-s4 opt-in job keys
energy_smooth, glow_break_T, soft.strokes / soft.stroke_min_len and page label_rects (ported verbatim).
"""
import datetime
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w7lib as L7  # noqa: E402
from w7lib import cpu_yield  # noqa: E402

RANK = {'exact-static': 0, 'likely': 1}


def keys_for(stage, tex):
    rows = [k for k in L7.jload(L7.EXPORT / f'stage{stage}' / 'keys.json') if k['key'].startswith(tex + '-')]
    return rows


def review_flags(stage):
    pr = L7.jload(L7.REVIEWDIR / f'stage{stage}' / 'palette-review.json')
    hold = set(pr['cycling_or_runtime_clut_candidate_keys'])
    zero_only = {tuple(p) for p in pr['zero_only_positions']}
    return hold, zero_only, pr


def richness(words):
    return len(set(int(v) for v in words) - {0})


def monotone(rgb, used):
    """Spearman |rho| of luminance vs index over the used opaque entries (ramp test for the glow field)."""
    used = [i for i in used]
    if len(used) < 3:
        return 0.0
    Y = 0.2126 * rgb[used, 0] + 0.7152 * rgb[used, 1] + 0.0722 * rgb[used, 2]
    ra = np.argsort(np.argsort(used)); rb = np.argsort(np.argsort(Y))
    return float(abs(np.corrcoef(ra, rb)[0, 1]))


def pick_window(idx, rgb, cls, w, h):
    Y = 0.2126 * rgb[idx, 0] + 0.7152 * rgb[idx, 1] + 0.0722 * rgb[idx, 2]
    vis = cls[idx] != 0
    best, by, bx = -1, 0, 0
    for y in range(0, 256 - h + 1, 8):
        for x in range(0, 256 - w + 1, 8):
            v = vis[y:y + h, x:x + w]
            if v.mean() < 0.6:
                continue
            s = float(Y[y:y + h, x:x + w][v].std()) * v.mean() + 4 * len(np.unique(idx[y:y + h, x:x + w]))
            if s > best:
                best, by, bx = s, y, x
    return by, bx


def review_sheet(path, tex, key, idx, rgb, cls, rgb16, c16, a2048, a1024):
    nat = L7.native_rgba(idx, rgb, cls)
    tiles = []
    # A: full tile, native nearest 2x vs HD 1024 box-down to 512
    A0 = Image.fromarray(L7.on_bg(nat)).resize((512, 512), Image.NEAREST)
    A1 = Image.fromarray(L7.on_bg(a1024)).resize((512, 512), Image.BOX)
    L7.label(A0, 'NATIVE %s (nearest)' % key); L7.label(A1, 'HD runtime-1024 (box view)')
    tiles.append((A0, A1))
    # B: 16x close (32x32 texels)
    y, x = pick_window(idx, rgb, cls, 32, 32)
    B0 = Image.fromarray(L7.on_bg(nat[y:y + 32, x:x + 32])).resize((512, 512), Image.NEAREST)
    hd = np.dstack([np.clip(np.rint(rgb16[y * 16:(y + 32) * 16, x * 16:(x + 32) * 16]), 0, 255).astype(np.uint8),
                    c16[y * 16:(y + 32) * 16, x * 16:(x + 32) * 16]])
    B1 = Image.fromarray(L7.on_bg(hd))
    L7.label(B0, 'NATIVE 16x u%d-%d v%d-%d' % (x, x + 31, y, y + 31)); L7.label(B1, 'HD master 16x (4096)')
    tiles.append((B0, B1))
    # C: in-game size SIMULATION: 9 px per texel (2880x2160 internal), bilinear from runtime-2048, no mips
    y, x = pick_window(idx, rgb, cls, 56, 40)
    C0 = Image.fromarray(L7.on_bg(nat[y:y + 40, x:x + 56])).resize((56 * 9, 40 * 9), Image.NEAREST)
    crop = a2048[y * 8:(y + 40) * 8, x * 8:(x + 56) * 8]
    sim = L7.bilinear_resample(L7.on_bg(crop).astype(np.float32), 9 / 8)
    C1 = Image.fromarray(np.clip(np.rint(sim), 0, 255).astype(np.uint8)[:40 * 9, :56 * 9])
    L7.label(C0, 'NATIVE in-game size 9 px/texel'); L7.label(C1, 'SIMULATION 2048 bilinear no-mip 9 px/texel')
    tiles.append((C0, C1))
    W = 8 + max(a.width + b.width + 8 for a, b in tiles) + 8
    Hh = 30 + sum(max(a.height, b.height) + 10 for a, b in tiles)
    sheet = Image.new('RGB', (W, Hh), (40, 40, 48))
    L7.label(sheet, 'W7 %s %s - predicted-static source, import only after live capture; panel C is a SIMULATION' % (tex, key), (8, 8))
    yy = 30
    for a, b in tiles:
        sheet.paste(a, (8, yy)); sheet.paste(b, (8 + a.width + 8, yy)); yy += max(a.height, b.height) + 10
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return L7.sha256(path)


def energy_gate(a, idx, rgb, cls, size, cell=32, tol=0.06):
    """FX contract: per cell, mean light (luminance of visible texels) within +-tol of native; scalar fix outside."""
    f = size // 256
    Yn = 0.2126 * rgb[idx, 0] + 0.7152 * rgb[idx, 1] + 0.0722 * rgb[idx, 2]
    vis_n = cls[idx] != 0
    out = []
    for cy in range(0, 256, cell):
        for cx in range(0, 256, cell):
            vn = vis_n[cy:cy + cell, cx:cx + cell]
            if vn.sum() < 8:
                continue
            en = float(Yn[cy:cy + cell, cx:cx + cell][vn].sum()) / vn.size
            blk = a[cy * f:(cy + cell) * f, cx * f:(cx + cell) * f]
            vh = blk[..., 3] != 0
            Yh = 0.2126 * blk[..., 0] + 0.7152 * blk[..., 1] + 0.0722 * blk[..., 2]
            eh = float(Yh[vh].sum()) / (vh.size)
            ratio = eh / max(en, 1e-6)
            fix = 1.0
            if abs(ratio - 1) > tol and eh > 0:
                fix = 1.0 / ratio
                rgbb = blk[..., :3].astype(np.float32)
                rgbb[vh] = np.clip(rgbb[vh] * fix, 0, 255)
                blk[..., :3] = np.rint(rgbb).astype(np.uint8)
            out.append(dict(cell=[cx, cy, cell, cell], ratio_before=round(ratio, 4), scale_applied=round(fix, 4)))
    return out


def energy_gate_smooth(a, idx, rgb, cls, size, cell=32, tol=0.06, iters=4, gain_range=(0.5, 2.0)):
    """Opt-in FX energy gate (job 'energy_smooth': true; lane-s4 2026-11-13). Same per-cell contract as energy_gate,
    but the correction is a smooth gain field: per-cell log-gains, bilinear between cell centres (texel-centred),
    iterated so each cell's mean light lands near native; no straight brightness step at cell borders. Cells whose
    native light is ~0 (all black) only receive leakage from neighbours: they are zeroed hard, as before, and do not
    pull their neighbours' gain. Gains are clamped to gain_range."""
    f = size // 256
    n = 256 // cell
    Yn = 0.2126 * rgb[idx, 0] + 0.7152 * rgb[idx, 1] + 0.0722 * rgb[idx, 2]
    vis_n = cls[idx] != 0
    en = np.zeros((n, n)); valid = np.zeros((n, n), bool)
    for j in range(n):
        for i in range(n):
            vn = vis_n[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell]
            valid[j, i] = vn.sum() >= 8
            en[j, i] = float(Yn[j * cell:(j + 1) * cell, i * cell:(i + 1) * cell][vn].sum()) / vn.size
    zero = valid & (en <= 1e-3)
    upd_ok = valid & ~zero
    rgbf = a[..., :3].astype(np.float32)
    vh = a[..., 3] != 0
    Yh = 0.2126 * rgbf[..., 0] + 0.7152 * rgbf[..., 1] + 0.0722 * rgbf[..., 2]
    Yh[~vh] = 0

    def cell_energy(Y):
        return Y.reshape(n, cell * f, n, cell * f).sum(axis=(1, 3)) / float((cell * f) ** 2)

    def gain_field(lg):
        return np.exp(L7.ndi.zoom(lg, size / n, order=1, mode='nearest', grid_mode=True)).astype(np.float32)

    eh0 = cell_energy(Yh)
    ratio0 = eh0 / np.maximum(en, 1e-6)
    lg = np.zeros((n, n))
    lo, hi = np.log(gain_range[0]), np.log(gain_range[1])
    for _ in range(iters):
        cpu_yield()
        G = gain_field(lg)
        r = cell_energy(Yh * G) / np.maximum(en, 1e-6)
        upd = upd_ok & (np.abs(r - 1) > tol / 2) & (r > 0)
        if not upd.any():
            break
        lg[upd] -= np.log(r[upd])
        lg = np.clip(lg, lo, hi)
    G = gain_field(lg)
    rgbf = np.where(vh[..., None], np.clip(rgbf * G[..., None], 0, 255), rgbf)
    for j, i in np.argwhere(zero):
        rgbf[j * cell * f:(j + 1) * cell * f, i * cell * f:(i + 1) * cell * f] = 0
    a[..., :3] = np.rint(rgbf).astype(np.uint8)
    Yf = 0.2126 * rgbf[..., 0] + 0.7152 * rgbf[..., 1] + 0.0722 * rgbf[..., 2]
    Yf[~vh] = 0
    ratio1 = cell_energy(Yf) / np.maximum(en, 1e-6)
    out = []
    for j, i in np.argwhere(valid):
        out.append(dict(cell=[int(i * cell), int(j * cell), cell, cell], ratio_before=round(float(ratio0[j, i]), 4),
                        gain_centre=0.0 if zero[j, i] else round(float(np.exp(lg[j, i])), 4),
                        ratio_after=None if zero[j, i] else round(float(ratio1[j, i]), 4), native_black=bool(zero[j, i]),
                        mode='smooth'))
    return out


def main():
    job = L7.jload(sys.argv[1])
    cpu_yield()
    t0 = time.time()
    root = Path(job['root']) / job['name']
    assert not (root / 'manifest.json').exists(), 'frozen deliverable already has a manifest (immutable)'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    stage = job['stage']
    hold, zero_only, pr = review_flags(stage)
    cluts = L7.stage_cluts(stage)
    record = dict(name=job['name'], stage=stage, built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  job=job, pages={}, validation={})
    for pg in job['pages']:
        cpu_yield()
        tex = pg['tex']
        mode = pg.get('mode', job['mode'])
        idx, src = L7.load_page(stage, tex)
        ks = keys_for(stage, tex)
        excl_zero = [k['key'] for k in ks if k['key'][9:] == L7.ZERO_PAL]
        cand = []
        for k in ks:
            pal = k['key'][9:]
            if pal == L7.ZERO_PAL:
                continue
            words = cluts.get((k['clut_xy'][0], k['clut_xy'][1], pal))
            if words is None:
                continue
            cand.append((k, words))
        renderable = [k for k, _ in cand]

        def coverage(kw):
            """Review/reference CLUT score: share of the page it draws opaque x colour richness; exact-static
            keys get a 10 % bonus, then pairing count breaks ties."""
            cl = L7.clut_rgba(kw[1])[1]
            s = float((cl[idx] != 0).mean()) * (0.5 + min(richness(kw[1]), 15) / 30.0)
            return (-(s * (1.1 if kw[0]['confidence'] == 'exact-static' else 1.0)), -kw[0]['pair_count'])
        cand.sort(key=coverage)
        if pg.get('chosen_pal'):
            cand.sort(key=lambda kw: kw[0]['key'][9:] != pg['chosen_pal'])
        render_set = [cand[0]] + [kw for kw in cand[1:] if kw[0]['confidence'] == 'exact-static']
        render_set = render_set[:job.get('max_renders', 3)]
        chosen_k, chosen_w = render_set[0]
        ref_rgb, ref_cls = L7.clut_rgba(chosen_w)
        # ---- master
        soft = dict(job.get('soft', {}), **pg.get('soft', {}))
        # dither partners must be close in colour under EVERY renderable static CLUT of this page
        uniq = {}
        for k, w in cand:
            uniq[k['key'][9:]] = w
        N = L7.near_matrix([L7.clut_rgba(w) for w in uniq.values()], soft.get('near_T', 48.0), soft.get('near_quorum', 1.0))
        xtra = dict(strokes=True, stroke_min_len=soft.get('stroke_min_len', 3)) if soft.get('strokes') else {}  # opt-in (lane-s4 v3)
        Lb, Wt, sstats = L7.soft_labels_toned(idx, N, crisp=tuple(soft.get('crisp', (0.42, 4.0))),
                                             blend_sigma=soft.get('blend_sigma', 0.9), no_busy=soft.get('no_busy', False),
                                             **xtra)
        sstats['near_matrix_cluts'] = len(uniq)
        # lane-s5 v2 regions: FX contract boxes, 8bpp native pass-through, glyph de-stair (in this order)
        regions = []
        for b_ in pg.get('fx_boxes', []):
            cpu_yield()
            regions.append(L7.fx_region(Lb, Wt, idx, [L7.clut_rgba(w) for w in uniq.values()], b_, **job.get('fx_region', {})))
        nat_mask = None
        if pg.get('native_8bpp'):
            nat_mask, blocks8 = L7.alt8_mask(idx, **pg['native_8bpp'])
            regions.append(dict(kind='native-8bpp-pending', rule=dict(pg['native_8bpp'], detector='alt8_mask'),
                                texels=L7.native_mask_region(Lb, Wt, idx, nat_mask), blocks8=blocks8,
                                note='8bpp sub-image read as 4bpp: native pass-through, NOT HD; pending an 8bpp-mode '
                                     'master after the capture shows the 8bpp draws (texpage, 256-colour CLUT, key)'))
        for gb in pg.get('glyph_destair', []):
            cpu_yield()
            regions.append(L7.destair_glyph(Lb, Wt, idx, gb, **job.get('destair', {})))
        glow, glow_mask, glow_info = None, None, None
        if mode in ('effect', 'sky'):
            classes = [L7.clut_rgba(w)[1] for _, w in render_set]
            opaque = [i for i in range(16) if all(c[i] != 0 for c in classes)]
            used = [i for i in np.unique(idx).tolist() if i in opaque]
            rho = min(monotone(L7.clut_rgba(w)[0], used) for _, w in render_set)
            glow_info = dict(ramp_spearman_min=round(rho, 3), opaque_indices=opaque,
                             transparency_consistent=all((c == 0).tolist() == (classes[0] == 0).tolist() for c in classes))
            if rho >= job.get('ramp_min', 0.85):
                glow = L7.glow_field(idx, opaque, soft.get('glow_sigma', 0.55))
                if pg.get('turbulence', job.get('turbulence', 0)):
                    rng = np.random.default_rng(L7.zlib.crc32((job.get('seed_name', job['name']) + tex).encode()))
                    n4 = L7.ndi.gaussian_filter(rng.standard_normal((1024, 1024)).astype(np.float32), 6, mode='wrap')
                    n4 += 0.5 * L7.ndi.gaussian_filter(rng.standard_normal((1024, 1024)).astype(np.float32), 2.5, mode='wrap')
                    n16 = L7.up16(n4 / max(n4.std(), 1e-6))
                    glow = glow + pg.get('turbulence', job.get('turbulence', 0)) * n16
                glow_mask = np.ones(glow.shape, bool)
                glow_info['used'] = 'glow (continuous index, RGB free of class thresholds)'
                gbT = pg.get('glow_break_T', job.get('glow_break_T'))
                if gbT:   # opt-in (lane-s4, 2026-11-13): crisp labels where the index path leaves the colour segment
                    B = L7.glow_break_pairs([L7.clut_rgba(w)[0] for _, w in render_set], gbT)
                    glow_mask, nbrk = L7.glow_break_weight(idx, B)
                    glow_info.update(glow_break_T=gbT, broken_pairs=[[int(i), int(j)] for i, j in np.argwhere(np.triu(B))],
                                     broken_texels=nbrk, glow_weight_mean=round(float(glow_mask.mean()), 4))
                    glow_info['used'] = 'glow with break weight (labels where the index path leaves the colour segment)'
                rects = pg.get('label_rects')
                if rects:   # opt-in (lane-s4, 2026-11-13, effects v3): crisp categorical labels inside these texel rects
                    rm = np.zeros(idx.shape, np.float32)
                    for x, y, w_, h_ in rects:
                        rm[y:y + h_, x:x + w_] = 1
                    rm4 = L7.ndi.gaussian_filter(np.repeat(np.repeat(rm, 4, 0), 4, 1), 0.35 * 4, mode='nearest')
                    keep = 1.0 - np.clip(L7.up16(rm4), 0, 1)
                    glow_mask = (glow_mask.astype(np.float32) if glow_mask.dtype == bool else glow_mask) * keep
                    glow_info.update(label_rects=rects, glow_weight_mean=round(float(glow_mask.mean()), 4))
                    glow_info['used'] += '; categorical labels inside label_rects'
            else:
                glow_info['used'] = 'shape (palette is not a ramp: categorical soft labels)'
        mat = dict(job.get('material', {}), **pg.get('material', {})) if mode in ('world', 'enemy', 'armour') else {}
        mat_run = dict(mat, _exclude_texels=nat_mask) if (mat and nat_mask is not None) else mat
        logD = L7.material_logD(Lb, Wt, ref_rgb, ref_cls, idx, mat_run, job.get('seed_name', job['name']) + tex) if mat else None
        mdir = root / 'master'
        mdir.mkdir(exist_ok=True)
        np.savez_compressed(mdir / f'{tex}-labels16.npz', labels=Lb, weights=Wt)
        np.save(mdir / f'{tex}-native-idx.npy', idx)
        if logD is not None:
            np.save(mdir / f'{tex}-logD8-f16.npy', logD)
        if glow is not None:
            np.save(mdir / f'{tex}-glow16-f16.npy', glow.astype(np.float16))
            if glow_mask is not None and glow_mask.dtype != bool:
                np.save(mdir / f'{tex}-glowweight16-u8.npy', np.rint(glow_mask * 255).astype(np.uint8))
        # ---- renders
        prec = dict(tex=tex, member=pg['member'], page_xy=pg['page_xy'], mode=mode, family=job['family'], source=src,
                    regions=regions,
                    soft_stats=sstats, glow=glow_info, material=mat or None,
                    logD_p1_p99=[float(np.percentile(logD, 1)), float(np.percentile(logD, 99))] if logD is not None else None,
                    keys=dict(rendered=[], renderable_later=[], palette_hold=[], excluded_zero_clut=excl_zero,
                              excluded_stale=[]))
        for k, words in render_set:
            cpu_yield()
            key = k['key']
            assert L7.crc(words.tobytes()) == key[9:]
            rgb, cls = L7.clut_rgba(words)
            rgb16, c16 = L7.render(Lb, Wt, rgb, cls, logD=logD, glow=glow, glow_mask=glow_mask)
            ent = dict(key=key, clut_xy=k['clut_xy'], confidence=k['confidence'], pair_count=k['pair_count'],
                       chosen=(key == chosen_k['key']), palette_hold=key in hold, exports={})
            for size, sub in ((2048, 'runtime-2048'), (1024, 'runtime-1024')):
                cpu_yield()
                a, changed = L7.export_rgba(rgb16, c16, idx, rgb, cls, size)
                if mode == 'effect':
                    ent.setdefault('energy', {})[str(size)] = L7_energy = (
                        energy_gate_smooth if job.get('energy_smooth') else energy_gate)(a, idx, rgb, cls, size)
                    a, changed2 = L7.export_rgba(a[..., :3].astype(np.float32), a[..., 3], idx, rgb, cls, size)
                v = L7.validate(a, idx, cls)
                p = root / sub / f'{key}.png'
                h = L7.save_png(a, p)
                ent['exports'][str(size)] = dict(path=f'{sub}/{key}.png', sha256=h, centre_classes_stamped=changed, validation=v)
                record['validation'][f'{sub}/{key}.png'] = v
                if size == 2048:
                    a2048 = a
                else:
                    a1024 = a
            if key == chosen_k['key']:
                ent['review'] = dict(path=f'review/{key}-review.png',
                                     sha256=review_sheet(root / 'review' / f'{key}-review.png', tex, key, idx, rgb, cls, rgb16, c16, a2048, a1024))
            prec['keys']['rendered'].append(ent)
            del rgb16, c16
        done = {e['key'] for e in prec['keys']['rendered']}
        prec['keys']['renderable_later'] = [dict(key=k['key'], clut_xy=k['clut_xy'], confidence=k['confidence'],
                                                 palette_hold=k['key'] in hold) for k in renderable if k['key'] not in done]
        prec['keys']['palette_hold'] = sorted(k['key'] for k in ks if k['key'] in hold)
        prec['keys']['index_master_only_runtime_clut_positions'] = sorted(
            {tuple(k['clut_xy']) for k in ks if tuple(k['clut_xy']) in zero_only})
        record['pages'][tex] = prec
        print(tex, mode, 'rendered', len(prec['keys']['rendered']), 'later', len(prec['keys']['renderable_later']),
              'hold', len(prec['keys']['palette_hold']), 'zero', len(excl_zero),
              'mismatch', [e['exports'][s]['validation']['centre_class_mismatch'] for e in prec['keys']['rendered'] for s in e['exports']],
              'glow', glow_info and glow_info['used'][:5], '%.0fs' % (time.time() - t0), flush=True)
    # shared pages owned by another lane: reference only (words re-checked, stage keys listed), never built here
    record['shared_pages'] = {}
    for sp_ in job.get('shared_pages', []):
        cpu_yield()
        tex = sp_['tex']
        _, src = L7.load_page(stage, tex)
        ks = keys_for(stage, tex)
        record['shared_pages'][tex] = dict(
            sp_, source=src, built_here=False,
            stage_keys=[dict(key=k['key'], clut_xy=k['clut_xy'], confidence=k['confidence'], pair_count=k['pair_count'],
                             palette_hold=k['key'] in hold, zero_clut=k['key'][9:] == L7.ZERO_PAL,
                             renderable_static=cluts.get((k['clut_xy'][0], k['clut_xy'][1], k['key'][9:])) is not None)
                        for k in ks])
        print(tex, 'shared page referenced (owner %s), stage keys %d' % (sp_['owner'], len(ks)), flush=True)
    # builder copies (provenance) and swatch provenance
    bdir = root / 'builder'
    bdir.mkdir(exist_ok=True)
    for f in ('w7lib.py', 'build_w7.py', 'freeze_w7.py', 'glyph_check.py', 'verify_frozen.py'):
        sp = Path(__file__).resolve().parent / f
        if sp.exists():
            shutil.copy2(sp, bdir / f)
    shutil.copy2(sys.argv[1], bdir / Path(sys.argv[1]).name)
    used_sw = sorted({n for pg in record['pages'].values() for n, _ in ((pg['material'] or {}).get('swatch') or [])})
    if used_sw:
        cdir = root / 'comfy'
        cdir.mkdir(exist_ok=True)
        for n in used_sw:
            sp = L7.SWATCHES[n]
            for f in sp.parent.glob(n + '-*'):
                if f.suffix in ('.json', '.png') and ('tileable' in f.name or 'graph' in f.name or 'history' in f.name):
                    shutil.copy2(f, cdir / f.name)
    record['seconds'] = round(time.time() - t0, 1)
    (root / 'build-record.json').write_text(json.dumps(record, indent=1, default=str), encoding='utf-8')
    val = dict(convention='class at pixel floor((i+0.5)*scale) of every native texel == class(CLUT[native index]); '
                          'class 0 = raw 0x0000, 255 = STP, 127 = opaque',
               sources='exact-static export words (CRC32 re-checked) + chosen predicted static CLUT (CRC32 re-checked)',
               files=record['validation'],
               total_mismatches=sum(v['centre_class_mismatch'] for v in record['validation'].values()))
    (root / 'native-class-validation.json').write_text(json.dumps(val, indent=1), encoding='utf-8')
    print('done', job['name'], 'mismatches', val['total_mismatches'], '%.0fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
