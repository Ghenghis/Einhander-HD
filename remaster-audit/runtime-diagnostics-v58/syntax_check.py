#!/usr/bin/env python3
"""clang -fsyntax-only for the 3 patched v58 TUs and their exact bases (claude-einhander). Below-normal priority,
strictly sequential, no objects, no link, no game. New diagnostics = patched minus original, per flavor.
  debug_server.c, gpu_gl_renderer.c : v54 compile-debug_server.c argv (same template the v57 check used)
  main.cpp                          : v47 compile-runtime-main argv, runtime paths remapped to the upload-index-hitch
                                      worktree with its include/src prepended, exactly as v48 build.py does
"""
import ctypes
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
V57 = Path("C:/github/Einhander/remaster-audit/runtime-review/native-upload-stream/new")
V56 = E / "sampling-build-v56-gpu-cache/new"
R = "C:/github/Einhander/windows-x64/psxrecomp/runtime"
W = "C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime"
C_TEMPLATE = json.loads((E / "sampling-build-v54-display-opt-in/build.json").read_text(encoding="utf-8"))["commands"][0]["arguments"]
MAIN_TEMPLATE = next(c["arguments"] for c in json.loads((E / "sampling-build-v47-attrib/build.json").read_text(encoding="utf-8"))["commands"]
                     if any(x.replace("\\", "/").endswith("/runtime/src/main.cpp") for x in c["arguments"]))


def below_normal():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def strip(template):
    a, skip = [], 0
    for x in template:
        if skip:
            skip -= 1
            continue
        if x in ("-MT", "-MF", "-o", "-c"):
            skip = 1
            continue
        if x == "-MD":
            continue
        a.append(x)
    return a


def c_args(src, inc, extra):
    a = strip(C_TEMPLATE)
    return [a[0], "-I" + str(inc), "-I" + str(V57), "-I" + str(V56)] + a[1:] + list(extra) + ["-fsyntax-only", str(src)]


def main_args(src, inc, extra):
    a = [x.replace("\\", "/").replace(R, W) for x in strip(MAIN_TEMPLATE)]
    return [a[0], "-I" + str(inc), "-I" + W + "/include", "-I" + W + "/src"] + a[1:] + list(extra) + ["-fsyntax-only", str(src)]


def diag(out):
    rows = set()
    for line in out.splitlines():
        m = re.match(r"(.*?):(\d+):(\d+): (warning|error): (.*)", line)
        if m:
            rows.add((Path(m.group(1)).name, m.group(4), re.sub(r"\s+", " ", m.group(5))))
    return rows


def main():
    result = dict(below_normal=below_normal(), sequential=True, files={},
                  flags=dict(c="v54 compile-debug_server.c argv minus -MD/-MT/-MF/-o/-c, plus -fsyntax-only",
                             main="v47 compile-runtime-main argv, runtime remapped to upload-index-hitch worktree (v48 rule), "
                                  "minus -MD/-MT/-MF/-o/-c, plus -fsyntax-only"))
    jobs = [("debug_server.c", V57 / "debug_server.c", V57, c_args),
            ("gpu_gl_renderer.c", V57 / "gpu_gl_renderer.c", V57, c_args),
            ("main.cpp", Path(W + "/src/main.cpp"), Path(W + "/src"), main_args)]
    only = set(sys.argv[1:])   # optional TU filter, e.g. debug_server.c (rerun only what changed)
    jobs = [j for j in jobs if not only or j[0] in only]
    result["only"] = sorted(only)
    for name, orig, orig_inc, fn in jobs:
        r = {}
        for label, src, inc in (("original", orig, orig_inc), ("patched", HERE / "new" / name, HERE / "new")):
            for flavor, extra in (("build", ()), ("wall", ("-Wall", "-Wextra"))):
                p = subprocess.run(fn(src, inc, extra), capture_output=True, text=True, timeout=1200)
                r[f"{label}_{flavor}"] = dict(exit=p.returncode, diags=diag(p.stderr), tail=p.stderr.strip().splitlines()[-6:])
        result["files"][name] = dict(
            original=str(orig), original_exit=r["original_build"]["exit"], patched_exit=r["patched_build"]["exit"],
            new_build_diagnostics=sorted(r["patched_build"]["diags"] - r["original_build"]["diags"]),
            new_wall_diagnostics=sorted(r["patched_wall"]["diags"] - r["original_wall"]["diags"]),
            patched_build_tail=r["patched_build"]["tail"] if r["patched_build"]["exit"] else [])
        print(name, result["files"][name]["original_exit"], result["files"][name]["patched_exit"], flush=True)
    result["passed"] = all(f["original_exit"] == 0 and f["patched_exit"] == 0 and not f["new_build_diagnostics"]
                           and not f["new_wall_diagnostics"] for f in result["files"].values())
    (HERE / "syntax-check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
