// CPU-only glue r2 wiring fixture (claude-einhander), glue fixture r0. SOURCE ONLY until a grant.
// Links the FROZEN glue r2 TUs (scene_runtime.cpp 3bbc6821, scene_t2_bridge.r2.cpp a88b6911) with ledger r0
// (scene_ledger.r0.cpp 9614a6a8) and the native capture TUs (v66-r3 scene_capture.cpp 78c4158d, scene_json.cpp
// 4305f17e). gpu.c is NOT linked (it is compile-checked separately): its two glue entry points are faked here, as
// are the five PGXP / GTE-ring functions the runtime binds (every lookup misses). Exercises liveness wiring and the
// explicit-native paths only. No primitive transports; no GL, SDK, game, GPU or DLL.
// Every CHECK executes exactly once (none in loops or helpers). owner_errors is process-lifetime, so the
// foreign-thread group runs last.
// Usage: test-glue-r0.exe RESULT.json      exit 0 only when every check passed.
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
#include "scene_ledger.r0.h"
#include "scene_runtime.h"
#include "scene_t2_bridge.r2.h"
#include <thread>

static int g_checks, g_failures;
#define CHECK(c) do { ++g_checks; if (!(c)) { ++g_failures; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

// ---- fakes for the native symbols the glue TUs reference (gpu.c, PGXP, GTE ring) ----
static uint32_t g_scan[SCENE_SCANOUT_WORDS];
extern "C" int pgxp_get_precise_vertex_view(uint32_t, uint32_t, PgxpView *) { return PGXP_SRC_NATIVE; }
extern "C" int pgxp_get_precise_vertex_view_ex(uint32_t, uint32_t, PgxpView *, int *miss_reason) {
    if (miss_reason) *miss_reason = 0;
    return PGXP_SRC_NATIVE;
}
extern "C" int gte_rtp_ring_get_xform(uint64_t, int16_t[9], int32_t[3], uint32_t *, uint32_t *) { return 0; }
extern "C" int pgxp_enabled(void) { return 1; }
extern "C" int pgxp_view_payload(void) { return 1; }
extern "C" int gpu_scene_gp0_open(void) { return 0; }
extern "C" void gpu_scene_scanout_state(uint32_t s[SCENE_SCANOUT_WORDS]) { memcpy(s, g_scan, sizeof g_scan); }

// Raw scanout states in the glue r2 layout: start x/y, h range, v range, mode bits, disable.
static const uint32_t kA[SCENE_SCANOUT_WORDS] = {0, 0, 0x260, 0xC60, 0x10, 0x100, 0x01, 0};
static const uint32_t kB[SCENE_SCANOUT_WORDS] = {0, 256, 0x260, 0xC60, 0x10, 0x100, 0x01, 0};
static const uint32_t kBmode[SCENE_SCANOUT_WORDS] = {0, 256, 0x260, 0xC60, 0x10, 0x100, 0x21, 0};
static t2::LedgerEntry g_ledger[4];
static t2::r4::T2FrameR4 g_fr;

