#!/usr/bin/env python3
"""Dummy-child self-test r2 for run_rc2_envelope_r1.py (claude-einhander-support, EIN-SUPPORT-WATCHDOG-VARIANT-20261114).
SOURCE ONLY. Run only after the coordinator clears the hold and gives a fresh grant. No outer Job of any kind.
  python -B -I selftest_envelope_r2.py --out <new dir> --cpu <granted cpu>
Spec: TEST-PLAN-r1.md (cases and oracles) plus TEST-PLAN-r2.md (the r2 delta, root review msg_e084f171):
  - each case has a `finally` that kills and waits only its own wrapper, and only while it still matches its creation time;
  - 240 s case-work budget; hard overall limit of 300 s; every cleanup wait bounded by min(30 s, time left to the limit);
  - the T5b "before" mask is recorded only; the explicit set, the readback and the child's self-report must equal the
    original mask;
  - all_ok requires exactly 10 cases, all ok, plus both sentinel flags. No retries; partial receipts are kept.
Exit 0 = all_ok; 1 = any failure (each recorded); 2 = pins/usage/affinity (nothing started)."""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ENV = HERE / 'run_rc2_envelope_r1.py'
PLAN_R1 = HERE / 'TEST-PLAN-r1.md'
PLAN_R2 = HERE / 'TEST-PLAN-r2.md'
R1 = Path('C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/tools/run_rc2.r1.py')
PINS = {R1: 'cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd',
        ENV: 'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',
        PLAN_R1: '9b2420b934ae4260b02f81008d5ab65f03799869a8f6cccbf03216d80bddc6a0',
        PLAN_R2: '6039654d449001827b66acea668dc0978f8ee18dff9ffd8ebf08e582a1f9d44e'}
