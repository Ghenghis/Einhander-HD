"""Reconcile latest canyon, Astraea canopy and HUD artwork into a fresh plan."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import zlib
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import ROOT,EVIDENCE,sha,pinned,verified_native_source
from extend_stage1_mk3_plan import source,centres
from extend_stage1_w3_plan import native_centres
from publish_stage1_wave2_results import registered_key

ART=ROOT/'remaster-audit/comfy-authoring'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
def resolve(folder,r):
    p=Path(r['path']);return pinned(dict(path=str(p if p.is_absolute() else folder/p),sha256=r['sha256']))
def colors(native):
    w,h=native['source_shape_words'];words=np.frombuffer(pinned(native['source_words']).read_bytes(),dtype='<u2').reshape(h,w)
    clut=np.frombuffer(pinned(native['source_clut']).read_bytes(),dtype='<u2')
    indices=((words[:,:,None]>>np.array([0,4,8,12]))&15).reshape(h,w*4)
    return clut[indices]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['parent-plan','parent-candidate','output-plan','proofs']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.proofs.resolve();target=a.output_plan.resolve()
    assert out.parent==EVIDENCE.resolve() and not out.exists() and target.parent==EVIDENCE.resolve() and not target.exists()
    parent=read(a.parent_candidate);assert sha(a.parent_plan)==parent['composition_plan']['sha256']
    plan=copy.deepcopy(read(a.parent_plan));plan['parent']=ref(a.parent_candidate);out.mkdir();inputs=[];changed=[];added=[];ui_checks=[]
    def upsert(row):
        key=registered_key(row);matches=[i for i,x in enumerate(plan['entries']) if registered_key(x)==key]
        assert len(matches)<=1
        if matches:plan['entries'][matches[0]]=row;changed.append(key)
        else:plan['entries'].append(row);added.append(key)
    # All32 phases are independently captured native source pairs.
    folder=ART/'w3-astraea/frozen/w3-astraea-canopy-B9EB2209-v2';mfile=folder/'manifest.json'
    assert sha(mfile)=='28d9a2575a182e63b237f85f36823b592c9b040bf1f3102e6d587cd2263d0342'
    m=read(mfile);inputs.append(ref(mfile));receipt=Path(m['evidence']['verification_file'])
    assert sha(receipt)==m['evidence']['verification_sha256'];verified=read(receipt)
    for key,item in m['keys'].items():
        entry=next(x for x in verified['entries'] if x['key']==key)
        native,stock=source(dict(verification_file=str(receipt),verification_sha256=m['evidence']['verification_sha256'],entry=entry))
        relative='runtime/1024/'+key+'.png';image=folder/relative;assert sha(image)==item['runtime'][relative]['sha256'];centres(image,stock)
        upsert(dict(key=key,manifest=ref(mfile),image=ref(image),native_source=native,known_limits=m['known_limits']))
    # Keep each mixed native page outside its explicitly authored rectangle.
    wall_old=next(x for x in plan['entries'] if x['key']=='AB2DB563-07D24911')
    stock=Path(wall_old['exact']['source_clut']['path']).parent
    canonical_stock=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
    canyon=[]
    for name,key in [('AB2DB563-wall-v3','AB2DB563-07D24911'),('AB2DB563-emblem-v3b','AB2DB563-B869F949'),('2294438F-band-v3-proposal','2294438F-EA6ACA31')]:
        folder=ART/'w3-canyon/frozen'/name;mfile=folder/'manifest.json';m=read(mfile);inputs.append(ref(mfile))
        image=folder/'runtime-2048'/(key+'.png');assert sha(image)==m['files'][image.relative_to(folder).as_posix()]
        old=next((x for x in plan['entries'] if x['key']==key),None)
        if old:exact=copy.deepcopy(old['exact'])
        else:
            clut=canonical_stock/(key+'.clut.bin');assert sha(clut)==m['source']['clut_sha256']
            metadata=read(canonical_stock/(key+'.source.json'))
            exact=dict(source_words=wall_old['exact']['source_words'],source_clut=ref(clut),source_shape_words=[64,256],
                depth=0,page_xy=wall_old['exact']['page_xy'],uv=m['region']['uv'],clut_xy=metadata['clut_xy'])
        row=dict(key=key,manifest=ref(mfile),image=ref(image),image_uv=exact['uv'],image_space_native=[256,256],exact=exact,
            known_limits=m.get('known_limits',[]))
        native_centres(row);upsert(row);canyon.append(row)
    assert np.array_equal(colors(canyon[0]['exact'])[5:69]&0x7FFF,colors(canyon[2]['exact'])[:64]&0x7FFF),'Native wall/band colour correspondence changed'
    # UI glyph tracing keeps categorical alpha, while its changed stroke and
    # shadow samples are reported rather than claimed to be bit-exact native.
    for name in ['hud-label-font-BDAE4156-v1','results-grades-8E1A509D-v1','results-score-header-48F8001A-v1','results-footer-8E1A509D-v6']:
        folder=ART/'w3-hud/frozen'/name;mfile=folder/'manifest.json';m=read(mfile);inputs.append(ref(mfile));sources=m['sources']
        for item in m['keys']:
            key=item['key'];raw_hash=int(key.split('-')[0],16)
            output=item.get('out_4096') or item.get('out_4096x128') or item['runtime']['2048'];image=resolve(folder,output)
            words_ref=sources.get('strip_words') or sources['words'];words_path=pinned(words_ref);words=words_path.read_bytes();rows=None
            if zlib.crc32(words)!=raw_hash:
                candidates=[n for n in range(len(words)//128-7) if zlib.crc32(words[n*128:(n+8)*128])==raw_hash]
                assert candidates,'No source rows for '+key
                chunks={words[n*128:(n+8)*128] for n in candidates};assert len(chunks)==1
                words=next(iter(chunks));words_path=out/(key+'.words.bin');words_path.write_bytes(words);rows=candidates
            clut_ref=item.get('clut') or sources.get('clut');assert clut_ref,'Missing actual CLUT for '+key
            clut_path=pinned(clut_ref);height=len(words)//128;assert height in [8,256]
            native=dict(source_words=ref(words_path),source_clut=ref(clut_path),source_shape_words=[64,height],depth=0)
            verified_native_source(native,key)
            with Image.open(image) as opened:
                rgba=np.asarray(opened.convert('RGBA'));assert set(np.unique(rgba[:,:,3])).issubset({0,127,255})
                assert opened.width%256==0 and opened.height%height==0;scale=opened.width//256;assert scale==opened.height//height
                values=colors(native);alpha=np.where(values==0,0,np.where(values&0x8000,255,127)).astype('uint8')
                match=int(np.count_nonzero(rgba[scale//2::scale,scale//2::scale,3]==alpha))
                if not np.any(values):assert not np.any(rgba[:,:,3]),'Null palette cannot draw a UI block'
                if name.endswith('-v6'):
                    base=pinned(sources['base'])
                    with Image.open(base) as old:
                        before=np.asarray(old.convert('RGBA'));assert before.shape==rgba.shape
                        mask=np.ones(rgba.shape[:2],bool);l,t,r,b=item['changed_rect_texels'];mask[t*scale:b*scale,l*scale:r*scale]=False
                        assert np.array_equal(before[mask],rgba[mask]),'Footer changed outside NORMAL M'
            upsert(dict(key=key,manifest=ref(mfile),image=ref(image),native_source=native,
                native_origin=dict(full_page_words=words_ref,derived_row_candidates=rows),known_limits=m.get('known_limits',[])))
            ui_checks.append(dict(key=key,native_centre_classes_equal=match,total_centres=256*height,categorical_alpha=True))
    for pin in inputs:assert sha(Path(pin['path']))==pin['sha256'],'Frozen input changed'
    plan['w3_extras']=dict(inputs=inputs,added_keys=added,replaced_keys=changed,canopy_phases=32,canyon_entries=3,
        native_wall_band_colors_identical=True,ui_alpha_checks=ui_checks,live_accepted=False,installed=False,
        limits=['UI tracing is categorical, not universally native-centre-alpha identical','157 historical fade CLUT aliases still need actual palettes','Canyon lamp erratum and motion busyness need live review'])
    write(target,plan);write(out/'import.json',plan['w3_extras'])
    print(json.dumps(dict(plan=str(target),entries=len(plan['entries']),added=len(added),replaced=len(changed),ui_exports=len(ui_checks))))

if __name__=='__main__':main()
