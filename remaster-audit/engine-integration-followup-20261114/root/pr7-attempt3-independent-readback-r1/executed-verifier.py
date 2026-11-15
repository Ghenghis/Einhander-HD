"""Independent small receipt/source/identity readback. Does not run probe or compiler."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

root=Path('C:/github/Einhander');notes=Path(__file__).resolve().parent
primary=root/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary'
runs=primary/'remix-probe-r5/runs'
name='PR7-1-20261114T202434Z';build=runs/name/'20261114T202436Z'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
pins=[]
def need(ok,message):
    if not ok:raise RuntimeError(message)
def read(path,expected=None):
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    need(expected is None or digest==expected,'pin changed: '+str(path))
    pins.append(dict(path=str(path),sha256=digest,bytes=len(raw)));return raw
for path,pin in [
    (primary/'tools/run_rc2.r1.py','cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'),
    (primary/'remix-probe-r5/build_r7_cpu.py','a9475b3c0f7e4c59f637fbcab23f690c63393aa91bccf9c14210289aaebf1b4c'),
    (primary/'remix-probe-r5/sdk_modern_gl_probe.r7.cpp','751d3231690d172590232dfbaf20710a9bdeac1b514f4d780bd7893be312fc05'),
    (notes/'sdk-release-header/remix_c.h','e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c')]:read(path,pin)
wrapper=json.loads(read(runs/(name+'-rc.json')))
result=json.loads(read(build/'result.json'))
need(wrapper['start_utc']<'2026-11-14T20:25:00','late launch')
need(wrapper['precheck']['system_cpu_pct']==50.1 and wrapper['precheck']['free_gib']==57.36,'unexpected launch gate')
need(wrapper['cpu']==15 and wrapper['affinity']==[15] and wrapper['priority']==16384,'wrapper controls')
need(wrapper['wrapper_exit']==wrapper['child_exit_code']==1 and not wrapper['timeout_killed'],'not expected terminal failure')
need(wrapper['job']['active']==0 and wrapper['tree_absent'] and wrapper['child_absent'] and not wrapper['descendants_left'],'tree cleanup')
need(not result['passed'] and not result['gpu_executed'] and not result['dll_loaded'] and result['exe_sha256'] is None,'scope changed')
need([row['label'] for row in result['steps']]==['syntax','compile-object'],'later step unexpectedly ran')
syntax,compile_step=result['steps']
need(syntax['passed'] and syntax['exit']==0 and compile_step['exit']==1 and not compile_step['passed'],'step verdicts')
need('unable to open output file' in compile_step['output'] and 'No such file or directory' in compile_step['output'],'unexpected compile failure')
identities=[]
for pid,created in [(wrapper['wrapper_pid'],wrapper['wrapper_create_time']),
                    (wrapper['child_pid'],wrapper['child_create_time'])]:
    try:alive=psutil.pid_exists(pid) and psutil.Process(pid).create_time()==created
    except psutil.NoSuchProcess:alive=False
    need(not alive,'owned identity remains alive')
    identities.append(dict(pid=pid,creation_unix=created,same_identity_alive=alive))
artifacts={name:(build/name).exists() for name in ('probe.obj','sdk-modern-gl-r7.exe')}
need(not any(artifacts.values()),'unexpected artifact exists')
out=notes/'pr7-attempt3-independent-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),readback_passed=True,build_passed=False,
    sources_and_receipts=pins,known_identities_checked=identities,
    compile_child_creation_independently_verified=False,reported_job_active=0,
    source_syntax_passed=True,syntax_seconds=syntax['seconds'],object_compile_passed=False,
    failure='relative output path resolved again under child cwd=out; file could not be opened',
    wrapper_elapsed_s=wrapper['elapsed_s'],wrapper_exit=1,hard_job_memory_cap=False,
    hard_memory_scope='approved cd3988af wrapper has no hard Job memory cap',artifacts=artifacts,
    cpu_controls_executed=False,guard77_executed=False,link_executed=False,
    compiler_reexecuted=False,gpu_run=False,game_run=False,dll_loaded=False,live_qualified=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
(out/'executed-verifier.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({key:value for key,value in receipt.items() if key!='sources_and_receipts'}))
