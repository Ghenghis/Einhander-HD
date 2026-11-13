#!/usr/bin/env python3
"""Real-loader regression test: exact-entry unmasking under differential admission.

Bug (RUNTIME-REVIEW.md section 15): in overlay_loader_dispatch, an exact,
CRC-matching manifested lazy entry E (0x80026714) is loaded only when the
already-loaded broader CPS range owner H (0x800262B0) has device_touch. In
differential mode (PSX_OVERLAY_DIFF, optionally PSX_OVERLAY_DIFF_ADDR) H is
cand_selected_for_diff and diff-gated, so the CPS continuation gate returns
outcome 5 to the interpreter on every edge: E never loads and never gets its own
shadow. The fix (exact-entry-unmask.diff) ORs `owner_diff_gated` -- the gate's
exact predicate -- into exact_needs_load.

This script compiles the REAL runtime/src/overlay_loader.c with the stub harness
overlay_exact_unmask_harness.c, builds two real shard DLLs
(overlay_exact_unmask_fixture.c), publishes them into a synthetic namespaced
cache that the loader itself scans and lazily LoadLibrary's, and runs seven
cases against up to three loader builds:

  before   the tree's loader with the owner_diff_gated term reverted (or the
           tree itself if it does not contain the fix yet)
  tree     runtime/src/overlay_loader.c exactly as it is on disk
  proposed exact-entry-unmask.diff applied to `before` (a copy in _build/)

Required outcome: `before` FAILS P1 and P2 and passes N1..N5; `proposed` (and
`tree`, when it already contains the fix) passes every case, and N2..N5 are
metric-for-metric identical to `before`.

  python test_overlay_exact_unmask_runtime.py              # before/after table
  python test_overlay_exact_unmask_runtime.py --mode tree  # tree only (CI form)

Nothing under windows-x64/ is modified; all outputs go to ./_build/ (or
--build-dir). Uses only the installed C compiler (gcc/cc on PATH, or --cc).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

HERE = pathlib.Path(__file__).resolve().parent
ADOPTED = (HERE.parent / "src" / "overlay_loader.c").is_file()   # in runtime/tests
if ADOPTED:
    DEFAULT_RUNTIME = HERE.parent
else:                                                        # remaster-audit location
    DEFAULT_RUNTIME = HERE.parents[2] / "windows-x64" / "psxrecomp" / "runtime"
DEFAULT_DIFF = HERE.parent / "exact-entry-unmask.diff"
# Shared "keep the CPU quiet" flag; override the location with MASKING_TEST_QUIET_FLAG.
QUIET_FLAG = pathlib.Path(os.environ.get(
    "MASKING_TEST_QUIET_FLAG",
    str(HERE.parents[1] / "comfy-authoring" / "CPU-QUIET")))

GAME = "MASK-TEST"
EXT = ".dll" if platform.system() == "Windows" else ".so"
EXE = ".exe" if platform.system() == "Windows" else ""

H_ENTRY, H_LEN = 0x800262B0, 0x48C      # broad owner, one range [262B0, 2673C)
F2_ENTRY, F2_LEN = 0x8002673C, 0x68     # H bundle sibling root  [2673C, 267A4)
E_ENTRY, E_LEN = 0x80026714, 0x28       # exact orphan fragment  [26714, 2673C)
CODE_BASE, CODE_END = 0x262B0, 0x267A4
H_PAIR, E_PAIR = 0x4D41534B48000001, 0x4D41534B45000001   # synthetic pair ids
EDGES = 64
BUDGET = 32                              # OVERLAY_DIFF_BUDGET

DIFF_ADDR_E = "0x80026714"
CASES = [
    # name, env, e_crc_flip, description
    ("P1", {"PSX_OVERLAY_DIFF": "1", "PSX_OVERLAY_DIFF_ADDR": DIFF_ADDR_E}, False,
     "diff + DIFF_ADDR=E, owner H loaded but never diffed"),
    ("P2", {"PSX_OVERLAY_DIFF": "1"}, False,
     "diff, no DIFF_ADDR, H inside its 32-pass budget"),
    ("N1", {"PSX_OVERLAY_DIFF": "1", "PSX_OVERLAY_DIFF_ADDR": DIFF_ADDR_E}, True,
     "as P1 but E's manifest CRC is stale"),
    ("N2", {"PSX_OVERLAY_DIFF": "1", "PSX_OVERLAY_DIFF_ADDR": DIFF_ADDR_E}, False,
     "H diverged in its shadow -> device_touch=1"),
    ("N3", {}, False,
     "diff mode off"),
    ("N4", {"PSX_OVERLAY_DIFF": "1", "PSX_OVERLAY_DIFF_ADDR": DIFF_ADDR_E}, False,
     "non-exact edge 0x80026720 inside H (Whoopee guard)"),
    ("N5", {"PSX_OVERLAY_DIFF": "1"}, False,
     "no DIFF_ADDR, H already passed 32 diffs"),
]
EXPECT_BEFORE_FAIL = {"P1", "P2"}


# ---------------------------------------------------------------- utilities

def wait_quiet() -> None:
    """Honour the shared CPU-QUIET flag before every compile or run."""
    if ADOPTED or not QUIET_FLAG.exists():
        return
    print(f"[quiet] {QUIET_FLAG} present; waiting...", flush=True)
    deadline = time.monotonic() + 4 * 3600
    while QUIET_FLAG.exists():
        if time.monotonic() > deadline:
            raise SystemExit("CPU-QUIET did not clear within 4 hours")
        time.sleep(15)
    print("[quiet] cleared", flush=True)


def run(command: list[str], *, env: dict | None = None, timeout: int = 300,
        what: str = "") -> str:
    wait_quiet()
    result = subprocess.run(command, text=True, env=env, timeout=timeout,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(
            f"{what or 'command'} failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    warnings = result.stderr.count("warning:")
    if what:
        print(f"  built {what}" + (f" ({warnings} compiler warnings)" if warnings else ""),
              flush=True)
    return result.stdout


def sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


# ------------------------------------------------------- loader variants

FIX_TERM = re.compile(r"exact_needs_load\s*=\s*lazy_exact\s*&&\s*\([^;]*owner_diff_gated[^;]*\);")
PREFIX_EXPR = re.compile(
    r"exact_needs_load\s*=\s*lazy_exact\s*&&\s*"
    r"\(loaded_range_ci\s*<\s*0\s*\|\|\s*s_cand\[loaded_range_ci\]\.device_touch\);")


def has_fix(text: str) -> bool:
    return FIX_TERM.search(text) is not None


def revert_fix(text: str) -> str:
    """Remove the owner_diff_gated block and its OR term -> pre-fix predicate."""
    lines = text.splitlines()
    decl = [i for i, line in enumerate(lines)
            if re.match(r"\s*int\s+owner_diff_gated\s*=", line)]
    if len(decl) != 1:
        raise SystemExit(f"cannot revert: {len(decl)} owner_diff_gated declarations")
    start = end = decl[0]
    if lines[start - 1].strip().endswith("*/"):           # comment block above
        start -= 1
        while not lines[start].lstrip().startswith("/*"):
            start -= 1
    while not lines[end].rstrip().endswith(";"):
        end += 1
    del lines[start:end + 1]
    out, n = re.subn(r"\s*\|\|\s*owner_diff_gated\s*\)", ")", "\n".join(lines) + "\n")
    if n != 1 or "owner_diff_gated" in out or not PREFIX_EXPR.search(out):
        raise SystemExit("cannot revert: unexpected owner_diff_gated shape")
    return out


def apply_unified_diff(text: str, diff_text: str) -> str:
    """Apply a single-file unified diff; every hunk must match exactly once."""
    if sum(1 for raw in diff_text.splitlines() if raw.startswith("+++ ")) != 1:
        raise SystemExit("expected a single-file unified diff")
    lines = text.splitlines()
    hunks: list[tuple[list[str], list[str]]] = []
    cur = None
    for raw in diff_text.splitlines():
        if raw.startswith("@@"):
            cur = ([], [])
            hunks.append(cur)
        elif cur is None or raw.startswith("\\"):
            continue                       # file headers / "\ No newline" marker
        elif raw == "" or raw[0] == " ":
            cur[0].append(raw[1:])
            cur[1].append(raw[1:])
        elif raw[0] == "-":
            cur[0].append(raw[1:])
        elif raw[0] == "+":
            cur[1].append(raw[1:])
        else:
            cur = None
    if not hunks:
        raise SystemExit("diff contains no hunks")
    for old, new in hunks:
        norm_old = [s.rstrip() for s in old]
        hits = [i for i in range(len(lines) - len(old) + 1)
                if [s.rstrip() for s in lines[i:i + len(old)]] == norm_old]
        if len(hits) != 1:
            raise SystemExit(f"diff hunk matched {len(hits)} times (need exactly 1)")
        lines[hits[0]:hits[0] + len(old)] = new
    return "\n".join(lines) + "\n"


# --mutants: deliberately wrong "fixes" derived from the proposed loader. Each
# must be caught by the named negative case(s); proves the negatives have teeth.
def _sub1(pattern: str, repl: str):
    def apply(text: str) -> str:
        out, n = re.subn(pattern, repl, text, count=1)
        if n != 1:
            raise SystemExit(f"mutant pattern not found: {pattern}")
        return out
    return apply


MUTANTS = [
    ("mut-exact-always", "exact entry always beats a loaded owner (option b)",
     _sub1(FIX_TERM.pattern, "exact_needs_load = lazy_exact;"), {"N3", "N5"}),
    ("mut-no-budget", "owner_diff_gated ignores the 32-pass budget",
     _sub1(r"\(s_diff_addr\s*\|\|\s*s_cand\[loaded_range_ci\]\.diff_passes\s*<\s*"
           r"OVERLAY_DIFF_BUDGET\)", "1"), {"N5"}),
    ("mut-no-diff-mode", "owner_diff_gated without s_diff_mode",
     _sub1(r"(int\s+owner_diff_gated\s*=\s*loaded_range_ci\s*>=\s*0\s*&&)\s*s_diff_mode\s*&&",
           r"\1"), {"N3"}),
    ("mut-any-edge", "gated owner forces a region scan on every edge, exact or not",
     _sub1(FIX_TERM.pattern,
           "exact_needs_load = (lazy_exact && (loaded_range_ci < 0 || "
           "s_cand[loaded_range_ci].device_touch)) || owner_diff_gated;"), {"N4"}),
]


def git_prefix_loader(runtime: pathlib.Path) -> tuple[str, str] | None:
    """(short sha, text) of the newest committed overlay_loader.c without the
    fix, read-only via `git log` / `git show`; None outside a git checkout."""
    try:
        top = subprocess.run(["git", "-C", str(runtime), "rev-parse", "--show-toplevel"],
                             text=True, capture_output=True, timeout=30)
        if top.returncode:
            return None
        root = pathlib.Path(top.stdout.strip())
        rel = (runtime / "src" / "overlay_loader.c").resolve().relative_to(
            root.resolve()).as_posix()
        log = subprocess.run(["git", "-C", str(root), "log", "-n", "20", "--format=%h",
                              "--", rel], text=True, capture_output=True, timeout=30)
        for sha in log.stdout.split():
            blob = subprocess.run(["git", "-C", str(root), "show", f"{sha}:{rel}"],
                                  capture_output=True, timeout=30)
            if blob.returncode == 0:
                text = blob.stdout.decode("utf-8")
                if not has_fix(text):
                    return sha, text
        return None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


# ------------------------------------------------------------- build

def cflags(runtime: pathlib.Path) -> list[str]:
    flags = ["-std=c11", "-O0", "-Wall", "-Wextra",
             "-DPSX_NO_DEBUG_TOOLS", "-DPSX_OVERLAY_DLL_BUILD",
             f"-I{runtime / 'include'}"]
    if platform.system() != "Windows":
        flags.append("-D_GNU_SOURCE")
    return flags


def build_common(cc: str, runtime: pathlib.Path, out: pathlib.Path) -> list[pathlib.Path]:
    objs = []
    for src in (runtime / "src" / "overlay_path_canon.c",
                runtime / "src" / "overlay_posix.c",
                runtime / "src" / "crc32.c",
                HERE / "overlay_exact_unmask_harness.c"):
        obj = out / (src.stem + ".o")
        run([cc, *cflags(runtime), "-c", str(src), "-o", str(obj)], what=src.name)
        objs.append(obj)
    return objs


def build_harness(cc: str, runtime: pathlib.Path, loader_src: pathlib.Path,
                  common: list[pathlib.Path], out: pathlib.Path, tag: str) -> pathlib.Path:
    obj = out / f"overlay_loader_{tag}.o"
    run([cc, *cflags(runtime), "-c", str(loader_src), "-o", str(obj)],
        what=f"overlay_loader.c [{tag}] from {loader_src}")
    exe = out / f"exact_unmask_harness_{tag}{EXE}"
    link = [cc, str(obj), *map(str, common), "-o", str(exe)]
    if platform.system() != "Windows":
        link += ["-ldl", "-pthread"]
    run(link, what=f"harness [{tag}]")
    return exe


def build_fixture(cc: str, runtime: pathlib.Path, out: pathlib.Path, *,
                  pair: int, funcs: list[int], tag: str) -> pathlib.Path:
    lib = out / f"fixture_{tag}{EXT}"
    command = [cc, "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror", "-shared",
               f"-I{runtime / 'include'}", f"-DTEST_PAIR_ID=0x{pair:016X}ULL"]
    for i, entry in enumerate(funcs):
        command.append(f"-DTEST_FUNC{i}=func_{entry:08X}")
    if platform.system() != "Windows":
        command.append("-fPIC")
    command += [str(HERE / "overlay_exact_unmask_fixture.c"), "-o", str(lib)]
    run(command, what=f"fixture {tag} ({', '.join(f'func_{e:08X}' for e in funcs)})")
    return lib


# ------------------------------------------------------ synthetic cache

def code_image() -> bytes:
    """Benign straight-line code (addiu $t0,$t0,imm) ending each function's
    range with `jr $ra; nop`, so the loader's delay-slot guard accepts it."""
    words = {a: 0x25080000 | ((a >> 2) & 0xFFFF) for a in range(CODE_BASE, CODE_END, 4)}
    for jr in (0x26734, 0x2679C):          # end of H/E range, end of F2 range
        words[jr], words[jr + 4] = 0x03E00008, 0x00000000
    return b"".join(struct.pack("<I", words[a]) for a in range(CODE_BASE, CODE_END, 4))