PY = sys.executable
HIDDEN_BELOW_NORMAL = 0x08004000
WORK_S, HARD_S = 240.0, 300.0
EXPECTED_CASES = ('T1_normal_return', 'T2_failure_exit7', 'T3_timeout_grandchild', 'T4_injected_postspawn_failure',
                  'T5a_affinity_one_core', 'T5b_affinity_original', 'T6_hard_memory_cap', 'T7a_usage_timeout_over_300',
                  'T7b_usage_invalid_cap', 'T8_r1_baseline')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_process(pid, ctime):
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).create_time() == ctime
    except psutil.Error:
        return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--cpu', type=int, required=True)
    a = ap.parse_args()
    got = {str(p): sha(p) for p in PINS}
    bad = [str(p) for p in PINS if got[str(p)] != PINS[p]]
    if bad:
        print(json.dumps(dict(pin_mismatch=bad, got=got)), file=sys.stderr); return 2
    original = sorted(psutil.Process().cpu_affinity())
    if len(original) < 2 or a.cpu not in original:
        print(f'refusing: allowed affinity {original} (need >= 2 CPUs incl. --cpu; never inside a 1-CPU Job)', file=sys.stderr)
        return 2
    root = Path(a.out).resolve()
    root.mkdir(parents=True, exist_ok=False)                  # exclusive output dir
    t_start = time.monotonic()
    hard_left = lambda: HARD_S - (time.monotonic() - t_start)
    cleanup_wait = lambda: max(0.1, min(30.0, hard_left()))
    res = dict(schema='support-envelope-selftest-r2', pins=got, selftest_sha256=sha(Path(__file__)), cpu=a.cpu,
               allowed_affinity=original, budget=dict(work_s=WORK_S, hard_s=HARD_S), cases=[],
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    sentinel, s_ct = None, None
    try:
        sentinel = subprocess.Popen([PY, '-I', '-c', 'import time; time.sleep(600)'], creationflags=HIDDEN_BELOW_NORMAL)
        s_ct = psutil.Process(sentinel.pid).create_time()
        res['sentinel'] = dict(pid=sentinel.pid, create_time=s_ct)

        def case(name, tool, timeout, child, oracle, extra=(), env_extra=None):
            row = dict(case=name, ok=False)
            res['cases'].append(row)
            w, w_ct = None, None
            try:
                work_left = WORK_S - (time.monotonic() - t_start)
                if work_left < 5:
                    row['why'] = 'case-work budget exhausted before this case'; return
                out = root / name; out.mkdir()
                child = [c.replace('{OUT}', str(out)) for c in child]
                rc_path = out / 'receipt.json'
                env = dict(os.environ, **(env_extra or {}))
                w = subprocess.Popen([PY, '-B', '-I', str(tool), '--out', str(rc_path), '--cpu', str(a.cpu), '--timeout',
                                      str(timeout), *extra, '--', *child], env=env, creationflags=HIDDEN_BELOW_NORMAL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                w_ct = psutil.Process(w.pid).create_time()
                row.update(wrapper_pid=w.pid, wrapper_create_time=w_ct)
                t0 = time.monotonic()
                try:
                    so, se = w.communicate(timeout=max(0.1, min(float(timeout) + 30.0, work_left, hard_left())))
                except subprocess.TimeoutExpired:
                    row['incomplete'] = 'wrapper exceeded its case bound'
                    if same_process(w.pid, w_ct):
                        w.kill()                              # its kill-on-close Job removes the child tree
                    so, se = w.communicate(timeout=cleanup_wait())
                row.update(wrapper_rc=w.returncode, elapsed_s=round(time.monotonic() - t0, 2), stderr_tail=(se or '')[-1500:])
                rec = None
                if rc_path.exists():
                    try:
                        rec = json.loads(rc_path.read_text(encoding='utf-8'))
                    except ValueError as exc:
                        row['receipt_error'] = f'unparseable receipt: {exc}'
                row['receipt'] = {k: (rec or {}).get(k) for k in (
                    'rc', 'child_exit_code', 'timeout_killed', 'tree_absent', 'descendants_seen', 'descendants_left',
                    'job_limits_readback', 'child_affinity_before_set', 'child_affinity_set_to', 'child_readback_before_resume',
                    'allowed_before_pin', 'start_utc', 'wrapper_error', 'peak_job_memory_bytes', 'affinity')}
                row['receipt_present'] = rec is not None
                if 'incomplete' in row or 'receipt_error' in row:
                    row['why'] = 'incomplete or bad receipt'; return
                ok, why = oracle(w.returncode, rec, out)
                row.update(ok=bool(ok), why=why)
            except Exception as exc:  # noqa: BLE001 - recorded as a failure, never a pass
                row['why'] = f'{exc.__class__.__name__}: {exc}'
            finally:
                # r2: never leave an owned wrapper (and its Job) running after any exception
                if w is not None and w.poll() is None:
                    row['finally_cleanup'] = 'wrapper still running'
                    if w_ct is not None and same_process(w.pid, w_ct):
                        w.kill()
                        row['finally_cleanup'] += '; killed owned wrapper (PID+creation verified)'
                    try:
                        w.wait(timeout=cleanup_wait())
                    except subprocess.TimeoutExpired:
                        row['finally_cleanup'] += '; wait bound expired'
                    row['ok'] = False

        tree = lambda r: bool(r) and r.get('tree_absent') is True
        aff = 'import json,sys,psutil; json.dump(sorted(psutil.Process().cpu_affinity()), open(sys.argv[1],"w"))'
        grand = ('import subprocess,sys,time; subprocess.Popen([sys.executable,"-I","-c","import time; time.sleep(120)"]); '
                 'time.sleep(120)')
        mem = ('import sys\ntry:\n x = bytearray(256 << 20)\nexcept MemoryError:\n open(sys.argv[1] + "/memerror.txt","w").write("memerror")\n'
               ' raise SystemExit(3)\nopen(sys.argv[1] + "/after_alloc.txt","w").write("after")\n')
        ok0 = [PY, '-I', '-c', 'import sys; sys.exit(0)']

        case('T1_normal_return', ENV, 30, ok0, lambda rc, r, o: (
            rc == 0 and r.get('rc') == 0 and tree(r) and r['job_limits_readback']['affinity_mask'] == 1 << a.cpu, 'rc0/tree/mask'))
        case('T2_failure_exit7', ENV, 30, [PY, '-I', '-c', 'import sys; sys.exit(7)'], lambda rc, r, o: (
            rc == 7 and r.get('child_exit_code') == 7 and tree(r), 'rc7 propagated'))
        case('T3_timeout_grandchild', ENV, 3, [PY, '-I', '-c', grand], lambda rc, r, o: (
            rc == 124 and r.get('timeout_killed') is True and tree(r) and len(r.get('descendants_seen') or []) >= 1
            and not r.get('descendants_left'), 'rc124, grandchild seen and gone'))
        case('T4_injected_postspawn_failure', ENV, 30, ok0, lambda rc, r, o: (
            rc == 125 and 'after_spawn' in str(r.get('wrapper_error')) and r.get('start_utc') is None and tree(r),
            'rc125 before resume, never started'), env_extra={'RUN_RC2_FAULT': 'after_spawn'})
        case('T5a_affinity_one_core', ENV, 30, [PY, '-I', '-c', aff, '{OUT}/aff.json'], lambda rc, r, o: (
            rc == 0 and tree(r) and json.loads((o / 'aff.json').read_text()) == [a.cpu]
            and r['child_readback_before_resume']['cpu_affinity'] == [a.cpu], 'child sees [cpu]'))
        case('T5b_affinity_original', ENV, 30, [PY, '-I', '-c', aff, '{OUT}/aff.json'], lambda rc, r, o: (
            rc == 0 and tree(r) and r.get('child_affinity_set_to') == original
            and r['child_readback_before_resume']['cpu_affinity'] == original and r.get('allowed_before_pin') == original
            and json.loads((o / 'aff.json').read_text()) == original,
            f"explicit set/readback/self-report = original (before-set recorded: {r.get('child_affinity_before_set')})"),
            extra=('--child-affinity', 'original'))
        case('T6_hard_memory_cap', ENV, 30, [PY, '-I', '-c', mem, '{OUT}'], lambda rc, r, o: (
            r['job_limits_readback']['job_memory_limit'] == 64 << 20 and rc == 3 and r.get('child_exit_code') == 3
            and (o / 'memerror.txt').exists() and not (o / 'after_alloc.txt').exists() and tree(r),
            'cap readback + controlled MemoryError + no after-alloc marker (peak reported only)'),
            extra=('--max-job-mib', '64'))
        case('T7a_usage_timeout_over_300', ENV, 301, ok0, lambda rc, r, o: (
            rc == 2 and r is None and not (o / 'receipt.json').exists(), 'exit 2, no receipt, nothing started'))
        case('T7b_usage_invalid_cap', ENV, 30, ok0, lambda rc, r, o: (
            rc == 2 and r is None and not (o / 'receipt.json').exists(), 'exit 2, no receipt, nothing started'),
            extra=('--max-job-mib', '5000'))
        case('T8_r1_baseline', R1, 30, ok0, lambda rc, r, o: (
            rc == 0 and tree(r) and r.get('affinity') == [a.cpu], 'canonical r1 on the same child'))
    finally:
        if sentinel is not None:
            alive = s_ct is not None and same_process(sentinel.pid, s_ct)
            res.setdefault('sentinel', {})['untouched_by_cases'] = alive
            if alive:
                sentinel.kill()
            try:
                sentinel.wait(timeout=cleanup_wait())
            except subprocess.TimeoutExpired:
                pass
            res['sentinel']['absent_after'] = not (s_ct is not None and same_process(sentinel.pid, s_ct))
        names = tuple(c['case'] for c in res['cases'])
        res['elapsed_s'] = round(time.monotonic() - t_start, 2)
        res['case_count_exact'] = names == EXPECTED_CASES
        res['all_ok'] = res['case_count_exact'] and all(c.get('ok') for c in res['cases']) and \
            bool(res.get('sentinel', {}).get('untouched_by_cases')) and bool(res.get('sentinel', {}).get('absent_after'))
        (root / 'result.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(dict(all_ok=res['all_ok'], case_count_exact=res['case_count_exact'],
                              cases={c['case']: c.get('ok') for c in res['cases']}, sentinel=res.get('sentinel'),
                              elapsed_s=res['elapsed_s'])))
    return 0 if res['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
