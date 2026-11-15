"""Verify actual T1 failure artifacts without compiling or running any fixture."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
P=R/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/t1'
A=P/'runs/t1-r1-2157/20261114T215837Z';E=P/'runs/t1-r1-2157-envelope.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
need(sha(E)=='95e94d693846a114d6816a4295f8253a5d3a8a797225843245b8994281b13247','envelope changed')
need(sha(A/'result.json')=='9c62483b670f48619ec22d1c0044f3fd2f9e8bc3e07032165e501f0f03e2ca3d','result changed')
e=json.loads(E.read_bytes());m=json.loads((A/'result.json').read_bytes())
need(m['passed'] is False and len(m['steps'])==2,'not the original compile failure')
extract,compile_step=m['steps'];need(extract['label']=='extract' and extract['passed'],'extraction failed')
need(compile_step['label']=='compile' and compile_step['exit']==1 and not compile_step['timed_out'],'compile outcome changed')
need("'/*' within block comment" in (A/'compile.log').read_text(encoding='utf-8'),'observed diagnostic changed')
need(not (A/'test-t1.exe').exists(),'unexpected executable')
pins=[]
for name,entry in m['inputs'].items():
    path=Path(entry['path']);need(path.resolve().is_relative_to(R.resolve()),'outside project')
    need(sha(path)==entry['sha256'],'input changed '+name);pins.append(dict(path=str(path.relative_to(R)),sha256=sha(path)))
for name,want in m['executed_copies'].items():
    need(sha(A/name)==want,'executed copy changed '+name)
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==1 and not e['timeout_killed'],'envelope outcome changed')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[13],'priority':16384},'child readback')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==8192,'Job readback')
need(e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'cleanup receipt')
identities=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time']),
    ('compiler',compile_step['pid'],compile_step['creation_unix'])]
known=[]
for label,pid,created in identities:
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known identity remains');known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'t1-compile-failure-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,
    original_fixture_pass=False,compile_exit=1,checks_executed=0,expected_unrun_checks=36,
    envelope_sha256=sha(E),result_sha256=sha(A/'result.json'),compile_log_sha256=sha(A/'compile.log'),
    source_pins=pins,executed_copy_pins=m['executed_copies'],known_identities=known,
    elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],fixture_replayed=False,
    extracted_division_repeated=False,game_run=False,gpu_run=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_pins','executed_copy_pins','known_identities')}))
