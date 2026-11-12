"""Rebuild the visually identified auxiliary Latin book, protecting body UVs."""
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
OUT=AUDIT/'hud-restoration/auxiliary-glyphbook-vector-candidate-v1'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
SOURCES=AUDIT/'hud-restoration/counter-vector-candidate-v2/manifest.json'
FONTS=AUDIT/'menu-restoration/font-strip-candidate-v6/manifest.json'
BODY=AUDIT/'menu-restoration/description-vector-candidate-v4/manifest.json'
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
GLYPHS=[(c,[8+8*n,104,16+8*n,112]) for n,c in enumerate('0123456789ABCDE')]
GLYPHS += [(c,[8*n,112,8+8*n,120]) for n,c in enumerate('FGHIJKLMNOPQRSTU')]
GLYPHS += [(c,[x,120,x+8,128]) for c,x in [('V',0),('W',8),('X',16),('Y',24),('Z',32),
    ('/',40),('-',48),('.',64),(':',72),("'",80),('"',88),('?',96),('!',104),('(',112),(')',120)]]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def decode(raw,clut):
    words=np.frombuffer(raw,dtype='<u2').reshape(256,64);idx=np.empty((256,256),np.uint8)
    for c in range(4):idx[:,c::4]=(words>>(c*4))&15
    v=np.frombuffer(clut,dtype='<u2');pal=np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,
        np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)
    return idx,pal

def glyph_mask(text,rect,idx):
    x0,y0,x1,y1=rect;crop=idx[y0:y1,x0:x1];yy,xx=np.where(crop!=15)
    assert len(xx),text+' source empty'
    box=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
    font=ImageFont.truetype(str(FONT),256);temp=Image.new('L',(600,500))
    ImageDraw.Draw(temp).text((20,20),text,font=font,fill=255);ink=temp.crop(temp.getbbox())
    maxw=(box[2]-box[0])*S-8;maxh=(box[3]-box[1])*S-10
    ratio=min(maxw/ink.width,maxh/ink.height)
    width=max(1,round(ink.width*ratio));height=max(1,round(ink.height*ratio))
    ink=ink.resize((width,height),Image.Resampling.LANCZOS)
    left=box[0]*S+((box[2]-box[0])*S-width)//2
    top=box[1]*S+((box[3]-box[1])*S-height)//2
    mask=Image.new('L',(128,128));mask.paste(ink,(left,top))
    return np.asarray(mask),box

def author(before,row,height,raw,clut):
    idx,pal=decode(raw,clut);after=before.copy();mask=np.zeros(before.shape[:2],bool);registrations=[]
    for text,rect in GLYPHS:
        x0,y0,x1,y1=rect;low=max(y0,row);high=min(y1,row+height)
        if low>=high:continue
        coverage,box=glyph_mask(text,rect,idx);patch=np.zeros((128,128,4),np.uint8)
        patch[:,:,:3]=np.rint(coverage[:,:,None].astype(float)*pal[0,:3]/255).astype(np.uint8)
        patch[:,:,3]=np.where(coverage>1,pal[0,3],0)
        target=(slice((low-row)*S,(high-row)*S),slice(x0*S,x1*S));sy=(low-y0)*S
        after[target]=patch[sy:sy+(high-low)*S];mask[target]=True
        registrations.append(dict(character=text,canonical_rect=rect,
            native_rect=[x0,low-row,x1,high-row],source_registration_bbox=box,
            contour_source='Fresh Bahnschrift vectors, natural aspect preserved inside original source registration'))
    assert np.array_equal(after[~mask],before[~mask])
    return after,mask,registrations

