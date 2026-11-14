/* s67 audio gap-counter fixture r3 (supersedes r2 and r1, both kept unchanged).
 * r3 change vs r2: mute_then_unmute_reset now resets WHILE in a gap and pulls 100 starved
 * frames before any refill (catches a reset that forgets in_gap). All else identical to r2.
 * NOT compiled or run yet: needs a fresh CPU grant after the host-freeze hold lifts.
 * Built twice from this one file by run_rab_gap_r3.py:
 *   base:    -I<dir holding the ORIGINAL  recomp_audio_drc.h>
 *   patched: -I<dir holding the PROPOSED  recomp_audio_drc.h>  -DRAB_HAS_GAP
 * Usage: test_rab_gap_r3 <existing_output_dir>
 *   Writes <dir>/<case>.pcm (raw int16 little-endian interleaved stereo, every pulled sample)
 *   and prints one JSON line per case with the old counter (underrun_events) at every mark.
 *   Exit code: 0 only if every check passed; 1 on any failed check; 2 on usage/IO/init error.
 * Acceptance is decided by the host driver, not by this exit code alone:
 *   (A) every check below passes in both builds;
 *   (B) for every case, the .pcm bytes (SHA-256) are identical between base and patched;
 *   (C) for every case, the old-counter marks are identical between base and patched.
 *
 * Structural oracles (why the expected values are exact without pre-computing frame counts):
 *   - The bridge has no re-prime: once primed, a frame is starved exactly when the source frame
 *     it needs has not been pushed. With NO push during a drain, starvation is therefore one
 *     contiguous run until the next push, so gaps==1 and cur==max==(old-counter delta) exactly.
 *   - After pushing 200 ms and pulling at most 100 ms of host time, no frame starves, so the old
 *     counter must not move and the gap must be closed (cur==0).
 *   - Gap counters are epoch-local: "sum of gap lengths == underrun_events - snapshot taken at the
 *     last reset". underrun_events itself is lifetime-cumulative and is never reset. */
#define RECOMP_AUDIO_DRC_IMPL
#include "recomp_audio_drc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef unsigned long long ull;

static int g_fail = 0;
static FILE *g_pcm = NULL;
static double g_phase = 0.0;
static ull g_marks[16];
static int g_nmarks = 0;
static const char *g_case = "";

#define CHECK(cond) do { if (!(cond)) { g_fail = 1; \
    fprintf(stderr, "FAIL case=%s line=%d: %s\n", g_case, __LINE__, #cond); } } while (0)

static ull U(const rab_bridge *b) { rab_stats st; rab_get_stats(b, &st); return (ull)st.underrun_events; }
static void mark(const rab_bridge *b) { if (g_nmarks < 16) g_marks[g_nmarks++] = U(b); }

static void push(rab_bridge *b, int frames) {           /* deterministic 440 Hz stereo tone */
    int16_t buf[2 * 4096];
    while (frames > 0) {
        int n = frames > 4096 ? 4096 : frames;
        for (int i = 0; i < n; ++i) {
            int16_t v = (int16_t)lrint(8000.0 * sin(g_phase));
            g_phase += 2.0 * 3.14159265358979323846 * 440.0 / 44100.0;
            buf[2 * i] = v; buf[2 * i + 1] = (int16_t)-v;
        }
        rab_push(b, buf, n); frames -= n;
    }
}
static void pull(rab_bridge *b, int frames, int chunk) { /* host callbacks of `chunk` frames */
    int16_t out[2 * 4096];
    while (frames > 0) {
        int n = frames > chunk ? chunk : frames;
        rab_pull(b, out, n);
        for (int i = 0; i < 2 * n; ++i) {                /* explicit little-endian bytes */
            uint16_t v = (uint16_t)out[i];
            unsigned char le[2] = { (unsigned char)(v & 0xFF), (unsigned char)(v >> 8) };
            if (fwrite(le, 1, 2, g_pcm) != 2) { fprintf(stderr, "IO error\n"); exit(2); }
        }
        frames -= n;
    }
}
static void begin(rab_bridge *b, const char *dir, const char *name) {
    char path[1024];
    g_case = name; g_nmarks = 0; g_phase = 0.0;
    snprintf(path, sizeof path, "%s/%s.pcm", dir, name);
    g_pcm = fopen(path, "wb");
    if (!g_pcm) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    rab_config c; rab_config_defaults(&c);
    c.channels = 2; c.source_rate = 44100.0; c.host_rate = 48000.0;
    int rc = rab_init(b, &c);
    if (rc != 0) { fprintf(stderr, "rab_init failed rc=%d case=%s\n", rc, name); exit(2); }
}
#ifdef RAB_HAS_GAP
static rab_gap_stats G(const rab_bridge *b) { rab_gap_stats g; rab_get_gap_stats(b, &g); return g; }
#define GAPS_EQ(b, n, mx, cu, ep) do { rab_gap_stats g_ = G(b); \
    CHECK(g_.gaps == (uint64_t)(n)); CHECK(g_.max_gap_frames == (uint64_t)(mx)); \
    CHECK(g_.cur_gap_frames == (uint64_t)(cu)); CHECK((b)->gap_epoch == (uint64_t)(ep)); } while (0)
