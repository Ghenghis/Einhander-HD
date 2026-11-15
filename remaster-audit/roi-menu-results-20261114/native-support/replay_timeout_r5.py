#!/usr/bin/env python3
"""claude-einhander-support: independent replay of the s67 timeout-profile r5 synthetic suite (EIN-SUPPORT-TIMEOUT-VERIFY-20261114).

Run ONLY under an explicit codex-einhander-crash-check grant. The script reads the s67 folder; every write goes to --out.
  python -B -I replay_timeout_r5.py --out <new dir> --validator-sha <sha256> --tests-sha <sha256> --cap-s <grant cap>
         [--affinity-hex <grant mask>] [--check-only]
  The cap, affinity and pins all come from the grant. The job enforces BelowNormal and the affinity on every process in the tree.

What it does:
  1. Pins the exact validator, tests and canonical validator (sha256) before and after the run, plus a full hash list of the
     s67 folder so any change there is reported.
  2. Resource gate: system CPU below 60% over a 1 s sample, and free physical memory above 16 GiB. If the gate fails it
     stops with exit 3 and starts nothing.
  3. Starts one child, `python -B -I test_timeout_leg.py <out>/work`:
     - BelowNormal priority, thread environment limited to 1;
     - assigned at once to a Job Object (kill-on-close, 512 MiB job memory limit). Job accounting gives the child-tree
       process counts. Assignment happens after the child starts; the first grandchild (a validator run) appears only
       after fixture building.
     - Hard cap of 150 s; on overrun the whole job is terminated.
  4. Records the child's PID, creation time and start/end UTC; the job's total, active and terminated process counts and
     peak memory; the outer exit; the case counts from the suite's JSON; and the canonical validator X/T negative control
     row. Writes <out>/result.json, stdout.json and stderr.txt.
Exit: 0 = suite rc 0, all_ok, X/T control ok and the s67 folder unchanged; 1 = otherwise; 2 = usage or pin error; 3 = gate refused.
"""
import argparse
import ctypes
import ctypes.wintypes as W
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

SRC = 'C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/tooling/timeout-profile'
CANON = 'C:/github/Einhander/remaster-audit/fullgame-prep/acquisition/validate_acquisition.py'
PINS = {}   # set from the required --validator-sha / --tests-sha (the exact pins named in the grant); no stale defaults
CANON_PIN = 'b5952fae2f7687ed057cd93bda8b894412093d4612a21f127b171f303d32d0d1'
CAP_S, MEM_CAP, CPU_MAX, FREE_MIN = 150, 512 << 20, 60.0, 16 << 30
k32 = ctypes.WinDLL('kernel32', use_last_error=True)


def utc(t=None):
    return datetime.datetime.fromtimestamp(time.time() if t is None else t, datetime.timezone.utc).isoformat()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tree_hashes(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root).replace('\\', '/')] = sha(p)
    return out


def ft(f):
    return (f.dwHighDateTime << 32) | f.dwLowDateTime


def cpu_percent(interval=1.0):
    def snap():
        i, k, u = W.FILETIME(), W.FILETIME(), W.FILETIME()
        if not k32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u)):
            raise OSError(ctypes.get_last_error(), 'GetSystemTimes')
        return ft(i), ft(k), ft(u)
    i0, k0, u0 = snap()
    time.sleep(interval)
    i1, k1, u1 = snap()
    total = (k1 - k0) + (u1 - u0)          # kernel time includes idle
    return 100.0 * (1.0 - (i1 - i0) / total) if total else 100.0


class MEMSTAT(ctypes.Structure):
    _fields_ = [('dwLength', W.DWORD), ('dwMemoryLoad', W.DWORD), ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def free_phys():
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(m)
    if not k32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError(ctypes.get_last_error(), 'GlobalMemoryStatusEx')
    return m.ullAvailPhys


class IOC(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('r', 'w', 'o', 'rb', 'wb', 'ob')]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', W.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', W.DWORD), ('SchedulingClass', W.DWORD)]


class EXT_LIMIT(ctypes.Structure):
    _fields_ = [('Basic', BASIC_LIMIT), ('Io', IOC), ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t)]


