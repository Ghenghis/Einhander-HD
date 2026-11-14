"""s67 bounded CPU host driver r5 for test_rab_gap_r3.c (NOT run yet).
SUPERSEDES run_rab_gap_r4.py (5d75f375) and r3 (3f74854d), both kept unchanged, for all future jobs.
r5 vs r4 (main msg_31a8a05c), one change only: the PATCHED build now uses the CURRENT COMBINED integration
candidate header audio-telemetry-combined-r1/recomp_audio_drc.h.proposed (c84258e1), not the old gap-only
header (7de21fb8). Same fixture 397202b9, same 7 cases, same base header 70cb5acd, same 2 compiles + 2 runs in
one job under the 105 s envelope. This qualifies PCM bit identity and the legacy underrun counter of the current
combined header; the combined getter/pump/baseline logic is covered by run_combined_r2.py (a3def870).
r4 text below is unchanged except the patched-header pin and the driver name.

r4 history: r4 superseded r3, whose compiler backend was unqualified (it pinned only the binary passed with --cc).

Run ONLY under a fresh grant, inside the qualified outer Job (wall <= 120 s, 1024 MiB, one CPU, BelowNormal). The
outer Job bounds the whole process tree and its kill/refusal receipt counts as FAILURE (an outer kill can prevent
manifest.json). This driver's inner caps fit inside it: global envelope 105 s for 2 compiles + 2 runs, each step's
timeout = min(step cap, time left), a step is refused (FAIL) if < 5 s remain. Refuses without --grant-id.

r4 vs r3 (main msg_bd36c213):
  - fixed C launcher C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe, pinned
    separately (16896 bytes, mtime 2026-06-16 19:21:19 -0700, read and hashed 2026-11-14T21:04:05Z; byte-identical
    to clang++.exe - the launcher selects C mode from its invoked name, so it is invoked by this exact path), plus
    the same 3 backend pins as T1 driver r2 (b0423d8a) / combined Dr2 (a3def870): clang-22.exe, libclang-cpp.dll,
    libLLVM-22.dll, all hashed in realpath(CC).parent before any compile; --cc/--cc-sha256 removed;
  - every source pin is a constant (fixture 397202b9, original header 70cb5acd, proposed header 7de21fb8);
    --fixture-sha256 removed;
  - read-once byte checks: each input is read ONCE, those bytes are hashed against the pin and written to <out>/src;
    the written file is re-hashed and must match; the compiler only ever reads the copies;
  - per-step caps 25/15/25/15 s under a 105 s envelope; per-child creation_unix best-effort via optional psutil
    (None + reason, never fabricated).
Unchanged from r3: C11 frontend flags (-O2 -std=c11 -Wall, -DRAB_HAS_GAP for patched), hidden BelowNormal children
(0x08004000), single-thread env, exclusive absolute --out, manifest in try/finally, acceptance = both builds exit 0,
exact 7 case names in order, per-case PCM SHA-256 base == patched (PCM bit identity), per-case old-counter
(legacy underrun_events) marks base == patched. The compiler is hashed then executed by path; a swap in between is
not excluded.
"""
import argparse, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path

try:
    import psutil  # optional: best-effort child creation time only
except ImportError:
    psutil = None

HERE = Path(__file__).resolve().parent
SOURCES = {  # key: (path, pinned sha256, copy path relative to <out>/src)
    "fixture": (HERE / "test_rab_gap_r3.c",
                "397202b9c22631a1732dada485c833bac727c5c5d4afda5dccb49f454c97aecf", "test_rab_gap_r3.c"),
    "base_header": (Path(r"C:/github/Einhander/windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h"),
                    "70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29", "base_inc/recomp_audio_drc.h"),
    "patched_header": (Path(r"C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/proposals/"
                            r"audio-telemetry-combined-r1/recomp_audio_drc.h.proposed"),   # CURRENT COMBINED r1
                       "c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c", "patched_inc/recomp_audio_drc.h"),
}
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe")
TOOLCHAIN = {
    "clang.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",        # C launcher (own pin)
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",     # = T1 / Dr2
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e", # = T1 / Dr2
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",   # = T1 / Dr2
}
CASES = ["unprimed_starvation", "one_gap", "recovery", "multiple_gaps",
         "gap_split_across_callbacks", "mute_then_unmute_reset", "reset_by_init"]
