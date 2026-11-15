// CPU-only glue r3 lifecycle fixture (claude-einhander), glue fixture r2. SOURCE ONLY until a grant.
// r2 = r1 (44ab03a6, preserved) narrowed for failure diagnosis, per root msg_b1a99057. The 19 authored CHECKs and
// every scenario step are unchanged. Only these change:
//   - stamp(nullptr) returns an all-zero CompletionR6 and never dereferences a failed take. The CHECK before it
//     already records the failed take. (In r1, stamp(f), stamp(f3) and stamp(f5) dereferenced a null frame on a
//     producer refusal and lost the check summary.) gate() and release() are already null-safe in bridge r3;
//   - each failing CHECK line is recorded (first 32), and a diagnostic snapshot is taken after each group
//     L/O/M/Q/P/R/F: the producer audit (seal/invalid/built/bound/published/busy/refused counts, last invalid
//     bits, last scan and bind reasons), epoch, owner errors, armed epoch and the PresentState snapshot;
//   - fixture JSON revision "r2" carries failed_lines, the group snapshots and the final audit.
// Snapshots only read state; nothing in them is asserted or counted.
// r1 header follows.
// CPU-only glue r3 lifecycle fixture (claude-einhander), glue fixture r1. SOURCE ONLY until a grant.
// What it links: glue r3 (scene_runtime.cpp r3, scene_t2_bridge.r3.cpp), ledger r3 and the native v66-r3 capture TUs.
// gpu.c is not linked; its entry points are faked here (scanout state, gp0_open), and so are the PGXP / GTE-ring
// sources. Unlike glue fixture r0, the fake views are T1-consistent:
//   - the GP0 vertex word is the reprojected SXY word;
//   - flags are RTP_COMMITTED + SF, cmd 1, lane 0;
//   - the transform ring returns RT/TR whose xform_hash matches.
// So scene_capture qualifies real textured polygons, ledger r3 records them, and T2 r3/r4/r6 transport them. The
// fixture drives the complete r6 owned present lifecycle through the actual runtime entry points (arm, tick,
// command + ledger command, GP1, cancel) and the bridge consumer API (take, gate, release, scanout_now). NOTHING
// suppresses native output: gate() is only evaluated. No GL, SDK, game, GPU or DLL.
// Every CHECK executes exactly once (none in loops or helpers). The foreign-thread arm runs last, because
// owner_errors is process-lifetime.
// Usage: test-glue-r2.exe RESULT.json  (the driver sets PSXRECOMP_SCENE_CAPTURE=1)  exit 0 only when all pass.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r3.h"
#include "remix_t2.r4.h"
#include "remix_t2.r6.h"
#include "scene_ledger.r3.h"
#include "scene_runtime.h"
#include "scene_t2_bridge.r3.h"
#include <thread>

static int g_checks, g_failures;
static int g_fail_lines[32], g_nfail_lines;                          // r2: diagnosis only
#define CHECK(c) do { ++g_checks; if (!(c)) { ++g_failures; if (g_nfail_lines < 32) g_fail_lines[g_nfail_lines++] = __LINE__; \
                                              printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

namespace {
// ---- verbatim from v66-r3 scene_capture.cpp (78c4158d) :15-21 ----
uint32_t xform_hash(const SceneVertex &v) {
    uint32_t h=2166136261u;
    auto mix=[&](uint32_t w){for(int i=0;i<4;++i){h^=(w>>(i*8))&255u;h*=16777619u;}};
    for(auto w:v.rt)mix(uint16_t(w));
    for(auto w:v.tr)mix(uint32_t(w));
    mix(v.view.h);mix(uint32_t(v.view.ofx));mix(uint32_t(v.view.ofy));return h;
}
// ---- end of verbatim copy ----
}  // namespace

static const int16_t RT_ID[9] = {4096, 0, 0, 0, 4096, 0, 0, 0, 4096};
static const int32_t TR0[3] = {0, 0, 1000};
static const uint16_t H = 500;
static const int32_t OFX = 160 << 16, OFY = 120 << 16;
static const uint32_t kClut = (500u << 6) | 2u;      // CLUT (32,500); polygon tpage 0x0008: 4 bpp page (512,0)
static const uint64_t kOverlay = 0x55;

