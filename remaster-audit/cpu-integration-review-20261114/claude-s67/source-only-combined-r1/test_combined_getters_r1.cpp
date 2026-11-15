// s67 combined-telemetry harness r1 (NOT compiled or run; needs a fresh CPU grant). r0 f8271496 kept.
// r1 adds: phase L (legacy branch with and without device), phase R (real rab_reset_gap_stats under
// the lock: mid-gap reset opens a new counted SEGMENT; base == lifetime underruns at reset), and the
// gap_epoch_base_underruns output in every comparison (identity U - base == cur within one gap).
// Binds the PROPOSED code: #includes combined_getters.extracted.inc, the exact text between the
// "s67 combined getters: BEGIN/END" markers of main.cpp.proposed (the driver re-extracts it from the
// pinned copy and byte-compares). Built against the COMBINED header (recomp_audio_drc.h.proposed).
//
// Race-free by construction: shared flags are std::atomic; lock ownership is thread_local + atomic
// holder; every bridge access after the writer starts is under the stub lock. The stub lock is a
// NON-recursive std::mutex (stricter than SDL's recursive lock): a recursive acquire is a hard failure.
// A CHECKED rab_get_telemetry (macro-substituted for the getter block only) asserts the lock is held
// by the calling thread at the moment of the copy whenever a device is open (placement, not counts).
//
// Phases (exit 0 PASS, 1 check failed, 2 setup error):
//   A  single-thread lifecycle, both old and new getters:
//      A1 not ready + no device   -> old rc 0, _ex rc 0, gap_ok 0, no lock, no checked copy
//      A2 ready + no device       -> rc 1, gap_ok 1, unlocked copy allowed (no audio thread), values exact
//      A3 ready + device          -> rc 1, gap_ok 1, exactly one lock per call, copy made WITH the lock,
//                                    old getter == _ex fields, gap getter == _ex gap fields
//   B  labelled NEGATIVE CONTROL (deterministic, single thread, no UB): torn copies built by hand on a
//      separate bridge (stats copied, writer advances 20 of 37 frames, gap copied). All three detectors
//      must fire: (D1) dU % 37 != 0 on a mid-callback copy, (D2) dU != dP, (D3) U - cur_gap != K.
//   C  concurrent positive test vs a writer thread (lock; rab_pull(37); unlock) on a drained bridge in
//      ONE continuous gap: every _ex snapshot must have (U - U0) % 37 == 0, U - cur_gap == K, gaps == 1,
//      monotonic U. Writer progress during C proven (>= 1000 pulls, >= 100 distinct U values).
//      Final (after join, under the lock): dU == dP == 37 * pulls and cur_gap - cur0 == dU.
//   Bounds: writer start 5 s, phase C 20 s, stop flag 5 s. NOTE: g_done is set before the thread has
//   actually terminated, so t.join() is NOT independently bounded here; the mandatory outer Job wall
//   limit (<= 120 s) is what bounds the whole process tree.
#define RECOMP_AUDIO_DRC_IMPL
#include "recomp_audio_drc.h"
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <thread>

typedef uint32_t SDL_AudioDeviceID;

static std::mutex g_audio_mtx;
static thread_local int t_depth = 0;
static thread_local int t_role = 0;               // 1 writer, 2 main/reader
static std::atomic<int> g_holder{0};
static std::atomic<uint64_t> g_lock_count{0}, g_copies_locked{0}, g_copies_unlocked{0};
static std::atomic<int> g_fail{0};
static void fail(const char *m) { g_fail.store(1); std::fprintf(stderr, "FAIL %s\n", m); }

void psx_sdl_audio_lock(SDL_AudioDeviceID dev) {
    if (dev == 0) fail("lock with device 0");
    if (t_depth != 0) { fail("recursive acquire"); std::fflush(stderr); std::_Exit(1); }
    g_audio_mtx.lock();
    t_depth = 1;
    if (g_holder.exchange(t_role) != 0) fail("lock not exclusive");
    g_lock_count.fetch_add(1);
}
void psx_sdl_audio_unlock(SDL_AudioDeviceID) {
    if (t_depth != 1) fail("unlock without lock");
    g_holder.store(0);
    t_depth = 0;
    g_audio_mtx.unlock();
}

// stubs for the getter block's main.cpp dependencies (main thread only after setup)
static bool g_stub_legacy = false;
static bool audio_legacy_mode(void) { return g_stub_legacy; }
extern "C" { int g_audio_host_rate = 48000; }
static rab_bridge s_drc;
static bool s_drc_ready = false;
static SDL_AudioDeviceID sdl_audio_device = 0;
static uint64_t s_drc_generation = 1;
static std::atomic<uint64_t> g_queued_calls{0};
static uint32_t psx_sdl_audio_queued_size(SDL_AudioDeviceID dev) {   // legacy branch only
    if (!g_stub_legacy && s_drc_ready) fail("queued_size reached on the bridge path");
    if (dev == 0) fail("queued_size with device 0");
    g_queued_calls.fetch_add(1);
    return 17640;                                   // = 100.0 ms at 44100 Hz * 4 bytes
}
static uint64_t g_legacy_underruns = 0;

