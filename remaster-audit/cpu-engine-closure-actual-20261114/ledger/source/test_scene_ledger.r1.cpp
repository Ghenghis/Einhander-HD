// CPU fixture for scene_ledger r1 scene_ledger_display_hazard (claude-einhander). SOURCE ONLY until a grant naming
// the CPU runs it through build_scene_ledger_fixture.r1.py inside the required envelope. Synthetic GP0 words only;
// no GL, SDK, game. Every CHECK executes exactly once (no CHECK inside a loop or helper). Lines 12-73 below are a
// verbatim copy of test_scene_ledger.r0.cpp (c1d389f1) lines 12-73 (helpers), checked with diff.
// Groups: Z arguments/lifecycle, H hazard verdicts, W wrap, P policy consistency, X incomplete ledgers.
#include "scene_ledger.r1.h"
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <thread>

static int g_checks, g_failures;
#define CHECK(c) do { ++g_checks; if (!(c)) { ++g_failures; std::printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

static const uint32_t T = 7;              // owner token
static uint32_t frame_no = 100, gen_no = 0;

static uint32_t V(int x, int y) { return ((uint32_t(y) & 0x7FFu) << 16) | (uint32_t(x) & 0x7FFu); }
static uint32_t XY(int x, int y) { return (uint32_t(y) << 16) | uint32_t(x); }   // transfer coord/size word
static SceneLedgerState state(int l, int t, int r, int b, int ox, int oy) {
    SceneLedgerState s;
    std::memset(&s, 0, sizeof s);
    s.draw_left = uint16_t(l); s.draw_top = uint16_t(t); s.draw_right = uint16_t(r); s.draw_bottom = uint16_t(b);
    s.draw_offset_x = ox; s.draw_offset_y = oy;
    s.texpage = 0x0008;
    s.native_screen_mapping = 1;
    s.display_known = 1; s.display_x = 0; s.display_y = 0; s.display_w = 320; s.display_h = 240;
    return s;
}
static bool R(const LedgerRect &r, int x0, int y0, int x1, int y1) {
    return r.x0 == x0 && r.y0 == y0 && r.x1 == x1 && r.y1 == y1;
}
// Arm generation ++gen_no at frame_no, enter RECORDING at frame_no + 1.
static bool begin(int gp0_open = 0) {
    scene_ledger_cancel(T);
    frame_no += 10;
    ++gen_no;
    return scene_ledger_arm(T, frame_no, gen_no, gp0_open) == LEDGER_OK && scene_ledger_tick(T, frame_no + 1) == LEDGER_OK;
}
static int cmd_t(uint32_t token, std::initializer_list<uint32_t> words, const SceneLedgerState *s) {
    uint32_t w[16];
    int n = 0;
    for (uint32_t x : words) w[n++] = x;
    return scene_ledger_command(token, frame_no + 1, w, n, s);
}
static int cmd(std::initializer_list<uint32_t> words, const SceneLedgerState *s) { return cmd_t(T, words, s); }
static void seal() { scene_ledger_tick(T, frame_no + 2); }
static SceneLedgerHeader H() {
    SceneLedgerHeader h;
    std::memset(&h, 0, sizeof h);
    scene_ledger_header(T, &h);
    return h;
}
static SceneLedgerEntry E(uint32_t i) {
    SceneLedgerEntry e;
    scene_ledger_get(T, i, gen_no, &e);
    return e;
}
static uint32_t policy(std::initializer_list<uint32_t> refs, uint32_t *entry = nullptr) {
    uint32_t t[8];
    uint32_t n = 0;
    for (uint32_t x : refs) t[n++] = x;
    SceneLedgerVerdict v{99, 0, 0};
    if (scene_ledger_policy(T, gen_no, t, n, &v) != LEDGER_OK) return 98;
    if (entry) *entry = v.entry;
    return v.verdict;
}
// Transported polygon of the policy tests: textured tri, 4 bpp page at (512,0), CLUT at (32,500), tpage word
// 0x0008, three vertices at (10,10),(50,10),(10,50) plus the draw offset.
static const uint32_t kClut = (500u << 6) | 2u;
static int poly(const SceneLedgerState &s, uint32_t tpage = 0x0008, int x = 10, int y = 10) {
    return cmd({0x24808080u, V(x, y), (kClut << 16) | 0x0000u, V(x + 40, y), (tpage << 16) | 0x0010u, V(x, y + 40), 0x1000u}, &s);
}

