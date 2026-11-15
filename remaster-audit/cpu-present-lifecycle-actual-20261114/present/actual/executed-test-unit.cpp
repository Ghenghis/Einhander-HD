// CPU-only fixture for T2 r6 owned present lifecycle (claude-einhander). SOURCE ONLY until a grant. Same include
// closure as test_t2.r4.cpp plus remix_t2.r6.h (remix_t2.r5.h is not included). Every CHECK executes exactly once
// (none inside loops or helpers). Primitives are T1-qualified (vert()/prim() verbatim from test_t2.r3.cpp 215df688
// :28-66), so frames transport. Policy and display-hazard hooks are fakes.
// Groups: N normal pipelined double buffering, S stale completions, P pending protection and bounded rules,
// F late flip / mode / range / disable / reset / foreign / arm_epoch, W writes and reference mode, D bind refusals,
// B build refusals, K seqlock smoke test.
// Usage: test-t2r6.exe RESULT.json      exit 0 only when every check passed.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r3.h"
#include "remix_t2.r4.h"
#include "remix_t2.r6.h"
#include <thread>
using namespace t2;
using namespace t2::r6;

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

static uint32_t ok_policy(void *, uint32_t, uint32_t, const uint32_t *, uint32_t) { return r4::kPolicyTransportOk; }
static uint32_t native_policy(void *, uint32_t, uint32_t, const uint32_t *, uint32_t) { return 3; }
static const r4::PolicyHook kOkPolicy{ok_policy, nullptr};
static const r4::PolicyHook kNativePolicy{native_policy, nullptr};

struct FakeHazard { uint32_t verdict, calls, count, ords[4]; int32_t rect[4]; };
static FakeHazard fh;
static uint32_t fake_hazard(void *ctx, uint32_t, uint32_t, const uint32_t *o, uint32_t n, const int32_t rect[4]) {
    FakeHazard *h = static_cast<FakeHazard *>(ctx);
    h->calls++; h->count = n;
    for (uint32_t i = 0; i < n && i < 4; ++i) h->ords[i] = o[i];
    memcpy(h->rect, rect, sizeof h->rect);
    return h->verdict;
}
static const DisplayHazardHook kHazard{fake_hazard, &fh};

static const uint64_t kOverlay = 0x55;
static ScenePrimitive prims[2];
static LedgerEntry ledger[2];
static LedgerHeader lh;
static SceneCaptureInfo info;
static T2FrameR6 fa, fb, fc, fd, fe;

