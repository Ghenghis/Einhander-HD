"""Pin Wave2 revisions in a fresh private plan; never edit frozen inputs."""
import argparse
import json
import hashlib
import re
import zlib
from collections import Counter
from pathlib import Path
from PIL import Image
import numpy as np

from build_stage1_frozen_candidate import ROOT,EVIDENCE,pinned,sha,verified_native_source


def ref(path):return dict(path=str(path.resolve()),sha256=sha(path))


def polish(plan):
    base=ROOT/'remaster-audit/comfy-authoring/w2-polish/frozen'
    revisions={
        'night-cloud-sky-page640-v1':'night-cloud-sky-page640-v4',
        'night-cloud-sky-page640-v3':'night-cloud-sky-page640-v4',
        'atlas-95A3BCF8-t3-v1':'atlas-95A3BCF8-w2-v2',
        'fd18-sinbal-v2':'fd18-sinbal-v4',
        '73BF9877-BE204159-v2':'73BF9877-BE204159-v3',
    }
    updated=[]
    for row in plan['entries']:
        old=Path(row['manifest']['path']).parent.name
        if old not in revisions:continue
        folder=base/revisions[old];manifest=folder/'manifest.json';meta=json.loads(manifest.read_bytes())
        if meta.get('status')!='candidate':raise ValueError('Non-candidate polish revision')
        filename=Path(row['image']['path']).name
        if old.startswith('night-cloud'):image=folder/filename
        elif old.startswith('atlas-'):image=folder/'runtime'/filename
        elif old.startswith('fd18-'):
            if meta['uv_rect_half_open']!=row['exact']['uv']:raise ValueError('Sign binding changed')
            image=folder/'region'/filename
        else:
            if meta['page_uv_rect']!=row['exact']['uv']:raise ValueError('Facade binding changed')
            image=folder/(row['key']+'-w2-v3-2048.png')
        relative=image.relative_to(folder).as_posix();declared=meta['files'][relative]
        expected=declared if isinstance(declared,str) else declared['sha256']
        if sha(image)!=expected:raise ValueError('Frozen image differs from manifest: '+str(image))
        prior=dict(manifest=row['manifest'],image=row['image'])
        row.update(manifest=ref(manifest),image=ref(image))
        updated.append(dict(key=row['key'],previous=prior,revised_manifest=row['manifest'],image=row['image']))
    latest=Counter(Path(r['manifest']['path']).parent.name for r in plan['entries'] if Path(r['manifest']['path']).parent.name in revisions.values())
    if latest!={'night-cloud-sky-page640-v4':5,'atlas-95A3BCF8-w2-v2':84,'fd18-sinbal-v4':2,'73BF9877-BE204159-v3':1}:
        raise ValueError('Expected exactly92 entries in the current approved polish revisions')
    return updated


