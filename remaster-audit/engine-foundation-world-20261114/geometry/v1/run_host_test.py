#!/usr/bin/env python3
"""Compile and run the private view-provenance host tests (claude-einhander). CPU only, below normal, ONE compiler at a
time, no game, no GPU. Writes host-test.json.

1. tests/test_pgxp_view.cpp + FULL modified src/gte.cpp + src/pgxp.cpp (debug tools ON: real gte_execute ring + commit).
2. Regression controls with the CANONICAL harnesses, each against canonical and modified sources:
     runtime/tests/test_pgxp.cpp + pgxp.cpp                                   (as CMake pgxp_test)
     runtime/tests/test_gte_register_access.cpp + gte.cpp + pgxp.cpp with
       PSX_NO_DEBUG_TOOLS=1 PSX_GTE_REGISTER_TEST=1 PSX_ENABLE_BLOCK_CYCLES=1  (as CMake gte_register_access_test;
       this is also the no-debug-tools build of the modified gte.cpp)
3. Mutation controls on the modified sources: each mutant must make test 1 fail."""
import ctypes
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RT = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime")
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe"
WORK = HERE / "work"
FLAGS = ["-std=c++17", "-O1", "-Wall", "-Wextra"]

MUTANTS = [
    ("RTPT lane mis-indexed", "gte.cpp", "vin.lane = (V == gte->V0) ? 0 : (V == gte->V1) ? 1 : 2;",
     "vin.lane = (V == gte->V0) ? 0 : (V == gte->V1) ? 2 : 1;"),
    ("payload stores shifted MAC", "gte.cpp", "            vin.mac[0] = mac1;\n", "            vin.mac[0] = mac1 >> 12;\n"),
    ("SZ_SAT misses negative depth", "gte.cpp", "const bool vw_sz_sat = vw_z12 < 0 || vw_z12 > 0xFFFF;",
     "const bool vw_sz_sat = vw_z12 > 0xFFFF;"),
    ("XY_SAT never set", "gte.cpp", "                vf |= PGXP_VIEW_XY_SAT;\n", "                (void)0;\n"),
    ("ring liveness ignores overwrite", "gte.cpp",
     "    if (s_gte_rtp_seq - seq > GTE_RTP_RING_CAP) return 0;\n"
     "    return s_gte_rtp_ring[seq % GTE_RTP_RING_CAP].seq == (uint32_t)seq;\n", "    return 1;\n"),
    ("tag not moved with shadow copies", "pgxp.cpp", "        if (s_view_on) *vtag_of(dst) = *vtag_of(src);\n",
     "        if (s_view_on) { }\n"),
    ("identity copy drops the view", "pgxp.cpp", "    *dst = *src;\n    if (dst->flags & PGXP_F_VW) {\n",
     "    *dst = *src;\n    dst->flags &= (uint16_t)~PGXP_F_VW;\n    if (dst->flags & PGXP_F_VW) {\n"),
    ("half write keeps the view", "pgxp.cpp",
     "        dst->flags &= (uint16_t)~((hi_half ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ | PGXP_F_VW);\n",
     "        dst->flags &= (uint16_t)~((hi_half ? PGXP_F_VY : PGXP_F_VX) | PGXP_F_VZ);\n"),
    ("consumer skips packet-word validation", "pgxp.cpp", "    if (pv->value != packet_word) {\n        s_vstats.value_mismatch++;",
     "    if (0) {\n        s_vstats.value_mismatch++;"),
    ("producer ignores suppression/sandbox", "pgxp.cpp", "    if (!g_pgxp_active) return;\n    const int with_view",
     "    if (!s_enabled) return;\n    const int with_view"),
    ("commit ignores ring seq", "pgxp.cpp", "ok = r->tag == tag && r->rtp_seq == seq && r->cmd == cmd",
     "ok = r->tag == tag && r->cmd == cmd"),
    ("allocation failure fails open", "pgxp.cpp", "            --s_view_fail_allocs;\n            enabled = 0;\n",
     "            --s_view_fail_allocs;\n"),
    ("view enabled by default", "pgxp.cpp", "static int          s_view_on = 0;", "static int          s_view_on = 1;"),
    ("mode toggle keeps old tags", "pgxp.cpp",
     "    pgxp_invalidate_all();                     /* no tag outlives its mode     */\n", ""),
    ("tag wrap not restarted", "pgxp.cpp", "    if (with_view && s_view_seq == 0) view_restart();\n", ""),
]


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_run(name, sources, includes, defines=(), timeout=900):
    exe = WORK / f"{name}.exe"
    cmd = [CLANG, *FLAGS, *[f"-D{d}" for d in defines], *[f"-I{i}" for i in includes], *map(str, sources), "-o", str(exe)]
    c = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    rec = dict(name=name, compile_rc=c.returncode, compile_errors=[l for l in c.stderr.splitlines() if "error" in l][:12],
               sources={str(s): sha(s) for s in sources}, defines=list(defines))
    if c.returncode != 0:
        return rec
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=timeout)
    rec.update(exe_sha256=sha(exe), run_rc=r.returncode, stdout_tail=r.stdout.strip().splitlines()[-3:],
               stderr_fail_lines=[l for l in r.stderr.splitlines() if l.startswith("FAIL")][:12])
    return rec


