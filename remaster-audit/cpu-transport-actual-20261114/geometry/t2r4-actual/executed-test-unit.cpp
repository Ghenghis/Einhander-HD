// CPU-only unit fixture for T2 r4 (claude-einhander). SOURCE ONLY, not compiled or run. Same include closure as
// test_t2.r3.cpp (scene_capture.h v68 b90ebe9d, pgxp.h v68 1f50599f, gte_divide_extracted.inc cfa7686a,
// remix_t1_reproject.r1.h 4a0a536c, remix_t2.r3.h 8baba81c) plus remix_t2.r4.h. Every CHECK executes once.
// Groups: P positive path (zeroed primitives: none transported, F_OK, live-eligible), B binding negatives,
// Q policy binding on a REAL transported set (primitives built exactly as test_t2.r3.cpp's vert()/prim(), copied
// verbatim), F foreign GP0 after seal / after export / late invalidation (each with its OWN T2Liveness, since
// owner_errors is process-lifetime by design), S slot budget. A fake policy records what it was asked.
// Usage: test-t2r4.exe RESULT.json      exit 0 only when every check passed.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r3.h"
#include "remix_t2.r4.h"
#include <thread>
using namespace t2;
using namespace t2::r4;

static int g_checks, g_failures;
#define CHECK(c) do { ++g_checks; if (!(c)) { ++g_failures; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---- verbatim from test_t2.r3.cpp (215df688) :28-66: identity-RT vertices qualified through the T1 oracle ----
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

struct FakePolicy {
    uint32_t verdict, calls, frame, generation, count, ords[8];
    T2Liveness *bump;                                   // optional: an invalidation during the policy walk
};
static FakePolicy fp;
static uint32_t fake_policy(void *ctx, uint32_t frame, uint32_t generation, const uint32_t *o, uint32_t n) {
    FakePolicy *p = static_cast<FakePolicy *>(ctx);
    p->calls++; p->frame = frame; p->generation = generation; p->count = n;
    for (uint32_t i = 0; i < n && i < 8; ++i) p->ords[i] = o[i];
    if (p->bump) p->bump->invalidate();
    return p->verdict;
}
static const PolicyHook hook{fake_policy, &fp};

static const uint64_t kOverlay = 0x1234;
static ScenePrimitive prims[3];
static LedgerEntry ledger[3];
static LedgerHeader lh;
static SceneCaptureInfo info;
static T2FrameR4 fa, fb, fc;
static T2Frame r3f;
static T2Resolver resolver;
static ResolveResult rr;

static void scene(uint32_t frame, uint32_t gen, uint32_t ord1 = 1) {
    memset(prims, 0, sizeof prims);
    for (int i = 0; i < 2; ++i) { prims[i].opcode = 0x24; prims[i].frame = frame; prims[i].generation = gen; }
    prims[0].ordinal = 0;
    prims[1].ordinal = ord1;
    ledger[0] = LedgerEntry{10, 10, 50, 50, 0, 1};
    ledger[1] = LedgerEntry{600, 10, 640, 50, 1, 1};
    lh = LedgerHeader{frame, gen, 2, 1};
    memset(&info, 0, sizeof info);
    info.mode = SCENE_SEALED; info.complete = 1; info.geometry_types_complete = 1;
    info.count = 2; info.capacity = SCENE_CAPACITY; info.textured_seen = 2;
    info.frame = frame; info.generation = gen;
}
// Three real primitives at frame 10; the middle one is unqualified, so the final transported set is {0, 2}.
static void scene_q(uint32_t gen) {
    prims[0] = prim(0x24, 0, TR0, 0, H, gen);
    prims[1] = prim(0x24, 1, TR0, 20, H, gen);
    prims[1].qualified = 0;
    prims[2] = prim(0x24, 2, TR0, 40, H, gen);
    for (uint32_t i = 0; i < 3; ++i) ledger[i] = LedgerEntry{(int16_t)(i * 10), 0, (int16_t)(i * 10 + 5), 5, i, 1};
    lh = LedgerHeader{10, gen, 3, 1};
    memset(&info, 0, sizeof info);
    info.mode = SCENE_SEALED; info.complete = 1; info.geometry_types_complete = 1;
    info.count = 3; info.capacity = SCENE_CAPACITY; info.textured_seen = 3;
    info.frame = 10; info.generation = gen;
}
static SealedBinding binding(uint32_t frame, uint32_t gen, uint64_t epoch, uint32_t commands = 2) {
    return SealedBinding{frame, gen, commands, epoch, 1, 1, 1, 1};
}
static void make(const SealedBinding &b, const T2Liveness &L, T2FrameR4 *out, bool diagnostic = false,
                 const PolicyHook *h = &hook, uint32_t n = 2) {
    r4::build(prims, n, &info, b, &lh, ledger, n, diagnostic, h, L, out);
}
static CompletionR4 done(const T2FrameR4 &f) {
    return CompletionR4{Completion{f.prov.frame, f.prov.generation, true, kOverlay}, f.prov.epoch};
}

