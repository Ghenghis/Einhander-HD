"""Correct the unpublished packet, replay bounded broker controls, stage owned paths."""
from pathlib import Path
import datetime, hashlib, json, os, re, shutil, subprocess
import psutil
assert __import__('sys').flags.utf8_mode, 'Run with python -X utf8 to preserve existing UTF-8 documents.'

r = Path('C:/github/Einhander')
w = Path('C:/github/Einhander-wt/display-history-opt-in')
n = Path(__file__).resolve().parent
name = 'texture-composer-followup-20261114'
p = w / 'remaster-audit' / name
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([11])
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
def legacy_utf8(file):
    text=Path(file).read_bytes().decode('utf-8',errors='surrogateescape')
    text=''.join(bytes([ord(c)-0xdc00]).decode('cp1252') if 0xdc80<=ord(c)<=0xdcff else c for c in text)
    return re.sub(r'\r+\n','\n',text).replace('\r','\n')
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=w, text=True).strip() == 'ee7824a4e4e869972045b914225cfdf1efab8fcc'
mapping = json.loads((p / 'SOURCE-MAP.json').read_text())

def snapshot(src, dest):
    src = Path(src)
    dest = p / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    assert b'\0' not in data
    if src.suffix == '.json':
        json.loads(data)
    with dest.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    relative = dest.relative_to(p).as_posix()
    mapping['sources'] = [x for x in mapping['sources'] if x['published'] != relative]
    mapping['sources'].append(dict(source=str(src), published=relative, bytes=len(data), sha256=sha(dest), captured_utc=now()))

out = n / 'shared-broker-cpu-r2'
out.mkdir(exist_ok=True)
broker = r / 'tools/coordination/shared-gpu.mjs'
tests = r / 'tools/coordination/test-shared-gpu.mjs'
pins = {str(f): sha(f) for f in [broker, tests]}
if (out/'result.json').exists():
    receipt=json.loads((out/'result.json').read_text())
    assert receipt['passed'] and receipt['source_sha256']==pins
    assert receipt['stdout_sha256']==sha(out/'stdout.log') and receipt['stderr_sha256']==sha(out/'stderr.log')