// r1 helper: display-hazard verdict of `refs` against target (x, y, w, h); 98 when the call itself fails.
static uint32_t hazard(std::initializer_list<uint32_t> refs, int x, int y, int w, int h, uint32_t *entry = nullptr,
                       uint32_t *ref = nullptr) {
    uint32_t t[8];
    uint32_t n = 0;
    for (uint32_t v : refs) t[n++] = v;
    const int32_t rect[4] = {x, y, w, h};
    SceneLedgerVerdict v{99, 0, 0};
    if (scene_ledger_display_hazard(T, gen_no, t, n, rect, &v) != LEDGER_OK) return 98;
    if (entry) *entry = v.entry;
    if (ref) *ref = v.ref;
    return v.verdict;
}

int main(int argc, char **argv) {
    // ---- Z: arguments and lifecycle ----
    {
        const int32_t rect[4] = {0, 256, 320, 240};
        SceneLedgerVerdict v{99, 0, 0};
        CHECK(scene_ledger_display_hazard(T, 1, nullptr, 0, rect, &v) == LEDGER_BAD_STATE);   // owner unbound
    }
    CHECK(scene_ledger_init(T, 1) == LEDGER_OK);
    // Interval: display A = (0,0,320,240) on every command; the frame draws into B (drawing area y 256..495).
    const SceneLedgerState sb = state(0, 256, 319, 495, 0, 0);
    CHECK(XY(16, 8) == 0x00080010u);                              // helper sanity (transfer word layout)
    CHECK(begin() && poly(sb, 0x0008, 10, 266) == LEDGER_OK);    // textured_index 0: page (512,0) 4 bpp, CLUT (32,500)
    {
        const int32_t rect[4] = {0, 256, 320, 240};
        SceneLedgerVerdict v{99, 0, 0};
        CHECK(scene_ledger_display_hazard(T, gen_no, nullptr, 0, rect, &v) == LEDGER_OK && v.verdict == LP_NATIVE_INCOMPLETE);
    }
    seal();
    CHECK(H().sealed == 1 && H().complete == 1 && H().display_count == 1 && R(H().display[0], 0, 0, 320, 240));
    CHECK((E(0).flags & LF_CAPTURED_TEXTURED) && E(0).textured_index == 0);
    {
        const int32_t rect[4] = {0, 256, 320, 240};
        const int32_t zero_w[4] = {0, 256, 0, 240};
        const uint32_t one = 0;
        SceneLedgerVerdict v{99, 0, 0};
        CHECK(scene_ledger_display_hazard(T, gen_no, &one, 1, nullptr, &v) == LEDGER_BAD_ARGUMENT);
        CHECK(scene_ledger_display_hazard(T, gen_no, &one, 1, rect, nullptr) == LEDGER_BAD_ARGUMENT);
        CHECK(scene_ledger_display_hazard(T, gen_no, nullptr, 1, rect, &v) == LEDGER_BAD_ARGUMENT);
        CHECK(scene_ledger_display_hazard(T, gen_no, &one, 1, zero_w, &v) == LEDGER_BAD_ARGUMENT);
        CHECK(scene_ledger_display_hazard(T + 1, gen_no, &one, 1, rect, &v) == LEDGER_WRONG_THREAD);
        CHECK(scene_ledger_display_hazard(T, gen_no + 1, &one, 1, rect, &v) == LEDGER_OK &&
              v.verdict == LP_NATIVE_INCOMPLETE && v.entry == 0xFFFFFFFFu && v.ref == 0xFFFFFFFFu);
    }

    // ---- H: verdicts for the sealed interval ----
    CHECK(hazard({0}, 0, 256, 320, 240) == LP_TRANSPORT_OK);       // hidden buffer B, page/CLUT elsewhere
    CHECK(hazard({}, 0, 256, 320, 240) == LP_TRANSPORT_OK);
    {
        uint32_t e = 7, r = 7;
        CHECK(hazard({0}, 0, 200, 320, 240, &e, &r) == LP_NATIVE_DISPLAY && e == 0xFFFFFFFFu && r == 0xFFFFFFFFu);
    }
    CHECK(hazard({}, 0, 0, 320, 240) == LP_NATIVE_DISPLAY);        // the target is the displayed buffer A
    {
        uint32_t e = 7, r = 7;
        CHECK(hazard({0}, 500, 0, 320, 240, &e, &r) == LP_NATIVE_DISPLAY && e == 0 && r == 0);   // page (512..576)
    }
    {
        uint32_t e = 7, r = 7;
        CHECK(hazard({0}, 0, 272, 320, 240, &e, &r) == LP_NATIVE_DISPLAY && e == 0 && r == 0);   // CLUT row 500
    }
    CHECK(hazard({5}, 0, 256, 320, 240) == LP_NATIVE_BAD_REF);
    CHECK(hazard({0, 0}, 0, 256, 320, 240) == LP_NATIVE_BAD_REF);

    // ---- W: wrap-split targets ----
    CHECK(hazard({0}, 1000, 256, 64, 240) == LP_TRANSPORT_OK);     // pieces (1000..1024) and (0..40) at y 256..496
    CHECK(hazard({0}, 1000, 0, 64, 240) == LP_NATIVE_DISPLAY);     // the wrapped piece (0..40, 0..240) is A
    CHECK(hazard({0}, 0, 400, 320, 240) == LP_NATIVE_DISPLAY);     // y 400..640 wraps to 0..128: A

    // ---- P: consistency with the r0 policy of the same interval ----
    CHECK(policy({0}) == LP_TRANSPORT_OK);

    // ---- X: 15 bpp page (no CLUT), then incomplete ledgers ----
    CHECK(begin() && poly(sb, 0x0108, 10, 266) == LEDGER_OK);    // depth 2: page (512..768, 0..256), no CLUT
    seal();
    CHECK(hazard({0}, 700, 0, 64, 240) == LP_NATIVE_DISPLAY && hazard({0}, 0, 272, 320, 240) == LP_TRANSPORT_OK);
    scene_ledger_note_external_vram_write();
    CHECK(hazard({0}, 0, 256, 320, 240) == LP_NATIVE_INCOMPLETE);  // an external write since arm
    {
        SceneLedgerState su = sb;
        su.display_known = 0;
        CHECK(begin() && poly(su, 0x0008, 10, 266) == LEDGER_OK);
        seal();
        CHECK(hazard({0}, 0, 256, 320, 240) == LP_NATIVE_INCOMPLETE);   // display area unknown
    }
    {
        int foreign_rc = -1;
        CHECK(begin() && poly(sb, 0x0008, 10, 266) == LEDGER_OK);
        std::thread th([&foreign_rc] { foreign_rc = cmd_t(T + 1, {0xE1000008u}, nullptr); });
        th.join();
        seal();
        CHECK(foreign_rc == LEDGER_WRONG_THREAD && hazard({0}, 0, 256, 320, 240) == LP_NATIVE_INCOMPLETE);
    }

    const bool passed = g_failures == 0;
    std::printf("{\"fixture\":\"scene_ledger\",\"revision\":\"r1\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
                g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = std::fopen(argv[1], "wb");
        if (!f) return 3;
        std::fprintf(f, "{\"fixture\":\"scene_ledger\",\"revision\":\"r1\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                        "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (std::fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
