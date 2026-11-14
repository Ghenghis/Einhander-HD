#!/usr/bin/env python3
"""s45: one-page equivalence check of the merged W7 tools (tools/w7m) against a frozen lane deliverable built by the
current lane tools. READ-ONLY on the lanes: the job copy is re-rooted to
remaster-audit/parallel-stages-20261114/s45/verify-w7m/<UTC>-<set>-<TEX>/ (job name and seeds unchanged, pages = [TEX]).

    python -I -B tools/s45_w7m_verify.py --ref <frozen set dir> --job <lane job.json> --tex <TEX> [--timeout 150]

The build runs as a child process: below normal, one logical CPU, OMP/BLAS threads 1, hard timeout. Comparison:
runtime-2048 / runtime-1024 / review PNGs and master .npy by sha256; master .npz by array equality (zip entries carry
timestamps). PASS = every reference file of that page has an identical counterpart."""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
W7M = S45 / "tools/w7m"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--job", required=True)
    ap.add_argument("--tex", required=True)
    ap.add_argument("--timeout", type=float, default=150.0)
    a = ap.parse_args()
    import psutil
    ref = Path(a.ref)
    job = json.loads(Path(a.job).read_text(encoding="utf-8"))
    assert (ref / "manifest.json").is_file(), "reference must be a frozen set"
    pages = [p for p in job["pages"] if p["tex"] == a.tex]
    assert len(pages) == 1, f"{a.tex} not in job"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "verify-w7m" / f"{stamp}-{job['name']}-{a.tex}"
    rd.mkdir(parents=True, exist_ok=False)
    vj = dict(job, root=str(rd).replace("\\", "/"), pages=pages)
    jp = rd / f"{job['name']}.json"
    jp.write_text(json.dumps(vj, indent=1) + "\n", encoding="utf-8")
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-I", "-B", str(W7M / "build_w7.py"), str(jp)], cwd=str(rd), env=env,
                         stdout=open(rd / "build.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                         creationflags=0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    try:
        psutil.Process(p.pid).cpu_affinity([psutil.Process().cpu_affinity()[-1]])
    except Exception as e:  # noqa: BLE001
        print("affinity not set:", e)
    print("build PID", p.pid, "run", rd, flush=True)
    try:
        rc = p.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "timeout-killed"
    secs = round(time.time() - t0, 1)
    out = rd / job["name"]
    rows, ok = [], rc == 0
    for rf in sorted(ref.rglob("*")):
        rel = rf.relative_to(ref).as_posix()
        if not rf.is_file() or a.tex not in rf.name:
            continue
        if not (rel.startswith("runtime-") or rel.startswith("master/") or rel.startswith("review/")):
            continue
        nf = out / rel
        r = dict(file=rel, ref_sha256=sha(rf), exists=nf.is_file())
        if nf.is_file():
            if rf.suffix == ".npz":
                with np.load(rf) as A, np.load(nf) as Bz:
                    r["arrays_equal"] = sorted(A.files) == sorted(Bz.files) and all(np.array_equal(A[k], Bz[k]) for k in A.files)
                r["identical"] = r["arrays_equal"]
            else:
                r["new_sha256"] = sha(nf)
                r["identical"] = r["new_sha256"] == r["ref_sha256"]
        else:
            r["identical"] = False
        ok = ok and r["identical"]
        rows.append(r)
    res = dict(run=rd.name, owner="claude-einhander-s45", ref=str(ref), job=str(a.job), tex=a.tex, build_pid=p.pid,
               returncode=rc, seconds=secs, w7m=json.loads((W7M / "MERGE-RECORD.json").read_text(encoding="utf-8"))["outputs"],
               files=rows, compared=len(rows), identical=sum(r["identical"] for r in rows), PASS=bool(ok and rows),
               status="tool-equivalence check only; not art acceptance")
    (rd / "verify.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print("PASS" if res["PASS"] else "FAIL", f"{res['identical']}/{res['compared']}", "rc", rc, f"{secs}s", "verify.json", sha(rd / "verify.json"))


if __name__ == "__main__":
    main()
