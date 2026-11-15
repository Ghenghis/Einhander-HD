from pathlib import Path
import json,sys,hashlib
import numpy as np
from PIL import Image
n=Path(__file__).parent;plan=json.loads((n/'world-integration-plan-v1.json').read_text());rows=[];bad=[]
for e in plan['entries']:
 s=e['native_source'];w,h=s['source_shape_words'];depth=s['depth'];words=np.frombuffer(Path(s['source_words']['path']).read_bytes(),dtype='<u2').reshape(h,w)
 if depth<2:
  shifts=np.arange(4 if depth==0 else 2,dtype=np.uint16)*(4 if depth==0 else 8);indices=((words[:,:,None]>>shifts)&(15 if depth==0 else 255)).reshape(h,-1);palette=np.frombuffer(Path(s['source_clut']['path']).read_bytes(),dtype='<u2');pixels=palette[indices]
 else:pixels=words
 expected=np.where(pixels==0,0,np.where(pixels&0x8000,255,127)).astype(np.uint8)
 with Image.open(e['image']['path']) as im:
  assert im.mode=='RGBA',(e['key'],im.mode);width,height=im.size;assert width%expected.shape[1]==0 and height%h==0;scale=width//expected.shape[1];assert scale==height//h
  alpha=np.array(im.getchannel('A'));sample=alpha[scale//2::scale,scale//2::scale];assert sample.shape==expected.shape
  mismatches=int(np.count_nonzero(sample!=expected));classes=[int(x) for x in np.unique(alpha)];assert set(classes)<={0,127,255}
 row={'key':e['key'],'dimensions':[width,height],'native_texels':[expected.shape[1],h],'native_centres_checked':int(expected.size),'class_mismatches':mismatches,'alpha_classes':classes,'image_sha256':hashlib.sha256(Path(e['image']['path']).read_bytes()).hexdigest()};assert row['image_sha256']==e['image']['sha256'];rows.append(row)
 if mismatches:bad.append(row)
 if len(rows)%25==0:print(json.dumps({'checked':len(rows),'failures':len(bad)}),flush=True)
result={'plan_sha256':hashlib.sha256((n/'world-integration-plan-v1.json').read_bytes()).hexdigest(),'keys_checked':len(rows),'native_centres_checked':sum(x['native_centres_checked'] for x in rows),'failures':bad,'rows':rows,'scope':'Independent native word/CLUT categorical-alpha decode and texel-centre comparison. No RGB look, motion, renderer, gameplay or fullcoverage acceptance.'}
(n/'world-integration-native-class-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['keys_checked','native_centres_checked','failures']},indent=2));raise SystemExit(bool(bad))
