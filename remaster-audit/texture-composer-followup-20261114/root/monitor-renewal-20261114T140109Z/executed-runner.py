"""Replace only the verified owned bounded metadata monitor, without model claims."""
from pathlib import Path
import datetime,json,os,psutil,shutil,subprocess,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
health=r/'.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json'
prior=json.loads(health.read_text()); old=psutil.Process(prior['watcher_pid'])
command=old.cmdline(); created=old.create_time()
assert old.name().lower()=='node.exe' and any('session-health.mjs' in x for x in command) and '--watch' in command and '1800' in command,command
assert prior['watcher_only'] and not prior['proves_model_activity']
out=n/('monitor-renewal-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=False)
(out/'prior-health.json').write_text(json.dumps(prior,indent=2)+'\n')
assert old.create_time()==created and old.cmdline()==command
old.terminate(); old.wait(timeout=5)
args=['node',str(r/'coordination/claude-session-briefs-20261114/session-health.mjs'),'--watch','1800']
with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
    child=subprocess.Popen(args,cwd=r,stdout=stdout,stderr=stderr,creationflags=0x08004000)
deadline=time.monotonic()+10
while time.monotonic()<deadline:
    assert child.poll() is None,'New metadata monitor exited before ready'
    fresh=json.loads(health.read_text())
    if fresh.get('watcher_pid')==child.pid:break
    time.sleep(.1)
else:raise RuntimeError('Replacement monitor has no observed first health snapshot; inspect owned PID/logs')
assert fresh['watcher_only'] and not fresh['proves_model_activity']
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),prior_pid=prior['watcher_pid'],prior_command=command,prior_creation_unix=created,prior_terminated=True,pid=child.pid,command=args,bound_end_utc=fresh['bound_end_utc'],first_snapshot_utc=fresh['observed_utc'],first_snapshot=fresh,watcher_only=True,proves_model_activity=False,model_resumption=False,gpu_run=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py')
print(json.dumps({k:v for k,v in receipt.items() if k!='first_snapshot'}))
