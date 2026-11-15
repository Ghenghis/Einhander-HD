"""Refresh dated own-session proof without editing a worker's checkpoint."""
from pathlib import Path
import datetime,hashlib,json,os,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'six-session-roster-refresh-r1';out.mkdir(exist_ok=False)
file=r/'coordination/CLAUDE-SESSIONS-20261114.json';original=file.read_bytes();roster=json.loads(original)
(out/'prior-roster.json').write_bytes(original)
sha=lambda b:hashlib.sha256(b).hexdigest();now=datetime.datetime.now(datetime.timezone.utc).isoformat();proofs=[]
assert len(roster['sessions'])==6
for row in roster['sessions']:
    owner=row['owner'];cli=row['cli_session_id']
    activity=r/'.hermes3d_orchestrator/continuity'/('activity-'+sha(cli.encode())[:16]+'.json')
    ab=activity.read_bytes();a=json.loads(ab)
    assert a['owner']==owner and a['session_id']==cli,(owner,'activity identity mismatch')
    checkpoint=r/row['checkpoint'];cb=checkpoint.read_bytes();c=json.loads(cb)
    assert c.get('owner',owner)==owner,(owner,'checkpoint owner mismatch')
    if c.get('session_id'):assert c['session_id'].removeprefix('local_') in [cli,row['session_id']]
    # Historical own-inbox proof remains attributed to the model messages, not this reader.
    row['state']='actual_own_hook_checkpoint_verified_at_dated_snapshot'
    row['live_hook_verified_utc']=now
    row['checkpoint_sha256']=sha(cb);row['checkpoint_verified_utc']=now
    row['latest_metadata_proof']=dict(observed_utc=now,activity_path=activity.relative_to(r).as_posix(),activity_sha256=sha(ab),event=a.get('event'),activity_observed_utc=a.get('observed_utc'),checkpoint_utc=c.get('checkpoint_utc'),checkpoint_phase=c.get('phase'),proves_current_model_work=False)
    (out/(owner+'-activity.json')).write_bytes(ab);(out/(owner+'-checkpoint.json')).write_bytes(cb)
    proofs.append(dict(owner=owner,activity_sha256=sha(ab),checkpoint_sha256=sha(cb),phase=c.get('phase'),model_liveness_not_inferred=True))
    if owner=='claude-einhander-s45':
        row['scope']='Stage4/5 source, shared panorama, 8bpp boss regions and strict audits. Menu/HUD transferred to claude-einhander-ui at16:24Z.'
    if owner=='claude-einhander-ui':row['task_ids']=['EIN-MENU-HUD-20261114']
health=json.loads((r/'.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json').read_text())
assert health['watcher_pid']==37252 and psutil.pid_exists(37252)
roster['actual_monitor']=dict(pid=37252,bound_end_utc=health['bound_end_utc'],verified_utc=now,watcher_only=True,proves_model_activity=False)
roster['gpu_policy']='Modern private3090Ti probe actually ran16:33UTC and FAILED blank geometry/Shutdown deadline. Owned processes absent, nonce markers removed and explicit shared release16:35:17 revision10. Root CPU-only diagnosis; future GPU starts require current fenced grant/resource gate, never elapsed-time takeover.'
roster['rationale']='Six registered native Claude sessions with distinct Stage1/shared-runtime, S2/3, S4/5, S6/7, HUD/UI and verification support ownership. At most two heavy CPU jobs globally, BelowNormal/single CPU, main owns GPU/integration/publication.'
roster['updated_utc']=now;roster['snapshot_limitation']='Dated own-hook/checkpoint metadata and historical model work/inbox evidence do not prove a current active model turn, automatic wake or uninterrupted future availability.'
data=(json.dumps(roster,indent=2)+'\n').encode()
assert file.read_bytes()==original,'Roster changed during preparation'
temp=file.with_name(file.name+'.root-refresh.new')
with temp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
temp.replace(file)
receipt=dict(at_utc=now,prior_sha256=sha(original),new_sha256=sha(data),rows=proofs,worker_checkpoints_edited=False,actual_monitor=roster['actual_monitor'],gpu_run=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