def crc_of(code: bytes, entry: int, length: int) -> int:
    lo = (entry & 0x1FFFFFFF) - CODE_BASE
    return zlib.crc32(code[lo:lo + length]) & 0xFFFFFFFF


def manifest(pair: int, funcs: list[tuple[int, int, int]]) -> str:
    out = ["# psxrecomp overlay code-range manifest v2 (entry+code_crc)\n",
           "# psxrecomp overlay provenance orphan-v1\n",
           f"P {pair:016X}\n"]
    for entry, crc, length in funcs:
        out += [f"F {entry:08X} {crc:08X}\n", f"R {entry:08X} {length:X}\n"]
    return "".join(out)


def publish_cache(root: pathlib.Path, leaf: str, code: bytes, h_lib: pathlib.Path,
                  e_lib: pathlib.Path, e_crc_flip: bool) -> tuple[str, str]:
    d = root / GAME / leaf
    d.mkdir(parents=True, exist_ok=True)
    h_crc = crc_of(code, H_ENTRY, H_LEN)
    f2_crc = crc_of(code, F2_ENTRY, F2_LEN)
    e_crc = crc_of(code, E_ENTRY, E_LEN)
    # Both region-start 0x00011000, as in the observed cache (the dirty
    # boot-text run walks back to 0x11000); E is exact-only reachable.
    h_name = f"00011000_{h_crc:08X}{EXT}"
    e_name = f"00011000_{e_crc:08X}{EXT}"
    shutil.copy2(h_lib, d / h_name)
    shutil.copy2(e_lib, d / e_name)
    (d / h_name).with_suffix(".ranges").write_text(
        manifest(H_PAIR, [(H_ENTRY, h_crc, H_LEN), (F2_ENTRY, f2_crc, F2_LEN)]),
        encoding="ascii", newline="")
    (d / e_name).with_suffix(".ranges").write_text(
        manifest(E_PAIR, [(E_ENTRY, e_crc ^ (1 if e_crc_flip else 0), E_LEN)]),
        encoding="ascii", newline="")
    return h_name, e_name


