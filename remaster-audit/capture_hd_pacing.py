"""Check normal-use HD pacing without per-primitive receipt logging."""
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from stage1_session import ROOT,command,screenshot

confirmed=json.loads((ROOT/'evidence/gameplay-confirmed.json').read_text())
if hashlib.sha256((ROOT/'captures'/confirmed['capture_name']).read_bytes()).hexdigest()!=confirmed['capture_sha256']:
    raise RuntimeError('Gameplay confirmation changed')
if (ROOT/'evidence/draws.jsonl').exists():
    raise RuntimeError('Use a fresh session without receipt logging')
stop=threading.Event()
errors=[]
def assist():
    try:
        while not stop.is_set():
            command('write_ram',addr='0x80085718',val='0xA5')
            command('write_ram',addr='0x800813C4',val='0x03')
            stop.wait(.2)
    except Exception as error:
        errors.append(repr(error));stop.set()
worker=threading.Thread(target=assist)
started=time.monotonic()
command('set_input',buttons='0x3FFF')
worker.start()
try:
    for offset in (20,65,110):
        remaining=started+offset-time.monotonic()
        if remaining>0 and stop.wait(remaining):break
        if errors:raise RuntimeError(errors)
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('measure_runtime.py')),
            '--seconds','10','--name',f'delivery-2x-{offset}'],capture_output=True,text=True,timeout=25)
        print(result.stdout,flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
        print(screenshot(f'pacing-{offset+10}'),flush=True)
finally:
    stop.set();worker.join(timeout=10);command('clear_input')
if errors:raise RuntimeError(errors)
(ROOT/'evidence/pacing-run.json').write_text(json.dumps({'seconds':time.monotonic()-started,
    'proof_logging':False,'assists':'Stationary Cross+Square, isolated lives/invulnerability writes every 200ms',
    'measurement_offsets':[20,65,110],'errors':errors},indent=2)+'\n')
