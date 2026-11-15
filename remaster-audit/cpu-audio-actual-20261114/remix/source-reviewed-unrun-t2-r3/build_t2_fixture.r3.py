"""CPU-only fixture driver r3 for T2 r3 (claude-einhander; drivers r0 2173b570, r1 fc07ca5f, r2 11cfcadb superseded, not to be run; requires fixture==t2, revision==r3, failures==0). Derived from the T1 driver r2 (b0423d8a) with the same
rules: raw-byte pins first, gte.cpp CRLF->LF normalization before the divide-block anchors, single in-memory read
and re-hashed copies. Extra inputs over T1: v68 src/scene_capture.h (ScenePrimitive/SceneCaptureInfo layout),
remix_t2.r3.h (builder/resolver/slot/gate) and test_t2.r3.cpp (82 checks: B1-B14, R1-R5, H1-H3, G1-G2).
Run ONLY under a grant naming
the CPU, inside the required outer envelope
  remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py
  sha256 fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36
  options: --cpu 15 --timeout 120 --max-job-mib 1024 --no-window
No GL, SDK, game or runtime. Inputs are read ONCE into memory, pin-checked, and every executed copy is written
from those bytes and re-hashed:
  - pgxp.h from the v68 private build (PgxpView layout and flag values);
  - the exact runtime UNR divide block (from 'static uint8_t s_gte_div_table[0x101];' through the closing brace
    of gte_divide) extracted from BOTH the v61 gte.cpp that v68 links and the canonical gte.cpp; both blocks
    must be byte-identical and equal BLOCK_SHA. Nothing is retyped;
  - the oracle header and the test.
Steps: compile (clang++ -std=c++17 -Wall -Wextra -Werror, pinned toolchain, 45 s), run (10 s): exit 0,
82 checks, passed, gl_used false, sdk_used false. Children are CREATE_NO_WINDOW|BELOW_NORMAL with bounded
waits; the envelope owns tree cleanup. The result manifest is written in try/finally (best effort: a forced
outer kill can skip it). The compiler is hashed then executed by path; a swap in between is not excluded."""
import argparse, datetime, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
T1DIR = HERE.parent / "t1"
R = Path("C:/github/Einhander")
INPUTS = {  # name -> (path, sha256)
    "pgxp.h": (R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1/include/pgxp.h",
               "1f50599f51a53fdc989d1d0bb9c7aea46f0f6cc53b303048367c0f05b18c4c47"),
    "gte_v61.cpp": (R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/src/gte.cpp",
                    "139d2e49c6a77b68a1d96a4325f9c244db4f9ed1b2277187be068454304c1849"),
    "gte_canonical.cpp": (R / "windows-x64/psxrecomp/runtime/src/gte.cpp",
                          "0563d9a1da49c6c0538c1285f803939c1a9441b5485a16a4d6f7eff6f50656c0"),
    "remix_t1_reproject.r1.h": (T1DIR / "remix_t1_reproject.r1.h",
                                "4a0a536c3e2313a6e25be47fc877607c2d5006ac398828eb558218c0fe68d795"),
    "scene_capture.h": (R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1/src/scene_capture.h",
                        "b90ebe9da7f11ed0c12ad2ea041564cb45a69a061b4da89b92e05dd9858856c8"),
    "remix_t2.r3.h": (HERE / "remix_t2.r3.h", "8baba81cdbb402585f4f535d830cea822ca9b81f963fb64bc809f53ff019911b"),
    "test_t2.r3.cpp": (HERE / "test_t2.r3.cpp",
                                 "215df688a16079308e66a4c2b89fd4ab46ac32a7c5075cf8aa9f0744bdc4fff4"),
}
BLOCK_SHA = "cfa7686a59c223f358d2507674af7289dc462213e0b676165b87b60974a896ef"
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")
TOOLCHAIN = {
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Werror"]
CHECKS = 82
HIDDEN_BELOW_NORMAL = 0x08000000 | 0x00004000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def divide_block(raw_text):
    # Called only after the raw-byte pin check. Normalize CRLF -> LF; any remaining CR is an error.
    text = raw_text.replace("\r\n", "\n")
    if "\r" in text:
        raise ValueError("stray CR after CRLF normalization")
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if l == "static uint8_t s_gte_div_table[0x101];"]
    div = [i for i, l in enumerate(lines) if l.startswith("static int32_t gte_divide(")]
    if len(starts) != 1 or len(div) != 1 or div[0] <= starts[0]:
        raise ValueError("divide block anchors not unique/ordered")
    end = next((i for i in range(div[0], len(lines)) if lines[i] == "}"), None)
    if end is None:
        raise ValueError("gte_divide closing brace not found")
    return "\n".join(lines[starts[0]:end + 1]) + "\n"


def write_exact(path, data):
    with open(path, "xb") as f:
        f.write(data)
    if sha(Path(path).read_bytes()) != sha(data):
        raise ValueError("copy sha mismatch: " + str(path))
    return sha(data)


