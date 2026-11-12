"""Fresh vector score digits and observed Cannon identifier/tail, in exact cells."""
from pathlib import Path
import argparse
import json
import hashlib
from datetime import datetime, timezone

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_three_asset_proof import verify_stock

ROOT = Path(__file__).resolve().parent.parent
FONT = Path('C:/Windows/Fonts/bahnschrift.ttf')
SCALE = 16


def ref(path):
    path = Path(path)
    return dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def vector(text, native):
    a = np.array(native.convert('RGBA'))
    yy, xx = np.where((a[:, :, 3] > 0) & (a[:, :, :3].max(2) > 35))
    if not len(xx):
        raise ValueError('Source lettering missing ' + text)
    # Native pixels define registration only. All new strokes come from the
    # vector font, with a compact independently antialiased edge.
    box = [int(xx.min()), int(yy.min()), int(xx.max())+1, int(yy.max())+1]
    font = ImageFont.truetype(str(FONT), 256)
    temp = Image.new('L', (2048, 400))
    ImageDraw.Draw(temp).text((16, 16), text, font=font, fill=255, stroke_width=0)
    ink = temp.crop(temp.getbbox())
    width = max(8, (box[2]-box[0])*SCALE-6)
    height = max(8, (box[3]-box[1])*SCALE-5)
    ink = ink.resize((width, height), Image.Resampling.LANCZOS)
    mask = Image.new('L', (native.width*SCALE, native.height*SCALE))
    mask.paste(ink, (box[0]*SCALE+3, box[1]*SCALE+2))
    coverage = np.array(mask)
    samples = a[(a[:, :, 3] > 0) & (a[:, :, :3].max(2) > 35)]
    face = samples[np.argmax(samples[:, :3].max(1))]
    rgb = np.rint(coverage[:, :, None].astype(np.float32)*face[:3]/255).astype(np.uint8)
    rgba = np.zeros((*coverage.shape, 4), np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = np.where(coverage > 1, int(face[3]), 0)
    return rgba, box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, default=ROOT/'remaster-audit/dev-center-evidence/typography-repair-20261112-v10/candidate.json')
    parser.add_argument('--output', type=Path, default=ROOT/'remaster-audit/hud-restoration/counter-vector-candidate-v2')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise ValueError('Immutable output already exists')
    parent = json.loads(args.parent.read_bytes())
    parents = {r['name'][:-4]: r for r in parent['files']}
    old = json.loads((ROOT/'remaster-audit/hud-restoration/candidate-20261112-coherent-v4/manifest.json').read_bytes())
    sources = {r['key']: Path(r['source']) for r in old['files']}
    jobs = {}
    for key in sources:
        if key.startswith('BDAE4156-'):
            jobs[key] = [(str(number), [column*8, row*16+5, column*8+8, row*16+16])
                         for row, numbers in enumerate(('12345', '67890'))
                         for column, number in enumerate(numbers)]
            # Twelve optical initials agree with the source atlas and the
            # verified equipment catalog. Word-tail registration is explicit;
            # individual internal character addresses are not claimed.
            for row, initials in enumerate(('BCGH', 'FMPR', 'SVWJ')):
                jobs[key].extend((letter, [128+col*16,row*16,144+col*16,row*16+16])
                                 for col,letter in enumerate(initials))
            registration = Image.open(sources[key]).convert('RGBA')
            native_pixels = np.array(registration)
            for text, bounds in [
                ('LADE',[128,64,192,69]), ('LASH',[128,69,192,74]),
                ('OSQUITO',[128,74,192,79]), ('RENADE',[128,79,192,84]),
                ('YTHON',[128,84,192,89]), ('ANNON',[128,89,192,94]),
                ('ASP',[230,42,256,47]), ('IOT',[230,47,256,52]),
                ('PREADER',[192,52,230,57]), ('ULCAN',[230,52,256,57]),
                ('EDGEHOG',[192,57,230,62]), ('UNO',[230,57,256,62]),
            ]:
                x0,y0,x1,y1=bounds
                crop=native_pixels[y0:y1,x0:x1]
                yy,xx=np.where((crop[:,:,3]>0)&(crop[:,:,:3].max(2)>35))
                if not len(xx): raise ValueError('Missing source tail '+text)
                jobs[key].append((text,[x0+int(xx.min()),y0,x0+int(xx.max())+1,y1]))
        elif key.startswith('913FE978-'):
            jobs[key] = [('ANNON', [128, 1, 153, 6])]
    pack = out/'pack/einhander-texture-replacements'
    pack.mkdir(parents=True)
    (pack.parent/'Hashes.ini').write_text('')
    masks = {}
    rows = []
    preview = Image.new('RGB', (2500, len(jobs)*150), '#111827')
    draw = ImageDraw.Draw(preview)
    for n, (key, words) in enumerate(sorted(jobs.items())):
        source = sources[key]
        verify_stock(source.parent, key)
        native = Image.open(source).convert('RGBA')
        parent_path = Path(parents[key]['composed_path'])
        base = np.array(Image.open(parent_path).convert('RGBA'))
        authored = base.copy()
        selected = np.zeros(base.shape[:2], bool)
        registrations = []
        for text, rect in words:
            x0, y0, x1, y1 = rect
            pixels, inkbox = vector(text, native.crop(tuple(rect)))
            target = (slice(y0*SCALE, y1*SCALE), slice(x0*SCALE, x1*SCALE))
            authored[target] = pixels
            selected[target] = True
            registrations.append(dict(text=text, native_rect=rect, registration_inkbox=inkbox))
        if not np.array_equal(authored[~selected], base[~selected]):
            raise ValueError('Protected HUD artwork changed')
        path = pack/(key+'.png')
        Image.fromarray(authored).save(path)
        with Image.open(path) as decoded:
            if not np.array_equal(np.array(decoded.convert('RGBA')), authored):
                raise ValueError('PNG roundtrip changed')
        masks[key] = selected
        rows.append(dict(key=key, parent=ref(parent_path), source=ref(source),
            selected_native_regions=[r for _, r in words], registrations=registrations,
            outputs=dict(pack=dict(**ref(path), size=list(Image.open(path).size))),
            protected_outside_exact=True, alpha_classes=list(map(int, np.unique(authored[:, :, 3])))))
        draw.text((8, n*150+4), key+' | fresh score digits / source-proven C + ANNON', fill='white')
        x = 8
        for text, rect in words:
            x0,y0,x1,y1 = rect
            pixels=authored[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE]
            im=Image.fromarray(pixels[:, :, :3]).resize(((x1-x0)*4,(y1-y0)*4),Image.Resampling.LANCZOS).convert('RGBA')
            im.putalpha(Image.fromarray(np.where(pixels[:, :, 3]>0,255,0).astype(np.uint8)).resize(im.size,Image.Resampling.NEAREST))
            preview.paste(im,(x,n*150+35),im)
            x+=im.width+10
    preview.save(out/'counter-vectors-actual4x.png')
    np.savez_compressed(out/'changed-masks.npz',**masks)
    manifest=dict(at_utc=datetime.now(timezone.utc).isoformat(), method='Fresh Bahnschrift vectors; source pixels used only for registration/color/STP',
        font=ref(FONT), parent_candidate=ref(args.parent), files=rows, asset_count=len(rows),
        changed_masks=ref(out/'changed-masks.npz'), protected_outside_exact=True,
        live_verified=False, remaining=['All weapon tails and initials require actual per-equipment replay; small popup atlas and Hit Gauge lettering remain separately registered work'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(output=str(out), pngs=len(rows), checks='PASS', live_verified=False)))


if __name__ == '__main__':
    main()