# ------------------------------------------------------------- checks

def ival(m: dict, key: str) -> int:
    v = m[key]
    return int(v, 16) if v.startswith("0x") else int(v)


def checks_for(name: str, m: dict) -> list[tuple[str, bool]]:
    g = lambda k: ival(m, k)                        # noqa: E731
    c: list[tuple[str, bool]] = [
        ("H bundle published before the phase (pre_h_cands=1, E absent)",
         g("pre_h_cands") == 1 and g("pre_e_cands") == 0 and g("h_module") == 1),
        ("interp stub saw only known entries", g("interp_other") == 0),
    ]
    h_untouched = (g("h_root_calls") == 0 and g("h_diff_passes") == 0 and
                   g("h_device_touch") == 0 and g("phase_h_interp") == 0)
    e_absent = g("e_cands") == 0 and g("e_module") == 0 and g("phase_loads") == 0
    e_once = (g("e_cands") == 1 and g("e_init") == 1 and g("phase_loads") == 1)
    gate5 = (g("probe_count") == EDGES and g("probe_outcome") == 5 and
             g("probe_found") == H_ENTRY & 0x1FFFFFFF and g("phase_ret0") == EDGES)
    root_delta = g("h_root_calls") - g("pre_h_root_calls")
    if name in ("P1", "P2"):
        shadows = EDGES if name == "P1" else BUDGET
        c += [
            ("pre: H loaded, root never called, 0 diff passes",
             g("pre_h_diff_passes") == 0 and g("pre_h_device_touch") == 0 and
             g("pre_h_root_calls") == 0),
            ("E loads exactly once (1 candidate, 1 overlay_init, 1 DLL load)", e_once),
            (f"E gets its own entry-level shadow ({shadows} shadow calls, all E's)",
             g("phase_shadow_calls") == shadows and g("phase_e_interp") == shadows),
            (f"E's diff_passes reach the budget ({BUDGET})", g("e_diff_passes") == BUDGET),
            ("E's native body ran (shadow native pass / live after budget)",
             g("e_native_calls") == EDGES and g("e_last_pc") == E_ENTRY),
            ("no edge falls to the owner's diff gate (probe count 0, 64 completions)",
             g("probe_count") == 0 and g("phase_ret1") == EDGES and
             g("phase_result_ok") == EDGES),
            ("H stays untouched and unvalidated", h_untouched),
            ("exactly one try_load_region in the phase", g("phase_try_load_region") == 1),
        ]
    elif name == "N1":
        c += [
            ("E (stale CRC) is not loaded", e_absent),
            ("owner diff gate still holds (outcome 5 x64 at owner 0x800262B0)", gate5),
            ("H stays untouched and unvalidated", h_untouched),
        ]
    elif name == "N2":
        c += [
            ("pre: H diverged in its own shadow -> device_touch=1",
             g("pre_h_device_touch") == 1 and g("total_shadow_divs") >= 1),
            ("E loads exactly once (existing device_touch path)", e_once),
            ("E is shadowed on every edge (DIFF_ADDR=E)",
             g("phase_shadow_calls") == EDGES and g("phase_e_interp") == EDGES),
            ("H's root is not re-run", root_delta == 0 and g("phase_h_interp") == 0),
        ]
    elif name == "N3":
        c += [
            ("E is not loaded", e_absent),
            ("H runs the continuation natively (outcome 2 x64, pc=0x80026714)",
             g("probe_count") == EDGES and g("probe_outcome") == 2 and
             root_delta == EDGES and g("h_root_last_pc") == E_ENTRY and
             g("phase_result_ok") == EDGES),
            ("no manifest scan on any edge", g("phase_try_load_region") == 0),
            ("no shadow diff runs", g("phase_shadow_calls") == 0),
        ]
    elif name == "N4":
        c += [
            ("no try_load_region / manifest scan on any non-exact edge",
             g("phase_try_load_region") == 0),
            ("owner diff gate holds at 0x80026720 (outcome 5 x64)",
             g("probe_count") == EDGES and g("probe_outcome") == 5 and
             g("probe_found") == H_ENTRY & 0x1FFFFFFF),
            ("E is not loaded", e_absent),
            ("H stays untouched and unvalidated", h_untouched),
        ]
    elif name == "N5":
        c += [
            ("pre: H passed its budget (diff_passes=32)", g("pre_h_diff_passes") == BUDGET),
            ("E is not force-loaded", e_absent and g("phase_try_load_region") == 0),
            ("validated owner runs the continuation natively (outcome 2 x64)",
             g("probe_count") == EDGES and g("probe_outcome") == 2 and
             root_delta == EDGES and g("phase_result_ok") == EDGES),
        ]
    return c


