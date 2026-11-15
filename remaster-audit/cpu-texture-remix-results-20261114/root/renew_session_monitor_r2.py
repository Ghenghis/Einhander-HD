"""Renew a verified owned monitor or record its actual bounded expiry/absence."""
from pathlib import Path
import datetime as dt,json,os,psutil,shutil,subprocess,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
health=r/'.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json'
prior=json.loads(health.read_bytes());pid=prior['watcher_pid']
assert prior['watcher_only'] and not prior['proves_model_activity']
end=dt.datetime.fromisoformat(prior['bound_end_utc'].replace('Z','+00:00'))
start=end-dt.timedelta(seconds=1800)
out=n/('monitor-renewal-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=False)
(out/'prior-health.json').write_text(json.dumps(prior,indent=2)+'\n',encoding='utf-8')
receipt=dict(prior_pid=pid,prior_bound_end_utc=prior['bound_end_utc'],prior_terminated=False,
    prior_identity_absent=False,prior_expired=dt.datetime.now(dt.timezone.utc)>=end)
try:
    old=psutil.Process(pid);command=old.cmdline();created=old.create_time()
    expected=(old.name().lower()=='node.exe' and any('session-health.mjs' in x for x in command)
        and '--watch' in command and '1800' in command and abs(created-start.timestamp())<5)
    if not expected:raise RuntimeError('Existing PID does not match the original monitor identity; left untouched')
    receipt.update(prior_command=command,prior_creation_unix=created)
    assert old.create_time()==created and old.cmdline()==command
    old.terminate();old.wait(timeout=5);receipt['prior_terminated']=True
except psutil.NoSuchProcess:receipt['prior_identity_absent']=True
args=['node',str(r/'coordination/claude-session-briefs-20261114/session-health.mjs'),'--watch','1800']
with (out/'stdout.jsonl').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
    child=subprocess.Popen(args,cwd=r,stdout=stdout,stderr=stderr,creationflags=0x08004000)
created=psutil.Process(child.pid).create_time();deadline=time.monotonic()+10
while time.monotonic()<deadline:
    assert child.poll() is None,'Replacement metadata monitor exited'
    fresh=json.loads(health.read_bytes())
    if fresh.get('watcher_pid')==child.pid:break
    time.sleep(.1)
else:raise TimeoutError('No observed first snapshot for replacement monitor')
assert fresh['watcher_only'] and not fresh['proves_model_activity']
receipt.update(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),pid=child.pid,creation_unix=created,
    command=args,bound_end_utc=fresh['bound_end_utc'],first_snapshot_utc=fresh['observed_utc'],
    first_snapshot=fresh,watcher_only=True,proves_model_activity=False,gpu_run=False,
    uninterrupted_monitoring_claimed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');shutil.copyfile(__file__,out/'executed-runner.py')
print(json.dumps({k:v for k,v in receipt.items() if k!='first_snapshot'}))
