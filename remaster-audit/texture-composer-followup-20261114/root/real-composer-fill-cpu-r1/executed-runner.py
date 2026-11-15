"""Measure composer fill on an actual transparent Stage5 audit probe, without admitting its source."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,sys,time
import numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
sys.path.insert(0,str(r/'remaster-audit'));import build_stage1_frozen_candidate as composer
out=n/'real-composer-fill-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:]);start=time.monotonic()
report=r/'remaster-audit/parallel-stages-20261114/s45/probe-audit/20261114T141451Z-s5/result.json'
assert hashlib.sha256(report.read_bytes()).hexdigest()=='9e138d586edd945f9c340ba990717b72e2ab485f2e81d187fa4defbaf95bbf37'
row=json.loads(report.read_text())['rows'][0];src=Path(row['png']);assert hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
policy=json.loads((n/'composer-cutout-fill-cpu-r1/result.json').read_text())['policy'];fill=composer.load_cutout_rgb_fill(policy)
with Image.open(src) as image:
    a=np.array(image.convert('RGBA'));image,details=composer.apply_cutout_rgb_fill(image,fill[1]);b=np.array(image)
visible=a[:,:,3]!=0;adj=np.zeros(visible.shape,bool);adj[1:,:]|=visible[:-1,:];adj[:-1,:]|=visible[1:,:];adj[:,1:]|=visible[:,:-1];adj[:,:-1]|=visible[:,1:]
changed=np.any(a[:,:,:3]!=b[:,:,:3],axis=2)
before=int((~visible&adj&changed).sum());assert before==row['v2']['r5_fringe_px']==100550
again,_=composer.apply_cutout_rgb_fill(Image.fromarray(b),fill[1]);assert np.array_equal(np.array(again),b)
assert np.array_equal(a[:,:,3],b[:,:,3]) and np.array_equal(a[:,:,:3][visible],b[:,:,:3][visible])
dest=out/'filled-probe.png';Image.fromarray(b).save(dest)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,key=row['key'],source_png=str(src),source_sha256=row['sha256'],output_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),alpha_unchanged=True,visible_rgb_unchanged=True,details=details,r5_border_before=before,r5_border_after=0,fill_idempotent=True,source_admitted=False,gpu_run=False,stage_accepted=False,scope='Real audit-only predicted-palette probe; invisible RGB correction is measured, not live visual/source acceptance.',composer_source_sha256=hashlib.sha256((r/'remaster-audit/build_stage1_frozen_candidate.py').read_bytes()).hexdigest(),seconds=round(time.monotonic()-start,3),below_normal=True,cpu_affinity=me.cpu_affinity())
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(result))