struct ViewRec { uint32_t addr; PgxpView view; };
static ViewRec g_views[16];
static uint32_t g_nviews;
static uint64_t g_xf_seq;
static uint32_t g_xf_frame;
static uint32_t g_scan[SCENE_SCANOUT_WORDS];
static int g_gp0_open, g_pgxp_on = 1;

// ---- fakes: PGXP / GTE ring (scene_runtime's SceneCaptureSource) and gpu.c glue entry points ----
extern "C" int pgxp_get_precise_vertex_view_ex(uint32_t addr, uint32_t packet_word, PgxpView *out, int *miss_reason) {
    if (miss_reason) *miss_reason = 0;
    for (uint32_t i = 0; i < g_nviews; ++i)
        if (g_views[i].addr == addr && g_views[i].view.packed == packet_word) {
            *out = g_views[i].view;
            return PGXP_SRC_DATAFLOW;
        }
    return PGXP_SRC_NATIVE;
}
extern "C" int pgxp_get_precise_vertex_view(uint32_t addr, uint32_t packet_word, PgxpView *out) {
    return pgxp_get_precise_vertex_view_ex(addr, packet_word, out, nullptr);
}
extern "C" int gte_rtp_ring_get_xform(uint64_t seq, int16_t rt[9], int32_t tr[3], uint32_t *frame, uint32_t *caller_ra) {
    if (seq != g_xf_seq) return 0;
    memcpy(rt, RT_ID, sizeof RT_ID);
    memcpy(tr, TR0, sizeof TR0);
    *frame = g_xf_frame;
    if (caller_ra) *caller_ra = 0;
    return 1;
}
extern "C" int pgxp_enabled(void) { return g_pgxp_on; }
extern "C" int pgxp_view_payload(void) { return 1; }
extern "C" int gpu_scene_gp0_open(void) { return g_gp0_open; }
extern "C" void gpu_scene_scanout_state(uint32_t s[SCENE_SCANOUT_WORDS]) { memcpy(s, g_scan, sizeof g_scan); }

// Raw scanout states (glue r2 layout): A shows (0,0), B shows (0,256); mode 0x01 = 320 wide, 15-bit, progressive.
static const uint32_t kA[SCENE_SCANOUT_WORDS] = {0, 0, 0x260, 0xC60, 0x10, 0x100, 0x01, 0};
static const uint32_t kB[SCENE_SCANOUT_WORDS] = {0, 256, 0x260, 0xC60, 0x10, 0x100, 0x01, 0};
static const uint32_t kBdepth[SCENE_SCANOUT_WORDS] = {0, 256, 0x260, 0xC60, 0x10, 0x100, 0x21, 0};
static const uint32_t kAdepth[SCENE_SCANOUT_WORDS] = {0, 0, 0x260, 0xC60, 0x10, 0x100, 0x21, 0};