// Raw scanout state: start, ranges, mode bits, disable (glue r2 layout).
static ScanoutState scan(uint32_t x, uint32_t y, uint32_t mode = 0x01, uint32_t hx2 = 0xC60, uint32_t disabled = 0) {
    ScanoutState s = {{x, y, 0x260, hx2, 0x10, 0x100, mode, disabled}};
    return s;
}
// Two transported primitives of generation `gen`, drawn with drawing area (left, top)-(left+319, top+239).
static void scene(uint32_t gen, uint16_t left, uint16_t top) {
    prims[0] = prim(0x24, 0, TR0, 0, H, gen);
    prims[1] = prim(0x24, 1, TR0, 20, H, gen);
    for (int i = 0; i < 2; ++i) {
        prims[i].state.draw_left = left; prims[i].state.draw_top = top;
        prims[i].state.draw_right = (uint16_t)(left + 319); prims[i].state.draw_bottom = (uint16_t)(top + 239);
    }
    ledger[0] = LedgerEntry{0, 0, 5, 5, 0, 1};
    ledger[1] = LedgerEntry{10, 0, 15, 5, 1, 1};
    lh = LedgerHeader{10, gen, 2, 1};
    memset(&info, 0, sizeof info);
    info.mode = SCENE_SEALED; info.complete = 1; info.geometry_types_complete = 1;
    info.count = 2; info.capacity = SCENE_CAPACITY; info.textured_seen = 2; info.frame = 10; info.generation = gen;
}
static SealedScanout sealed(const ScanoutState &boundary, uint64_t gen, uint16_t left, uint16_t top) {
    SealedScanout s;
    memset(&s, 0, sizeof s);
    s.boundary = boundary;
    s.boundary_generation = gen;
    s.target = boundary;
    s.target.w[0] = left; s.target.w[1] = top;
    s.target_rect[0] = left; s.target_rect[1] = top; s.target_rect[2] = 320; s.target_rect[3] = 240;
    s.draw_area_constant = 1;
    s.draw_left = left; s.draw_top = top; s.draw_right = (uint16_t)(left + 319); s.draw_bottom = (uint16_t)(top + 239);
    return s;
}
static void make(uint32_t gen, uint64_t epoch, const r4::T2Liveness &L, const SealedScanout &ss, T2FrameR6 *out,
                 const r4::PolicyHook *policy = &kOkPolicy, const DisplayHazardHook *hz = &kHazard) {
    const r4::SealedBinding b{10, gen, 2, epoch, 1, 1, 1, 1};
    r6::build(prims, 2, &info, b, &lh, ledger, 2, policy, L, ss, hz, out);
}
// Fresh lifecycle: the first observation (always a change: bumps the epoch), then capture_begin.
static uint64_t begin_showing(PresentState &P, r4::T2Liveness &L, const ScanoutState &shown) {
    P.observe_scanout(shown, L);
    uint64_t e = 0;
    capture_begin(L, true, &e);
    return e;
}
// Declared boundary, then build and bind frame `gen` drawn at (left, top) against the owner's current scanout.
static BindReason seal_frame(PresentState &P, r4::T2Liveness &L, uint64_t epoch, uint32_t gen, uint16_t left,
                             uint16_t top, T2FrameR6 *out) {
    P.boundary(L);
    scene(gen, left, top);
    const PresentSnapshot &o = P.owner_snapshot();
    make(gen, epoch, L, sealed(o.scanout, o.scanout_generation, left, top), out);
    return P.bind(L, out);
}
static CompletionR6 done(const T2FrameR6 &f, uint64_t scan_gen, const ScanoutState &s) {
    return CompletionR6{r4::CompletionR4{Completion{f.r4.prov.frame, f.r4.prov.generation, true, kOverlay}, f.r4.prov.epoch},
                        f.present.serial, scan_gen, s};
}

