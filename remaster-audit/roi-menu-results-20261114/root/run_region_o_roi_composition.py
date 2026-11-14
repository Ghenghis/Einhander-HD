"""Run only after a current coordinator CPU grant, via the pinned Job Object guard."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
cpu=int(sys.argv[1]);grant_utc=datetime.datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'))
assert cpu in (13,15) and 0<=(datetime.datetime.now(datetime.timezone.utc)-grant_utc).total_seconds()<180
out=n/'region-o-roi-composition-r1';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
composer=r/'remaster-audit/build_stage1_frozen_candidate.py';plan=n/'region-o-roi-plan-r1.json'
guard=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/tools/run_rc2.py'
assert sha(composer)=='c8c3cca561ef01a662b5ae8c43fe79e3830b4550136b7e8ef7dda677bc0df699'
assert sha(plan)=='07b02f6ef9fa155ac82c4404c3f908653f88de9766ee6e839b8646454c9ce62d'
assert sha(guard)=='cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'
for f in [composer,plan,guard]:(out/f.name).write_bytes(f.read_bytes())
args=[sys.executable,'-B','-I',str(guard),'--out',str(out/'rc.json'),'--cpu',str(cpu),'--timeout','120','--max-cpu','60','--min-free-gib','16','--',sys.executable,'-B','-I',str(composer),'--plan',str(plan),'--output',str(r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-o-roi-r1')]
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
start=time.monotonic()
with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
    run=subprocess.run(args,cwd=r,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
receipt=json.loads((out/'rc.json').read_text())
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=args,outer_exit=run.returncode,elapsed_s=time.monotonic()-start,guard_receipt=receipt,gpu_run=False,game_run=False,installed=False,source_unchanged=sha(composer)=='c8c3cca561ef01a662b5ae8c43fe79e3830b4550136b7e8ef7dda677bc0df699')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(run.returncode)
