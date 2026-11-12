"""Fresh small Gunpod initials/ammunition digits with exact row aliases."""
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

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
HUD=AUDIT/'hud-restoration/candidate-20261112-coherent-v4/manifest.json'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
OUT=AUDIT/'hud-restoration/small-hud-vector-candidate-v3'
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
S=16
GLYPHS=[(letter,[192+12*c,11*r,204+12*c,11*r+11])
        for r,line in enumerate(['BCGH','FMPR','SVWJ']) for c,letter in enumerate(line)]
GLYPHS += [(letter,[192+6*c,34+9*r,198+6*c,43+9*r])
           for r,line in enumerate(['01234','56789']) for c,letter in enumerate(line)]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def read_pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()


def indices(raw):
    words=np.frombuffer(raw,dtype='<u2').reshape(256,64)
    result=np.empty((256,256),np.uint8)
    for c in range(4):result[:,c::4]=(words>>(c*4))&15
    return result


def palette(clut):
    v=np.frombuffer(clut,dtype='<u2')
    return np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,
        np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)


def coverage(character,rect,idx):
    x0,y0,x1,y1=rect;crop=idx[y0:y1,x0:x1]
    yy,xx=np.where(crop!=15)
    assert len(xx),'Empty original glyph '+character
    bbox=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
    font=ImageFont.truetype(str(FONT),256)
    tmp=Image.new('L',(600,500));ImageDraw.Draw(tmp).text((16,16),character,font=font,fill=255)
    ink=tmp.crop(tmp.getbbox())
    w=(bbox[2]-bbox[0])*S-6;h=(bbox[3]-bbox[1])*S-5
    ink=ink.resize((w,h),Image.Resampling.LANCZOS)
    mask=Image.new('L',((x1-x0)*S,(y1-y0)*S));mask.paste(ink,(bbox[0]*S+3,bbox[1]*S+2))
    return np.asarray(mask),bbox


def render(character,rect,idx,pal):
    mask,bbox=coverage(character,rect,idx)
    # Initials use the shared native flat-face index1. Every tiny ammo digit
    # uses the shared palette0face, rather than inheriting differing maxima
    # from the low-resolution antialias tones of each individual digit.
    face=pal[1 if rect[1]<34 else 0]
    result=np.zeros((*mask.shape,4),np.uint8)
    result[:,:,:3]=np.rint(mask[:,:,None].astype(float)*face[:3]/255).astype(np.uint8)
    result[:,:,3]=np.where(mask>1,int(face[3]),0)
    return result,bbox


def intersections(row,height):
    out=[]
    for text,(x0,y0,x1,y1) in GLYPHS:
        low=max(y0,row);high=min(y1,row+height)
        if low<high:out.append((text,(x0,low-row,x1,high-row),(x0,y0,x1,y1)))
    return out


def author(base,row,height,idx,pal):
    result=base.copy();selected=np.zeros(base.shape[:2],bool);registrations=[]
    for text,local,original in intersections(row,height):
        x0,y0,x1,y1=local;full,bbox=render(text,original,idx,pal)
        sy=(row+y0-original[1])*S
        result[y0*S:y1*S,x0*S:x1*S]=full[sy:sy+(y1-y0)*S]
        selected[y0*S:y1*S,x0*S:x1*S]=True
        registrations.append(dict(text=text,native_rect=list(local),
            canonical_rect=list(original),source_registration_bbox=bbox,
            contour_source='fresh Bahnschrift vector; source coverage supplies registration only'))
    assert np.array_equal(result[~selected],base[~selected])
    return result,selected,registrations