CREATIONFLAGS = 0x08004000 if os.name == "nt" else 0   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
ENVELOPE_S = 105
CAPS = {"compile:base": 25, "run:base": 15, "compile:patched": 25, "run:patched": 15}   # 80 s <= 105 <= 120
REQUIRED_RECEIPT = ("step", "argv", "start_utc", "pid", "rc", "timed_out", "timeout_s", "elapsed_s", "stdout", "stderr")


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    return sha_bytes(Path(p).read_bytes())


class Budget:
    def __init__(self):
        self.t0 = time.monotonic()

    def left(self):
        return ENVELOPE_S - (time.monotonic() - self.t0)


def run_child(step, argv, budget, man):
    left = budget.left()
    if left < 5:
        man["reasons"].append(f"envelope exhausted before {step} ({left:.1f} s left)")
        return None
    timeout = min(CAPS[step], left)
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = "1"
    rec = {"step": step, "argv": [str(x) for x in argv], "start_utc": utc(), "pid": None, "rc": None,
           "timed_out": False, "timeout_s": round(timeout, 1), "creation_unix": None}
    t0 = time.monotonic()
    p = subprocess.Popen(rec["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATIONFLAGS, env=env)
    rec["pid"] = p.pid
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
    if any(k not in rec for k in REQUIRED_RECEIPT) or rec["rc"] is None:
        man["reasons"].append(f"incomplete receipt for {step}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grant-id", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    try:
        out.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        print(f"refusing: {out} exists", file=sys.stderr)
        return 2
    man = {"driver": "run_rab_gap_r5.py", "driver_sha256": sha(__file__),
           "supersedes": "run_rab_gap_r4.py 5d75f375, run_rab_gap_r3.py 3f74854d",
           "patched_target": "CURRENT COMBINED header audio-telemetry-combined-r1 c84258e1 (not old gap-only 7de21fb8)",
           "grant_id": a.grant_id, "out": str(out), "started_utc": utc(), "envelope_s": ENVELOPE_S, "caps_s": CAPS,
           "inputs": {}, "children": [], "cases": {}, "verdict": "FAIL", "reasons": [], "errors": [],
           "note": "outer Job receipt is authoritative for wall/memory limits"}
    code = 1
    try:
        code = body(out, man)
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


def body(out, man):
    budget = Budget()
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
    if invoked != TOOLCHAIN["clang.exe"]:
        man["reasons"].append("toolchain pin mismatch: invoked clang.exe")
    if man["reasons"]:
        return 2

    src = out / "src"
    src.mkdir(exist_ok=False)
    copies = {}
    for k, (orig, want, rel) in SOURCES.items():
        data = orig.read_bytes()                       # read ONCE
        got = sha_bytes(data)
        dst = src / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        written = sha(dst)
        copies[k] = dst
        man["inputs"][k] = {"original": str(orig), "read_sha256": got, "copy": str(dst),
                            "copy_sha256": written, "expected": want}
        if got != want or written != want:
            man["reasons"].append(f"pin mismatch: {k}")
    if man["reasons"]:
        return 2

    ext = ".exe" if os.name == "nt" else ""
    builds = {}
    for name, extra in (("base", []), ("patched", ["-DRAB_HAS_GAP"])):
        inc = copies[f"{name}_header"].parent
        exe = out / f"{name}{ext}"
        argv = [CC, "-O2", "-std=c11", "-Wall", *extra, f"-I{inc}", copies["fixture"], "-o", exe]
        if os.name != "nt":
            argv.append("-lm")
        rec = run_child(f"compile:{name}", argv, budget, man)
        if rec is None or rec["timed_out"] or rec["rc"] != 0 or not exe.is_file():
            man["reasons"].append(f"compile failed: {name}")
            return 1
        man["inputs"][f"{name}_exe"] = {"path": str(exe), "sha256": sha(exe)}
        rundir = out / f"{name}_run"
        rundir.mkdir(exist_ok=False)
        rec = run_child(f"run:{name}", [exe, rundir], budget, man)
        if rec is None:
            return 1
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
