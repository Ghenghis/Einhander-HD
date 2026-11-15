from pathlib import Path
import datetime,hashlib,json,sys,psutil,numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([me.cpu_affinity()[-1]])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
f=r/'remaster-audit/claude-backlog/95a3-k-panel/frozen/95A3BCF8-K-panel-v1';manifest=f/'manifest.json';m=json.loads(manifest.read_text());key=m['key']
for rel,ref in m['files'].items():assert sha(f/rel)==ref['sha256'],rel
for name,ref in m['sources'].items():assert sha(ref['path'])==ref['sha256'],name
stock=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
wp=stock/(key+'.words.bin');cp=stock/(key+'.clut.bin');mp=stock/(key+'.source.json');meta=json.loads(mp.read_text())
assert meta['known_words']==meta['total_words'] and meta['depth']==0 and meta['width_words']==64 and meta['height']==256
ref=lambda p:{'path':str(p),'sha256':sha(p)}
native={'source_words':ref(wp),'source_clut':ref(cp),'source_shape_words':[64,256],'depth':0}
sys.path.insert(0,str(r/'remaster-audit'));from build_stage1_frozen_candidate import verified_native_source
verified_native_source(native,key)
words=np.frombuffer(wp.read_bytes(),dtype='<u2').reshape(256,64);indices=((words[:,:,None]>>(np.arange(4,dtype=np.uint16)*4))&15).reshape(256,256)
palette=np.frombuffer(cp.read_bytes(),dtype='<u2');pixels=palette[indices];expected=np.where(pixels==0,0,np.where(pixels&0x8000,255,127)).astype(np.uint8)
parent=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v3/candidate.json';old=json.loads(parent.read_text());row=next(x for x in old['files'] if x['name']==key+'.png')
assert row['sha256']==m['sources']['live_2048']['sha256'] and sha(row['composed_path'])==row['sha256']
arrays={}
for label,path in [('old',Path(row['composed_path'])),('candidate2048',f/'page2048'/(key+'.png')),('candidate4096',f/'page4096'/(key+'.png'))]:
 with Image.open(path) as im:
  assert im.mode=='RGBA';a=np.asarray(im);scale=im.width//256;assert im.size==(256*scale,256*scale)
  centre=a[scale//2::scale,scale//2::scale,3];mismatch=centre!=expected
  arrays[label]={'dimensions':list(im.size),'native_centres':65536,'class_mismatches':int(np.count_nonzero(mismatch)),
   'mismatch_class_pairs':{f'{int(x)}->{int(y)}':int(np.count_nonzero(mismatch&(centre==x)&(expected==y))) for x in [0,127,255] for y in [0,127,255] if np.any(mismatch&(centre==x)&(expected==y))},'sha256':sha(path)}
  if label=='old':old_rgba=a.copy()
  if label=='candidate2048':new_rgba=a.copy()
assert arrays['old']['class_mismatches']==3550
assert arrays['candidate2048']['class_mismatches']==0 and arrays['candidate4096']['class_mismatches']==0
changed_rgb=np.any(old_rgba[:,:,:3]!=new_rgba[:,:,:3],axis=2);outside=changed_rgb.copy();outside[64*8:112*8,128*8:192*8]=False
assert not np.any(outside),'RGB outside declared K rectangle changed'
entry={'manifest':ref(manifest),'key':key,'image':ref(f/'page2048'/(key+'.png')),'native_source':native,'source_handoff':ref(mp),
 'integration_variant':'page2048','selected_set':m['name'],'retained_limits':m['known_limits']}
plan={'parent':ref(parent),'entries':[entry],'scope':'Private K-panel revision plus native class repair; no GPU, game or visual acceptance. Other pack classes under independent audit.'}
(n/'k-panel-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':sha(manifest),'native_source':native,'checks':arrays,
 'changed_rgb_pixels_in_K':int(np.count_nonzero(changed_rgb)),'changed_rgb_pixels_outside_K':0,
 'native_class_fix_independently_confirmed':True,'gpu_work':False,'live_accepted':False,'scope':'Raw native-word/CLUT decode, class check, file pins and RGB-region ownership only.'}
(n/'k-panel-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
