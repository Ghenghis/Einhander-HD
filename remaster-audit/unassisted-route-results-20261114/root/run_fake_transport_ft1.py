from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
source=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/fake-transport/fake_transport_default_path.r0.py'
pins={source:'6c147a284db6f209f48139cc2341c99e26a1f5035cf198f54b275f8da84a08a6',
    r/'remaster-audit/run_stage1_unassisted_review.py':'c47b10929c318280b471cc60dc84a89f3b8fe4db59f325e7630dee482d1939a5',
    r/'remaster-audit/unassisted_command_guard.py':'9e6ca8159a2f471fcbbde996464a6ba2eb6a51846c44567eefdb6e5cceaa2240',
    n/'region-o-roi-composition-r1/run_rc2.py':'cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'}
for p,h in pins.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h,str(p)
out=n/'fake-transport-ft1-r1';out.mkdir(exist_ok=False);shutil.copy2(source,out/source.name)
args=[sys.executable,'-B','-I',str(n/'region-o-roi-composition-r1/run_rc2.py'),
    '--out',str(out/'rc.json'),'--cpu','15','--timeout','90','--max-cpu','60','--min-free-gib','16','--',
    sys.executable,'-B',str(out/source.name),'--out-root',str(out/'runs'),
    '--expect-runner-sha',pins[r/'remaster-audit/run_stage1_unassisted_review.py'],
    '--expect-guard-sha',pins[r/'remaster-audit/unassisted_command_guard.py']]
with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
    run=subprocess.run(args,cwd=r,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),
        stdout=stdout,stderr=stderr,creationflags=0x08004000,timeout=100)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=run.returncode,
    command=args,pins={str(p):h for p,h in pins.items()},guard_receipt=json.loads((out/'rc.json').read_bytes()),
    gpu_run=False,game_run=False,simulated_transport=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
raise SystemExit(run.returncode)
