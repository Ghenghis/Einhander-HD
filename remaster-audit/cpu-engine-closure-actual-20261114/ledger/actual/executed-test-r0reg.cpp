// CPU fixture for scene_ledger r0 (claude-einhander). SOURCE ONLY until a grant naming the CPU runs it through
// build_scene_ledger_fixture.r0.py inside the required envelope. Synthetic GP0 words only; no GL, SDK, game.
// Every CHECK executes exactly once (no CHECK inside a loop or helper), so the static count is the run count.
// Groups: I lifecycle, A order/class, B bbox, M mapping, C transfers, D polyline/unsupported/malformed,
// O overflow, E policy, F threads/external/open-body/display/frames.
#include "scene_ledger.r0.h"
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

int main(int argc, char **argv) {
    // ---- I: lifecycle ----
    { SceneLedgerHeader h; CHECK(scene_ledger_header(T, &h) == LEDGER_BAD_STATE); }   // owner unbound
    CHECK(scene_ledger_init(0, 1) == LEDGER_BAD_ARGUMENT);
    CHECK(scene_ledger_init(T, 2) == LEDGER_BAD_ARGUMENT);
    CHECK(scene_ledger_init(T, 1) == LEDGER_OK);
    CHECK(scene_ledger_init(T, 1) == LEDGER_BAD_STATE);
    CHECK(scene_ledger_init(T + 1, 1) == LEDGER_WRONG_THREAD);
    CHECK(scene_ledger_arm(T, 50, 0, 0) == LEDGER_BAD_ARGUMENT);
    CHECK(scene_ledger_arm(T, 50, 1, 2) == LEDGER_BAD_ARGUMENT);

    // ---- A: interleaved order and classes (generation 1) ----
    const SceneLedgerState s0 = state(0, 0, 1023, 511, 0, 0);
    {
        frame_no = 100; gen_no = 1;
        scene_ledger_arm(T, 100, 1, 0);
        const uint32_t armed_fill[3] = {0x02000000u, XY(0, 0), XY(16, 16)};
        scene_ledger_command(T, 100, armed_fill, 3, &s0);        // ARMED frame 100: outside the interval
        scene_ledger_tick(T, 101);
        cmd({0xE1000008u}, &s0);                                 // 0
        poly(s0);                                                // 1  textured_index 0
        cmd({0x02000000u, XY(256, 16), XY(32, 8)}, &s0);         // 2
        cmd({0x20000000u, V(0, 0), V(5, 0), V(0, 5)}, &s0);      // 3
        cmd({0xE3000000u}, &s0);                                 // 4
        cmd({0x64808080u, V(100, 100), kClut << 16, XY(16, 16)}, &s0);   // 5 textured rect, state texpage
        cmd({0x80000000u, XY(600, 300), XY(700, 300), XY(10, 10)}, &s0); // 6
        cmd({0xA0000000u, XY(800, 400), XY(8, 4)}, &s0);         // 7
        cmd({0xC0000000u, XY(900, 100), XY(4, 4)}, &s0);         // 8
        cmd({0x00000000u}, &s0);                                 // 9
        cmd({0x40000000u, V(0, 0), V(3, 4)}, &s0);               // 10
        poly(s0);                                                // 11 textured_index 1
        scene_ledger_tick(T, 102);
        const SceneLedgerHeader h = H();
        CHECK(h.sealed == 1 && h.complete == 1 && h.incomplete_mask == 0 && h.mode == LEDGER_SEALED);
        CHECK(h.command_count == 12 && h.entry_count == 12);
        CHECK(h.frame == 101 && h.generation == 1 && h.owner_token == T);
        CHECK(h.textured_seen == 2 && h.display_count == 1 && R(h.display[0], 0, 0, 320, 240));
        CHECK(E(0).op == 0xE1);                                  // the ARMED fill is outside the interval
        CHECK(E(0).cls == LC_STATE && E(1).cls == LC_POLYGON && E(2).cls == LC_FILL && E(3).cls == LC_POLYGON &&
              E(4).cls == LC_STATE && E(5).cls == LC_RECT && E(6).cls == LC_COPY && E(7).cls == LC_WRITE &&
              E(8).cls == LC_READ && E(9).cls == LC_NOP && E(10).cls == LC_LINE && E(11).cls == LC_POLYGON);
        CHECK(E(0).global_index == 0 && E(5).global_index == 5 && E(11).global_index == 11);
        CHECK(E(1).textured_index == 0 && E(11).textured_index == 1 && E(3).textured_index == 0xFFFFFFFFu &&
              E(5).textured_index == 0xFFFFFFFFu);
        CHECK((E(1).flags & (LF_TEXTURED_POLY | LF_CAPTURED_TEXTURED | LF_TEXTURED | LF_DRAW)) ==
              (LF_TEXTURED_POLY | LF_CAPTURED_TEXTURED | LF_TEXTURED | LF_DRAW));
        CHECK((E(5).flags & LF_TEXTURED) && (E(5).flags & LF_DRAW) && !(E(5).flags & LF_TEXTURED_POLY));
        CHECK(E(1).tpage == 0x0008 && E(1).clut == kClut && E(5).tpage == 0x0008 && E(5).clut == kClut);
        CHECK(E(0).state_hash != 0 && E(0).state_hash == E(1).state_hash && h.final_state_hash == E(11).state_hash);
        CHECK((E(9).flags & LF_EMPTY) && (E(0).flags & LF_EMPTY) && E(9).dst_count == 0);
        SceneLedgerEntry z;
        std::memset(&z, 0xAB, sizeof z);
        const int rc = scene_ledger_get(T, 0, 2, &z);
        CHECK(rc == LEDGER_BAD_STATE && z.op == 0 && z.global_index == 0 && z.flags == 0);
        CHECK(scene_ledger_get(T, 12, 1, &z) == LEDGER_BAD_STATE);
        SceneLedgerHeader h2;
        CHECK(scene_ledger_header(T + 1, &h2) == LEDGER_WRONG_THREAD);
        CHECK(H().complete == 1);                                // a foreign READ does not invalidate
    }

    // ---- B: bounding boxes ----
    {
        begin();
        const SceneLedgerState off = state(0, 0, 1023, 511, 1023, 0);   // maximum native offset
        const SceneLedgerState clamp = state(100, 50, 200, 60, 0, 0);
        const SceneLedgerState wide = state(0, 0, 1023, 511, 600, 0);
        const SceneLedgerState inverted = state(300, 0, 200, 511, 0, 0);
        cmd({0x20000000u, V(-1024, 0), V(-1000, 0), V(-1024, 10)}, &off);   // 0: 0x400 = -1024 (+1023 = -1)
        cmd({0x20000000u, V(1023, 0), V(1023, 2), V(1021, 0)}, &s0);       // 1: 0x3FF = 1023
        cmd({0x20000000u, V(0, 0), V(10, 0), V(0, 5)}, &s0);               // 2: half-open
        cmd({0x20000000u, V(90, 40), V(250, 40), V(90, 70)}, &clamp);      // 3: drawing-area clamp
        cmd({0x02000000u, XY(0, 0), XY(16, 4)}, &clamp);                   // 4: fill ignores the area
        cmd({0x20000000u, V(-512, 0), V(512, 0), V(0, 1)}, &wide);         // 5: dx = 1024 oversize
        cmd({0x60000000u, V(0, 10), XY(0x400, 2)}, &s0);                   // 6: native mono rect w 1024 -> 1023
        cmd({0x64000000u, V(0, 20), kClut << 16, XY(0x400, 2)}, &s0);      // 7: native textured rect w & 0x3FF = 0
        cmd({0x68000000u, V(5, 30)}, &s0);                                 // 8: 1x1
        cmd({0x70000000u, V(5, 40)}, &s0);                                 // 9: 8x8
        cmd({0x7C000000u, V(5, 60), kClut << 16}, &s0);                    // 10: 16x16 textured
        cmd({0x50000000u, V(1, 1), 0x00FFFFFFu, V(4, 9)}, &s0);           // 11: shaded line [1],[3]
        cmd({0x20000000u, V(0, 0), V(10, 0), V(0, 10)}, &inverted);        // 12: left > right
        seal();
        CHECK(H().complete == 1 && H().entry_count == 13);
        CHECK(R(E(0).bbox, 0, 0, 24, 11));                       // [-1,24) clamped at left 0; +1024 would be off-area
        CHECK(R(E(1).bbox, 1021, 0, 1024, 3));
        CHECK(R(E(2).bbox, 0, 0, 11, 6) && E(2).dst_count == 1 && R(E(2).dst[0], 0, 0, 11, 6));
        CHECK(R(E(3).bbox, 100, 50, 201, 61));
        CHECK(R(E(4).bbox, 0, 0, 16, 4) && E(4).dst_count == 1 && (E(4).flags & LF_MUTATES));
        CHECK((E(5).flags & LF_OVERSIZE) && R(E(5).bbox, 88, 0, 1024, 2));
        CHECK(!(E(2).flags & LF_OVERSIZE));
        CHECK(R(E(6).bbox, 0, 10, 1023, 12));
        CHECK(E(7).dst_count == 0 && (E(7).flags & LF_EMPTY) && (E(7).flags & LF_TEXTURED));
        CHECK(R(E(8).bbox, 5, 30, 6, 31) && R(E(9).bbox, 5, 40, 13, 48));
        CHECK(R(E(10).bbox, 5, 60, 21, 76) && (E(10).flags & LF_TEXTURED) && E(10).clut == kClut);
        CHECK(R(E(11).bbox, 1, 1, 5, 10));
        CHECK(E(12).dst_count == 0 && (E(12).flags & LF_EMPTY));
    }

    // ---- M: native screen mapping ----
    {
        SceneLedgerState unmapped = s0;
        unmapped.native_screen_mapping = 0;
        begin();
        cmd({0x20000000u, V(0, 0), V(5, 0), V(0, 5)}, &unmapped);
        seal();
        const SceneLedgerHeader h = H();
        CHECK(h.complete == 0 && (h.incomplete_mask & LI_MAPPING) && h.mapping_unknown == 1);
        begin();
        cmd({0x02000000u, XY(0, 0), XY(16, 16)}, &unmapped);       // VRAM-space fill is unaffected
        seal();
        CHECK(H().complete == 1);
    }

    // ---- C: transfers ----
    {
        begin();
        cmd({0x80000000u, XY(600, 300), XY(100, 50), XY(10, 20)}, &s0);   // 0
        cmd({0xA0000000u, XY(1000, 10), XY(48, 4)}, &s0);                  // 1: crosses x = 1024
        cmd({0xA0000000u, XY(1000, 500), XY(48, 24)}, &s0);                // 2: corner
        cmd({0x02000000u, XY(0x13, 5), XY(0x11, 3)}, &s0);                 // 3: fill alignment
        cmd({0x02000000u, XY(0, 0), XY(0x3F1, 1)}, &s0);                   // 4: rounds to 0x400
        cmd({0x02000000u, XY(0, 0), XY(0, 4)}, &s0);                       // 5: width 0
        cmd({0x02000000u, XY(1008, 20), XY(32, 2)}, &s0);                  // 6: fill wraps
        cmd({0x80000000u, XY(5, 7), XY(9, 11), XY(0, 0)}, &s0);            // 7: zero size = 0x400 x 0x200
        cmd({0xA0000000u, XY(0, 0), XY(0, 0)}, &s0);                       // 8
        cmd({0xC0000000u, XY(10, 10), XY(0, 0)}, &s0);                     // 9
        seal();
        CHECK(H().complete == 1 && H().entry_count == 10);
        CHECK(E(0).src_count == 1 && R(E(0).src[0], 600, 300, 610, 320) && E(0).dst_count == 1 &&
              R(E(0).dst[0], 100, 50, 110, 70) && (E(0).flags & LF_MUTATES) && (E(0).flags & LF_READS));
        CHECK(E(1).dst_count == 2 && R(E(1).dst[0], 1000, 10, 1024, 14) && R(E(1).dst[1], 0, 10, 24, 14) &&
              R(E(1).bbox, 0, 10, 1024, 14));
        CHECK(E(2).dst_count == 4 && R(E(2).dst[0], 1000, 500, 1024, 512) && R(E(2).dst[1], 0, 500, 24, 512) &&
              R(E(2).dst[2], 1000, 0, 1024, 12) && R(E(2).dst[3], 0, 0, 24, 12));
        CHECK(E(3).dst_count == 1 && R(E(3).dst[0], 16, 5, 48, 8));
        CHECK(E(4).dst_count == 1 && R(E(4).dst[0], 0, 0, 1024, 1));
        CHECK(E(5).dst_count == 0 && (E(5).flags & LF_EMPTY));
        CHECK(E(6).dst_count == 2 && R(E(6).dst[0], 1008, 20, 1024, 22) && R(E(6).dst[1], 0, 20, 16, 22));
        CHECK(E(7).src_count == 4 && E(7).dst_count == 4 && R(E(7).src[0], 5, 7, 1024, 512) &&
              R(E(7).src[3], 0, 0, 5, 7) && R(E(7).dst[0], 9, 11, 1024, 512));
        CHECK(E(8).dst_count == 1 && R(E(8).dst[0], 0, 0, 1024, 512));
        CHECK(E(9).src_count == 4 && E(9).dst_count == 0 && (E(9).flags & LF_READS) && !(E(9).flags & LF_MUTATES));
    }

    // ---- D: polyline, unsupported, malformed ----
    {
        begin();
        const uint32_t hdr_only[1] = {0x48000000u};
        CHECK(scene_ledger_command(T, frame_no + 1, hdr_only, 1, nullptr) == LEDGER_OK);
        seal();
        const SceneLedgerHeader h = H();
        CHECK(h.complete == 0 && (h.incomplete_mask & LI_UNKNOWN_FOOTPRINT) && h.polylines == 1 &&
              h.unknown_footprints == 1 && h.command_count == 1);
        begin();
        CHECK(cmd({0x58000000u, V(0, 0)}, nullptr) == LEDGER_BAD_ARGUMENT);   // polyline header must be 1 word
        seal();
        CHECK((H().incomplete_mask & LI_MALFORMED) && (H().incomplete_mask & LI_UNKNOWN_FOOTPRINT));
        begin();
        cmd({0x1F000000u}, &s0);                                    // IRQ: native execute halts
        cmd({0xF0000000u}, &s0);                                    // native word count 0
        seal();
        CHECK((H().incomplete_mask & LI_UNSUPPORTED) && H().unsupported == 2 && H().complete == 0);
        begin();
        CHECK(cmd({0x24000000u, V(0, 0), 0, V(5, 0), 0, V(0, 5)}, &s0) == LEDGER_BAD_ARGUMENT);   // 6 != 7 words
        poly(s0);
        CHECK(scene_ledger_command(T, frame_no + 1, nullptr, 3, &s0) == LEDGER_BAD_ARGUMENT);
        CHECK(cmd({0x20000000u, V(0, 0), V(5, 0), V(0, 5)}, nullptr) == LEDGER_BAD_ARGUMENT);   // no state
        seal();
        CHECK(H().textured_seen == 2 && H().malformed == 3 && (H().incomplete_mask & LI_MALFORMED) && H().command_count == 4);
    }

    // ---- O: overflow ----
    {
        begin();
        for (int i = 0; i < SCENE_LEDGER_CAPACITY + 1; ++i) cmd({0x00000000u}, &s0);
        seal();
        const SceneLedgerHeader h = H();
        CHECK(h.overflow == 1 && h.command_count == uint32_t(SCENE_LEDGER_CAPACITY + 1) &&
              h.entry_count == uint32_t(SCENE_LEDGER_CAPACITY) &&
              (h.incomplete_mask & LI_OVERFLOW) && h.complete == 0);
    }

    // ---- E: VRAM hazard policy ----
    const SceneLedgerState sp = state(0, 256, 319, 495, 0, 256);   // back buffer below the displayed (0,0,320,240)
    {
        begin();
        cmd({0xE1000008u}, &sp);
        poly(sp);                                                   // 1
        cmd({0x20000000u, V(100, 100), V(110, 100), V(100, 110)}, &sp);
        seal();
        CHECK(H().complete == 1 && policy({0}) == LP_TRANSPORT_OK);
        CHECK(policy({}) == LP_TRANSPORT_OK);
        CHECK(policy({5}) == LP_NATIVE_BAD_REF && policy({0, 0}) == LP_NATIVE_BAD_REF);
        uint32_t saved = gen_no;
        gen_no = saved + 100;
        CHECK(policy({0}) == LP_NATIVE_INCOMPLETE);                  // another generation
        gen_no = saved;
    }
    {
        uint32_t entry = 0;
        begin(); poly(sp); cmd({0xA0000000u, XY(520, 10), XY(8, 8)}, &sp); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_MUTATION && entry == 1);          // write after the last draw
        begin(); cmd({0xA0000000u, XY(520, 10), XY(8, 8)}, &sp); poly(sp); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_MUTATION && entry == 0);          // write before the first draw
        begin(); poly(sp); cmd({0xA0000000u, XY(700, 300), XY(8, 8)}, &sp); seal();
        CHECK(policy({0}) == LP_TRANSPORT_OK);                                   // touches nothing transported
        begin(); poly(sp); cmd({0x02000000u, XY(32, 500), XY(16, 1)}, &sp); seal();
        CHECK(policy({0}) == LP_NATIVE_MUTATION);                                // fill over the CLUT row
        const SceneLedgerState into_page = state(512, 0, 575, 255, 512, 0);
        begin(); poly(sp); cmd({0x20000000u, V(0, 0), V(5, 0), V(0, 5)}, &into_page); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_DRAW_DEST && entry == 1);         // native draw into the page
        begin(); poly(sp, 0x0000); seal();
        CHECK(policy({0}) == LP_NATIVE_DISPLAY);                                 // page (0,0) is displayed
        begin(); poly(sp); cmd({0x02000000u, XY(0, 0), XY(16, 16)}, &sp); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_FB_MUTATION && entry == 1);       // fill of the displayed area
        begin(); poly(sp); cmd({0x80000000u, XY(16, 270), XY(700, 300), XY(8, 8)}, &sp); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_READBACK && entry == 1);          // copy reads the suppressed dst
        begin(); cmd({0x80000000u, XY(16, 270), XY(700, 300), XY(8, 8)}, &sp); poly(sp); seal();
        CHECK(policy({0}) == LP_TRANSPORT_OK);                                   // same read before the polygon
        SceneLedgerState sample = sp;
        sample.texpage = 0x0010;                                                 // 4 bpp page (0,256)
        begin(); poly(sp); cmd({0x64808080u, V(100, 100), kClut << 16, XY(16, 16)}, &sample); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_READBACK && entry == 1);          // textured sample of the dst
        begin(); poly(sp); cmd({0x48000000u}, nullptr); seal();
        CHECK(policy({0}) == LP_NATIVE_INCOMPLETE);
        SceneLedgerState wrap = state(512, 256, 831, 495, 512, 256);
        wrap.display_y = 256;                                                    // display (0,256,320,240)
        begin(); poly(wrap, 0x010F); cmd({0xA0000000u, XY(100, 10), XY(8, 8)}, &wrap); seal();
        CHECK(policy({0}, &entry) == LP_NATIVE_MUTATION && entry == 1);          // 15 bpp page 960 wraps to 0..191
        begin(); poly(sp, 0x0188); cmd({0xA0000000u, XY(40, 500), XY(8, 1)}, &sp); seal();
        CHECK(policy({0}) == LP_TRANSPORT_OK);                                   // depth 3 -> 15 bpp: no CLUT
        begin(); poly(sp, 0x0188); cmd({0xA0000000u, XY(700, 100), XY(8, 8)}, &sp); seal();
        CHECK(policy({0}) == LP_NATIVE_MUTATION);                                // and a 256-halfword page
    }

    // ---- F: foreign threads, external writes, open bodies, display, frames, generations ----
    {
        begin();
        poly(s0);
        CHECK(cmd_t(T + 1, {0x00000000u}, &s0) == LEDGER_WRONG_THREAD);
        seal();
        const SceneLedgerHeader h = H();
        CHECK(h.entry_count == 1 && h.complete == 0 && (h.incomplete_mask & LI_FOREIGN) && h.foreign_calls == 1);
    }
    {
        begin();
        const uint32_t rec = frame_no + 1;
        std::thread foreign_thread([rec] {
            const uint32_t w[1] = {0x02000000u};
            for (int i = 0; i < 1000; ++i) scene_ledger_command(T + 2, rec, w, 1, nullptr);
        });
        for (int i = 0; i < 100; ++i) cmd({0x00000000u}, &s0);
        foreign_thread.join();
        seal();
        const SceneLedgerHeader h = H();
        CHECK(h.entry_count == 100 && h.command_count == 100 && h.foreign_calls == 1000 && h.complete == 0);
    }
    {
        begin(); poly(s0); scene_ledger_note_external_vram_write(); seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_EXTERNAL) && H().external_writes == 1);
        begin(); poly(s0); seal();
        CHECK(H().complete == 1);
        scene_ledger_tick(T + 1, frame_no + 3);                      // foreign mutating call after the seal
        SceneLedgerEntry z;
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_FOREIGN) && scene_ledger_get(T, 0, gen_no, &z) == LEDGER_BAD_STATE);
    }
    {
        begin(1);                                                   // armed inside an open body
        poly(s0);
        seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_ARM_OPEN));
        const uint32_t write_hdr[3] = {0xA0000000u, XY(0, 0), XY(4, 4)}, line_hdr[1] = {0x58000000u};
        const uint32_t fill[3] = {0x02000000u, XY(0, 0), XY(16, 16)};
        scene_ledger_cancel(T); frame_no += 10; ++gen_no;
        scene_ledger_arm(T, frame_no, gen_no, 0);
        scene_ledger_command(T, frame_no, write_hdr, 3, &s0);        // last ARMED command opens a VRAM write
        scene_ledger_tick(T, frame_no + 1); poly(s0); seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_OPEN_AT_START));
        scene_ledger_cancel(T); frame_no += 10; ++gen_no;
        scene_ledger_arm(T, frame_no, gen_no, 0);
        scene_ledger_command(T, frame_no, line_hdr, 1, nullptr);     // ... or a polyline body
        scene_ledger_tick(T, frame_no + 1); poly(s0); seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_OPEN_AT_START));
        scene_ledger_cancel(T); frame_no += 10; ++gen_no;
        scene_ledger_arm(T, frame_no, gen_no, 0);
        scene_ledger_command(T, frame_no, fill, 3, &s0);             // a closed command does not
        scene_ledger_tick(T, frame_no + 1); poly(s0); seal();
        CHECK(H().complete == 1);
    }
    {
        SceneLedgerState unknown = s0;
        unknown.display_known = 0;
        begin(); poly(unknown); seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_DISPLAY_UNKNOWN));
        begin();
        SceneLedgerState d = s0;
        d.display_x = 0; cmd({0x00000000u}, &d);
        d.display_x = 64; cmd({0x00000000u}, &d);
        d.display_x = 128; cmd({0x00000000u}, &d);
        d.display_x = 0; cmd({0x00000000u}, &d);                     // repeated: not a new display
        d.display_x = 192; cmd({0x00000000u}, &d);
        seal();
        CHECK(H().complete == 1 && H().display_count == 4);
        begin();
        d.display_x = 0; cmd({0x00000000u}, &d);
        d.display_x = 64; cmd({0x00000000u}, &d);
        d.display_x = 128; cmd({0x00000000u}, &d);
        d.display_x = 192; cmd({0x00000000u}, &d);
        d.display_x = 256; cmd({0x00000000u}, &d);
        seal();
        CHECK(H().complete == 0 && (H().incomplete_mask & LI_DISPLAY_OVERFLOW) && H().display_count == 4);
    }
    {
        scene_ledger_cancel(T); frame_no += 10; ++gen_no;
        scene_ledger_arm(T, frame_no, gen_no, 0);
        scene_ledger_tick(T, frame_no + 2);                          // start skipped a frame
        scene_ledger_tick(T, frame_no + 3);
        CHECK(H().sealed == 1 && H().complete == 0 && (H().incomplete_mask & LI_FRAME_GAP));
        scene_ledger_cancel(T); frame_no += 10; ++gen_no;
        scene_ledger_arm(T, frame_no, gen_no, 0);
        scene_ledger_tick(T, frame_no + 1);
        scene_ledger_tick(T, frame_no + 3);                          // seal skipped a frame
        CHECK(H().sealed == 1 && H().complete == 0 && (H().incomplete_mask & LI_FRAME_GAP));
        CHECK(scene_ledger_arm(T, frame_no + 10, gen_no, 0) == LEDGER_BAD_ARGUMENT);   // generation reused
        CHECK(scene_ledger_cancel(T) == LEDGER_OK && H().mode == LEDGER_IDLE);
        SceneLedgerEntry z;
        CHECK(scene_ledger_get(T, 0, gen_no, &z) == LEDGER_BAD_STATE);
        CHECK(scene_ledger_arm(T, frame_no + 10, gen_no + 1, 0) == LEDGER_OK &&
              scene_ledger_arm(T, frame_no + 10, gen_no + 2, 0) == LEDGER_BAD_STATE);   // already armed
    }

    const bool passed = g_failures == 0;
    std::printf("{\"fixture\":\"scene_ledger\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
                g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = std::fopen(argv[1], "wb");   // the driver's fresh out directory guarantees a new file
        if (!f) return 3;
        std::fprintf(f, "{\"fixture\":\"scene_ledger\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                        "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (std::fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
