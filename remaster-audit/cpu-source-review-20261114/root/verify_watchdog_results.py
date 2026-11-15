"""Independent small-receipt/source/PID-identity verification; no child test execution."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
S=R/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/watchdog'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
pins=[];identities=[]
def require(ok,why):
    if not ok:raise RuntimeError(why)
def read(path,expected=None):
    raw=Path(path).read_bytes();h=hashlib.sha256(raw).hexdigest()
    require(expected is None or expected==h,'pin changed '+str(path))
    pins.append(dict(path=str(path),sha256=h,bytes=len(raw)));return raw
def absent(pid,ctime):
    try:alive=psutil.pid_exists(pid) and psutil.Process(pid).create_time()==ctime
    except psutil.NoSuchProcess:alive=False
    identities.append(dict(pid=pid,creation_unix=ctime,same_identity_alive=alive))
    require(not alive,'owned test identity still active')
read(S/'run_rc2_envelope_r1.py','fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36')
read(S/'selftest_envelope_r2.py','aff35f825624dfd00b29923b235ecd620c6a56a8771a2f32a6187416e435b2d8')
read(S/'TEST-PLAN-r1.md','9b2420b934ae4260b02f81008d5ab65f03799869a8f6cccbf03216d80bddc6a0')
read(S/'TEST-PLAN-r2.md','6039654d449001827b66acea668dc0978f8ee18dff9ffd8ebf08e582a1f9d44e')
outcome=json.loads(read(S/'run-20261114T192518Z/result.json','a727da4e28ce8b5ee1e4d4ac1fed901c24d65563a9b273ea8ff41be2f9e98ad1'))
launch=json.loads(read(S/'run-20261114T192518Z.launcher.json','75f3773db91bd71059500bd462bb8e231ab8b249a978d0752f86e650e5de05c3'))
require(outcome['all_ok'] and outcome['case_count_exact'] and len(outcome['cases'])==10,'case counts')
require(launch['harness']['exit']==0 and launch['harness']['priority']==16384,'harness exit/priority')
require(launch['gate']['cpu_percent']<60 and launch['gate']['free_gib']>=16,'host gates')
require(outcome['sentinel']['untouched_by_cases'] and outcome['sentinel']['absent_after'],'sentinel flags')
absent(launch['harness']['pid'],launch['harness']['create_time'])
absent(outcome['sentinel']['pid'],outcome['sentinel']['create_time'])
counts=[]
for row in outcome['cases']:
    require(row['ok'] and not row.get('incomplete') and not row.get('receipt_error') and not row.get('finally_cleanup'),'case incomplete '+row['case'])
    absent(row['wrapper_pid'],row['wrapper_create_time'])
    path=S/'run-20261114T192518Z'/row['case']/'receipt.json'
    if row['case'].startswith('T7'):
        require(row['wrapper_rc']==2 and not path.exists(),'usage child created receipt')
        continue
    rc=json.loads(read(path));require(rc['tree_absent'] and rc['job_empty'] and rc['child_absent'],'case cleanup')
    absent(rc['child_pid'],rc['child_create_time'])
    counts.append(dict(case=row['case'],child_exit=rc['child_exit_code'],wrapper_exit=rc['wrapper_exit'],tree_absent=True))
    require(row['wrapper_rc']==rc['wrapper_exit'],'exit disagreement')
base=S/'run-20261114T192518Z'
normal=json.loads((base/'T5b_affinity_original/receipt.json').read_bytes())
require(normal['child_affinity_set_to']==normal['allowed_before_pin']==normal['child_readback_before_resume']['cpu_affinity']==list(range(16)),'normal affinity')
memory=json.loads((base/'T6_hard_memory_cap/receipt.json').read_bytes())
require(memory['job_limits_readback']['job_memory_limit']==67108864 and memory['child_exit_code']==3,'memory refusal')
require((base/'T6_hard_memory_cap/memerror.txt').is_file() and not (base/'T6_hard_memory_cap/after_alloc.txt').exists(),'memory markers')
out=N/'watchdog-independent-readback-r1';out.mkdir(exist_ok=False)
data=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=True,cases=10,
    sources_and_receipts=pins,identities_checked=identities,case_exits=counts,
    reported_elapsed_s=outcome['elapsed_s'],before_affinity=normal['child_affinity_before_set'],
    normal_affinity_verified=list(range(16)),memory_cap_bytes=67108864,
    refused_commit_peak_reported_only=memory['peak_job_memory_bytes'],
    sentinel_untouched_and_absent=True,root_reexecuted_tests=False,
    launcher_identity_independently_replayed=False,game_run=False,gpu_run=False,live_qualified=False)
(out/'result.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in data.items() if k not in ('sources_and_receipts','identities_checked','case_exits')}))
