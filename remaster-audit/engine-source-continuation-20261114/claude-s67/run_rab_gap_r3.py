"""s67 bounded CPU host driver r3 for test_rab_gap_r3.c (NOT run yet). Supersedes run_rab_gap_r2.py (kept).

Run ONLY under a fresh shared-resource CPU grant, inside the qualified outer Job wrapper (which holds the
time/memory limits for the whole child tree). It refuses to start without --grant-id.

r3 changes vs r2 (main's msg_f87bcc5b):
  - manifest.json is written in try/finally; any unexpected exception (JSON, IO, subprocess, hashing,
    copying) is recorded as an error with its traceback and the verdict stays FAIL;
  - each child (compiler, test exe) is started hidden at BelowNormal priority
    (creationflags 0x08004000 = CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS on Windows) with
    single-thread env (OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1); PID, start UTC, actual argv, elapsed
    seconds, return code and timeout status are recorded per child;
  - --out is resolved to an absolute path and created exclusively (mkdir exist_ok=False);
  - the fixture and both headers are COPIED into <out>/src first; the copies are hashed and must match
    the pins; the compiler is then run only on those copies (the mutable originals are never re-read).

Acceptance: both builds compile and exit 0; exact 7 case names in order; per-case .pcm SHA-256 identical
base vs patched; per-case old-counter marks identical base vs patched. Exit code 0 only on PASS.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_HEADER = Path(r"C:/github/Einhander/windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h")
BASE_HEADER_SHA = "70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29"
PATCHED_HEADER = HERE / "recomp_audio_drc.h.proposed"
PATCHED_HEADER_SHA = "7de21fb8aac0f442bf50b0259257b4768480c89b21ce8aeba6753339f1f371c9"
FIXTURE = HERE / "test_rab_gap_r3.c"
CASES = ["unprimed_starvation", "one_gap", "recovery", "multiple_gaps",
         "gap_split_across_callbacks", "mute_then_unmute_reset", "reset_by_init"]
CREATIONFLAGS = 0x08004000 if os.name == "nt" else 0
COMPILE_TIMEOUT_S, RUN_TIMEOUT_S = 60, 30


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def child_env():
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    return env


def run_child(argv, timeout):
    rec = {"argv": [str(x) for x in argv], "start_utc": utc(), "pid": None, "rc": None, "timed_out": False}
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATIONFLAGS, env=child_env())
    rec["pid"] = p.pid
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        rec["timed_out"] = True
        p.kill()
        out, err = p.communicate()
    rec["rc"] = p.returncode
    rec["elapsed_s"] = round(time.monotonic() - t0, 3)
    rec["stdout"] = out.decode("utf-8", errors="replace")
    rec["stderr"] = err.decode("utf-8", errors="replace")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--cc", required=True)
    ap.add_argument("--cc-sha256", required=True)
    ap.add_argument("--fixture-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = Path(a.out).resolve()
    try:
        out.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        print(f"refusing: {out} exists", file=sys.stderr)
        return 2
    man = {"driver": "run_rab_gap_r3.py", "driver_sha256": sha(__file__), "grant_id": a.grant_id,
           "out": str(out), "started_utc": utc(), "inputs": {}, "children": [], "cases": {},
           "verdict": "FAIL", "reasons": [], "errors": []}
    code = 1
    try:
        code = body(a, out, man)
    except Exception:
        man["errors"].append(traceback.format_exc())
        code = 1
    finally:
        if man["reasons"] or man["errors"]:
            man["verdict"] = "FAIL"
            if code == 0:
                code = 1
        man["finished_utc"] = utc()
        (out / "manifest.json").write_bytes(json.dumps(man, indent=2).encode("utf-8"))
    return code


def body(a, out, man):
    cc = Path(a.cc)
    got = sha(cc) if cc.is_file() else None
    man["inputs"]["cc"] = {"path": str(cc), "sha256": got, "expected": a.cc_sha256}
    if got != a.cc_sha256:
        man["reasons"].append("pin mismatch: cc")
        return 2

    src = out / "src"
    src.mkdir(exist_ok=False)
    copies = {
        "fixture": (FIXTURE, src / "test_rab_gap_r3.c", a.fixture_sha256),
        "base_header": (BASE_HEADER, src / "base_inc" / "recomp_audio_drc.h", BASE_HEADER_SHA),
        "patched_header": (PATCHED_HEADER, src / "patched_inc" / "recomp_audio_drc.h", PATCHED_HEADER_SHA),
    }
    for k, (orig, dst, want) in copies.items():
        dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(orig, dst)
        got = sha(dst)
        man["inputs"][k] = {"original": str(orig), "copy": str(dst), "copy_sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"pin mismatch: {k} (copy)")
    if man["reasons"]:
        return 2

    exe_ext = ".exe" if os.name == "nt" else ""
    builds = {}
    for name, extra in (("base", []), ("patched", ["-DRAB_HAS_GAP"])):
        inc = copies[f"{name}_header"][1].parent
        exe = out / f"{name}{exe_ext}"
        argv = [cc, "-O2", "-std=c11", "-Wall", *extra, f"-I{inc}", copies["fixture"][1], "-o", exe]
        if os.name != "nt":
            argv.append("-lm")
        rec = run_child(argv, COMPILE_TIMEOUT_S)
        rec["step"] = f"compile:{name}"
        man["children"].append(rec)
        if rec["timed_out"] or rec["rc"] != 0 or not exe.is_file():
            man["reasons"].append(f"compile failed: {name}")
            return 1
        man["inputs"][f"{name}_exe"] = {"path": str(exe), "sha256": sha(exe)}

        rundir = out / f"{name}_run"
        rundir.mkdir(exist_ok=False)
        rec = run_child([exe, rundir], RUN_TIMEOUT_S)
        rec["step"] = f"run:{name}"
        man["children"].append(rec)
        if rec["timed_out"] or rec["rc"] != 0:
            man["reasons"].append(f"run failed or checks failed: {name} rc={rec['rc']} timed_out={rec['timed_out']}")
        lines = []
        for ln in rec["stdout"].splitlines():
            if ln.startswith("{"):
                try:
                    lines.append(json.loads(ln))
                except json.JSONDecodeError as e:
                    man["reasons"].append(f"bad JSON line in {name}: {e}")
        builds[name] = {"lines": lines, "dir": rundir}

    for name in ("base", "patched"):
        got = [l.get("case") for l in builds[name]["lines"]]
        if got != CASES:
            man["reasons"].append(f"case list mismatch in {name}: {got}")
    for i, case in enumerate(CASES):
        rec = {}
        for name in ("base", "patched"):
            p = builds[name]["dir"] / f"{case}.pcm"
            ls = builds[name]["lines"]
            rec[name] = {"pcm_sha256": sha(p) if p.is_file() else None,
                         "pcm_bytes": p.stat().st_size if p.is_file() else None,
                         "line": ls[i] if i < len(ls) else None}
        b, q = rec["base"], rec["patched"]
        rec["pcm_equal"] = b["pcm_sha256"] is not None and b["pcm_sha256"] == q["pcm_sha256"]
        bm = (b["line"] or {}).get("marks")
        rec["old_counter_marks_equal"] = bm is not None and bm == (q["line"] or {}).get("marks")
        if not rec["pcm_equal"]:
            man["reasons"].append(f"pcm differs or missing: {case}")
        if not rec["old_counter_marks_equal"]:
            man["reasons"].append(f"old-counter marks differ or missing: {case}")
        man["cases"][case] = rec

    if man["reasons"]:
        return 1
    man["verdict"] = "PASS"
    return 0


if __name__ == "__main__":
    sys.exit(main())
