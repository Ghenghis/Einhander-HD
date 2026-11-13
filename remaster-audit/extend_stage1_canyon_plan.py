"""Pin the brighter matching canyon pair and their source-sized emissive masks."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import ROOT,EVIDENCE,sha,pinned
from extend_stage1_w3_plan import native_centres

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-plan',type=Path,required=True)
    a=p.parse_args();out=a.output_plan.resolve();assert out.parent==EVIDENCE.resolve() and not out.exists()
    plan=copy.deepcopy(read(a.plan));pinned(plan['parent']);base=ROOT/'remaster-audit/comfy-authoring/w3-canyon/frozen';pins=[];rows=[]
    for name,key,mask_name in [('AB2DB563-wall-v4','AB2DB563-07D24911','extras/AB2DB563-07D24911-emissive-mask-2048.png'),
        ('2294438F-band-v4-proposal','2294438F-EA6ACA31','runtime-2048/2294438F-EA6ACA31-emissive.png')]:
        folder=base/name;mf=folder/'manifest.json';m=read(mf);pins.append(ref(mf))
        image=folder/'runtime-2048'/(key+'.png');assert sha(image)==m['files'][image.relative_to(folder).as_posix()]
        mask_folder=folder if name.startswith('AB') else base/'2294438F-band-v4-emissive-v1'
        mask_manifest=mask_folder/'manifest.json';mm=read(mask_manifest);pins.append(ref(mask_manifest))
        mask=mask_folder/mask_name;assert sha(mask)==mm['files'][mask_name]
        row=next(x for x in plan['entries'] if x['key']==key)
        row.update(manifest=ref(mf),image=ref(image),emissive=ref(mask),source_handoff=ref(mask_manifest),known_limits=m['known_limits'])
        native_centres(row)
        with Image.open(mask) as opened,Image.open(image) as rgb:
            assert opened.mode=='L' and opened.size==rgb.size==(2048,2048)
        rows.append(row)
    with Image.open(pinned(rows[0]['image'])) as wall,Image.open(pinned(rows[1]['image'])) as band:
        assert np.array_equal(np.asarray(wall)[40:552],np.asarray(band)[:512]),'Matching RGB band differs'
    with Image.open(pinned(rows[0]['emissive'])) as wall,Image.open(pinned(rows[1]['emissive'])) as band:
        assert np.array_equal(np.asarray(wall)[40:552],np.asarray(band)[:512]),'Matching emissive band differs'
    for pin in pins:pinned(pin)
    plan['canyon_emissive_update']=dict(base_plan=ref(a.plan),inputs=pins,source_sized_mask_mode='L8',matching_rgb_and_mask_rows=True,
        runtime_sidecar='<registered replacement key>-emissive.png',startup_opt_in='PSXRECOMP_HD_EMISSIVE=1',live_accepted=False,installed=False)
    out.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(plan=str(out),entries=len(plan['entries']),masked_entries=2)))

if __name__=='__main__':main()