def visual(a):
    rgb=a[:,:,:3].copy();rgb[a[:,:,3]==0]=(12,23,39);return Image.fromarray(rgb)

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes())
    for field in ['parent_candidate','source_counter_manifest','source_font_manifest','body_manifest','font','builder']:
        assert sha(m[field]['path'])==m[field]['sha256']
    _,raw,_=verify_stock(out/'sources','BDAE4156-B88C038E')
    body=json.loads(Path(m['body_manifest']['path']).read_bytes())['glyph_records']
    checks=[]
    for r in m['files']:
        key=r['key'];md,words,clut=verify_stock(out/'sources',key);row=r['canonical_native_row'];height=r['source_height']
        assert words==raw[row*128:(row+height)*128]
        assert sha(r['parent']['path'])==r['parent']['sha256']
        assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
        for source in r['source_archives']:assert sha(source['path'])==source['sha256']
        before=pixels(r['parent']['path']);actual=pixels(r['outputs']['pack']['path'])
        expected,mask,registrations=author(before,row,height,raw,clut)
        assert np.array_equal(actual,expected) and np.array_equal(actual[~mask],before[~mask])
        assert r['selected_native_regions']==[g['native_rect'] for g in registrations]
        assert r['changed_pixels']==int(np.any(actual!=before,axis=2).sum())
        if height==256:
            for g in body:
                x0,y0,x1,y1=g['uv'];assert not mask[y0*S:y1*S,x0*S:x1*S].any()
            assert not mask[120*S:128*S,56*S:64*S].any(),'Unknown overbar changed'
        checks.append(dict(key=key,source_crc_clut_verified=True,raw_canonical_exact=True,
            exact_fresh_vector_recipe=True,protected_outside_exact=True,body37_regions_untouched=True))
    idx,_=decode(raw,clut)
    for c,rect in GLYPHS:
        mask,_=glyph_mask(c,rect,idx)
        assert mask[0].max()==mask[-1].max()==mask[:,0].max()==mask[:,-1].max()==0
    assert len(GLYPHS)==46 and len(checks)==5
    result=dict(outcome='PASS',asset_count=5,glyph_count=46,checks=checks,
        draw_use='Not observed in the stored sampled capture logs or24fullGP0frames examined; no live use/placement acceptance inferred',
        live_acceptance='NOT RUN',at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result

def build(out):
    if out.exists():raise ValueError('Immutable output already exists')
    parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    sourcecounter=json.loads(SOURCES.read_bytes());fonts=json.loads(FONTS.read_bytes())
    jobs=[(r['key'],Path(r['source']['path']),0,256) for r in sourcecounter['files'] if r['key'].startswith('BDAE4156-')]
    alias=next(r for r in fonts['files'] if r['key']=='AAA5C104-B88C038E')
    jobs.append((alias['key'],Path(alias['source']),112,8))
    canonical_path=next(path for key,path,_,_ in jobs if key=='BDAE4156-B88C038E')
    _,raw,_=verify_stock(canonical_path.parent,'BDAE4156-B88C038E')
    (out/'sources').mkdir(parents=True);pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
    (out/'pack/Hashes.ini').write_text('');rows=[];masks={};example=None
    for key,source,row,height in sorted(jobs):
        md,words,clut=verify_stock(source.parent,key);assert words==raw[row*128:(row+height)*128]
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            target=out/'sources'/(key+suffix);shutil.copyfile(source.with_suffix(suffix),target);source_refs.append(ref(target))
        baseline=Path(parents[key]['composed_path']);assert sha(baseline)==parents[key]['sha256']
        before=pixels(baseline);after,mask,registrations=author(before,row,height,raw,clut)
        target=pack/(key+'.png');Image.fromarray(after).save(target);masks[key]=mask
        rows.append(dict(key=key,parent=ref(baseline),source_archives=source_refs,canonical_native_row=row,
            source_height=height,selected_native_regions=[g['native_rect'] for g in registrations],
            registrations=registrations,outputs=dict(pack=dict(**ref(target),size=[after.shape[1],after.shape[0]])),
            changed_pixels=int(np.any(after!=before,axis=2).sum()),protected_outside_exact=True,live_verified=False))
        if key=='BDAE4156-B88C038E':example=(pixels(source),before,after)
    preview=Image.new('RGB',(1550,1120),(12,23,39));draw=ImageDraw.Draw(preview)
    for view,label in enumerate(['Native source glyph identities /8x','Prior candidate /actual8x','Fresh vector glyphs /actual8x']):
        draw.text((8,view*360+4),label,fill='white')
        for n,(text,rect) in enumerate(GLYPHS):
            col=n%16;line=n//16;x=col*96;y=view*360+line*112+28
            scale=1 if view==0 else S;x0,y0,x1,y1=rect
            crop=example[view][y0*scale:y1*scale,x0*scale:x1*scale]
            preview.paste(visual(crop).resize((64,64),Image.Resampling.NEAREST if view==0 else Image.Resampling.LANCZOS),(x+8,y))
            draw.text((x+8,y+68),text+' @'+str(x0)+','+str(y0),fill=(180,200,220))
    draw.text((8,1090),'Uncertain source overbar[56,120,64,128] protected.46identities are source-optical; actual draw use unobserved.',fill='white')
    preview.save(out/'auxiliary-glyphbook-before-after-actual8x.png')
    np.savez_compressed(out/'changed-masks.npz',**masks);shutil.copyfile(__file__,out/'build-source.py')
    m=dict(schema_version=1,contract='auxiliary-latin-source-glyphs-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),source_counter_manifest=ref(SOURCES),source_font_manifest=ref(FONTS),
        body_manifest=ref(BODY),font=ref(FONT),builder=ref(out/'build-source.py'),asset_count=5,glyph_count=46,
        files=rows,changed_masks=ref(out/'changed-masks.npz'),preview=ref(out/'auxiliary-glyphbook-before-after-actual8x.png'),
        source_map=[dict(character=c,native_rect=rect,identity='Direct optical reading of verified original8x8cell') for c,rect in GLYPHS],
        protected=['All37v4description glyph rectangles','All other prior artwork/lettering',
                   'Uncertain overbar at[56,120,64,128]','Empty firstcell[0,104,8,112]'],
        method='Fresh Bahnschrift outlines with natural glyph aspect centered inside original nonclear registration bounds. Shared native palette0face and categorical alpha; original tones never supply contours. ExactAAA5row112alias receives canonical crops.',
        draw_use_evidence=dict(sampled_capture_receipts='No matchingBDAEsource draw atx<128,y104..127 in stored capture.jsonl files scanned',
            complete_gp0_frames_examined=24,complete_gp0_source_brackets=15,matching_draws=0,
            qualification='Sampled/logged coverage is limited; does not prove unused or establish name-entry ownership'),
        unresolved=[dict(component='Overbar glyph or UI mark',native_rect=[56,120,64,128],status='Protected unchanged; identity uncertain')],
        protected_outside_exact=True,live_verified=False)
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');result=verify(out)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
