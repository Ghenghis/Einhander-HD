// s67 unit test for the proposed s67_pump_after_push (NOT compiled or run; needs a fresh CPU grant).
// Single-threaded, deterministic, no SDL. #includes pump_after_push.extracted.inc, the exact text of
// the helper cut from main.cpp.proposed (57f915a4...) by its unique signature line, against stubs:
// a recording audio_trace_event, the combined header's rab_telemetry, and the main.cpp globals it uses.
// What it can show: the helper's event/baseline/resync/generation/cache logic. What it cannot show:
// the trace ORDER inside the real pump, the lock placement of the snapshot, or any SDL behaviour.
// Exit 0 PASS, 1 FAIL.
#define RECOMP_AUDIO_DRC_IMPL
#include "recomp_audio_drc.h"   // combined header (rab_telemetry)
#include <cstdint>
#include <cstdio>

enum { AUDIO_EV_UNDERRUN = 4 };  // value from audio_trace.h:53
struct Ev { uint16_t kind; uint32_t a, b; };
static Ev g_ev[64];
static int g_nev = 0;
void audio_trace_event(uint16_t kind, uint32_t a, uint32_t b) { if (g_nev < 64) g_ev[g_nev++] = {kind, a, b}; }

int g_audio_unmute_resync = 0;              // bound by the helper's block-scope extern
static uint64_t      s_drc_generation = 0;
static rab_telemetry s_pump_tel;
static int           s_pump_tel_valid = 0;
static uint64_t      s_pump_tel_generation = 0;

#include "pump_after_push.extracted.inc"

static int g_fail = 0;
#define CHECK(c) do { if (!(c)) { g_fail = 1; std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)

static rab_telemetry T(uint64_t underruns, double fill) {
    rab_telemetry t{}; t.stats.underrun_events = underruns; t.stats.last_fill_ms = fill; return t;
}
static void push(uint64_t u, double fill = 100.0) {   // models: resync captured, snapshot, helper
    const int resync = g_audio_unmute_resync;
    rab_telemetry t = T(u, fill);
    s67_pump_after_push(&t, resync);
}

int main() {
    // 1. first bridge generation, no underruns: no event, cache valid for this generation
    s_drc_generation = 1;
    push(0, 120.0);
    CHECK(g_nev == 0);
    CHECK(s_pump_tel_valid == 1 && s_pump_tel_generation == 1 && s_pump_tel.stats.last_fill_ms == 120.0);

    // 2. increase -> exactly one event with the exact delta, b == 1
    push(37);
    CHECK(g_nev == 1 && g_ev[0].kind == AUDIO_EV_UNDERRUN && g_ev[0].a == 37 && g_ev[0].b == 1);

    // 3. no increase -> no event
    push(37);
    CHECK(g_nev == 1);

    // 4. resync pending (unmute): fresh snapshot becomes the baseline, flag cleared, NO event
    g_audio_unmute_resync = 1;
    push(5000);
    CHECK(g_nev == 1);
    CHECK(g_audio_unmute_resync == 0);

    // 5. after resync only the increase past the new baseline is reported
    push(5010);
    CHECK(g_nev == 2 && g_ev[1].a == 10);

    // 6. soft return: generation changes, counters restart at 0 on the new bridge.
    //    A small new count (< old baseline 5010) must still be reported, not hidden.
    s_drc_generation = 3;                     // rab_free (++), rab_init (++)
    push(12);
    CHECK(g_nev == 3 && g_ev[2].a == 12);
    CHECK(s_pump_tel_generation == 3);

    // 7. resync and generation change at the same push: baseline = fresh value, no event
    s_drc_generation = 5;
    g_audio_unmute_resync = 1;
    push(7);
    CHECK(g_nev == 3 && g_audio_unmute_resync == 0);
    push(9);
    CHECK(g_nev == 4 && g_ev[3].a == 2);

    std::printf("{\"events\":%d,\"result\":\"%s\"}\n", g_nev, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
