"""Sequential CPU-only preparation under the user's GPU reservation."""
from pathlib import Path
import datetime,json,subprocess,sys,os,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
assert json.loads(hold)['owner']=='user-external-project'
env=os.environ.copy()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:env[k]='1'
plan=n/'world-remaining-plan-v1.json';out=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v2'
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_work':False,'below_normal':True,'sequential':True,'commands':[]}
steps=[('classes',[sys.executable,'-X','utf8',str(n/'check_world_patch_classes.py'),'--plan',str(plan),'--output',str(n/'world-remaining-class-check.json')]),
 ('composition',[sys.executable,'-X','utf8',str(r/'remaster-audit/build_stage1_frozen_candidate.py'),'--plan',str(plan),'--output',str(out)])]
for phase,args in steps:
 with (n/('world-remaining-'+phase+'.log')).open('w') as log:
  p=subprocess.run(args,cwd=r,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=0x4000)
 receipt['commands'].append({'phase':phase,'args':args,'exit':p.returncode})
 assert p.returncode==0,phase
assert marker.read_bytes()==hold
receipt.update(ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_gpu_hold_unchanged=True,candidate=str(out/'candidate.json'))
(n/'world-remaining-composition-execution.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