def summary(m: dict) -> str:
    g = lambda k: ival(m, k)                        # noqa: E731
    out = (f"out={g('probe_outcome')}x{g('probe_count')}" if g("probe_count") else "out=-")
    return (f"E={g('e_cands')} sh={g('phase_shadow_calls')} {out} "
            f"scan={g('phase_try_load_region')}")


STABLE_SKIP = {"loader_msg"}


def metric_diff(a: dict, b: dict) -> list[str]:
    return [f"{k}: {a.get(k)} -> {b.get(k)}" for k in sorted(set(a) | set(b))
            if k not in STABLE_SKIP and a.get(k) != b.get(k)]


# -------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=("compare", "tree"), default="compare")
    ap.add_argument("--runtime", type=pathlib.Path, default=DEFAULT_RUNTIME)
    ap.add_argument("--diff", type=pathlib.Path, default=DEFAULT_DIFF)
    ap.add_argument("--cc", default=shutil.which("gcc") or shutil.which("cc"))
    ap.add_argument("--build-dir", type=pathlib.Path, default=None,
                    help="default: ./_build (kept); a temp dir when run from runtime/tests")
    ap.add_argument("--mutants", action="store_true",
                    help="also build 4 deliberately wrong fixes; each must be caught")
    args = ap.parse_args()
    if args.mutants and args.mode != "compare":
        raise SystemExit("--mutants needs --mode compare")
    if not args.cc:
        raise SystemExit("gcc/cc is required (or pass --cc)")
    runtime = args.runtime.resolve()
    tree_loader = runtime / "src" / "overlay_loader.c"
    tree_text = tree_loader.read_text(encoding="utf-8")

    temp_build = args.build_dir is None and ADOPTED
    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    if temp_build:
        build = pathlib.Path(tempfile.mkdtemp(prefix="psx-exact-unmask-", dir=temp_root)).resolve()
    else:
        build = (args.build_dir or HERE / "_build").resolve()
        if build.exists():
            raise SystemExit(f"Fresh build directory required: {build}")
    (build / "src").mkdir(parents=True)
    try:
        return run_all(args, runtime, tree_loader, tree_text, build)
    finally:
        if temp_build:
            if build.parent != temp_root or not build.name.startswith("psx-exact-unmask-") or build.is_symlink():
                raise RuntimeError(f"Refusing cleanup outside the owned temporary build: {build}")
            shutil.rmtree(build, ignore_errors=True)


