from pathlib import Path
import datetime,json,os
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
release=json.loads((n/'user-release-20261114T1403/result.json').read_text())
monitor=json.loads((n/'monitor-renewal-20261114T140109Z/result.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(file,data):
    temp=file.with_name(file.name+'.codex-checkpoint.tmp')
    with temp.open('w',encoding='utf8',newline='\n') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,file)
rosterfile=r/'coordination/CLAUDE-SESSIONS-20261114.json';roster=json.loads(rosterfile.read_text())
roster['gpu_policy']='User explicitly released 3090 Ti in message01a1da5d-d9df-7000-95e5-44b85363c268; root verified actual human turn and archived old hold at14:03:44 UTC. Root alone coordinates one short GPU/live job after actual resource/source gates. Native workers remain CPU-only without individual grants. No driver/power settings changed.'
roster['updated_utc']=now;roster['monitoring_handoff'].update(watcher_pid=monitor['pid'],current_bound_end_utc=monitor['bound_end_utc'],renewal_receipt=str(n/'monitor-renewal-20261114T140109Z/result.json'))
atomic(rosterfile,json.dumps(roster,indent=2)+'\n')
text='''**Latest resource update:** the user explicitly released the RTX 3090 Ti in the other Einhander chat; root verified the actual human message and archived/removed the old hold at14:03:44 UTC. Reuse still requires root coordination, a quiet resource window and reviewed source. No new GPU test has started at this checkpoint; no power/driver setting was changed. Older reservation paragraphs below are historical and superseded. Native workers remain CPU-only without individual grants.

Published checkpoint `ee7824a4e4e869972045b914225cfdf1efab8fcc` is remote-verified in draft PR1:189 new packet pins,2,243 historical/new pins verified;55 documents,89 JSON reports,970 references,0 issues. Its immutable packet preserves failures. The later RISE float32 correction is local:33/33 class checks pass and approved reference is byte-identical; composition/live acceptance remains pending.

The owned metadata monitor was actually renewed: PID26032, first snapshot14:01:10 UTC, bound14:31:09.548 UTC; receipt `remaster-audit/runtime-review/gpu-texture-remix-20261114/monitor-renewal-20261114T140109Z/result.json`. It proves metadata monitoring only. Main continues actual inbox turns. The crash-check coordinator schedules bounded texture jobs; root retains v6/runtime/GPU/build/publication. Whole remaster remains incomplete.

'''
paths=['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md',*['docs/'+x for x in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]]
for rel in paths:
    file=r/rel;title,tail=file.read_text().split('\n',1);atomic(file,title+'\n\n## Resource release and actual monitor renewal — November 14\n\n'+text+tail.lstrip())
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statefile.read_text());state['updated_at_utc']=now;state['github_head']='ee7824a4e4e869972045b914225cfdf1efab8fcc';state['latest_resource_policy']=dict(user_3090_released=True,source_user_message=release['release']['source_user_message'],release_receipt='remaster-audit/runtime-review/gpu-texture-remix-20261114/user-release-20261114T1403/result.json',worker_gpu_grants=False,root_live_test_started=False,driver_settings_changed=False);state['actual_monitor']=dict(pid=monitor['pid'],bound_end_utc=monitor['bound_end_utc'],watcher_only=True,proves_model_activity=False);atomic(statefile,json.dumps(state,indent=2)+'\n')
print(json.dumps(dict(at_utc=now,paths=paths,roster=str(rosterfile),local_checkpoint=True,committed=False,pushed=False,gpu_started=False)))
