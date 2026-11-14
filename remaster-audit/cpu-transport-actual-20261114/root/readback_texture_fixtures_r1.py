"""Verify completed stripe/settings fixture receipts only, without image processing or reruns."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent;S=R/'remaster-audit/parallel-stages-20261114'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
known=[];runs={}
for label,ep,cpu in [('stripe',S/'s45/runs/diagbands-r3-fixtures-envelope.json',13),('settings',S/'s23/runs/stselftest-2246-envelope.json',12)]:
    e=json.loads(ep.read_bytes());need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'fixture envelope')
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate')
    need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[cpu],'priority':16384},'child settings')
    need(e['job_limits_readback']['affinity_mask']==1<<cpu and e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'Job/tree')
    for k,pid,ct in [('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]:
        try:absent=psutil.Process(pid).create_time()!=ct
        except psutil.NoSuchProcess:absent=True
        need(absent,'known identity remains');known.append(dict(run=label,label=k,pid=pid,creation_unix=ct,identity_absent=True))
    runs[label]=dict(envelope_sha256=sha(ep),elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
a=S/'s45/repairs/20261114T223836Z-diagbands-r3-fixtures'
m=json.loads((a/'receipt.json').read_bytes());f=json.loads((a/'fixtures-receipt.json').read_bytes())
need(f['all_ok'] and len(f['cases'])==16 and all(r['ok'] for r in f['cases']),'stripe cases')
need(m['status']=='FIXTURES OK' and m['mode']=='fixtures','stripe scope')
need(sha(S/'s45/tools/s45_diag_bands_r3.py')==m['tool_sha256']=='76adfdc710077299c3c044826ed78f908d904a3fed0bcbfe9949477acd46a381','stripe source')
for row in m['pins'].values():need(row['ok'] and sha(Path(row['path']))==row['sha256'],'stripe input pin')
runs['stripe'].update(cases=16,result_sha256=sha(a/'receipt.json'),fixtures_sha256=sha(a/'fixtures-receipt.json'),art_admitted=False,key_repairs_run=False)
b=S/'s23/runs/stager-selftest-2246/SELFTEST.json';st=json.loads(b.read_bytes());test=st['selftest']
need(st['ok'] and st['exit_code']==0 and test['passed'] and len(test)==8 and all(test.values()),'settings conditions')
need(sha(S/'s23/tools/pilot_stage_onekey_r1.py')==st['self_sha256']=='0b4e0c16c0d8b58605023c4941175acbc42b3d9f05096a227fd4f9190098d540','settings source')
runs['settings'].update(conditions=7,result_sha256=sha(b),cache_qualified=False,pilot_staged=False)
for p in [S/'s45/runs/diagbands-r3-fixtures-runner/executed-watchdog.py',S/'s23/runs/stselftest-2246-runner/executed-watchdog.py']:
    need(sha(p)=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','copied watchdog')
out=N/'texture-fixture-actual-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,known_identities=known,
    fixtures_replayed=False,image_processing_run=False,game_launched=False,gpu_used=False,art_admitted=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(metadata_readback_pass=True,runs=runs,known_identities_absent=len(known))))
