#!/usr/bin/env python3
"""lane-s5 glyph lock check for the Duerer '13' hull numbers (run after build_w7.py, before freeze_w7.py).

    python -I -B glyph_check.py <deliverable root>

The '13' is painted with native index 0 on two exact-static pages:
  BFC445B0 (3/16, 576,0): rotated '13', components u140-175 v54-67 and u141-175 v74-81;
  3D108041 (3/17, 704,0): upright '13', components u147-158 v182-224 and u164-184 v182-224.
Palette-independent checks on the 16x label master (weight of the glyph index >= 0.5 is 'glyph'):
  IoU and pixel disagreement vs the nearest-neighbour native glyph mask, symmetric boundary deviation (Hausdorff, texels),
  per-glyph-texel coverage (no stroke texel may drop below 0.5), spill onto non-glyph texels, centre labels.
Per rendered key: glyph texel-centre classes in both exports, and the colour at glyph texel centres vs native
(material only: logD is zero-mean per index), plus the relief shading in the 1-texel ring around the glyph.
Writes <root>/glyph-check.json (summary is copied into the manifest by freeze_w7.py) and review/glyph-<TEX>.png.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import w7lib as L7  # noqa: E402
from w7lib import cpu_yield  # noqa: E402

M = L7.M
GLYPHS = [
    dict(tex='BFC445B0', name='13 (rotated)', box=[138, 52, 178, 84], glyph_idx=0),
    dict(tex='3D108041', name='13', box=[145, 180, 187, 227], glyph_idx=0),
]


def boundary_dev(a, b):
    """Max distance (px) from a pixel in a-not-b to the nearest pixel of b, and vice versa (Hausdorff on the diff)."""
    da = ndi.distance_transform_edt(~b)          # distance to nearest b pixel
    db = ndi.distance_transform_edt(~a)
    d1 = float(da[a & ~b].max()) if (a & ~b).any() else 0.0
    d2 = float(db[b & ~a].max()) if (b & ~a).any() else 0.0
    return d1, d2


def main():
    root = Path(sys.argv[1])
    rec = L7.jload(root / 'build-record.json')
    stage = rec['stage']
    cl = L7.stage_cluts(stage)
    out = dict(rule="Never alter the number glyphs: the '13' must keep its native extents (tight contours, no outline "
                    "term); checked on the palette-independent label master and on every rendered export",
               glyphs=[])
    for g in GLYPHS:
        cpu_yield()
        tex = g['tex']
        if tex not in rec['pages']:
            continue
        x0, y0, x1, y1 = g['box']
        gi = g['glyph_idx']
        idx, _ = L7.load_page(stage, tex)
        z = np.load(root / 'master' / f'{tex}-labels16.npz')
        Lb = z['labels'][:, y0 * M:y1 * M, x0 * M:x1 * M]
        Wt = z['weights'][:, y0 * M:y1 * M, x0 * M:x1 * M]
        logD = np.load(root / 'master' / f'{tex}-logD8-f16.npy')[y0 * 8:y1 * 8, x0 * 8:x1 * 8] \
            if (root / 'master' / f'{tex}-logD8-f16.npy').exists() else None
        w = [Wt[0].astype(np.float32) / 255, Wt[1].astype(np.float32) / 255]
        w.append(np.clip(1 - w[0] - w[1], 0, 1))
        wg = sum(w[k] * (Lb[k] == gi) for k in range(3))
        hd = wg >= 0.5
        sub = idx[y0:y1, x0:x1]
        nat_t = sub == gi
        nat = np.kron(nat_t, np.ones((M, M), bool))
        inter, union = (hd & nat).sum(), (hd | nat).sum()
        d_hd_out, d_nat_lost = boundary_dev(hd, nat)
        cov = wg.reshape(y1 - y0, M, x1 - x0, M).mean(axis=(1, 3))
        ys, xs = L7.texel_centres(y1 - y0, M), L7.texel_centres(x1 - x0, M)
        cen = Lb[0][np.ix_(ys, xs)]
        res = dict(tex=tex, member=rec['pages'][tex]['member'], name=g['name'], box_uv=[x0, y0, x1, y1], glyph_index=gi,
                   glyph_texels=int(nat_t.sum()),
                   iou_16x=round(float(inter / max(union, 1)), 4),
                   disagree_px_share_of_glyph=round(float((hd ^ nat).sum() / max(nat.sum(), 1)), 4),
                   max_outward_dev_texel=round(d_hd_out / M, 3), max_inward_dev_texel=round(d_nat_lost / M, 3),
                   glyph_texel_coverage_min=round(float(cov[nat_t].min()), 3),
                   glyph_texel_coverage_mean=round(float(cov[nat_t].mean()), 3),
                   glyph_texels_below_half=int((cov[nat_t] < 0.5).sum()),
                   nonglyph_texels_with_spill_ge_half=int((cov[~nat_t] >= 0.5).sum()),
                   centre_label_mismatch=int((cen != sub).sum()),
                   keys=[])
        ring = ndi.binary_dilation(nat_t, iterations=1) & ~nat_t
        page = rec['pages'][tex]
        sheet_key = None
        for e in page['keys']['rendered']:
            cpu_yield()
            key = e['key']
            words = cl[(e['clut_xy'][0], e['clut_xy'][1], key[9:])]
            assert L7.crc(words.tobytes()) == key[9:]
            rgb, cls = L7.clut_rgba(words)
            kr = dict(key=key, glyph_rgb_native=[int(v) for v in rgb[gi]], glyph_class=int(cls[gi]))
            for size in ('2048', '1024'):
                a = np.asarray(Image.open(root / e['exports'][size]['path']))
                f = int(size) // 256
                ty, tx = L7.texel_centres(256, f), L7.texel_centres(256, f)
                c = a[np.ix_(ty[y0:y1], tx[x0:x1])]
                kr[f'centre_class_mismatch_{size}'] = int((c[..., 3] != cls[sub]).sum())
                gl = c[nat_t][:, :3].astype(np.int32)
                kr[f'glyph_centre_rgb_maxabs_{size}'] = int(np.abs(gl - rgb[gi].astype(np.int32)).max()) if len(gl) else 0
                rr = c[ring][:, :3].astype(np.float32)
                nr = rgb[sub][ring].astype(np.float32)
                if len(rr):
                    Yr = rr @ np.array([0.2126, 0.7152, 0.0722], np.float32) + 1
                    Yn = nr @ np.array([0.2126, 0.7152, 0.0722], np.float32) + 1
                    kr[f'ring_luma_ratio_p5_p95_{size}'] = [round(float(np.percentile(Yr / Yn, 5)), 3),
                                                            round(float(np.percentile(Yr / Yn, 95)), 3)]
            res['keys'].append(kr)
            if e.get('chosen'):
                sheet_key = (key, rgb, cls, e)
        # review sheet: native 16x | HD master 16x (chosen key) | runtime-2048 (2x nearest) | native outline on HD
        if sheet_key:
            key, rgb, cls, e = sheet_key
            r16, c16 = L7.render(Lb, Wt, rgb, cls, logD=logD)
            hdimg = L7.on_bg(np.dstack([np.clip(np.rint(r16), 0, 255).astype(np.uint8), c16]))
            natimg = L7.on_bg(np.kron(L7.native_rgba(sub, rgb, cls), np.ones((M, M, 1), np.uint8)))
            a = np.asarray(Image.open(root / e['exports']['2048']['path']))[y0 * 8:y1 * 8, x0 * 8:x1 * 8]
            rt = np.asarray(Image.fromarray(L7.on_bg(a)).resize(((x1 - x0) * M, (y1 - y0) * M), Image.NEAREST))
            ov = hdimg.copy()
            edge = nat & ~ndi.binary_erosion(nat, iterations=2)
            ov[edge] = (255, 40, 200)
            panels = [(natimg, 'NATIVE %s 16x nearest' % key), (hdimg, 'HD master 16x (4096)'),
                      (rt, 'runtime-2048 (shown 2x nearest)'), (ov, 'native glyph outline (magenta) on HD')]
            Wd = sum(p.shape[1] + 8 for p, _ in panels) + 8
            Hd = panels[0][0].shape[0] + 40
            sh = Image.new('RGB', (Wd, Hd), (40, 40, 48))
            L7.label(sh, "lane-s5 glyph check %s '%s' u%d-%d v%d-%d  IoU %.4f  max dev out %.2f / in %.2f texel" % (
                tex, g['name'], x0, x1 - 1, y0, y1 - 1, res['iou_16x'], res['max_outward_dev_texel'],
                res['max_inward_dev_texel']), (8, 8))
            xx = 8
            for p, t in panels:
                im = Image.fromarray(p)
                L7.label(im, t)
                sh.paste(im, (xx, 32))
                xx += p.shape[1] + 8
            pth = root / 'review' / f'glyph-{tex}.png'
            sh.save(pth)
            res['review'] = dict(path=f'review/glyph-{tex}.png', sha256=L7.sha256(pth))
        out['glyphs'].append(res)
        print(json.dumps({k: v for k, v in res.items() if k != 'keys'}), flush=True)
    gl = out['glyphs']
    out['summary'] = dict(
        file='glyph-check.json', glyphs=len(gl),
        min_iou_16x=min((x['iou_16x'] for x in gl), default=None),
        max_outward_dev_texel=max((x['max_outward_dev_texel'] for x in gl), default=None),
        max_inward_dev_texel=max((x['max_inward_dev_texel'] for x in gl), default=None),
        glyph_texels_below_half=sum(x['glyph_texels_below_half'] for x in gl),
        nonglyph_texels_with_spill_ge_half=sum(x['nonglyph_texels_with_spill_ge_half'] for x in gl),
        centre_label_mismatch=sum(x['centre_label_mismatch'] for x in gl),
        export_centre_class_mismatch=sum(k[f'centre_class_mismatch_{s}'] for x in gl for k in x['keys'] for s in ('2048', '1024')),
        reviews=[x.get('review', {}).get('path') for x in gl])
    (root / 'glyph-check.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('summary', json.dumps(out['summary']))


if __name__ == '__main__':
    main()
