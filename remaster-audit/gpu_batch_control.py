"""Suspend/resume only this task's verified checkpointed UltraSharp worker."""
import argparse,json,time,os
from pathlib import Path
import psutil
parser=argparse.ArgumentParser();parser.add_argument('action',choices=['pause','resume','status']);args=parser.parse_args()
root=Path('C:/github/REMASTER_STAGING/full-remaster/world-machines')
progress=json.loads((root/'progress.json').read_text())
try:process=psutil.Process(progress['pid'])
except psutil.NoSuchProcess:
 if args.action!='status':raise RuntimeError('Worker exited; restart run_full_remaster.py --profile world-machines --output-name world-machines to resume checkpoints')
 print(json.dumps({'running':False,'progress':progress,'complete':json.loads((root/'complete.json').read_text()) if (root/'complete.json').exists() else None}));raise SystemExit(0)
command=process.cmdline()
if len(command)<2 or Path(command[1]).name!='run_full_remaster.py' or process.cwd().lower()!='c:\\github\\einhander' or '--profile' not in command or 'world-machines' not in command:
 raise RuntimeError('PID does not match the owned restoration worker')
path=root/'control.json';state=json.loads(path.read_text()) if path.exists() else {}
same=state.get('pid')==process.pid and state.get('created')==process.create_time()
paused=same and state.get('paused',False)
if args.action=='pause' and not paused:process.suspend();paused=True
if args.action=='resume' and paused:process.resume();paused=False
state={'pid':process.pid,'created':process.create_time(),'paused':paused,'updated':time.time(),'purpose':'GPU-isolated playback measurements; resume restoration after testing'}
temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(state,indent=2)+'\n');os.replace(temporary,path)
print(json.dumps(state))
