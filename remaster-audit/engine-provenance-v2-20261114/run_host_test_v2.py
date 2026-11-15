#!/usr/bin/env python3
"""Compile and run the private view-provenance v2 host tests (claude-einhander). CPU only, below normal, ONE compiler at a
time, no game, no GPU. Writes host-test-v2.json.

1. tests/test_pgxp_view_v2.cpp + FULL v2 src/gte.cpp + src/pgxp.cpp + src/pgxp_view_census.cpp + tests/gpu_census_harness.c,
   which compiles the ACTUAL code cut (by anchor) from the generated v2 src/gpu.c (census arming, transport re-derive,
   texture predicate, census hooks) and src/debug_server.c (pgxp_view handler, json_get_int). Debug tools ON. The TCP
   replies the test prints ("JSON:" lines) are parsed and checked here.
2. Regression: the delivered v1 test (../impl/tests/test_pgxp_view.cpp) against the v2 gte/pgxp sources; the canonical
   pgxp_test and gte_register_access_test (no-debug-tools config) against the v2 sources.
3. Syntax: clang -fsyntax-only with the real runtime compile argv (v54 build.json template) on canonical and v2 gpu.c and
   debug_server.c; new diagnostics = v2 minus canonical (build flags and -Wall -Wextra).
4. Mutation controls on the v2 sources: each must make test 1 fail."""
import ctypes
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RT = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime")
TC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")
CLANGXX, CLANG = str(TC / "clang++.exe"), str(TC / "clang.exe")
WORK = HERE / "work"
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
TEMPLATE = json.loads((E / "sampling-build-v54-display-opt-in/build.json").read_text(encoding="utf-8"))["commands"][0]["arguments"]
CXXF = ["-std=c++17", "-O1", "-Wall", "-Wextra"]
CF = ["-std=gnu11", "-O1", "-Wall", "-Wextra"]

EXTRACTS = {  # name: (source file, start anchor, end anchor (exclusive) or None = end of function)
    "extract_gpu_state.inc": ("src/gpu.c", "static int s_texture_correction_enabled = 0;\n", "uint32_t gpu_texture_correction_hits(void) {"),
    "extract_gpu_prim.inc": ("src/gpu.c", "/* Arming rate for perspective-correct UVs, per condition.", "/* Write a single pixel to VRAM"),
    "extract_json_get_int.inc": ("src/debug_server.c", "static int json_get_int(const char *json, const char *key, int def)\n{", None),
    "extract_tcp_handler.inc": ("src/debug_server.c", "/* pgxp_view — opt-in 3D view-provenance census",
                                "/* pgxp — live-tune the value-propagation engine"),
}

