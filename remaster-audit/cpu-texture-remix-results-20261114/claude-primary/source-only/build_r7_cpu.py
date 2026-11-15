"""CPU-only build and contract check of the r7 modern-GL probe PROPOSAL (claude-einhander). Run only under a grant.
Never executes the GPU branch: the built exe is run only with --cpu-contract and --guard-contract. No DLL, window or GL.

Usage: python build_r7_cpu.py --cpu N --out-root DIR
Steps (one at a time, each a single child, BelowNormal, affinity N, bounded timeout, exit checked):
  syntax          clang++ -fsyntax-only                     (r4 took 1.5 s)       cap 45 s
  compile-object  clang++ -O0 -c                                                   cap 60 s
  link            clang++ obj -luser32 -lgdi32 -lopengl32                          cap 45 s
  cpu-contract    exe --cpu-contract   -> exit 0, 65 checks, passed, revision r7   cap 10 s
  guard-contract  exe --guard-contract -> exit 77 (no owned lease), gpu_started false, dll_loaded false   cap 10 s
Toolchain and flags are r4's (build_modern_gl_cpu_r2.py): clang 22.1.8 mingw, -std=c++17 -Wall -Wextra -Werror
-Wno-missing-field-initializers, plus -I <N> so the unchanged include "sdk-release-header/remix_c.h" resolves to the
pinned header. Stops at the first failing step. Writes DIR/<stamp>/{result.json, <step>.log, probe.obj, exe,
executed-source.cpp}; nothing outside DIR."""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
SRC = HERE / "sdk_modern_gl_probe.r7.cpp"
N = Path("C:/github/Einhander/remaster-audit/runtime-review/gpu-texture-remix-20261114")
HEADER = N / "sdk-release-header/remix_c.h"
HEADER_SHA = "e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c"
CC = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe"
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers", "-I", str(N)]
CHECKS = 65


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--expect-source-sha", default=None)
    a = ap.parse_args()
    if sha(HEADER) != HEADER_SHA:
        raise SystemExit("pinned header changed")
    if a.expect_source_sha and sha(SRC) != a.expect_source_sha.lower():
        raise SystemExit("r7 source sha mismatch")
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([a.cpu])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out_root) / stamp
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(SRC, out / "executed-source.cpp")
    obj, exe = out / "probe.obj", out / "sdk-modern-gl-r7.exe"
    steps = [("syntax", [CC, *FLAGS, "-fsyntax-only", str(SRC)], 0, 45),
             ("compile-object", [CC, *FLAGS, "-O0", "-c", str(SRC), "-o", str(obj)], 0, 60),
             ("link", [CC, str(obj), "-o", str(exe), "-luser32", "-lgdi32", "-lopengl32"], 0, 45),
             ("cpu-contract", [str(exe), "--cpu-contract"], 0, 10),
             ("guard-contract", [str(exe), "--guard-contract"], 77, 10)]
    rows, passed = [], True
    result = dict(tool=Path(__file__).name, source=str(SRC), source_sha256=sha(SRC), header_sha256=HEADER_SHA,
                  builder_sha256=sha(__file__), cpu=a.cpu, started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  gpu_executed=False, dll_loaded=False)
    env = dict(os.environ)
    env.pop("EINHANDER_PRIVATE_GPU_NONCE", None)        # the guard step must never see a lease
    for label, args, expected, cap in steps:
        log = out / f"{label}.log"
        t = time.monotonic()
        with open(log, "w", encoding="utf-8") as stream:
            child = subprocess.Popen(args, cwd=out, stdout=stream, stderr=subprocess.STDOUT, env=env,
                                     creationflags=0x4000)
            row = dict(label=label, args=args, pid=child.pid, expected_exit=expected, cap_seconds=cap)
            try:
                code = child.wait(timeout=cap)
                row["timed_out"] = False
            except subprocess.TimeoutExpired:
                row["timed_out"] = True
                for d in psutil.Process(child.pid).children(recursive=True):
                    d.kill()
                child.kill()
                code = child.wait(timeout=5)
        row.update(exit=code, seconds=round(time.monotonic() - t, 3),
                   output=log.read_text(encoding="utf-8", errors="replace")[-3000:])
        ok = code == expected and not row["timed_out"]
        if ok and label == "cpu-contract":
            line = json.loads(row["output"].strip().splitlines()[-1])
            ok = (line.get("cpu_contract_checks") == CHECKS and line.get("passed") is True
                  and line.get("revision") == "r7" and line.get("dll_loaded") is False and line.get("gl_context") is False)
            row["contract"] = line
        if ok and label == "guard-contract":
            line = json.loads(row["output"].strip().splitlines()[-1])
            ok = line.get("owned_execution_lease") is False and line.get("gpu_started") is False and line.get("dll_loaded") is False
            row["guard"] = line
        row["passed"] = ok
        rows.append(row)
        if not ok:
            passed = False
            break
    result.update(steps=rows, passed=passed, exe_sha256=sha(exe) if exe.exists() else None,
                  ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with open(out / "result.json", "x", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(dict(out=str(out), passed=passed, steps={r["label"]: r["passed"] for r in rows},
                          exe_sha256=result["exe_sha256"])))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