// checked copy: placement of the copy relative to the lock
static void s67_checked_get_telemetry(const rab_bridge *b, rab_telemetry *out) {
    if (sdl_audio_device) {
        if (t_depth != 1 || g_holder.load() != t_role) fail("telemetry copied without holding the lock");
        g_copies_locked.fetch_add(1);
    } else {
        g_copies_unlocked.fetch_add(1);
    }
    rab_get_telemetry(b, out);
}
#define rab_get_telemetry s67_checked_get_telemetry
#include "combined_getters.extracted.inc"            // proposed getters, verbatim
#undef rab_get_telemetry

struct Ex { double fill, target, corr; uint64_t under, over, gaps, mx, cur, ep, base, gen; int legacy, rate, gap_ok, rc; };
static Ex query_ex() {
    Ex e{};
    e.rc = psx_audio_out_stats_ex(&e.fill, &e.target, &e.under, &e.over, &e.corr, &e.legacy, &e.rate,
                                  &e.gaps, &e.mx, &e.cur, &e.ep, &e.base, &e.gen, &e.gap_ok);
    return e;
}
static int init_bridge(rab_bridge *b) {
    rab_config c; rab_config_defaults(&c);
    c.channels = 2; c.source_rate = 44100.0; c.host_rate = 48000.0;
    return rab_init(b, &c);
}
static void prime_and_drain(rab_bridge *b) {
    int16_t buf[2 * 1024];
    for (int i = 0; i < 2 * 1024; ++i) buf[i] = (int16_t)((i * 37) & 0x3FFF);
    for (int k = 0; k < 11; ++k) rab_push(b, buf, 1024);
    int16_t out[2 * 1024];
    for (int k = 0; k < 200; ++k) rab_pull(b, out, 1024);
}
static bool same_ex(const Ex &e, const rab_telemetry &t) {
    return e.under == t.stats.underrun_events && e.over == t.stats.overflow_drops &&
           e.fill == t.stats.last_fill_ms && e.corr == t.stats.last_correction &&
           e.gaps == t.gap.gaps && e.mx == t.gap.max_gap_frames && e.cur == t.gap.cur_gap_frames &&
           e.ep == t.gap_epoch && e.base == t.gap_epoch_base_underruns && e.gen == s_drc_generation;
}

static std::atomic<int> g_started{0}, g_stop{0}, g_done{0};
static std::atomic<uint64_t> g_pulls{0};
static void writer() {
    t_role = 1;
    int16_t out[2 * 37];
    g_started.store(1);
    while (!g_stop.load()) {
        psx_sdl_audio_lock(1);
        rab_pull(&s_drc, out, 37);
        psx_sdl_audio_unlock(1);
        g_pulls.fetch_add(1);
    }
    g_done.store(1);
}
static bool wait_flag(std::atomic<int> &f, int ms) {
    auto t0 = std::chrono::steady_clock::now();
    while (!f.load()) {
        if (std::chrono::steady_clock::now() - t0 > std::chrono::milliseconds(ms)) return false;
        std::this_thread::yield();
    }
    return true;
}

