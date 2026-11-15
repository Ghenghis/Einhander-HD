"""Capture complete moving-image controls with actual CPU confinement and raw stdout."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess,time
n=Path(__file__).resolve().parent;out=n/'modern-r4-controls-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=me.cpu_affinity();me.cpu_affinity([11 if 11 in allowed else allowed[0]])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
args=['python','-B',str(n/'test_modern_gl_image.py')];t=time.monotonic()
x=subprocess.run(args,cwd=n,capture_output=True,text=True,timeout=15,creationflags=0x4000)
(out/'stdout.json').write_text(x.stdout);(out/'stderr.log').write_text(x.stderr)
assert x.returncode==0,(x.stdout,x.stderr);control=json.loads(x.stdout);assert control['passed'] and control['cpu_cases']==12 and not control['real_gpu_images_audited']
parent=json.loads((n/'modern-parent-cleanup-cpu-r2/result.json').read_text());assert parent['passed'] and parent['cpu_cases']==7 and parent['source_sha256']==sha(n/'run_modern_gl_probe.py')
for file in ['sdk_modern_gl_probe.cpp','run_modern_gl_probe.py','audit_modern_gl_image.py','test_modern_gl_image.py','test_modern_parent_cleanup.py']:shutil.copy2(n/file,out/file)
shutil.copy2(n/'modern-parent-cleanup-cpu-r2/result.json',out/'cleanup-result.json');shutil.copy2(__file__,out/'executed-runner.py')
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,command=args,exit=x.returncode,seconds=round(time.monotonic()-t,3),image_controls=12,cleanup_controls=7,below_normal=True,cpu_affinity=me.cpu_affinity(),pins={f:sha(out/f) for f in ['sdk_modern_gl_probe.cpp','run_modern_gl_probe.py','audit_modern_gl_image.py','test_modern_gl_image.py','test_modern_parent_cleanup.py']},prior_observation=dict(tool_chunk='8b1852',exit=0,cases=12,full_stdout_not_retained=True,resource_confinement_not_established=True),repeat_reason='Retain complete raw output and establish measured affinity/priority for the evidence packet.',gpu_run=False,actual_gpu_images_audited=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
