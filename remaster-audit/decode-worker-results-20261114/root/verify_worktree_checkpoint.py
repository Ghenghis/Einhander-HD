from pathlib import Path
import datetime,hashlib,json,psutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;out=n/'worktree-checkpoint-cpu-r1';out.mkdir(exist_ok=False)
p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.cpu_affinity([11])
files=[r/'tools/coordination'/f for f in ['claude-continuity-hook.mjs','claude-checkpoint.mjs','test-claude-continuity.mjs','test-claude-checkpoint.mjs']]
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
before={str(f):sha(f) for f in files}
run=subprocess.run(['node','--test','--test-reporter=tap',str(files[2]),str(files[3])],cwd=r,capture_output=True,timeout=20)
(out/'stdout.log').write_bytes(run.stdout);(out/'stderr.log').write_bytes(run.stderr)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit=run.returncode,passed=run.returncode==0,source_pins=before,affinity=p.cpu_affinity(),below_normal=True,gpu_run=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
assert before=={str(f):sha(f) for f in files}
assert run.returncode==0,(run.stdout[-3000:],run.stderr[-1000:]);print(json.dumps(receipt))
