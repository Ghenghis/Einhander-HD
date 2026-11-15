"""CPU-only fixture driver r6 for T2 r6 (claude-einhander). Builds and runs ONE executable, which must pass:
  unit : test_t2.r6.cpp (fixture t2, revision r6, 50 checks) over the T2 r3 closure plus remix_t2.r4.h and
         remix_t2.r6.h (owned present lifecycle; r5 is not an input). The r6 fixture uses fake policy and hazard hooks,
         so there is no ledger closure (no gpu.c / gpu_gl_renderer.c blocks, no scene_ledger sources).
Rules inherited from build_t2_fixture.r5.py (4901aaec), which inherited them from build_t2_fixture.r4.py (7b39f6a4):
  - raw-byte pins first; a single in-memory read per input; every executed copy re-hashed after writing;
  - gte.cpp: raw pin, then CRLF->LF, then the divide-block anchors; v61 == canonical == cfa7686a. lf_lines and
    divide_block are byte copies of 7b39f6a4 lines 182-189 and 209-221 (themselves copies of 55901a53);
  - pgxp.h: the executed copy is DERIVED from the raw-pinned 1f50599f by exactly one comment-only replacement at
    byte offset 3986, "*x16/*y16" -> "*x16 and *y16", and must hash to 50a6ef6d; warnings stay strict (no
    -isystem, no -Wno-*).
Run ONLY under a grant naming the CPU, inside the required outer envelope (or a verified copy of it)
  remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py
  sha256 fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36
  options: --cpu N --timeout 120 --max-job-mib 1024 --no-window
No GL, SDK, game or runtime. Steps: extract, copies, toolchain pin, compile-unit (45 s), run-unit (10 s). Children
are CREATE_NO_WINDOW|BELOW_NORMAL with bounded waits; the envelope owns tree cleanup and the 120 s whole-job limit.
run-unit starts std::threads (foreign reset; seqlock smoke test, not a memory-model proof). result.json is written in
try/finally (best effort: a forced outer kill can skip it). The compiler is hashed then executed by path; a swap in
between is not excluded."""
import argparse, datetime, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
T2DIR = HERE.parent
T1DIR = HERE.parent.parent / "t1"
R = Path("C:/github/Einhander")
V68 = R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1"
INPUTS = {  # name -> (path, sha256)
    "pgxp.h": (V68 / "include/pgxp.h", "1f50599f51a53fdc989d1d0bb9c7aea46f0f6cc53b303048367c0f05b18c4c47"),
    "gte_v61.cpp": (R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/src/gte.cpp",
                    "139d2e49c6a77b68a1d96a4325f9c244db4f9ed1b2277187be068454304c1849"),
    "gte_canonical.cpp": (R / "windows-x64/psxrecomp/runtime/src/gte.cpp",
                          "0563d9a1da49c6c0538c1285f803939c1a9441b5485a16a4d6f7eff6f50656c0"),
    "remix_t1_reproject.r1.h": (T1DIR / "remix_t1_reproject.r1.h",
                                "4a0a536c3e2313a6e25be47fc877607c2d5006ac398828eb558218c0fe68d795"),
    "scene_capture.h": (V68 / "src/scene_capture.h", "b90ebe9da7f11ed0c12ad2ea041564cb45a69a061b4da89b92e05dd9858856c8"),
    "remix_t2.r3.h": (T2DIR / "remix_t2.r3.h", "8baba81cdbb402585f4f535d830cea822ca9b81f963fb64bc809f53ff019911b"),
    "remix_t2.r4.h": (T2DIR / "r4" / "remix_t2.r4.h", "eebb2c8fd26a2df58bd6748cfefe7a670e236029cd6dcffe279617abd8478a96"),
    "remix_t2.r6.h": (HERE / "remix_t2.r6.h", "419dea9499010e5f5524b3913f81b09db0279ce87a25861a2cb49c17554f76dd"),
    "test_t2.r6.cpp": (HERE / "test_t2.r6.cpp", "06d3b8f0749876a2746c3a425e648f3b1731b9c683883743f05359222508fc94"),
}
PGXP_DELTA_OFFSET = 3986
PGXP_DELTA_OLD = b"*x16/*y16"
PGXP_DELTA_NEW = b"*x16 and *y16"
PGXP_DERIVED_SHA = "50a6ef6d335c7b6cd678ed50c17f4a4c506ed868537439e6b01e2dacaaa88e52"
DIVIDE_BLOCK_SHA = "cfa7686a59c223f358d2507674af7289dc462213e0b676165b87b60974a896ef"
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")
TOOLCHAIN = {
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Werror"]
FIXTURES = {"unit": ("t2", 50)}
HIDDEN_BELOW_NORMAL = 0x08000000 | 0x00004000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---- byte copy of build_t2_fixture.r4.py (7b39f6a4) lines 182-189: lf_lines ----
def lf_lines(raw, name):
    # Called only after the raw-byte pin check. CRLF -> LF; any remaining CR is an error.
    text = raw.replace(b"\r\n", b"\n")
    if b"\r" in text:
        raise ValueError("stray CR after CRLF normalization: " + name)
    return text.split(b"\n")


# ---- byte copy of build_t2_fixture.r4.py (7b39f6a4) lines 209-221: divide_block ----
def divide_block(raw):
    # As build_t2_fixture.r3.py: from 's_gte_div_table' through the closing brace of gte_divide.
    lines = lf_lines(raw, "gte.cpp")
    starts = [i for i, l in enumerate(lines) if l == b"static uint8_t s_gte_div_table[0x101];"]
    div = [i for i, l in enumerate(lines) if l.startswith(b"static int32_t gte_divide(")]
    if len(starts) != 1 or len(div) != 1 or div[0] <= starts[0]:
        raise ValueError("divide block anchors not unique/ordered")
    end = next((i for i in range(div[0], len(lines)) if lines[i] == b"}"), None)
    if end is None:
        raise ValueError("gte_divide closing brace not found")
    return b"\n".join(lines[starts[0]:end + 1]) + b"\n"

# ---- end of byte copies ----


def derive_pgxp(raw):
    # Called only after the raw-byte pin check. One comment-only byte replacement; nothing else changes.
    if raw.count(PGXP_DELTA_OLD) != 1 or raw.find(PGXP_DELTA_OLD) != PGXP_DELTA_OFFSET:
        raise ValueError("pgxp.h comment token not unique at the pinned offset")
    derived = raw[:PGXP_DELTA_OFFSET] + PGXP_DELTA_NEW + raw[PGXP_DELTA_OFFSET + len(PGXP_DELTA_OLD):]
    if sha(derived) != PGXP_DERIVED_SHA:
        raise ValueError("derived pgxp.h sha mismatch")
    return derived


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


def fixture_ok(rows, out, key):
    name, checks = FIXTURES[key]
    try:
        line = json.loads((out / f"fixture-{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        rows[-1]["passed"] = False
        rows[-1]["fixture_error"] = repr(error)
        return False
    rows[-1]["fixture"] = line
    rows[-1]["passed"] = (line.get("fixture") == name and line.get("revision") == "r6" and line.get("failures") == 0
                          and line.get("checks") == checks and line.get("passed") is True
                          and line.get("gl_used") is False and line.get("sdk_used") is False)
    return rows[-1]["passed"]


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
                      options=["--cpu", str(a.cpu), "--timeout", "120", "--max-job-mib", "1024", "--no-window"],
                      verified_by_this_driver=False))
    rows = result["steps"]
    try:
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([a.cpu])
        data = {}
        for name, (path, pin) in INPUTS.items():
            blob = Path(path).read_bytes()          # the only read of each input
            if not pin or sha(blob) != pin:
                raise ValueError("input pin mismatch: " + name)
            data[name] = blob
        result["inputs"] = {n: dict(path=str(p), sha256=s) for n, (p, s) in INPUTS.items()}
        ext = dict(label="extract", normalization="raw pin, then CRLF->LF bytes, then anchors")
        rows.append(ext)
        div61 = divide_block(data["gte_v61.cpp"])
        divcan = divide_block(data["gte_canonical.cpp"])
        derived_pgxp = derive_pgxp(data["pgxp.h"])
        ext["divide_block"] = dict(sha256=sha(div61), v61_equals_canonical=div61 == divcan)
        ext["pgxp_derivation"] = dict(original_sha256=sha(data["pgxp.h"]), derived_sha256=sha(derived_pgxp),
                                      offset=PGXP_DELTA_OFFSET, old=PGXP_DELTA_OLD.decode("ascii"),
                                      new=PGXP_DELTA_NEW.decode("ascii"),
                                      original_bytes=len(data["pgxp.h"]), derived_bytes=len(derived_pgxp))
        ext["passed"] = div61 == divcan and sha(div61) == DIVIDE_BLOCK_SHA
        if not ext["passed"]:
            return 1
        copies = {"gte_divide_extracted.inc": div61, "pgxp.h": derived_pgxp,
                  "remix_t1_reproject.r1.h": data["remix_t1_reproject.r1.h"], "scene_capture.h": data["scene_capture.h"],
                  "remix_t2.r3.h": data["remix_t2.r3.h"], "remix_t2.r4.h": data["remix_t2.r4.h"],
                  "remix_t2.r6.h": data["remix_t2.r6.h"], "executed-test-unit.cpp": data["test_t2.r6.cpp"]}
        result["executed_copies"] = {n: write_exact(out / n, blob) for n, blob in copies.items()}
        real_dir = Path(os.path.realpath(CC)).parent
        tools = {n: dict(path=str(real_dir / n), sha256=sha((real_dir / n).read_bytes())) for n in TOOLCHAIN}
        result["toolchain"] = dict(invoked=str(CC), invoked_sha256=sha(CC.read_bytes()), files=tools)
        if result["toolchain"]["invoked_sha256"] != TOOLCHAIN["clang++.exe"] or \
                any(tools[n]["sha256"] != s for n, s in TOOLCHAIN.items()):
            raise ValueError("compiler pin mismatch")
        result["exe_sha256"] = {}
        for key in FIXTURES:
            exe = out / f"test-t2r6-{key}.exe"
            if not run_child(f"compile-{key}", [CC, *FLAGS, "-I", out, out / f"executed-test-{key}.cpp", "-o", exe],
                             out, 0, 45, out, rows):
                return 1
            result["exe_sha256"][key] = sha(exe.read_bytes())
            if not run_child(f"run-{key}", [exe, out / f"fixture-{key}.json"], out, 0, 10, out, rows):
                return 1
            if not fixture_ok(rows, out, key):
                return 1
        result["passed"] = all(r.get("passed") for r in rows)
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
