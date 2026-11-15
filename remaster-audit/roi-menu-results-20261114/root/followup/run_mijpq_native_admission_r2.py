"""Run the pinned CPU native pack verifier under the same bounded grant."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
cpu=int(sys.argv[1]);grant=datetime.datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'))
remaining=180-(datetime.datetime.now(datetime.timezone.utc)-grant).total_seconds()
assert cpu in (13,15) and remaining>1
cap=min(45,int(remaining));out=n/'mijpq-native-admission-r1';out.mkdir(exist_ok=False)
exe=r/'remaster-audit/claude-backlog/sign-washout-audit/verifier-build/verify_native.exe'
assert hashlib.sha256(exe.read_bytes()).hexdigest()=='859fc54e92a8397170f3fb4c6f959c8d49e5d205b8b3fe6bda7c9fed997bfd7b'
guard=n/'region-o-roi-composition-r1/run_rc2.py'
assert hashlib.sha256(guard.read_bytes()).hexdigest()=='cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'
pack=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-mijpq-roi-r1/pack'
assert (pack.parent/'candidate.json').is_file()
args=[sys.executable,'-B','-I',str(guard),'--out',str(out/'rc.json'),'--cpu',str(cpu),'--timeout',str(cap),'--max-cpu','60','--min-free-gib','16','--',str(exe),str(pack),'1699']
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:run=subprocess.run(args,cwd=r,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=run.returncode,command=args,guard_receipt=json.loads((out/'rc.json').read_text()),gpu_run=False,game_run=False,live_accepted=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(run.returncode)
