// CPU fixture for scene_ledger r3 footprint + draw-area queries (claude-einhander). SOURCE ONLY until a grant naming
// the CPU runs it through build_scene_ledger_fixture.r3.py. Synthetic GP0 words only; no GL, SDK, game. Every CHECK
// executes exactly once (no CHECK inside a loop or helper; the equality corpus is aggregated, then checked once).
// Lines 12-73 below are a verbatim copy of test_scene_ledger.r0.cpp (c1d389f1) lines 12-73 (helpers).
// Groups: P pure (before init), Q equality corpus vs recorded entries, U unknown footprints, S no side effects,
// D draw-area constancy, Z arguments.
#include "scene_ledger.r3.h"
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

// r2 helpers (no CHECK inside).
struct Cmd { uint32_t w[8]; int n; const SceneLedgerState *s; };
struct Fp { LedgerRect dst[SCENE_LEDGER_MAX_PIECES]; uint32_t count, known; int rc; };
static Fp fp(const uint32_t *w, int n, const SceneLedgerState *s) {
    Fp f;
    std::memset(&f, 0, sizeof f);
    f.count = 99;
    f.known = 99;
    f.rc = scene_ledger_footprint(w, n, s, f.dst, &f.count, &f.known);
    return f;
}
static uint32_t area_query(uint32_t token, uint32_t gen, uint16_t a[4]) {
    uint32_t c = 99;
    if (scene_ledger_draw_area(token, gen, &c, a) != LEDGER_OK) return 98;
    return c;
}