def run_all(args, runtime: pathlib.Path, tree_loader: pathlib.Path, tree_text: str,
            build: pathlib.Path) -> int:
    ver = subprocess.run([args.cc, "--version"], text=True, capture_output=True)
    print(f"compiler : {args.cc} ({(ver.stdout or ver.stderr).splitlines()[0]})")
    print(f"runtime  : {runtime}")
    print(f"tree     : overlay_loader.c sha256={sha12(tree_loader.read_bytes())} "
          f"contains-fix={'yes' if has_fix(tree_text) else 'no'}")

    variants: list[tuple[str, pathlib.Path]] = []
    if args.mode == "tree":
        variants.append(("tree", tree_loader))
    else:
        before_text = revert_fix(tree_text) if has_fix(tree_text) else tree_text
        prefix = git_prefix_loader(runtime)
        if prefix is not None:
            same = prefix[1].splitlines() == before_text.splitlines()
            print(f"before   : {'identical to' if same else 'differs from'} the newest "
                  f"pre-fix committed overlay_loader.c ({prefix[0]}; line-ending insensitive)")
        before_src = build / "src" / "before" / "overlay_loader.c"
        before_src.parent.mkdir(parents=True)
        before_src.write_text(before_text, encoding="utf-8", newline="\n")
        variants.append(("before", before_src))
        if has_fix(tree_text):
            variants.append(("tree", tree_loader))
        else:
            print("tree     : no fix on disk, so `before` IS the tree loader as-is")
        if args.diff.is_file():
            diff_text = args.diff.read_text(encoding="utf-8")
            proposed_text = apply_unified_diff(before_text, diff_text)
            if not has_fix(proposed_text):
                raise SystemExit(f"{args.diff} did not introduce owner_diff_gated")
            proposed_src = build / "src" / "proposed" / "overlay_loader.c"
            proposed_src.parent.mkdir(parents=True)
            proposed_src.write_text(proposed_text, encoding="utf-8", newline="\n")
            variants.append(("proposed", proposed_src))
            print(f"proposed : {args.diff.name} applied to before -> {proposed_src}")
        elif has_fix(tree_text):
            proposed_text = tree_text
            print(f"proposed : {args.diff} not found; comparing before vs tree only")
        else:
            raise SystemExit("the tree has no fix and no --diff was found to apply")
        if args.mutants:
            for tag, _, mutate, _ in MUTANTS:
                src = build / "src" / tag / "overlay_loader.c"
                src.parent.mkdir(parents=True)
                src.write_text(mutate(proposed_text), encoding="utf-8", newline="\n")
                variants.append((tag, src))
    mutant_tags = {m[0] for m in MUTANTS} if args.mutants else set()

    print("building (bounded: 4 common objects, 2 fixtures, "
          f"{len(variants)} loader builds)", flush=True)
    obj = build / "obj"
    obj.mkdir()
    common = build_common(args.cc, runtime, obj)
    h_lib = build_fixture(args.cc, runtime, obj, pair=H_PAIR,
                          funcs=[H_ENTRY, F2_ENTRY], tag="H")
    e_lib = build_fixture(args.cc, runtime, obj, pair=E_PAIR, funcs=[E_ENTRY], tag="E")
    harnesses = {tag: build_harness(args.cc, runtime, src, common, obj, tag)
                 for tag, src in variants}

    leaf = run([str(next(iter(harnesses.values()))), "leaf"], timeout=60).strip()
    code = code_image()
    code_bin = build / "code.bin"
    code_bin.write_bytes(code)

    base_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PSX_")}
    base_env["PSX_OVERLAY_IMAGE_WARM"] = "0"

    results: dict[str, dict[str, dict]] = {}
    for tag, exe in harnesses.items():
        results[tag] = {}
        for name, env_extra, flip, _ in CASES:
            cache = build / "run" / tag / name / "cache"
            h_name, e_name = publish_cache(cache, leaf, code, h_lib, e_lib, flip)
            out = run([str(exe), cache.as_posix(), name, str(code_bin), h_name, e_name],
                      env={**base_env, **env_extra}, timeout=120)
            (cache.parent / "metrics.txt").write_text(out, encoding="utf-8")
            results[tag][name] = dict(line.split("=", 1) for line in out.splitlines()
                                      if "=" in line)

    verdict: dict[str, dict[str, tuple[bool, list[str]]]] = {}
    for tag in results:
        verdict[tag] = {}
        for name, *_ in CASES:
            m = results[tag][name]
            checks = checks_for(name, m)
            if tag != "before" and "before" in results and name != "N1" and \
                    name not in EXPECT_BEFORE_FAIL:
                delta = metric_diff(results["before"][name], m)
                checks.append(("metric-for-metric identical to before", not delta))
            failed = [label for label, ok in checks if not ok]
            verdict[tag][name] = (not failed, failed)

    tags = [t for t in results if t not in mutant_tags]
    width = 41
    print()
    print(f"| case | {'scenario':<52} | " + " | ".join(f"{t:<{width}}" for t in tags) + " |")
    print(f"|------|{'-' * 54}|" + "|".join("-" * (width + 2) for _ in tags) + "|")
    for name, _, _, desc in CASES:
        cells = []
        for t in tags:
            ok = verdict[t][name][0]
            cells.append(f"{'PASS' if ok else 'FAIL'} {summary(results[t][name])}"[:width])
        print(f"| {name:<4} | {desc:<52} | " + " | ".join(f"{c:<{width}}" for c in cells) + " |")
    print("\nlegend: E=candidates registered at 0x80026714 after the phase, sh=shadow diffs in "
          "the phase,\n        out=overlay_cps_probe outcome x count (5 = continuation diff "
          f"gate), scan=try_load_region calls in the {EDGES}-edge phase")

    for t in tags:
        for name, *_ in CASES:
            ok, failed = verdict[t][name]
            if ok:
                continue
            m = results[t][name]
            print(f"\n[{t}] {name} FAILED:")
            for label in failed:
                print(f"    - {label}")
            print(f"    observed: e_cands={m['e_cands']} e_init={m['e_init']} "
                  f"phase_loads={m['phase_loads']} phase_shadow_calls="
                  f"{m['phase_shadow_calls']} probe: count={m['probe_count']} "
                  f"chosen_addr={m['probe_found']} chosen_nranges={m['probe_nrange']} "
                  f"cands_in_range={m['probe_ncand']} crc_matched={m['probe_matched']} "
                  f"outcome={m['probe_outcome']}")
    if "before" in results:
        for t in tags:
            if t == "before":
                continue
            delta = metric_diff(results["before"]["N1"], results[t]["N1"])
            if delta:
                print(f"\nnote [{t}] N1 differs from before only in: " + "; ".join(delta))

    ok = True
    if args.mode == "tree":
        ok = all(v[0] for v in verdict["tree"].values())
        print("\nRESULT:", "PASS (tree loader passes every case)" if ok else
              "FAIL (tree loader fails a case above)")
        return 0 if ok else 1
    before_ok = all(verdict["before"][n][0] == (n not in EXPECT_BEFORE_FAIL)
                    for n, *_ in CASES)
    after_tags = [t for t in tags if t != "before"]
    after_ok = all(all(v[0] for v in verdict[t].values()) for t in after_tags)
    print("\nRESULT:")
    print(f"  before  : {'as required' if before_ok else 'UNEXPECTED'} "
          "(must FAIL P1,P2 and PASS N1..N5)")
    for t in after_tags:
        good = all(v[0] for v in verdict[t].values())
        print(f"  {t:<8}: {'PASS all cases' if good else 'FAILS a case'}")
    mutants_ok = True
    if mutant_tags:
        print("\nmutant self-check (each wrong fix must be caught):")
        for tag, desc, _, must in MUTANTS:
            failing = {n for n, v in verdict[tag].items() if not v[0]}
            caught = must <= failing
            mutants_ok &= caught
            print(f"  {tag:<17} {desc:<61} fails {','.join(sorted(failing)) or '-':<14} "
                  f"(must: {','.join(sorted(must))}) -> {'caught' if caught else 'MISSED'}")
    ok = before_ok and after_ok and mutants_ok
    print("  =>", "regression reproduced on the pre-fix loader and fixed" if ok
          else "NOT as required")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