int main(int argc, char **argv) {
    const ScanoutState A = scan(0, 0), B = scan(0, 256);
    const ScanoutState Bdepth = scan(0, 256, 0x01 | 0x20), Brange = scan(0, 256, 0x01, 0xC00),
                       Boff = scan(0, 256, 0x01, 0xC60, 1);
    PresentSnapshot s;

    // ---- N: normal pipelined double buffering (frame N into B while A is shown, then N+1 into A) ----
    r4::T2Liveness L;
    PresentState P;
    const ChangeKind k0 = P.observe_scanout(A, L);
    CHECK(k0 == T2C_UNEXPECTED && L.epoch_now() == 2 && P.owner_snapshot().scanout_generation == 1);
    uint64_t e = 0;
    const bool began = capture_begin(L, true, &e);
    CHECK(began && e == 2 && L.epoch_now() == 2);                    // no bump at capture begin
    uint64_t e_bad = 7;
    CHECK(!capture_begin(L, false, &e_bad) && e_bad == 0);           // owner not healthy
    const BindReason ba = seal_frame(P, L, e, 21, 0, 256, &fa);
    CHECK(fa.scan_reason == T2S_OK && ba == T2B_OK && fa.present.serial == 1 && fa.r4.frame.transported == 2 &&
          fh.calls == 1 && fh.count == 2 && fh.ords[0] == 0 && fh.ords[1] == 1 &&
          fh.rect[0] == 0 && fh.rect[1] == 256 && fh.rect[2] == 320 && fh.rect[3] == 240);
    CHECK(P.read(&s) && s.pending.kind == T2P_PENDING && s.pending.serial == 1 && s.displayed.kind == T2P_EMPTY);
    const CompletionR6 ca = done(fa, 2, B);
    CHECK(!gate_allow_suppress(fa, kOverlay, nullptr, L, P) && !gate_allow_suppress(fa, kOverlay, &ca, L, P));
    uint64_t e_next = 0;                                             // the next ordinary capture begins pre-flip
    CHECK(capture_begin(L, true, &e_next) && e_next == e && P.read(&s) && s.pending.serial == 1);
    const ChangeKind kf = P.observe_scanout(B, L);
    CHECK(kf == T2C_FLIP_EXPECTED && L.epoch_now() == e && gate_allow_suppress(fa, kOverlay, &ca, L, P));
    CHECK(P.observe_scanout(B, L) == T2C_NO_CHANGE && gate_allow_suppress(fa, kOverlay, &ca, L, P));
    const BindReason bb = seal_frame(P, L, e, 22, 0, 0, &fb);
    CHECK(bb == T2B_OK && fb.present.serial == 2 && gate_allow_suppress(fa, kOverlay, &ca, L, P));   // N still shown
    const CompletionR6 cb = done(fb, 3, A);
    const ChangeKind kf2 = P.observe_scanout(A, L);
    CHECK(kf2 == T2C_FLIP_EXPECTED && gate_allow_suppress(fb, kOverlay, &cb, L, P) &&
          !gate_allow_suppress(fa, kOverlay, &ca, L, P));
    CHECK(P.read(&s) && s.last_retire_reason == T2R_SUPERSEDED && s.retired_serial == 1 && s.displayed.serial == 2);

    // ---- S: stale completions for the displayed frame N+1 ----
    CHECK(!gate_allow_suppress(fb, kOverlay, &ca, L, P));           // frame N's completion
    CompletionR6 c_serial = cb; c_serial.serial = 1;
    CHECK(!gate_allow_suppress(fb, kOverlay, &c_serial, L, P));
    CompletionR6 c_gen = cb; c_gen.scanout_generation = 2;
    CHECK(!gate_allow_suppress(fb, kOverlay, &c_gen, L, P));
    CompletionR6 c_state = cb; c_state.scanout = B;
    CHECK(!gate_allow_suppress(fb, kOverlay, &c_state, L, P));

    // ---- P: pending protection and bounded rules (continuing: N+1 displayed, A shown) ----
    const BindReason bc = seal_frame(P, L, e, 23, 0, 256, &fc);      // boundary 1 after the flip
    CHECK(bc == T2B_OK && fc.present.serial == 3);
    const BindReason bd = seal_frame(P, L, e, 24, 0, 256, &fd);      // no flip came: boundary 2
    CHECK(bd == T2B_PENDING_BUSY && fd.present.serial == 0 && P.read(&s) && s.pending.serial == 3 &&
          gate_allow_suppress(fb, kOverlay, &cb, L, P));
    P.boundary(L);                                                   // boundary 3: abandoned and stale
    CHECK(P.read(&s) && s.pending.kind == T2P_EMPTY && s.displayed.kind == T2P_EMPTY &&
          !gate_allow_suppress(fb, kOverlay, &cb, L, P));
    const ChangeKind klate = P.observe_scanout(B, L);                // late flip of the abandoned candidate
    CHECK(klate == T2C_UNEXPECTED && L.epoch_now() == e + 1);
    {
        r4::T2Liveness Ls;
        PresentState Ps;
        const uint64_t es = begin_showing(Ps, Ls, A);
        seal_frame(Ps, Ls, es, 25, 0, 256, &fd);
        Ps.observe_scanout(B, Ls);
        const CompletionR6 cd = done(fd, 2, B);
        Ps.boundary(Ls);
        Ps.boundary(Ls);
        const bool shown2 = gate_allow_suppress(fd, kOverlay, &cd, Ls, Ps);
        Ps.boundary(Ls);
        CHECK(shown2 && !gate_allow_suppress(fd, kOverlay, &cd, Ls, Ps) && Ps.read(&s) &&
              s.last_retire_reason == T2R_STALE);
    }
    {
        r4::T2Liveness La;
        PresentState Pa;
        const uint64_t ea = begin_showing(Pa, La, A);
        seal_frame(Pa, La, ea, 26, 0, 256, &fd);
        Pa.boundary(La);
        const bool still = Pa.read(&s) && s.pending.kind == T2P_PENDING;
        Pa.boundary(La);
        CHECK(still && Pa.read(&s) && s.pending.kind == T2P_EMPTY && s.last_retire_reason == T2R_ABANDONED);
    }

    // ---- F: late flip, mode / range / disable at the flip, reset, foreign reset, arm_epoch, foreign call ----
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 30, 0, 256, &fd);
        Pf.observe_scanout(B, Lf);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        const ChangeKind k = Pf.observe_scanout(A, Lf);              // late flip between resolve and gate
        CHECK(ok_before && k == T2C_UNEXPECTED && Lf.epoch_now() == ef + 1 && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf));
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 31, 0, 256, &fd);
        const ChangeKind k = Pf.observe_scanout(Bdepth, Lf);         // right start, 24-bit depth
        const CompletionR6 cd = done(fd, 2, Bdepth);
        CHECK(k == T2C_UNEXPECTED && Lf.epoch_now() == ef + 1 && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf) &&
              Pf.read(&s) && s.pending.kind == T2P_EMPTY && s.last_retire_reason == T2R_UNEXPECTED_SCANOUT);
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 32, 0, 256, &fd);
        const ChangeKind k = Pf.observe_scanout(Brange, Lf);         // right start, other horizontal range
        const CompletionR6 cd = done(fd, 2, Brange);
        CHECK(k == T2C_UNEXPECTED && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf) && Pf.read(&s) &&
              s.pending.kind == T2P_EMPTY);
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 33, 0, 256, &fd);
        const ChangeKind k = Pf.observe_scanout(Boff, Lf);           // display disabled at the flip
        const CompletionR6 cd = done(fd, 2, Boff);
        CHECK(k == T2C_UNEXPECTED && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf) && Pf.read(&s) &&
              s.pending.kind == T2P_EMPTY);
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 34, 0, 256, &fd);
        Pf.observe_scanout(B, Lf);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        Pf.invalidate_all(Lf, T2R_INVALIDATED);                      // owner reset / savestate / invalid capture
        CHECK(ok_before && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf) && Lf.epoch_now() == ef + 1 &&
              Pf.read(&s) && s.displayed.kind == T2P_EMPTY && s.last_retire_reason == T2R_INVALIDATED);
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 35, 0, 256, &fd);
        Pf.observe_scanout(B, Lf);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        std::thread t([&Lf] { Lf.invalidate(); });                   // foreign-thread reset: r4 epoch only
        t.join();
        const bool after = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        Pf.boundary(Lf);                                             // the owner retires it at its next boundary
        CHECK(ok_before && !after && Pf.read(&s) && s.displayed.kind == T2P_EMPTY && s.last_retire_reason == T2R_EPOCH);
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 36, 0, 256, &fd);
        Pf.observe_scanout(B, Lf);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        Lf.arm_epoch();                                              // r4 arm keeps its F7 meaning
        CHECK(ok_before && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf));
    }
    {
        r4::T2Liveness Lf;
        PresentState Pf;
        const uint64_t ef = begin_showing(Pf, Lf, A);
        seal_frame(Pf, Lf, ef, 37, 0, 256, &fd);
        Pf.observe_scanout(B, Lf);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf);
        Lf.note_foreign();                                           // a foreign GP0/frame call
        uint64_t e2 = 5;
        CHECK(ok_before && !gate_allow_suppress(fd, kOverlay, &cd, Lf, Pf) && !capture_begin(Lf, true, &e2) && e2 == 0);
    }

    // ---- W: writes (displayed target B = rect (0,256,320,240)) and reference mode ----
    {
        r4::T2Liveness Lw;
        PresentState Pw;
        const uint64_t ew = begin_showing(Pw, Lw, A);
        seal_frame(Pw, Lw, ew, 40, 0, 256, &fd);
        Pw.observe_scanout(B, Lw);
        const CompletionR6 cd = done(fd, 2, B);
        const bool ok_before = gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw);
        const int32_t back[4] = {0, 0, 320, 240};                    // next interval draws into A: no overlap
        Pw.note_write(back, true);
        const bool ok_back = gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw);
        const int32_t front[4] = {0, 300, 16, 16};                   // a fill into the shown buffer
        Pw.note_write(front, true);
        CHECK(ok_before && ok_back && !gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw) && Pw.read(&s) &&
              s.displayed.kind == T2P_EMPTY && s.last_retire_reason == T2R_WRITE && Lw.epoch_now() == ew);
    }
    {
        r4::T2Liveness Lw;
        PresentState Pw;
        const uint64_t ew = begin_showing(Pw, Lw, A);
        seal_frame(Pw, Lw, ew, 41, 0, 256, &fd);
        const int32_t into_pending[4] = {100, 300, 8, 8};            // the sealed buffer changes before its flip
        Pw.note_write(into_pending, true);
        const bool gone = Pw.read(&s) && s.pending.kind == T2P_EMPTY && s.last_retire_reason == T2R_WRITE;
        CHECK(gone && Pw.observe_scanout(B, Lw) == T2C_UNEXPECTED);
    }
    {
        r4::T2Liveness Lw;
        PresentState Pw;
        const uint64_t ew = begin_showing(Pw, Lw, A);
        seal_frame(Pw, Lw, ew, 42, 0, 256, &fd);
        Pw.observe_scanout(B, Lw);
        const CompletionR6 cd = done(fd, 2, B);
        const int32_t any[4] = {0, 0, 1, 1};
        Pw.note_write(any, false);                                   // footprint unknown
        CHECK(!gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw) && Pw.read(&s) && s.displayed.kind == T2P_EMPTY &&
              s.last_retire_reason == T2R_UNKNOWN_WRITE);
    }
    {
        r4::T2Liveness Lw;
        PresentState Pw;
        const uint64_t ew = begin_showing(Pw, Lw, A);
        seal_frame(Pw, Lw, ew, 43, 0, 256, &fd);
        Pw.observe_scanout(B, Lw);
        const CompletionR6 cd = done(fd, 2, B);
        const int32_t wraps[4] = {1000, 0, 64, 16};                  // wraps past x = 1024: treated as unknown
        Pw.note_write(wraps, true);
        CHECK(!gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw) && Pw.read(&s) && s.last_retire_reason == T2R_UNKNOWN_WRITE);
    }
    {
        r4::T2Liveness Lw;
        PresentState Pw;
        const uint64_t ew = begin_showing(Pw, Lw, A);
        seal_frame(Pw, Lw, ew, 44, 0, 256, &fd);
        Pw.observe_scanout(B, Lw);
        const CompletionR6 cd = done(fd, 2, B);
        Pw.set_reference_mode(true);
        const bool g = gate_allow_suppress(fd, kOverlay, &cd, Lw, Pw);
        const BindReason br = seal_frame(Pw, Lw, ew, 45, 0, 0, &fe);
        CHECK(!g && br == T2B_REFERENCE && fe.present.serial == 0 && Pw.read(&s) && s.last_retire_reason == T2R_REFERENCE);
        Pw.set_reference_mode(false);
        const BindReason br2 = seal_frame(Pw, Lw, ew, 46, 0, 0, &fe);
        CHECK(br2 == T2B_OK && fe.present.serial == 2);
    }

    // ---- D: bind refusals ----
    {
        r4::T2Liveness Ld;
        PresentState Pd;
        const uint64_t ed = begin_showing(Pd, Ld, A);
        const BindReason br = seal_frame(Pd, Ld, ed, 50, 0, 0, &fd);  // drawn into the shown buffer
        CHECK(fd.scan_reason == T2S_SINGLE_BUFFER && br == T2B_NOT_CANDIDATE && fd.present.serial == 0 &&
              Pd.read(&s) && s.pending.kind == T2P_EMPTY);
    }
    {
        r4::T2Liveness Ld;
        PresentState Pd;
        const uint64_t ed = begin_showing(Pd, Ld, A);
        Pd.boundary(Ld);
        scene(51, 0, 256);
        make(51, ed, Ld, sealed(A, 7, 0, 256), &fd);                 // boundary generation is not the owner's
        CHECK(fd.scan_reason == T2S_OK && Pd.bind(Ld, &fd) == T2B_SCANOUT_MOVED && fd.present.serial == 0);
    }
    {
        r4::T2Liveness Ld;
        PresentState Pd;
        const uint64_t ed = begin_showing(Pd, Ld, A);
        Pd.boundary(Ld);
        scene(52, 0, 256);
        make(52, ed, Ld, sealed(A, 1, 0, 256), &fd);
        Ld.invalidate();                                             // between build and bind
        CHECK(fd.scan_reason == T2S_OK && Pd.bind(Ld, &fd) == T2B_NOT_LIVE && fd.present.serial == 0);
    }

    // ---- B: build-time refusals ----
    r4::T2Liveness Lb;
    scene(60, 0, 256);
    { SealedScanout ss = sealed(A, 1, 0, 256); ss.draw_area_constant = 0; make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_DRAW_AREA_VARIED && fd.present.scan_ok == 0);
    { SealedScanout ss = sealed(A, 1, 0, 256); ss.target.w[1] = 240; ss.target_rect[1] = 240; make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_TARGET_NOT_BUFFER);
    { SealedScanout ss = sealed(A, 1, 0, 256); ss.target.w[6] = 0x21; make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_TARGET_STATE);
    { SealedScanout ss = sealed(scan(0, 0, 0x01, 0xC60, 1), 1, 0, 256); make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_TARGET_DISABLED);
    { SealedScanout ss = sealed(A, 1, 0, 256); ss.target_rect[2] = 0; make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_RECT);
    { SealedScanout ss = sealed(A, 1, 0, 256); ss.target_rect[3] = 300; make(60, Lb.epoch_now(), Lb, ss, &fd); }
    CHECK(fd.scan_reason == T2S_RECT);                               // 256 + 300 > 512: outside VRAM
    prims[1].state.draw_top = 0;                                     // one transported prim in another area
    make(60, Lb.epoch_now(), Lb, sealed(A, 1, 0, 256), &fd);
    CHECK(fd.scan_reason == T2S_PRIM_AREA && fd.present.scan_ok == 0);
    scene(61, 0, 256);
    fh.verdict = 6;                                                  // LP_NATIVE_DISPLAY at the target rect
    make(61, Lb.epoch_now(), Lb, sealed(A, 1, 0, 256), &fd);
    CHECK(fd.scan_reason == T2S_HAZARD && fd.hazard_verdict == 6 && fd.present.scan_ok == 0);
    fh.verdict = 0;
    make(61, Lb.epoch_now(), Lb, sealed(A, 1, 0, 256), &fd, &kOkPolicy, nullptr);
    CHECK(fd.scan_reason == T2S_HAZARD_MISSING);
    make(61, Lb.epoch_now(), Lb, sealed(A, 1, 0, 256), &fd, &kNativePolicy);
    CHECK(fd.scan_reason == T2S_NOT_LIVE && fd.r4.prov_reason == r4::PR_POLICY);

    // ---- K: seqlock smoke test (not a memory-model proof) ----
    {   // X and Y differ in EVERY word; the writer alternates them, so X is published exactly at odd scanout
        // generations and Y at even ones. A torn snapshot or a state/generation mismatch is detectable.
        const ScanoutState X = {{1, 2, 3, 4, 5, 6, 7, 0}}, Y = {{101, 102, 103, 104, 105, 106, 107, 1}};
        r4::T2Liveness Lk;
        PresentState Pk;
        Pk.observe_scanout(X, Lk);                                   // generation 1
        bool torn = false, decreasing = false;
        uint32_t reads = 0;
        uint64_t last = 0;
        std::thread writer([&Pk, &Lk, &X, &Y] { for (int i = 0; i < 5000; ++i) Pk.observe_scanout((i & 1) ? X : Y, Lk); });
        std::thread reader([&] {
            for (int i = 0; i < 5000; ++i) {
                PresentSnapshot r;
                if (!Pk.read(&r)) continue;
                ++reads;
                const uint64_t g = r.scanout_generation;
                if (!(same(r.scanout, X) && (g & 1) == 1) && !(same(r.scanout, Y) && (g & 1) == 0)) torn = true;
                if (r.pending.kind != T2P_EMPTY || r.displayed.kind != T2P_EMPTY) torn = true;
                if (g < last) decreasing = true;
                last = g;
            }
        });
        writer.join();
        reader.join();
        PresentSnapshot fin;
        const bool fin_ok = Pk.read(&fin);
        CHECK(!torn && !decreasing && reads > 0 && fin_ok && fin.scanout_generation == 5001 && same(fin.scanout, X) &&
              Lk.epoch_now() == 1 + 5001);
    }

    const bool passed = g_failures == 0;
    printf("{\"fixture\":\"t2\",\"revision\":\"r6\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
           g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = fopen(argv[1], "wb");
        if (!f) return 3;
        fprintf(f, "{\"fixture\":\"t2\",\"revision\":\"r6\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                   "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
