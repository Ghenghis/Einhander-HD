"""New private RISE composition with independent native-alpha and parent checks."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess,time,zlib
import numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector/expand33/20261114T135902Z'
manifest=source/'result.json';assert sha(manifest)=='d4379b41b64bbeff1e38fb965a93a5880f677e3779b716859f60ba8fce1326ec'
data=json.loads(manifest.read_text());assert data['summary']['palettes']==33 and data['summary']['reference_palette_identical_to_approved_v5']
parent=e/'world-integrated-crisp-v4/candidate.json';pd=json.loads(parent.read_text());pack=Path(pd['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT'])
entries=[];input_checks=[]
for row in data['rows']:
    key=row['key'];png=source/'palettes'/row['png'];assert sha(png)==row['sha256']
    words=pack/(key+'.words.bin');clut=pack/(key+'.clut.bin');wb=words.read_bytes();cb=clut.read_bytes()
    assert len(wb)==1024 and len(cb)==32 and f'{zlib.crc32(wb):08X}-{zlib.crc32(cb):08X}'==key
    raw=np.frombuffer(wb,dtype='<u2').reshape(32,16);indices=((raw[:,:,None]>>np.array([0,4,8,12],dtype=np.uint16))&15).reshape(32,64)
    cw=np.frombuffer(cb,dtype='<u2');classes=np.where(cw==0,0,np.where((cw&0x8000)!=0,255,127)).astype(np.uint8)[indices]
    with Image.open(png) as im:
        rgba=np.asarray(im.convert('RGBA'));assert im.size==(1024,512)
        assert np.array_equal(rgba[:,:,3],np.repeat(np.repeat(classes,16,axis=0),16,axis=1)),key
    entries.append(dict(manifest=dict(path=str(manifest),sha256=sha(manifest)),key=key,image=dict(path=str(png),sha256=sha(png)),native_source=dict(source_words=dict(path=str(words),sha256=sha(words)),source_clut=dict(path=str(clut),sha256=sha(clut)),source_shape_words=[16,32],depth=0),integration_variant='native-faithful-rise-f32-1024x512',retained_limits=['New private palette expansion; in-game cycle order/appearance not accepted.','Native categorical alpha exactly equals native words and CLUT at every HD pixel.','Existing exact-upload region registration retained from parent.']))
    input_checks.append(dict(key=key,source_png_sha256=sha(png),native_alpha_all_pixels_equal=True,words_crc_and_clut_crc_match=True))
prototype=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector/expand33/20261114T135902Z'
fill_policy=dict(method='cm_fill_cutout_rgb-v2b',**{label:dict(path=str(prototype/file),sha256=sha(prototype/file)) for label,file in [('library','class_mip.dll'),('source','class_mip.c'),('header','class_mip.h'),('build_receipt','result.json')]})
plan=n/'rise-f32-plan.json';plan.write_text(json.dumps(dict(parent=dict(path=str(parent),sha256=sha(parent)),entries=entries,cutout_rgb_fill=fill_policy,scope='Private new composition only; no installation or live acceptance.'),indent=2)+'\n')
out=e/'world-integrated-rise-f32-r1';assert not out.exists();started=time.monotonic();rows=[]
commands=[('compose',['python','-X','utf8',str(r/'remaster-audit/build_stage1_frozen_candidate.py'),'--plan',str(plan),'--output',str(out)],120),('native-admission',[str(r/'remaster-audit/claude-backlog/sign-washout-audit/verifier-build/verify_native.exe'),str(out/'pack'),'1699'],45)]
for label,args,cap in commands:
    t=time.monotonic();x=subprocess.run(args,cwd=r,env=env,capture_output=True,text=True,encoding='utf8',timeout=cap,creationflags=0x4000)
    (n/('rise-f32-'+label+'.log')).write_text(x.stdout+x.stderr);rows.append(dict(label=label,command=args,exit=x.returncode,seconds=round(time.monotonic()-t,3)));print(json.dumps(rows[-1]),flush=True);assert x.returncode==0,x.stdout+x.stderr
new=json.loads((out/'candidate.json').read_text());assert new['final_count']==1699 and new['authored_entries']==33
lookup={row['name']:row for row in new['files']};replaced={row['key']+'.png' for row in entries}
for row in pd['files']:
    assert sha(row['composed_path'])==row['sha256'],'Parent changed'
    now=lookup[row['name']];assert sha(now['composed_path'])==now['sha256']
    if row['name'] not in replaced:assert now['sha256']==row['sha256'],'Unrelated texture changed'
    else:
        src=next(x['image']['path'] for x in entries if x['key']+'.png'==row['name'])
        with Image.open(src) as a,Image.open(now['composed_path']) as b:assert np.array_equal(np.asarray(a.convert('RGBA')),np.asarray(b.convert('RGBA')))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=rows,seconds=round(time.monotonic()-started,3),candidate=str(out/'candidate.json'),candidate_sha256=sha(out/'candidate.json'),parent_sha256=sha(parent),new_entries=33,all_other_parent_images_unchanged=1666,source_png_pixels_equal=True,all_33_native_alpha_exact=True,input_checks=input_checks,final_count=1699,production_installed=False,live_visual_accepted=False,gpu_executed=False,below_normal=True,cpu_affinity=me.cpu_affinity(),scope='Native admission and composition; old unrelated class/RGB defects are retained and this is not whole-world or gameplay acceptance.')
(n/'rise-f32-composition-result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-compose.py');print(json.dumps({k:v for k,v in receipt.items() if k not in ('commands','input_checks')}))