def main():
    WORK.mkdir(exist_ok=True)
    pri = below_normal()
    ver = subprocess.run([CLANG, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    inc_mod = [HERE / "include", RT / "include"]
    inc_can = [RT / "include"]
    results = dict(compiler=ver, below_normal=pri, runs=[], mutants=[])

    results["runs"].append(build_run("view_test_modified", [HERE / "tests/test_pgxp_view.cpp", HERE / "src/gte.cpp",
                                                             HERE / "src/pgxp.cpp"], inc_mod))
    for tag, srcdir, inc in (("canonical", RT / "src", inc_can), ("modified", HERE / "src", inc_mod)):
        results["runs"].append(build_run(f"pgxp_test_{tag}", [RT / "tests/test_pgxp.cpp", srcdir / "pgxp.cpp"], inc))
        results["runs"].append(build_run(f"gte_register_access_test_{tag}",
                                         [RT / "tests/test_gte_register_access.cpp", srcdir / "gte.cpp", srcdir / "pgxp.cpp"],
                                         inc, ("PSX_NO_DEBUG_TOOLS=1", "PSX_GTE_REGISTER_TEST=1",
                                               "PSX_ENABLE_BLOCK_CYCLES=1")))

    mdir = WORK / "mut"
    (mdir / "src").mkdir(parents=True, exist_ok=True)
    base = {n: (HERE / "src" / n).read_text(encoding="utf-8") for n in ("gte.cpp", "pgxp.cpp")}
    for label, fname, old, new in MUTANTS:
        n = base[fname].count(old)
        if n != 1:
            results["mutants"].append(dict(label=label, error=f"anchor count {n}"))
            continue
        for f, text in base.items():
            (mdir / "src" / f).write_text(text.replace(old, new) if f == fname else text, encoding="utf-8", newline="\n")
        rec = build_run("view_test_mutant", [HERE / "tests/test_pgxp_view.cpp", mdir / "src/gte.cpp", mdir / "src/pgxp.cpp"],
                        inc_mod)
        caught = rec["compile_rc"] != 0 or rec.get("run_rc", 0) != 0
        results["mutants"].append(dict(label=label, file=fname, caught=caught, compile_rc=rec["compile_rc"],
                                       run_rc=rec.get("run_rc"), first_fail=(rec.get("stderr_fail_lines") or [None])[0]))
    ok_runs = all(r["compile_rc"] == 0 and r.get("run_rc") == 0 for r in results["runs"])
    results["all_runs_pass"] = ok_runs
    results["mutants_caught"] = sum(1 for m in results["mutants"] if m.get("caught"))
    results["mutants_total"] = len(MUTANTS)
    results["verdict"] = "pass" if ok_runs and results["mutants_caught"] == len(MUTANTS) else "FAIL"
    (HERE / "host-test.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for r in results["runs"]:
        print(r["name"], "compile", r["compile_rc"], "run", r.get("run_rc"), r.get("stdout_tail", [])[-1:] if r.get("stdout_tail") else "",
              r.get("compile_errors") or "", r.get("stderr_fail_lines") or "")
    for m in results["mutants"]:
        print("mutant:", m["label"], "caught" if m.get("caught") else "NOT CAUGHT", m.get("first_fail") or m.get("error") or "")
    print("verdict", results["verdict"], f"{results['mutants_caught']}/{results['mutants_total']}")


if __name__ == "__main__":
    main()