// Draw state of every polygon: drawing area B = (0,256)-(319,495), draw offset (0,256), identity mapping.
static SceneDrawState g_ds;
static SceneLedgerState g_ls;
static void init_states() {
    memset(&g_ds, 0, sizeof g_ds);
    g_ds.draw_offset_y = 256;
    g_ds.draw_left = 0; g_ds.draw_top = 256; g_ds.draw_right = 319; g_ds.draw_bottom = 495;
    g_ds.effective_left = 0; g_ds.effective_right = 319;
    g_ds.native_screen_mapping = 1;
    memset(&g_ls, 0, sizeof g_ls);
    g_ls.draw_offset_y = 256;
    g_ls.draw_left = 0; g_ls.draw_top = 256; g_ls.draw_right = 319; g_ls.draw_bottom = 495;
    g_ls.texpage = 0x0008;
    g_ls.native_screen_mapping = 1;
    g_ls.display_known = 1; g_ls.display_x = 0; g_ls.display_y = 0; g_ls.display_w = 320; g_ls.display_h = 240;
}
// A T1-consistent view (as test_t2.r3.cpp vert()), bound to the fake ring record `seq` of frame `view_frame`.
static PgxpView make_view(int16_t x, int16_t y, uint32_t view_frame, uint64_t seq) {
    SceneVertex s;
    memset(&s, 0, sizeof s);
    memcpy(s.rt, RT_ID, sizeof s.rt); memcpy(s.tr, TR0, sizeof s.tr);
    s.view.v[0] = x; s.view.v[1] = y; s.view.v[2] = 0; s.view.h = H; s.view.ofx = OFX; s.view.ofy = OFY;
    for (int a = 0; a < 3; a++)
        s.view.mac[a] = (int64_t)TR0[a] * 4096 + (int64_t)RT_ID[a * 3] * x + (int64_t)RT_ID[a * 3 + 1] * y;
    s.view.flags = PGXP_VIEW_SF;
    T1Expect e;
    memset(&e, 0, sizeof e);
    t1_reproject(s.view, false, &e);
    s.view.sz3 = e.sz3; s.view.packed = e.packed; s.view.x16 = e.x16; s.view.y16 = e.y16;
    s.view.flags = (uint16_t)(e.modelled_flags | PGXP_VIEW_RTP_COMMITTED);
    s.view.frame = view_frame; s.view.cmd = 1; s.view.lane = 0; s.view.rtp_seq = seq;
    s.view.xform_hash = xform_hash(s);
    return s.view;
}
// One textured polygon (GP0 0x24) of frame `frame`, through both gpu.c hooks in gpu.c's order (capture, ledger).
static void emit_poly(uint32_t frame, uint32_t base, int16_t dx) {
    g_xf_seq = frame;
    g_xf_frame = frame - 1;                                         // lag 1, as the capture expects
    const PgxpView v0 = make_view(dx, 0, frame - 1, frame), v1 = make_view((int16_t)(dx + 10), 0, frame - 1, frame),
                   v2 = make_view(dx, 10, frame - 1, frame);
    g_views[g_nviews++] = ViewRec{base, v0};
    g_views[g_nviews++] = ViewRec{base + 8, v1};
    g_views[g_nviews++] = ViewRec{base + 16, v2};
    const uint32_t w[7] = {0x24808080u, v0.packed, (kClut << 16) | 0x0000u, v1.packed, (0x0008u << 16) | 0x0010u,
                           v2.packed, 0x1000u};
    const uint32_t src[7] = {base - 4, base, base + 4, base + 8, base + 12, base + 16, base + 20};
    scene_runtime_command(frame, w, 7, src, &g_ds);
    scene_runtime_ledger_command(frame, w, 7, &g_ls);
}
static void emit_fill(uint32_t frame, uint32_t x, uint32_t y, uint32_t fw, uint32_t fh) {
    const uint32_t w[3] = {0x02000000u, (y << 16) | x, (fh << 16) | fw};
    const uint32_t src[3] = {0x9000, 0x9004, 0x9008};
    scene_runtime_command(frame, w, 3, src, &g_ds);
    scene_runtime_ledger_command(frame, w, 3, &g_ls);
}
// Arm at f0, record two polygons at f0 + 1 into buffer B, seal at f0 + 2. Returns the arm result.
static int produce(uint32_t f0) {
    g_nviews = 0;
    const int rc = scene_runtime_arm(f0);
    scene_runtime_tick(f0 + 1);
    emit_poly(f0 + 1, 0x1000, 0);
    emit_poly(f0 + 1, 0x2000, 20);
    scene_runtime_tick(f0 + 2);
    return rc;
}
static t2::r6::CompletionR6 stamp(const t2::r6::T2FrameR6 *f) {
    t2::r6::CompletionR6 c;
    memset(&c, 0, sizeof c);
    if (!f) return c;                                                // r2: a failed take is never dereferenced
    uint64_t gen = 0;
    uint32_t s[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    scene_t2_scanout_now(&gen, s);
    c.c = t2::r4::CompletionR4{t2::Completion{f->r4.prov.frame, f->r4.prov.generation, true, kOverlay}, f->r4.prov.epoch};
    c.serial = f->present.serial;
    c.scanout_generation = gen;
    memcpy(c.scanout.w, s, sizeof s);
    return c;
}
static t2::r6::PresentSnapshot snap() {
    t2::r6::PresentSnapshot s;
    memset(&s, 0, sizeof s);
    scene_t2_present().read(&s);
    return s;
}
// ---- r2: read-only diagnostics (never asserted). Called on the owner thread only, so guard() has no effect. ----
struct GroupDiag {
    char group;
    int checks, failures;
    SceneT2Audit audit;
    uint64_t epoch, owner_errors, armed_epoch;
    t2::r6::PresentSnapshot present;
};
static GroupDiag g_diag[7];
static int g_ndiag;
static void diag(char group) {
    if (g_ndiag >= 7) return;
    GroupDiag &d = g_diag[g_ndiag++];
    d.group = group;
    d.checks = g_checks;
    d.failures = g_failures;
    d.audit = scene_t2_audit();
    d.epoch = scene_t2_epoch_now();
    d.owner_errors = scene_t2_owner_errors_now();
    d.armed_epoch = scene_runtime_armed_epoch();
    d.present = snap();
}
static void put_u64(FILE *fo, uint64_t v) {                          // portable: no 64-bit printf length modifier
    char b[24];
    int i = 23;
    b[i] = 0;
    do { b[--i] = (char)('0' + v % 10); v /= 10; } while (v);
    fputs(b + i, fo);
}
static void kv(FILE *fo, const char *key, uint64_t v, bool more) {
    fprintf(fo, "\"%s\":", key);
    put_u64(fo, v);
    if (more) fputc(',', fo);
}
static void put_audit(FILE *fo, const SceneT2Audit &a) {
    fputc('{', fo);
    kv(fo, "seals", a.seals, true); kv(fo, "invalid_seals", a.invalid_seals, true); kv(fo, "built", a.built, true);
    kv(fo, "bound", a.bound, true); kv(fo, "published", a.published, true); kv(fo, "busy", a.busy, true);
    kv(fo, "refused_scanout", a.refused_scanout, true); kv(fo, "last_invalid", a.last_invalid, true);
    kv(fo, "last_scan_reason", a.last_scan_reason, true); kv(fo, "last_bind_reason", a.last_bind_reason, false);
    fputc('}', fo);
}
static void put_words(FILE *fo, const char *key, const uint32_t *w, unsigned n) {
    fprintf(fo, "\"%s\":[", key);
    for (unsigned i = 0; i < n; ++i) fprintf(fo, "%s%u", i ? "," : "", (unsigned)w[i]);
    fputc(']', fo);
}
static void put_record(FILE *fo, const t2::r6::PresentRecord &r) {
    fputc('{', fo);
    kv(fo, "kind", r.kind, true); kv(fo, "serial", r.serial, true); kv(fo, "epoch", r.epoch, true);
    kv(fo, "boundary_generation", r.boundary_generation, true); kv(fo, "flip_generation", r.flip_generation, true);
    kv(fo, "frame", r.frame, true); kv(fo, "generation", r.generation, true); kv(fo, "boundaries", r.boundaries, true);
    put_words(fo, "target", r.target.w, (unsigned)(sizeof r.target.w / sizeof r.target.w[0]));
    fprintf(fo, ",\"target_rect\":[%d,%d,%d,%d]}", (int)r.target_rect[0], (int)r.target_rect[1], (int)r.target_rect[2],
            (int)r.target_rect[3]);
}
static void put_diag(FILE *fo, const GroupDiag &d) {
    fprintf(fo, "{\"group\":\"%c\",\"checks\":%d,\"failures\":%d,\"audit\":", d.group, d.checks, d.failures);
    put_audit(fo, d.audit);
    fputc(',', fo);
    kv(fo, "epoch", d.epoch, true); kv(fo, "owner_errors", d.owner_errors, true); kv(fo, "armed_epoch", d.armed_epoch, true);
    fputs("\"present\":{", fo);
    kv(fo, "scanout_generation", d.present.scanout_generation, true); kv(fo, "retired_serial", d.present.retired_serial, true);
    kv(fo, "reference_mode", d.present.reference_mode, true);
    kv(fo, "last_retire_reason", d.present.last_retire_reason, true);
    put_words(fo, "scanout", d.present.scanout.w, (unsigned)(sizeof d.present.scanout.w / sizeof d.present.scanout.w[0]));
    fputs(",\"pending\":", fo);
    put_record(fo, d.present.pending);
    fputs(",\"displayed\":", fo);
    put_record(fo, d.present.displayed);
    fputs("}}", fo);
}

int main(int argc, char **argv) {
    const char *env = getenv("PSXRECOMP_SCENE_CAPTURE");
    if (!env || strcmp(env, "1") != 0) return 4;
    memcpy(g_scan, kA, sizeof g_scan);
    init_states();
    const SceneT2Audit &au = scene_t2_audit();

    // ---- L: the complete lifecycle: N into B while A shows; ordinary N+1 capture; expected flip; writes ----
    CHECK(scene_runtime_enabled() == 1);
    const int rc1 = produce(5);
    CHECK(rc1 == SCENE_OK && scene_t2_epoch_now() == 2 && scene_runtime_armed_epoch() == 2);   // 1st GP1 seen: 1->2
    CHECK(au.seals == 1 && au.invalid_seals == 0 && au.built == 1 && au.bound == 1 && au.published == 1 &&
          au.last_scan_reason == t2::r6::T2S_OK && au.last_bind_reason == t2::r6::T2B_OK);
    const t2::r6::T2FrameR6 *f = scene_t2_take();
    CHECK(f != nullptr && f->present.serial == 1 && f->r4.frame.transported == 2 && f->present.target.w[1] == 256 &&
          f->present.target_rect[0] == 0 && f->present.target_rect[1] == 256 && f->present.target_rect[2] == 320 &&
          f->present.target_rect[3] == 240 && f->r4.prov.policy_ok == 1);
    const t2::r6::CompletionR6 before_flip = stamp(f);
    CHECK(!scene_t2_gate(f, kOverlay, &before_flip) && snap().pending.serial == 1);   // pending, nothing shown yet
    CHECK(scene_runtime_arm(8) == SCENE_OK && scene_t2_epoch_now() == 2 && snap().pending.serial == 1);   // N+1 begins
    scene_runtime_scanout_changed(kB);                               // the expected flip to N's buffer
    const t2::r6::CompletionR6 shown = stamp(f);
    CHECK(scene_t2_epoch_now() == 2 && snap().displayed.serial == 1 && scene_t2_gate(f, kOverlay, &shown));
    scene_runtime_tick(9);                                           // interval N+1 records
    emit_fill(9, 0, 0, 320, 240);                                    // N+1 clears back buffer A: not shown
    CHECK(scene_t2_gate(f, kOverlay, &shown));
    emit_fill(9, 0, 304, 16, 16);                                    // a write into shown buffer B
    CHECK(!scene_t2_gate(f, kOverlay, &shown) && snap().displayed.kind == t2::r6::T2P_EMPTY &&
          snap().last_retire_reason == t2::r6::T2R_WRITE);
    scene_t2_release(f);
    CHECK(scene_t2_take() == nullptr);
    diag('L');

    // ---- O: a GP0 body open AT SEAL never binds, and later data cannot revive it (root msg_2fe98abb) ----
    scene_runtime_cancel();
    scene_runtime_scanout_changed(kA);                               // show A again (an unexpected change: bump)
    const uint64_t o0 = scene_t2_epoch_now();
    g_nviews = 0;
    scene_runtime_arm(20);
    scene_runtime_tick(21);
    emit_poly(21, 0x1000, 0);
    g_gp0_open = 1;                                                  // an upload body still streaming at the seal
    scene_runtime_tick(22);
    g_gp0_open = 0;
    CHECK(au.seals == 2 && au.invalid_seals == 1 && au.last_invalid == 4u && au.bound == 1 &&
          scene_t2_take() == nullptr && scene_t2_epoch_now() > o0);
    emit_poly(22, 0x2000, 20);                                       // later data after the seal
    scene_runtime_tick(23);
    CHECK(au.seals == 2 && au.bound == 1 && scene_t2_take() == nullptr);
    diag('O');

    // ---- M: a mode change at the flip is unexpected ----
    scene_runtime_cancel();
    const int rc3 = produce(30);
    const t2::r6::T2FrameR6 *f3 = scene_t2_take();
    scene_runtime_scanout_changed(kBdepth);                          // right start, 24-bit: not the target
    const t2::r6::CompletionR6 c3 = stamp(f3);
    CHECK(rc3 == SCENE_OK && f3 != nullptr && au.bound == 2 && !scene_t2_gate(f3, kOverlay, &c3) &&
          snap().displayed.kind == t2::r6::T2P_EMPTY && snap().last_retire_reason == t2::r6::T2R_UNEXPECTED_SCANOUT);
    scene_t2_release(f3);
    diag('M');

    // ---- Q: a 24-bit display at the seal is not qualified: nothing binds ----
    scene_runtime_cancel();
    scene_runtime_scanout_changed(kAdepth);
    produce(40);
    CHECK(au.refused_scanout == 1 && au.bound == 2 && scene_t2_take() == nullptr);
    diag('Q');

    // ---- P: a polyline header (body outside the hook) retires everything ----
    scene_runtime_cancel();
    scene_runtime_scanout_changed(kA);
    produce(50);
    const t2::r6::T2FrameR6 *f5 = scene_t2_take();
    scene_runtime_scanout_changed(kB);
    const t2::r6::CompletionR6 c5 = stamp(f5);
    const bool ok5 = f5 != nullptr && scene_t2_gate(f5, kOverlay, &c5);
    const uint32_t polyline[1] = {0x48000000u};
    scene_runtime_command(52, polyline, 1, nullptr, nullptr);
    scene_runtime_ledger_command(52, polyline, 1, nullptr);
    CHECK(ok5 && au.bound == 3 && !scene_t2_gate(f5, kOverlay, &c5) && snap().last_retire_reason == t2::r6::T2R_UNKNOWN_WRITE);
    scene_t2_release(f5);
    diag('P');

    // ---- R: reference mode while PGXP is unavailable; recovery binds only a NEW sealed frame ----
    scene_runtime_cancel();
    g_pgxp_on = 0;
    const int rc6 = scene_runtime_arm(60);
    CHECK(rc6 == SCENE_PROVENANCE_UNAVAILABLE && snap().reference_mode == 1);
    g_pgxp_on = 1;
    scene_runtime_scanout_changed(kA);
    produce(70);
    CHECK(snap().reference_mode == 0 && au.bound == 4 && snap().pending.serial == au.bound &&
          snap().displayed.kind == t2::r6::T2P_EMPTY);
    diag('R');

    // ---- F: a foreign-thread consumer, then a foreign arm (last: owner_errors is process-lifetime) ----
    scene_runtime_scanout_changed(kB);                               // the expected flip of the frame bound in R
    bool foreign_ok = false;
    uint64_t foreign_serial = 0;
    std::thread consumer([&foreign_ok, &foreign_serial] {
        const t2::r6::T2FrameR6 *g = scene_t2_take();
        if (!g) return;
        const t2::r6::CompletionR6 c = stamp(g);
        foreign_ok = scene_t2_gate(g, kOverlay, &c);
        foreign_serial = g->present.serial;
        scene_t2_release(g);
    });
    consumer.join();
    CHECK(foreign_ok && foreign_serial == 4 && scene_t2_take() == nullptr);
    int foreign_rc = -1;
    std::thread arm_thread([&foreign_rc] { foreign_rc = scene_runtime_arm(80); });
    arm_thread.join();
    scene_runtime_cancel();
    scene_runtime_scanout_changed(kA);
    const uint64_t seals_before = au.seals;
    const int rc7 = produce(90);
    CHECK(foreign_rc == SCENE_WRONG_THREAD && rc7 == SCENE_OK && scene_runtime_armed_epoch() == 0 &&
          au.seals == seals_before && scene_t2_take() == nullptr && scene_t2_owner_errors_now() == 1);
    diag('F');

    const bool passed = g_failures == 0;
    printf("{\"fixture\":\"glue\",\"revision\":\"r2\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
           g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *fo = fopen(argv[1], "wb");
        if (!fo) return 3;
        fprintf(fo, "{\"fixture\":\"glue\",\"revision\":\"r2\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                    "\"gl_used\":false,\"sdk_used\":false,\"failed_lines\":[", g_checks, g_failures,
                passed ? "true" : "false");
        for (int i = 0; i < g_nfail_lines; ++i) fprintf(fo, "%s%d", i ? "," : "", g_fail_lines[i]);
        fputs("],\"groups\":[", fo);
        for (int i = 0; i < g_ndiag; ++i) {
            if (i) fputc(',', fo);
            put_diag(fo, g_diag[i]);
        }
        fputs("],\"audit\":", fo);
        put_audit(fo, au);
        fputs("}\n", fo);
        if (fclose(fo) != 0) return 3;
    }
    return passed ? 0 : 1;
}
