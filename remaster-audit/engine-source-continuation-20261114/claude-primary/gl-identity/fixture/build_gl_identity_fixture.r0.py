"""CPU-only fixture for the GL identity patch (claude-einhander). Run ONLY under a grant naming the CPU.
No GL, no window, no DLL, no game. The code under test is extracted from the pinned patches, never retyped.

Usage: python build_gl_identity_fixture.r0.py --cpu N --out-root DIR
Steps (each a single child, BelowNormal, affinity N, bounded timeout, exit checked; stops at first failure):
  extract  (in-process) verify both patch pins; take hunk-1 '+' lines; require canonical == v68 bodies;
           require hunk 2 to add exactly '    gl_identity_capture();'; write gl_identity_extracted.inc
  compile  clang++ -x c -std=c11 -Wall -Wextra -Werror  test_gl_identity.r0.c -> exe     cap 45 s
  run      exe result.json stdout.txt -> exit 0, 15 checks, passed true, gl_used false    cap 10 s
Writes DIR/<stamp>/{result.json, extract.json, gl_identity_extracted.inc, executed-test.c, *.log, exe,
fixture-result.json, fixture-stdout.txt}; nothing outside DIR."""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
TEST = HERE / "test_gl_identity.r0.c"
PATCHES = {
    "canonical": (HERE.parent / "gl-identity.canonical-92d08057.r0.patch",
                  "42690420aefb2de4f48b98420903a3587564cc63802ddcb4849798b2e9244ac3"),
    "v68": (HERE.parent / "gl-identity.v68-9a878ca4.r0.patch",
            "2f603398d7971bca206328dcfe64ebadf5896445055d12388ba1477f051e7538"),
}
CC = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe"
FLAGS = ["-x", "c", "-std=c11", "-Wall", "-Wextra", "-Werror"]
CHECKS = 15


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hunks(text):
    out, cur = [], None
    for line in text.split("\n"):
        if line.startswith("@@"):
            cur = []
            out.append(cur)
        elif cur is not None:
            cur.append(line)
    return out


def extract():
    bodies, calls = {}, {}
    for name, (path, pin) in PATCHES.items():
        data = path.read_bytes()
        if sha(data) != pin:
            raise SystemExit(f"{name} patch pin mismatch")
        hs = hunks(data.decode("utf-8"))
        if len(hs) != 2:
            raise SystemExit(f"{name} patch must have exactly 2 hunks")
        added = [l[1:] for l in hs[0] if l.startswith("+")]
        if not added or not added[0].startswith("/* Adapter identity") or \
                not any(l.startswith("static void gl_identity_capture(void)") for l in added):
            raise SystemExit(f"{name} hunk 1 is not the identity block")
        second = [l[1:] for l in hs[1] if l.startswith("+")]
        if second != ["    gl_identity_capture();"] or any(l.startswith("-") for l in hs[1]):
            raise SystemExit(f"{name} hunk 2 must only add the capture call")
        bodies[name] = "\n".join(added) + "\n"
        calls[name] = second
    if bodies["canonical"] != bodies["v68"]:
        raise SystemExit("canonical and v68 identity blocks differ")
    return bodies["canonical"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--expect-test-sha", default=None)
    a = ap.parse_args()
    if a.expect_test_sha and sha(TEST.read_bytes()) != a.expect_test_sha.lower():
        raise SystemExit("test source sha mismatch")
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([a.cpu])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out_root) / stamp
    out.mkdir(parents=True, exist_ok=False)
    block = extract()
    (out / "gl_identity_extracted.inc").write_text(block, encoding="utf-8", newline="\n")
    shutil.copyfile(TEST, out / "executed-test.c")
    with open(out / "extract.json", "x", encoding="utf-8") as f:
        json.dump(dict(patches={k: dict(path=str(p), sha256=s) for k, (p, s) in PATCHES.items()},
                       extracted_sha256=sha(block.encode("utf-8")), extracted_lines=block.count("\n")), f, indent=1)
    exe = out / "test-gl-identity.exe"
    steps = [("compile", [CC, *FLAGS, "-I", str(out), str(out / "executed-test.c"), "-o", str(exe)], 0, 45),
             ("run", [str(exe), str(out / "fixture-result.json"), str(out / "fixture-stdout.txt")], 0, 10)]
    rows, passed = [], True
    result = dict(tool=Path(__file__).name, builder_sha256=sha(Path(__file__).read_bytes()),
                  test_sha256=sha(TEST.read_bytes()), extracted_sha256=sha(block.encode("utf-8")), cpu=a.cpu,
                  started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), gl_used=False)
    for label, args, expected, cap in steps:
        log = out / f"{label}.log"
        t = time.monotonic()
        with open(log, "w", encoding="utf-8") as stream:
            child = subprocess.Popen(args, cwd=out, stdout=stream, stderr=subprocess.STDOUT, creationflags=0x4000)
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
        if ok and label == "run":
            line = json.loads((out / "fixture-result.json").read_text(encoding="utf-8"))
            ok = line.get("checks") == CHECKS and line.get("passed") is True and line.get("gl_used") is False
            row["fixture"] = line
        row["passed"] = ok
        rows.append(row)
        if not ok:
            passed = False
            break
    result.update(steps=rows, passed=passed, exe_sha256=sha(exe.read_bytes()) if exe.exists() else None,
                  ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with open(out / "result.json", "x", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(dict(out=str(out), passed=passed, steps={r["label"]: r["passed"] for r in rows})))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
