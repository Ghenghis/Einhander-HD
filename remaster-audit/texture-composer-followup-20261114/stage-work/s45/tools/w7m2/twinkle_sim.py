#!/usr/bin/env python3
"""lane-s5 motion SIMULATION of twinkle on the FX regions of the Duerer armour pages (no game, no GPU).

    python -I -B twinkle_sim.py <v1 root> <v2 root> <out json> <out sheet png> [duerer|world]

For each FX region and display scale (9 px per native texel = nominal 4K; 3 px per native texel = a shrunk / distant
sprite, minified 2048 texture), a 24-frame fly-past at v = (0.37, 0.23) display px per frame is sampled the way the
runtime does it: runtime-2048 RGBA (class 0 shown as the dark review background) with bilinear filtering and NO mips;
the stock reference is the native page through the same CLUT with nearest sampling (PSX look). Each frame is motion-
compensated back to frame 0 by an exact Fourier shift; what does not follow the motion is twinkle/crawl:
  twinkle = RMS over frames and interior pixels of (compensated frame - mean compensated frame) / RMS contrast of the
            mean compensated frame   (0 = perfectly stable texture in motion)
  mean_flicker = std over frames of the region mean luminance / its mean (whole-sprite brightness pumping)
Labels: SIMULATION. Same key (review CLUT) for v1 and v2.
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

REGION_SETS = {}
REGIONS = [('3D108041', 'shock rings', [0, 0, 176, 80]), ('3D108041', 'burst/crater', [0, 80, 80, 176]),
           ('3D108041', 'debris bursts', [176, 0, 256, 112]), ('BFC445B0', 'flames', [192, 0, 256, 128]),
           ('1168CC84', 'crater', [128, 204, 192, 256]),
           ('1168CC84', 'camouflage armour plate (material control)', [16, 16, 112, 112])]
REGION_SETS['duerer'] = REGIONS
REGION_SETS['world'] = [('1A2ACF78', 'smoke puffs (FX)', [128, 128, 256, 192]),
                        ('1A2ACF78', 'dark puff sprites (FX)', [0, 128, 128, 192]),
                        ('1A2ACF78', 'smoke trails (FX)', [0, 192, 240, 224]),
                        ('9F3D98EF', 'plates and panels (material control)', [0, 0, 64, 64]),
                        ('7E088757', 'mottled plates (material control)', [0, 128, 64, 192]),
                        ('452F3CC3', 'panels (material control)', [0, 192, 128, 256]),
                        ('503474BD', 'wall plating (material control)', [0, 0, 64, 64])]
SCALES = [9.0, 3.0]
FRAMES, V = 24, (0.37, 0.23)
YW = np.array([0.2126, 0.7152, 0.0722], np.float32)


def frames_for(img, f_tex, box, s, order):
    """img: (H, W, 3) float composite at f_tex px per native texel; returns list of luminance frames (display grid)."""
    x0, y0, x1, y1 = box
    pad = 4                                             # native texels of context around the region
    w_d = int((x1 - x0 + 2 * pad) * s); h_d = int((y1 - y0 + 2 * pad) * s)
    Y = img @ YW
    out = []
    for t in range(FRAMES):
        X, Yy = np.meshgrid(np.arange(w_d, dtype=np.float32), np.arange(h_d, dtype=np.float32))
        u = ((X + 0.5 - V[0] * t) / s + (x0 - pad)) * f_tex - 0.5
        v = ((Yy + 0.5 - V[1] * t) / s + (y0 - pad)) * f_tex - 0.5
        if order == 0:
            u, v = np.floor(u + 0.5), np.floor(v + 0.5)
        out.append(ndi.map_coordinates(Y, [v, u], order=order, mode='nearest').astype(np.float32))
    return out


def measure(fr, s):
    m = int(np.ceil(max(V) * FRAMES)) + int(2 * s) + 2
    comp = []
    for t, f in enumerate(fr):
        F = np.fft.fft2(f)
        c = np.real(np.fft.ifft2(ndi.fourier_shift(F, (-V[1] * t, -V[0] * t))))   # undo the +v*t motion
        comp.append(c[m:-m, m:-m])
    comp = np.stack(comp)
    mean = comp.mean(0)
    contrast = float(np.sqrt(((mean - mean.mean()) ** 2).mean()))
    tw = float(np.sqrt(((comp - mean) ** 2).mean())) / max(contrast, 1e-6)
    means = np.array([f.mean() for f in fr])
    return dict(twinkle=round(tw, 4), mean_flicker=round(float(means.std() / max(means.mean(), 1e-6)), 5),
                contrast=round(contrast, 2)), comp.std(0)


def main():
    v1, v2, out_json, out_png = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    regions = REGION_SETS[sys.argv[5] if len(sys.argv) > 5 else 'duerer']   # optional 5th arg: duerer | world
    recs = {r: L7.jload(r / 'build-record.json') for r in (v1, v2)}
    cl = L7.stage_cluts(5)
    res, tiles = [], []
    for tex, name, box in regions:
        cpu_yield()
        idx, _ = L7.load_page(5, tex)
        e1 = [e for e in recs[v1]['pages'][tex]['keys']['rendered'] if e['chosen']][0]
        e2 = [e for e in recs[v2]['pages'][tex]['keys']['rendered'] if e['chosen']][0]
        assert e1['key'] == e2['key']
        words = cl[(e1['clut_xy'][0], e1['clut_xy'][1], e1['key'][9:])]
        rgb, cls = L7.clut_rgba(words)
        nat = L7.on_bg(L7.native_rgba(idx, rgb, cls)).astype(np.float32)
        a1 = L7.on_bg(np.asarray(Image.open(v1 / e1['exports']['2048']['path']))).astype(np.float32)
        a2 = L7.on_bg(np.asarray(Image.open(v2 / e2['exports']['2048']['path']))).astype(np.float32)
        row = dict(tex=tex, region=name, box=box, key=e1['key'], scales={})
        for s in SCALES:
            cpu_yield()
            r = {}
            maps = {}
            for lab, img, f, order in (('native_nearest', nat, 1, 0), ('v1_2048_bilinear', a1, 8, 1), ('v2_2048_bilinear', a2, 8, 1)):
                r[lab], maps[lab] = measure(frames_for(img, f, box, s, order), s)
            row['scales'][f'{s:g}px_per_texel'] = r
            if s == 3.0:
                tiles.append((tex, name, maps))
        res.append(row)
        print(tex, name, json.dumps(row['scales']), flush=True)
    out_json.write_text(json.dumps(dict(
        label='SIMULATION (bilinear no-mip fly-past, Fourier motion compensation); not an in-game capture',
        frames=FRAMES, velocity_px_per_frame=V, metrics=__doc__.split('compensated back')[1].split('Labels')[0].strip(),
        regions=res), indent=1), encoding='utf-8')
    # sheet: temporal std maps at 3 px/texel (bright = twinkle), native | v1 | v2 per region
    rows = []
    for tex, name, maps in tiles:
        ims = []
        for lab in ('native_nearest', 'v1_2048_bilinear', 'v2_2048_bilinear'):
            mp = np.clip(maps[lab] * 6, 0, 255).astype(np.uint8)
            im = Image.fromarray(mp).convert('RGB')
            L7.label(im, '%s %s %s' % (tex, name, lab))
            ims.append(im)
        rows.append(ims)
    W = max(8 + sum(i.width + 8 for i in r) for r in rows)
    H = 30 + sum(max(i.height for i in r) + 8 for r in rows)
    sh = Image.new('RGB', (W, H), (40, 40, 48))
    ImageDraw.Draw(sh).text((8, 8), 'SIMULATION twinkle map (temporal std after motion compensation x6), 3 px per native '
                                   'texel, 2048 bilinear no-mip; bright = twinkles', fill=(255, 220, 120))
    y = 30
    for r in rows:
        x = 8
        for im in r:
            sh.paste(im, (x, y)); x += im.width + 8
        y += max(i.height for i in r) + 8
    sh.save(out_png)


if __name__ == '__main__':
    main()