def run_child(label, argv, cwd, expected, cap, out, rows):
    row = dict(label=label, argv=[str(a) for a in argv], expected_exit=expected, cap_seconds=cap,
               pid=None, creation_unix=None, exit=None, timed_out=None, seconds=None, passed=False)
    rows.append(row)
    t = time.monotonic()
    with open(out / f"{label}.log", "x", encoding="utf-8") as stream:
        child = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                 creationflags=HIDDEN_BELOW_NORMAL)
        row["pid"] = child.pid
        try:
            row["creation_unix"] = psutil.Process(child.pid).create_time()
        except psutil.Error:
            pass
        try:
            row["exit"] = child.wait(timeout=cap)
            row["timed_out"] = False
        except subprocess.TimeoutExpired:
            row["timed_out"] = True
            child.kill()
            try:
                row["exit"] = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                row["exit"] = None
    row["seconds"] = round(time.monotonic() - t, 3)
    row["output_tail"] = (out / f"{label}.log").read_text(encoding="utf-8", errors="replace")[-3000:]
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
    out = root.resolve() / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    result = dict(tool=Path(__file__).name, builder_sha256=sha(Path(__file__).read_bytes()), cpu=a.cpu,
                  out=str(out), started_utc=now(), gl_used=False, sdk_used=False, steps=[], passed=False,
                  exception=None, envelope_required=dict(
                      path="remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py",
                      sha256="fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36",
                      options=["--cpu", "15", "--timeout", "120", "--max-job-mib", "1024", "--no-window"],
                      verified_by_this_driver=False))
    rows = result["steps"]
    try:
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([a.cpu])
        pins = dict(INPUTS)                          # every pin is a mandatory constant
        data = {}
        for name, (path, pin) in pins.items():
            blob = Path(path).read_bytes()          # the only read of each input
            if not pin or sha(blob) != pin:
                raise ValueError("input pin mismatch: " + name)
            data[name] = blob
        result["inputs"] = {n: dict(path=str(p), sha256=s) for n, (p, s) in pins.items()}
        b61 = divide_block(data["gte_v61.cpp"].decode("utf-8"))
        bcan = divide_block(data["gte_canonical.cpp"].decode("utf-8"))
        ext = dict(label="extract", block_sha256=sha(b61.encode("utf-8")), v61_equals_canonical=b61 == bcan,
                   normalization="raw pin, then CRLF->LF, then anchors",
                   raw_sha256={n: sha(data[n]) for n in ("gte_v61.cpp", "gte_canonical.cpp")})
        ext["passed"] = ext["v61_equals_canonical"] and ext["block_sha256"] == BLOCK_SHA
        rows.append(ext)
        if not ext["passed"]:
            return 1
        copies = {"gte_divide_extracted.inc": b61.encode("utf-8"), "pgxp.h": data["pgxp.h"],
                  "remix_t1_reproject.r1.h": data["remix_t1_reproject.r1.h"], "scene_capture.h": data["scene_capture.h"],
                  "remix_t2.r3.h": data["remix_t2.r3.h"],
                  "executed-test.cpp": data["test_t2.r3.cpp"]}
        result["executed_copies"] = {n: write_exact(out / n, blob) for n, blob in copies.items()}
        real_dir = Path(os.path.realpath(CC)).parent
        tools = {n: dict(path=str(real_dir / n), sha256=sha((real_dir / n).read_bytes())) for n in TOOLCHAIN}
        result["toolchain"] = dict(invoked=str(CC), invoked_sha256=sha(CC.read_bytes()), files=tools)
        if result["toolchain"]["invoked_sha256"] != TOOLCHAIN["clang++.exe"] or \
                any(tools[n]["sha256"] != s for n, s in TOOLCHAIN.items()):
            raise ValueError("compiler pin mismatch")
        exe = out / "test-t2.exe"
        if not run_child("compile", [CC, *FLAGS, "-I", out, out / "executed-test.cpp", "-o", exe], out, 0, 45, out, rows):
            return 1
        result["exe_sha256"] = sha(exe.read_bytes())
        if not run_child("run", [exe, out / "fixture-result.json"], out, 0, 10, out, rows):
            return 1
        try:
            line = json.loads((out / "fixture-result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            rows[-1]["passed"] = False
            rows[-1]["fixture_error"] = repr(error)
            return 1
        rows[-1]["fixture"] = line
        rows[-1]["passed"] = (line.get("fixture") == "t2" and line.get("revision") == "r3" and line.get("failures") == 0 and line.get("checks") == CHECKS and line.get("passed") is True
                              and line.get("gl_used") is False and line.get("sdk_used") is False)
        result["passed"] = rows[-1]["passed"]
        return 0 if result["passed"] else 1
    except BaseException as error:
        result["exception"] = "".join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        return 1
    finally:
        result["ended_utc"] = now()
        with open(out / "result.json", "x", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        print(json.dumps(dict(out=str(out), passed=result["passed"], steps={r["label"]: r.get("passed") for r in rows})))


if __name__ == "__main__":
    sys.exit(main())