def verify(out):
    m=json.loads((out/'manifest.json').read_bytes())
    for field in ['parent_candidate','font','canonical_source','builder']:
        assert sha(m[field]['path'])==m[field]['sha256']
    _,raw,_=verify_stock(out/'sources','BDAE4156-B88C038E');idx=indices(raw)
    checked=[]
    for r in m['files']:
        key=r['key'];md,words,clut=verify_stock(out/'sources',key)
        for sr in r['source_archives']:assert sha(sr['path'])==sr['sha256']
        assert sha(r['parent']['path'])==r['parent']['sha256']
        assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
        row=r['canonical_native_row'];height=r['source_height']
        assert words==raw[row*128:(row+height)*128]
        baseline=read_pixels(r['parent']['path']);actual=read_pixels(r['outputs']['pack']['path'])
        expected,mask,registration=author(baseline,row,height,idx,palette(clut))
        assert np.array_equal(actual,expected)
        assert np.array_equal(actual[~mask],baseline[~mask])
        assert set(np.unique(actual[:,:,3]))<={0,127,255}
        assert r['selected_native_regions']==[v['native_rect'] for v in registration]
        assert r['changed_pixels']==int(np.any(actual!=baseline,axis=2).sum())
        if not key.startswith('BDAE'):
            assert height==8 and r['raw_alias_exact']
        checked.append(dict(key=key,raw_crc_clut_verified=True,
            exact_canonical_slice=True,fresh_vector_recipe_exact=True,protected_outside_exact=True))
    result=dict(outcome='PASS',asset_count=len(checked),checks=checked,
        source_stroke_threshold=False,live_acceptance='NOT RUN',at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result


def build(out):
    if out.exists():raise ValueError('Immutable output exists')
    parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    src={r['key']:Path(r['source']) for r in json.loads(HUD.read_bytes())['files']}
    _,raw,_=verify_stock(src['BDAE4156-B88C038E'].parent,'BDAE4156-B88C038E')
    idx=indices(raw);jobs=[]
    for key,path in src.items():
        if key.startswith('BDAE4156-'):jobs.append((key,path,0,256))
    windows={}
    for row in range(52):
        if intersections(row,8):windows.setdefault(raw[row*128:(row+8)*128],[]).append(row)
    excluded=[]
    for a in json.loads(QUEUE.read_bytes())['assets']:
        md=a.get('source_metadata',{})
        if not a.get('source_verified') or (md.get('width_words'),md.get('height'),md.get('depth'))!=(64,8,0):continue
        path=Path(a['source']);words=path.with_suffix('.words.bin').read_bytes()
        if words not in windows:continue
        assert len(windows[words])==1,'Ambiguous exact raw alias '+a['key']
        if a['key'] not in parents:
            excluded.append(dict(key=a['key'],reason='Absent parent composition'));continue
        jobs.append((a['key'],path,windows[words][0],8))
    (out/'sources').mkdir(parents=True)
    pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
    (out/'pack/Hashes.ini').write_text('')
    rows=[];masks={};preview=Image.new('RGB',(1250,4*210),(12,23,39));d=ImageDraw.Draw(preview)
    for key,source,row,height in sorted(jobs):
        md,words,clut=verify_stock(source.parent,key)
        assert words==raw[row*128:(row+height)*128]
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            dest=out/'sources'/(key+suffix);shutil.copyfile(source.with_suffix(suffix),dest);source_refs.append(ref(dest))
        parent=Path(parents[key]['composed_path']);assert sha(parent)==parents[key]['sha256']
        before=read_pixels(parent);after,mask,registration=author(before,row,height,idx,palette(clut))
        target=pack/(key+'.png');Image.fromarray(after).save(target);masks[key]=mask
        rows.append(dict(key=key,parent=ref(parent),source_archives=source_refs,
            canonical_native_row=row,source_height=height,raw_alias_exact=height==8,
            raw_words_sha256=hashlib.sha256(words).hexdigest(),source_crc_clut_verified=True,
            selected_native_regions=[v['native_rect'] for v in registration],registrations=registration,
            changed_pixels=int(np.any(after!=before,axis=2).sum()),outputs=dict(pack=dict(**ref(target),size=[after.shape[1],after.shape[0]])),
            protected_outside_exact=True,live_verified=False))
        if key.startswith('BDAE'):
            n=['BDAE4156-4C1DD349','BDAE4156-B88C038E','BDAE4156-DDD3D3CF','BDAE4156-E21112A6'].index(key)
            d.text((8,n*210+4),key+' | small Gunpod initials + ammunition digits, actual8x',fill='white')
            x=8
            for text,rect in GLYPHS:
                x0,y0,x1,y1=rect
                pix=after[y0*S:y1*S,x0*S:x1*S];rgb=pix[:,:,:3].copy();rgb[pix[:,:,3]==0]=(12,23,39)
                im=Image.fromarray(rgb).resize(((x1-x0)*8,(y1-y0)*8),Image.Resampling.LANCZOS)
                if text=='0':x=8
                preview.paste(im,(x,n*210+(28 if y0<34 else 126)));x+=im.width+3
    preview.save(out/'small-hud-vectors-actual8x.png')
    np.savez_compressed(out/'changed-masks.npz',**masks)
    shutil.copyfile(__file__,out/'build-source.py')
    m=dict(schema_version=1,contract='small-hud-fresh-vector-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),font=ref(FONT),canonical_source=ref(out/'sources/BDAE4156-B88C038E.png'),
        builder=ref(out/'build-source.py'),asset_count=len(rows),files=rows,
        changed_masks=ref(out/'changed-masks.npz'),preview=ref(out/'small-hud-vectors-actual8x.png'),
        glyph_identity='Direct original-source optical reading: BCGH/FMPR/SVWJ and01234/56789',
        source_use='Exact raw source supplies cell registration, palette and STP; fresh font supplies every contour',
        face_policy='Shared palette1for12initials; shared palette0for10tinyammo digits, avoiding inherited per-digit shade islands',
        source_alias_rule='Byte equality of complete256x8raw rows, then alias-specific verifiedCLUT; canonical full glyph masks cropped, never rerendered in isolated slices',
        excluded=excluded,live_verified=False,remaining=['Per-equipment and ammo-state live replay','Alias paths beyond source-verified queue are not claimed'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=verify(out);(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
