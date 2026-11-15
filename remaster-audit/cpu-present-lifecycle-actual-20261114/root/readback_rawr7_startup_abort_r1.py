"""Verify actual game startup and controlled transport abort; no gameplay acceptance or replay."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
Q=R/'coordination/pizza-review-20261114/raw37c-live-20261114T233521Z'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; identities=[]
def pin(p,want=None,prefix=None):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); assert want is None or h==want; assert prefix is None or h.startswith(prefix); pins[str(p)]=h; return h
def read(p,want=None,prefix=None): pin(p,want,prefix); return json.loads(p.read_bytes())
e=read(Q/'envelope.json'); a=read(Q/'evidence/raw37c-evidence.json',prefix='07e5310c')
assert e['rc']==e['wrapper_exit']==e['child_exit_code']==1 and not e['timeout_killed']
assert e['child_readback_before_resume']==dict(cpu_affinity=list(range(16)),priority=32) and e['job_assigned_before_resume']
assert e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left']
assert a['verdict']=='ABORTED' and a['abort']=='AdapterEvidenceError: connected debug TCP peer missing or ambiguous'
s=a['steps']['S0']; c=a['cleanup_holder']; reg=a['fence']['game_registration']
assert s['exe_sha256']=='37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc' and s['nice']==32 and s['cpu_affinity']==list(range(16))
assert c['owned_pid']==s['pid']==reg['registered_pid'] and c['owned_identity']==[s['pid'],s['create_time']] and reg['registered_create_time']==s['create_time']
assert c['identity_absent'] is True and c['tree_absent'] is False and reg['committed'] is True
assert a['cleanup_holder_facts']['retained_handle_exited'] and a['cleanup_holder_facts']['popen_aliases_released']
assert not any(k.startswith('G') for k in a['steps'])
for role,pid,ct in [('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time']),('game',s['pid'],s['create_time'])]:
    try: gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess: gone=True
    assert gone; identities.append(dict(role=role,pid=pid,creation_unix=ct,identity_absent=True))
for name,want in a['logs'].items(): pin(Q/'evidence'/name,want)
command_paths=sorted((Q/'evidence/commands').glob('*.json'))
intents=[]
for p in command_paths:
    obj=read(p)
    if p.name.endswith('-intent.json'): intents.append(obj['request']['cmd'])
assert intents==['skin_material']
driver=R/'remaster-audit/parallel-stages-20261114/s67/proposals/raw37c-diagnostic/raw37c_driver_r7.py'; pin(driver,'4dbc93d901f32a25f4a63c5d2a04d0c1c3f4295ceae6a4afc5c6e5e0ba428230')
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,actual_game_started=True,actual_menu_audio_acceptance=False,verdict='ABORTED',elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],game_identity=dict(pid=s['pid'],creation_unix=s['create_time'],exe_sha256=s['exe_sha256'],priority=32,affinity=list(range(16))),listener_seconds_cold_cache=s['listener_seconds_cold_cache'],first_command='skin_material',peer_failure_phase='not persisted; pre-send versus post-reply cannot be determined',menu_gates_completed=0,audio_stats_recorded=False,exact_identity_broker_holder_join=True,holder_identity_absent=True,outer_job_empty=True,whole_cleanup_join_pass=True,private_settings_after=a['settings_sha256_after'],pins=pins,known_identities=identities,game_replayed_by_root=False,gpu_or_driver_settings_changed_by_root=False,release_scope='coordinator reports explicit broker release; private token files not read by root')
out=N/'rawr7-startup-abort-actual-readback-r1'; out.mkdir(exist_ok=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in rec.items() if k not in ('pins','known_identities')}|dict(pins_verified=len(pins),known_identities_absent=len(identities))))
