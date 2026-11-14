// CPU integration fixture: T2 r4 x REAL scene_ledger r0 policy (claude-einhander). SOURCE ONLY until a grant.
// Same T2 closure as test_t2.r4.cpp plus scene_ledger.r0.h and the (diagnostic-only) export adapter
// scene_ledger_t2.r0.h; linked with scene_ledger.r0.cpp and its generated scene_ledger_native_unpack.inc.
// Every CHECK executes once. Each scenario records a real ledger interval (arm 9, record 10, seal 11) whose textured
// polygons are T1-qualified primitives (vert()/prim() copied verbatim from test_t2.r3.cpp 215df688 :28-66),
// exports it, and runs r4::build with a policy hook that calls scene_ledger_policy on the owner token.
// The adapter export is complete in I1-I4 while the policy is native: r4 must keep those frames native.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <initializer_list>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r3.h"
#include "remix_t2.r4.h"
#include "scene_ledger.r0.h"
#include "scene_ledger_t2.r0.h"
using namespace t2;
using namespace t2::r4;

static int g_checks, g_failures;
#define CHECK(c) do { ++g_checks; if (!(c)) { ++g_failures; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---- verbatim from test_t2.r3.cpp (215df688) :28-66 ----
static const int16_t RT_ID[9] = {4096, 0, 0, 0, 4096, 0, 0, 0, 4096};
static const uint16_t H = 500;
static const int32_t OFX = 160 << 16, OFY = 120 << 16;

static SceneVertex vert(const int16_t rt[9], const int32_t tr[3], int16_t x, int16_t y, int16_t z, uint8_t u, uint8_t v,
                        uint16_t h = H) {
    SceneVertex s; memset(&s, 0, sizeof s);
    memcpy(s.rt, rt, sizeof s.rt); memcpy(s.tr, tr, sizeof s.tr);
    s.view.v[0] = x; s.view.v[1] = y; s.view.v[2] = z; s.view.h = h; s.view.ofx = OFX; s.view.ofy = OFY;
    for (int a = 0; a < 3; a++)
        s.view.mac[a] = (int64_t)tr[a] * 4096 + (int64_t)rt[a * 3] * x + (int64_t)rt[a * 3 + 1] * y + (int64_t)rt[a * 3 + 2] * z;
    s.view.flags = PGXP_VIEW_SF;
    T1Expect e; memset(&e, 0, sizeof e);
    t1_reproject(s.view, false, &e);
    s.view.sz3 = e.sz3; s.view.packed = e.packed; s.view.x16 = e.x16; s.view.y16 = e.y16;
    s.view.flags = (uint16_t)(e.modelled_flags | PGXP_VIEW_RTP_COMMITTED);
    s.reason = SCENE_VERTEX_OK; s.lag = 1; s.u = u; s.v = v; s.rgb = 0x808080;
    return s;
}

static const int32_t TR0[3] = {0, 0, 1000};
static ScenePrimitive prim(uint8_t opcode, uint32_t ordinal, const int32_t tr[3] = TR0, int16_t dx = 0,
                           uint16_t h = H, uint32_t generation = 1) {
    ScenePrimitive p; memset(&p, 0, sizeof p);
    p.opcode = opcode; p.qualified = 1; p.frame = 10; p.generation = generation; p.ordinal = ordinal;
    p.tpage = 0x10; p.clut = 0x20; p.depth = 0;
    p.semi_trans = (opcode & 0x02) ? 1 : 0; p.raw_texture = (opcode & 0x01) ? 1 : 0;
    const bool quad = (opcode & 0x08) != 0;
    p.nverts = quad ? 4 : 3; p.triangle_count = quad ? 2 : 1;
    const uint8_t idx[6] = {0, 1, 2, 2, 1, 3}; memcpy(p.indices, idx, sizeof idx);
    p.vertex[0] = vert(RT_ID, tr, (int16_t)(dx + 0), 0, 0, 0, 0, h);
    p.vertex[1] = vert(RT_ID, tr, (int16_t)(dx + 10), 0, 0, 16, 0, h);
    p.vertex[2] = vert(RT_ID, tr, (int16_t)(dx + 0), 10, 0, 0, 16, h);
    p.vertex[3] = vert(RT_ID, tr, (int16_t)(dx + 10), 10, 0, 16, 16, h);
    p.screen_mapping_known = 1;
    p.eligible_triangle_mask = (uint8_t)((1u << p.triangle_count) - 1u);
    for (int k = 0; k < 4; k++) { p.vertex[k].packet_word = p.vertex[k].view.packed; p.vertex[k].view.frame = p.frame - p.vertex[k].lag; }
    return p;
}
// ---- end of verbatim copy ----

