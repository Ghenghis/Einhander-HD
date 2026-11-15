/* s67 proposal fixture (NOT compiled or run yet; needs owner review and a CPU grant).
 * Compile twice from the same file:
 *   baseline:  cc -O2 -I<dir with ORIGINAL recomp_audio_drc.h>  test_rab_gap.c -lm -o base
 *   patched:   cc -O2 -DRAB_HAS_GAP -I<dir with PROPOSED header renamed recomp_audio_drc.h> test_rab_gap.c -lm -o patched
 * Each prints one JSON line per case: PCM FNV-1a hash of every pulled int16 sample, underrun_events, and (patched only) gaps.
 * Pass criteria:
 *   (1) for every case, pcm_fnv and underrun_events are IDENTICAL between base and patched (counters never change audio);
 *   (2) patched gap counters equal the expected values below, and the gap lengths sum to underrun_events since the last reset. */
#define RECOMP_AUDIO_DRC_IMPL
#include "recomp_audio_drc.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

static uint32_t fnv;
static void fnv_add(const int16_t *s, int n) {
    for (int i = 0; i < n; ++i) {
        uint16_t v = (uint16_t)s[i];
        fnv = (fnv ^ (v & 0xFF)) * 16777619u;
        fnv = (fnv ^ (v >> 8)) * 16777619u;
    }
}
static double phase;
static void push(rab_bridge *b, int frames) {            /* deterministic 440 Hz stereo tone */
    int16_t buf[2 * 4096];
    while (frames > 0) {
        int n = frames > 4096 ? 4096 : frames;
        for (int i = 0; i < n; ++i) {
            int16_t v = (int16_t)lrint(8000.0 * sin(phase)); phase += 2.0 * 3.14159265358979 * 440.0 / 44100.0;
            buf[2 * i] = v; buf[2 * i + 1] = (int16_t)-v;
        }
        rab_push(b, buf, n); frames -= n;
    }
}
static void pull(rab_bridge *b, int frames, int chunk) {  /* host callbacks of `chunk` frames */
    int16_t out[2 * 4096];
    while (frames > 0) {
        int n = frames > chunk ? chunk : frames;
        rab_pull(b, out, n); fnv_add(out, 2 * n); frames -= n;
    }
}
static void init(rab_bridge *b) {
    rab_config c; rab_config_defaults(&c);
    c.channels = 2; c.source_rate = 44100.0; c.host_rate = 48000.0;
    if (rab_init(b, &c) != 0) { printf("{\"error\":\"rab_init\"}\n"); }
    fnv = 2166136261u; phase = 0.0;
}
static void report(const char *name, rab_bridge *b) {
    rab_stats st; rab_get_stats(b, &st);
#ifdef RAB_HAS_GAP
    rab_gap_stats g; rab_get_gap_stats(b, &g);
    printf("{\"case\":\"%s\",\"pcm_fnv\":\"%08X\",\"underruns\":%llu,\"gaps\":%llu,\"max_gap\":%llu,\"cur_gap\":%llu,\"epoch\":%llu}\n",
           name, fnv, (unsigned long long)st.underrun_events, (unsigned long long)g.gaps,
           (unsigned long long)g.max_gap_frames, (unsigned long long)g.cur_gap_frames, (unsigned long long)b->gap_epoch);
#else
    printf("{\"case\":\"%s\",\"pcm_fnv\":\"%08X\",\"underruns\":%llu}\n", name, fnv, (unsigned long long)st.underrun_events);
#endif
}

int main(void) {
    rab_bridge b;
    /* prime: fill above the 180 ms target, then pull steadily while pushing */
#define PRIME() do { push(&b, 44100 / 4); pull(&b, 4800, 1024); } while (0)

    init(&b); pull(&b, 4096, 1024); report("unprimed_starvation", &b);          /* expect underruns 0, gaps 0 */
    rab_free(&b);

    init(&b); PRIME(); pull(&b, 48000, 1024); report("one_gap", &b);           /* ring drains: expect gaps 1, max_gap == underruns, cur_gap == max_gap (ongoing) */
    rab_free(&b);

    init(&b); PRIME(); pull(&b, 48000, 1024); push(&b, 44100 / 2); pull(&b, 4800, 1024);
    report("recovery", &b);                                                     /* expect gaps 1, cur_gap 0 after recovery */
    rab_free(&b);

    init(&b); PRIME();
    for (int k = 0; k < 3; ++k) { pull(&b, 48000, 1024); push(&b, 44100 / 2); pull(&b, 2400, 1024); }
    report("multiple_gaps", &b);                                                /* expect gaps 3, sum of gap lengths == underruns */
    rab_free(&b);

    init(&b); PRIME(); pull(&b, 48000, 37); report("gap_split_across_callbacks", &b); /* odd callback size: expect gaps 1 (not one per callback) */
    rab_free(&b);

    init(&b); PRIME(); pull(&b, 48000, 1024);
#ifdef RAB_HAS_GAP
    rab_reset_gap_stats(&b);                                                    /* models the unmute resync in main.cpp */
#endif
    push(&b, 44100 / 2); pull(&b, 4800, 1024); report("mute_then_unmute_reset", &b); /* expect gaps 0, epoch 1; underruns unchanged */
    rab_free(&b);

    init(&b); PRIME(); pull(&b, 48000, 1024); rab_free(&b); init(&b); report("reset_by_init", &b); /* expect all counters 0 */
    rab_free(&b);
    return 0;
}
