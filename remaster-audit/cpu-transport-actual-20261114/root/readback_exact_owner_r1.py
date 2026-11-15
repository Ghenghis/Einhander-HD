"""Verify completed regression artifacts and three recorded identities without replay."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil, subprocess
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
A=N/'exact-owner-tests-2233'; E=N/'exact-owner-2233-envelope.json'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
def need(ok,why):
    if not ok: raise RuntimeError(why)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((A/'result.json').read_bytes()); e=json.loads(E.read_bytes())
need(m['passed'] and m['grant_id']=='msg_773798dcd18c4ef9','result outcome')
need(m['summary']==['# tests 12','# pass 12','# fail 0','# cancelled 0','# skipped 0'],'TAP counts')
need(m['exit']==0 and not m['timed_out'],'node exit')
need(sha(A/'test.tap')==m['tap_sha256']=='6aa2bb67a1a0a2090e19a74b25e14021ad3adf2c6ae109e06b29981e01ae00bc','TAP hash')
for k,row in m['copies'].items():
    need(sha(Path(row['original']))==sha(Path(row['copied']))==row['sha256'],'source/copy pin '+k)
need(sha(N/'run_exact_owner_continuity_r1.py')==m['driver_sha256'],'driver pin')
need(sha(N/'exact-owner-2233-runner/executed-watchdog.py')=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','watchdog pin')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'Job outcome')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate')
need(e['child_readback_before_resume']=={'cpu_affinity':[13],'priority':16384} and e['job_assigned_before_resume'],'pre-resume settings')
need(e['job_limits_readback']['affinity_mask']==8192 and e['job_limits_readback']['job_memory_limit']==268435456,'Job limits')
need(e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'empty Job/tree')
ids=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time']),('node',m['pid'],m['creation_unix'])]
known=[]
for label,pid,created in ids:
    try: absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess: absent=True
    need(absent,'known identity remains '+label)
    known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'exact-owner-actual-readback-r1'; out.mkdir(exist_ok=False)
for filename in ('claude-continuity-hook.mjs','test-claude-continuity.mjs'):
    cmd=['git','diff','--no-index','--numstat','--',str(Path('C:/github/Einhander-wt/display-history-opt-in/tools/coordination')/filename),str(R/'tools/coordination'/filename)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
    need(p.returncode==1,'expected narrow difference to publication baseline')
    (out/(filename+'.numstat.txt')).write_text(p.stdout,encoding='utf-8')
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,
    result_sha256=sha(A/'result.json'),envelope_sha256=sha(E),tap_sha256=sha(A/'test.tap'),
    tests=12,passed=12,failed=0,skipped=0,known_identities=known,
    elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],
    node_hash_at_execution=m['node'],node_binary_rehashed_by_readback=False,
    copied_scripts=m['copies'],test_replayed=False,gpu_used=False,game_launched=False,
    native_sessions_invoked=False,arbitrary_regex_supported=False,
    legacy_bare_owner_remains_ambiguous_in_hermes=True,future_producers_require_anchored_exact_owners=True)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(metadata_readback_pass=True,tests=12,known_identities_absent=3,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])))