int main(int argc, char **argv) {
    const char *env = getenv("PSXRECOMP_SCENE_CAPTURE");             // set by the driver for this child only
    if (!env || strcmp(env, "1") != 0) return 4;
    memcpy(g_scan, kA, sizeof g_scan);

    // ---- O: ownership and initial state (the first call binds this thread as the emulation owner) ----
    CHECK(scene_runtime_enabled() == 1);
    CHECK(scene_t2_epoch_now() == 1 && scene_t2_owner_errors_now() == 0 && scene_runtime_armed_epoch() == 0);

    // ---- A: arm binds a fresh r4 epoch (arm_epoch bumps) after both arms; the ledger takes the generation ----
    CHECK(scene_runtime_arm(5) == SCENE_OK && scene_runtime_armed_epoch() == 2 && scene_t2_epoch_now() == 2);
    SceneLedgerHeader lh0;
    memset(&lh0, 0, sizeof lh0);
    CHECK(scene_runtime_ledger_header(&lh0) == SCENE_OK && lh0.mode == LEDGER_ARMED && lh0.generation == 1);

    // ---- S: GP1 scanout, conservative glue r2 rule (the arm snapshot is the known prior state) ----
    scene_runtime_scanout_changed(kA);                               // equals the arm snapshot
    const uint64_t s1 = scene_t2_epoch_now();
    scene_runtime_scanout_changed(kB);                               // display start moved
    const uint64_t s2 = scene_t2_epoch_now();
    CHECK(s1 == 2 && s2 == 3 && scene_runtime_armed_epoch() == 2);   // the bound frame is now epoch-stale
    scene_runtime_scanout_changed(kB);                               // same-value rewrite
    const uint64_t s3 = scene_t2_epoch_now();
    scene_runtime_scanout_changed(kBmode);                           // one mode bit, same start
    const uint64_t s4 = scene_t2_epoch_now();
    CHECK(s3 == 3 && s4 == 4);
    scene_runtime_scanout_changed(nullptr);                          // ignored
    CHECK(scene_t2_epoch_now() == 4);

    // ---- N: scene_t2_build explicit-native paths ----
    CHECK(!scene_t2_build(nullptr, 4, &g_fr) && g_fr.prov_reason == t2::r4::PR_CAPTURE && g_fr.prov.bound == 0 &&
          g_fr.frame.live_eligible == 0);
    CHECK(!scene_t2_build(g_ledger, 0, &g_fr) && g_fr.prov_reason == t2::r4::PR_CAPTURE);
    CHECK(!scene_t2_build(g_ledger, 4, nullptr));
    CHECK(!scene_t2_build(g_ledger, 4, &g_fr) && g_fr.prov_reason == t2::r4::PR_CAPTURE);   // armed, not sealed
    ScenePrimitive p;
    memset(&p, 0, sizeof p);
    CHECK(scene_runtime_capture_get(0, 1, &p) == SCENE_BAD_STATE);   // not sealed

    // ---- E: an empty sealed interval (frame 6 records, frame 7 seals) ----
    scene_runtime_tick(6);
    scene_runtime_tick(7);
    SceneCaptureInfo ci;
    memset(&ci, 0, sizeof ci);
    CHECK(scene_runtime_info(&ci) == SCENE_OK && ci.mode == SCENE_SEALED && ci.complete == 1 && ci.count == 0 &&
          ci.generation == 1 && ci.owner_errors == 0);
    CHECK(!scene_t2_build(g_ledger, 4, &g_fr) && g_fr.prov_reason == t2::r4::PR_CAPTURE);   // zero records
    CHECK(scene_runtime_capture_get(0, 1, &p) == SCENE_BAD_STATE);   // index >= count
    char json[64];
    json[0] = 'x';
    CHECK(scene_runtime_json(0, 1, json, sizeof json) == SCENE_BAD_STATE && json[0] == 0);

    // ---- L: external write, cancel, re-arm, owner invalidate ----
    const uint64_t e0 = scene_t2_epoch_now();
    scene_runtime_note_external_vram_write();
    CHECK(scene_t2_epoch_now() == e0 + 1);
    CHECK(scene_runtime_cancel() == SCENE_OK && scene_runtime_armed_epoch() == 0 && scene_t2_epoch_now() == e0 + 2);
    CHECK(scene_runtime_arm(8) == SCENE_OK && scene_runtime_armed_epoch() == e0 + 3 && scene_t2_epoch_now() == e0 + 3);
    scene_runtime_invalidate();
    CHECK(scene_runtime_armed_epoch() == 0 && scene_t2_epoch_now() == e0 + 4);
    CHECK(scene_runtime_info(&ci) == SCENE_OK && ci.mode == SCENE_IDLE && ci.generation == 2);

    // ---- F: foreign threads (last) ----
    const uint64_t f0 = scene_t2_epoch_now();
    int foreign_enabled = -1;
    std::thread ta([&foreign_enabled] { foreign_enabled = scene_runtime_enabled(); });
    ta.join();
    CHECK(foreign_enabled == 0 && scene_t2_owner_errors_now() == 1 && scene_t2_epoch_now() == f0 + 1);
    std::thread tb([] { scene_runtime_invalidate(); });              // a foreign reset still bumps the epoch
    tb.join();
    CHECK(scene_t2_owner_errors_now() == 2 && scene_t2_epoch_now() == f0 + 3);
    int foreign_arm = -1;
    std::thread tc([&foreign_arm] { foreign_arm = scene_runtime_arm(9); });
    tc.join();
    CHECK(foreign_arm == SCENE_WRONG_THREAD && scene_t2_owner_errors_now() == 3 && scene_t2_epoch_now() == f0 + 4);
    uint64_t foreign_epoch = 7;
    std::thread td([&foreign_epoch] { foreign_epoch = scene_runtime_armed_epoch(); });
    td.join();
    CHECK(foreign_epoch == 0 && scene_t2_owner_errors_now() == 4);
    CHECK(scene_runtime_info(&ci) == SCENE_OK && ci.owner_errors == 4);
    CHECK(scene_runtime_arm(10) == SCENE_OK);                        // the owner can still arm ...
    scene_runtime_tick(11);
    scene_runtime_tick(12);
    CHECK(!scene_t2_build(g_ledger, 4, &g_fr) && g_fr.prov_reason == t2::r4::PR_OWNER_ERRORS);   // ... never transport

    const bool passed = g_failures == 0;
    printf("{\"fixture\":\"glue\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",
           g_checks, g_failures, passed ? "true" : "false");
    if (argc > 1) {
        FILE *f = fopen(argv[1], "wb");
        if (!f) return 3;
        fprintf(f, "{\"fixture\":\"glue\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,\"passed\":%s,"
                   "\"gl_used\":false,\"sdk_used\":false}\n", g_checks, g_failures, passed ? "true" : "false");
        if (fclose(f) != 0) return 3;
    }
    return passed ? 0 : 1;
}
