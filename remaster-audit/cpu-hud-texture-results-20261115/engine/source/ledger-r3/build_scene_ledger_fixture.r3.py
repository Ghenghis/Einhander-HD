"""CPU-only fixture driver r3 for scene_ledger r3 (claude-einhander). Builds and runs FOUR executables, each linked
with scene_ledger.r3.cpp (compiled with scene_ledger.r3.h); all must pass:
  r0reg : the UNCHANGED r0 suite test_scene_ledger.r0.cpp (c1d389f1; revision r0, 99 checks, actual PASS in
          ledger-r1-run1) compiled with scene_ledger.r0.h;
  r1reg : the UNCHANGED r1 suite test_scene_ledger.r1.cpp (eb4655ec; revision r1, 32 checks, actual PASS in
          ledger-r1-run1) compiled with scene_ledger.r1.h;
  r2reg : the UNCHANGED r2 suite test_scene_ledger.r2.cpp (7f7bd5dd; revision r2, 28 authored checks, unrun)
          compiled with scene_ledger.r2.h;
  r3    : test_scene_ledger.r3.cpp (revision r3, 29 authored checks) = the r2 suite plus the root msg_2fe98abb case:
          a draw with native_screen_mapping == 2 is unknown (identity is exactly 1).
scene_ledger.r3.h / .cpp are r2 (9bcb4ea1 / 10585241) with that one correction (see the r2-to-r3 diffs). This driver
is build_scene_ledger_fixture.r2.py (2d31c89c) with the inputs, fixtures, copies and linked cpp changed.
Rules inherited from build_t2_fixture.r4.py (7b39f6a4), whose lines 77-271 (sha, now, BLOCKS, TEMPLATE, lf_lines,
native_block, divide_block, derive_pgxp, write_exact, run_child) are byte copies below (sed -n); divide_block and
derive_pgxp are unused here (the ledger closure has no T2/pgxp input):
  - raw-byte pins first; a single in-memory read per input; every executed copy re-hashed after writing;
  - ledger native closure: the 12 BLOCKS from raw-pinned v66-r3 gpu.c / gpu_gl_renderer.c in BYTES after
    CRLF->LF, wrapped by the ledger r0 TEMPLATE into scene_ledger_native_unpack.inc; warnings stay strict.
Run ONLY under a grant naming the CPU, inside the required outer envelope (or a verified copy of it)
  remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py
  sha256 fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36
  options: --cpu N --timeout 120 --max-job-mib 1024 --no-window
No GL, SDK, game or runtime. Steps: extract, copies, toolchain pin, compile-r0reg (45 s), run-r0reg (10 s),
compile-r1reg, run-r1reg, compile-r2reg, run-r2reg, compile-r3, run-r3 (45 s / 10 s each). Children are CREATE_NO_WINDOW|BELOW_NORMAL with bounded waits; the envelope owns
tree cleanup and the 120 s whole-job limit. result.json is written in try/finally (best effort). The compiler is
hashed then executed by path; a swap in between is not excluded."""
import argparse, datetime, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
LEDGER0 = HERE.parent / "ledger-r0"
LEDGER1 = HERE.parent / "ledger-r1"
LEDGER2 = HERE.parent / "ledger-r2"
R = Path("C:/github/Einhander")
V66 = R / "remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3/src"
INPUTS = {  # name -> (path, sha256)
    "gpu.c": (V66 / "gpu.c", "3d8b5d3e23c42a22fe1cecbe1287a286f2f4305147d67cb1039bdef96f628689"),
    "gpu_gl_renderer.c": (V66 / "gpu_gl_renderer.c",
                          "b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16"),
    "scene_ledger.r0.h": (LEDGER0 / "scene_ledger.r0.h",
                          "220d1a5e8426ffe20a7d9abb776f629dc08b51be76188ef29d37e6bb7455adbc"),
    "test_scene_ledger.r0.cpp": (LEDGER0 / "test_scene_ledger.r0.cpp",
                                 "c1d389f1490fb178eb61a25640bdb47c53740d85f8a1dcc96a7ac7e543f4809a"),
    "scene_ledger.r1.h": (LEDGER1 / "scene_ledger.r1.h", "f080658b11c2692de5d47c88989d203cd78bb2b058b128012ff45a394b62f15c"),
    "test_scene_ledger.r1.cpp": (LEDGER1 / "test_scene_ledger.r1.cpp",
                                 "eb4655ec65a65599b1cf1fbbe5a3cf48eced5ee847a599a9930eabfc7d468cc2"),
    "scene_ledger.r2.h": (LEDGER2 / "scene_ledger.r2.h", "9bcb4ea1f5bb5da219d11072b547300ea4c5f178381964751b6b57c293d5167d"),
    "test_scene_ledger.r2.cpp": (LEDGER2 / "test_scene_ledger.r2.cpp",
                                 "7f7bd5ddbba09279c2c08ef4250a47d53e01da92c00eaa566ec317346a13a5e6"),
    "scene_ledger.r3.h": (HERE / "scene_ledger.r3.h", "9a0af4a903cfbd653ed858cec2f23e71ade8322fe6e55255e1dbddff833073fd"),
    "scene_ledger.r3.cpp": (HERE / "scene_ledger.r3.cpp",
                            "234993106083f7ed5633d50b6a0872851397c8d6198bc8f508ecb1cb4564513e"),
    "test_scene_ledger.r3.cpp": (HERE / "test_scene_ledger.r3.cpp",
                                 "a51b2c1d6676cab2642e7196f28fdebc509029c4035db82f21b450f568af23b4"),
}
PGXP_DELTA_OFFSET = 3986
PGXP_DELTA_OLD = b"*x16/*y16"
PGXP_DELTA_NEW = b"*x16 and *y16"
PGXP_DERIVED_SHA = "50a6ef6d335c7b6cd678ed50c17f4a4c506ed868537439e6b01e2dacaaa88e52"
CC = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")
TOOLCHAIN = {
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Werror"]
FIXTURES = {"r0reg": ("scene_ledger", "r0", 99), "r1reg": ("scene_ledger", "r1", 32), "r2reg": ("scene_ledger", "r2", 28),
            "r3": ("scene_ledger", "r3", 29)}
HIDDEN_BELOW_NORMAL = 0x08000000 | 0x00004000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---- byte copy of build_scene_ledger_fixture.r0.py (55901a53) lines 61-153: BLOCKS and TEMPLATE ----
BLOCKS = {
    "sign_extend": ("gpu.c", b"static int32_t sign_extend(uint32_t val, int bits) {",
                    b"static int32_t sign_extend(uint32_t val, int bits) {", b"}", 4,
                    "97dd1b03dd35e010d69d310aab285a17e87c06691221a05356b35d97973c1940"),
    "parse_vertex": ("gpu.c", b"static void parse_vertex(uint32_t word, int32_t* x, int32_t* y) {",
                     b"static void parse_vertex(uint32_t word, int32_t* x, int32_t* y) {", b"}", 4,
                     "971000ac2c1fe5e0d6cd33d460988ae9f40a3491298d6b37eb7b2c81bb624949"),
    "word_count": ("gpu.c", b"static int gp0_command_word_count(uint8_t opcode) {",
                   b"static int gp0_command_word_count(uint8_t opcode) {", b"}", 85,
                   "c5f6fa67dfb83120d0c8a902258f33db4a9523bb1376743b51d681aa18040598"),
    "fill": ("gpu.c", b"static void gp0_exec_fill_rect(void) {",
             b"    uint32_t dst_x = gp0_cmd_buf[1] & 0x3F0u;          /* X masked to 16-pixel alignment */",
             b"    uint32_t height = (gp0_cmd_buf[2] >> 16) & 0x1FFu;", 4,
             "e47c795b35adedcc0fd38a456427e4a4be5721b9d3a588376a0a5103f78a965f"),
    "copy": ("gpu.c", b"static void gp0_execute_command(void) {",
             b"            int src_x = gp0_cmd_buf[1] & 0x3FF;", b"            if (h == 0) h = 0x200;", 8,
             "fc758e038ad110ceae00c9a55cf6d0fa425dfc6781d10cf8db56619778c3a790"),
    "cpu_to_vram": ("gpu.c", b"static void gp0_exec_cpu_to_vram(void) {",
                    b"    vram_write_x = gp0_cmd_buf[1] & 0x3FFu;",
                    b"    vram_write_h = (h == 0) ? 0x200 : (uint16_t)h;", 8,
                    "1998ffd79b8e6d4007cf22e9070dd741c83f26f11f231412c59353612ce9d152"),
    "vram_to_cpu": ("gpu.c", b"static void gp0_exec_vram_to_cpu(void) {",
                    b"    vram_read_x = gp0_cmd_buf[1] & 0x3FFu;",
                    b"    vram_read_h = (h == 0) ? 0x200 : (uint16_t)h;", 7,
                    "6d11eb6299945a63f950fcae1b459ea90ef607ebf10ec743cc27ce82b2c32fa4"),
    "mono_rect_size": ("gpu.c", b"static void gp0_exec_mono_rect(void) {",
                       b"    int w = gp0_cmd_buf[2] & 0xFFFFu;", b"    if (h > 511)  h = 511;", 4,
                       "7e56cc9f946ea3c505e3cd1bf1aa23a99684ab7338a37f8b0c204bad9eaff672"),
    "textured_rect_size": ("gpu.c", b"static void gp0_exec_textured_rect(void) {",
                           b"    int w = gp0_cmd_buf[3] & 0x3FF;", b"    if (h > 511)  h = 511;", 4,
                           "c7d973123942f91019d94d75e8d5395ee5d05833789afe142fc2b30e573ccef6"),
    "clut": ("gpu.c", b"static void gp0_exec_textured_tri(void) {",
             b"    uint16_t clut_x = (clut & 0x3F) * 16;", b"    uint16_t clut_y = (clut >> 6) & 0x1FF;", 2,
             "ce195f2af16b2d5fc19cf4d94890f5adc49ac42dc3ff93bba7b4e8719abbf029"),
    "poly_tpage": ("gpu.c", b"static void gp0_exec_textured_tri(void) {",
                   b"    uint16_t tpage = tpage_word & 0x1FF;", b"    uint16_t tpage = tpage_word & 0x1FF;", 1,
                   "89e95d52143777686c79e545f5c4a2461e310951077bf4814509ffb56649d868"),
    "page": ("gpu_gl_renderer.c", b"static void gpu_textured_triangle(const int *xs, const int *ys,",
             b"    int base_x = (texpage & 0xF) * 64;",
             b"    int depth  = (texpage >> 7) & 3; if (depth > 2) depth = 2;", 3,
             "648c6a2a2a82359b187f3b0e3adb9e82cc2e43bdb28245846b9c2c65506f70b1"),
}
# Fixed wrapper text; "@name@" lines are replaced by the extracted block (between BEGIN/END markers).
TEMPLATE = b"""// scene_ledger_native_unpack.inc -- GENERATED by build_scene_ledger_fixture.r0.py; do not edit.
// Lines between BEGIN and END markers are byte-exact copies (after CRLF->LF) of the raw-pinned native sources
// named in each marker; everything else is the driver's fixed template.
#include <stdint.h>
namespace scene_ledger_native {
@sign_extend@
@parse_vertex@
@word_count@
static inline void fill_unpack(const uint32_t *gp0_cmd_buf, uint32_t *o_x, uint32_t *o_y, uint32_t *o_w,
                               uint32_t *o_h) {
@fill@
    *o_x = dst_x; *o_y = dst_y; *o_w = width; *o_h = height;
}
static inline void copy_unpack(const uint32_t *gp0_cmd_buf, int *o_sx, int *o_sy, int *o_dx, int *o_dy, int *o_w,
                               int *o_h) {
@copy@
    *o_sx = src_x; *o_sy = src_y; *o_dx = dst_x; *o_dy = dst_y; *o_w = w; *o_h = h;
}
static inline void cpu_to_vram_unpack(const uint32_t *gp0_cmd_buf, int *o_x, int *o_y, int *o_w, int *o_h) {
    uint16_t vram_write_x, vram_write_y, vram_write_w, vram_write_h;   /* gpu.c globals are uint16_t */
@cpu_to_vram@
    *o_x = vram_write_x; *o_y = vram_write_y; *o_w = vram_write_w; *o_h = vram_write_h;
}
static inline void vram_to_cpu_unpack(const uint32_t *gp0_cmd_buf, int *o_x, int *o_y, int *o_w, int *o_h) {
    uint16_t vram_read_x, vram_read_y, vram_read_w, vram_read_h;       /* gpu.c globals are uint16_t */
@vram_to_cpu@
    *o_x = vram_read_x; *o_y = vram_read_y; *o_w = vram_read_w; *o_h = vram_read_h;
}
static inline void mono_rect_size(const uint32_t *gp0_cmd_buf, int *o_w, int *o_h) {
@mono_rect_size@
    *o_w = w; *o_h = h;
}
static inline void textured_rect_size(const uint32_t *gp0_cmd_buf, int *o_w, int *o_h) {
@textured_rect_size@
    *o_w = w; *o_h = h;
}
static inline void clut_unpack(uint16_t clut, int *o_x, int *o_y) {
@clut@
    *o_x = clut_x; *o_y = clut_y;
}
static inline uint16_t poly_tpage(uint16_t tpage_word) {
@poly_tpage@
    return tpage;
}
static inline void page_unpack(uint16_t texpage, int *o_x, int *o_y, int *o_depth) {
@page@
    *o_x = base_x; *o_y = base_y; *o_depth = depth;
}
}  // namespace scene_ledger_native
"""


# ---- byte copy of build_scene_ledger_fixture.r0.py (55901a53) lines 175-214: lf_lines, native_block, divide_block ----
def lf_lines(raw, name):
    # Called only after the raw-byte pin check. CRLF -> LF; any remaining CR is an error.
    text = raw.replace(b"\r\n", b"\n")
    if b"\r" in text:
        raise ValueError("stray CR after CRLF normalization: " + name)
    return text.split(b"\n")


def native_block(lines, anchor, first, last, count):
    a = [i for i, l in enumerate(lines) if l == anchor]
    if len(a) != 1:
        raise ValueError("anchor not unique: %r" % anchor)
    end = next((i for i in range(a[0] + 1, len(lines)) if lines[i] == b"}"), None)
    if end is None:
        raise ValueError("function end not found: %r" % anchor)
    f = [i for i in range(a[0], end + 1) if lines[i] == first]
    if len(f) != 1:
        raise ValueError("first line not unique in function: %r" % first)
    l = next((i for i in range(f[0], end + 1) if lines[i] == last), None)
    if l is None:
        raise ValueError("last line not found: %r" % last)
    block = lines[f[0]:l + 1]
    if len(block) != count:
        raise ValueError("block line count %d != %d: %r" % (len(block), count, first))
    return b"\n".join(block) + b"\n", f[0] + 1


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
    name, revision, checks = FIXTURES[key]
    try:
        line = json.loads((out / f"fixture-{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        rows[-1]["passed"] = False
        rows[-1]["fixture_error"] = repr(error)
        return False
    rows[-1]["fixture"] = line
    rows[-1]["passed"] = (line.get("fixture") == name and line.get("revision") == revision
                          and line.get("failures") == 0 and line.get("checks") == checks
                          and line.get("passed") is True and line.get("gl_used") is False
                          and line.get("sdk_used") is False)
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
        native = {n: lf_lines(data[n], n) for n in ("gpu.c", "gpu_gl_renderer.c")}
        ext = dict(label="extract", normalization="raw pin, then CRLF->LF bytes, then anchors", blocks={})
        rows.append(ext)
        inc = TEMPLATE
        for name, (src, anchor, first, last, count, pin) in BLOCKS.items():
            block, line_no = native_block(native[src], anchor, first, last, count)
            ext["blocks"][name] = dict(source=src, first_line=line_no, lines=count, sha256=sha(block),
                                       pinned=pin, passed=sha(block) == pin)
            marker = b"@" + name.encode() + b"@\n"
            if inc.count(marker) != 1:
                raise ValueError("template marker not unique: " + name)
            wrapped = (b"// BEGIN " + src.encode() + b" " + name.encode() + b" (sha256 " + pin.encode() + b")\n" +
                       block + b"// END " + name.encode() + b"\n")
            inc = inc.replace(marker, wrapped)
        if any(b"@" + n.encode() + b"@" in inc for n in BLOCKS):
            raise ValueError("unreplaced template marker")
        ext["passed"] = all(b["passed"] for b in ext["blocks"].values())
        if not ext["passed"]:
            return 1
        copies = {"scene_ledger_native_unpack.inc": inc, "scene_ledger.r0.h": data["scene_ledger.r0.h"],
                  "scene_ledger.r1.h": data["scene_ledger.r1.h"], "scene_ledger.r2.h": data["scene_ledger.r2.h"],
                  "scene_ledger.r3.h": data["scene_ledger.r3.h"], "scene_ledger.r3.cpp": data["scene_ledger.r3.cpp"],
                  "executed-test-r0reg.cpp": data["test_scene_ledger.r0.cpp"],
                  "executed-test-r1reg.cpp": data["test_scene_ledger.r1.cpp"],
                  "executed-test-r2reg.cpp": data["test_scene_ledger.r2.cpp"],
                  "executed-test-r3.cpp": data["test_scene_ledger.r3.cpp"]}
        result["executed_copies"] = {n: write_exact(out / n, blob) for n, blob in copies.items()}
        real_dir = Path(os.path.realpath(CC)).parent
        tools = {n: dict(path=str(real_dir / n), sha256=sha((real_dir / n).read_bytes())) for n in TOOLCHAIN}
        result["toolchain"] = dict(invoked=str(CC), invoked_sha256=sha(CC.read_bytes()), files=tools)
        if result["toolchain"]["invoked_sha256"] != TOOLCHAIN["clang++.exe"] or \
                any(tools[n]["sha256"] != s for n, s in TOOLCHAIN.items()):
            raise ValueError("compiler pin mismatch")
        result["exe_sha256"] = {}
        for key in FIXTURES:
            exe = out / f"test-scene-ledger-{key}.exe"
            if not run_child(f"compile-{key}", [CC, *FLAGS, "-I", out, out / f"executed-test-{key}.cpp",
                                                out / "scene_ledger.r3.cpp", "-o", exe], out, 0, 45, out, rows):
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