class BASIC_ACCT(ctypes.Structure):
    _fields_ = [('TotalUserTime', ctypes.c_longlong), ('TotalKernelTime', ctypes.c_longlong),
                ('ThisPeriodTotalUserTime', ctypes.c_longlong), ('ThisPeriodTotalKernelTime', ctypes.c_longlong),
                ('TotalPageFaultCount', W.DWORD), ('TotalProcesses', W.DWORD), ('ActiveProcesses', W.DWORD),
                ('TotalTerminatedProcesses', W.DWORD)]


k32.CreateJobObjectW.restype = W.HANDLE
k32.OpenProcess.restype = W.HANDLE


def make_job(affinity=0):
    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), 'CreateJobObjectW')
    lim = EXT_LIMIT()
    # KILL_ON_JOB_CLOSE | JOB_MEMORY | PRIORITY_CLASS (BelowNormal for every process in the job) [| AFFINITY from the grant]
    lim.Basic.LimitFlags = 0x2000 | 0x200 | 0x20 | (0x10 if affinity else 0)
    lim.Basic.PriorityClass = 0x4000
    lim.Basic.Affinity = affinity
    lim.JobMemoryLimit = MEM_CAP
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(lim), ctypes.sizeof(lim)):
        raise OSError(ctypes.get_last_error(), 'SetInformationJobObject')
    return job


def job_info(job):
    a, e = BASIC_ACCT(), EXT_LIMIT()
    k32.QueryInformationJobObject(job, 1, ctypes.byref(a), ctypes.sizeof(a), None)
    k32.QueryInformationJobObject(job, 9, ctypes.byref(e), ctypes.sizeof(e), None)
    return dict(total_processes=a.TotalProcesses, active_processes=a.ActiveProcesses,
                terminated_processes=a.TotalTerminatedProcesses, cpu_user_s=a.TotalUserTime / 1e7,
                cpu_kernel_s=a.TotalKernelTime / 1e7, peak_job_memory_bytes=e.PeakJobMemoryUsed,
                peak_process_memory_bytes=e.PeakProcessMemoryUsed)