int main(int argc, char **argv) {
    const SceneLedgerState s0 = state(0, 0, 1023, 511, 0, 0);
    const SceneLedgerState sb = state(0, 256, 319, 495, 0, 256);
    SceneLedgerState su = s0;
    su.native_screen_mapping = 0;

    // ---- P: pure, before the ledger is even initialised ----
    {
        const uint32_t fill[3] = {0x02000000u, XY(256, 16), XY(32, 8)};
        const Fp f = fp(fill, 3, &s0);
        CHECK(f.rc == LEDGER_OK && f.known == 1 && f.count == 1 && R(f.dst[0], 256, 16, 288, 24));
    }
    {
        uint16_t a[4] = {7, 7, 7, 7};
        uint32_t c = 7;
        CHECK(scene_ledger_draw_area(T, 1, &c, a) == LEDGER_BAD_STATE);   // owner unbound
    }
    CHECK(scene_ledger_init(T, 1) == LEDGER_OK);

    // ---- Q: equality corpus, one complete interval (two states, every known class) ----
    const Cmd corpus[] = {
        {{0xE1000008u}, 1, &s0},
        {{0x24808080u, V(10, 10), (kClut << 16) | 0x0000u, V(50, 10), (0x0008u << 16) | 0x0010u, V(10, 50), 0x1000u}, 7, &s0},
        {{0x02000000u, XY(256, 16), XY(32, 8)}, 3, &s0},
        {{0x20000000u, V(0, 0), V(5, 0), V(0, 5)}, 4, &s0},
        {{0xE3000000u}, 1, &s0},
        {{0x64808080u, V(100, 100), kClut << 16, XY(16, 16)}, 4, &s0},
        {{0x80000000u, XY(600, 300), XY(700, 300), XY(10, 10)}, 4, &s0},
        {{0xA0000000u, XY(800, 400), XY(8, 4)}, 3, &s0},
        {{0xC0000000u, XY(900, 100), XY(4, 4)}, 3, &s0},
        {{0x00000000u}, 1, &s0},
        {{0x40000000u, V(0, 0), V(3, 4)}, 3, &s0},
        {{0x60000000u, V(0, 10), XY(0x400, 2)}, 3, &s0},
        {{0x68000000u, V(5, 30)}, 2, &s0},
        {{0x70000000u, V(5, 40)}, 2, &s0},
        {{0x7C000000u, V(5, 60), kClut << 16}, 3, &s0},
        {{0x02000000u, XY(1008, 496), XY(32, 32)}, 3, &s0},          // fill wrapping both edges: 4 pieces
        {{0x60000000u, V(0, 0), XY(0, 0)}, 3, &s0},                   // zero-size rect: no footprint
        {{0x24808080u, V(10, 10), (kClut << 16) | 0x0000u, V(50, 10), (0x0008u << 16) | 0x0010u, V(10, 50), 0x1000u}, 7, &sb},
    };
    const uint32_t nq = uint32_t(sizeof corpus / sizeof corpus[0]);
    CHECK(begin());
    for (uint32_t i = 0; i < nq; ++i) scene_ledger_command(T, frame_no + 1, corpus[i].w, corpus[i].n, corpus[i].s);
    seal();
    const SceneLedgerHeader hq = H();
    CHECK(hq.complete == 1 && hq.entry_count == nq);
    CHECK(policy({0}) == LP_NATIVE_FB_MUTATION);                     // r0 policy unchanged: the fill hits display A
    uint32_t compared = 0, mismatches = 0;
    for (uint32_t i = 0; i < nq; ++i) {
        const SceneLedgerEntry e = E(i);
        const Fp f = fp(corpus[i].w, corpus[i].n, corpus[i].s);
        bool same = f.rc == LEDGER_OK && f.known == uint32_t((e.flags & LF_UNKNOWN_FOOTPRINT) ? 0 : 1) &&
                    f.count == e.dst_count;
        for (uint32_t k = 0; same && k < f.count; ++k) same = std::memcmp(&f.dst[k], &e.dst[k], sizeof(LedgerRect)) == 0;
        ++compared;
        if (!same) ++mismatches;
    }
    CHECK(compared == nq && mismatches == 0);
    {
        const Fp f = fp(corpus[15].w, corpus[15].n, corpus[15].s);
        CHECK(f.known == 1 && f.count == 4 && R(f.dst[0], 1008, 496, 1024, 512) && R(f.dst[1], 0, 496, 16, 512) &&
              R(f.dst[2], 1008, 0, 1024, 16) && R(f.dst[3], 0, 0, 16, 16));
    }
    {
        const Fp f = fp(corpus[17].w, corpus[17].n, corpus[17].s);   // offset (0,256), clamped to y 256..495
        CHECK(f.known == 1 && f.count == 1 && R(f.dst[0], 10, 266, 51, 307));
    }
    {
        const Fp st = fp(corpus[0].w, corpus[0].n, corpus[0].s), rd = fp(corpus[8].w, corpus[8].n, corpus[8].s),
                 zr = fp(corpus[16].w, corpus[16].n, corpus[16].s);
        CHECK(st.known == 1 && st.count == 0 && rd.known == 1 && rd.count == 0 && zr.known == 1 && zr.count == 0);
    }
    {
        const Fp cp = fp(corpus[6].w, corpus[6].n, corpus[6].s), wr = fp(corpus[7].w, corpus[7].n, corpus[7].s);
        CHECK(cp.known == 1 && cp.count == 1 && R(cp.dst[0], 700, 300, 710, 310) && wr.known == 1 && wr.count == 1 &&
              R(wr.dst[0], 800, 400, 808, 404));
    }

    // ---- U: unknown footprints (no ledger needed) ----
    {
        const uint32_t polyline[1] = {0x48000000u}, irq[1] = {0x1F000000u}, short_fill[2] = {0x02000000u, XY(0, 0)};
        const uint32_t tri[4] = {0x20000000u, V(0, 0), V(5, 0), V(0, 5)};
        const Fp a = fp(polyline, 1, &s0), b = fp(irq, 1, &s0), c = fp(short_fill, 2, &s0), d = fp(tri, 4, &su),
                 e = fp(tri, 4, nullptr), g = fp(nullptr, 0, &s0);
        CHECK(a.known == 0 && a.count == 0 && b.known == 0 && c.known == 0 && d.known == 0 && d.count == 0 &&
              e.known == 0 && g.known == 0 && a.rc == LEDGER_OK && g.rc == LEDGER_OK);
    }
    {   // r3: identity mapping is exactly 1; any other nonzero value is unknown for draws (r2 accepted 2)
        SceneLedgerState s2 = s0;
        s2.native_screen_mapping = 2;
        const uint32_t tri[4] = {0x20000000u, V(0, 0), V(5, 0), V(0, 5)};
        const uint32_t fill[3] = {0x02000000u, XY(0, 0), XY(16, 16)};
        const Fp d2 = fp(tri, 4, &s2), f2 = fp(fill, 3, &s2);
        CHECK(d2.known == 0 && d2.count == 0 && f2.known == 1 && f2.count == 1);   // fills are not draws
    }

    // ---- S: no ledger side effects, in RECORDING and in ARMED ----
    {
        CHECK(begin());
        const uint32_t tri[4] = {0x20000000u, V(0, 0), V(5, 0), V(0, 5)};
        const SceneLedgerHeader before = H();
        const Fp f = fp(tri, 4, &su);                                 // an unmapped draw, answered unknown
        const SceneLedgerHeader after = H();
        CHECK(f.known == 0 && after.incomplete_mask == before.incomplete_mask &&
              after.mapping_unknown == before.mapping_unknown && after.command_count == before.command_count);
        seal();
        scene_ledger_cancel(T);
        scene_ledger_arm(T, frame_no + 5, ++gen_no, 0);               // ARMED: nothing is recorded ...
        const uint32_t fill[3] = {0x02000000u, XY(0, 256), XY(320, 240)};
        const Fp g = fp(fill, 3, &s0);                                // ... but the footprint is still answered
        CHECK(g.known == 1 && g.count == 1 && R(g.dst[0], 0, 256, 320, 496) && H().mode == LEDGER_ARMED &&
              H().command_count == 0);
    }

    // ---- D: drawing-area constancy ----
    {
        uint16_t a[4] = {9, 9, 9, 9};
        CHECK(begin() && poly(s0) == LEDGER_OK && cmd({0xE1000008u}, &s0) == LEDGER_OK);
        const uint32_t before_seal = area_query(T, gen_no, a);
        seal();
        const uint32_t sealed_c = area_query(T, gen_no, a);
        CHECK(before_seal == 0 && sealed_c == 1 && a[0] == 0 && a[1] == 0 && a[2] == 1023 && a[3] == 511);
        uint16_t b[4] = {9, 9, 9, 9};
        CHECK(area_query(T, gen_no + 1, b) == 0 && b[0] == 0 && b[2] == 0);   // another generation, zeroed
        uint16_t c[4];
        CHECK(begin() && poly(s0) == LEDGER_OK && poly(sb) == LEDGER_OK);
        seal();
        CHECK(area_query(T, gen_no, c) == 0);                           // varied
        uint16_t d[4];
        CHECK(begin());
        seal();
        CHECK(area_query(T, gen_no, d) == 0);                           // empty interval: no observed state
        uint16_t e[4];
        CHECK(begin() && poly(sb) == LEDGER_OK);                         // a new arm resets the bookkeeping
        seal();
        CHECK(area_query(T, gen_no, e) == 1 && e[0] == 0 && e[1] == 256 && e[2] == 319 && e[3] == 495);
        scene_ledger_note_external_vram_write();
        uint16_t f[4];
        CHECK(area_query(T, gen_no, f) == 0);                           // no longer complete
    }

    // ---- Z: arguments ----
    {
        uint16_t a[4];
        uint32_t c = 0;
        LedgerRect r[SCENE_LEDGER_MAX_PIECES];
        uint32_t n = 0, k = 0;
        const uint32_t nop[1] = {0};
        CHECK(scene_ledger_draw_area(T, gen_no, nullptr, a) == LEDGER_BAD_ARGUMENT &&
              scene_ledger_draw_area(T, gen_no, &c, nullptr) == LEDGER_BAD_ARGUMENT &&
              scene_ledger_draw_area(T + 1, gen_no, &c, a) == LEDGER_WRONG_THREAD);
        CHECK(scene_ledger_footprint(nop, 1, &s0, nullptr, &n, &k) == LEDGER_BAD_ARGUMENT &&
              scene_ledger_footprint(nop, 1, &s0, r, nullptr, &k) == LEDGER_BAD_ARGUMENT &&
              scene_ledger_footprint(nop, 1, &s0, r, &n, nullptr) == LEDGER_BAD_ARGUMENT);
        int foreign_known = -1;
        std::thread th([&foreign_known, &s0] {                         // any thread, no token
            const uint32_t fill[3] = {0x02000000u, XY(16, 16), XY(16, 16)};
            const Fp f = fp(fill, 3, &s0);
            foreign_known = int(f.known);
        });
        th.join();
        CHECK(foreign_known == 1 && H().foreign_calls == 0);
    }

    const bool passed = g_failures == 0;
    std::printf("{\"fixture\":\"scene_ledger\",\"revision\":\"r3\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
                g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *fo = std::fopen(argv[1], "wb");
        if (!fo) return 3;
        std::fprintf(fo, "{\"fixture\":\"scene_ledger\",\"revision\":\"r3\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                         "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (std::fclose(fo) != 0) return 3;
    }
    return passed ? 0 : 1;
}