int main() {
    t_role = 2;
    if (init_bridge(&s_drc) != 0) { std::fprintf(stderr, "rab_init failed\n"); return 2; }

    // ---- L legacy branch (bridge must never be touched)
    {
        g_stub_legacy = true; g_legacy_underruns = 42;
        uint64_t lc = g_lock_count.load(), cl = g_copies_locked.load(), cu = g_copies_unlocked.load();
        s_drc_ready = true; sdl_audio_device = 1;                       // L1 legacy + device
        uint64_t qc = g_queued_calls.load();
        Ex e = query_ex();
        if (e.rc != 1 || e.legacy != 1 || e.fill != 100.0 || e.target != 0.0 || e.under != 42 ||
            e.over != 0 || e.corr != 0.0 || e.gap_ok != 0 || e.gaps || e.mx || e.cur || e.ep || e.base)
            fail("L1 legacy+device values");
        if (g_queued_calls.load() != qc + 1) fail("L1 queued_size not called once");
        double f, t, c; uint64_t u, o; int l, r;
        if (psx_audio_out_stats(&f, &t, &u, &o, &c, &l, &r) != 1 || f != 100.0 || u != 42 || l != 1) fail("L1 old getter");
        uint64_t g, mx, cg, ep;
        if (psx_audio_out_gap_stats(&g, &mx, &cg, &ep) != 0 || g || mx || cg || ep) fail("L1 gap getter");
        sdl_audio_device = 0;                                           // L2 legacy + no device
        qc = g_queued_calls.load();
        e = query_ex();
        if (e.rc != 0 || e.fill != 0.0 || e.under != 42 || e.gap_ok != 0) fail("L2 legacy+no-device values");
        if (g_queued_calls.load() != qc) fail("L2 queued_size called without device");
        if (g_lock_count.load() != lc || g_copies_locked.load() != cl || g_copies_unlocked.load() != cu)
            fail("L touched the bridge or the lock");
        g_stub_legacy = false; g_legacy_underruns = 0; s_drc_ready = false;
    }

    // ---- A
    {
        s_drc_ready = false; sdl_audio_device = 0;
        uint64_t lc = g_lock_count.load(), cl = g_copies_locked.load(), cu = g_copies_unlocked.load();
        double f, t, c; uint64_t u, o; int l, r;
        if (psx_audio_out_stats(&f, &t, &u, &o, &c, &l, &r) != 0) fail("A1 old rc");
        Ex e = query_ex();
        if (e.rc != 0 || e.gap_ok != 0) fail("A1 _ex rc/gap_ok");
        if (g_lock_count.load() != lc || g_copies_locked.load() != cl || g_copies_unlocked.load() != cu) fail("A1 touched bridge");
    }
    prime_and_drain(&s_drc);
    rab_telemetry ref;
    {
        s_drc_ready = true; sdl_audio_device = 0;
        uint64_t lc = g_lock_count.load(), cu = g_copies_unlocked.load();
        Ex e = query_ex();
        rab_get_telemetry(&s_drc, &ref);
        if (e.rc != 1 || e.gap_ok != 1 || !same_ex(e, ref)) fail("A2 values");
        if (g_lock_count.load() != lc || g_copies_unlocked.load() != cu + 1) fail("A2 lock/copy");
    }
    {
        sdl_audio_device = 1;
        uint64_t lc = g_lock_count.load(), cl = g_copies_locked.load();
        Ex e = query_ex();
        rab_get_telemetry(&s_drc, &ref);
        if (e.rc != 1 || e.gap_ok != 1 || !same_ex(e, ref)) fail("A3 _ex values");
        if (g_lock_count.load() != lc + 1 || g_copies_locked.load() != cl + 1) fail("A3 lock/copy placement");
        double f, t, c; uint64_t u, o; int l, r;
        if (psx_audio_out_stats(&f, &t, &u, &o, &c, &l, &r) != 1 || u != e.under || o != e.over ||
            f != e.fill || c != e.corr || l != 0 || r != 48000) fail("A3 old getter != _ex");
        uint64_t g, mx, cg, ep;
        if (psx_audio_out_gap_stats(&g, &mx, &cg, &ep) != 1 || g != e.gaps || mx != e.mx || cg != e.cur || ep != e.ep)
            fail("A3 gap getter != _ex");
        if (g_lock_count.load() != lc + 3) fail("A3 one lock per getter call");
    }

    // ---- B negative control
    int fired = 0;
    {
        rab_bridge cb;
        if (init_bridge(&cb) != 0) return 2;
        prime_and_drain(&cb);
        int16_t out[2 * 37];
        rab_pull(&cb, out, 37);
        rab_telemetry t0; rab_get_telemetry(&cb, &t0);
        const uint64_t CU0 = t0.stats.underrun_events, CP0 = t0.stats.pulled_frames;
        const uint64_t CK = t0.stats.underrun_events - t0.gap.cur_gap_frames;
        rab_telemetry torn = t0;                      // stats copied before the "callback"
        rab_pull(&cb, out, 20);                       // callback 20 of 37 frames in
        rab_telemetry mid; rab_get_telemetry(&cb, &mid);
        torn.gap = mid.gap;                           // gap copied mid-callback
        rab_telemetry torn2 = t0; torn2.stats.underrun_events = mid.stats.underrun_events;
        if ((torn2.stats.underrun_events - CU0) % 37 != 0) fired++;                                   // D1
        if (torn2.stats.underrun_events - CU0 != torn2.stats.pulled_frames - CP0) fired++;             // D2
        if (torn.stats.underrun_events - torn.gap.cur_gap_frames != CK) fired++;                       // D3
        rab_free(&cb);
    }
    if (fired != 3) fail("negative control: a detector did not fire");

    // ---- R real gap reset controls (single thread, reset under the lock like the pump does)
    {
        Ex before = query_ex();                         // drained: one ongoing gap, epoch 0, base 0
        if (before.gaps != 1 || before.cur == 0 || before.cur != before.under || before.ep != 0 || before.base != 0)
            fail("R pre-reset state");
        psx_sdl_audio_lock(1);
        rab_reset_gap_stats(&s_drc);                    // mid-gap reset
        psx_sdl_audio_unlock(1);
        Ex r0 = query_ex();
        if (r0.under != before.under) fail("R reset touched lifetime underruns");
        if (r0.gaps != 0 || r0.mx != 0 || r0.cur != 0 || r0.ep != 1 || r0.base != before.under)
            fail("R post-reset gap state / base");
        int16_t o37[2 * 37];
        psx_sdl_audio_lock(1);
        rab_pull(&s_drc, o37, 37);                      // still starved: opens a NEW counted segment
        psx_sdl_audio_unlock(1);
        Ex r1 = query_ex();
        if (r1.gaps != 1 || r1.cur != 37 || r1.mx != 37 || r1.ep != 1) fail("R new segment counters");
        if (r1.under - r1.base != 37 || r1.under - r1.base != r1.cur) fail("R epoch identity U-base==cur");
    }

    // ---- C concurrent
    int16_t probe[2 * 37];
    rab_telemetry p0; rab_get_telemetry(&s_drc, &p0);
    rab_pull(&s_drc, probe, 37);
    rab_telemetry c0; rab_get_telemetry(&s_drc, &c0);
    if (c0.stats.underrun_events - p0.stats.underrun_events != 37 || c0.gap.gaps != 1 || c0.gap_epoch != 1) {
        std::fprintf(stderr, "setup: bridge not drained into one gap\n"); return 2;
    }
    const uint64_t U0 = c0.stats.underrun_events, P0 = c0.stats.pulled_frames, CUR0 = c0.gap.cur_gap_frames;
    const uint64_t K = U0 - CUR0;

    std::thread th(writer);
    if (!wait_flag(g_started, 5000)) { fail("writer did not start in 5 s"); std::fflush(stderr); std::_Exit(1); }
    const uint64_t READS = 200000, MIN_PULLS = 1000, MIN_DISTINCT = 100;
    const uint64_t pulls_at_start = g_pulls.load();
    uint64_t reads = 0, v37 = 0, vk = 0, vg = 0, distinct = 0, last = U0;
    auto t0 = std::chrono::steady_clock::now();
    for (;;) {
        Ex e = query_ex();
        ++reads;
        if (e.rc != 1 || e.gap_ok != 1) fail("C rc");
        if ((e.under - U0) % 37 != 0) v37++;
        if (e.under - e.cur != K) vk++;
        if (e.under - e.base != e.cur) vk++;            // r1: epoch identity within one gap
        if (e.gaps != 1) vg++;
        if (e.under < last) fail("C not monotonic");
        if (e.under != last) distinct++;
        last = e.under;
        if ((reads & 1023) == 0) std::this_thread::yield();
        if (reads >= READS && g_pulls.load() - pulls_at_start >= MIN_PULLS && distinct >= MIN_DISTINCT) break;
        if (std::chrono::steady_clock::now() - t0 > std::chrono::seconds(20)) { fail("C timeout 20 s"); break; }
    }
    const uint64_t pulls_during = g_pulls.load() - pulls_at_start;
    g_stop.store(1);
    if (!wait_flag(g_done, 5000)) { fail("writer did not stop in 5 s"); std::fflush(stderr); std::_Exit(1); }
    th.join();                                        // bounded only by the outer Job (see header note)

    psx_sdl_audio_lock(1);
    rab_telemetry fin; rab_get_telemetry(&s_drc, &fin);
    psx_sdl_audio_unlock(1);
    const uint64_t pulls_total = g_pulls.load();
    if (v37 || vk || vg) fail("C incoherent snapshot through the proposed getter");
    if (pulls_during < MIN_PULLS) fail("C writer progress below MIN_PULLS");
    if (distinct < MIN_DISTINCT) fail("C too few distinct values");
    const uint64_t dU = fin.stats.underrun_events - U0, dP = fin.stats.pulled_frames - P0;
    if (dU != dP || dP != 37ull * pulls_total) fail("final: dU/dP/pulls mismatch");
    if (fin.gap.cur_gap_frames - CUR0 != dU || fin.gap.gaps != 1) fail("final: gap does not match underruns");

    std::printf("{\"negative_controls_fired\":%d,\"reads\":%llu,\"viol_mod37\":%llu,\"viol_coherence\":%llu,"
                "\"viol_gaps\":%llu,\"distinct\":%llu,\"pulls_during_C\":%llu,\"pulls_total\":%llu,"
                "\"locked_copies\":%llu,\"result\":\"%s\"}\n",
                fired, (unsigned long long)reads, (unsigned long long)v37, (unsigned long long)vk,
                (unsigned long long)vg, (unsigned long long)distinct, (unsigned long long)pulls_during,
                (unsigned long long)pulls_total, (unsigned long long)g_copies_locked.load(),
                g_fail.load() ? "FAIL" : "PASS");
    rab_free(&s_drc);
    return g_fail.load() ? 1 : 0;
}
