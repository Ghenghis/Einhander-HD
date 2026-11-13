"""Pin delivered atlas window masks without altering any authored RGB image."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import ROOT, EVIDENCE, sha, pinned

def ref(path):
    return dict(path=str(path.resolve()), sha256=sha(path))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('parent-plan','parent-candidate','output-plan'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();target=args.output_plan.resolve()
    assert target.parent==EVIDENCE.resolve() and not target.exists()
    parent=json.loads(args.parent_candidate.read_bytes())
    assert sha(args.parent_plan)==parent['composition_plan']['sha256']
    plan=copy.deepcopy(json.loads(args.parent_plan.read_bytes()))
    folder=ROOT/'remaster-audit/comfy-authoring/w3-emissive/frozen/95A3BCF8-O-emissive-v1'
    manifest=folder/'manifest.json';metadata=json.loads(manifest.read_bytes())
    assert metadata['region_uv_half_open']==[176,112,240,176]
    assert metadata['pins']['pack_candidate']==ref(args.parent_candidate)
    pinned(metadata['pins']['source_manifest'])
    proof=[]
    for key in metadata['keys']:
        row=next(x for x in plan['entries'] if x['key']==key)
        assert not row.get('exact'),'These masks match full-page atlas replacements'
        item=metadata['masks']['2048/'+key.split('-')[1]]
        mask=folder/item['file'];assert sha(mask)==item['sha256']
        image=pinned(row['image']);assert sha(image)==item['runtime_png']['sha256']
        with Image.open(mask) as opened,Image.open(image) as rgb:
            assert opened.mode=='L' and opened.size==rgb.size==(2048,2048)
            data=np.asarray(opened);outside=data.copy();outside[112*8:176*8,176*8:240*8]=0
            assert not outside.any(),'Mask leaks outside delivered region O'
            assert np.count_nonzero(data)==item['nonzero_px']
        row.update(emissive=ref(mask),source_handoff=ref(manifest))
        proof.append(dict(key=key,image=ref(image),mask=ref(mask),nonzero_px=item['nonzero_px']))
    plan['parent']=ref(args.parent_candidate)
    plan['atlas_emissive_update']=dict(base_plan=ref(args.parent_plan),manifest=ref(manifest),entries=proof,
        rgb_unchanged=True,live_accepted=False,installed=False)
    target.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(plan=str(target),entries=len(plan['entries']),added_masks=len(proof))))

if __name__=='__main__':main()
