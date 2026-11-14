from pathlib import Path
import datetime,hashlib,json,os,subprocess,time,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
hold=r/'remaster-audit/comfy-authoring/GPU-RESERVED';before=hold.read_bytes()
assert json.loads(before)['owner']=='user-external-project'
p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.cpu_affinity([p.cpu_affinity()[-1]])
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_work':False,'game_executed':False,'one_logical_cpu':p.cpu_affinity(),'below_normal':True,'commands':[]}
out=e/'world-integrated-crisp-v4'
commands=[['python','-X','utf8',str(r/'remaster-audit/build_stage1_frozen_candidate.py'),'--plan',str(n/'k-panel-plan.json'),'--output',str(out)],
 [str(r/'remaster-audit/claude-backlog/sign-washout-audit/verifier-build/verify_native.exe'),str(out/'pack'),'1699']]
for i,args in enumerate(commands):
 start=time.monotonic();q=subprocess.run(args,cwd=r,capture_output=True,text=True,encoding='utf-8',env=env,timeout=300,creationflags=0x4000)
 log=n/f'k-panel-compose-{i}.log';log.write_text(q.stdout+q.stderr,encoding='utf-8')
 receipt['commands'].append({'args':args,'exit':q.returncode,'seconds':round(time.monotonic()-start,3),'log':log.name})
 print(json.dumps(receipt['commands'][-1]),flush=True)
 assert q.returncode==0,q.stderr
assert hold.read_bytes()==before
d=json.loads((out/'candidate.json').read_bytes());assert d['final_count']==1699
row=next(x for x in d['files'] if x['name']=='95A3BCF8-723E222C.png')
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
receipt.update(candidate_sha256=sha(out/'candidate.json'),key=row['name'],composed_png_sha256=row['sha256'],input_png_sha256=row['input']['image']['sha256'],parent_retained=True,user_gpu_hold_unchanged=True,production_installed=False,live_visual_accepted=False)
(n/'k-panel-composition-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='commands'}))
