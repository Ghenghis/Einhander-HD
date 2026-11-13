"""Compose a pinned artwork plan into a fresh private candidate, never install it.

Plan: parent={path,sha256}; entries=[{manifest:{path,sha256}, key, image:
{path,sha256}, optional exact:{source_words:{path,sha256}, source_clut:
{path,sha256}, source_shape_words:[w,h], page_xy:[x,y], uv:[l,t,r,b],
depth:0|1|2, clut_xy:[x,y]}}]. Exact images already cover the UV rectangle.
Every image must use categorical alpha. Hashes pin inputs; output receipts
record lineage, retained limitations, and pending live acceptance.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import zlib
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
KEY=re.compile(r'[0-9A-F]{8}-[0-9A-F]{8}')

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def pinned(ref):
    path=Path(ref['path']).resolve()
    if sha(path)!=ref['sha256']:raise ValueError('Pinned input changed: '+str(path))
    return path

def atomic(path,data):
    # Break immutable parent hardlinks before replacing any candidate file.
    temporary=path.with_name(path.name+'.new')
    with temporary.open('xb') as stream:stream.write(data)
    temporary.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.parent!=EVIDENCE.resolve() or out.exists():raise ValueError('Use a fresh direct child of private completion evidence')
    plan_path=args.plan.resolve();plan=json.loads(plan_path.read_bytes())
    parent_path=pinned(plan['parent']);parent=json.loads(parent_path.read_bytes())
    parent_pack=Path(parent['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT'])
    manifest_refs={}
    for row in plan['entries']:
        path=pinned(row['manifest']);metadata=json.loads(path.read_bytes())
        manifest_refs[str(path)]=dict(sha256=sha(path),metadata=metadata)
        pinned(row['image'])
        if row.get('alpha'):pinned(row['alpha'])
        if row.get('source_handoff'):pinned(row['source_handoff'])
        if not KEY.fullmatch(row['key']):raise ValueError('Invalid exact key')
        declared=metadata.get('keys',{})
        if isinstance(declared,dict) and row['key'] in declared:
            native=declared[row['key']]
            if all(k in native for k in ('words','words_sha256','clut','clut_sha256')):
                words=pinned(dict(path=native['words'],sha256=native['words_sha256'])).read_bytes()
                clut=pinned(dict(path=native['clut'],sha256=native['clut_sha256'])).read_bytes()
                if f'{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}'!=row['key']:
                    raise ValueError('Manifest native source pair does not match its key')
    out.mkdir();pack=out/'pack'
    snapshots=out/'input-manifests';snapshots.mkdir()
    for path,ref in manifest_refs.items():
        data=Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest()!=ref['sha256']:raise ValueError('Manifest changed before snapshot')
        snapshot=snapshots/(ref['sha256']+'.json');snapshot.write_bytes(data)
        ref['snapshot']=str(snapshot)
    def link_or_copy(source,target):
        try:os.link(source,target)
        except OSError:shutil.copy2(source,target)
        return target
    shutil.copytree(parent_pack,pack,copy_function=link_or_copy)
    replacements=pack/'einhander-texture-replacements'
    if not replacements.is_dir():raise ValueError('Expected one canonical replacement directory')
    ledger={}
    for row in parent['files']:
        path=replacements/row['name']
        if sha(path)!=row['sha256']:raise ValueError('Parent ledger differs: '+row['name'])
        ledger[row['name']]=dict(row,composed_path=str(path),origin='unchanged immutable parent',
            parent=dict(path=row['composed_path'],sha256=row['sha256']))
    exact_file=pack/'ExactRegions.tsv'
    exact_lines=exact_file.read_text().splitlines() if exact_file.exists() else ['EIN_EXACT_REGIONS_V1']
    chosen=set()
    for row in plan['entries']:
        image_path=pinned(row['image']);key=row['key'];exact=row.get('exact')
        source_proof=None
        if exact:
            words=pinned(exact['source_words']).read_bytes();clut=pinned(exact['source_clut']).read_bytes()
            w,h=exact['source_shape_words'];depth=exact['depth'];ppw=4>>depth
            if depth not in (0,1,2) or len(words)!=w*h*2:raise ValueError('Invalid source dimensions/depth')
            if f'{zlib.crc32(words):08X}-{zlib.crc32(clut) if depth<2 else 0:08X}'!=key:
                raise ValueError('Source words or full CLUT do not match declared native key')
            if len(clut)!=(32 if depth==0 else 512 if depth==1 else 0):raise ValueError('Invalid full CLUT size')
            l,t,r,b=exact['uv']
            if not (0<=l<r<=w*ppw and 0<=t<b<=h and l%ppw==0 and r%ppw==0):raise ValueError('Unaligned/outside exact rectangle')
            cropped=b''.join(words[(y*w+l//ppw)*2:(y*w+r//ppw)*2] for y in range(t,b))
            key=f'{zlib.crc32(cropped):08X}-{zlib.crc32(clut) if depth<2 else 0:08X}'
            x=exact['page_xy'][0]+l//ppw;y=exact['page_xy'][1]+t
            rw=(r-l)//ppw;rh=b-t;cx,cy=exact['clut_xy']
            if x<320 or x+rw>1024 or y<0 or y+rh>512:raise ValueError('Exact rectangle outside texture VRAM')
            for suffix,data in [('words.bin',cropped),('clut.bin',clut),('valid.bin',bytes([1])*(rw*rh))]:
                atomic(pack/(key+'.'+suffix),data)
            line='\t'.join(map(str,[key,x,y,rw,rh,depth,cx,cy]))
            if line not in exact_lines:exact_lines.append(line)
            source_proof=dict(fullpage_key=row['key'],region_key=key,rectangle_words=[x,y,rw,rh],
                uv_half_open=[l,t,r,b],depth=depth,clut_xy=[cx,cy],words_sha256=hashlib.sha256(cropped).hexdigest(),
                clut_sha256=hashlib.sha256(clut).hexdigest(),source_words=row['exact']['source_words'])
        if key in chosen:raise ValueError('Conflicting plan entries for '+key)
        chosen.add(key)
        with Image.open(image_path) as opened:
            image=opened.convert('RGBA')
            if row.get('image_uv'):
                nw,nh=row['image_space_native'];l0,t0,r0,b0=row['image_uv']
                if image.width%nw or image.height%nh:raise ValueError('Image crop has a noninteger native scale')
                sx,sy=image.width//nw,image.height//nh
                image=image.crop((l0*sx,t0*sy,r0*sx,b0*sy))
            width,height=image.size
            if row.get('alpha'):
                with Image.open(pinned(row['alpha'])) as source_alpha:
                    alpha=source_alpha.getchannel('A') if source_alpha.mode=='RGBA' else source_alpha.convert('L')
                    if row.get('alpha_uv'):alpha=alpha.crop(tuple(row['alpha_uv']))
                    if not set(np.unique(np.asarray(alpha))).issubset({0,127,255}):
                        raise ValueError('Native alpha plane is not categorical')
                    if alpha.width*height!=alpha.height*width:raise ValueError('Native alpha plane aspect differs')
                    image.putalpha(alpha.resize(image.size,Image.Resampling.NEAREST))
            if exact and (width%(r-l) or height%(b-t) or width//(r-l)!=height//(b-t)):
                raise ValueError('Exact artwork scale does not match its native rectangle')
            classes=np.unique(np.asarray(image.getchannel('A')))
            if not set(classes).issubset({0,127,255}):raise ValueError('Noncategorical alpha: '+str(image_path))
            if not (1<=width<=4096 and 1<=height<=4096):raise ValueError('Image exceeds renderer dimensions')
            buffer=io.BytesIO();image.save(buffer,format='PNG')
        name=key+'.png';target=replacements/name;previous=ledger.get(name)
        atomic(target,buffer.getvalue())
        ledger[name]=dict(name=name,composed_path=str(target),sha256=sha(target),dimensions=[width,height],
            bytes=target.stat().st_size,origin='frozen artwork candidate',input=row,
            previous_sha256=previous['sha256'] if previous else None,source_proof=source_proof,
            alpha_classes=classes.tolist(),live_verified=False)
    atomic(exact_file,('\n'.join(exact_lines)+'\n').encode())
    report=copy.deepcopy(parent)
    report.update(evidence=str(out),variant=out.name,files=sorted(ledger.values(),key=lambda row:row['name']),
        final_count=len(ledger),composition_plan=dict(path=str(plan_path),sha256=sha(plan_path)),
        frozen_manifests=manifest_refs,parent_candidate=dict(path=str(parent_path),sha256=sha(parent_path)),
        authored_entries=len(plan['entries']),live_visual_accepted=False,production_installed=False,
        composed_at_utc=datetime.now(timezone.utc).isoformat())
    report['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT']=str(pack)
    report['launches']['candidate']['environment_overrides'].update(PSXRECOMP_SKIN_ENEMY_PROFILE='stock',PSXRECOMP_SKIN_ENEMY_DETAIL_PATH='')
    # Verify parent identities again after every atomic candidate replacement.
    for row in parent['files']:
        if sha(row['composed_path'])!=row['sha256']:raise ValueError('Parent was changed during composition')
    (out/'candidate.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(candidate=str(out/'candidate.json'),files=len(ledger),authored_entries=len(plan['entries']),production_installed=False)))

if __name__=='__main__':main()
