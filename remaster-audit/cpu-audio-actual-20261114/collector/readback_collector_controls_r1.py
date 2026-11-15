"""Independent post-exit receipt/identity readback, never a test rerun."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

N=Path(__file__).resolve().parent;run=N/'collector-controls-run-r1'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
out=N/'collector-controls-independent-readback-r1';out.mkdir(exist_ok=False)
def need(ok,why):
    if not ok:raise RuntimeError(why)
def read(name):return json.loads((run/name).read_bytes())
launcher=read('launcher.json');envelope=read('envelope.json');controls=read('controls/result.json')
need(launcher['passed'] is False and launcher['wrapper_exit']==0 and launcher['wrapper_identity_absent'] is False,
     'Original failed-launcher evidence changed')
identities=[]
for role,pid,created in [('wrapper',envelope['wrapper_pid'],envelope['wrapper_create_time']),
                         ('child',envelope['child_pid'],envelope['child_create_time'])]:
    try:absent=abs(psutil.Process(pid).create_time()-created)>=.001
    except psutil.NoSuchProcess:absent=True
    identities.append(dict(role=role,pid=pid,creation_unix=created,identity_absent=absent))
need(all(row['identity_absent'] for row in identities),'Known executed process still present')
pins={
 'executed-launcher.py':'949d4f9736f481484a833886a129081c44c6ab86090906af4fae6553a5135e5c',
 'executed-watchdog.py':'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',
 'executed-controls.py':'f8b517c11cb32f0d3b2cfcee3ba51ebbf6cb2f5c13498cc2d9caff8bc223a907'}
hashes={}
for name,want in pins.items():
    got=hashlib.sha256((run/name).read_bytes()).hexdigest();need(got==want,'Executed source changed '+name)
    hashes[name]=got
for name in ('launcher.json','envelope.json','controls/result.json','stdout.log','stderr.log'):
    hashes[name]=hashlib.sha256((run/name).read_bytes()).hexdigest()
for row in launcher['source_pins']:
    need(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],'Original source changed')
need(envelope['child_exit_code']==0 and envelope['wrapper_exit']==0 and envelope['tree_absent'] is True
     and envelope['job']['active']==0 and envelope['job_limits_readback']['job_memory_limit']==128*2**20
     and envelope['job_limits_readback']['limit_flags']&0x200
     and envelope['child_readback_before_resume']==dict(cpu_affinity=[11],priority=16384), 'Envelope check failed')
need(envelope['precheck']['system_cpu_pct']<60 and envelope['precheck']['free_gib']>=16,'Resource gate failed')
need(controls['all_ok'] is True and controls['case_count']==controls['expected_cases']==len(controls['cases'])==74
     and all(row['ok'] is True for row in controls['cases']) and 'fatal' not in controls,'Fixture check failed')
need(controls['controls_sha256']==pins['executed-controls.py'] and controls['cpu']==11
     and controls['allowed_affinity']==[11],'Fixture provenance failed')
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_passed=True,
    original_launcher_passed=False,original_launcher_failure='wrapper_identity_absent=false while retained handle exited',
    original_receipt_rewritten=False,synthetic_controls_passed=True,controls_count=74,
    controls_elapsed_s=controls['elapsed_s'],envelope_elapsed_s=envelope['elapsed_s'],
    peak_job_memory_bytes=envelope['peak_job_memory_bytes'],job_memory_limit_bytes=128*2**20,
    known_process_identities=identities,source_and_receipt_hashes=hashes,source_pins=launcher['source_pins'],
    resource_precheck=envelope['precheck'],tests_rerun=False,proposal_imported=False,gpu_run=False,
    game_run=False,real_socket_tested=False,live_qualified=False,installed=False,
    limitation='Readback validates synthetic fixture and later cleanup, not the original launcher verdict or real OS/game adapter integration')
(out/'result.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
(out/'executed-reader.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_and_receipt_hashes','source_pins')}))
