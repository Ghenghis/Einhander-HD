"""run_rc2.py (r1) - run ONE granted command below normal on ONE explicit logical CPU, inside a Windows Job Object,
and record the child's real exit code (claude-einhander).

Replaces run_rc.py (f07bee3b...). The coordinator found that it:
  1. pinned the last allowed CPU instead of an explicit one;
  2. killed only the immediate child on timeout;
  3. exited 0 regardless of the child's exit code.
r1 also fixes three points from the coordinator's review of r0 (fdd6f3e8..., msg_4ad952a7):
  - argtypes/restype are declared for every Win32/NT call;
  - every failure path cleans up the job and the child and writes a 125 receipt;
  - the absence check runs only after the wrapper has released its own handles to the exited child.

Usage:
  python run_rc2.py --out RC.json --cpu N --timeout S [--max-cpu PCT] [--min-free-gib G] -- CMD ...

Exit codes:
  - the child's own exit code on normal completion with the whole tree absent;
  - 124: timeout; the job was terminated and the tree is absent;
  - 125: wrapper error, or the tree was not proven absent;
  - 3: precheck declined; nothing was started;
  - 2: usage error (argparse); nothing was started.

Receipt (rc.json):
  - written with fsync before resume, and again at the end;
  - records the child's exit code, job accounting (total/active/terminated), every descendant PID ever seen,
    and child, descendant and job absence as separate facts.
Test-only fault injection: env RUN_RC2_FAULT=after_spawn raises after the child is created (suspended) and assigned,
before resume. Used by the self-test.
"""
import argparse
import ctypes
import datetime
import gc
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

import psutil

K32 = ctypes.WinDLL("kernel32", use_last_error=True)
NTDLL = ctypes.WinDLL("ntdll")
CREATE_SUSPENDED = 0x00000004
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_AFFINITY = 0x00000010
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
JobObjectBasicAccountingInformation = 1
JobObjectExtendedLimitInformation = 9
PROCESS_ALL_ACCESS = 0x1F0FFF


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                  "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]


# Every Win32/NT entry point used below has explicit types (no default int conversion of 64-bit HANDLEs).
K32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
K32.CreateJobObjectW.restype = wintypes.HANDLE
K32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
K32.SetInformationJobObject.restype = wintypes.BOOL
K32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                          wintypes.LPVOID]
K32.QueryInformationJobObject.restype = wintypes.BOOL
K32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
K32.AssignProcessToJobObject.restype = wintypes.BOOL
K32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
K32.TerminateJobObject.restype = wintypes.BOOL
K32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
K32.OpenProcess.restype = wintypes.HANDLE
K32.CloseHandle.argtypes = [wintypes.HANDLE]
K32.CloseHandle.restype = wintypes.BOOL
NTDLL.NtResumeProcess.argtypes = [wintypes.HANDLE]
NTDLL.NtResumeProcess.restype = ctypes.c_long


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def check(ok, what):
    if not ok:
        raise OSError(f"{what} failed: winerror {ctypes.get_last_error()}")


def write(path, rec):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def accounting(job):
    info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
    check(K32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation, ctypes.byref(info),
                                        ctypes.sizeof(info), None), "QueryInformationJobObject")
    return dict(active=info.ActiveProcesses, total=info.TotalProcesses, terminated=info.TotalTerminatedProcesses,
                user_s=info.TotalUserTime / 1e7, kernel_s=info.TotalKernelTime / 1e7)


def gone(pid, ctime):
    """True when no live process holds this PID with this creation time. psutil.pid_exists() checks the exit code,
    so an exited process whose handle is still open elsewhere does NOT count as running. A PID reused by a new
    process has a different creation time."""
    if not psutil.pid_exists(pid):
        return True
    try:
        return psutil.Process(pid).create_time() != ctime
    except psutil.NoSuchProcess:
        return True


def wait_gone(items, seconds=2.0):
    """Poll until every (pid, ctime) is gone or the bound expires; return the PIDs still present."""
    deadline = time.monotonic() + seconds
    left = [pid for pid, ct in items if not gone(pid, ct)]
    while left and time.monotonic() < deadline:
        time.sleep(0.025)
        left = [pid for pid, ct in items if not gone(pid, ct)]
    return sorted(left)


