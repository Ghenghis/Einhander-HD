#!/usr/bin/env python3
"""s45 J-F runner: started by `cmd start /belownormal /affinity 2000` (CPU 13 only, inherited by children); runs
tools/s45_cm_repair.py --probe-run <J-E run> --key K for four keys sequentially under one 28 s watchdog; records PIDs,
creation times, affinity, exits and child absence in s45/repairs/J-F-<UTC>.json."""
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
RUN = S45 / "probe-audit/20261114T141451Z-s5"
KEYS = ["1A2ACF78-0DA351E7", "3D108041-BE3400E6", "BFC445B0-066C0B81", "1168CC84-A345AE9E"]
BUDGET = 28.0


def main():
    import psutil
    t0 = time.time()
    me = psutil.Process()
    rec = dict(runner_pid=os.getpid(), runner_created=datetime.datetime.fromtimestamp(me.create_time(), datetime.timezone.utc).isoformat(),
               runner_affinity=me.cpu_affinity(), runner_priority=me.nice(), keys=[], budget_s=BUDGET)
    print("RUNNER PID", os.getpid(), "affinity", rec["runner_affinity"], "priority", rec["runner_priority"], flush=True)
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    for k in KEYS:
        left = BUDGET - (time.time() - t0)
        if left < 3:
            rec["keys"].append(dict(key=k, skipped="watchdog budget"))
            continue
        p = subprocess.Popen([sys.executable, "-I", "-B", str(S45 / "tools/s45_cm_repair.py"), "--probe-run", str(RUN), "--key", k],
                             cwd=str(S45), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            cp = psutil.Process(p.pid)
            info = dict(pid=p.pid, created=datetime.datetime.fromtimestamp(cp.create_time(), datetime.timezone.utc).isoformat(),
                        affinity=cp.cpu_affinity(), priority=cp.nice())
        except Exception as e:  # noqa: BLE001
            info = dict(pid=p.pid, note=f"inspect failed: {e}")
        print("CHILD", k, info, flush=True)
        try:
            out, _ = p.communicate(timeout=left)
            info.update(returncode=p.returncode, output=out[-3000:])
        except subprocess.TimeoutExpired:
            for c in psutil.Process(p.pid).children(recursive=True):
                c.kill()
            p.kill()
            out, _ = p.communicate()
            info.update(returncode="killed-watchdog", output=(out or "")[-3000:])
        info["key"] = k
        rec["keys"].append(info)
        print(k, "rc", info["returncode"], flush=True)
        del p   # release the Popen process handle: on Windows an open handle keeps the exited process object visible
    # child absence, checked after every Popen handle is released (the J-F 14:36Z record checked too early: a race)
    import gc
    gc.collect()
    for info in rec["keys"]:
        if "pid" in info:
            info["child_absent_after"] = not psutil.pid_exists(info["pid"])
    rec["seconds"] = round(time.time() - t0, 1)
    rec["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (S45 / "repairs" / f"J-F-{stamp}.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print("DONE seconds", rec["seconds"], "record", f"repairs/J-F-{stamp}.json", flush=True)


if __name__ == "__main__":
    main()
