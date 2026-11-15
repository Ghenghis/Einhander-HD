#!/usr/bin/env python3
"""Build (NEVER run) the GPU self-test for the private class-aware mip shader path (claude-einhander).
CPU only, below normal, one logical CPU, one compiler. Inputs: a PASSING run_host.py run folder (its patched TU's
preprocessed output). Extracts the exact TEX_VS and HD_FS strings, compiles gl_selftest_classmips.c statically
against the toolchain's SDL3 (same static link style and system libraries as the v61 executable), and writes
selftest/<UTC>/ (exist_ok=False): the exe, the two shader files, README-ROOT.md, build.json with hashes.
Running the exe is root's step (it creates a GL context on the GPU)."""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
DEPS = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/deps")
SYSLIBS = ["-ladvapi32", "-lcomdlg32", "-ldbghelp", "-ldinput8", "-lgdi32", "-limm32", "-liphlpapi", "-lkernel32", "-lm",
           "-lole32", "-loleaut32", "-lopengl32", "-lsetupapi", "-lshell32", "-luser32", "-luuid", "-lversion", "-lwinmm",
           "-lwinpthread", "-lwinspool", "-lws2_32"]       # the v61 link's system libraries (Einhander_Recompiled.rsp)
ESC = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def extract(pre, name):
    m = re.search(r"static const char \*" + name + r"\s*=\s*((?:\s*\"(?:[^\"\\]|\\.)*\")+)\s*;", pre)
    if not m:
        raise SystemExit(f"{name} not found")
    parts = re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1))
    return "".join(re.sub(r"\\(.)", lambda mm: ESC.get(mm.group(1), mm.group(0)), p) for p in parts)


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path, help="passing runs/<UTC> folder of run_host.py")
    a = ap.parse_args()
    res = json.loads((a.run / "result.json").read_text(encoding="utf-8"))
    assert res.get("verdict") == "pass", "selftest is only built from a passing host run"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    od = HERE / "selftest" / stamp
    od.mkdir(parents=True, exist_ok=False)
    pre = (a.run / "patched" / "pre.i").read_text(encoding="utf-8")
    (od / "TEX_VS.vert").write_text(extract(pre, "TEX_VS"), encoding="utf-8")
    (od / "HD_FS.frag").write_text(extract(pre, "HD_FS"), encoding="utf-8")
    assert (od / "HD_FS.frag").read_bytes() == (a.run / "patched" / "HD_FS.frag").read_bytes(), "HD_FS differs from the host run"
    for p in (HERE / "gl_selftest_classmips.c", HERE / "hd_class_mips.inc", Path(__file__)):
        shutil.copy2(p, od / p.name)
    exe = od / "gl_selftest_classmips.exe"
    cmd = [CLANG, "-std=c11", "-O2", "-Wall", "-Wextra", "-I", str(od), "-isystem", str(DEPS / "include"),
           str(od / "gl_selftest_classmips.c"), str(DEPS / "lib/libSDL3.a"), "-static", *SYSLIBS, "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=0x4000)
    (od / "compile.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    b = dict(run=stamp, host_run=str(a.run), host_result_sha256=sha(a.run / "result.json"), compile_rc=r.returncode,
             warnings=(r.stdout + r.stderr).count("warning:"), command=cmd,
             files={p.name: sha(p) for p in sorted(od.iterdir()) if p.is_file() and p.suffix != ".log"},
             executed=False, note="NOT RUN by claude-einhander (GPU). Root runs it; see README-ROOT.md.")
    (od / "build.json").write_text(json.dumps(b, indent=1) + "\n", encoding="utf-8")
    patch_step = next(v for k, v in res["steps"].items() if k.endswith("-patch"))
    (od / "README-ROOT.md").write_text(
        "# GPU self-test v3+v4 of the private class-aware mip shader + upload path (built by claude-einhander, NOT run)\n\n"
        "Run on the 3090 Ti when you schedule it. It opens a hidden 64x64 SDL3 window with a GL 3.3 core context, renders\n"
        "offscreen only and exits; there is no game, no Remix and no file writes except the JSON.\n\n"
        "```\n"
        f"cd {od}\n"
        "gl_selftest_classmips.exe TEX_VS.vert HD_FS.frag selftest-result.json\n"
        "```\n\n"
        "- **Exit 0** means every scoped check passed (DESIGN-V3.md, after your FAIL N/class-mip-gpu-r1 of the v1 build):\n"
        "  - link, uniforms and FBO OK, no GL error;\n"
        "  - the stroke never vanishes for m <= s (2, 4, 8) on the facade path (C) AND the new non-facade path (N);\n"
        "  - no cutout bleed for m >= 2 on C and N;\n"
        "  - point mode is unchanged, and lod 0 is identical to level-0-only;\n"
        "  - the level-0 R5-filled variant D has no lod-0 fringe (that fringe is a level-0 content issue);\n"
        "  - fail closed on real GL: an injected wrong-size level gives HDCM_E_GL after 1 verified level, and the restore\n"
        "    leaves MAX_LEVEL 1000;\n"
        "  - v4 RGB edges (u_hd_rgb_edges):\n"
        "    - the lod-0 fringe is gone on A/C/N;\n"
        "    - the class-level paths keep their scoped goals;\n"
        "    - discard support and output alpha are identical with RGB edges on and off;\n"
        "    - an all-opaque page is exactly unchanged at every scale;\n"
        "    - the point path is unchanged.\n"
        "- **Reported only:** m = 12 (> s), lod-0 darkness of A/B/C/N, the A/B comparison numbers, and the GPU time to upload\n"
        "  and verify a 2048^2 prepared level set through the renderer's callback.\n"
        "- **v5 RGB-only sidecars** add no shader code and no GL call. HD_FS is byte-identical to v4's (compare\n"
        "  `HD_FS.frag` with the v4 self-test). An admitted RGB-only slot samples with u_hd_class_levels 0 and\n"
        "  u_hd_rgb_edges 1 on the non-facade level-0 path, which is the A path above. The same checks therefore cover v5's\n"
        "  GPU-visible behaviour; the v5 identity/admission logic is host-verified (DESIGN-V5.md).\n"
        "- **Shader sources** are extracted byte-exact from the patched TU of host run "
        f"`{a.run.name}` (patched sha256 {patch_step['patched_sha256']}).\n",
        encoding="utf-8")
    print(json.dumps({k: b[k] for k in ("run", "compile_rc", "warnings", "executed")}))


if __name__ == "__main__":
    main()
