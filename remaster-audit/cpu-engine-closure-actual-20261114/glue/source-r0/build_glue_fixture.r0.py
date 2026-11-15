"""CPU-only build-closure driver r0 for the FROZEN ledger glue r2 (claude-einhander), per root msg_31e3312e.
Proves, on one CPU and with no GL, SDK, game, GPU or DLL, that the glue r2 sources compile and link in a pinned,
hermetic closure, and runs a wiring fixture:
  compile-gpu-base / compile-gpu-patched : v66-r3 gpu.c (3d8b5d3e) and glue r2 gpu.c (de9dfd77), each with its own
      scene_runtime.h, compiled as C with the EXACT native defines and optimisation flags of the v66-r3 build.json
      compile-gpu.c command (no warning flags, raw pgxp.h, as natively). Objects are hashed, never linked or run.
  compile-native-capture / compile-native-json : v66-r3 scene_capture.cpp / scene_json.cpp with the native C++
      flags (raw pgxp.h); linked into the fixture unchanged.
  compile-ledger / compile-runtime / compile-bridge / compile-harness : ledger r0, glue r2 scene_runtime.cpp and
      scene_t2_bridge.r2.cpp, and test_glue.r0.cpp under -std=c++17 -Wall -Wextra -Werror with the DERIVED pgxp.h.
  link, run-glue : fixture glue, revision r0, 28 authored checks (fakes for gpu.c / PGXP / GTE-ring entry points).
Every compile writes -MD -MF dependencies; a step passes only if every dependency resolves inside this run's
output folder or the pinned toolchain root (hermeticity: no header comes from the repository or an SDK).
Native include closure: the v66-r3 .obj.d files list exactly 23 include/*.h headers for gpu.c and scene_capture.h /
pgxp.h for the capture TUs; the native -I directories outside v66-r3 (runtime, recompiler, recomp-ui, VulkanSDK,
build-ss8c, deps) contribute no header and are omitted. v68 links these same v66-r3 objects (v68 build.json); the
"37c" parents are NOT compared here (paths not supplied).
Rules inherited from build_t2_fixture.r4.py (7b39f6a4), whose lines 77-271 (sha, now, BLOCKS, TEMPLATE,
lf_lines, native_block, divide_block, derive_pgxp, write_exact, run_child) are byte copies below (sed -n):
  - raw-byte pins first; a single in-memory read per input; every executed copy re-hashed after writing;
  - gte.cpp divide block cfa7686a (v61 == canonical); ledger native closure from the raw-pinned v66-r3 gpu.c /
    gpu_gl_renderer.c BLOCKS; pgxp.h DERIVED (comment-only, offset 3986, 50a6ef6d) for the strict TUs only.
Run ONLY under a grant naming the CPU, inside the required outer envelope (or a verified copy of it)
  remaster-audit/cpu-source-review-20261114/claude-support/run_rc2_envelope_r1.py
  sha256 fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36
  options: --cpu N --timeout 120 --max-job-mib 1024 --no-window
Children are CREATE_NO_WINDOW|BELOW_NORMAL with bounded waits; the envelope owns tree cleanup and the 120 s limit.
result.json is written in try/finally (best effort). The compilers are hashed then executed by path."""
import argparse, datetime, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
CAPTURE = HERE.parent
T2DIR = CAPTURE.parent / "t2"
T1DIR = CAPTURE.parent / "t1"
LEDGER = CAPTURE / "ledger-r0"
GLUE = CAPTURE / "ledger-glue-r2" / "patched"
R = Path("C:/github/Einhander")
EV = R / "remaster-audit/dev-center-evidence/stage1-completion-20261112"
V66 = EV / "sampling-build-v66-reviewed-scene-r3"
GPU_HEADERS = {  # v66-r3 include/*.h listed by gpu.c.obj.d (pgxp.h raw)
    "gpu.h": "2403a6bab465e2f2c5e2830d8cb8efcd61066dfc55092256f1e5a9068b3df405",
    "pgxp.h": "1f50599f51a53fdc989d1d0bb9c7aea46f0f6cc53b303048367c0f05b18c4c47",
    "mod_memory.h": "89174eb7cd7db7294d6f5e5a0b99a6b5e24a5a724c6d8adca56239de830db83f",
    "gpu_primitive_reject.h": "d8ad4e64e9cc536e18e47d488b46216c4d7bc44df0de0b821d2e72f7e53b02db",
    "gpu_sw_renderer.h": "7211fae8b6741507a9e4260ea1915b1e36d2a76cc0d477f991bca07ba7a08285",
    "gpu_vram_dirty.h": "9536a2e2cbf54eb4178cc8540412ad71b1c3919d40857c238893a9e8a22171d2",
    "gpu_render.h": "a4e686c8fa453b691a8e299ab991a10d076da97461ffb5cc27b4c85a2d2654cc",
    "text_xlate.h": "8f64dfc366cbefac0fb01ef585c31ef5ab9d96a2ae2ca8994f7a0ccaa3d25707",
    "crash_trace.h": "c37c6e1f50003e4454bf995ef678e7259a66844fb042e070c53b9738bf8b751f",
    "debug_server.h": "819212833c2903e010bc8a7f0c9403052bf96a84c7adcdc28cf80d4d2422f842",
    "cpu_state.h": "f73944953efa2effaa62ba672a7bd6cc618f4df2f5381624aaca62dc73ab2053",
    "psx_icache.h": "1fbfa842f69e16e9432f1ff4baf2a03fa284735daf3d8142f751c8d37d338f2a",
    "pgxp_hooks.h": "fa5ae62be37343236118d3229af4ade4ee3d36e8ca4917ae83a327926cdd678d",
    "psx_cyc.h": "a3efef40effc95eef8d1f6e88bcba1cb785dcea5ad0ff38e55d4d753ce4109f6",
    "psx_cycles.h": "0e4c3e30fd7f235ab6226c9bf7c9d515c817dc39f12aa706a1ec53f1165d92f7",
    "event_ring.h": "06cc69ded9a8c2c6ed7723d86633eaaf1336c5da9aee432724142fe4696f6d89",
    "color_lut.h": "4738db18cb4aa215ed03eaf44474ffd1dc397f73cb38e4ffd0666fabd3a00830",
    "mod_runtime.h": "b1e9f43a7d97a326df3b60b458256f5c2c8e58a520e89ab42da831b2cf49cc80",
    "sio.h": "e53de1c7ee0947f0785e60ed0e0bb90affff10b9d13311708a09a63acecbfc3e",
    "ws_cull_detect.h": "75172fae6957a89ac7cf70416b3e6715c7b0dc1726e99364f6ffb4707374e684",
    "ws_aspect_cone_math.h": "b40a362504331b5963ccc2e72cf8dfa3fb43990c7f61ba7a58961431f44b04aa",
    "ws_ui_group.h": "38190a000994c9b57995835023b37848e99fdf4458b8be1c71b875c1f1054833",
    "pst_wire.h": "3448f12dc6fc4d657d211adb25bf5f1ae0546e3a46d99a8749c736c80ba227ab",
}
INPUTS = {  # name -> (path, sha256)
    "gte_v61.cpp": (EV / "sampling-build-v61-view-metrics-r2/src/gte.cpp",
                    "139d2e49c6a77b68a1d96a4325f9c244db4f9ed1b2277187be068454304c1849"),
    "gte_canonical.cpp": (R / "windows-x64/psxrecomp/runtime/src/gte.cpp",
                          "0563d9a1da49c6c0538c1285f803939c1a9441b5485a16a4d6f7eff6f50656c0"),
    "gpu.c": (V66 / "src/gpu.c", "3d8b5d3e23c42a22fe1cecbe1287a286f2f4305147d67cb1039bdef96f628689"),
    "gpu_gl_renderer.c": (V66 / "src/gpu_gl_renderer.c",
                          "b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16"),
    "base_scene_runtime.h": (V66 / "src/scene_runtime.h",
                             "6ddedc789b76254f865217c9e4e0eec7bba498cc039397178c7cec4ea5d41544"),
    "scene_capture.h": (V66 / "src/scene_capture.h", "b90ebe9da7f11ed0c12ad2ea041564cb45a69a061b4da89b92e05dd9858856c8"),
    "scene_capture.cpp": (V66 / "src/scene_capture.cpp",
                          "78c4158d6428b57e5c1312b61637af4cfebd0c8a484860294ae13ce140c9eff8"),
    "scene_json.cpp": (V66 / "src/scene_json.cpp", "4305f17e8d0dfea833209400da4ddc819d8cc2aa3ed46b584d6f4a257889211f"),
    "glue_gpu.c": (GLUE / "gpu.c", "de9dfd7742d337d94811dca542043d18d8fb330352474d67bda64a2b3dd88335"),
    "glue_scene_runtime.cpp": (GLUE / "scene_runtime.cpp",
                               "3bbc68218ad9e7e2d5cbb925b2a5db9d68e8fb7581b6f70fd8105b0461baea00"),
    "glue_scene_runtime.h": (GLUE / "scene_runtime.h",
                             "730b5b4f76afe22ef14102aa4f62985a49f67c77cdf22940d9f3c9fe0c3fdd98"),
    "scene_t2_bridge.r2.cpp": (GLUE / "scene_t2_bridge.r2.cpp",
                               "a88b69112ff59468609ab0e316c01c7c0afa164b84dee0365177ebaa95d99736"),
    "scene_t2_bridge.r2.h": (GLUE / "scene_t2_bridge.r2.h",
                             "c6a59759e36449b5f8f44487070a09670605f37377fa35d8adc121ccc7bd7c64"),
    "scene_ledger.r0.h": (LEDGER / "scene_ledger.r0.h", "220d1a5e8426ffe20a7d9abb776f629dc08b51be76188ef29d37e6bb7455adbc"),
    "scene_ledger.r0.cpp": (LEDGER / "scene_ledger.r0.cpp",
                            "9614a6a81bd2175418a68551044601cba85c1621e6a91d2c3dcba2b4e88be62c"),
    "scene_ledger_t2.r0.h": (LEDGER / "scene_ledger_t2.r0.h",
                             "94bc9c245e3f2c003119fd57fdaf49de959d37799bbe870ba1c8528017dd39c8"),
    "remix_t1_reproject.r1.h": (T1DIR / "remix_t1_reproject.r1.h",
                                "4a0a536c3e2313a6e25be47fc877607c2d5006ac398828eb558218c0fe68d795"),
    "remix_t2.r3.h": (T2DIR / "remix_t2.r3.h", "8baba81cdbb402585f4f535d830cea822ca9b81f963fb64bc809f53ff019911b"),
    "remix_t2.r4.h": (T2DIR / "r4" / "remix_t2.r4.h", "eebb2c8fd26a2df58bd6748cfefe7a670e236029cd6dcffe279617abd8478a96"),
    "test_glue.r0.cpp": (HERE / "test_glue.r0.cpp", "7cce4f6b163ec606296b9e3cb03e45cae56ba3058c85d4414062e13abbde5f3c"),
}
INPUTS.update({"include/" + n: (V66 / "include" / n, s) for n, s in GPU_HEADERS.items()})
PGXP_DELTA_OFFSET = 3986
PGXP_DELTA_OLD = b"*x16/*y16"
PGXP_DELTA_NEW = b"*x16 and *y16"
PGXP_DERIVED_SHA = "50a6ef6d335c7b6cd678ed50c17f4a4c506ed868537439e6b01e2dacaaa88e52"
DIVIDE_BLOCK_SHA = "cfa7686a59c223f358d2507674af7289dc462213e0b676165b87b60974a896ef"
TOOLBIN = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")
CC = TOOLBIN / "clang++.exe"
C_CC = TOOLBIN / "clang.exe"
TOOLCHAIN = {
    "clang++.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang.exe": "a8b7a614eeadd9105f814be3701a7f312cda4cea51751b75b408c16100c94e85",
    "clang-22.exe": "870a1393b07b9debf407cfdad19f6d4680da32a213c33d0a6eb6ae7e8c8171a1",
    "libclang-cpp.dll": "df189bb471795cd9c65958374d75356578c383ecb198bab1c248f281dfab3d6e",
    "libLLVM-22.dll": "1e2aed1785cedbbb6f19338eac72257649bab60157e044d0435883871a2f58af",
}
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Werror"]
# Exact defines and optimisation flags of the v66-r3 build.json compile-gpu.c / compile-scene_capture.cpp commands.
NATIVE_DEFINES = [
    "-DDEFAULT_DEBUG_PORT=4370", "-DFMT_HEADER_ONLY=1", "-DLNG_SDL3=1", "-DNOMINMAX",
    '-DPSX_BUNDLED_BIOS_PATH="bios/openbios.bin"', '-DPSX_DEFAULT_BIOS_PATH="bios/SCPH1001.BIN"',
    '-DPSX_DEFAULT_GAME_CONFIG_PATH="game.toml"', "-DPSX_ENABLE_BLOCK_CYCLES=1", "-DPSX_HAS_CODEGEN_SETUP_HOST=1",
    "-DPSX_HAS_GAME_CODEGEN=1", "-DPSX_HAS_GAME_DISPATCH=1", "-DPSX_HAS_RBENGINE_SNAP=1", "-DPSX_HAS_SETUP_WIZARD=1",
    "-DPSX_HAVE_VULKAN=1", "-DPSX_MAX_PLAYERS=1", "-DPSX_NATIVE_BUILD=1", "-DPSX_SDL3=1",
    '-DPSX_WINDOW_TITLE="Einhander Recompiled"', "-DRECOMP_LAUNCHER", "-DRECOMP_UI_ENABLE_MODS=1",
    "-DRECOMP_UI_PSX_HAS_REWIND=1", "-DSDL_MAIN_HANDLED",
]
NATIVE_C = ["-O3", "-DNDEBUG", "-fzero-initialized-in-bss"]
NATIVE_CXX = ["-O3", "-DNDEBUG", "-std=gnu++17", "-fzero-initialized-in-bss"]
FIXTURES = {"glue": ("glue", 28)}
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
    name, checks = FIXTURES[key]
    try:
        line = json.loads((out / f"fixture-{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        rows[-1]["passed"] = False
        rows[-1]["fixture_error"] = repr(error)
        return False
    rows[-1]["fixture"] = line
    rows[-1]["passed"] = (line.get("fixture") == name and line.get("revision") == "r0" and line.get("failures") == 0
                          and line.get("checks") == checks and line.get("passed") is True
                          and line.get("gl_used") is False and line.get("sdk_used") is False)
    return rows[-1]["passed"]


def deps_ok(row, dep_file, roots):
    # Hermeticity: every dependency named in the -MF file must resolve inside one of the allowed roots.
    try:
        text = Path(dep_file).read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        row["deps_error"] = repr(error)
        return False
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    cut = text.find(": ")
    deps = text[cut + 2:].split() if cut >= 0 else []
    allowed = [os.path.normcase(os.path.realpath(r)) for r in roots]
    outside = []
    for d in deps:
        p = os.path.normcase(os.path.realpath(d))
        if not any(p == a or p.startswith(a + os.sep) for a in allowed):
            outside.append(d)
    row["deps_count"] = len(deps)
    row["deps_outside"] = outside
    return bool(deps) and not outside


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
        div61 = divide_block(data["gte_v61.cpp"])
        divcan = divide_block(data["gte_canonical.cpp"])
        derived_pgxp = derive_pgxp(data["include/pgxp.h"])
        ext["divide_block"] = dict(sha256=sha(div61), v61_equals_canonical=div61 == divcan)
        ext["pgxp_derivation"] = dict(original_sha256=sha(data["include/pgxp.h"]), derived_sha256=sha(derived_pgxp),
                                      offset=PGXP_DELTA_OFFSET, old=PGXP_DELTA_OLD.decode("ascii"),
                                      new=PGXP_DELTA_NEW.decode("ascii"))
        ext["passed"] = (all(b["passed"] for b in ext["blocks"].values()) and div61 == divcan
                         and sha(div61) == DIVIDE_BLOCK_SHA)
        if not ext["passed"]:
            return 1
        dirs = {d: out / d for d in ("gpu-include", "gpu-base", "gpu-patched", "native", "strict", "obj")}
        for d in dirs.values():
            d.mkdir()
        layout = {}
        for n in GPU_HEADERS:
            layout["gpu-include/" + n] = data["include/" + n]                       # raw, as natively
        layout.update({
            "gpu-base/gpu.c": data["gpu.c"], "gpu-base/scene_runtime.h": data["base_scene_runtime.h"],
            "gpu-base/scene_capture.h": data["scene_capture.h"],
            "gpu-patched/gpu.c": data["glue_gpu.c"], "gpu-patched/scene_runtime.h": data["glue_scene_runtime.h"],
            "gpu-patched/scene_capture.h": data["scene_capture.h"], "gpu-patched/scene_ledger.r0.h": data["scene_ledger.r0.h"],
            "native/scene_capture.cpp": data["scene_capture.cpp"], "native/scene_json.cpp": data["scene_json.cpp"],
            "native/scene_capture.h": data["scene_capture.h"], "native/pgxp.h": data["include/pgxp.h"],
            "strict/pgxp.h": derived_pgxp, "strict/scene_capture.h": data["scene_capture.h"],
            "strict/gte_divide_extracted.inc": div61, "strict/remix_t1_reproject.r1.h": data["remix_t1_reproject.r1.h"],
            "strict/remix_t2.r3.h": data["remix_t2.r3.h"], "strict/remix_t2.r4.h": data["remix_t2.r4.h"],
            "strict/scene_ledger.r0.h": data["scene_ledger.r0.h"], "strict/scene_ledger.r0.cpp": data["scene_ledger.r0.cpp"],
            "strict/scene_ledger_t2.r0.h": data["scene_ledger_t2.r0.h"], "strict/scene_ledger_native_unpack.inc": inc,
            "strict/scene_runtime.h": data["glue_scene_runtime.h"], "strict/scene_runtime.cpp": data["glue_scene_runtime.cpp"],
            "strict/scene_t2_bridge.r2.h": data["scene_t2_bridge.r2.h"],
            "strict/scene_t2_bridge.r2.cpp": data["scene_t2_bridge.r2.cpp"],
            "strict/executed-test-glue.cpp": data["test_glue.r0.cpp"],
        })
        result["executed_copies"] = {rel: write_exact(out / rel, blob) for rel, blob in layout.items()}
        real_dir = Path(os.path.realpath(CC)).parent
        tools = {n: dict(path=str(real_dir / n), sha256=sha((real_dir / n).read_bytes())) for n in TOOLCHAIN}
        result["toolchain"] = dict(invoked=[str(CC), str(C_CC)], invoked_sha256=[sha(CC.read_bytes()), sha(C_CC.read_bytes())],
                                   files=tools)
        if result["toolchain"]["invoked_sha256"] != [TOOLCHAIN["clang++.exe"], TOOLCHAIN["clang.exe"]] or \
                any(tools[n]["sha256"] != s for n, s in TOOLCHAIN.items()):
            raise ValueError("compiler pin mismatch")
        roots = [out, TOOLBIN.parent, real_dir.parent]
        result["hermetic_roots"] = [str(r) for r in roots]
        o = dirs["obj"]
        gpu_c = [C_CC, *NATIVE_DEFINES, *NATIVE_C, "-I", dirs["gpu-include"]]
        native_cxx = [CC, *NATIVE_DEFINES, *NATIVE_CXX, "-I", dirs["native"]]
        strict = [CC, *FLAGS, "-I", dirs["strict"]]
        compiles = [
            ("compile-gpu-base", gpu_c, dirs["gpu-base"] / "gpu.c", o / "gpu-base.o"),
            ("compile-gpu-patched", gpu_c, dirs["gpu-patched"] / "gpu.c", o / "gpu-patched.o"),
            ("compile-native-capture", native_cxx, dirs["native"] / "scene_capture.cpp", o / "scene_capture.o"),
            ("compile-native-json", native_cxx, dirs["native"] / "scene_json.cpp", o / "scene_json.o"),
            ("compile-ledger", strict, dirs["strict"] / "scene_ledger.r0.cpp", o / "scene_ledger.o"),
            ("compile-runtime", strict, dirs["strict"] / "scene_runtime.cpp", o / "scene_runtime.o"),
            ("compile-bridge", strict, dirs["strict"] / "scene_t2_bridge.r2.cpp", o / "scene_t2_bridge.o"),
            ("compile-harness", strict, dirs["strict"] / "executed-test-glue.cpp", o / "test_glue.o"),
        ]
        result["object_sha256"] = {}
        for label, base, src, obj in compiles:
            if not run_child(label, [*base, "-MD", "-MF", f"{obj}.d", "-c", src, "-o", obj], out, 0, 45, out, rows):
                return 1
            row = rows[-1]
            row["object_sha256"] = result["object_sha256"][label] = sha(obj.read_bytes())
            row["passed"] = deps_ok(row, f"{obj}.d", roots)
            if not row["passed"]:
                return 1
        exe = out / "test-glue-r0.exe"
        objs = [o / n for n in ("scene_capture.o", "scene_json.o", "scene_ledger.o", "scene_runtime.o",
                                "scene_t2_bridge.o", "test_glue.o")]
        if not run_child("link", [CC, *objs, "-o", exe], out, 0, 45, out, rows):
            return 1
        result["exe_sha256"] = {"glue": sha(exe.read_bytes())}
        os.environ["PSXRECOMP_SCENE_CAPTURE"] = "1"     # the runtime's capture switch, inherited by run-glue only
        result["run_env"] = {"PSXRECOMP_SCENE_CAPTURE": "1"}
        if not run_child("run-glue", [exe, out / "fixture-glue.json"], out, 0, 10, out, rows):
            return 1
        if not fixture_ok(rows, out, "glue"):
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