#else
#define GAPS_EQ(b, n, mx, cu, ep) do { } while (0)
#endif
static void end(rab_bridge *b) {
    printf("{\"case\":\"%s\",\"build\":\"%s\",\"marks\":[", g_case,
#ifdef RAB_HAS_GAP
           "patched"
#else
           "base"
#endif
    );
    for (int i = 0; i < g_nmarks; ++i) printf("%s%llu", i ? "," : "", g_marks[i]);
    printf("]");
#ifdef RAB_HAS_GAP
    { rab_gap_stats g = G(b);
      printf(",\"gaps\":%llu,\"max_gap\":%llu,\"cur_gap\":%llu,\"epoch\":%llu",
             (ull)g.gaps, (ull)g.max_gap_frames, (ull)g.cur_gap_frames, (ull)b->gap_epoch); }
#endif
    printf("}\n");
    fclose(g_pcm); g_pcm = NULL;
    rab_free(b);
}

/* prime: 250 ms pushed (>= 180 ms target, < 280 ms ring), then 100 ms pulled: never starves */
static void prime(rab_bridge *b) { push(b, 44100 / 4); pull(b, 4800, 1024); }
/* drain: 1 s of host frames with no push; the ~150 ms left in the ring runs out mid-way */
static void drain(rab_bridge *b, int chunk) { pull(b, 48000, chunk); }
/* refill: 200 ms pushed, then <= 100 ms pulled: never starves */
static void refill(rab_bridge *b, int host_frames) { push(b, 44100 / 5); pull(b, host_frames, 1024); }

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: %s <existing_output_dir>\n", argv[0]); return 2; }
    const char *dir = argv[1];
    rab_bridge b;

    /* 1. unprimed_starvation: pulls before any push are not underruns and not gaps */
    begin(&b, dir, "unprimed_starvation");
    pull(&b, 4096, 1024); mark(&b);
    CHECK(g_marks[0] == 0);
    GAPS_EQ(&b, 0, 0, 0, 0);
    end(&b);

    /* 2. one_gap: one contiguous drain, gap still in progress at the end */
    begin(&b, dir, "one_gap");
    prime(&b); mark(&b);                       /* m0 == 0 */
    drain(&b, 1024); mark(&b);                 /* m1 == L > 0 */
    CHECK(g_marks[0] == 0);
    CHECK(g_marks[1] > 0 && g_marks[1] < 48000);
    GAPS_EQ(&b, 1, g_marks[1], g_marks[1], 0); /* ongoing: cur == max == L */
    end(&b);

    /* 3. recovery: gap closes on the first delivered frame; old counter stops moving */
    begin(&b, dir, "recovery");
    prime(&b); drain(&b, 1024); mark(&b);      /* m0 == L */
    refill(&b, 4800); mark(&b);                /* m1 == L */
    CHECK(g_marks[0] > 0);
    CHECK(g_marks[1] == g_marks[0]);
    GAPS_EQ(&b, 1, g_marks[0], 0, 0);
    end(&b);

    /* 4. multiple_gaps: exactly 3 gaps separated by delivered audio */
    begin(&b, dir, "multiple_gaps");
    prime(&b); mark(&b);                       /* m0 == 0 */
    for (int k = 0; k < 3; ++k) {
        drain(&b, 1024); mark(&b);             /* m1, m3, m5 */
        refill(&b, 2400); mark(&b);            /* m2, m4, m6: unchanged */
    }
    {
        ull L1 = g_marks[1] - g_marks[0], L2 = g_marks[3] - g_marks[2], L3 = g_marks[5] - g_marks[4];
        ull mx = L1 > L2 ? L1 : L2; if (L3 > mx) mx = L3;
        CHECK(g_marks[0] == 0);
        CHECK(L1 > 0 && L2 > 0 && L3 > 0);
        CHECK(g_marks[2] == g_marks[1] && g_marks[4] == g_marks[3] && g_marks[6] == g_marks[5]);
        CHECK(L1 + L2 + L3 == g_marks[6]);    /* no reset in this case: since-reset == lifetime */
        GAPS_EQ(&b, 3, mx, 0, 0);
    }
    end(&b);

    /* 5. gap_split_across_callbacks: one contiguous gap over many 37-frame callbacks is ONE gap */
    begin(&b, dir, "gap_split_across_callbacks");
    prime(&b); mark(&b);                       /* m0 == 0 */
    drain(&b, 37); mark(&b);                   /* m1 == L, spans > 2 callbacks */
    CHECK(g_marks[0] == 0);
    CHECK(g_marks[1] > 2 * 37 && g_marks[1] < 48000);
    GAPS_EQ(&b, 1, g_marks[1], g_marks[1], 0);
    end(&b);

    /* 6. mute_then_unmute_reset: reset models main.cpp's unmute resync.
     *    Old counter keeps its pre-reset lifetime value; gap counters restart at epoch 1;
     *    after the reset, gap lengths sum to (old counter - snapshot taken at the reset). */
    begin(&b, dir, "mute_then_unmute_reset");
    prime(&b); drain(&b, 1024); mark(&b);      /* m0 == Lpre > 0 (one gap, epoch 0) */
    GAPS_EQ(&b, 1, g_marks[0], g_marks[0], 0);
