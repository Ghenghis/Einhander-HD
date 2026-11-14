from pathlib import Path
import datetime,hashlib,json,psutil,re,shutil,subprocess,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;out=n/'session-interop-cpu-review-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest();marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
receiptpath=r/'coordination/claude-session-briefs-20261114/verified-2026-11-14T13-45-49-189Z/verification.json';author=json.loads(receiptpath.read_text())
files=['tools/coordination/claude-continuity-hook.mjs','tools/coordination/claude-checkpoint.mjs','tools/coordination/test-claude-continuity.mjs','tools/coordination/test-claude-checkpoint.mjs']
for rel in files:
    assert sha(r/rel)==author['files'][rel],rel
    dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(r/rel,dest)
shutil.copy2(receiptpath,out/'author-verification.json');shutil.copy2(__file__,out/'executed-runner.py')
rows=[]
for label,args,cwd in [('hook-tests',['node','--test','--test-reporter=tap','--test-concurrency=1',*files[2:]],r),('image-oracle-controls',['python','-X','utf8',str(n/'test_modern_gl_image.py')],n)]:
    start=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.monotonic();x=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=30,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr);rows.append(dict(label=label,args=args,cwd=str(cwd),started_utc=start,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=round(time.monotonic()-tick,3),exit=x.returncode));assert x.returncode==0,(label,x.stdout,x.stderr)
    if label=='hook-tests':assert re.search(r'^# pass 18$',x.stdout,re.M) and re.search(r'^# fail 0$',x.stdout,re.M)
    else:obj=json.loads(x.stdout);assert obj['cpu_cases']==8 and obj['passed'] and not obj['real_gpu_images_audited'];(out/'image-oracle-controls.json').write_text(json.dumps(obj,indent=2)+'\n')
assert marker.read_bytes()==hold
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,commands=rows,hook_tests=18,image_oracle_cases=8,author_receipt_sha256=sha(receiptpath),source_pins={rel:sha(r/rel) for rel in files},image_oracle_source_sha256=sha(n/'audit_modern_gl_image.py'),image_oracle_test_sha256=sha(n/'test_modern_gl_image.py'),cpu_affinity=me.cpu_affinity(),below_normal=True,gpu_executed=False,user_hold_unchanged=True,live_gpu_images_audited=False,actual_native_workers='Three additional workers actual startup/own hooks/first source artifacts verified by author; component tests do not prove future liveness or stage acceptance.')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
