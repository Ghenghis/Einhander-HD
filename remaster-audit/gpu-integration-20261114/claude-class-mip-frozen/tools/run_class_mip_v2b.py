#!/usr/bin/env python3
"""Build and run the class-ownership / class-aware mip prototype V2b fixtures (proto-v2b, runs-v2b; v2 rules + cm_flags_ex), then the mutation controls (claude-einhander).
CPU only, below normal, ONE compiler/process at a time. Every run writes ONLY into a new folder runs/<UTC>/
(exist_ok=False): result.json, run.log, and byte copies of every input (sources, test, runner) - nothing is ever
overwritten, failed runs included. runs/INDEX.jsonl gets one appended line per run."""
import ctypes
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE / "proto-v2b"
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
FLAGS = ["-std=c11", "-O1", "-Wall", "-Wextra"]
INPUTS = [PROTO / "class_mip.h", PROTO / "class_mip.c", PROTO / "test_class_mip.c", Path(__file__)]

MUTANTS = [
    ("R2 displacement bound s/2 relaxed to s", "#define CM_R2_BOUND 0.5", "#define CM_R2_BOUND 1.0"),
    ("default R2 metric switched to Chebyshev", "#define CM_R2_METRIC 0", "#define CM_R2_METRIC 1"),
    ("cm_flags_ex ignores metric", "return metric == 1 ? (dx > dy ? dx : dy) : sqrt(dx * dx + dy * dy);", "return sqrt(dx * dx + dy * dy);"),
    ("cm_flags_ex ignores bound", "classify(rgba, w, h, ncls, tw, th, s, bound_frac, metric, flag_out, queue);", "classify(rgba, w, h, ncls, tw, th, s, CM_R2_BOUND, metric, flag_out, queue);"),
    ("cm_flags_ex accepts bad metric", "(metric != 0 && metric != 1)", "(metric < 0)"),
    ("R4 cross-cell connectivity disabled", "        if ((flag[i] & 1) && !(flag[i] & 32)) flag[i] |= 4;\n", ""),
    ("R4 connectivity ignores class", "if ((flag[q] & 32) || rgba[q * 4 + 3] != a) continue;", "if (flag[q] & 32) continue;"),
    ("repair limited to one pass", "#define CM_MAX_PASSES 8", "#define CM_MAX_PASSES 1"),
    ("R1 centre pixel off by one", "const size_t i = ((size_t)cy * s + s / 2) * w + (size_t)cx * s + s / 2;\n            if (rgba[i * 4 + 3] != ncls",
     "const size_t i = ((size_t)cy * s + s / 2) * w + (size_t)cx * s + s / 2 - 1;\n            if (rgba[i * 4 + 3] != ncls"),
    ("repair rewrites visible RGB on 127<->255", "                        if (old != 0) continue;                    /* 127<->255: alpha only */\n", ""),
    ("M3 majority instead of coverage preservation", "k = (int)floor((double)vis0 * k2 / ((double)s * s) + 0.5);",
     "k = vis0 * 2 >= s * s ? k2 : 0;"),
    ("M3 never-empty rule removed", "                if (C != 0 && k == 0) k = 1;", ""),
    ("M4 native class at the cell level removed", "            if (cs == 1) k = C != 0;", "            if (cs == 1) k = vis0 * 2 >= s * s;"),
    ("M2 RGB averages cutout children", "                        if (!p[3]) continue;\n                        sr += p[0];",
     "                        sr += p[0];"),
    ("level cutout RGB not filled", "    return cm_fill_cutout_rgb(dst, lw, h >> L) < 0 ? -1 : 0;", "    return 0;"),
    ("proposed sampler reads class at level 0", "        const int lc = (int)floor(l + 0.5);", "        const int lc = 0;"),
]


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_run(src_c, exe, log):
    c = subprocess.run([CLANG, *FLAGS, str(PROTO / "test_class_mip.c"), str(src_c), f"-I{PROTO}", "-o", str(exe)],
                       capture_output=True, text=True, timeout=900)
    log.append(f"$ compile {src_c.name} -> rc {c.returncode}\n{c.stderr}")
    if c.returncode:
        return dict(compile_rc=c.returncode, errors=[l for l in c.stderr.splitlines() if "error" in l][:8])
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=900)
    log.append(f"$ run {exe.name} -> rc {r.returncode}\n{r.stdout}{r.stderr}")
    return dict(compile_rc=0, run_rc=r.returncode, exe_sha256=sha(exe),
                metrics=[l[7:] for l in r.stdout.splitlines() if l.startswith("METRIC ")],
                summary=(r.stdout.strip().splitlines() or [""])[-1],
                fails=[l for l in r.stderr.splitlines() if l.startswith("FAIL")][:8])


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "runs-v2b" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    for p in INPUTS:
        shutil.copy2(p, rd / p.name)
    log = []
    res = dict(run=stamp, below_normal=below_normal(), inputs={p.name: sha(p) for p in INPUTS},
               compiler=subprocess.run([CLANG, "--version"], capture_output=True, text=True).stdout.splitlines()[0])
    res["fixtures"] = build_run(PROTO / "class_mip.c", rd / "test_class_mip.exe", log)
    base = (PROTO / "class_mip.c").read_text(encoding="utf-8")
    res["mutants"] = []
    for label, old, new in MUTANTS:
        if base.count(old) != 1:
            res["mutants"].append(dict(label=label, error=f"anchor count {base.count(old)}"))
            continue
        mc = rd / "mutant_class_mip.c"
        mc.write_text(base.replace(old, new), encoding="utf-8")
        r = build_run(mc, rd / "mutant.exe", log)
        res["mutants"].append(dict(label=label, caught=r.get("compile_rc") != 0 or r.get("run_rc") != 0,
                                   first_fail=(r.get("fails") or r.get("errors") or [None])[0]))
    mc = rd / "mutant_class_mip.c"
    if mc.exists():
        mc.unlink()
    for e in ("mutant.exe",):
        if (rd / e).exists():
            (rd / e).unlink()
    caught = sum(1 for m in res["mutants"] if m.get("caught"))
    f = res["fixtures"]
    res["verdict"] = "pass" if f.get("run_rc") == 0 and caught == len(MUTANTS) else "FAIL"
    res["mutants_caught"] = f"{caught}/{len(MUTANTS)}"
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    (rd / "run.log").write_text("\n".join(log), encoding="utf-8")
    with open(HERE / "runs-v2b" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, verdict=res["verdict"], mutants=res["mutants_caught"],
                                 result_sha256=sha(rd / "result.json"))) + "\n")
    print(json.dumps(dict(run=stamp, fixtures=f.get("summary"), verdict=res["verdict"], mutants=res["mutants_caught"]), indent=1))
    for m in res["mutants"]:
        print("mutant:", m["label"], "caught" if m.get("caught") else "NOT CAUGHT", m.get("first_fail") or m.get("error") or "")
    for mtr in f.get("metrics", []):
        print("  ", mtr)


if __name__ == "__main__":
    main()
