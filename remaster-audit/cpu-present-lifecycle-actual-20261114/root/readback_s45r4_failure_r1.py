"""Read the real failed S45 fixture receipt; preserve the late-hold timeline."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent; S=R/'remaster-audit/parallel-stages-20261114/s45'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}
def pin(p,want):
    got=hashlib.sha256(p.read_bytes()).hexdigest(); assert got==want,(str(p),got); pins[str(p)]=got
def read(p,want): pin(p,want); return json.loads(p.read_bytes())
e=read(S/'runs/diagbands-r4-fixtures-envelope.json','0a5f1314a43e2ce031a75e74dec716c2c7fb12eb187ca3e8774d60d9b0d1c3a2')
d=S/'repairs/20261114T232856Z-diagbands-r4-fixtures'
a=read(d/'receipt.json','ef88b7e9bebc21fa36be18f659dd0d4f69a95f8b2786957704359d388900d1a3')
b=read(d/'fixtures-receipt.json','08e1afe65deb8bcb6d285fc55630388c6724c8e2db430836829e3f3dcc4d5d16')
assert e['rc']==e['child_exit_code']==e['wrapper_exit']==3 and not e['timeout_killed']
assert e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384} and e['job_assigned_before_resume']
assert e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16 and e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left']
assert not b['all_ok'] and len(b['cases'])==23 and sum(c['ok'] for c in b['cases'])==19
neg=[c for c in b['cases'] if c['expect_fail']]; pos=[c for c in b['cases'] if not c['expect_fail']]
assert len(neg)==15 and all(c['ok'] for c in neg) and len(pos)==8 and sum(not c['ok'] for c in pos)==4
assert a['status']=='FAILED' and a['reason']=='fixture mismatch'
pin(S/'tools/s45_diag_bands_r4.py',a['tool_sha256'])
for row in a['pins'].values(): assert row['ok']; pin(Path(row['path']),row['sha256'])
pin(S/'runs/diagbands-r4-fixtures-runner/executed-watchdog.py','fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36')
identities=[]
for role in ['wrapper','child']:
    pid=e[role+'_pid']; ct=e[role+'_create_time']
    try: gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess: gone=True
    assert gone; identities.append(dict(role=role,pid=pid,creation_unix=ct,identity_absent=True))
out=N/'s45r4-failure-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,actual_fixture_pass=False,exit=3,cases=23,cases_ok=19,positive_failed=4,negatives_ok=15,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],failed_cases=[dict(name=c['name'],message=c['msg']) for c in pos if not c['ok']],pins=pins,known_identities=identities,source_only_unrun_description_superseded=True,hold_arrived_after_actual_authorized_run=True,fixtures_replayed=False,key_repair_run=False,gpu_used=False,art_admitted=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in rec.items() if k not in ('pins','known_identities')}|dict(pins_verified=len(pins),known_identities_absent=len(identities))))
