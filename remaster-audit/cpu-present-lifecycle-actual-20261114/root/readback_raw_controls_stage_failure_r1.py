"""Check actual61 pure controls and the separate import-before-prepare staging failure."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent; S=R/'remaster-audit/parallel-stages-20261114/s67'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; identities=[]; runs={}
def pin(p,want):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); assert h==want,(str(p),h,want); pins[str(p)]=h
def read(p,want): pin(p,want); return json.loads(p.read_bytes())
for label,stem,rc,sha in [('controls61','raw37c-controls-r4-2322',0,'baf6012191e9cf3c71273aa3101a665a4ac28d80bc3cfc995b8cd9a72575f034'),('stage-import-failure','raw37c-stage-r3-2323',1,'420e7740883fe40d53314ef04bba98336933b3547d7d8ceb86050c0a49e11c8c')]:
    p=S/'runs'/(stem+'-envelope.json'); e=read(p,sha)
    assert e['rc']==e['wrapper_exit']==e['child_exit_code']==rc and not e['timeout_killed']
    assert e['child_readback_before_resume']=={'cpu_affinity':[14],'priority':16384} and e['job_assigned_before_resume']
    assert e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16 and e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left']
    for role in ['wrapper','child']:
        pid=e[role+'_pid']; ct=e[role+'_create_time']
        try: gone=psutil.Process(pid).create_time()!=ct
        except psutil.NoSuchProcess: gone=True
        assert gone; identities.append(dict(run=label,role=role,pid=pid,creation_unix=ct,identity_absent=True))
    runs[label]=dict(envelope_sha256=sha,exit=rc,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
p=S/'runs/raw37c-controls-r4-2322.log'; pin(p,'7afd98983386c5b93323751dca75ac21eb56aa7b1092ef4306a9ce209d5c191c')
line=json.loads(p.read_text().splitlines()[-1]); assert line==dict(checks=61,failures=[],result='PASS')
pin(S/'proposals/raw37c-diagnostic/test_raw37c_driver_r4.py','4cb682814039ba2e3f19a6e061f0c8d1398016ec44c7ac869a3f57f247325262')
pin(S/'proposals/raw37c-diagnostic/raw37c_driver_r3.py','9ee0b4fe149971a74ccb5aa525b2842112d5c9f78e9dc655aa6a9a6203324c7a')
p=S/'runs/raw37c-stage-r3-2323.log'; pin(p,'e57d4f45f001f063842b1f9d8f9b3388eadfb5bbe75e8077078ff88d88ab5960')
assert 'ModuleNotFoundError' in p.read_text() and 'build_facade_ab_candidates' in p.read_text()
batch=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112/raw37c-r3-20261114T2323Z'; assert not batch.exists()
runs['controls61'].update(checks=61,failures=0,pure_doubles_only=True)
runs['stage-import-failure'].update(successful=False,failed_before_prepare=True,batch_absent_at_readback=True,cause='isolated import search path missing canonical facade module',gpu_used=False)
out=N/'raw-controls-stage-failure-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=identities,tests_replayed=False,game_launched=False,gpu_used=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(metadata_readback_pass=True,runs=runs,pins_verified=len(pins),known_identities_absent=len(identities))))