else:
    started = now()
    run = subprocess.run(['node', '--test', '--test-reporter=tap', str(tests)], cwd=r, capture_output=True, timeout=20)
    (out / 'stdout.log').write_bytes(run.stdout)
    (out / 'stderr.log').write_bytes(run.stderr)
    assert run.returncode == 0 and b'# pass 8' in run.stdout
    assert pins == {str(f): sha(f) for f in [broker, tests]}
    receipt = dict(started_utc=started, ended_utc=now(), returncode=run.returncode, tests=8, passed=True,
                   pid=me.pid, affinity=me.cpu_affinity(), priority='BELOW_NORMAL', source_sha256=pins,
                   scope='CPU-only isolated state/mutex/outbox controls. No actual GPU grant/start, graphics or live state mutation.',
                   stdout_sha256=sha(out/'stdout.log'), stderr_sha256=sha(out/'stderr.log'))
    (out/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
for f in sorted(out.iterdir()):
    snapshot(f, 'root/shared-broker-cpu-r2/'+f.name)
for f in sorted((n/'shared-broker-cpu-r1').iterdir()):
    snapshot(f,'root/shared-broker-cpu-r1/'+f.name)
for f in [broker, tests, r/'tools/coordination/shared_gpu_guard.py']:
    snapshot(f, 'root/'+f.name)
    shutil.copy2(f, w/f.relative_to(r))

monitor = json.loads((n/'monitor-renewal-20261114T145329Z/result.json').read_text())
assert monitor['pid'] == 31968
rosterfile = r/'coordination/CLAUDE-SESSIONS-20261114.json'
roster = json.loads(rosterfile.read_text())
roster['updated_utc'] = now()
roster['monitoring_handoff'].update(watcher_pid=monitor['pid'],current_bound_end_utc=monitor['bound_end_utc'],
    renewal_receipt='remaster-audit/runtime-review/gpu-texture-remix-20261114/monitor-renewal-20261114T145329Z/result.json')
roster['gpu_policy'] = 'Pizza explicitly released the broker at14:56:05UTC (rev3, grant null); coordinator independently found parent35576 and child6216 absent14:57:01. Root legacy marker remains pending reconciliation. No Einhander GPU probe started; new starts require actual coordinated grant and resource checks.'
roster['sessions'][0]['live_hook_status'] = 'Original parent-root session retired from new assignments15:04UTC with durable handoff and no owned jobs. Canonical-root supported replacement remains pending; no fabricated user_stop or global hook change.'
rosterfile.write_text(json.dumps(roster, indent=2)+'\n')
snapshot(rosterfile, 'dated-coordination/CLAUDE-SESSIONS-20261114.json')

readme = p/'README.md'
text = legacy_utf8(readme)
text = text.split('\n## Later handoff and shared-resource verification')[0]
text = text.replace('The actual metadata monitor PID1652 is bounded to14:55:21UTC;', 'The actual metadata monitor PID31968 is bounded to15:23:29.643UTC;')
text += '''
## Later handoff and shared-resource verification

Pizza explicitly released its broker grant at14:56:05UTC after37 frames/exit0; the coordinator independently found registered parent35576 and GPU child6216 absent14:57:01. Shared revision3 has no owner. Root's separate legacy user-project marker remains pending reconciliation at this publication checkpoint. No Einhander modern GPU test started. Time expiry alone never transfers ownership.

The canonical shared-resource broker and Python launcher guard are included. Eight independently replayed broker controls pass on CPU11/below-normal: exclusive ownership/fencing, expiry refusal, deny/allow, durable requests, actual job identity requirements, mutex contention, real live-PID refusal and durable outbox delivery outside the state mutex. Twelve launcher-guard and seven integrated parent-cleanup controls pass separately. Actual positive broker registration plus graphics execution remain NOT RUN. This is a cooperative launcher protocol, not an OS GPU lock. Release blocks any registered live PID and currently may also fail closed on PID reuse; exact process identity needs manual reconciliation without terminating unrelated processes. Private tokens, live state and unrelated chat URLs are excluded.

The first captured broker replay printed eight passing controls in Node's default human-readable reporter, but the capture harness wrongly required TAP text and stopped before writing a result. Its stdout/stderr are preserved; the corrected repeat explicitly selects TAP and captures exit0. That harness assertion failure is not a broker test failure.

The original native primary session retired from new assignments at15:04UTC with durable handoff and no jobs. A supported canonical-root replacement is pending; three other native workers continue. S45 owns actual menu/HUD implementation:152 missing fade keys are DERIVED CRC-matched palette candidates, not directly captured source; provenance reproduces18/18 retained phases, but remaining five keys/source/live admission stay open. S23's new J3 finds six light-strip phase-pair silhouette defects and prepares phase-union isolation; that repair has not run at this checkpoint. S67's later r2b native-fill proposal reports8/8 class passes and removes the wrong teal smoke fill in simulation; it remains unaccepted in game. These later notices are qualified author reports, outside the frozen earlier run subset.
'''
readme.write_text(text)

gpu_doc = '''# Shared GPU coordination — verified CPU results, November14

The shared broker now enforces one cooperative grant at a time for Pizza and Einhander launchers. A request does not grant access. The coordinator grants a fenced token, the holder checks it before starting and registers its managed job, and release requires an explicit no-GPU-jobs assertion with no registered PID still alive. Expiry prevents new starts and never transfers ownership. Notifications use a durable outbox outside the mutation mutex.

Eight independent CPU controls pass; twelve Python launcher-guard controls and seven integrated cleanup controls pass separately. [Exact source, captured output and qualified results](../remaster-audit/texture-composer-followup-20261114/README.md). Canonical sources are [the broker](../tools/coordination/shared-gpu.mjs), [its controls](../tools/coordination/test-shared-gpu.mjs) and [the launcher guard](../tools/coordination/shared_gpu_guard.py).

Pizza explicitly released at14:56:05UTC after its37-frame job/exit0. The coordinator independently observed registered parent35576 and child6216 absent14:57:01. Root's legacy user-project hold has not yet been reconciled. No Einhander modern GPU/game/audio test ran. Positive integrated registration/graphics execution remains unverified; no ray tracing or DLSS in-game result is claimed.

This protocol relies on participating launchers. It does not reserve GPU resources at the operating-system level. Current release checks fail closed on any live registered PID, including a possible reused PID; reconcile exact identity without killing unrelated work. Hidden tokens and live state are excluded from publication. Global driver settings and power limits were unchanged.
'''
(r/'docs/SHARED-GPU-RESULTS-20261114.md').write_text(gpu_doc)
shutil.copy2(r/'docs/SHARED-GPU-RESULTS-20261114.md',w/'docs/SHARED-GPU-RESULTS-20261114.md')
docs=['docs/'+x for x in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
for rel in docs:
    f=r/rel
    content=legacy_utf8(f)
    content=re.sub(r'\n## Resource and native-worker update —15:06UTC\n.*?(?=\n## |\Z)','',content,flags=re.S)
    title,tail=content.split('\n',1)
    update='''
## Resource and native-worker update —15:06UTC

Pizza explicitly released its shared GPU grant14:56:05UTC; coordinator independently checked parent/child absence14:57:01. Root's legacy marker is still pending reconciliation; no new Einhander GPU/game/audio test ran. [Shared-resource controls and limits](../docs/SHARED-GPU-RESULTS-20261114.md) pass on CPU. The metadata monitor PID31968 is bounded to15:23:29.643UTC and proves monitoring only. Original native primary retired from new assignments with a durable handoff; supported canonical-root replacement remains pending. Other three workers continue stage/UI repairs. HUD152 derived fade-key candidates are not source/live admission; S23 phase silhouette defects and S67 native smoke-fill repairs remain subject to actual acceptance.

'''
    with f.open('w',encoding='utf-8',newline='\n') as stream:
        stream.write(title+'\n'+update+tail.lstrip())
    shutil.copy2(f,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json'
state=json.loads(statefile.read_text())
state['updated_at_utc']=now()
state['actual_monitor']=dict(pid=monitor['pid'],bound_end_utc=monitor['bound_end_utc'],watcher_only=True,proves_model_activity=False)
state['latest_resource_policy'].update(broker_revision=3,broker_owner=None,broker_explicit_release_utc='2026-11-14T14:56:05Z',legacy_marker_pending_reconciliation=True,new_start_requires_coordinator_grant=True,requires_explicit_user_release=False)
statefile.write_text(json.dumps(state,indent=2)+'\n')
shutil.copy2(statefile,w/statefile.relative_to(r))
snapshot(Path(__file__),'root/'+Path(__file__).name)
mapping['prepublication_correction_utc']=now()
(p/'SOURCE-MAP.json').write_text(json.dumps(mapping,indent=2)+'\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'))
for f in p.rglob('*'):
    if f.is_file():
        dest=r/'remaster-audit'/name/f.relative_to(p)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(f,dest)
paths=['remaster-audit/'+name,*docs,'docs/SHARED-GPU-RESULTS-20261114.md',statefile.relative_to(r).as_posix(),*[f.relative_to(r).as_posix() for f in [broker,tests,r/'tools/coordination/shared_gpu_guard.py']]]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=now(),packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),broker_controls=receipt,staged=True,committed=False,pushed=False,gpu_test_started=False)
(n/'texture-composer-finalized.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
