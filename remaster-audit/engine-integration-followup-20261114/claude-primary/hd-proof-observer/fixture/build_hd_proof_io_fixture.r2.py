"""CPU-only fault/boundary fixture driver r2 for the HD proof observer r3 I/O block (claude-einhander).
Run ONLY under a grant naming the CPU, inside the required outer envelope
  remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py
  sha256 fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36
  options: --cpu 15 --timeout 120 --max-job-mib 1024 --no-window  (whole-tree Job, BelowNormal, threads 1)
That envelope is the authority for wall time, job memory and tree cleanup (run_rc2.r1.py cd3988af has no
memory cap and is NOT the envelope for this driver). No GL, window or game.
r0 (a03b7782) and r1 (3f070a2e) are preserved and must not be executed.
r2 changes from r1: the envelope contract above; the test source is hashed from the bytes held in memory and
executed-test.c is written from those same bytes and re-hashed before compile (no check/use race on the test);
the result manifest is best-effort: a forced outer Job kill can prevent the finally block from running.
The compiler binaries are hashed before compile and executed by path; a swap between hash and exec is not
excluded by this driver (the toolchain directory is outside the run's control).

Usage: python build_hd_proof_io_fixture.r2.py --cpu N --out-root ABS_DIR
  extract  (in-process) from BOTH pinned r3 patches, the added lines from 'HD-PROOF-IO BEGIN' through
           'HD-PROOF-IO END' (every line must be an added line); both blocks byte-identical, equal to BLOCK_SHA,
           declaring EXACTLY the 13 statics the test resets. No git, no base checkout, no canonical file touched.
  compile  clang++ (pinned wrapper + pinned real driver/libraries) -x c -std=c11 -Wall -Wextra -Werror   45 s
  run      test exe -> exit 0, 36 checks, passed, gl_used false, real_file_io false                      10 s
Children: one at a time, CREATE_NO_WINDOW|BELOW_NORMAL (0x08004000), affinity inherited from this
process (set to N), bounded wait; on timeout only that child is killed and the outer Job finishes cleanup.
A result manifest is written in try/finally (best effort; see above), including exceptions, every child's argv, PID, creation
time, exit and elapsed. Scope: real_file_io=false describes the observer block's stdio, which is shimmed;
the driver and the fixture still write their own output files."""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, time, traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
TEST = HERE / "test_hd_proof_io.r0.c"
TEST_SHA = "f80a55f8267bb987482c8cfd66e70dfef162c9e3a3c95d6e532c307576f24e9d"
PATCHES = {
    "canonical": (HERE.parent / "hd-proof-observer.canonical-92d08057.r3.patch",
                  "44f7444e6bf6616fd8e66815d0cb8d78599d1946f6312752976fe6a4a9bfc985"),
    "v68": (HERE.parent / "hd-proof-observer.v68-9a878ca4.r3.patch",
            "683e046c327c4e36cafd7f80df4310d5f11cd6087ea257b501a8552232b15ffc"),
}
BLOCK_SHA = "e31d6795459a62c73db8334ca77d16e82a357960d3c744d4c71f5e2c4233b02c"   # LF-joined, final LF
STATICS = {"s_hd_proof_file", "s_hd_proof_init_done", "s_hd_proof_log_on", "s_hd_proof_capped",
           "s_hd_proof_open_error", "s_hd_proof_start_offset", "s_hd_proof_bytes", "s_hd_proof_write_errors",
           "s_hd_proof_dropped_lines", "s_hd_proof_close_errors", "s_hd_proof_epoch", "s_hd_proof_seen_epoch",
           "s_hd_proof_lines"}
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")
TOOLCHAIN = {   # file name -> sha256, relative to the resolved directory of CC
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",   # llvm-mingw target wrapper
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
FLAGS = ["-x", "c", "-std=c11", "-Wall", "-Wextra", "-Werror"]
CHECKS = 36
FLAGS_HIDDEN_BELOW_NORMAL = 0x08000000 | 0x00004000


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def added_block(patch_text):
    """Exact added lines of the IO block; every line in the block must be an added ('+') line."""
    lines = patch_text.split("\n")
    begin = [i for i, l in enumerate(lines) if "HD-PROOF-IO BEGIN" in l]
    end = [i for i, l in enumerate(lines) if "HD-PROOF-IO END" in l]
    if len(begin) != 1 or len(end) != 1 or end[0] <= begin[0]:
        raise ValueError("exactly one ordered HD-PROOF-IO block required in the patch")
    body = lines[begin[0]:end[0] + 1]
    if not all(l.startswith("+") and not l.startswith("+++") for l in body):
        raise ValueError("HD-PROOF-IO block contains non-added lines")
    block = "\n".join(l[1:] for l in body) + "\n"
    names = set()
    for l in block.split("\n"):
        if l.startswith("static ") and "(" not in l:
            names.update(re.findall(r"\bs_hd_proof_\w+", l))
    return block, names


def run_child(label, argv, cwd, expected, cap, out, rows):
    log = out / f"{label}.log"
    row = dict(label=label, argv=[str(a) for a in argv], expected_exit=expected, cap_seconds=cap,
               pid=None, creation_unix=None, exit=None, timed_out=None, seconds=None, passed=False)
    rows.append(row)                        # recorded before launch, so a failure still leaves the argv
    t = time.monotonic()
    with open(log, "x", encoding="utf-8") as stream:
        child = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                 creationflags=FLAGS_HIDDEN_BELOW_NORMAL)
        row["pid"] = child.pid
        try:
            row["creation_unix"] = psutil.Process(child.pid).create_time()
        except psutil.Error:
            row["creation_unix"] = None     # exited before it could be read; exit code still recorded
        try:
            row["exit"] = child.wait(timeout=cap)
            row["timed_out"] = False
        except subprocess.TimeoutExpired:
            row["timed_out"] = True
            child.kill()                    # this child only; the outer Job owns tree cleanup
            try:
                row["exit"] = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                row["exit"] = None
    row["seconds"] = round(time.monotonic() - t, 3)
    row["output_tail"] = log.read_text(encoding="utf-8", errors="replace")[-3000:]
    row["passed"] = row["exit"] == expected and row["timed_out"] is False
    return row["passed"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--out-root", required=True)
    a = ap.parse_args()
    root = Path(a.out_root)
    if not root.is_absolute():
        raise SystemExit("--out-root must be absolute")
    root = root.resolve()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = root / stamp
    out.mkdir(parents=True, exist_ok=False)          # exclusive per run
    result = dict(tool=Path(__file__).name, builder_sha256=sha_file(__file__), cpu=a.cpu, out=str(out),
                  started_utc=now(), gl_used=False, steps=[], passed=False, exception=None,
                  io_scope="real_file_io=false means the observer block's stdio is shimmed; "
                           "the driver and the fixture write their own files under out")
    rows = result["steps"]
    try:
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([a.cpu])
        result["driver_pid"], result["driver_creation_unix"] = me.pid, me.create_time()
        test_bytes = TEST.read_bytes()                 # the only read of the test source
        if sha_bytes(test_bytes) != TEST_SHA:
            raise ValueError("test source sha mismatch")
        result["test_sha256"] = TEST_SHA
        result["envelope_required"] = dict(
            path="remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py",
            sha256="fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36",
            options=["--cpu", "15", "--timeout", "120", "--max-job-mib", "1024", "--no-window"],
            verified_by_this_driver=False)       # the envelope launches this driver; it records itself
        blocks = {}
        for name, (path, pin) in PATCHES.items():
            data = path.read_bytes()
            if sha_bytes(data) != pin:
                raise ValueError(name + " patch pin mismatch")
            blocks[name] = added_block(data.decode("utf-8"))
        block, names = blocks["canonical"]
        ext = dict(label="extract", block_sha256=sha_bytes(block.encode("utf-8")), statics=sorted(names),
                   canonical_equals_v68=blocks["canonical"][0] == blocks["v68"][0])
        ext["passed"] = ext["canonical_equals_v68"] and ext["block_sha256"] == BLOCK_SHA and names == STATICS
        rows.append(ext)
        if not ext["passed"]:
            return 1
        (out / "hd_proof_io_extracted.inc").write_text(block, encoding="utf-8", newline="\n")
        with open(out / "executed-test.c", "xb") as f:   # written from the verified bytes
            f.write(test_bytes)
        copied = sha_file(out / "executed-test.c")
        result["executed_test_sha256"] = copied
        if copied != TEST_SHA:
            raise ValueError("executed test copy sha mismatch")
        real_dir = Path(os.path.realpath(CC)).parent
        tools = {n: dict(path=str(real_dir / n), sha256=sha_file(real_dir / n)) for n in TOOLCHAIN}
        result["toolchain"] = dict(invoked=str(CC), invoked_sha256=sha_file(CC), resolved_dir=str(real_dir), files=tools)
        if result["toolchain"]["invoked_sha256"] != TOOLCHAIN["clang++.exe"] or \
                any(tools[n]["sha256"] != s for n, s in TOOLCHAIN.items()):
            raise ValueError("compiler pin mismatch")
        exe = out / "test-hd-proof-io.exe"
        if not run_child("compile", [CC, *FLAGS, "-I", out, out / "executed-test.c", "-o", exe], out, 0, 45, out, rows):
            return 1
        result["exe_sha256"] = sha_file(exe)
        if not run_child("run", [exe, out / "fixture-result.json"], out, 0, 10, out, rows):
            return 1
        try:
            line = json.loads((out / "fixture-result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            rows[-1]["passed"] = False
            rows[-1]["fixture_error"] = repr(error)
            return 1
        rows[-1]["fixture"] = line
        rows[-1]["passed"] = (line.get("checks") == CHECKS and line.get("passed") is True
                              and line.get("gl_used") is False and line.get("real_file_io") is False)
        if not rows[-1]["passed"]:
            return 1
        result["passed"] = True
        return 0
    except BaseException as error:              # recorded, never swallowed silently
        result["exception"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        return 1
    finally:
        result["ended_utc"] = now()
        with open(out / "result.json", "x", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        print(json.dumps(dict(out=str(out), passed=result["passed"],
                              steps={r["label"]: r.get("passed") for r in rows})))


if __name__ == "__main__":
    sys.exit(main())
