"""Consume coordinator light exception1a6d0e8c exactly once, no retry."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import psutil
import subprocess
import sys
import time

root=Path('C:/github/Einhander');notes=Path(__file__).resolve().parent
guard=root/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/watchdog/run_rc2_envelope_r1.py'
expected={guard:'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',
    root/'remaster-audit/gl_adapter_identity_guard.py':'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08',
    root/'remaster-audit/test_gl_adapter_identity_guard.py':'18977886193c7dd1bdeedb12bc7df30215e21765ec4c775ef7c75df1dda00503'}
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
out=notes/'adapter-controls-run-r1';out.mkdir(exist_ok=False)
pins=[]
for path,pin in expected.items():
    raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
    if actual!=pin:raise RuntimeError('source pin changed: '+str(path))
    pins.append(dict(path=str(path),sha256=actual))
child=notes/'adapter_controls_child.py';pins.append(dict(path=str(child),sha256=hashlib.sha256(child.read_bytes()).hexdigest()))
command=[sys.executable,'-I','-B',str(guard),'--out',str(out/'envelope.json'),'--cpu','11',
         '--timeout','10','--max-job-mib','128','--no-window','--',sys.executable,'-I','-B',str(child),str(out/'result.json')]
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),grant_message='msg_1a6d0e8c46fb8bc5',
    source_pins=pins,command=command,attempt=1,retries=0,heavy_job=False,gpu_run=False,game_run=False)
start=time.perf_counter()
with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
    process=subprocess.Popen(command,cwd=root,stdout=stdout,stderr=stderr,creationflags=0x08004000)
    receipt.update(wrapper_pid=process.pid,wrapper_creation_unix=psutil.Process(process.pid).create_time())
    try:receipt['wrapper_exit']=process.wait(timeout=25)
    except subprocess.TimeoutExpired:
        receipt['outer_timeout']=True;process.kill();receipt['wrapper_exit']=process.wait(timeout=3)
receipt['outer_elapsed_s']=time.perf_counter()-start
try:receipt['wrapper_absent']=not psutil.pid_exists(process.pid) or psutil.Process(process.pid).create_time()!=receipt['wrapper_creation_unix']
except psutil.NoSuchProcess:receipt['wrapper_absent']=True
for name in ('envelope.json','result.json'):
    path=out/name
    if path.exists():receipt[name]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),data=json.loads(path.read_bytes()))
receipt['passed']=(receipt['wrapper_exit']==0 and receipt['wrapper_absent']
    and receipt.get('envelope.json',{}).get('data',{}).get('tree_absent') is True
    and receipt.get('result.json',{}).get('data',{}).get('passed') is True)
with (out/'launcher.json').open('x',encoding='utf-8') as file:json.dump(receipt,file,indent=2);file.write('\n');file.flush();os.fsync(file.fileno())
(out/'executed-launcher.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(dict(passed=receipt['passed'],wrapper_pid=process.pid,wrapper_exit=receipt['wrapper_exit'],
    wrapper_absent=receipt['wrapper_absent'],elapsed_s=receipt['outer_elapsed_s'],
    result=receipt.get('result.json'),envelope=receipt.get('envelope.json'))))
sys.exit(0 if receipt['passed'] else 1)
