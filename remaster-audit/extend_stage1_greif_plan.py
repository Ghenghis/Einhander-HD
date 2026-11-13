"""Replace both Greif cohorts with a frozen revision; reject centre-class drift."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build_stage1_frozen_candidate import ROOT,EVIDENCE,sha,pinned,verified_native_source
from extend_stage1_w3_extras_plan import colors

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['parent-plan','parent-candidate','output-plan']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--revision',choices=['v2','v3'],default='v3')
    a=parser.parse_args();target=a.output_plan.resolve()
    assert target.parent==EVIDENCE.resolve() and not target.exists()
    parent=read(a.parent_candidate);assert sha(a.parent_plan)==parent['composition_plan']['sha256']
    plan=copy.deepcopy(read(a.parent_plan));plan['parent']=ref(a.parent_candidate)
    positions={x['key']:i for i,x in enumerate(plan['entries'])};assert len(positions)==len(plan['entries'])
    pins=[];checks=[]
    for page in ['1263A036','38DC02FE']:
        folder=ROOT/'remaster-audit/comfy-authoring/t7-enemies/frozen'/('greif-'+page+'-'+a.revision)
        manifest=folder/'manifest.json';m=read(manifest);pins.append(ref(manifest))
        assert m['keys']['all_gates_pass'] and m['page']==page
        predecessor=folder.parent/Path(m['supersedes']['frozen']).name/'manifest.json'
        assert sha(predecessor)==m['supersedes']['manifest_sha256'];pins.append(ref(predecessor))
        for item in m['keys']['keys']:
            key=item['key'];row=copy.deepcopy(plan['entries'][positions[key]])
            expected=m['supersedes']['manifest_sha256']
            if row['manifest']['sha256']!=expected:expected=read(predecessor)['supersedes']['manifest_sha256']
            assert row['manifest']['sha256']==expected
            native=row['native_source'];verified_native_source(native,key)
            if item['kind']=='page':assert native['source_words']['sha256']==m['sources']['stock_keys'][key]['words_sha256']
            else:
                full=plan['entries'][positions[page+'-'+item['clut']]]['native_source']
                data=pinned(full['source_words']).read_bytes();start=item['row']*128
                assert pinned(native['source_words']).read_bytes()==data[start:start+1024]
            image=folder/'runtime-1024'/(key+'.png');image_ref=ref(image)
            values=colors(native);alpha=np.where(values==0,0,np.where(values&0x8000,255,127)).astype('uint8')
            with Image.open(image) as opened:
                rgba=np.asarray(opened.convert('RGBA'));assert set(np.unique(rgba[:,:,3])).issubset({0,127,255})
                assert opened.size==(alpha.shape[1]*4,alpha.shape[0]*4)
                equal=int(np.count_nonzero(rgba[2::4,2::4,3]==alpha))
                assert equal==alpha.size,'Native centre class changed: '+key
            row.update(manifest=ref(manifest),image=image_ref,known_limits=m['known_limits'],live_accepted=False)
            plan['entries'][positions[key]]=row
            checks.append(dict(key=key,kind=item['kind'],image=image_ref,native_centres=equal))
    assert len(checks)==116 and any(x['key']=='3B9C8491-6E78D825' for x in checks)
    for pin in pins:assert sha(Path(pin['path']))==pin['sha256']
    plan['greif_update']=dict(revision=a.revision,inputs=pins,entries=checks,page_and_strip_cohorts_together=True,
        live_accepted=False,installed=False,limitations='Artist recompositions and shimmer scores are simulations; live motion review remains required')
    target.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(plan=str(target),entries=len(plan['entries']),replaced=len(checks))))

if __name__=='__main__':main()
