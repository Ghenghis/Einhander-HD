"""Pin delivered T6/T7 artwork and verify full-page/strip native identities.

Writes a new private plan and proof directory, never edits artist folders or
installs assets. Predicted strips remain labelled unobserved. Transparent null
palettes stay native rather than being counted as new authored artwork.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zlib

from build_stage1_frozen_candidate import EVIDENCE,ROOT,sha,verified_native_source

def ref(path):return dict(path=str(path.resolve()),sha256=sha(path))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-plan',type=Path,required=True)
    p.add_argument('--output-plan',type=Path,required=True)
    p.add_argument('--proofs',type=Path,required=True)
    p.add_argument('--stock',type=Path,default=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements'))
    args=p.parse_args();proofs=args.proofs.resolve();output=args.output_plan.resolve()
    if proofs.parent!=EVIDENCE.resolve() or output.parent!=EVIDENCE.resolve() or proofs.exists() or output.exists():
        raise ValueError('Use fresh direct children of private completion evidence')
    plan=json.loads(args.parent_plan.read_bytes());proofs.mkdir();stock=args.stock.resolve()
    word_files={};palette_files={}
    for f in sorted(stock.glob('*.words.bin')):word_files.setdefault(f.name[:8],f)
    for f in sorted(stock.glob('*.clut.bin')):
        if f.stat().st_size==32:palette_files.setdefault(f.name[9:17],f)
    known={r['key'] for r in plan['entries']};new=[];skipped=[];inputs={};native_ledger=[]
    def load(folder):
        m=folder/'manifest.json';data=m.read_bytes();a=json.loads(data)
        if a.get('status')!='candidate':raise ValueError('Not a frozen candidate: '+str(m))
        inputs[str(m)]=hashlib.sha256(data).hexdigest();return m,a
    def words_for(raw):
        f=word_files.get(raw)
        if f is None:raise ValueError('Native source words missing for '+raw)
        b=f.read_bytes()
        if f'{zlib.crc32(b):08X}'!=raw:raise ValueError('Stock word CRC mismatch: '+str(f))
        return f,b
    def add(manifest,key,image,words,shape,word_origin,occurrence,declared_image_sha=None,borrowed_clut=None):
        if key.endswith('-190A55AD'):
            skipped.append(dict(key=key,reason='Transparent null palette; retain native fallback'));return
        if key in known:raise ValueError('Conflicting authored key '+key)
        image_ref=ref(image)
        if declared_image_sha and image_ref['sha256']!=declared_image_sha:raise ValueError('Frozen export differs from manifest: '+str(image))
        palette=stock/borrowed_clut if borrowed_clut else palette_files.get(key[9:])
        if palette is None or not palette.is_file():raise ValueError('Native CLUT missing for '+key)
        clut=palette.read_bytes()
        word_path=proofs/(key+'.words.bin');clut_path=proofs/(key+'.clut.bin')
        word_path.write_bytes(words);clut_path.write_bytes(clut)
        native=dict(source_words=ref(word_path),source_clut=ref(clut_path),source_shape_words=shape,depth=0)
        verified_native_source(native,key)
        origin=dict(words=word_origin,clut=ref(palette),occurrence=occurrence)
        row=dict(manifest=ref(manifest),key=key,image=image_ref,native_source=native,native_origin=origin)
        plan['entries'].append(row);known.add(key);new.append(key)
        native_ledger.append(dict(key=key,source=native,origin=origin))
    base=ROOT/'remaster-audit/comfy-authoring'
    hulls=base/'t6-player/frozen/t6-mk2-hulls-v1';manifest,a=load(hulls)
    for key,meta in a['keys'].items():
        original,words=words_for(key[:8]);source=stock/(key+'.words.bin')
        if not source.is_file() or sha(source)!=meta['stock_source_sha256']['.words.bin']:
            raise ValueError('Hull source differs from frozen source proof: '+key)
        add(manifest,key,hulls/'runtime/1024-calm'/(key+'.png'),words,[16,64],ref(original),'captured source upload')
    pods=base/'t6-player/frozen/t6-gunpods-v1';manifest,a=load(pods)
    for pod in a['files']:
        page_key=pod['page_key'];original,words=words_for(page_key[:8])
        if len(words)!=64*256*2:raise ValueError('Unexpected Gunpod page geometry')
        rows=[dict(key=page_key,rows=None,status='draw-referenced native page')]+pod['strips']
        for item in rows:
            key=item['key'];uvrows=item['rows']
            raw=words if uvrows is None else words[uvrows[0]*128:uvrows[1]*128]
            image=pods/'runtime/1024'/(key+'.png')
            declared=pod['files'][str(image.relative_to(pods))]
            add(manifest,key,image,raw,[64,256 if uvrows is None else uvrows[1]-uvrows[0]],
                dict(full_page=ref(original),rows=uvrows),item['status'],declared)
    enemies=base/'t7-enemies/frozen'
    for folder in ('greif-1263A036-v1','greif-38DC02FE-v1','uhu-46D3938E-v1','uhu-87C52FC0-v1','fighter-2294438F-v1'):
        d=enemies/folder;manifest,a=load(d)
        for raw,page in a['pages'].items():
            original,words=words_for(raw)
            if len(words)!=64*256*2:raise ValueError('Unexpected actor page geometry')
            for item in page['keys']['keys']:
                key=item['key'];row=item.get('row');is_strip=item['kind']=='strip'
                native=words[row*128:(row+8)*128] if is_strip else words
                source=page['source_keys'].get(key,{})
                if not is_strip and source.get('words_sha256') and source['words_sha256']!=sha(original):
                    raise ValueError('Actor page differs from frozen source proof')
                add(manifest,key,d/'runtime-1024'/(key+'.png'),native,[64,8 if is_strip else 256],
                    dict(full_page=ref(original),rows=[row,row+8] if is_strip else None),
                    'captured stock source' if (not is_strip or item.get('stock_dump')) else 'derived strip; occurrence not yet captured',
                    borrowed_clut=item.get('borrowed_clut'))
    for m,digest in inputs.items():
        if sha(m)!=digest:raise ValueError('Frozen manifest changed during planning: '+m)
    receipt=proofs/'native-source-verification.json'
    receipt.write_text(json.dumps(dict(native_pairs=len(new),entries=native_ledger,skipped=skipped,
        parent_plan=ref(args.parent_plan),frozen_manifests=inputs,production_installed=False),indent=2)+'\n')
    plan['actor_source_verification']=ref(receipt)
    plan.setdefault('limitations',[]).extend(['Actor exports use their recommended calmer1024 variants; hull UV seams and other documented defects remain.','Predicted strip identities have verified bytes but unobserved upload occurrences; no live acceptance is implied.','Fighter artwork preserves the original green/orange palette and replaces the old crimson strips.'])
    output.write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(dict(plan=str(output),added_entries=len(new),total_entries=len(plan['entries']),native_pairs_verified=len(new),null_palettes_left_native=len(skipped))))

if __name__=='__main__':main()
