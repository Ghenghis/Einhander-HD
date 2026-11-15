from pathlib import Path
import datetime,hashlib,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/scene-texture-followup-20261114'
src=r/'remaster-audit/runtime-review/post-crash-recovery-20261114';f=src/'20261114T130829345501Z/integrity.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest()
assert sha(f)=='7130302e991de9c8ffbd4b7eeaa51339f2ab6c79f8ac82c6dac2dfee66e3a393'
d=json.loads(f.read_text());failed=0;counterparts=0;inputs=0
for row in d['damaged_files']:
    data=Path(row['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['current']['sha256'] and data and not any(data);failed+=1
    c=row['recovery_candidate']
    if c and c.get('exists'):
        data=Path(c['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==c['sha256'] and b'\0' not in data;counterparts+=1
for row in d['recorded_inputs']:
    assert any(sha(c['path'])==row['expected'] for c in row['copies']);inputs+=1
assert (failed,counterparts,inputs)==(90,89,10)
dst=p/'root/recovery';dst.mkdir(exist_ok=False)
for name,source in [('integrity.json',f),('crash-events.json',src/'crash-events.json'),('verify_recovery.py',src/'verify_recovery.py')]:shutil.copy2(source,dst/name)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),independent_receipt_sha256=sha(f),failed_frozen_files_reverified=failed,intact_counterparts_reverified=counterparts,recorded_input_pins_reverified=inputs,original_receipt_actor='Separate user-owned crash/status chat01a1da2a, now codex-einhander-crash-check; main independently checks its reported file bytes here.',original_published_pins_count=990,original_published_pins_scope='Original separate audit; main has independently checked its own1348 staged source/evidence pins.',files_repaired=False,gpu_executed=False)
(dst/'main-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,p/'root/include_recovery_receipt.py')
readme=p/'README.md';s=readme.read_text();needle='Native Claude was resumed'
addition='The separate crash/status chat independently found 89 intact source/run/selftest counterparts for the 90 damaged text files and matching copies of all 10 recorded run input pins. Main rechecked those concrete file hashes before including `root/recovery/integrity.json`, its checker and `main-verification.json`. The scoped System events record an unexpected prior shutdown at 05:43:59 Phoenix and boot at approximately 05:49:21; these timestamps do not establish a crash or corruption cause. The failed freeze remains untouched.\n\n'
assert needle in s;s=s.replace(needle,addition+needle,1);readme.write_text(s)
for rel in ['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']:shutil.copy2(r/rel,w/rel)
print(json.dumps(receipt))