def run_child(a, cmd, rec):
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               NUMEXPR_NUM_THREADS="1")
    env.pop("RUN_RC2_FAULT", None)
    fault = os.environ.get("RUN_RC2_FAULT", "")
    st = dict(job=None, p=None)
    seen = {}
    error = None
    timed_out = False
    t0 = time.monotonic()
    try:
        job = K32.CreateJobObjectW(None, None)
        check(job, "CreateJobObjectW")
        st["job"] = job
        lim = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        lim.BasicLimitInformation.LimitFlags = (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_AFFINITY
                                                | JOB_OBJECT_LIMIT_PRIORITY_CLASS)
        lim.BasicLimitInformation.Affinity = 1 << a.cpu
        lim.BasicLimitInformation.PriorityClass = BELOW_NORMAL_PRIORITY_CLASS
        check(K32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(lim),
                                          ctypes.sizeof(lim)), "SetInformationJobObject")
        st["p"] = subprocess.Popen(cmd, env=env, creationflags=CREATE_SUSPENDED | BELOW_NORMAL_PRIORITY_CLASS)
        rec["child_pid"] = st["p"].pid
        rec["child_create_time"] = psutil.Process(st["p"].pid).create_time()
        hproc = K32.OpenProcess(PROCESS_ALL_ACCESS, False, st["p"].pid)
        try:
            check(hproc, "OpenProcess")
            check(K32.AssignProcessToJobObject(job, hproc), "AssignProcessToJobObject")
            rec["job_assigned_before_resume"] = True
            if fault == "after_spawn":
                raise OSError("RUN_RC2_FAULT=after_spawn (test-only injected failure before resume)")
            rec["start_utc"] = now()
            write(a.out, rec)
            status = NTDLL.NtResumeProcess(hproc)
            if status != 0:
                raise OSError(f"NtResumeProcess NTSTATUS {status & 0xFFFFFFFF:#x}")
        finally:
            if hproc:
                K32.CloseHandle(hproc)
        t0 = time.monotonic()
        while True:
            try:
                for c in psutil.Process(rec["child_pid"]).children(recursive=True):
                    try:
                        seen.setdefault(c.pid, c.create_time())
                    except psutil.Error:
                        pass
            except psutil.Error:
                pass
            try:
                st["p"].wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - t0 > a.timeout:
                    timed_out = True
                    check(K32.TerminateJobObject(job, 124), "TerminateJobObject")
                    st["p"].wait(timeout=30)
                    break
    except BaseException as e:  # noqa: BLE001 - every failure is recorded and cleaned up below
        error = e
        rec["wrapper_error"] = repr(e)
    finally:
        job, p = st["job"], st["p"]
        if p is not None and p.poll() is None:            # still alive (suspended or running): kill the tree
            if job:
                K32.TerminateJobObject(job, 125)
            try:
                p.kill()
            except OSError:
                pass
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        child_rc = p.returncode if p is not None else None
        rec["child_exit_code"] = child_rc
        rec["timeout_killed"] = timed_out
        rec["elapsed_s"] = round(time.monotonic() - t0, 3)
        rec["end_utc"] = now()
        job_active = 0
        if job:
            try:
                acct = accounting(job)
                deadline = time.monotonic() + 5
                while acct["active"] and time.monotonic() < deadline:
                    time.sleep(0.05)
                    acct = accounting(job)
                rec["job"] = acct
                job_active = acct["active"]
            except OSError as e2:
                rec["job_query_error"] = repr(e2)
                job_active = None
        # release this wrapper's own handles to the exited child BEFORE the absence observation
        st["p"] = None
        del p
        gc.collect()
        rec["descendants_seen"] = sorted(seen)
        rec["descendants_left"] = wait_gone(list(seen.items()))
        if rec.get("child_pid") is not None and rec.get("child_create_time") is not None:
            rec["child_absent"] = not wait_gone([(rec["child_pid"], rec["child_create_time"])])
        elif rec.get("child_pid") is not None:
            rec["child_absent"] = not psutil.pid_exists(rec["child_pid"])
        else:
            rec["child_absent"] = True                     # no child was ever created
        rec["job_empty"] = job_active == 0
        rec["tree_absent"] = rec["job_empty"] and not rec["descendants_left"] and rec["child_absent"]
        if error is not None or not rec["tree_absent"]:
            rc = 125
        elif timed_out:
            rc = 124
        else:
            rc = child_rc
        rec["rc"] = rc
        rec["wrapper_exit"] = rc
        try:
            write(a.out, rec)
        except OSError as e3:
            print(f"run_rc2: receipt write failed: {e3!r}", file=sys.stderr)
            rc = 125
        if job:
            K32.CloseHandle(job)
        if error is not None:
            print(f"run_rc2 wrapper error: {error!r}", file=sys.stderr)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--timeout", type=float, required=True)
    ap.add_argument("--max-cpu", type=float, default=None)
    ap.add_argument("--min-free-gib", type=float, default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("missing command after --")
    me = psutil.Process()
    allowed = me.cpu_affinity()
    if a.cpu not in allowed:
        ap.error(f"--cpu {a.cpu} not in allowed affinity {allowed}")
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([a.cpu])
    rec = dict(tool="run_rc2.py", revision="r1", cmd=cmd, cwd=os.getcwd(), wrapper_pid=me.pid,
               wrapper_create_time=me.create_time(), cpu=a.cpu, affinity=me.cpu_affinity(), priority=int(me.nice()),
               timeout_s=a.timeout, rc=None, created_utc=now())
    if a.max_cpu is not None or a.min_free_gib is not None:
        cpu_pct = psutil.cpu_percent(interval=1.0)
        free = psutil.virtual_memory().available / 2 ** 30
        rec["precheck"] = dict(system_cpu_pct=cpu_pct, free_gib=round(free, 2), max_cpu=a.max_cpu,
                               min_free_gib=a.min_free_gib, at_utc=now())
        if (a.max_cpu is not None and cpu_pct >= a.max_cpu) or (a.min_free_gib is not None and free < a.min_free_gib):
            rec.update(declined=True, child_pid=None, wrapper_exit=3, end_utc=now())
            write(a.out, rec)
            return 3
    return run_child(a, cmd, rec)


if __name__ == "__main__":
    sys.exit(main())
