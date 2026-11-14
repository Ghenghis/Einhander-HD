"""Check the actual PR7 CPU build/contracts. Does not load the executable or replay tests."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
P=R/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-probe-r5'
A=P/'runs/PR7-1-2200/20261114T220309Z';E=P/'runs/PR7-1-2200-envelope.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads(E.read_bytes());m=json.loads((A/'result.json').read_bytes())
pins=[(P/'build_r7_cpu.r1.py','b0e08a6a71b7cab97e3deab5860aaa017bbe7d2d8ff3dcf90c1b424ab924f69e'),
    (P/'sdk_modern_gl_probe.r7.cpp','751d3231690d172590232dfbaf20710a9bdeac1b514f4d780bd7893be312fc05'),
    (A/'executed-source.cpp','751d3231690d172590232dfbaf20710a9bdeac1b514f4d780bd7893be312fc05'),
    (N/'sdk-release-header/remix_c.h','e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c'),
    (P/'runs/PR7-1-2200-runner/executed-watchdog.py','fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36')]
for p,w in pins:need(sha(p)==w,'source changed '+str(p))
need(m['passed'] is True and m['gpu_executed'] is False and m['dll_loaded'] is False,'overall result')
need([s['label'] for s in m['steps']]==['syntax','compile-object','link','cpu-contract','guard-contract'],'step list')
need(all(s['passed'] is True and not s['timed_out'] for s in m['steps']),'step failed')
need([s['exit'] for s in m['steps']]==[0,0,0,0,77],'step exits')
need(m['steps'][3]['contract']==dict(cpu_contract_checks=65,passed=True,revision='r7',dll_loaded=False,gl_context=False),'CPU contract')
need(m['steps'][4]['guard']==dict(reservation_exists=False,owned_execution_lease=False,gpu_started=False,dll_loaded=False),'guard contract')
need(sha(A/'sdk-modern-gl-r7.exe')==m['exe_sha256']=='eb28476c13d3d5cb07a9444de9c36c5b405e83790c5670ae000c6bbdf5c8435e','executable changed')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'envelope failed')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'gate failed')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[13],'priority':16384},'child readback')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==8192,'Job readback')
need(e['job']['active']==0 and e['tree_absent'] and e['child_absent'] and not e['descendants_left'],'cleanup receipt')
known=[]
for label,pid,created in [('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]:
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known owned identity remains');known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'pr7-build-success-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,
    actual_build_and_cpu_contract_pass=True,envelope_sha256=sha(E),result_sha256=sha(A/'result.json'),
    object_sha256=sha(A/'probe.obj'),executable_sha256=m['exe_sha256'],cpu_checks_passed=65,guard_exit=77,
    inputs=[dict(path=p.relative_to(R).as_posix(),sha256=w) for p,w in pins],known_identities=known,
    elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],compiled_source='original pinned path, not archived copy',
    subchild_creation_times='not recorded by original builder; no fabricated values',toolchain_rehashed_by_readback=False,
    fixture_replayed=False,gpu_run=False,game_run=False,dll_loaded=False,gl_context_created=False,
    rendered_image_accepted=False,installed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('inputs','known_identities')}))
