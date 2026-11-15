"""Own and release a single light private game test; preserve all evidence."""
from pathlib import Path
import datetime,json,subprocess,sys,psutil
root=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
marker=root/'remaster-audit/comfy-authoring/GPU-RESERVED'
directory=root/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-live-r1/hd-on_rewind-on'
assert not marker.exists(),'GPU reservation already exists'
assert not (directory/'launch-candidate.json').exists(),'Fresh run required'
reservation={'owner':'codex-einhander-recovery','task':'EIN-C-ONLY-STUTTER-AUDIO-20261113','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'scope':'One private 120s world integration flypast; 5 sparse stills; no video/source collector. Light Claude CPU work allowed; not performance acceptance.'}
with marker.open('x') as f:json.dump(reservation,f)
(n/'world-live-reservation.json').write_text(json.dumps(reservation,indent=2)+'\n')
args=[sys.executable,'-X','utf8','-u',str(n/'run_world_live_review.py'),'--batch','world-integrated-live-r1','--rewind','1','--run-prepared']
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'args':args}
with (directory/'world-runner.log').open('w',encoding='utf-8') as log:
    p=subprocess.Popen(args,cwd=root,stdout=log,stderr=subprocess.STDOUT,creationflags=0x4000)
    print(json.dumps({'runner_pid':p.pid,'log':str(directory/'world-runner.log')}),flush=True)
    try:receipt['exit']=p.wait(timeout=270)
    except subprocess.TimeoutExpired:
        (directory/'STOP').write_text('bounded runner timeout\n')
        receipt['timeout']=True
        receipt['exit']=p.wait(timeout=45)
proof_path=directory/'world-flypast-proof.json'
proof=json.loads(proof_path.read_text()) if proof_path.exists() else {}
launch_path=directory/'launch-candidate.json';launch=json.loads(launch_path.read_text()) if launch_path.exists() else {}
pid=launch.get('pid');gone=bool(pid) and not psutil.pid_exists(pid)
receipt.update(ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),game_pid=pid,pid_gone=gone,
 port_closed=proof.get('close',{}).get('port_closed',False),errors=proof.get('errors'),owned_process_exit=proof.get('owned_process_exit'))
if gone and receipt['port_closed']:
    assert json.loads(marker.read_text())==reservation
    marker.unlink();receipt['reservation_released']=True
else:receipt['reservation_released']=False
(n/'world-live-execution.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
raise SystemExit(0 if receipt['exit']==0 and receipt['reservation_released'] and receipt['errors']==[] else 1)
