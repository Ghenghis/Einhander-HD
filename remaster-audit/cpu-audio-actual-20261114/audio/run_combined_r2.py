"""s67 bounded CPU driver r2 for BOTH combined-telemetry harnesses (NOT run yet). r1 73b764af and r0 90b00802 kept.
r2 vs r1 (main msg_e4fbf475): the compiler is a FIXED path and its real dispatch closure is pinned - clang++.exe,
clang-22.exe, libclang-cpp.dll, libLLVM-22.dll - with the same 4 pins as primary's T1 driver r2 (b0423d8a), all
hashed in realpath(CC).parent before any compile; --cc/--cc-sha256 are removed. Child creation time is recorded
best-effort via psutil (None + reason if psutil is missing or the process already exited; never fabricated).
The compiler is hashed then executed by path; a swap in between is not excluded.

MANDATORY: run only under a fresh grant, inside the qualified outer Job (wall <= 120 s, 1024 MiB, one CPU,
BelowNormal). The outer Job bounds the whole process tree. This driver's inner caps are sized to fit inside
it: a global envelope of 105 s covers 2 compiles + 2 runs (each step's timeout = min(step cap, time left);
a step is refused and recorded as a failure if fewer than 5 s remain). An outer kill can still prevent
manifest.json from being written; the wrapper's kill/refusal receipt then counts as FAILURE.

Steps (refuses without --grant-id; --out created exclusively; fixed CC + 4-file toolchain closure pinned):
  1. copy into <out>/src: getters harness r1, pump harness, combined header r1, main.cpp r1, both .inc files;
     every copy hashed against its pin;
  2. re-extract BOTH blocks from the COPIED main.cpp (getters BEGIN/END markers; pump helper by its unique
     signature line) and byte-compare with the copied .inc files;
  3. compile getters harness, run it; compile pump harness, run it (copies only; hidden + BelowNormal;
     single-thread env); every step gets a receipt with pid, start_utc, argv, elapsed_s, rc, timed_out,
     timeout_s, stdout, stderr - all required;
  4. strict result checks (required fields, exact values) per harness; verdict PASS only if every step
     receipt is complete, both compiles and runs exit 0, and both result objects pass.
Exit code 0 only on PASS. manifest.json written in try/finally.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED = {  # key: (file next to this driver, copy name, pinned sha256; None = from --getters-harness-sha256)
    "getters_harness": ("test_combined_getters_r1.cpp", "test_combined_getters_r1.cpp", None),
    "pump_harness": ("test_pump_after_push.cpp", "test_pump_after_push.cpp",
                     "e6355f83142dbc776443915330a859770a2c1739708f408b6f261ad8f10d452d"),
    "getters_inc": ("combined_getters.extracted.inc", "combined_getters.extracted.inc",
                    "fa7feb4b4540a7614b12ba760dcdc09a2c3424a8f38a6f9eea16ab759ef68d3f"),
    "pump_inc": ("pump_after_push.extracted.inc", "pump_after_push.extracted.inc",
                 "2ca3702e8b1cd500e0141ee74f85e0a93bd3c36347d17f26d7653ce313a183d6"),
    "header": ("recomp_audio_drc.h.proposed", "recomp_audio_drc.h",
               "c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c"),
    "main_cpp": ("main.cpp.proposed", "main.cpp.proposed",
                 "8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36"),
}
BEGIN, END = "/* s67 combined getters: BEGIN */", "/* s67 combined getters: END */"
PUMP_SIG = "static void s67_pump_after_push(const rab_telemetry *tel, int resync) {"
CREATIONFLAGS = 0x08004000 if os.name == "nt" else 0   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")
TOOLCHAIN = {  # identical to remix-transport/t1/build_t1_fixture.r2.py (b0423d8a) TOOLCHAIN
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
try:
    import psutil  # optional: best-effort child creation time only
except ImportError:
    psutil = None
ENVELOPE_S = 105
# 25 + 35 + 25 + 10 = 95 s <= ENVELOPE_S 105 s <= outer Job 120 s. The getters run cap covers its own
# internal bounds (writer start 5 s + phase C 20 s + stop 5 s = 30 s) plus margin.
CAPS = {"compile:getters": 25, "run:getters": 35, "compile:pump": 25, "run:pump": 10}
REQUIRED_RECEIPT = ("step", "argv", "start_utc", "pid", "rc", "timed_out", "timeout_s", "elapsed_s", "stdout", "stderr")


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Budget:
    def __init__(self):
        self.t0 = time.monotonic()

    def left(self):
        return ENVELOPE_S - (time.monotonic() - self.t0)


def run_child(step, argv, cap, budget, man):
    left = budget.left()
    if left < 5:
        man["reasons"].append(f"envelope exhausted before {step} ({left:.1f} s left)")
        return None
    timeout = min(cap, left)
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    rec = {"step": step, "argv": [str(x) for x in argv], "start_utc": utc(), "pid": None, "rc": None,
           "timed_out": False, "timeout_s": round(timeout, 1)}
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATIONFLAGS, env=env)
    rec["pid"] = p.pid
    rec["creation_unix"] = None
    if psutil is None:
        rec["creation_note"] = "psutil not installed"
    else:
        try:
            rec["creation_unix"] = psutil.Process(p.pid).create_time()
        except psutil.Error as e:
            rec["creation_note"] = f"unavailable: {type(e).__name__} (process may have exited)"
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
    man["children"].append(rec)
    missing = [k for k in REQUIRED_RECEIPT if k not in rec or rec[k] is None and k != "rc"]
    if missing or rec["rc"] is None:
        man["reasons"].append(f"incomplete receipt for {step}: {missing}")
    return rec


def last_json(rec, man, step):
    lines = [l for l in rec["stdout"].splitlines() if l.startswith("{")]
    if not lines:
        man["reasons"].append(f"{step}: no JSON result line")
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as e:
        man["reasons"].append(f"{step}: bad JSON ({e})")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--getters-harness-sha256", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    try:
        out.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        print(f"refusing: {out} exists", file=sys.stderr)
        return 2
    man = {"driver": "run_combined_r2.py", "driver_sha256": sha(__file__), "grant_id": a.grant_id,
           "out": str(out), "started_utc": utc(), "envelope_s": ENVELOPE_S, "caps_s": CAPS,
           "inputs": {}, "children": [], "results": {}, "verdict": "FAIL", "reasons": [], "errors": [],
           "note": "outer Job receipt is authoritative for wall/memory limits"}
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
    budget = Budget()
    cc = CC
    real_dir = Path(os.path.realpath(CC)).parent
    tools = {}
    for n, want in TOOLCHAIN.items():
        f = real_dir / n
        got = sha(f) if f.is_file() else None
        tools[n] = {"path": str(f), "sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"toolchain pin mismatch: {n}")
    invoked = sha(CC) if CC.is_file() else None
    man["inputs"]["toolchain"] = {"invoked": str(CC), "invoked_sha256": invoked, "real_dir": str(real_dir), "files": tools}
    if invoked != TOOLCHAIN["clang++.exe"]:
        man["reasons"].append("toolchain pin mismatch: invoked clang++.exe")
    if man["reasons"]:
        return 2
    src = out / "src"
    src.mkdir(exist_ok=False)
    copies = {}
    for k, (name, dst_name, want) in PINNED.items():
        want = want or a.getters_harness_sha256
        dst = src / dst_name
        shutil.copyfile(HERE / name, dst)
        got = sha(dst)
        copies[k] = dst
        man["inputs"][k] = {"original": str(HERE / name), "copy": str(dst), "copy_sha256": got, "expected": want}
        if got != want:
            man["reasons"].append(f"pin mismatch: {k} (copy)")
    if man["reasons"]:
        return 2

    text = copies["main_cpp"].read_bytes().decode("utf-8").replace("\r\n", "\n")
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.count(PUMP_SIG) != 1:
        man["reasons"].append("extraction anchors not unique in copied main.cpp")
        return 2
    i = text.index(BEGIN); j = text.index(END) + len(END) + 1
    k = text.index(PUMP_SIG); l = text.index("\n}\n", k) + 3
    man["inputs"]["getters_reextract_equal"] = text[i:j].encode() == copies["getters_inc"].read_bytes()
    man["inputs"]["pump_reextract_equal"] = text[k:l].encode() == copies["pump_inc"].read_bytes()
    if not (man["inputs"]["getters_reextract_equal"] and man["inputs"]["pump_reextract_equal"]):
        man["reasons"].append("an extracted block differs from the copied main.cpp")
        return 2

    ext = ".exe" if os.name == "nt" else ""
    plan = [("getters", copies["getters_harness"], out / f"test_combined_getters_r1{ext}"),
            ("pump", copies["pump_harness"], out / f"test_pump_after_push{ext}")]
    for name, srcfile, exe in plan:
        argv = [cc, "-std=c++17", "-O2", "-Wall", f"-I{src}", srcfile, "-o", exe]
        if os.name != "nt":
            argv.append("-pthread")
        rec = run_child(f"compile:{name}", argv, CAPS[f"compile:{name}"], budget, man)
        if rec is None or rec["timed_out"] or rec["rc"] != 0 or not exe.is_file():
            man["reasons"].append(f"compile failed: {name}")
            return 1
        man["inputs"][f"{name}_exe"] = {"path": str(exe), "sha256": sha(exe)}
        rec = run_child(f"run:{name}", [exe], CAPS[f"run:{name}"], budget, man)
        if rec is None:
            return 1
        if rec["timed_out"] or rec["rc"] != 0:
            man["reasons"].append(f"run failed: {name} rc={rec['rc']} timed_out={rec['timed_out']}")
        res = last_json(rec, man, name)
        man["results"][name] = res
        if res is None:
            continue
        if name == "getters":
            need = {"result": "PASS", "negative_controls_fired": 3, "viol_mod37": 0, "viol_coherence": 0, "viol_gaps": 0}
            for f, v in need.items():
                if res.get(f) != v:
                    man["reasons"].append(f"getters: {f}={res.get(f)!r}, required {v!r}")
            for f, lo in (("reads", 200000), ("pulls_during_C", 1000), ("distinct", 100)):
                if not isinstance(res.get(f), int) or res[f] < lo:
                    man["reasons"].append(f"getters: {f}={res.get(f)!r}, required >= {lo}")
        else:
            for f, v in {"result": "PASS", "events": 4}.items():
                if res.get(f) != v:
                    man["reasons"].append(f"pump: {f}={res.get(f)!r}, required {v!r}")
    if man["reasons"]:
        return 1
    man["verdict"] = "PASS"
    return 0


if __name__ == "__main__":
    sys.exit(main())