def creation_utc(handle):
    c, x, k, u = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
    if not k32.GetProcessTimes(handle, ctypes.byref(c), ctypes.byref(x), ctypes.byref(k), ctypes.byref(u)):
        return None
    return utc((ft(c) - 116444736000000000) / 1e7)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--check-only', action='store_true', help='pins and gate only; start no child')
    ap.add_argument('--validator-sha', required=True, help='exact sha256 of validate_timeout_leg.py named in the grant')
    ap.add_argument('--tests-sha', required=True, help='exact sha256 of test_timeout_leg.py named in the grant')
    ap.add_argument('--cap-s', type=int, required=True, help='hard wall-clock cap in seconds named in the grant')
    ap.add_argument('--affinity-hex', default='', help='CPU affinity mask named in the grant, e.g. 8000 for CPU15')
    a = ap.parse_args(argv)
    global CAP_S
    CAP_S = a.cap_s
    affinity = int(a.affinity_hex, 16) if a.affinity_hex else 0
    PINS.clear()
    PINS.update({'validate_timeout_leg.py': a.validator_sha.lower(), 'test_timeout_leg.py': a.tests_sha.lower()})
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        print('refusing: --out exists and is not empty', file=sys.stderr)
        return 2
    os.makedirs(out, exist_ok=True)
    res = dict(schema='support-timeout-r5-replay-v1', task='EIN-SUPPORT-TIMEOUT-VERIFY-20261114', owner='claude-einhander-support',
               runner_sha256=sha(os.path.abspath(__file__)), python=sys.version, src=SRC, out=out.replace('\\', '/'),
               caps=dict(seconds=CAP_S, job_memory_bytes=MEM_CAP, cpu_gate_percent=CPU_MAX, free_gate_bytes=FREE_MIN))
    pins_before = {n: sha(os.path.join(SRC, n)) for n in PINS}
    res['pins_before'] = dict(pins_before, canonical=sha(CANON))
    tree_before = tree_hashes(SRC)
    bad = [n for n, h in PINS.items() if pins_before[n] != h] + (['canonical'] if res['pins_before']['canonical'] != CANON_PIN else [])
    res['pin_mismatch'] = bad

    def finish(code):
        res['exit'] = code
        res['finished_utc'] = utc()
        with open(os.path.join(out, 'result.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=1)
        print(json.dumps({k: res.get(k) for k in ('exit', 'gate', 'child', 'suite', 'xt_control', 'src_unchanged')}, default=str))
        return code
    if bad:
        return finish(2)
    cpu, free = cpu_percent(), free_phys()
    res['gate'] = dict(utc=utc(), cpu_percent=round(cpu, 2), free_phys_bytes=free, passed=cpu < CPU_MAX and free > FREE_MIN)
    if not res['gate']['passed'] or a.check_only:
        res['check_only'] = a.check_only
        return finish(3 if not res['gate']['passed'] else 0)
    work = os.path.join(out, 'work')
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    cmd = [sys.executable, '-B', '-I', os.path.join(SRC, 'test_timeout_leg.py'), work]
    res['command'] = cmd
    res['caps'].update(seconds=CAP_S, affinity_hex=f'{affinity:x}' if affinity else None)
    job = make_job(affinity)
    with open(os.path.join(out, 'stdout.json'), 'wb') as so, open(os.path.join(out, 'stderr.txt'), 'wb') as se:
        t0 = time.time()
        p = subprocess.Popen(cmd, cwd=out, env=env, stdout=so, stderr=se, creationflags=0x4000)   # BELOW_NORMAL_PRIORITY_CLASS
        assigned = bool(k32.AssignProcessToJobObject(job, W.HANDLE(int(p._handle))))
        child = dict(pid=p.pid, start_utc=utc(t0), creation_utc=creation_utc(W.HANDLE(int(p._handle))), job_assigned=assigned,
                     priority='BELOW_NORMAL')
        try:
            rc, timed_out = p.wait(timeout=CAP_S), False
        except subprocess.TimeoutExpired:
            k32.TerminateJobObject(job, 1)
            rc, timed_out = p.wait(), True
        child.update(end_utc=utc(), elapsed_s=round(time.time() - t0, 3), exit=rc, timed_out=timed_out)
        child['job'] = job_info(job)
    k32.CloseHandle(job)
    res['child'] = child
    try:
        rep = json.load(open(os.path.join(out, 'stdout.json'), encoding='utf-8'))
        rows = rep.get('results', [])
        res['suite'] = dict(cases=rep.get('cases'), passed=rep.get('passed'), all_ok=rep.get('all_ok'),
                            failed_cases=[r['case'] for r in rows if not r.get('ok')],
                            r5_cases=sum(1 for r in rows if str(r.get('case', '')).startswith('r5')),
                            # stricter independent view: a negative should fail ONLY its expected gate; co-failures (run 1: K on
                            # every snapshot negative) mean the control did not isolate that gate on a clean base
                            cofailures=[dict(case=r['case'], expect=r.get('expect'), failing=r.get('failing'))
                                        for r in rows if r.get('expect') not in ('pass', 'fails X and T')
                                        and [g for g in r.get('failing', []) if g != r.get('expect')]])
        xt = [r for r in rows if r.get('case') == 'canonical validator on the timeout leg']
        res['xt_control'] = xt[0] if xt else None
    except (ValueError, OSError) as exc:
        res['suite'] = dict(parse_error=f'{exc.__class__.__name__}: {exc}')
        res['xt_control'] = None
    res['pins_after'] = dict({n: sha(os.path.join(SRC, n)) for n in PINS}, canonical=sha(CANON))
    tree_after = tree_hashes(SRC)
    res['src_unchanged'] = tree_after == tree_before
    if not res['src_unchanged']:
        res['src_diff'] = sorted(set(tree_before.items()) ^ set(tree_after.items()))
    ok = (rc == 0 and not timed_out and res['suite'].get('all_ok') is True and res['src_unchanged']
          and bool(res['xt_control'] and res['xt_control'].get('ok')) and child['job']['active_processes'] == 0)
    return finish(0 if ok else 1)


if __name__ == '__main__':
    sys.exit(main())