static const uint32_t TOK = 21;
static const uint32_t kClut = (500u << 6) | 2u;                     // CLUT row (32,500), 16 entries at 4 bpp
static const uint64_t kOverlay = 0x77;
static uint32_t gen = 100;
static SceneLedgerState st, into_page;
static ScenePrimitive P[2];
static SceneCaptureInfo ci;
static LedgerHeader lh;
static LedgerEntry le[16];
static uint32_t nle;
static T2FrameR4 fr;

static uint32_t V(int x, int y) { return ((uint32_t(y) & 0x7FFu) << 16) | (uint32_t(x) & 0x7FFu); }
static SceneLedgerState state(int l, int t, int r, int b, int ox, int oy) {
    SceneLedgerState s;
    memset(&s, 0, sizeof s);
    s.draw_left = uint16_t(l); s.draw_top = uint16_t(t); s.draw_right = uint16_t(r); s.draw_bottom = uint16_t(b);
    s.draw_offset_x = ox; s.draw_offset_y = oy;
    s.texpage = 0x0008; s.native_screen_mapping = 1;
    s.display_known = 1; s.display_x = 0; s.display_y = 256; s.display_w = 320; s.display_h = 240;
    return s;
}
static void send(std::initializer_list<uint32_t> words, const SceneLedgerState *s) {
    uint32_t w[16];
    int n = 0;
    for (uint32_t x : words) w[n++] = x;
    scene_ledger_command(TOK, 10, w, n, s);
}
// Textured triangle (40x40) sampling the tpage word's page and the CLUT at (32,500).
static void tri(int x, int y, uint32_t tpage = 0x0008) {
    send({0x24808080u, V(x, y), kClut << 16, V(x + 40, y), (tpage << 16) | 0x10u, V(x, y + 40), 0x1000u}, &st);
}
static void begin() { scene_ledger_cancel(TOK); ++gen; scene_ledger_arm(TOK, 9, gen, 0); scene_ledger_tick(TOK, 10); }
static void seal() { scene_ledger_tick(TOK, 11); }
// T2 side of the same interval: two qualified primitives (ordinals 0, 1), sealed capture info, adapter export.
static bool t2_side() {
    P[0] = prim(0x24, 0, TR0, 0, H, gen);
    P[1] = prim(0x24, 1, TR0, 20, H, gen);
    memset(&ci, 0, sizeof ci);
    ci.mode = SCENE_SEALED; ci.complete = 1; ci.geometry_types_complete = 1;
    ci.count = 2; ci.capacity = SCENE_CAPACITY; ci.textured_seen = 2; ci.frame = 10; ci.generation = gen;
    return scene_ledger_export_t2(TOK, gen, &lh, le, 16, &nle);
}
static SealedBinding sealed_binding(uint64_t epoch) {      // producer: from the owner-only sealed ledger header
    SceneLedgerHeader h;
    memset(&h, 0, sizeof h);
    scene_ledger_header(TOK, &h);
    return SealedBinding{h.frame, h.generation, h.command_count, epoch, 1, 1, h.sealed, h.complete};
}
struct LedgerPolicyCtx { uint32_t token; };
static uint32_t ledger_policy(void *ctx, uint32_t frame, uint32_t generation, const uint32_t *o, uint32_t n) {
    const uint32_t token = static_cast<LedgerPolicyCtx *>(ctx)->token;
    SceneLedgerHeader h;
    if (scene_ledger_header(token, &h) != LEDGER_OK || !h.complete || h.frame != frame || h.generation != generation)
        return LP_NATIVE_INCOMPLETE;
    SceneLedgerVerdict v;
    if (scene_ledger_policy(token, generation, o, n, &v) != LEDGER_OK) return LP_NATIVE_INCOMPLETE;
    return v.verdict;
}
static LedgerPolicyCtx pctx{TOK};
static const PolicyHook lhook{ledger_policy, &pctx};
static void build_r4(const SealedBinding &b, const T2Liveness &L) {
    r4::build(P, 2, &ci, b, &lh, le, nle, false, &lhook, L, &fr);
}
static CompletionR4 done() {
    return CompletionR4{Completion{fr.prov.frame, fr.prov.generation, true, kOverlay}, fr.prov.epoch};
}

