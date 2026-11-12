"""Propagate root counter-vector-v2 fields through exact native row aliases."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw
from build_three_asset_proof import verify_stock

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
COUNTER=AUDIT/'hud-restoration/counter-vector-candidate-v2/manifest.json'
COUNTER_CODE=AUDIT/'build_hud_counter_vectors.py'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
OUT=AUDIT/'hud-restoration/counter-row-alias-candidate-v2'
S=16
EXPECTED={'E4774D79-E0C06BFB':8,'E1F18F98-B88C038E':32,
 '786B98BF-B88C038E':40,'786B98BF-E21112A6':40,
 '2C781811-B88C038E':48,'2C781811-E21112A6':48,
 '921FC559-B88C038E':56,'D050AD1B-B88C038E':64,
 '5C02D3C1-B88C038E':72,'5C02D3C1-E0C06BFB':72,
 '913A6603-B88C038E':80,'913A6603-E0C06BFB':80,
 '913FE978-B88C038E':88,'913FE978-E0C06BFB':88,'913FE978-E21112A6':88}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def module(p):
    spec=importlib.util.spec_from_file_location('counter_alias_root_snapshot',p)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
def rgba(raw,clut):
    words=np.frombuffer(raw,dtype='<u2').reshape(256,64);idx=np.empty((256,256),np.uint8)
    for c in range(4):idx[:,c::4]=(words>>(c*4))&15
    v=np.frombuffer(clut,dtype='<u2');pal=np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,
        np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)
    return Image.fromarray(pal[idx])

def canonical(counter,palette_suffix,clut,raw,library):
    matching=next((r for r in counter['files'] if r['key']=='BDAE4156-'+palette_suffix),None)
    reference=matching or next(r for r in counter['files'] if r['key']=='BDAE4156-B88C038E')
    native=rgba(raw,clut);rendered=np.zeros((4096,4096,4),np.uint8);selected=np.zeros((4096,4096),bool)
    for reg in reference['registrations']:
        text=reg['text'];x0,y0,x1,y1=reg['native_rect']
        result,_=library.vector(text,native.crop((x0,y0,x1,y1)))
        rendered[y0*S:y1*S,x0*S:x1*S]=result;selected[y0*S:y1*S,x0*S:x1*S]=True
    if matching:
        assert sha(matching['outputs']['pack']['path'])==matching['outputs']['pack']['sha256']
        actual=pixels(matching['outputs']['pack']['path'])
        assert np.array_equal(actual[selected],rendered[selected]),'Root vector reproduction mismatch '+palette_suffix
        rendered=actual
    return rendered,selected,reference

def rectangles(reference,row):
    result=[]
    for reg in reference['registrations']:
        x0,y0,x1,y1=reg['native_rect'];low=max(y0,row);high=min(y1,row+8)
        if low<high:result.append([x0,low-row,x1,high-row])
    return result

def mask_rectangles(rects):
    mask=np.zeros((128,4096),bool)
    for x0,y0,x1,y1 in rects:mask[y0*S:y1*S,x0*S:x1*S]=True
    return mask

def visual(pix):
    rgb=pix[:,:,:3].copy();rgb[pix[:,:,3]==0]=(12,23,39);return Image.fromarray(rgb)

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes());counter=json.loads(Path(m['counter_parent']['path']).read_bytes())
    for field in ['parent_candidate','counter_parent','counter_vector_recipe','builder']:
        assert sha(m[field]['path'])==m[field]['sha256']
    library=module(m['counter_vector_recipe']['path'])
    _,raw,_=verify_stock(out/'sources','BDAE4156-B88C038E')
    cache={};checks=[];root_alias={r['key']:r for r in counter['files'] if r['key'].startswith('913FE978')}
    for r in m['files']:
        key=r['key'];suffix=key.split('-')[1];md,words,clut=verify_stock(out/'sources',key)
        assert words==raw[r['canonical_native_row']*128:(r['canonical_native_row']+8)*128]
        assert sha(r['parent']['path'])==r['parent']['sha256']
        assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
        for source in r['source_archives']:assert sha(source['path'])==source['sha256']
        if suffix not in cache:cache[suffix]=canonical(counter,suffix,clut,raw,library)
        field,mask,reference=cache[suffix];row=r['canonical_native_row'];rects=rectangles(reference,row)
        selected=mask_rectangles(rects);assert np.array_equal(selected,mask[row*S:(row+8)*S])
        before=pixels(r['parent']['path']);actual=pixels(r['outputs']['pack']['path']);expected=before.copy()
        expected[selected]=field[row*S:(row+8)*S][selected]
        assert np.array_equal(actual,expected) and np.array_equal(actual[~selected],before[~selected])
        assert r['selected_native_regions']==rects and r['changed_pixels']==int(np.any(actual!=before,axis=2).sum())
        if key in root_alias:
            other=pixels(root_alias[key]['outputs']['pack']['path']);othermask=mask_rectangles(root_alias[key]['selected_native_regions']);overlap=selected&othermask
            assert np.array_equal(actual[overlap],other[overlap]),'Root Cannon overlap differs '+key
        checks.append(dict(key=key,row=row,raw_crc_clut_exact=True,canonical_selected_rgba_exact=True,
            protected_outside_exact=True,root_cannon_overlap_exact=(key in root_alias)))
    assert {r['key']:r['canonical_native_row'] for r in m['files']}==EXPECTED
    result=dict(outcome='PASS',asset_count=len(checks),checks=checks,live_acceptance='NOT RUN',
        at_utc=datetime.now(timezone.utc).isoformat());print(json.dumps(result),flush=True);return result

def build(out):
    if out.exists():raise ValueError('Immutable candidate already exists')
    counter=json.loads(COUNTER.read_bytes());parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    source_page=next(r for r in counter['files'] if r['key']=='BDAE4156-B88C038E')['source']['path']
    _,raw,_=verify_stock(Path(source_page).parent,'BDAE4156-B88C038E')
    queue=json.loads(QUEUE.read_bytes())['assets'];sources={a['key']:Path(a['source']) for a in queue if a.get('source_verified')}
    for r in counter['files']:sources.setdefault(r['key'],Path(r['source']['path']))
    font=json.loads((AUDIT/'menu-restoration/font-strip-candidate-v6/manifest.json').read_bytes())
    for r in font['files']:sources.setdefault(r['key'],Path(r['source']))
    (out/'sources').mkdir(parents=True);pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
    (out/'pack/Hashes.ini').write_text('');shutil.copyfile(COUNTER_CODE,out/'root-counter-source.py')
    library=module(out/'root-counter-source.py')
    for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
        shutil.copyfile(Path(source_page).with_suffix(suffix),out/'sources'/('BDAE4156-B88C038E'+suffix))
    rows=[];masks={};cache={};preview=Image.new('RGB',(2200,1550),(12,23,39));draw=ImageDraw.Draw(preview)
    for n,(key,row) in enumerate(sorted(EXPECTED.items(),key=lambda v:(v[1],v[0]))):
        assert key in parents,'Alias absent parent composition '+key
        source=sources[key];md,words,clut=verify_stock(source.parent,key)
        assert md['width_words']==64 and md['height']==8 and words==raw[row*128:(row+8)*128]
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            dest=out/'sources'/(key+suffix);shutil.copyfile(source.with_suffix(suffix),dest);source_refs.append(ref(dest))
        suffix=key.split('-')[1]
        if suffix not in cache:cache[suffix]=canonical(counter,suffix,clut,raw,library)
        field,mask,reference=cache[suffix];rects=rectangles(reference,row);selected=mask_rectangles(rects)
        assert np.array_equal(selected,mask[row*S:(row+8)*S])
        baseline=Path(parents[key]['composed_path']);assert sha(baseline)==parents[key]['sha256']
        before=pixels(baseline);after=before.copy();after[selected]=field[row*S:(row+8)*S][selected]
        assert np.array_equal(after[~selected],before[~selected])
        target=pack/(key+'.png');Image.fromarray(after).save(target);masks[key]=selected
        rows.append(dict(key=key,parent=ref(baseline),source_archives=source_refs,canonical_native_row=row,
            selected_native_regions=rects,outputs=dict(pack=dict(**ref(target),size=[4096,128])),
            changed_pixels=int(np.any(after!=before,axis=2).sum()),raw_row_alias_exact=True,
            own_clut_crc_verified=True,canonical_match_kind='exact existing root selected crop' if suffix!='E0C06BFB' else 'same root vector recipe with actual alias CLUT',
            protected_outside_exact=True,live_verified=False))
        x=(n%2)*1100;y=880+(n//2)*80
        draw.text((x+8,y+2),key+' | canonical row'+str(row)+' / actual4x complete256x8strip',fill='white')
        preview.paste(visual(after).resize((1024,32),Image.Resampling.LANCZOS),(x+8,y+24))
    for n,suffix in enumerate(['B88C038E','E0C06BFB']):
        field,mask,_=cache[suffix];x=n*1100
        shown=np.zeros((1536,4096,4),np.uint8);selected=mask[:1536];shown[selected]=field[:1536][selected]
        draw.text((x+8,4),'Root counter vector context /'+suffix+' / actual4x selected fields only',fill='white')
        preview.paste(visual(shown).resize((1024,384),Image.Resampling.LANCZOS),(x+8,30))
        # A second 8x crop makes every small weapon tail legible in the preview.
        detail=shown[42*S:96*S,128*S:256*S]
        preview.paste(visual(detail).resize((1024,432),Image.Resampling.LANCZOS),(x+8,410))
    preview.save(out/'counter-alias-context-actual4x-and8x.png')
    np.savez_compressed(out/'changed-masks.npz',**masks);shutil.copyfile(__file__,out/'build-source.py')
    m=dict(schema_version=1,contract='root-counter-raw-row-alias-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),counter_parent=ref(COUNTER),counter_vector_recipe=ref(out/'root-counter-source.py'),
        builder=ref(out/'build-source.py'),asset_count=len(rows),files=rows,changed_masks=ref(out/'changed-masks.npz'),
        preview=ref(out/'counter-alias-context-actual4x-and8x.png'),
        method='Full raw256x8row equality establishes alias; own source CLUT is CRC-verified. Existing BDAE palette canonical selected output pixels are copied exactly. E0 uses the identical root vector function on canonical raw indices with actual alias CLUT. Whole glyphs are rendered before clipping the source-row window.',
        excluded=[dict(key='D050AD1B-E0C06BFB',canonical_native_row=64,reason='Source verified but absent parent composition; no new texture key added')],
        protected_outside_exact=True,live_verified=False,
        remaining=['Actual per-weapon and alias-path replay','Source-exact alias does not establish all-game inventory completion'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');result=verify(out)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
