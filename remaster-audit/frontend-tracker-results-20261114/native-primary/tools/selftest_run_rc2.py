"""Bounded self-test of run_rc2.py r1 (claude-einhander). Run only under an explicit CPU grant.
Usage: python selftest_run_rc2.py --cpu N --wrapper PATH/run_rc2.py --out-root DIR
Four controls, each < 10 s and near-zero CPU (sleep-based):
  C1 exit7     child exits 7            -> wrapper exit 7, child_exit_code 7, job total 1 / active 0, tree_absent
  C2 tree      child spawns a sleeping grandchild; --timeout 3 -> wrapper exit 124, timeout_killed, job total >= 2,
               active 0, grandchild seen and independently absent afterwards, child absent
  C3 decline   --max-cpu 0               -> wrapper exit 3, declined, no child created
  C4 fault     RUN_RC2_FAULT=after_spawn -> wrapper exit 125, injected error recorded, suspended child killed and
               absent, job empty
Writes DIR/<stamp>/summary.json (fsync); exit 0 only if all four pass."""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def gone(pid, ctime):
    if not psutil.pid_exists(pid):
        return True
    try:
        return ctime is not None and psutil.Process(pid).create_time() != ctime
    except psutil.NoSuchProcess:
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--wrapper", required=True)
    ap.add_argument("--out-root", required=True)
    a = ap.parse_args()
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([a.cpu])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out_root) / stamp
    out.mkdir(parents=True, exist_ok=False)
    py = sys.executable
    grandchild = ("import subprocess,sys,time;"
                  "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);time.sleep(60)")
    cases = {
        "C1_exit7": dict(args=["--timeout", "30"], cmd=[py, "-c", "import sys; sys.exit(7)"], env={}),
        "C2_tree_timeout": dict(args=["--timeout", "3"], cmd=[py, "-c", grandchild], env={}),
        "C3_decline": dict(args=["--timeout", "30", "--max-cpu", "0"], cmd=[py, "-c", "print('must not run')"], env={}),
        "C4_fault_after_spawn": dict(args=["--timeout", "30"], cmd=[py, "-c", "print('must not run')"],
                                     env={"RUN_RC2_FAULT": "after_spawn"}),
    }
    summary = dict(tool="selftest_run_rc2.py", harness_pid=me.pid, cpu=a.cpu, wrapper=str(Path(a.wrapper).resolve()),
                   started_utc=now(), cases={})
    for name, c in cases.items():
        rc_path = out / f"{name}.rc.json"
        t = time.monotonic()
        r = subprocess.run([py, a.wrapper, "--out", str(rc_path), "--cpu", str(a.cpu), *c["args"], "--", *c["cmd"]],
                           env=dict(os.environ, **c["env"]), capture_output=True, text=True, timeout=60)
        wall = round(time.monotonic() - t, 3)
        rec = json.loads(rc_path.read_text(encoding="utf-8")) if rc_path.exists() else {}
        job = rec.get("job", {})
        checks = {}
        if name == "C1_exit7":
            checks = dict(wrapper_exit_7=r.returncode == 7, child_exit_7=rec.get("child_exit_code") == 7,
                          job_total_1=job.get("total") == 1, job_active_0=job.get("active") == 0,
                          tree_absent=rec.get("tree_absent") is True, not_timeout=rec.get("timeout_killed") is False)
        elif name == "C2_tree_timeout":
            seen = rec.get("descendants_seen", [])
            checks = dict(wrapper_exit_124=r.returncode == 124, timeout_killed=rec.get("timeout_killed") is True,
                          job_total_ge2=(job.get("total") or 0) >= 2, job_active_0=job.get("active") == 0,
                          grandchild_seen=len(seen) >= 1, descendants_left_empty=rec.get("descendants_left") == [],
                          child_absent=rec.get("child_absent") is True,
                          independent_grandchild_absent=all(not psutil.pid_exists(pid) for pid in seen),
                          elapsed_3_to_8=3.0 <= (rec.get("elapsed_s") or 0) <= 8.0)
        elif name == "C3_decline":
            checks = dict(wrapper_exit_3=r.returncode == 3, declined=rec.get("declined") is True,
                          no_child=rec.get("child_pid") is None, no_job=("job" not in rec))
        elif name == "C4_fault_after_spawn":
            checks = dict(wrapper_exit_125=r.returncode == 125,
                          injected_recorded="after_spawn" in str(rec.get("wrapper_error", "")),
                          assigned_before_fault=rec.get("job_assigned_before_resume") is True,
                          child_killed=rec.get("child_exit_code") is not None,
                          child_absent=rec.get("child_absent") is True, job_empty=rec.get("job_empty") is True,
                          no_start=("start_utc" not in rec),
                          independent_child_absent=(rec.get("child_pid") is not None
                                                    and gone(rec["child_pid"], rec.get("child_create_time"))))
        summary["cases"][name] = dict(passed=all(checks.values()) and bool(checks), checks=checks,
                                      wrapper_exit=r.returncode, wall_s=wall, stderr=r.stderr[-400:],
                                      rc_json=rc_path.name)
    summary["passed"] = all(v["passed"] for v in summary["cases"].values())
    summary["ended_utc"] = now()
    p = out / "summary.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(dict(out=str(out), passed=summary["passed"],
                          cases={k: v["passed"] for k, v in summary["cases"].items()})))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
