"""Register frozen Mk.III hulls and its mechanical cell in a fresh private plan."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import EVIDENCE, ROOT, sha, pinned, verified_native_source

ART=ROOT/'remaster-audit/comfy-authoring/w3-mk3/frozen/w3-mk3-hulls-v1'
MANIFEST_SHA='2b68a3137f7c1ae252dbac3daa807971bc3c95b0dd5b5f3b64d41b55c69b29d9'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def ref(path):return dict(path=str(path.resolve()),sha256=sha(path))
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def source(verified):
    receipt=Path(verified['verification_file'])
    if 'verification_sha256' in verified:assert sha(receipt)==verified['verification_sha256']
    row=verified['entry'];assert row['status']=='pass'
    recorded=next(x for x in read(receipt)['entries'] if x['key']==row['key'])
    for field in ['status','raw_words_sha256','clut_sha256','png_sha256','dimensions','depth']:
        assert recorded[field]==row[field],'Manifest source must match independent verification'
    image=Path(row['path']);base=image.with_suffix('')
    assert sha(image)==row['png_sha256']
    words=Path(str(base)+'.words.bin');clut=Path(str(base)+'.clut.bin')
    assert sha(words)==row['raw_words_sha256'] and sha(clut)==row['clut_sha256']
    validity=Path(str(base)+'.valid.bin');assert set(validity.read_bytes())=={1}
    metadata=read(Path(str(base)+'.source.json'))
    result=dict(source_words=ref(words),source_clut=ref(clut),
                source_shape_words=[metadata['width_words'],metadata['height']],depth=metadata['depth'])
    assert validity.stat().st_size==metadata['width_words']*metadata['height']
    assert row['dimensions']==[metadata['width_words']*(4>>metadata['depth']),metadata['height']]
    verified_native_source(result,row['key'])
    return result,image

def centres(image,native):
    with Image.open(image) as opened,Image.open(native) as stock:
        rgba=np.asarray(opened.convert('RGBA'));a=np.asarray(stock.convert('RGBA'))[:,:,3]
        h,w=a.shape;assert rgba.shape[1]%w==0 and rgba.shape[0]%h==0
        scale=rgba.shape[1]//w;assert scale==rgba.shape[0]//h
        assert np.array_equal(rgba[scale//2::scale,scale//2::scale,3],a),'Native centre classes changed'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['parent-plan','parent-candidate','output-plan','proofs']:p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();out=args.proofs.resolve();target=args.output_plan.resolve()
    assert out.parent==EVIDENCE.resolve() and not out.exists()
    assert target.parent==EVIDENCE.resolve() and not target.exists()
    parent=read(args.parent_candidate);assert sha(args.parent_plan)==parent['composition_plan']['sha256']
    plan=copy.deepcopy(read(args.parent_plan));plan['parent']=ref(args.parent_candidate)
    manifest_path=ART/'manifest.json';assert sha(manifest_path)==MANIFEST_SHA
    manifest=read(manifest_path);manifest_ref=ref(manifest_path)
    out.mkdir();added=[]
    for category in ['keys','strip_keys']:
        for key,item in manifest[category].items():
            image=ART/'runtime/1024-calm'/(key+'.png')
            expected=item['runtime']['1024-calm'] if category=='keys' else item['runtime/1024-calm/'+key+'.png']
            assert sha(image)==expected
            native,stock=source(item['verified_source']);centres(image,stock)
            added.append(dict(key=key,manifest=manifest_ref,image=ref(image),native_source=native))
    # The page contains HUD glyphs too. Bind only the proven mechanical cell;
    # the rest of the page remains under its existing replacement/native path.
    cell=ART/'runtime/1024-calm/CELL-34796C39-E0AE221F-u192v64-cell.png'
    assert sha(cell)==manifest['grey_cell']['files'][cell.relative_to(ART).as_posix()]
    native,page=source(manifest['grey_cell']['verified_source'])
    words=np.frombuffer(pinned(native['source_words']).read_bytes(),dtype='<u2').reshape(256,64)
    with Image.open(page) as im:im.crop((192,64,256,128)).save(out/'native-cell.png')
    centres(cell,out/'native-cell.png')
    # The compositor pins the complete source page, then derives and registers
    # the small cell's raw CRC and VRAM rectangle from these exact bounds.
    added.append(dict(key='34796C39-E0AE221F',manifest=manifest_ref,image=ref(cell),exact=dict(
        source_words=native['source_words'],source_clut=native['source_clut'],
        source_shape_words=[64,256],page_xy=[832,256],uv=[192,64,256,128],depth=0,clut_xy=[272,510])))
    # Another native eight-row upload carries the same cell alongside HUD data.
    # Its surviving right-hand fragment proves rows80..87 of the page.
    key='59471BC6-E0AE221F';receipt=read(Path(manifest['evidence']['verification']))
    verified=next(x for x in receipt['entries'] if x['key']==key)
    native,stock=source(dict(verification_file=manifest['evidence']['verification'],
        verification_sha256=manifest['evidence']['verification_sha256'],entry=verified))
    strip_words=np.frombuffer(pinned(native['source_words']).read_bytes(),dtype='<u2').reshape(8,64)
    assert np.array_equal(strip_words[:,48:64],words[80:88,48:64])
    old=next(x for x in parent['files'] if x['name']==key+'.png');base=pinned(dict(path=old['composed_path'],sha256=old['sha256']))
    with Image.open(base) as im:result=im.convert('RGBA')
    assert result.size==(4096,128)
    before=np.asarray(result).copy()
    with Image.open(cell) as im:result.paste(im.crop((0,16*16,1024,24*16)),(192*16,0))
    assert np.array_equal(np.asarray(result)[:,:192*16],before[:,:192*16])
    composite=out/(key+'.png');result.save(composite);centres(composite,stock)
    added.append(dict(key=key,manifest=manifest_ref,image=ref(composite),native_source=native,
        composition=dict(parent_png=ref(base),cell=ref(cell),source_cell_rows=[16,24],destination_native_uv=[192,0,256,8],outside_rgba_unchanged=True)))
    assert len(added)==6 and not ({x['key'] for x in plan['entries']}&{x['key'] for x in added})
    plan['entries'].extend(added);plan['mk3_integration']=dict(manifest=manifest_ref,entries=6,
        shared_hulls_unchanged=['724E77DA-21FDE894','E2F3477C-21FDE894'],native_centres_verified=True,
        hud_outside_cell_preserved=True,live_accepted=False,installed=False)
    assert sha(manifest_path)==manifest_ref['sha256']
    write(target,plan);write(out/'integration.json',plan['mk3_integration'])
    print(json.dumps(dict(plan=str(target),authored_entries=len(plan['entries']),added=6)))

if __name__=='__main__':main()