int main(int argc, char **argv) {
    st = state(0, 0, 1023, 511, 0, 0);                            // display (0,256,320,240); page (512,0) 4 bpp
    into_page = state(512, 0, 575, 255, 512, 0);                  // drawing area inside that page
    CHECK(scene_ledger_init(TOK, 1) == LEDGER_OK);

    {   // I0 baseline: two transported polygons, nothing hazardous -> accepted, gate allows
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); seal();
        CHECK(t2_side() && nle == 2 && lh.complete == 1);
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_OK && fr.frame.frame_reason == F_OK && fr.frame.transported == 2 &&
              fr.prov.policy_ok == 1 && fr.prov.policy_verdict == LP_TRANSPORT_OK && fr.prov.policy_count == 2);
        const CompletionR4 c = done();
        CHECK(r4::gate_allow_suppress(fr, kOverlay, &c, L));
    }
    {   // I1 CLUT mutation AFTER the last draw, screen bbox disjoint from both polygons
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); send({0x02000000u, (500u << 16) | 32u, (1u << 16) | 16u}, &st); seal();
        CHECK(t2_side() && nle == 3 && lh.complete == 1);           // the adapter alone says complete
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_POLICY && fr.prov.policy_verdict == LP_NATIVE_MUTATION && fr.frame.live_eligible == 0);
    }
    {   // I2 draw feedback: a native draw writes into the transported page
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); send({0x20000000u, V(0, 100), V(5, 100), V(0, 105)}, &into_page); seal();
        CHECK(t2_side() && lh.complete == 1);
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_POLICY && fr.prov.policy_verdict == LP_NATIVE_DRAW_DEST && fr.frame.live_eligible == 0);
    }
    {   // I3 display overlap: polygon 0 samples page (0,256), which is the displayed area
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10, 0x0010); tri(100, 10); seal();
        CHECK(t2_side() && lh.complete == 1);
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_POLICY && fr.prov.policy_verdict == LP_NATIVE_DISPLAY && fr.frame.live_eligible == 0);
    }
    {   // I4 readback: a later VRAM->VRAM copy reads polygon 0's natively suppressed destination
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10);
        send({0x80000000u, (16u << 16) | 16u, (300u << 16) | 700u, (8u << 16) | 8u}, &st); seal();
        CHECK(t2_side() && lh.complete == 1);
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_POLICY && fr.prov.policy_verdict == LP_NATIVE_READBACK && fr.frame.live_eligible == 0);
    }
    {   // I5 foreign GP0 AFTER export, before acceptance: the policy re-evaluates inside build and refuses
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); seal();
        CHECK(t2_side());
        const SealedBinding b = sealed_binding(e);                 // taken while still complete
        const uint32_t w[1] = {0x00000000u};
        scene_ledger_command(TOK + 1, 10, w, 1, &st);              // foreign token: ledger counter only
        build_r4(b, L);
        CHECK(b.ledger_complete == 1 && fr.prov_reason == PR_POLICY && fr.prov.policy_verdict == LP_NATIVE_INCOMPLETE);
    }
    {   // I6 external VRAM write AFTER acceptance: only the epoch (glue duty) can revoke; the gate then refuses
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); seal();
        CHECK(t2_side());
        build_r4(sealed_binding(e), L);
        const CompletionR4 c = done();
        CHECK(fr.prov_reason == PR_OK && r4::gate_allow_suppress(fr, kOverlay, &c, L));
        scene_ledger_note_external_vram_write();
        L.invalidate();
        CHECK(!r4::gate_allow_suppress(fr, kOverlay, &c, L));
    }
    {   // I8 GP1 display change AFTER the last GP0 (the ledger cannot see GP1): glue duty L.invalidate() -> refused
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); seal();
        CHECK(t2_side());
        build_r4(sealed_binding(e), L);
        const CompletionR4 c = done();
        const bool before = r4::gate_allow_suppress(fr, kOverlay, &c, L);
        L.invalidate();                                            // gp1_display_area_start / range / mode hook
        CHECK(before && !r4::gate_allow_suppress(fr, kOverlay, &c, L) && r4::liveness(L, fr) == PR_EPOCH);
    }
    {   // I7 foreign GP0 after the seal, before export: the export refuses and r4 stays native
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        begin(); tri(10, 10); tri(100, 10); seal();
        const uint32_t w[1] = {0x00000000u};
        scene_ledger_command(TOK + 1, 10, w, 1, &st);
        CHECK(!t2_side() && nle == 0 && lh.complete == 0);
        build_r4(sealed_binding(e), L);
        CHECK(fr.prov_reason == PR_LEDGER && fr.frame.live_eligible == 0);
    }

    const bool passed = g_failures == 0;
    printf("{\"fixture\":\"t2r4_ledger\",\"revision\":\"r4\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
           g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = fopen(argv[1], "wb");
        if (!f) return 3;
        fprintf(f, "{\"fixture\":\"t2r4_ledger\",\"revision\":\"r4\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                   "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