#ifdef RAB_HAS_GAP
    rab_reset_gap_stats(&b);
#endif
    mark(&b);                                  /* m1 == m0: reset never touches the old counter */
    GAPS_EQ(&b, 0, 0, 0, 1);
    /* r3: the reset happened WHILE in a gap. Pull 100 more frames with NO push: the ring is
     * still empty, so all 100 are starved and must open ONE new gap of epoch 1. A mutant
     * reset that forgets to clear in_gap would leave gaps==0 here (r2 hid this behind a refill). */
    pull(&b, 100, 1024); mark(&b);             /* m2 == m1 + 100 */
    CHECK(g_marks[2] - g_marks[1] == 100);
    GAPS_EQ(&b, 1, 100, 100, 1);
    refill(&b, 4800); mark(&b);                /* m3 == m2: recovered, gap closed */
    CHECK(g_marks[3] == g_marks[2]);
    GAPS_EQ(&b, 1, 100, 0, 1);
    drain(&b, 1024); mark(&b);                 /* m4 == m3 + Lpost */
    {
        ull Lpost = g_marks[4] - g_marks[3];
        ull mx = Lpost > 100 ? Lpost : 100;
        CHECK(g_marks[0] > 0);
        CHECK(g_marks[1] == g_marks[0]);
        CHECK(Lpost > 0);
        CHECK(100 + Lpost == g_marks[4] - g_marks[1]); /* since-reset identity: snapshot m1, not lifetime */
        GAPS_EQ(&b, 2, mx, Lpost, 1);
    }
    end(&b);

    /* 7. reset_by_init: rab_init zeroes everything, including the old counter and epoch */
    begin(&b, dir, "reset_by_init");
    prime(&b); drain(&b, 1024); mark(&b);      /* m0 > 0 before re-init */
    CHECK(g_marks[0] > 0);
    GAPS_EQ(&b, 1, g_marks[0], g_marks[0], 0);
    {
        rab_free(&b);
        rab_config c; rab_config_defaults(&c);
        c.channels = 2; c.source_rate = 44100.0; c.host_rate = 48000.0;
        int rc = rab_init(&b, &c);
        if (rc != 0) { fprintf(stderr, "re-init failed rc=%d\n", rc); return 2; }
    }
    mark(&b);                                  /* m1 == 0 */
    CHECK(g_marks[1] == 0);
    GAPS_EQ(&b, 0, 0, 0, 0);
    end(&b);

    if (g_fail) { fprintf(stderr, "RESULT FAIL\n"); return 1; }
    fprintf(stderr, "RESULT PASS\n");
    return 0;
}