int main(int argc, char **argv) {
    // ---- P: positive path through every boundary ----
    T2Liveness L0;
    const uint64_t e0 = L0.arm_epoch();
    CHECK(e0 == 2 && L0.epoch_now() == 2 && L0.owner_errors_now() == 0);
    scene(201, 5);
    make(binding(201, 5, e0), L0, &fa);
    CHECK(fa.prov_reason == PR_OK && fa.prov.bound == 1 && fa.prov.epoch == e0 && fa.prov.frame == 201 &&
          fa.prov.generation == 5 && fa.prov.command_count == 2);
    CHECK(fa.frame.frame_reason == F_OK && fa.frame.live_eligible == 1 && fa.prov.policy_ok == 1 &&
          fa.prov.policy_verdict == kPolicyTransportOk);
    CHECK(fp.calls == 1 && fp.frame == 201 && fp.generation == 5 && fp.count == 0);   // empty transported set
    t2_build(prims, 2, &info, &lh, ledger, 2, false, &r3f);
    CHECK(memcmp(&r3f, &fa.frame, sizeof r3f) == 0);                     // r3 result unchanged when bound
    T2SlotR4 slot;
    CHECK(slot.reserve());
    CHECK(r4::publish(slot, &fa, L0) == PR_OK);
    make(binding(201, 5, e0), L0, &fb);
    CHECK(r4::publish(slot, &fb, L0) == PR_BUSY && slot.dropped_busy == 1);   // never overwrites
    ProvReason tr = PR_UNBOUND;
    T2FrameR4 *got = r4::take(slot, L0, &tr);
    CHECK(got == &fa && tr == PR_OK && slot.pending.load() == nullptr);
    CHECK(r4::resolve(resolver, *got, L0, &rr) && rr.ok);
    const CompletionR4 c0 = done(fa);
    CHECK(r4::gate_allow_suppress(fa, kOverlay, &c0, L0));
    CHECK(!r4::gate_allow_suppress(fa, kOverlay + 1, &c0, L0));           // r3 overlay rule still applies
    CHECK(!r4::gate_allow_suppress(fa, kOverlay, nullptr, L0));
    CHECK(slot.release() && !slot.release() && slot.release_underflows.load() == 1);

    // ---- B: binding negatives (L0 stays live: nothing below bumps it) ----
    info.owner_errors = 1;
    make(binding(201, 5, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_OWNER_ERRORS && fb.frame.frame_reason == F_INCOMPLETE_COVERAGE &&
          fb.frame.live_eligible == 0 && fb.prov.bound == 0 && fb.frame.native == 2 &&
          fb.frame.final_counts[P_NOT_QUALIFIED] == 2);   // r3 frame_native relabels only transported/unset
    info.owner_errors = 0;
    { SealedBinding b = binding(201, 5, e0); b.capture_complete = 0; make(b, L0, &fb); }
    CHECK(fb.prov_reason == PR_CAPTURE);
    info.mode = SCENE_RECORDING;
    make(binding(201, 5, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_CAPTURE);
    info.mode = SCENE_SEALED;
    { SealedBinding b = binding(201, 5, e0); b.ledger_sealed = 0; make(b, L0, &fb); }
    CHECK(fb.prov_reason == PR_LEDGER);
    lh.complete = 0;
    make(binding(201, 5, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_LEDGER && fb.frame.live_eligible == 0);
    lh.complete = 1;
    make(binding(202, 5, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_BINDING);
    make(binding(201, 6, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_BINDING);
    make(binding(201, 5, e0, 3), L0, &fb);
    CHECK(fb.prov_reason == PR_BINDING);
    make(binding(201, 5, e0 - 1), L0, &fb);
    CHECK(fb.prov_reason == PR_EPOCH);
    make(binding(201, 5, e0), L0, &fb, true);
    CHECK(fb.prov_reason == PR_DIAGNOSTIC && fb.frame.live_eligible == 0);
    CHECK(r4::liveness(L0, fb) == PR_UNBOUND && r4::publish(slot, &fb, L0) == PR_UNBOUND && slot.refused_stale == 1);
    scene(201, 5, 2);                                                      // ordinal mismatch -> r3 F_UNORDERED
    const uint32_t calls_before = fp.calls;
    make(binding(201, 5, e0), L0, &fb);
    CHECK(fb.prov_reason == PR_OK && fb.frame.frame_reason == F_UNORDERED && fb.prov.policy_ok == 0 &&
          fp.calls == calls_before && r4::publish(slot, &fb, L0) == PR_NOT_LIVE_ELIGIBLE);   // policy not consulted

    // ---- Q: policy bound to the exact final transported set ----
    {
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        scene_q(12);
        memset(&fp, 0, sizeof fp);
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_OK && fc.frame.frame_reason == F_OK && fc.frame.transported == 2 &&
              fc.frame.disposition_reason[1] == P_NOT_QUALIFIED && fc.prov.policy_ok == 1);
        CHECK(fp.calls == 1 && fp.frame == 10 && fp.generation == 12 && fp.count == 2 && fp.ords[0] == 0 && fp.ords[1] == 2);
        const uint32_t expected[2] = {0, 2};
        CHECK(fc.prov.policy_count == 2 && fc.prov.policy_set_hash == fnv(expected, sizeof expected));
        const CompletionR4 c = done(fc);
        CHECK(r4::gate_allow_suppress(fc, kOverlay, &c, L));
        fp.verdict = 3;                                                    // LP_NATIVE_MUTATION
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_POLICY && fc.frame.live_eligible == 0 && fc.prov.bound == 0 &&
              fc.prov.policy_verdict == 3 && fc.frame.transported == 0 && !r4::gate_allow_suppress(fc, kOverlay, &c, L));
        T2SlotR4 s;
        CHECK(r4::publish(s, &fc, L) == PR_UNBOUND && s.pending.load() == nullptr);
        fp.verdict = 5;                                                    // LP_NATIVE_DRAW_DEST
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_POLICY && fc.frame.live_eligible == 0);
        fp.verdict = 6;                                                    // LP_NATIVE_DISPLAY
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_POLICY && fc.frame.live_eligible == 0);
        fp.verdict = 7;                                                    // LP_NATIVE_READBACK
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_POLICY && fc.frame.live_eligible == 0);
        fp.verdict = 1;                                                    // LP_NATIVE_INCOMPLETE
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_POLICY && fc.frame.live_eligible == 0);
        make(binding(10, 12, e, 3), L, &fc, false, nullptr, 3);
        CHECK(fc.prov_reason == PR_POLICY_MISSING && fc.frame.live_eligible == 0);
        fp.verdict = 0;
        fp.bump = &L;                                                      // invalidation during the policy walk
        make(binding(10, 12, e, 3), L, &fc, false, &hook, 3);
        CHECK(fc.prov_reason == PR_CHANGED_DURING_BUILD && fc.frame.live_eligible == 0 && L.epoch_now() == e + 1);
        fp.bump = nullptr;
    }

    // ---- F: foreign GP0 after seal / after export, and late invalidation ----
    {   // F1: foreign GP0 after the seal, before the build
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        scene(301, 7);
        L.note_foreign();
        make(binding(301, 7, e), L, &fc);
        CHECK(fc.prov_reason == PR_OWNER_ERRORS && fc.frame.live_eligible == 0);
        const uint64_t again = L.arm_epoch();                              // a new arm cannot clear owner_errors
        make(binding(301, 7, again), L, &fc);
        CHECK(fc.prov_reason == PR_OWNER_ERRORS && L.owner_errors_now() == 1);
    }
    {   // F2: after a live build, before export
        T2Liveness L;
        T2SlotR4 s;
        const uint64_t e = L.arm_epoch();
        scene(302, 7);
        make(binding(302, 7, e), L, &fc);
        CHECK(fc.prov_reason == PR_OK);
        L.note_foreign();
        CHECK(r4::publish(s, &fc, L) == PR_OWNER_ERRORS && s.pending.load() == nullptr);
    }
    {   // F3: after export, before take: the consumer receives it flagged stale and must not resolve it
        T2Liveness L;
        T2SlotR4 s;
        const uint64_t e = L.arm_epoch();
        scene(303, 7);
        make(binding(303, 7, e), L, &fc);
        CHECK(r4::publish(s, &fc, L) == PR_OK);
        L.note_foreign();
        ProvReason r = PR_OK;
        T2FrameR4 *t = r4::take(s, L, &r);
        CHECK(t == &fc && r == PR_OWNER_ERRORS);
        CHECK(!r4::resolve(resolver, *t, L, &rr) && !rr.ok);
    }
    {   // F4: after take and resolve, before the gate
        T2Liveness L;
        T2SlotR4 s;
        const uint64_t e = L.arm_epoch();
        scene(304, 7);
        make(binding(304, 7, e), L, &fc);
        ProvReason r = PR_UNBOUND;
        r4::publish(s, &fc, L);
        T2FrameR4 *t = r4::take(s, L, &r);
        CHECK(t == &fc && r == PR_OK && r4::resolve(resolver, *t, L, &rr));
        const CompletionR4 c = done(fc);
        L.note_foreign();
        CHECK(!r4::gate_allow_suppress(fc, kOverlay, &c, L));
    }
    {   // F5: late invalidation (savestate / reset) after completion; the same call flips, nothing is cached
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        scene(305, 8);
        make(binding(305, 8, e), L, &fc);
        const CompletionR4 c = done(fc);
        CHECK(r4::gate_allow_suppress(fc, kOverlay, &c, L));
        L.invalidate();
        CHECK(!r4::gate_allow_suppress(fc, kOverlay, &c, L) && L.owner_errors_now() == 0 && r4::liveness(L, fc) == PR_EPOCH);
        make(binding(305, 8, e), L, &fb);                                  // no re-binding to the dead epoch
        CHECK(fb.prov_reason == PR_EPOCH);
    }
    {   // F6: completion not bound to the frame's epoch / frame
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        scene(306, 8);
        make(binding(306, 8, e), L, &fc);
        CompletionR4 c = done(fc);
        c.epoch = e - 1;
        CHECK(!r4::gate_allow_suppress(fc, kOverlay, &c, L));
        CompletionR4 d = done(fc);
        d.c.frame_id = 307;
        CHECK(!r4::gate_allow_suppress(fc, kOverlay, &d, L));
    }
    {   // F7: a new arm supersedes every frame of the previous generation; the new one is live
        T2Liveness L;
        const uint64_t ea = L.arm_epoch();
        scene(310, 9);
        make(binding(310, 9, ea), L, &fa);
        const uint64_t eb = L.arm_epoch();
        scene(311, 10);
        make(binding(311, 10, eb), L, &fb);
        const CompletionR4 ca = done(fa), cb = done(fb);
        CHECK(!r4::gate_allow_suppress(fa, kOverlay, &ca, L) && r4::gate_allow_suppress(fb, kOverlay, &cb, L));
    }
    {   // F8: concurrent invalidations from two threads: monotonic, none lost, bound frame dead
        T2Liveness L;
        const uint64_t e = L.arm_epoch();
        scene(320, 11);
        make(binding(320, 11, e), L, &fc);
        const CompletionR4 c = done(fc);
        std::thread a([&L] { for (int i = 0; i < 1000; ++i) L.invalidate(); });
        std::thread b([&L] { for (int i = 0; i < 1000; ++i) L.invalidate(); });
        a.join();
        b.join();
        CHECK(L.epoch_now() == e + 2000 && !r4::gate_allow_suppress(fc, kOverlay, &c, L));
    }

    // ---- S: slot budget (r3 semantics at sizeof(T2FrameR4)) ----
    {
        T2SlotR4 s;
        const bool four = s.reserve() && s.reserve() && s.reserve() && s.reserve();
        CHECK(four && !s.reserve() && s.refused_budget == 1);
    }

    const bool passed = g_failures == 0;
    printf("{\"fixture\":\"t2\",\"revision\":\"r4\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
           g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = fopen(argv[1], "wb");
        if (!f) return 3;
        fprintf(f, "{\"fixture\":\"t2\",\"revision\":\"r4\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                   "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
