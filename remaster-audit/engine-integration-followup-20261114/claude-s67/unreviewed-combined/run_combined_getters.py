"""s67 bounded CPU driver for test_combined_getters.cpp (NOT run yet).

MANDATORY: run only under a fresh grant, inside the qualified outer Job (wall <= 120 s, memory 1024 MiB,
one CPU, BelowNormal). The outer Job is what bounds the whole tree: this driver's own timeouts are inner
guards only, and an outer kill can prevent manifest.json from being written - the wrapper's own
refusal/kill receipt then counts as FAILURE. Refuses to start without --grant-id.

Steps:
  1. --out resolved absolute, created exclusively (parent must exist);
  2. copies harness, extracted getter block, combined header and combined main.cpp into <out>/src;
     every copy is hashed and must equal its pin; compiler binary pinned via --cc-sha256;
  3. re-extracts the getter block from the COPIED main.cpp (exact BEGIN/END markers) and byte-compares
     it with the copied .inc - the harness therefore runs the proposed code, not a stale cut;
  4. compiles the copies only (C++17, -O2), hidden + BelowNormal, single-thread env, 60 s inner timeout;
  5. runs the harness, 60 s inner timeout; records pid, start UTC, argv, elapsed, rc, timeout, output;
  6. verdict PASS only if: compile rc 0, run rc 0, last stdout JSON has result PASS,
     negative_controls_fired == 3, and all viol_* == 0. manifest.json written in try/finally.
Exit code 0 only on PASS.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED = {  # name: (source file next to this driver, pinned sha256 or None = given on the command line)
    "harness": (HERE / "test_combined_getters.cpp", None),
    "getters_inc": (HERE / "combined_getters.extracted.inc", "ed046b2bb357f61567d794915f26bc3eb5b9e618226ddbc0f753b7ea59fa671f"),
    "header": (HERE / "recomp_audio_drc.h.proposed", "0022c3bc8704439b50ead84b12ee7e123e79be331e2194a9578ee6292cd8a5e6"),
    "main_cpp": (HERE / "main.cpp.proposed", "57f915a48f156eb7e99e23b0a36ae259dcd9d9ced179ed0808842f30fbc1d234"),
}
BEGIN, END = "/* s67 combined getters: BEGIN */", "/* s67 combined getters: END */"
CREATIONFLAGS = 0x08004000 if os.name == "nt" else 0   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
COMPILE_TIMEOUT_S, RUN_TIMEOUT_S = 60, 60


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_child(argv, timeout):
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    rec = {"argv": [str(x) for x in argv], "start_utc": utc(), "pid": None, "rc": None, "timed_out": False}
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATIONFLAGS, env=env)
    rec["pid"] = p.pid
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        rec["timed_out"] = True
        p.kill()
        out, err = p.communicate()   # bounded only by the outer Job
    rec["rc"] = p.returncode
    rec["elapsed_s"] = round(time.monotonic() - t0, 3)
    rec["stdout"] = out.decode("utf-8", errors="replace")
    rec["stderr"] = err.decode("utf-8", errors="replace")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--cc", required=True, help="clang++ (or equivalent C++17 compiler) binary")
    ap.add_argument("--cc-sha256", required=True)
    ap.add_argument("--harness-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    try:
        out.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        print(f"refusing: {out} exists", file=sys.stderr)
        return 2
    man = {"driver": "run_combined_getters.py", "driver_sha256": sha(__file__), "grant_id": a.grant_id,
           "out": str(out), "started_utc": utc(), "inputs": {}, "children": [], "verdict": "FAIL",
           "reasons": [], "errors": [], "note": "outer Job receipt is authoritative for wall/memory limits"}
    code = 1
    try:
        code = body(a, out, man)
    except Exception:
        man["errors"].append(traceback.format_exc())
        code = 1
    finally:
        if man["reasons"] or man["errors"]:
            man["verdict"] = "FAIL"
            code = code or 1
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
    dst_names = {"harness": "test_combined_getters.cpp", "getters_inc": "combined_getters.extracted.inc",
                 "header": "recomp_audio_drc.h", "main_cpp": "main.cpp.proposed"}
    copies = {}
    for k, (orig, want) in PINNED.items():
        want = want or a.harness_sha256
        dst = src / dst_names[k]
        shutil.copyfile(orig, dst)
        got = sha(dst)
        copies[k] = dst
        man["inputs"][k] = {"original": str(orig), "copy": str(dst), "copy_sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"pin mismatch: {k} (copy)")
    if man["reasons"]:
        return 2

    text = copies["main_cpp"].read_bytes().decode("utf-8").replace("\r\n", "\n")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        man["reasons"].append("getter markers not unique in copied main.cpp")
        return 2
    i = text.index(BEGIN)
    j = text.index(END) + len(END) + 1
    cut = text[i:j].encode("utf-8")
    inc = copies["getters_inc"].read_bytes()
    man["inputs"]["reextract_equal"] = (cut == inc)
    if cut != inc:
        man["reasons"].append("extracted getter block differs from copied main.cpp")
        return 2

    exe = out / ("test_combined_getters.exe" if os.name == "nt" else "test_combined_getters")
    argv = [cc, "-std=c++17", "-O2", "-Wall", f"-I{src}", copies["harness"], "-o", exe]
    if os.name != "nt":
        argv.append("-pthread")
    rec = run_child(argv, COMPILE_TIMEOUT_S)
    rec["step"] = "compile"
    man["children"].append(rec)
    if rec["timed_out"] or rec["rc"] != 0 or not exe.is_file():
        man["reasons"].append("compile failed")
        return 1
    man["inputs"]["exe"] = {"path": str(exe), "sha256": sha(exe)}

    rec = run_child([exe], RUN_TIMEOUT_S)
    rec["step"] = "run"
    man["children"].append(rec)
    if rec["timed_out"] or rec["rc"] != 0:
        man["reasons"].append(f"run failed rc={rec['rc']} timed_out={rec['timed_out']}")
    lines = [l for l in rec["stdout"].splitlines() if l.startswith("{")]
    if not lines:
        man["reasons"].append("no JSON result line")
        return 1
    try:
        res = json.loads(lines[-1])
    except json.JSONDecodeError as e:
        man["reasons"].append(f"bad JSON result: {e}")
        return 1
    man["result"] = res
    if res.get("result") != "PASS":
        man["reasons"].append("harness result not PASS")
    if res.get("negative_controls_fired") != 3:
        man["reasons"].append("negative controls did not all fire")
    for k in ("viol_mod37", "viol_coherence", "viol_gaps"):
        if res.get(k) != 0:
            man["reasons"].append(f"{k} != 0")
    if man["reasons"]:
        return 1
    man["verdict"] = "PASS"
    return 0


if __name__ == "__main__":
    sys.exit(main())
