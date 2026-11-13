"""Import delivered Astraea hulls and approved W3 sign regions, never install."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import ROOT,EVIDENCE,pinned,sha,verified_native_source
from extend_stage1_mk3_plan import source,centres
from publish_stage1_wave2_results import registered_key

ART=ROOT/'remaster-audit/comfy-authoring'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
def local(folder,r):
    p=Path(r['path']);p=p if p.is_absolute() else folder/p
    return pinned(dict(path=str(p),sha256=r['sha256']))

def native_centres(row):
    e=row['exact'];words=np.frombuffer(pinned(e['source_words']).read_bytes(),dtype='<u2').reshape(e['source_shape_words'][1],e['source_shape_words'][0])
    clut=np.frombuffer(pinned(e['source_clut']).read_bytes(),dtype='<u2')
    assert e['depth']==0
    indices=((words[:,:,None]>>np.array([0,4,8,12]))&15).reshape(words.shape[0],words.shape[1]*4)
    colors=clut[indices];alpha=np.where(colors==0,0,np.where(colors&0x8000,255,127)).astype('uint8')
    l,t,r,b=e['uv'];a=alpha[t:b,l:r]
    with Image.open(pinned(row['image'])) as im:
        if row.get('image_uv'):
            nw,nh=row['image_space_native'];assert im.width%nw==0 and im.height%nh==0
            sx,sy=im.width//nw,im.height//nh;l0,t0,r0,b0=row['image_uv'];im=im.crop((l0*sx,t0*sy,r0*sx,b0*sy))
        assert im.width%a.shape[1]==0 and im.height%a.shape[0]==0
        scale=im.width//a.shape[1];assert scale==im.height//a.shape[0]
        assert np.array_equal(np.asarray(im.convert('RGBA'))[scale//2::scale,scale//2::scale,3],a),'Native sign-centre class changed'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['parent-plan','parent-candidate','output-plan','proofs']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.proofs.resolve();target=a.output_plan.resolve()
    assert out.parent==EVIDENCE.resolve() and not out.exists() and target.parent==EVIDENCE.resolve() and not target.exists()
    parent=read(a.parent_candidate);assert sha(a.parent_plan)==parent['composition_plan']['sha256']
    plan=copy.deepcopy(read(a.parent_plan));plan['parent']=ref(a.parent_candidate);out.mkdir();updates=[];added=[];pins=[]
    folder=ART/'w3-astraea/frozen/w3-astraea-hulls-v1';mfile=folder/'manifest.json'
    assert sha(mfile)=='c554da80a7512c3d8a8777d2700cea6947cb3515be575782fe2a9b5bb3644b7d'
    m=read(mfile);assembly=folder/'assembly.json';compiled=read(assembly);pins+=[ref(mfile),ref(assembly)]
    receipt=Path(m['evidence']['verification_file']);assert sha(receipt)==m['evidence']['verification_sha256'];verified=read(receipt)
    for key,item in m['keys'].items():
        entry=next(x for x in verified['entries'] if x['key']==key)
        for field in ['raw_words_sha256','clut_sha256','png_sha256']:assert item['source'][field]==entry[field]
        native,stock=source(dict(verification_file=str(receipt),verification_sha256=m['evidence']['verification_sha256'],entry=entry))
        image=folder/'runtime/1024-calm'/(key+'.png');assert sha(image)==compiled['keys'][key][image.relative_to(folder).as_posix()]
        centres(image,stock)
        added.append(dict(key=key,manifest=ref(mfile),source_handoff=ref(assembly),image=ref(image),native_source=native,
            known_limits=m['known_limits'],live_accepted=False))
    # The Astraea page differs in hull slots. Reuse only independently equal
    # weapon cells, never alias the whole page or the two unknown palettes.
    pod_manifest=ART/'t6-player/frozen/t6-gunpods-v1/manifest.json';pods=read(pod_manifest)
    e38=next(x for x in verified['entries'] if x['key'].startswith('E38AE747-'))
    page_native,page_png=source(dict(verification_file=str(receipt),verification_sha256=m['evidence']['verification_sha256'],entry=e38))
    page_words=np.frombuffer(pinned(page_native['source_words']).read_bytes(),dtype='<u2').reshape(256,64)
    meta=read(page_png.with_suffix('.source.json'));assert len(meta['fragments'])==1 and meta['fragments'][0][2:]==[64,256,0,0]
    page_xy=meta['fragments'][0][:2];pod_aliases=0;unobserved_pod_phases=[]
    for pod in pods['pods'].values():
        key='E38AE747-'+pod['clut']
        observed=next((x for x in verified['entries'] if x['key']==key),None)
        if not observed:unobserved_pod_phases.append(key);continue
        original=next(x for x in plan['entries'] if x['key']==pod['page_key'])
        original_words=np.frombuffer(pinned(original['native_source']['source_words']).read_bytes(),dtype='<u2').reshape(256,64)
        u,v=pod['cell_uv'];uv=[u,v,u+64,v+64]
        assert np.array_equal(page_words[v:v+64,u//4:(u+64)//4],original_words[v:v+64,u//4:(u+64)//4])
        for strip in pod['strips']:
            lo,hi=strip['rows'];assert np.array_equal(page_words[lo:hi],original_words[lo:hi]),'Weapon strip needs a scoped Astraea composite'
        native=dict(page_native,source_clut=original['native_source']['source_clut'])
        verified_native_source(native,key)
        row=dict(key=key,manifest=ref(pod_manifest),source_handoff=ref(mfile),image=original['image'],
            image_uv=uv,image_space_native=[256,256],exact=dict(**native,page_xy=page_xy,uv=uv,clut_xy=observed['clut_xy']),
            native_origin=dict(astraea_page_verification=ref(receipt),weapon_cell_words_identical=True,
                full_weapon_strips_identical=True,observed_pair=any(x['key']==key for x in verified['entries']),
                unknown_palettes_excluded=['2015CB79','D5F04FFE']))
        native_centres(row);added.append(row);pod_aliases+=1
    index_path=ART/'w3-signs/INDEX.json';index=read(index_path);pins.append(ref(index_path))
    for board in index['boards']:
        if not board.get('USE','').startswith('w3-signs/') or board['board']==1:continue
        folder=ART/board['USE'];mfile=folder/'manifest.json';m=read(mfile);pins.append(ref(mfile))
        if board['board']==20:
            region=m['exact_region'];key=region['exact_region_key'];image=folder/'region'/(key+'.png')
            assert sha(image)==m['files'][image.relative_to(folder).as_posix()]
            old=next(x for x in parent['files'] if x['name']==key+'.png');base=pinned(dict(path=old['composed_path'],sha256=old['sha256']))
            assert old['sha256']==m['parent']['sha256']
            with Image.open(base) as before,Image.open(image) as after:
                assert before.size==after.size and np.array_equal(np.asarray(before.convert('RGBA'))[:,448:],np.asarray(after.convert('RGBA'))[:,448:])
            # Reuse the parent's exact binding and its cropped native source.
            pack=Path(parent['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT'])
            words=pack/(key+'.words.bin');clut=pack/(key+'.clut.bin')
            native=dict(source_words=ref(words),source_clut=ref(clut),source_shape_words=[16,24],depth=0)
            verified_native_source(native,key)
            added.append(dict(key=key,manifest=ref(mfile),image=ref(image),native_source=native,
                native_origin=dict(existing_exact_region=region,outside_left_mark_rgba_unchanged=True)))
            continue
        phases=m['phases']
        for phase in phases:
            region=phase['region'];image=local(folder,region)
            words=local(folder,phase['source_files']['.words.bin']);clut=local(folder,phase['source_files']['.clut.bin'])
            meta=read(local(folder,phase['source_files']['.source.json']))
            native=dict(source_words=ref(words),source_clut=ref(clut),source_shape_words=[meta['width_words'],meta['height']],depth=meta['depth'])
            verified_native_source(native,phase['key']);assert meta['known_words']==meta['total_words']==meta['width_words']*meta['height']
            row=dict(key=phase['key'],manifest=ref(mfile),image=ref(image),exact=dict(**native,
                page_xy=region['page_xy'],uv=region['source_uv_half_open'],clut_xy=region['clut_xy']))
            assert registered_key(row)==region['exact_region_key'];native_centres(row)
            matches=[i for i,old in enumerate(plan['entries']) if registered_key(old)==region['exact_region_key']]
            if matches:
                assert len(matches)==1;old=plan['entries'][matches[0]]
                assert old['exact']['uv']==row['exact']['uv'] and old['exact']['clut_xy']==row['exact']['clut_xy']
                if m['supersedes'].get('manifest_sha256'):assert old['manifest']['sha256']==m['supersedes']['manifest_sha256']
                plan['entries'][matches[0]]=row;updates.append(region['exact_region_key'])
            else:
                assert board['board'] in [25,27],'Existing sign unexpectedly unmapped'
                added.append(row)
    existing={registered_key(x) for x in plan['entries']};assert not existing&{registered_key(x) for x in added}
    plan['entries'].extend(added)
    for pin in pins:assert sha(Path(pin['path']))==pin['sha256'],'Frozen input changed during import'
    plan['w3_import']=dict(input_refs=pins,astraea_hulls=5,sign_phase_replacements=len(updates),
        new_entries=len(added),skipped_rejected_kaplo=True,pod_whole_page_aliases=False,pod_cells_registered=pod_aliases,
        unobserved_pod_phases=unobserved_pod_phases,
        remaining=['Astraea canopy/glint, live pod-cell acceptance and unknown owners','All revised signs/ships require live pose and motion acceptance'],live_accepted=False,installed=False)
    write(target,plan);write(out/'import.json',plan['w3_import'])
    print(json.dumps(dict(plan=str(target),entries=len(plan['entries']),added=len(added),updated=len(updates))))

if __name__=='__main__':main()
