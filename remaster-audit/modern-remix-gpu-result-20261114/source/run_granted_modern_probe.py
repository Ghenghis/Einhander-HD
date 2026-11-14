"""Run the reviewed private probe only under a current fenced Einhander grant.

Live token is read locally into the child environment and never printed.
An outer observation deadline does not kill the cleanup-owning parent.
"""
from pathlib import Path
import datetime,gc,hashlib,json,os,psutil,subprocess,sys,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'modern-granted-execution-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
script=n/'run_modern_gl_probe.py';assert hashlib.sha256(script.read_bytes()).hexdigest()=='d545a7de7ef220e1c30eadb69eef3aa12f64db60861c40d56df485f4d36ea122'
state=json.loads((r/'.hermes3d_orchestrator/shared-gpu/state.json').read_text(encoding='utf-8-sig'))
grant=state.get('grant');assert isinstance(grant,dict) and grant['owner']=='claude-einhander' and grant.get('new_starts_allowed') is True
assert 'claude-einhander' not in state.get('denied',[])
if grant.get('expires_utc'):assert datetime.datetime.fromisoformat(grant['expires_utc'].replace('Z','+00:00'))>datetime.datetime.now(datetime.timezone.utc)
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3)
if cpu>=60 or free<16:
    receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cpu_percent=cpu,free_gib=free,declined_before_parent=True,gpu_run=False,requires_explicit_grant_release=True)
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));raise SystemExit(3)
assert all(not (r/'remaster-audit/comfy-authoring'/name).exists() for name in ['GPU-RESERVED','GPU-LOCK','CPU-QUIET'])
before={str(p) for p in n.glob('modern-gl-parent-*')}
env=dict(os.environ,EINHANDER_SHARED_GPU_TOKEN=grant['token'],OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
args=[sys.executable,'-X','utf8',str(script),'--run-after-explicit-user-release']
started=time.monotonic()
with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
    child=subprocess.Popen(args,cwd=r,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
    identity=psutil.Process(child.pid).create_time()
    start=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),managed_parent_pid=child.pid,creation_unix=identity,command=args,shared_revision=state['revision'],shared_owner=grant['owner'],affinity=me.cpu_affinity(),below_normal=True,precheck_cpu=cpu,free_gib=free,token_omitted=True)
    (out/'start.json').write_text(json.dumps(start,indent=2)+'\n',encoding='utf-8');print(json.dumps(start),flush=True)
    try:rc=child.wait(timeout=100)
    except subprocess.TimeoutExpired:
        receipt=dict(start=start,observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),parent_still_running=True,outer_observation_timed_out=True,grant_must_remain_held=True,parent_not_killed=True)
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));raise SystemExit(124)
pid=child.pid;del child;gc.collect()
absent=False;until=time.monotonic()+2
while time.monotonic()<until:
    try:
        current=psutil.Process(pid)
        if current.create_time()!=identity or not current.is_running():absent=True;break
    except psutil.NoSuchProcess:absent=True;break
    time.sleep(.025)
new=[p for p in n.glob('modern-gl-parent-*') if str(p) not in before];assert len(new)==1
resultfile=new[0]/'result.json';result=json.loads(resultfile.read_text(encoding='utf-8'))
receipt=dict(start=start,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=rc,seconds=time.monotonic()-started,managed_parent_identity_absent=absent,probe_result=str(resultfile),probe_result_sha256=hashlib.sha256(resultfile.read_bytes()).hexdigest(),probe_passed=result.get('passed'),gpu_executed=result.get('gpu_executed'),owned_child_gone=result.get('owned_process_gone'),owned_marker_released=result.get('owned_marker_released'),owned_lock_released=result.get('owned_lock_released'),broker_release_not_automatic=True)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
raise SystemExit(rc)