MUTANTS = [
    ("MAC 44-bit bound off by one", "src/gte.cpp", "if (macs[a] >= m44 || macs[a] < -m44)", "if (macs[a] > m44 || macs[a] < -m44)"),
    ("WRAP32 ignores sf", "src/gte.cpp", "const int64_t r = macs[a] >> shift;", "const int64_t r = macs[a] >> 12;"),
    ("WRAP32 checks only the positive side", "src/gte.cpp", "if (r > i32_max || r < i32_min)", "if (r > i32_max)"),
    ("census counts misses as hits", "src/pgxp_view_census.cpp",
     "if (pgxp_get_precise_vertex_view_ex(addrs[i], words[i], &v, &why) ==\n            PGXP_SRC_DATAFLOW) {",
     "if (pgxp_get_precise_vertex_view_ex(addrs[i], words[i], &v, &why) !=\n            PGXP_SRC_DATAFLOW) {"),
    ("miss reason collapsed", "src/pgxp_view_census.cpp", "            k->miss[why]++;\n", "            k->miss[PGXP_VIEW_MISS_NO_SHADOW]++;\n"),
    ("one-command ignores rtp_seq", "src/pgxp_view_census.cpp",
     "if (!committed || (hits > 0 && v.rtp_seq != seq0)) one_command = 0;", "if (!committed) one_command = 0;"),
    ("immediate word reported as no_shadow", "src/pgxp.cpp",
     "        s_vstats.no_source++;\n        return PGXP_VIEW_MISS_NO_SOURCE;", "        s_vstats.no_source++;\n        return PGXP_VIEW_MISS_NO_SHADOW;"),
    ("census does not arm the transport", "src/gpu.c", "                     ws_precise_nclip_cfg ||\n                     s_view_census);",
     "                     ws_precise_nclip_cfg);"),
    ("disarm does not re-derive the user's transport", "src/gpu.c",
     "    pgxp_view_census_set(want);\n    gpu_pgxp_rederive_enable();\n}\n", "    pgxp_view_census_set(want);\n}\n"),
    ("payload allocation failure fails open", "src/gpu.c", "    if (want && !pgxp_view_payload()) want = 0;\n", ""),
    ("census hook touches the renderer", "src/gpu.c",
     "        view_census_gp0(PGXP_VIEW_CENSUS_TRI, ti, 3);\n    }\n",
     "        view_census_gp0(PGXP_VIEW_CENSUS_TRI, ti, 3);\n        gr_set_perspective_triangle(0, 0.0f, 0.0f, 0.0f);\n    }\n"),
    ("TCP reset ignored", "src/debug_server.c", "    if (json_get_int(json, \"reset\", 0) != 0)\n        pgxp_view_census_reset();\n", ""),
    ("TCP disarm ignored", "src/debug_server.c", "    if (census >= 0)\n        gpu_view_census_set(census != 0);\n",
     "    if (census > 0)\n        gpu_view_census_set(census != 0);\n"),
]


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_lf(p):
    return Path(p).read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def extract(src_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (rel, start, end) in EXTRACTS.items():
        t = read_lf(src_dir / rel)
        if t.count(start) != 1:
            raise SystemExit(f"{name}: start anchor count {t.count(start)}")
        a = t.index(start)
        b = t.index(end, a) if end else t.index("\n}\n", a) + 3
        (out_dir / name).write_text(t[a:b], encoding="utf-8", newline="\n")


def run(cmd, timeout=1200):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def build_v2(src_dir, inc_dir, ext_dir, name):
    harness_o = WORK / f"{name}_harness.o"
    c = run([CLANG, *CF, f"-I{inc_dir}", f"-I{RT / 'include'}", f"-I{ext_dir}", "-c", str(HERE / "tests/gpu_census_harness.c"),
             "-o", str(harness_o)])
    if c.returncode != 0:
        return dict(name=name, compile_rc=c.returncode, compile_errors=[l for l in c.stderr.splitlines() if "error" in l][:10])
    exe = WORK / f"{name}.exe"
    c = run([CLANGXX, *CXXF, f"-I{inc_dir}", f"-I{RT / 'include'}", str(HERE / "tests/test_pgxp_view_v2.cpp"),
             str(src_dir / "src/gte.cpp"), str(src_dir / "src/pgxp.cpp"), str(src_dir / "src/pgxp_view_census.cpp"),
             str(harness_o), "-o", str(exe)])
    if c.returncode != 0:
        return dict(name=name, compile_rc=c.returncode, compile_errors=[l for l in c.stderr.splitlines() if "error" in l][:10])
    r = run([str(exe)], timeout=900)
    return dict(name=name, compile_rc=0, exe_sha256=sha(exe), run_rc=r.returncode, stdout=r.stdout,
                fail_lines=[l for l in r.stderr.splitlines() if l.startswith("FAIL")][:12])


def check_tcp(stdout):
    replies = [json.loads(l[5:]) for l in stdout.splitlines() if l.startswith("JSON:")]
    errs = []
    names = {"no_source", "disabled", "no_shadow", "value_mismatch", "no_view", "evicted", "incoherent"}
    if len(replies) != 5:
        return [f"expected 5 replies, got {len(replies)}"], replies
    r1, r2, r3, r4, r5 = replies
    for r in replies:
        if r.get("ok") is not True:
            errs.append(f"reply {r.get('id')} not ok")
        for k in ("triangles", "quads"):
            if set(r.get(k, {}).get("miss", {})) != names:
                errs.append(f"reply {r.get('id')} {k}.miss keys")
    if not (r1["census"] == 1 and r1["view_payload"] == 1 and r1["pgxp_enabled"] == 1 and r1["geometry_correction"] == 0
            and r1["texture_correction"] == 0):
        errs.append("reply1 arming state")
    if r1["triangles"]["prims"] < 1 or r1["payload"]["record_bytes"] != 80:
        errs.append("reply1 counters")
    if len(r2["recent"]) != 5 or any(v["r"] not in names | {"none"} for p in r2["recent"] for v in p["v"]):
        errs.append("reply2 recent")
    if len(r3["recent"]) != min(64, r3["ring"]["total"]):
        errs.append("reply3 recent clamp")
    if not (r4["census"] == 0 and r4["pgxp_enabled"] == 0 and r4["view_payload"] == 0):
        errs.append("reply4 disarm")
    if not (r5["census"] == 1 and r5["triangles"]["prims"] == 0 and r5["quads"]["prims"] == 0):
        errs.append("reply5 re-arm + reset")
    return errs, replies


def syntax_args(src, inc_first, extra):
    a, skip = [], 0
    for x in TEMPLATE:
        if skip:
            skip -= 1
            continue
        if x in ("-MT", "-MF", "-o", "-c"):
            skip = 1
            continue
        if x == "-MD":
            continue
        a.append(x)
    pre = [f"-I{inc_first}"] if inc_first else []
    return [a[0], *pre] + a[1:] + list(extra) + ["-fsyntax-only", str(src)]


def diag(out):
    rows = set()
    for line in out.splitlines():
        m = re.match(r"(.*?):(\d+):(\d+): (warning|error): (.*)", line)
        if m:
            rows.add((Path(m.group(1)).name, m.group(4), re.sub(r"\s+", " ", m.group(5))))
    return rows


def main():
    WORK.mkdir(exist_ok=True)
    pri = below_normal()
    res = dict(compiler=run([CLANGXX, "--version"]).stdout.splitlines()[0], below_normal=pri, runs=[], syntax={}, mutants=[])

    ext = WORK / "ext"
    extract(HERE, ext)
    main_run = build_v2(HERE, HERE / "include", ext, "view_v2_test")
    tcp_errs, replies = check_tcp(main_run.get("stdout", "")) if main_run.get("compile_rc") == 0 else (["no run"], [])
    main_run["tcp_errors"] = tcp_errs
    main_run["stdout_tail"] = [l for l in main_run.pop("stdout", "").splitlines() if not l.startswith("JSON:")][-3:]
    (HERE / "tcp-replies.json").write_text(json.dumps(replies, indent=1) + "\n", encoding="utf-8")
    res["runs"].append(main_run)

    inc = [HERE / "include", RT / "include"]
    def simple(name, srcs, defines=()):
        exe = WORK / f"{name}.exe"
        c = run([CLANGXX, *CXXF, *[f"-D{d}" for d in defines], *[f"-I{i}" for i in inc], *map(str, srcs), "-o", str(exe)])
        if c.returncode != 0:
            return dict(name=name, compile_rc=c.returncode, compile_errors=[l for l in c.stderr.splitlines() if "error" in l][:10])
        r = run([str(exe)], timeout=900)
        return dict(name=name, compile_rc=0, exe_sha256=sha(exe), run_rc=r.returncode,
                    stdout_tail=r.stdout.strip().splitlines()[-2:], fail_lines=[l for l in r.stderr.splitlines() if l.startswith("FAIL")][:8])
    res["runs"].append(simple("v1_test_on_v2_sources", [HERE.parent / "impl/tests/test_pgxp_view.cpp", HERE / "src/gte.cpp", HERE / "src/pgxp.cpp"]))
    res["runs"].append(simple("pgxp_test_on_v2", [RT / "tests/test_pgxp.cpp", HERE / "src/pgxp.cpp"]))
    res["runs"].append(simple("gte_register_access_test_on_v2", [RT / "tests/test_gte_register_access.cpp", HERE / "src/gte.cpp", HERE / "src/pgxp.cpp"],
                              ("PSX_NO_DEBUG_TOOLS=1", "PSX_GTE_REGISTER_TEST=1", "PSX_ENABLE_BLOCK_CYCLES=1")))

    for name in ("gpu.c", "debug_server.c"):
        r = {}
        for label, src, inc_first in (("canonical", RT / "src" / name, None), ("v2", HERE / "src" / name, HERE / "include")):
            for flavor, extra in (("build", ()), ("wall", ("-Wall", "-Wextra"))):
                p = run(syntax_args(src, inc_first, extra))
                r[f"{label}_{flavor}"] = dict(exit=p.returncode, diags=diag(p.stderr))
        res["syntax"][name] = dict(canonical_exit=r["canonical_build"]["exit"], v2_exit=r["v2_build"]["exit"],
                                   new_build_diagnostics=sorted(r["v2_build"]["diags"] - r["canonical_build"]["diags"]),
                                   new_wall_diagnostics=sorted(r["v2_wall"]["diags"] - r["canonical_wall"]["diags"]))

    mdir = WORK / "mut"
    for label, rel, old, new in MUTANTS:
        if mdir.exists():
            shutil.rmtree(mdir)
        for sub in ("src", "include"):
            (mdir / sub).mkdir(parents=True)
        for p in (HERE / "src").iterdir():
            (mdir / "src" / p.name).write_text(read_lf(p), encoding="utf-8", newline="\n")
        for p in (HERE / "include").iterdir():
            (mdir / "include" / p.name).write_text(read_lf(p), encoding="utf-8", newline="\n")
        t = (mdir / rel).read_text(encoding="utf-8")
        if t.count(old) != 1:
            res["mutants"].append(dict(label=label, error=f"anchor count {t.count(old)}"))
            continue
        (mdir / rel).write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        extract(mdir, mdir / "ext")
        rr = build_v2(mdir, mdir / "include", mdir / "ext", "view_v2_mutant")
        terr = check_tcp(rr.get("stdout", ""))[0] if rr.get("compile_rc") == 0 and rr.get("run_rc") == 0 else []
        caught = rr.get("compile_rc") != 0 or rr.get("run_rc") != 0 or bool(terr)
        res["mutants"].append(dict(label=label, file=rel, caught=caught, compile_rc=rr.get("compile_rc"), run_rc=rr.get("run_rc"),
                                   first_fail=(rr.get("fail_lines") or terr or [None])[0]))

    ok_runs = all(r.get("compile_rc") == 0 and r.get("run_rc") == 0 for r in res["runs"]) and not tcp_errs
    ok_syntax = all(s["v2_exit"] == s["canonical_exit"] and not s["new_build_diagnostics"] and not s["new_wall_diagnostics"]
                    for s in res["syntax"].values())
    res["mutants_caught"] = sum(1 for m in res["mutants"] if m.get("caught"))
    res["mutants_total"] = len(MUTANTS)
    res["verdict"] = "pass" if ok_runs and ok_syntax and res["mutants_caught"] == len(MUTANTS) else "FAIL"
    (HERE / "host-test-v2.json").write_text(json.dumps(res, indent=1, default=list) + "\n", encoding="utf-8")
    for r in res["runs"]:
        print(r["name"], "compile", r.get("compile_rc"), "run", r.get("run_rc"), r.get("stdout_tail"), r.get("compile_errors") or "",
              r.get("fail_lines") or "", r.get("tcp_errors") or "")
    for n, s in res["syntax"].items():
        print("syntax", n, s)
    for m in res["mutants"]:
        print("mutant:", m["label"], "caught" if m.get("caught") else "NOT CAUGHT", m.get("first_fail") or m.get("error") or "")
    print("verdict", res["verdict"], f"{res['mutants_caught']}/{res['mutants_total']}")


if __name__ == "__main__":
    main()
