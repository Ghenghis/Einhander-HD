"""Root independent CPU replay of the corrected source/draw proposal."""
from pathlib import Path
import datetime, hashlib, json, os, psutil, shutil, subprocess, time
r=Path('C:/github/Einhander'); n=Path(__file__).resolve().parent
p=r/'remaster-audit/runtime-review/session-continuation-20261114'
out=n/'source-draw-guard-review-r1'; out.mkdir(exist_ok=False)
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity(me.cpu_affinity()[-1:])
assert not psutil.pid_exists(28744), 'S67 CPU worker must exit first'
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED'; hold=marker.read_bytes()
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
receipt=p/'receipt-2026-11-14T13-55-45-243Z.json'
author=json.loads(receipt.read_text())
for row in author['files']:
    assert sha(r/row['path'])==row['sha256'], row['path']
    if Path(row['path']).suffix in ('.py','.mjs','.json','.jsonl','.md'):
        dest=out/'snapshot'/row['path']; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(r/row['path'],dest)
shutil.copy2(receipt,out/'author-receipt.json'); shutil.copy2(__file__,out/'executed-runner.py')
args=['python','-B',str(p/'test_source_draw_admission.py')]; start=time.monotonic()
x=subprocess.run(args,cwd=r,capture_output=True,text=True,timeout=15,creationflags=0x4000)
(out/'tests.log').write_text(x.stdout+x.stderr)
assert x.returncode==0 and 'Ran 13 tests' in x.stderr and '\nOK\n' in x.stderr, x.stdout+x.stderr
assert marker.read_bytes()==hold
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,command=args,exit=x.returncode,seconds=round(time.monotonic()-start,3),tests=13,source_sha256=sha(p/'source_draw_admission.py'),author_receipt_sha256=sha(receipt),cpu_affinity=me.cpu_affinity(),below_normal=True,gpu_executed=False,user_hold_unchanged=True,real_key_admitted=False,scope='Independent replay of synthetic source/draw controls including pinned actual-recorder row schema; not live stage identity, visibility or art acceptance.')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result))