def hud(plan,proofs):
    if proofs.parent!=EVIDENCE.resolve() or proofs.exists():raise ValueError('Fresh private native-proof directory required')
    proofs.mkdir();base=ROOT/'remaster-audit/comfy-authoring/w2-hud'
    index=base/'FROZEN-INDEX.json';catalog=json.loads(index.read_bytes())
    roots=[Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements'),
        Path('C:/github/REMASTER_STAGING/stage1_remaster/cpu-authority-source/stock/einhander-texture-replacements'),
        EVIDENCE/'astraea-native-sources-v2/hd-on_rewind-off/source-pages',
        EVIDENCE/'mk3-native-sources-v1/hd-on_rewind-off/source-pages',
        ROOT/'remaster-audit/menu-restoration/banner-font-candidate-v2/sources']
    native_cache={};pending={};sources=[];frozen={};predicted=[]
    def full_source(raw,depth):
        if (raw,depth) in native_cache:return native_cache[(raw,depth)]
        for directory in roots:
            for path in sorted(directory.glob(raw+'-*.words.bin')):
                words=path.read_bytes()
                if f'{zlib.crc32(words):08X}'!=raw:continue
                valid=path.with_name(path.name.replace('.words.bin','.valid.bin'))
                if valid.exists() and (len(valid.read_bytes())!=len(words)//2 or set(valid.read_bytes())!={1}):continue
                metadata=path.with_name(path.name.replace('.words.bin','.source.json'))
                if metadata.exists():
                    m=json.loads(metadata.read_bytes());w,h=m['width_words'],m['height']
                    if m['depth']!=depth:continue
                else:
                    png=path.with_name(path.name.replace('.words.bin','.png'))
                    if not png.exists():continue
                    with Image.open(png) as im:
                        if im.width%(4>>depth):continue
                        w,h=im.width//(4>>depth),im.height
                if len(words)!=w*h*2:continue
                result=(path,words,w,h);native_cache[(raw,depth)]=result;return result
        raise ValueError('Complete native words/geometry unavailable for '+raw)
    def palette(key,record):
        if key.endswith('-00000000'):return b'',dict(kind='direct16, no CLUT')
        if record.get('clut'):
            path=pinned(record['clut']);data=path.read_bytes()
            if f'{zlib.crc32(data):08X}'!=key[9:]:raise ValueError('Declared CLUT CRC mismatch')
            return data,ref(path)
        for directory in roots:
            for path in sorted(directory.glob('*-'+key[9:]+'.clut.bin')):
                data=path.read_bytes()
                if f'{zlib.crc32(data):08X}'==key[9:]:return data,ref(path)
        raise ValueError('Missing proven CLUT for '+key)
    def expected_image_hash(folder,meta,image):
        found=set()
        def walk(value):
            if isinstance(value,dict):
                if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
                    path=Path(value['path']);path=path if path.is_absolute() else folder/path
                    if path.resolve()==image.resolve():found.add(value['sha256'])
                for key,item in value.items():
                    if key.endswith('.png'):
                        path=Path(key);path=path if path.is_absolute() else folder/path
                        if path.resolve()==image.resolve():
                            if isinstance(item,str) and re.fullmatch('[0-9a-f]{64}',item):found.add(item)
                            elif isinstance(item,dict) and item.get('sha256'):found.add(item['sha256'])
                    walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        walk(meta);inventory=folder/'FILES.sha256.json'
        if inventory.exists():walk(json.loads(inventory.read_bytes()));frozen[str(inventory)]=sha(inventory)
        if found!={sha(image)}:raise ValueError('Output is not unambiguously pinned by frozen hashes: '+str(image))
    def write_native(key,words,clut,w,h,depth):
        for suffix,data in [('words.bin',words),('clut.bin',clut)]:
            path=proofs/(key+'.'+suffix)
            if path.exists() and path.read_bytes()!=data:raise ValueError('Conflicting native proofs for '+key)
            if not path.exists():path.write_bytes(data)
        source=dict(source_words=ref(proofs/(key+'.words.bin')),source_clut=ref(proofs/(key+'.clut.bin')),source_shape_words=[w,h],depth=depth)
        verified_native_source(source,key);return source
    for entry in catalog['entries']:
        if entry['status'] not in ('candidate','candidate-predicted-keys'):continue
        folder=base/entry['folder'];manifest=folder/'manifest.json'
        if sha(manifest)!=entry['manifest_sha256']:raise ValueError('Frozen HUD manifest changed')
        meta=json.loads(manifest.read_bytes());frozen[str(manifest)]=sha(manifest)
        records={r['key']:r for r in meta.get('keys',[])}
        for key in entry['keys']:
            record=records.get(key,{})
            image=folder/'pack'/(key+'.png')
            if not image.is_file():image=folder/'runtime-2048'/(key+'.png')
            expected_image_hash(folder,meta,image)
            clut,clut_origin=palette(key,record);depth=2 if not clut else 0 if len(clut)==32 else 1 if len(clut)==512 else -1
            if depth<0:raise ValueError('Unsupported CLUT size')
            row_index=record.get('page_row');raw=key[:8]
            parent_raw='B77B98B9' if folder.name.startswith('font-strips-') else 'BDAE4156' if row_index is not None else raw
            original,words,w,h=full_source(parent_raw,depth)
            if row_index is not None:
                if not 0<=row_index<=h-8:raise ValueError('Strip rows outside native parent')
                words=words[row_index*w*2:(row_index+8)*w*2];h=8
            if record.get('words') and sha(pinned(record['words']))!=hashlib.sha256(words).hexdigest():
                raise ValueError('Frozen strip source differs from the verified page crop')
            source=write_native(key,words,clut,w,h,depth)
            is_predicted=entry['status']=='candidate-predicted-keys' or record.get('predicted',False)
            row=dict(manifest=ref(manifest),key=key,image=ref(image),native_source=source,
                native_origin=dict(full_upload=ref(original),page_row=row_index,clut=clut_origin,
                    predicted_occurrence=bool(is_predicted),live_accepted=False))
            if key in pending and not folder.name.startswith('results-footer-'):raise ValueError('Unexpected duplicate HUD delivery '+key)
            pending[key]=row
            if is_predicted:predicted.append(key)
    replaced=0
    for key,row in pending.items():
        matches=[i for i,r in enumerate(plan['entries']) if r['key']==key]
        if len(matches)>1 or any(plan['entries'][i].get('exact') for i in matches):raise ValueError('HUD would overwrite a shared exact-region entry')
        if matches:plan['entries'][matches[0]]=row;replaced+=1
        else:plan['entries'].append(row)
        sources.append(dict(key=key,native_source=row['native_source'],origin=row['native_origin']))
    for path,digest in frozen.items():
        if sha(path)!=digest:raise ValueError('Frozen HUD files changed during planning')
    receipt=proofs/'hud-native-verification.json';receipt.write_text(json.dumps(dict(entries=sources,frozen_inputs=frozen,index=ref(index),predicted_keys=sorted(set(predicted)),live_accepted=False),indent=2)+'\n')
    plan['wave2_hud_native_verification']=ref(receipt)
    return dict(unique_entries=len(pending),replaced=replaced,added=len(pending)-replaced,predicted_unobserved=len(set(predicted)))


def effects(plan,proofs):
    if proofs.parent!=EVIDENCE.resolve() or proofs.exists():raise ValueError('Fresh private FX-proof directory required')
    proofs.mkdir();base=ROOT/'remaster-audit/comfy-authoring/w2-effects'
    catalog=json.loads((base/'INDEX.json').read_bytes());selected={};omitted=[];pending=[];receipts=[]
    for row in catalog['candidates']:
        if row['status']!='candidate':continue
        if not row['keys_delivered']:
            omitted.append(dict(name=row['name'],reason='No proven runtime CLUT/export; master-only delivery'));continue
        raw=row['texture_crc'];version=int(row['name'].rsplit('-v',1)[1])
        if raw not in selected or version>selected[raw][0]:selected[raw]=(version,row)
    for _,entry in selected.values():
        folder=base/entry['path'];manifest=folder/'manifest.json';metadata=json.loads(manifest.read_bytes())
        if metadata['status']!='candidate' or metadata.get('all_gates_pass') is False:raise ValueError('Unqualified frozen FX export')
        manifest_ref=ref(manifest);nw,nh=metadata['upload']['native_texels']
        for item in metadata['keys']:
            key=item['key'];image=pinned(dict(path=str(folder/item['png_1024']['path']),sha256=item['png_1024']['sha256']))
            word_path=folder/'source'/(key+'.words.bin')
            if not word_path.exists():word_path=next((folder/'source').glob(key[:8]+'-*.words.bin'))
            clut_path=folder/'source'/(key+'.clut.bin')
            for path in (word_path,clut_path):
                if sha(path)!=metadata['source_hashes'][path.name]:raise ValueError('Frozen FX source differs from manifest')
            words=word_path.read_bytes();clut=clut_path.read_bytes();depth=0 if len(clut)==32 else 1 if len(clut)==512 else -1
            if depth<0 or nw%(4>>depth):raise ValueError('Unexpected FX native geometry/depth')
            w=nw//(4>>depth);valid=word_path.with_name(word_path.name.replace('.words.bin','.valid.bin'))
            if valid.exists() and (len(valid.read_bytes())!=w*nh or set(valid.read_bytes())!={1}):raise ValueError('Incomplete FX source')
            wp=proofs/(key+'.words.bin');cp=proofs/(key+'.clut.bin');wp.write_bytes(words);cp.write_bytes(clut)
            native=dict(source_words=ref(wp),source_clut=ref(cp),source_shape_words=[w,nh],depth=depth)
            verified_native_source(native,key)
            raw=np.frombuffer(words,dtype='<u2')
            shifts=np.arange(4 if depth==0 else 2,dtype=np.uint16)*(4 if depth==0 else 8)
            indices=((raw[:,None]>>shifts)&(15 if depth==0 else 255)).reshape(nh,nw)
            pixels=np.frombuffer(clut,dtype='<u2')[indices]
            expected=np.where(pixels==0,0,np.where((pixels&0x8000)!=0,255,127)).astype(np.uint8)
            with Image.open(image) as opened:
                if opened.width%nw or opened.height%nh or opened.width//nw!=opened.height//nh:raise ValueError('FX image geometry changed')
                scale=opened.width//nw;alpha=np.asarray(opened.convert('RGBA').getchannel('A'))
                if not set(np.unique(alpha)).issubset({0,127,255}):raise ValueError('FX classes are not categorical')
                centres=alpha[scale//2::scale,scale//2::scale];mismatches=int(np.count_nonzero(centres!=expected))
                if mismatches:raise ValueError(f'FX native-centre classes differ for {key}: {mismatches}')
            matches=[i for i,r in enumerate(plan['entries']) if r['key']==key]
            if matches:raise ValueError('Unexpected authored FX key conflict '+key)
            row=dict(manifest=manifest_ref,key=key,image=ref(image),native_source=native,
                native_origin=dict(words=ref(word_path),clut=ref(clut_path),native_alpha_centres_exact=True,live_accepted=False))
            pending.append(row);receipts.append(dict(key=key,native_source=native,image=row['image'],native_alpha_centres_checked=nw*nh,mismatches=mismatches))
        if sha(manifest)!=manifest_ref['sha256']:raise ValueError('Frozen FX manifest changed during planning')
    if len(pending)!=65:raise ValueError('Expected65 currently delivered runtime FX entries')
    receipt=proofs/'effects-native-verification.json';receipt.write_text(json.dumps(dict(entries=receipts,omitted=omitted,live_accepted=False),indent=2)+'\n')
    for row in pending:row['source_handoff']=ref(receipt)
    plan['entries'].extend(pending);plan['wave2_fx_native_verification']=ref(receipt)
    return dict(added=len(pending),native_alpha_centres_exact=True,omitted_master_only=omitted)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-plan',required=True,type=Path)
    p.add_argument('--parent-candidate',required=True,type=Path)
    p.add_argument('--output-plan',required=True,type=Path)
    p.add_argument('--include-hud',action='store_true')
    p.add_argument('--proofs',type=Path)
    p.add_argument('--include-fx',action='store_true')
    p.add_argument('--fx-proofs',type=Path)
    args=p.parse_args();output=args.output_plan.resolve()
    if output.parent!=EVIDENCE.resolve() or output.exists():raise ValueError('Use a fresh direct child of private completion evidence')
    plan=json.loads(args.parent_plan.read_bytes());parent=json.loads(args.parent_candidate.read_bytes())
    if parent.get('production_installed') is not False:raise ValueError('Private parent candidate required')
    if parent['composition_plan']['sha256']!=sha(args.parent_plan):raise ValueError('Parent plan does not match composed candidate')
    updated=polish(plan);plan['parent']=ref(args.parent_candidate)
    if args.include_hud and not args.proofs:p.error('--include-hud requires --proofs')
    hud_result=hud(plan,args.proofs.resolve()) if args.include_hud else None
    if args.include_fx and not args.fx_proofs:p.error('--include-fx requires --fx-proofs')
    fx_result=effects(plan,args.fx_proofs.resolve()) if args.include_fx else None
    plan['wave2_polish_updates']=updated
    plan.setdefault('limitations',[]).append('Wave2 polish registration does not establish live appearance or remove documented defects; unchanged entries retain their own frozen provenance.')
    output.write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(dict(plan=str(output),polish_revisions=len(updated),hud=hud_result,effects=fx_result,total_entries=len(plan['entries']),installed=False)))


if __name__=='__main__':main()
