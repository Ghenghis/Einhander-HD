"""Rebuild the native prompt atlas with fresh vector lettering.

The lower BDAE page and DD0 upload are distinct originals. Only their text
fields are replaced; the small unclassified mark at x56..71,y240..255 is
protected. Original parents, game processes and installed assets are untouched.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_three_asset_proof import verify_stock
from build_coherent_font_candidate import module

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'remaster-audit'
DEFAULT_OUT = AUDIT / 'hud-restoration/prompt-vector-candidate-v2'
PARENT = AUDIT / 'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
SOURCE_MANIFEST = AUDIT / 'hud-restoration/candidate-20261112-coherent-v4/manifest.json'
FONT = Path('C:/Windows/Fonts/bahnschrift.ttf')
SCALE = 16
KEYS = ['BDAE4156-4C1DD349', 'BDAE4156-B88C038E',
        'BDAE4156-DDD3D3CF', 'BDAE4156-E21112A6', 'DD0B6963-4C1DD349']

# Native source registration. Half-open rectangles preserve the game's word
# sprite locations. Most are directly observed quads; remaining known words
# are optically registered inside their original isolated source bands.
COMMON = [
    ('CONTINUE?', (0,0,139,19)), ('PAUSE', (144,0,223,19)),
    ('FIGHTERS', (0,24,99,39)), ('START', (136,24,215,39)),
    ('NO', (216,24,241,39)), ('COUNT', (0,42,83,61)),
    ('DOWN', (87,42,155,61)), ('YES', (160,64,200,79)),
    ('TITLE', (0,80,62,95)), ('EXIT', (64,80,116,95)),
    ('PRESS START', (120,80,253,95)), ('CD', (0,96,27,111)),
    ('READ', (30,96,83,111)), ('RETRYING', (87,96,189,111)),
    ('WAIT', (0,112,52,127)), ('FIGHTER', (72,112,161,127)),
] + [(str(n),(n*16,64,n*16+15,79)) for n in range(10)]
EXTRA_BDAE = [('CONTINUE',(160,48,256,63)), ('LEFT',(200,64,248,79)),
              ('CRED',(192,96,240,111)), ('WAIT',(192,112,240,127))]
EXTRA_DD0 = [('REST',(160,48,212,63))]
CAPTURE_ROOT = AUDIT / 'dev-center-evidence'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def pixels(path):
    with Image.open(path) as im:
        im.load()
        return np.array(im.convert('RGBA'))


def registration(key):
    offset = 0 if key.startswith('DD0B') else 128
    words = COMMON + (EXTRA_DD0 if offset == 0 else EXTRA_BDAE)
    return [(text,(x0,y0+offset,x1,y1+offset)) for text,(x0,y0,x1,y1) in words]


def selected_regions(key):
    offset = 0 if key.startswith('DD0B') else 128
    # The preserved x56..71 bottom mark differs between original uploads.
    if offset:
        # The small source mark after NO is not part of its observed word quad.
        return [(0,128,256,160),(0,160,244,167),(248,160,256,167),
                (0,167,256,240),(0,240,56,256),(72,240,256,256)]
    return [(0,0,256,112), (0,112,56,128), (72,112,256,128)]


def region_mask(shape, regions):
    result = np.zeros(shape, bool)
    for x0,y0,x1,y1 in regions:
        result[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE] = True
    return result


def vector_mask(text, width, height):
    """Fresh outline coverage; original texture tones never supply strokes."""
    font = ImageFont.truetype(str(FONT), 512)
    box = font.getbbox(text)
    raw = Image.new('L',(box[2]-box[0]+12,box[3]-box[1]+12))
    ImageDraw.Draw(raw).text((6-box[0],6-box[1]),text,font=font,fill=255)
    raw = raw.crop(raw.getbbox())
    # Native quads include the original broad glow. Use a compact margin and
    # one common cap height for each sprite height, preserving its full width.
    margin_x = 10
    margin_y = 15
    target_h = height-2*margin_y
    target_w = width-2*margin_x
    if len(text)==1 and text.isdigit():
        target_w = min(target_w,round(target_h*.77))
    new = raw.resize((target_w,target_h),Image.Resampling.LANCZOS)
    canvas = Image.new('L',(width,height))
    canvas.paste(new,((width-target_w)//2,margin_y))
    return np.asarray(canvas)


def render_word(text, rect, palette):
    x0,y0,x1,y1=rect
    mask=vector_mask(text,(x1-x0)*SCALE,(y1-y0)*SCALE)
    result=np.zeros((*mask.shape,4),np.uint8)
    face=palette[0,:3].astype(float)
    visible=mask>=10
    core=mask>=224
    # RGB antialiasing is narrow and fresh. Alpha remains categorical PSX
    # cutout/STP, never an ordinary opacity channel.
    result[:,:,:3]=np.rint(face[None,None,:]*mask[:,:,None]/255).astype(np.uint8)
    result[:,:,3][visible]=127
    if 255 in palette[:,3]:
        result[:,:,3][visible & ~core]=255
    result[~visible]=0
    return result


def visual_rgb(array, background=(12,23,39)):
    rgb=array[:,:,:3].copy()
    rgb[array[:,:,3]==0]=background
    return Image.fromarray(rgb)


def collect_receipts():
    found=[]
    for candidate in ['hud-world-region-candidate-20261112-v9',
                      'hud-4k-candidate-20261112-v6',
                      'hud-4k-candidate-20261112-v3']:
        for path in sorted((CAPTURE_ROOT/candidate).glob('*/capture.jsonl')):
            for n,line in enumerate(path.open(encoding='utf-8'),1):
                try:r=json.loads(line)
                except json.JSONDecodeError:continue
                if r.get('key') not in KEYS or len(r.get('uv_bounds',[]))!=4:
                    continue
                if r['key'].startswith('BDAE') and r['uv_bounds'][1]<128:
                    continue
                identity=(r['key'],tuple(r['uv_bounds']))
                if any((f['key'],tuple(f['uv_bounds']))==identity for f in found):
                    continue
                found.append(dict(key=r['key'],uv_bounds=r['uv_bounds'],
                    capture=str(path),capture_line=n,frame=r.get('frame'),
                    event=r.get('event'),source_local_uv_not_implied_by_page_uv=True))
    return found


def verify(out, negative=False):
    m=json.loads((out/'manifest.json').read_bytes())
    for item in [m['parent_candidate'],m['source_manifest'],m['font'],m['builder']]:
        assert sha(item['path'])==item['sha256'],item['path']
    hud=module(AUDIT/'hud-restoration/candidate-20261112-coherent-v4/build-source.py','prompt_verify_hud')
    checked=[]
    for row in m['files']:
        key=row['key'];actual=pixels(row['path']);parent=pixels(row['baseline']['path'])
        assert sha(row['path'])==row['sha256']
        assert sha(row['baseline']['path'])==row['baseline']['sha256']
        for source in row['source_archives']:assert sha(source['path'])==source['sha256']
        md,words,clut=verify_stock(out/'sources',key)
        palette=hud.palette_rgba(clut)
        selected=region_mask(actual.shape[:2],row['selected_native_regions'])
        assert actual.shape==parent.shape and np.array_equal(actual[~selected],parent[~selected])
        expected=parent.copy();expected[selected]=0
        for text,rect in registration(key):
            x0,y0,x1,y1=rect
            expected[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE]=render_word(text,rect,palette)
        assert np.array_equal(actual,expected),key+' vector recipe mismatch'
        assert set(np.unique(actual[:,:,3]))<={0,127,255}
        assert row['changed_pixels']==int(np.any(actual!=parent,axis=2).sum())
        assert np.array_equal(actual[:128*SCALE],parent[:128*SCALE]) if key.startswith('BDAE') else True
        for text,rect in registration(key):
            mask=vector_mask(text,(rect[2]-rect[0])*SCALE,(rect[3]-rect[1])*SCALE)
            assert mask[0].max()==mask[-1].max()==mask[:,0].max()==mask[:,-1].max()==0
        if negative:
            bad=actual.copy();where=np.argwhere(~selected)[0];bad[tuple(where)]=[1,2,3,255]
            assert not np.array_equal(bad[~selected],parent[~selected])
            bad=actual.copy();where=np.argwhere(selected)[0];bad[tuple(where)]=[1,2,3,255]
            assert not np.array_equal(bad,expected)
        checked.append(dict(key=key,sha256=row['sha256'],outside_exact=True,
            all_fresh_vector_pixels_reproduced=True,word_contours_fit=True))
    result=dict(outcome='PASS',checked=checked,negative_controls=(
        ['protected pixel corruption detected','authored word corruption detected'] if negative else []),
        live_acceptance='NOT RUN',at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True)
    return result


def build(out):
    if (out/'manifest.json').exists():raise ValueError('Immutable output already exists')
    out.mkdir(parents=True,exist_ok=True)
    pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True,exist_ok=True)
    (out/'pack/Hashes.ini').write_text('')
    (out/'sources').mkdir(exist_ok=True)
    source_manifest=json.loads(SOURCE_MANIFEST.read_bytes())
    sources={r['key']:r for r in source_manifest['files']}
    parent=json.loads(PARENT.read_bytes());parents={r['name'][:-4]:r for r in parent['files']}
    hud=module(AUDIT/'hud-restoration/candidate-20261112-coherent-v4/build-source.py','prompt_build_hud')
    rows=[];previews={}
    for key in KEYS:
        source_path=Path(sources[key]['source'])
        md,words,clut=verify_stock(source_path.parent,key)
        assert sha(source_path)==sources[key]['source_sha256']
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            target=out/'sources'/(key+suffix);shutil.copyfile(source_path.with_suffix(suffix),target)
            source_refs.append(ref(target))
        baseline=Path(parents[key]['composed_path']);assert sha(baseline)==parents[key]['sha256']
        before=pixels(baseline);after=before.copy();regions=selected_regions(key)
        selected=region_mask(before.shape[:2],regions);after[selected]=0
        palette=hud.palette_rgba(clut)
        for text,rect in registration(key):
            x0,y0,x1,y1=rect
            after[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE]=render_word(text,rect,palette)
        assert np.array_equal(after[~selected],before[~selected])
        target=pack/(key+'.png');Image.fromarray(after).save(target)
        rows.append(dict(key=key,path=str(target.resolve()),sha256=sha(target),
            baseline=ref(baseline),source_archives=source_refs,
            source_crc_clut_verified=True,source_dimensions=[md['width_words']*4,md['height']],
            selected_native_regions=[list(r) for r in regions],
            word_registration=[dict(text=t,rect=list(r),contour_source='fresh Bahnschrift vector',
                optical_inside_source_quad=True) for t,r in registration(key)],
            changed_pixels=int(np.any(after!=before,axis=2).sum()),
            protected_outside_exact=True,live_verified=False))
        if key in ['BDAE4156-4C1DD349','BDAE4156-DDD3D3CF','DD0B6963-4C1DD349']:
            offset=0 if key.startswith('DD0B') else 128
            previews[key]=after[offset*SCALE:(offset+128)*SCALE]
    preview=Image.new('RGB',(1024,1650),(12,23,39));draw=ImageDraw.Draw(preview)
    y=0
    for key,pix in previews.items():
        draw.text((8,y+5),key+' | fresh vector prompts at actual4x; original sprite layout',fill='white')
        preview.paste(visual_rgb(pix).resize((1024,512),Image.Resampling.LANCZOS),(0,y+25));y+=550
    preview.save(out/'prompt-vector-actual4x.png')
    shutil.copyfile(__file__,out/'build-source.py')
    manifest=dict(schema_version=1,contract='fresh-prompt-vector-v1',
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),source_manifest=ref(SOURCE_MANIFEST),font=ref(FONT),
        builder=ref(out/'build-source.py'),asset_count=len(rows),files=rows,
        preview=ref(out/'prompt-vector-actual4x.png'),native_draw_receipts=collect_receipts(),
        method='Fresh Bahnschrift outlines replace prompt words/digits in the original atlas locations; source tone/alpha never supplies stroke contours. Compact face-color RGB AA and categorical PSX alpha; no native blur or halo.',
        protected=['BDAE full upper128native rows including description/Results glyphs',
                   'Unclassified small bottom markx56..71, not claimed as a letter',
                   'BDAE small source mark after NO atx244..247,y160..166'],
        qualifications=['BDAE lower page and DD0 are distinct originals, authored independently.',
            'Words read directly from verified originals; unobserved word-quads use optical source-band registration, disclosed per word.',
            'Frame identity/draw receipts establish ownership only; changed lettering requires actual live replay.'],
        live_verified=False)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=verify(out,True);(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=DEFAULT_OUT)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--negative-controls',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve(),args.negative_controls)
    else:build(args.output.resolve())
