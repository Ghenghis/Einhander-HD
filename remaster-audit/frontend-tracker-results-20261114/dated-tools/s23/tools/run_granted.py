"""s23 granted-job launcher with an actual receipt (light; the child does the pixel work).

  python -I run_granted.py --cpu 15 --cap 180 --receipt <run_dir>/receipt.json [--max-cpu 60 --min-free-gib 16] -- <child args...>

1. Precheck: system CPU% (psutil, 1 s sample) < --max-cpu and available RAM >= --min-free-gib, else NO start
   (receipt status "declined_precheck", exit code 3).
2. Start the child (the given python command) with env S23_CPU=<cpu>, OMP/OPENBLAS/MKL threads 1, BELOW_NORMAL
   priority and affinity [<cpu>] applied by this launcher immediately after spawn (the child also pins itself via
   s23lib.below_normal before pixel work). The child's PID and creation time are recorded at spawn, before it can exit.
3. Wait at most --cap seconds; on timeout terminate then kill the child tree (status "timeout").
4. After exit: record the numerical exit code, wall time, and whether the PID and any recorded children still exist.
Receipt fields are actual observations; nothing is inferred. The receipt is written atomically.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import psutil


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--cap", type=float, required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--max-cpu", type=float, default=60.0)
    ap.add_argument("--min-free-gib", type=float, default=16.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    assert cmd, "child command required after --"
    os.makedirs(os.path.dirname(os.path.abspath(a.receipt)), exist_ok=True)
    rec = dict(owner="claude-einhander-s23", launcher=os.path.abspath(__file__), cmd=cmd, cpu=a.cpu, cap_s=a.cap,
               precheck_utc=now())
    cpu_pct = psutil.cpu_percent(interval=1.0)
    free = psutil.virtual_memory().available / 2 ** 30
    rec["precheck"] = dict(cpu_percent=round(cpu_pct, 1), free_gib=round(free, 1), max_cpu=a.max_cpu, min_free_gib=a.min_free_gib,
                           ok=cpu_pct < a.max_cpu and free >= a.min_free_gib)

    def write():
        tmp = a.receipt + ".tmp"
        json.dump(rec, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, a.receipt)

    if not rec["precheck"]["ok"]:
        rec["status"] = "declined_precheck"
        write()
        print(json.dumps(dict(status=rec["status"], precheck=rec["precheck"])))
        sys.exit(3)
    env = dict(os.environ, S23_CPU=str(a.cpu), OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    flags = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, env=env, creationflags=flags)
    rec["start_utc"] = now()
    rec["pid"] = p.pid
    try:
        pp = psutil.Process(p.pid)
        rec["pid_create_utc"] = datetime.fromtimestamp(pp.create_time(), timezone.utc).isoformat()
        pp.cpu_affinity([a.cpu])
        rec["affinity_after_spawn"] = pp.cpu_affinity()
        rec["priority_after_spawn"] = int(pp.nice())
    except psutil.Error as e:
        rec["spawn_observation_error"] = repr(e)
    write()
    print(json.dumps(dict(status="started", pid=p.pid, create=rec.get("pid_create_utc"), affinity=rec.get("affinity_after_spawn"))), flush=True)
    children = {}            # pid -> create_time (identity; Windows reuses PIDs)
    status = "exited"
    own_create = None
    try:
        own_create = psutil.Process(p.pid).create_time()
    except psutil.Error:
        pass

    def same(pid, ctime):
        try:
            return ctime is not None and psutil.Process(pid).create_time() == ctime
        except psutil.Error:
            return False
    while True:
        try:
            for c in psutil.Process(p.pid).children(recursive=True):
                if c.pid not in children:
                    children[c.pid] = c.create_time()
        except psutil.Error:
            pass
        rc = p.poll()
        if rc is not None:
            break
        if time.monotonic() - t0 > a.cap:
            status = "timeout"
            for c, ct in list(children.items()):
                if same(c, ct):              # never kill a recycled, unrelated PID
                    try:
                        psutil.Process(c).kill()
                    except psutil.Error:
                        pass
            p.terminate()                    # tracked Popen handle of the direct child
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(5)
            break
        time.sleep(0.2)
    rec["status"] = status
    rec["exit_code"] = p.returncode
    rec["wall_s"] = round(time.monotonic() - t0, 2)
    rec["end_utc"] = now()
    time.sleep(0.5)
    rec["pid_exists_after"] = same(p.pid, own_create)          # identity-aware: same PID AND same creation time
    rec["pid_number_reused_by_other_process"] = psutil.pid_exists(p.pid) and not rec["pid_exists_after"]
    rec["children_seen"] = [dict(pid=c, create_time=ct) for c, ct in sorted(children.items())]
    rec["children_alive_after"] = sorted(c for c, ct in children.items() if same(c, ct))
    write()
    print(json.dumps(dict(status=status, exit_code=p.returncode, wall_s=rec["wall_s"], pid=p.pid, pid_exists_after=rec["pid_exists_after"],
                          children_alive_after=rec["children_alive_after"])))
    sys.exit(0 if status == "exited" and p.returncode == 0 else 1)


if __name__ == "__main__":
    main()
