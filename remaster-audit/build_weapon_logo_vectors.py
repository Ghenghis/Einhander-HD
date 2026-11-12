"""Fresh source-registered Gunpod wordmarks and exact eight-row aliases."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from build_three_asset_proof import verify_stock

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit';S=16
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
COUNTER=AUDIT/'hud-restoration/counter-vector-candidate-v2/manifest.json'
ALIASES=AUDIT/'hud-restoration/counter-row-alias-candidate-v2/manifest.json'
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
OUT=AUDIT/'hud-restoration/weapon-logo-vector-candidate-v1'
WORDS=['BLADE','CANNON','GRENADE','HEDGEHOG','JUNO','FLASH',
       'MOSQUITO','PYTHON','RIOT','SPREADER','VULCAN','WASP']
SPANS=[35,42,49,56,28,35,53,42,24,56,42,28]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def decode(raw,clut):
    words=np.frombuffer(raw,dtype='<u2').reshape(256,64);idx=np.empty((256,256),np.uint8)
    for c in range(4):idx[:,c::4]=(words>>(4*c))&15
    v=np.frombuffer(clut,dtype='<u2');pal=np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,
        np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)
    return idx,pal

def word_mask(text,span):
    font=ImageFont.truetype(str(FONT),256)
    temp=Image.new('L',(2048,400));ImageDraw.Draw(temp).text((16,16),text,font=font,fill=255)
    ink=temp.crop(temp.getbbox()).resize((span*S-8,107),Image.Resampling.LANCZOS)
    mask=Image.new('L',(64*S,8*S));mask.paste(ink,(4,10))
    return np.asarray(mask)

def fields(raw,clut):
    idx,pal=decode(raw,clut);result=np.zeros((96*S,256*S,4),np.uint8)
    for row,(text,span) in enumerate(zip(WORDS,SPANS)):
        crop=idx[row*8:(row+1)*8,64:128]
        yy,xx=np.where(crop!=0)
        assert [int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]==[0,0,span,8],text+' source registration changed'
        coverage=word_mask(text,span);patch=np.zeros((*coverage.shape,4),np.uint8)
        patch[:,:,:3]=np.rint(coverage[:,:,None].astype(float)*pal[0,:3]/255).astype(np.uint8)
        patch[:,:,3]=np.where(coverage>1,pal[0,3],0)
        result[row*8*S:(row+1)*8*S,64*S:128*S]=patch
    return result

def author(before,row,height,field):
    selected=np.zeros(before.shape[:2],bool);after=before.copy()
    low=max(0,row);high=min(96,row+height)
    if low<high:
        y0=(low-row)*S;y1=(high-row)*S
        after[y0:y1,64*S:128*S]=field[low*S:high*S,64*S:128*S]
        selected[y0:y1,64*S:128*S]=True
        rects=[[64,low-row,128,high-row]]
    else:rects=[]
    assert np.array_equal(after[~selected],before[~selected])
    return after,selected,rects

def visual(pix):
    rgb=pix[:,:,:3].copy();rgb[pix[:,:,3]==0]=(12,23,39);return Image.fromarray(rgb)

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes())
    for field in ['parent_candidate','counter_sources','alias_sources','font','builder']:
        assert sha(m[field]['path'])==m[field]['sha256']
    _,canonical,_=verify_stock(out/'sources','BDAE4156-B88C038E')
    cache={};checks=[]
    for r in m['files']:
        key=r['key'];md,raw,clut=verify_stock(out/'sources',key);row=r['canonical_native_row'];height=r['source_height']
        assert raw==canonical[row*128:(row+height)*128]
        for sr in r['source_archives']:assert sha(sr['path'])==sr['sha256']
        assert sha(r['parent']['path'])==r['parent']['sha256']
        assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
        suffix=key.split('-')[1]
        if suffix not in cache:cache[suffix]=fields(canonical,clut)
        before=pixels(r['parent']['path']);actual=pixels(r['outputs']['pack']['path'])
        expected,mask,rects=author(before,row,height,cache[suffix])
        assert np.array_equal(actual,expected) and np.array_equal(actual[~mask],before[~mask])
        assert rects==r['selected_native_regions']
        assert r['changed_pixels']==int(np.any(actual!=before,axis=2).sum())
        assert set(np.unique(actual[:,:,3]))<={0,127,255}
        checks.append(dict(key=key,source_crc_clut_verified=True,canonical_row_exact=True,
            exact_fresh_vector_recipe=True,protected_outside_exact=True))
    assert len(checks)==19
    # Fresh contours fit every original eight-row strip; original antialias
    # tones are registration references and never become stroke shapes.
    for text,span in zip(WORDS,SPANS):
        mask=word_mask(text,span)
        assert mask[0].max()==mask[-1].max()==mask[:,0].max()==mask[:,-1].max()==0
    result=dict(outcome='PASS',asset_count=len(checks),checks=checks,
        all12word_contours_fit=True,live_acceptance='NOT RUN',at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result

def build(out):
    if out.exists():raise ValueError('Immutable output exists')
    parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    source_manifest=json.loads(COUNTER.read_bytes());alias_manifest=json.loads(ALIASES.read_bytes())
    jobs=[]
    for r in source_manifest['files']:
        if r['key'].startswith('BDAE4156-'):jobs.append((r['key'],Path(r['source']['path']),0,256))
    for r in alias_manifest['files']:
        source=next(Path(s['path']) for s in r['source_archives'] if s['path'].endswith('.png'))
        jobs.append((r['key'],source,r['canonical_native_row'],8))
    assert len(jobs)==19 and len({j[0] for j in jobs})==19
    canonical_path=next(j[1] for j in jobs if j[0]=='BDAE4156-B88C038E')
    _,canonical,_=verify_stock(canonical_path.parent,'BDAE4156-B88C038E')
    (out/'sources').mkdir(parents=True);pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
    (out/'pack/Hashes.ini').write_text('');rows=[];masks={};cache={};before_b88=None;after_b88=None;native_b88=None
    for key,source,row,height in sorted(jobs):
        assert key in parents
        md,raw,clut=verify_stock(source.parent,key);assert raw==canonical[row*128:(row+height)*128]
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            dest=out/'sources'/(key+suffix);shutil.copyfile(source.with_suffix(suffix),dest);source_refs.append(ref(dest))
        suffix=key.split('-')[1]
        if suffix not in cache:cache[suffix]=fields(canonical,clut)
        baseline=Path(parents[key]['composed_path']);assert sha(baseline)==parents[key]['sha256']
        before=pixels(baseline);after,mask,rects=author(before,row,height,cache[suffix])
        target=pack/(key+'.png');Image.fromarray(after).save(target);masks[key]=mask
        rows.append(dict(key=key,parent=ref(baseline),source_archives=source_refs,
            canonical_native_row=row,source_height=height,selected_native_regions=rects,
            outputs=dict(pack=dict(**ref(target),size=[after.shape[1],after.shape[0]])),
            changed_pixels=int(np.any(after!=before,axis=2).sum()),source_crc_clut_verified=True,
            canonical_raw_row_exact=True,protected_outside_exact=True,live_verified=False))
        if key=='BDAE4156-B88C038E':before_b88=before;after_b88=after;native_b88=pixels(source)
    preview=Image.new('RGB',(1650,1240),(12,23,39));draw=ImageDraw.Draw(preview)
    for n,label in enumerate(['Verified native / nearest8x','Inherited candidate / actual8x','Fresh vector / actual8x']):
        draw.text((80+n*520,6),label,fill='white')
    for n,(text,span) in enumerate(zip(WORDS,SPANS)):
        y=30+n*95;draw.text((5,y+18),text,fill='white')
        for col,pix in enumerate([native_b88,before_b88,after_b88]):
            scale=1 if col==0 else S
            crop=pix[n*8*scale:(n+1)*8*scale,64*scale:128*scale]
            preview.paste(visual(crop).resize((512,64),Image.Resampling.NEAREST if col==0 else Image.Resampling.LANCZOS),(80+col*520,y))
        draw.text((80,y+68),'Source UV [64,'+str(n*8)+','+str(64+span)+','+str(n*8+8)+']; fresh fullword contour; entire64-wide padding cleaned',fill=(160,180,200))
    draw.text((8,1190),'Protected/unmapped: technical numeral strip atnativey104..111 and allnon-wordbank pixels. No new wording or game actions.',fill='white')
    preview.save(out/'weapon-wordmarks-source-before-after-actual8x.png')
    np.savez_compressed(out/'changed-masks.npz',**masks);shutil.copyfile(__file__,out/'build-source.py')
    m=dict(schema_version=1,contract='fresh-weapon-wordmarks-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),counter_sources=ref(COUNTER),alias_sources=ref(ALIASES),font=ref(FONT),builder=ref(out/'build-source.py'),
        asset_count=len(rows),files=rows,changed_masks=ref(out/'changed-masks.npz'),preview=ref(out/'weapon-wordmarks-source-before-after-actual8x.png'),
        words=[dict(text=text,source_native_cell=[64,n*8,128,n*8+8],source_word_span=span,
            identity_proof='Direct optical reading of verified native source; source endpoints measured against constant index0padding',
            contour_source='Fresh Bahnschrift vector') for n,(text,span) in enumerate(zip(WORDS,SPANS))],
        method='Twelve original Gunpod wordmarks rebuilt from fresh industrial sans outlines. Shared palette0faces and narrow RGB AA, categorical alpha. Original word registration/spans and source palette identities retained. Whole words generated before row clipping, so exactrawaliases share every selectedpixel.',
        explicit_unmapped=[dict(component='Technical numeral/symbol strip',native_region=[64,104,128,112],status='Protected unchanged; no semantic ownership or redraw claimed')],
        excluded=alias_manifest['excluded'],protected_outside_exact=True,live_verified=False,
        remaining=['Actual wordmark placements/weapon/slot/palette replay','No full-game inventory or typography coverage inference'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');result=verify(out)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
