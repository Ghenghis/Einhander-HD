/* PRIVATE glue r3 bridge TU (claude-einhander, source-only proposal; root msg_b02d1bcc / msg_08008ad5 /
 * msg_2fe98abb, design 19db18ce). It wires the T2 r6 owned present lifecycle into the runtime:
 *  - producer (emulation owner) at each sealed generation, in this order:
 *      1. boundary;
 *      2. an invalid seal retires everything and bumps the epoch (decision 3; also a body open at the seal);
 *      3. the frame binds only if a pool slot is free AND nothing is pending, so a bound candidate always reaches
 *         the consumer;
 *      4. copy the sealed generation's own records (scene_runtime_capture_get) and export the ledger;
 *      5. SealedScanout from the PresentState snapshot and ledger r3. The target start is the constant drawing
 *         area origin; the target size is the ONE displayed area of the interval (native halfwords), whose start
 *         must equal the PresentState's current scanout start. 24-bit, interlaced and 480-line modes are not
 *         qualified and stay native (root msg_08008ad5);
 *      6. r6::build with the r4 ledger policy (unchanged, still required) and the ledger r1 display-hazard hook;
 *      7. r6 bind, then publish into a private pool of kFrames immutable frames (decision 4). A published or taken
 *         frame is never rebuilt or overwritten;
 *  - every GP0 command: the ledger r3 pure footprint goes to PresentState::note_write; unknown retires all;
 *  - GP1: PresentState::observe_scanout; arm: prime + capture_begin (no bump); reference mode on request.
 * pgxp.h must be the comment-only DERIVED copy (50a6ef6d) wherever this TU is built with -Wall -Werror. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>
#include <stdint.h>
#include <string.h>
#include "scene_capture.h"
#define FLAG_DIV_OVF (1u << 17)
#include "gte_divide_extracted.inc"
#include "remix_t1_reproject.r1.h"
#include "remix_t2.r3.h"
#include "remix_t2.r4.h"
#include "remix_t2.r6.h"
#include "scene_ledger.r3.h"
#include "scene_ledger_t2.r0.h"
#include "scene_runtime.h"
#include "scene_t2_bridge.r3.h"

namespace {
using t2::r6::T2FrameR6;
constexpr uint32_t kModeVres = 1u << 3, kModeDepth24 = 1u << 5, kModeInterlace = 1u << 6;   // gpu.c :5142-5143
constexpr uint32_t kFrames = 4;
enum : uint32_t { FS_FREE = 0, FS_BUILDING, FS_PUBLISHED, FS_TAKEN };

t2::r4::T2Liveness g_liveness;
t2::r6::PresentState g_present;
ScenePrimitive g_prims[t2::kMaxPrims];     // owner only
t2::LedgerEntry g_ledger[t2::kMaxLedger];  // owner only
SceneT2Audit g_audit;                      // owner only
T2FrameR6 g_frames[kFrames];               // the private pool: written only in FS_BUILDING by the owner
std::atomic<uint32_t> g_frame_state[kFrames];
std::atomic<T2FrameR6 *> g_pending{nullptr};

// r4 policy hook (as glue r2): the sealed ledger must still name this frame/generation, then the r0 VRAM policy.
uint32_t ledger_policy(void *, uint32_t frame, uint32_t generation, const uint32_t *ordinals, uint32_t count) {
    SceneLedgerHeader h;
    memset(&h, 0, sizeof h);
    if (scene_runtime_ledger_header(&h) != SCENE_OK || !h.complete || h.frame != frame || h.generation != generation)
        return LP_NATIVE_INCOMPLETE;
    SceneLedgerVerdict v;
    memset(&v, 0, sizeof v);
    if (scene_runtime_ledger_policy(generation, ordinals, count, &v) != SCENE_OK) return LP_NATIVE_INCOMPLETE;
    return v.verdict;
}
// r6 display-hazard hook: the same header check, then ledger r1 scene_ledger_display_hazard on the exact set.
uint32_t display_hazard(void *, uint32_t frame, uint32_t generation, const uint32_t *ordinals, uint32_t count,
                        const int32_t rect[4]) {
    SceneLedgerHeader h;
    memset(&h, 0, sizeof h);
    if (scene_runtime_ledger_header(&h) != SCENE_OK || !h.complete || h.frame != frame || h.generation != generation)
        return LP_NATIVE_INCOMPLETE;
    SceneLedgerVerdict v;
    memset(&v, 0, sizeof v);
    if (scene_runtime_ledger_display_hazard(generation, ordinals, count, rect, &v) != SCENE_OK) return LP_NATIVE_INCOMPLETE;
    return v.verdict;
}
const t2::r4::PolicyHook kPolicy{ledger_policy, nullptr};
const t2::r6::DisplayHazardHook kHazard{display_hazard, nullptr};

// SealedBinding from owner-only state (glue r2): capture info, ledger header, armed epoch. Outputs zeroed first.
bool sealed_binding(SceneCaptureInfo *info, t2::r4::SealedBinding *b) {
    memset(info, 0, sizeof *info);
    memset(b, 0, sizeof *b);
    SceneLedgerHeader h;
    memset(&h, 0, sizeof h);
    if (scene_runtime_info(info) != SCENE_OK || scene_runtime_ledger_header(&h) != SCENE_OK) return false;
    const uint64_t epoch = scene_runtime_armed_epoch();
    if (!epoch) return false;
    *b = t2::r4::SealedBinding{info->frame, info->generation, h.command_count, epoch,
                               static_cast<uint8_t>(info->mode == SCENE_SEALED ? 1 : 0), info->complete, h.sealed,
                               h.complete};
    return true;
}
// SealedScanout of the sealed generation: exact sealed scanout state, constant draw area, the one displayed area.
bool sealed_scanout(uint32_t generation, t2::r6::SealedScanout *ss) {
    memset(ss, 0, sizeof *ss);
    const t2::r6::PresentSnapshot &o = g_present.owner_snapshot();
    if (!o.scanout_generation) return false;                                     // never observed
    if (o.scanout.w[6] & (kModeVres | kModeDepth24 | kModeInterlace)) return false;   // not qualified: native
    uint32_t constant = 0;
    uint16_t area[4] = {0, 0, 0, 0};
    if (scene_runtime_ledger_draw_area(generation, &constant, area) != SCENE_OK || constant != 1) return false;
    SceneLedgerHeader h;
    memset(&h, 0, sizeof h);
    if (scene_runtime_ledger_header(&h) != SCENE_OK || h.generation != generation || h.display_count != 1) return false;
    const LedgerRect &d = h.display[0];
    if (uint32_t(d.x0) != o.scanout.w[0] || uint32_t(d.y0) != o.scanout.w[1] || d.x1 <= d.x0 || d.y1 <= d.y0)
        return false;                                                            // two sources disagree: native
    ss->boundary = o.scanout;
    ss->boundary_generation = o.scanout_generation;
    ss->target = o.scanout;
    ss->target.w[0] = area[0];
    ss->target.w[1] = area[1];
    ss->target_rect[0] = area[0];
    ss->target_rect[1] = area[1];
    ss->target_rect[2] = d.x1 - d.x0;
    ss->target_rect[3] = d.y1 - d.y0;
    ss->draw_area_constant = 1;
    ss->draw_left = area[0];
    ss->draw_top = area[1];
    ss->draw_right = area[2];
    ss->draw_bottom = area[3];
    return true;
}
int free_frame() {
    for (uint32_t i = 0; i < kFrames; ++i)
        if (g_frame_state[i].load(std::memory_order_acquire) == FS_FREE) return int(i);
    return -1;
}
}  // namespace

extern "C" uint64_t scene_t2_arm_epoch(void) { return g_liveness.arm_epoch(); }
extern "C" void scene_t2_invalidate(void) { g_liveness.invalidate(); }
extern "C" void scene_t2_note_foreign(void) { g_liveness.note_foreign(); }
extern "C" uint64_t scene_t2_epoch_now(void) { return g_liveness.epoch_now(); }
extern "C" uint64_t scene_t2_owner_errors_now(void) { return g_liveness.owner_errors_now(); }

extern "C" uint64_t scene_t2_capture_begin(int owner_healthy) {
    uint64_t e = 0;
    return t2::r6::capture_begin(g_liveness, owner_healthy != 0, &e) ? e : 0;
}
extern "C" void scene_t2_observe_scanout(const uint32_t s[8]) {
    if (!s) return;
    t2::r6::ScanoutState st;
    memcpy(st.w, s, sizeof st.w);
    g_present.observe_scanout(st, g_liveness);
}
extern "C" void scene_t2_prime_scanout(const uint32_t s[8]) {
    if (g_present.owner_snapshot().scanout_generation != 0) return;
    scene_t2_observe_scanout(s);
}
extern "C" void scene_t2_note_command(const uint32_t *words, int count, const SceneLedgerState *state) {
    LedgerRect d[SCENE_LEDGER_MAX_PIECES];
    uint32_t pieces = 0, known = 0;
    if (scene_ledger_footprint(words, count, state, d, &pieces, &known) != LEDGER_OK || known != 1) {
        const int32_t any[4] = {0, 0, 1, 1};
        g_present.note_write(any, false);                                        // unknown: retire everything
        return;
    }
    for (uint32_t i = 0; i < pieces && i < uint32_t(SCENE_LEDGER_MAX_PIECES); ++i) {
        const int32_t r[4] = {d[i].x0, d[i].y0, d[i].x1 - d[i].x0, d[i].y1 - d[i].y0};
        g_present.note_write(r, true);
    }
}
extern "C" void scene_t2_retire_all(void) { g_present.invalidate_all(g_liveness, t2::r6::T2R_INVALIDATED); }
extern "C" void scene_t2_set_reference(int on) { g_present.set_reference_mode(on != 0); }

extern "C" void scene_t2_on_seal(uint32_t invalid) {
    ++g_audit.seals;
    g_present.boundary(g_liveness);                                              // the declared boundary first
    if (invalid) {
        ++g_audit.invalid_seals;
        g_audit.last_invalid = invalid;
        g_present.invalidate_all(g_liveness, t2::r6::T2R_INVALIDATED);
        return;
    }
    const int slot = free_frame();
    if (slot < 0 || g_pending.load(std::memory_order_acquire) != nullptr) {      // the consumer could not receive it
        ++g_audit.busy;
        return;
    }
    g_frame_state[slot].store(FS_BUILDING, std::memory_order_relaxed);
    T2FrameR6 *f = &g_frames[slot];
    SceneCaptureInfo info;
    t2::r4::SealedBinding b;
    t2::LedgerHeader lh;
    t2::r6::SealedScanout ss;
    memset(&info, 0, sizeof info);
    memset(&b, 0, sizeof b);
    memset(&lh, 0, sizeof lh);
    memset(&ss, 0, sizeof ss);
    uint32_t n = 0, count = 0;
    bool ok = sealed_binding(&info, &b);
    if (ok && (info.count == 0 || info.count > t2::kMaxPrims)) ok = false;
    for (uint32_t i = 0; ok && i < info.count; ++i) ok = scene_runtime_capture_get(i, b.generation, &g_prims[i]) == SCENE_OK;
    if (ok) count = info.count;
    if (ok && !scene_ledger_export_t2(GetCurrentThreadId(), b.generation, &lh, g_ledger, t2::kMaxLedger, &n)) ok = false;
    if (ok && !sealed_scanout(b.generation, &ss)) {
        ++g_audit.refused_scanout;
        ok = false;
    }
    if (!ok) {                                                                   // explicit native
        memset(&b, 0, sizeof b);
        memset(&lh, 0, sizeof lh);
        memset(&ss, 0, sizeof ss);
        n = 0;
        count = 0;
    }
    t2::r6::build(g_prims, count, &info, b, &lh, g_ledger, n, &kPolicy, g_liveness, ss, &kHazard, f);
    ++g_audit.built;
    g_audit.last_scan_reason = f->scan_reason;
    const t2::r6::BindReason br = g_present.bind(g_liveness, f);
    g_audit.last_bind_reason = br;
    if (br != t2::r6::T2B_OK) {
        g_frame_state[slot].store(FS_FREE, std::memory_order_release);
        return;
    }
    ++g_audit.bound;
    g_frame_state[slot].store(FS_PUBLISHED, std::memory_order_release);
    T2FrameR6 *expected = nullptr;
    if (!g_pending.compare_exchange_strong(expected, f, std::memory_order_acq_rel)) {   // only the owner publishes
        g_frame_state[slot].store(FS_FREE, std::memory_order_release);
        ++g_audit.busy;
        return;
    }
    ++g_audit.published;
}

const T2FrameR6 *scene_t2_take(void) {
    T2FrameR6 *f = g_pending.exchange(nullptr, std::memory_order_acq_rel);
    if (f) g_frame_state[f - g_frames].store(FS_TAKEN, std::memory_order_release);
    return f;
}
void scene_t2_release(const T2FrameR6 *frame) {
    for (uint32_t i = 0; i < kFrames; ++i) {
        if (frame != &g_frames[i]) continue;
        uint32_t expected = FS_TAKEN;
        g_frame_state[i].compare_exchange_strong(expected, FS_FREE, std::memory_order_acq_rel);   // a taken frame only
        return;
    }
}
bool scene_t2_gate(const T2FrameR6 *frame, uint64_t expected_overlay_hash, const t2::r6::CompletionR6 *c) {
    return frame && t2::r6::gate_allow_suppress(*frame, expected_overlay_hash, c, g_liveness, g_present);
}
bool scene_t2_scanout_now(uint64_t *generation, uint32_t s[8]) {
    t2::r6::PresentSnapshot snap;
    if (!generation || !s || !g_present.read(&snap)) return false;
    *generation = snap.scanout_generation;
    memcpy(s, snap.scanout.w, sizeof snap.scanout.w);
    return true;
}
const t2::r4::T2Liveness &scene_t2_liveness() { return g_liveness; }
const t2::r6::PresentState &scene_t2_present() { return g_present; }
const SceneT2Audit &scene_t2_audit() { return g_audit; }
