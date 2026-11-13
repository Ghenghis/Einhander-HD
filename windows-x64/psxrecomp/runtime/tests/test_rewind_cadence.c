/*
 * Regression for the local-rewind movie classifier (psx_rewind.c).
 *
 * What is REAL here (compiled from the tree, not re-implemented):
 *   - the whole psx_rewind.c unit, #included verbatim from -DREWIND_UNIT
 *     (either the untouched tree file = "before", or the tree file with
 *     rewind-fmv-classifier-v2.diff applied = "after"). This gives the test
 *     direct access to the static rewind_fmv_media_active() /
 *     rewind_capture_interval() and drives the public note_frame/poll API.
 *   - mdec.c, linked as-is: MDEC colour-decode recency is produced by real
 *     DECODE commands written through mdec_write(), so mdec_recently_active()
 *     sees the runtime's own guest-cycle stamp and hysteresis.
 *   - lib/retcomm-rbengine rbe_snap_ring.c, linked as-is.
 *
 * What is STUBBED (host / emulator edges only):
 *   - gpu_display_is_depth24() and cdrom_xa_stream_active(): scripted per
 *     frame from a trace (recorded from a real run, or synthetic, as labelled).
 *   - boot_state_save_buffer_raw(): returns a tiny blob and counts calls
 *     (a call == one capture attempt that reached serialization).
 *   - IRQ snapshot-safety / dispatchability / thumbnail / OSD: trivial stubs,
 *     scriptable for the counter tests.
 *
 * Usage: test_rewind_cadence <trace-dir> [--expect-legacy]
 *   default          assert the NARROW rule (after the diff)
 *   --expect-legacy  assert the tree's current behaviour (XA alone and
 *                    depth24 alone = movie), i.e. that the defect exists
 * Exit code 0 when every assertion of the chosen mode holds.
 */
#ifndef REWIND_UNIT
#define REWIND_UNIT "../src/psx_rewind.c"
#endif
#include REWIND_UNIT

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------- stubs */
uint64_t psx_cycle_count;
uint64_t s_frame_count;
int debug_server_fmv_quiet(void) { return 0; }

static int g_depth24, g_xa;
static int g_safe_every = 1;    /* poll k is snapshot-safe iff k % every == 0 */
static uint64_t g_poll_seq;
static int g_save_fail_every;   /* 0 = never fail */
static uint64_t g_save_calls, g_save_ok;
static uint32_t g_hint_pc = 0x80010000u;

int gpu_display_is_depth24(void) { return g_depth24; }
int cdrom_xa_stream_active(void) { return g_xa; }
void cdrom_accelerate_after_savestate(void) {}
void gpu_get_display_info(GpuDisplayInfo *out)
{
    memset(out, 0, sizeof(*out));
    out->width = 320; out->height = 240; out->depth24 = g_depth24;
}
uint32_t gpu_display_pixel_argb(const GpuDisplayInfo *di, uint32_t x, uint32_t y)
{
    (void)di; return (x ^ y) & 0xFFu;
}
int psx_irq_resume_context_snapshot_safe(void)
{
    return (g_poll_seq % (uint64_t)g_safe_every) == 0u;
}
uint32_t psx_compiled_irq_resume_pc(void) { return 0u; }
uint32_t psx_last_irq_check_pc(void) { return 0u; }
void interrupts_resync_after_restore(void) {}
int psx_is_dispatchable(uint32_t pc) { return pc >= 0x80010000u && pc < 0x80200000u; }
int psx_hle_scheduler_enabled(void) { return 1; }
void psx_scheduler_resume_at(uint32_t resume_pc) { (void)resume_pc; }
int psx_netplay_active(void) { return 0; }
uint32_t psx_netplay_rb_sticky_bb_pc(void) { return 0u; }
void psx_cycles_resync_after_restore(struct CPUState *cpu) { (void)cpu; }
void psx_frontend_on_savestate_loaded(void) {}
void host_osd_push(const char *msg, int duration_ms) { (void)msg; (void)duration_ms; }
const char *host_keymap_label(HostKeymapAction action, char *out, size_t cap)
{
    (void)action; if (out && cap) out[0] = 0; return out;
}
int boot_state_save_buffer_raw(const CPUState *cpu, uint32_t bios_checksum,
                               uint32_t entry_pc, uint8_t **out_data, size_t *out_len)
{
    (void)cpu; (void)bios_checksum; (void)entry_pc;
    g_save_calls++;
    if (g_save_fail_every && (g_save_calls % (uint64_t)g_save_fail_every) == 0u)
        return 0;
    *out_data = (uint8_t *)malloc(16);
    *out_len = 16;
    memset(*out_data, 0xA5, 16);
    g_save_ok++;
    return 1;
}
int boot_state_load_buffer(const uint8_t *file, size_t file_len, uint32_t bios_checksum,
                           uint32_t entry_pc, CPUState *cpu)
{
    (void)file; (void)file_len; (void)bios_checksum; (void)entry_pc; (void)cpu;
    return 0;
}

/* ------------------------------------------------- real MDEC commands */
#define VBLANK_CYCLES 564480ull /* interrupts.c VBLANK_CYCLES (NTSC) */
#define MDEC_DATA 0x1F801820u

/* One DECODE command through the real MDEC register path.
 * depth_code: 0 = 4-bit, 1 = 8-bit (mono, texture decompression),
 *             2 = 24-bit, 3 = 15-bit (colour = video). */
static void mdec_decode_one(uint32_t depth_code)
{
    const uint32_t blocks = depth_code >= 2 ? 6u : 1u; /* Cr Cb Y0..Y3 | Y */
    uint32_t i;
    mdec_write(MDEC_DATA, (1u << 29) | (depth_code << 27) | blocks);
    for (i = 0; i < blocks; i++)
        mdec_write(MDEC_DATA, 0x0010u | (0xFE00u << 16)); /* DC=16, EOB */
}

/* ----------------------------------------------------------- traces */
enum { K_NONE = 0, K_COLOR24 = 2, K_COLOR15 = 3, K_MONO8 = 1 };
#define MAXF 20000

typedef struct Trace {
    char name[64];
    char label[160];   /* RECORDED / SYNTHETIC / RECORDED+INFERRED and why */
    int  n;            /* frames */
    int  first_frame;  /* guest frame number of index 0 (recorded) */
    unsigned char d24[MAXF], xa[MAXF], dec[MAXF], kind[MAXF];
} Trace;

typedef struct Expect {
    /* -1 = do not assert. Per-frame movie checks use [lo,hi) index ranges. */
    int movie_lo, movie_hi;      /* every frame in range must be movie */
    int plain_lo, plain_hi;      /* every frame in range must be non-movie */
    int max_movie_frames;        /* total movie frames must be <= this */
} Expect;

static Trace T;

static void trace_reset(const char *name, const char *label, int n)
{
    memset(&T, 0, sizeof(T));
    snprintf(T.name, sizeof(T.name), "%s", name);
    snprintf(T.label, sizeof(T.label), "%s", label);
    T.n = n;
}

/* Recorded trace: "<frame> <depth24|-1> <mdec_count> <xa|-1>  # ...".
 * Sample-and-hold for depth24 / xa; the MDEC count delta between two sampled
 * frames is spread evenly over the frames in between (the sampling period is
 * 15-60 frames, so the exact decode frames inside a gap are not recorded). */
static int trace_load(const char *path, const char *name, const char *label,
                      int depth24_unknown_policy /* 0: unknown->0, 1: infer */)
{
    FILE *f = fopen(path, "r");
    char line[512];
    int have = 0, pf = 0, pm = 0, d24 = 0, xa = 0, i;
    int rows_f[4096], rows_m[4096], rows_d[4096], rows_x[4096], nr = 0;
    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 0; }
    while (fgets(line, sizeof(line), f) && nr < 4096) {
        int fr, d, m, x;
        if (line[0] == '#') continue;
        if (sscanf(line, "%d %d %d %d", &fr, &d, &m, &x) != 4) continue;
        rows_f[nr] = fr; rows_d[nr] = d; rows_m[nr] = m; rows_x[nr] = x; nr++;
    }
    fclose(f);
    if (nr < 2) return 0;
    trace_reset(name, label, rows_f[nr - 1] - rows_f[0] + 1);
    if (T.n > MAXF) return 0;
    T.first_frame = rows_f[0];
    for (i = 0; i < nr; i++) {
        int idx = rows_f[i] - T.first_frame;
        if (!have) { pf = idx; pm = rows_m[i]; have = 1; }
        if (idx > pf && rows_m[i] > pm) {
            int span = idx - pf, cnt = rows_m[i] - pm, k;
            for (k = 0; k < cnt; k++) {
                int at = pf + 1 + (int)(((long long)k * span) / cnt);
                T.dec[at]++;
                T.kind[at] = K_COLOR24; /* recorded: 46080 out words / 240 MB = 24-bit */
            }
        }
        if (rows_m[i] > pm) pm = rows_m[i];
        if (idx > pf) pf = idx;
        if (rows_d[i] >= 0) d24 = rows_d[i];
        if (rows_x[i] >= 0) xa = rows_x[i];
        {
            int j, end = (i + 1 < nr) ? rows_f[i + 1] - T.first_frame : T.n;
            for (j = idx; j < end && j < T.n; j++) { T.d24[j] = (unsigned char)d24; T.xa[j] = (unsigned char)xa; }
        }
    }
    if (depth24_unknown_policy == 1) {
        /* depth24 was not polled in the boot segment. captures.json
         * ("known-hd-after-cross", another session) shows depth24=1 during
         * this same intro movie; infer it on from the first to the last
         * recorded decode frame. */
        int lo = -1, hi = -1;
        for (i = 0; i < T.n; i++) if (T.dec[i]) { if (lo < 0) lo = i; hi = i; }
        for (i = 0; i < T.n; i++) T.d24[i] = (unsigned char)(lo >= 0 && i >= lo && i <= hi);
    }
    return 1;
}

/* ----------------------------------------------------------- runner */
typedef struct Result {
    int frames, movie_frames, captures, enabled_all;
    int first_bad_movie, first_bad_plain;
    unsigned char movie[MAXF];
} Result;

static CPUState g_cpu;

static void rewind_fresh(uint32_t user_interval)
{
    psx_rewind_set_depth(50);
    psx_rewind_set_interval(user_interval);
    psx_rewind_configure(0x12345678u, 0x80010000u);
}

static void run_trace(Result *r, uint32_t user_interval, int polls_per_frame)
{
    int i, p;
    uint64_t save0;
    memset(r, 0, sizeof(*r));
    r->enabled_all = 1;
    mdec_init();
    rewind_fresh(user_interval);
    g_save_fail_every = 0; g_safe_every = 1;
    save0 = g_save_ok;
    memset(&g_cpu, 0, sizeof(g_cpu));
    g_cpu.pc = g_hint_pc;
    for (i = 0; i < T.n; i++) {
        int k;
        psx_cycle_count += VBLANK_CYCLES;
        s_frame_count++;
        for (k = 0; k < T.dec[i]; k++)
            mdec_decode_one(T.kind[i] ? T.kind[i] : K_COLOR24);
        g_depth24 = T.d24[i];
        g_xa = T.xa[i];
        r->movie[i] = (unsigned char)rewind_fmv_media_active();
        r->movie_frames += r->movie[i];
        psx_rewind_note_frame();
        r->enabled_all &= psx_rewind_enabled();
        for (p = 0; p < polls_per_frame; p++) {
            g_poll_seq++;
            psx_rewind_poll(&g_cpu, g_hint_pc);
        }
    }
    r->frames = T.n;
    r->captures = (int)(g_save_ok - save0);
}

static int g_fail, g_checks;
static void check(int ok, const char *fmt, ...)
{
    va_list ap;
    g_checks++;
    if (ok) return;
    g_fail++;
    printf("    FAIL: ");
    va_start(ap, fmt); vprintf(fmt, ap); va_end(ap);
    printf("\n");
}

static void report(const Result *r, const Expect *e, int legacy_mode, int is_negative)
{
    int i, bad_m = -1, bad_p = -1;
    if (e->movie_lo >= 0)
        for (i = e->movie_lo; i < e->movie_hi && i < r->frames; i++)
            if (!r->movie[i]) { bad_m = i; break; }
    if (e->plain_lo >= 0)
        for (i = e->plain_lo; i < e->plain_hi && i < r->frames; i++)
            if (r->movie[i]) { bad_p = i; break; }
    printf("  %-34s frames=%5d movie=%5d (%5.1f%%) captures=%4d (%.2f/s @60Hz)\n",
           T.name, r->frames, r->movie_frames,
           r->frames ? 100.0 * r->movie_frames / r->frames : 0.0,
           r->captures, r->frames ? r->captures * 60.0 / r->frames : 0.0);
    printf("    [%s]\n", T.label);
    check(r->enabled_all, "%s: rewind must stay enabled", T.name);
    if (legacy_mode && is_negative) {
        /* The defect: the tree classifies this negative case as movie. */
        check(bad_p >= 0, "%s: expected the legacy rule to misclassify (defect not reproduced)", T.name);
        return;
    }
    if (e->movie_lo >= 0)
        check(bad_m < 0, "%s: frame index %d (guest frame %d) must be movie",
              T.name, bad_m, bad_m + T.first_frame);
    if (e->plain_lo >= 0)
        check(bad_p < 0, "%s: frame index %d (guest frame %d) must be non-movie",
              T.name, bad_p, bad_p + T.first_frame);
    if (e->max_movie_frames >= 0 && !legacy_mode)
        check(r->movie_frames <= e->max_movie_frames, "%s: %d movie frames > %d",
              T.name, r->movie_frames, e->max_movie_frames);
}

/* Synthetic generators (labelled). */
static void syn_movie(const char *name, const char *label, int n, int lead, int every,
                      int kind, int d24, int xa, int gap_at, int gap_len)
{
    int i;
    trace_reset(name, label, n);
    for (i = 0; i < n; i++) {
        int in_movie = i >= lead;
        T.d24[i] = (unsigned char)(in_movie && d24);
        T.xa[i] = (unsigned char)(in_movie && xa);
        if (in_movie && ((i - lead) % every) == 0 &&
            !(gap_len && i >= gap_at && i < gap_at + gap_len)) {
            T.dec[i] = 1; T.kind[i] = (unsigned char)kind;
        }
    }
}

static int first_dec(void) { int i; for (i = 0; i < T.n; i++) if (T.dec[i]) return i; return -1; }
static int last_dec(void) { int i; for (i = T.n - 1; i >= 0; i--) if (T.dec[i]) return i; return -1; }

static void interval_matrix(int legacy_mode)
{
    /* User preference is never overridden: non-movie uses the user interval,
     * movie uses min(user, fmv) — never sparser than the user's pick. */
    static const uint32_t ivs[5] = {1u, 4u, 8u, 12u, 15u};
    int k;
    printf("  interval matrix (user -> gameplay-XA / movie):");
    for (k = 0; k < 5; k++) {
        uint32_t want_movie = ivs[k] < 4u ? ivs[k] : 4u, got_g, got_m;
        rewind_fresh(ivs[k]);
        mdec_init();
        g_depth24 = 0; g_xa = 1;               /* ordinary XA gameplay */
        got_g = rewind_capture_interval();
        psx_cycle_count += VBLANK_CYCLES;
        mdec_decode_one(K_COLOR24);            /* a movie frame just decoded */
        g_depth24 = 1;
        got_m = rewind_capture_interval();
        printf(" %u->%u/%u", ivs[k], got_g, got_m);
        check(got_m == want_movie, "movie interval for user %u = %u, want %u", ivs[k], got_m, want_movie);
        if (!legacy_mode)
            check(got_g == ivs[k], "XA-gameplay interval for user %u = %u, want %u", ivs[k], got_g, ivs[k]);
        else
            check(got_g == want_movie, "legacy: XA-gameplay interval for user %u = %u (defect expects %u)", ivs[k], got_g, want_movie);
        psx_cycle_count += 1000ull * VBLANK_CYCLES; /* let the stamp age out */
    }
    printf("\n");
}

static void mdec_sanity(void)
{
    /* The signal itself, from the real mdec.c: colour decodes stamp recency,
     * mono (texture) decodes do not, and the stamp ages out. */
    uint32_t c0;
    mdec_init();
    psx_cycle_count += 100ull * VBLANK_CYCLES;
    c0 = mdec_get_decode_count();
    mdec_decode_one(K_MONO8);
    check(mdec_get_decode_count() == c0 + 1u, "mono decode must run (count)");
    check(!mdec_recently_active(8), "mono (8-bit) decode must not stamp video recency");
    mdec_decode_one(K_COLOR24);
    check(mdec_get_decode_count() == c0 + 2u, "colour decode must run (count)");
    check(mdec_recently_active(8), "24-bit colour decode must stamp video recency");
    psx_cycle_count += 6ull * VBLANK_CYCLES;
    check(!mdec_recently_active(8),
          "mdec_recently_active(8) spans 8*338688+169344 cycles ~= 5.1 vblanks, not 8");
    psx_cycle_count += 100ull * VBLANK_CYCLES;
}

#if defined(WITH_REWIND_STATS)
static void counters_test(void)
{
    /* The counter diff: every do_capture entry is accounted for exactly once,
     * taken == serialized+stored captures, and the reasons add up. */
    PsxRewindStats s;
    int i, p;
    uint64_t save0, calls0;
    printf("  counters (rewind-stats-counters.diff):\n");
    mdec_init();
    rewind_fresh(15u);
    psx_rewind_stats_reset();
    g_safe_every = 37;     /* most polls look like dirty-RAM pump sites */
    g_save_fail_every = 5; /* every 5th serialization fails */
    save0 = g_save_ok; calls0 = g_save_calls;
    memset(&g_cpu, 0, sizeof(g_cpu));
    for (i = 0; i < 1200; i++) {
        psx_cycle_count += VBLANK_CYCLES;
        g_depth24 = 0; g_xa = 1;
        psx_rewind_note_frame();
        for (p = 0; p < 6; p++) {
            g_poll_seq++;
            /* every 4th frame: no resolvable dispatchable resume PC at all */
            g_cpu.pc = (i % 4 == 3) ? 0u : g_hint_pc;
            psx_rewind_poll(&g_cpu, (i % 4 == 3) ? 0u : g_hint_pc);
        }
    }
    psx_rewind_stats_get(&s);
    printf("    frames=%llu media=%llu due_edges=%llu due_frames=%llu attempts=%llu "
           "unsafe=%llu pc=%llu save=%llu store=%llu taken=%llu lat_max=%llu count=%u\n",
           (unsigned long long)s.frames, (unsigned long long)s.media_frames,
           (unsigned long long)s.due_edges, (unsigned long long)s.due_frames,
           (unsigned long long)s.attempts, (unsigned long long)s.skip_unsafe,
           (unsigned long long)s.skip_pc, (unsigned long long)s.skip_save,
           (unsigned long long)s.skip_store, (unsigned long long)s.taken,
           (unsigned long long)s.latency_frames_max, s.count);
    check(s.frames == 1200u, "frames counted %llu", (unsigned long long)s.frames);
    check(s.taken == g_save_ok - save0, "taken %llu != stored blobs %llu",
          (unsigned long long)s.taken, (unsigned long long)(g_save_ok - save0));
    check(s.skip_save == (g_save_calls - calls0) - (g_save_ok - save0),
          "skip_save %llu != failed serializations", (unsigned long long)s.skip_save);
    check(s.attempts == s.taken + s.skip_no_ring + s.skip_unsafe + s.skip_pc +
                        s.skip_save + s.skip_store,
          "attempts do not add up");
    check(s.skip_unsafe > 0 && s.skip_pc > 0 && s.skip_save > 0, "every refusal path exercised");
    check(s.due_edges == s.taken + (uint64_t)(s.capture_due ? 1 : 0),
          "one request per stored capture (+1 if pending)");
    check(s.count == (s.taken < 50u ? (uint32_t)s.taken : 50u), "ring count %u", s.count);
    check(s.effective_interval == s.interval || s.effective_interval == s.fmv_interval,
          "effective interval reported");
    check(s.save_us_total <= s.capture_us_total, "save time is part of capture time");
    g_safe_every = 1; g_save_fail_every = 0;
}
#endif

int main(int argc, char **argv)
{
    const char *dir = argc > 1 ? argv[1] : "traces";
    int legacy = (argc > 2 && strcmp(argv[2], "--expect-legacy") == 0);
    char path[1024];
    Result *r = (Result *)calloc(1, sizeof(Result));
    Expect e;
    int fd, ld;

    printf("unit: %s\nmode: %s\n", REWIND_UNIT,
           legacy ? "expect LEGACY rule (defect present)" : "expect NARROW movie rule");

    mdec_sanity();
    interval_matrix(legacy);

    /* 1. RECORDED negative: ordinary stage-1 gameplay with XA BGM. */
    snprintf(path, sizeof(path), "%s/rec_stage1_gameplay_xa.trace", dir);
    if (!trace_load(path, "rec_stage1_gameplay_xa",
                    "RECORDED normal2-rewind-on-v2: fmv_state+gpu_state, 120 s after City gate",
                    0)) { printf("missing %s\n", path); return 2; }
    run_trace(r, 15u, 4);
    e.movie_lo = -1; e.plain_lo = 0; e.plain_hi = T.n; e.max_movie_frames = 0;
    report(r, &e, legacy, 1);
    if (!legacy)
        check(r->captures * 15 >= r->frames - 15 && r->captures * 15 <= r->frames + 15,
              "gameplay captures %d should be frames/15 (%d)", r->captures, r->frames / 15);

    /* 2. RECORDED positive: the intro movie (XA + 24-bit MDEC), skipped by
     *    the harness after 21 decodes. depth24 inferred (not polled). */
    snprintf(path, sizeof(path), "%s/rec_boot_intro_movie.trace", dir);
    if (!trace_load(path, "rec_boot_intro_movie",
                    "RECORDED mdec+xa (pacing-boot-observation+fmv_state); depth24 INFERRED", 1))
        { printf("missing %s\n", path); return 2; }
    fd = first_dec(); ld = last_dec();
    run_trace(r, 15u, 4);
    e.movie_lo = fd; e.movie_hi = ld + 1;
    e.plain_lo = ld + 40; e.plain_hi = T.n; e.max_movie_frames = -1;
    report(r, &e, legacy, 0);

    /* 3. SYNTHETIC positive: full intro at the recorded cadence (1 decode /
     *    2 frames, 24-bit, XA, depth24) for 30 s — density must be kept. */
    syn_movie("syn_intro_xa_24bit_30s",
              "SYNTHETIC: recorded intro cadence extended to 30 s", 1800 + 30, 30, 2,
              K_COLOR24, 1, 1, 0, 0);
    run_trace(r, 15u, 4);
    e.movie_lo = 30; e.movie_hi = T.n; e.plain_lo = -1; e.max_movie_frames = -1;
    report(r, &e, legacy, 0);
    check(r->captures * 4 >= (T.n - 30) - 8, "movie density: %d captures over %d frames",
          r->captures, T.n - 30);

    /* 4. SYNTHETIC positive: silent 24-bit movie at 15 fps (no XA). */
    syn_movie("syn_silent_movie_24bit_15fps", "SYNTHETIC: MDEC every 4 frames, no XA",
              900, 10, 4, K_COLOR24, 1, 0, 0, 0);
    run_trace(r, 15u, 4);
    e.movie_lo = 10; e.movie_hi = T.n; e.plain_lo = -1; e.max_movie_frames = -1;
    report(r, &e, legacy, 0);

    /* 5. SYNTHETIC positive: 15-bit movie (depth24 off), silent. */
    syn_movie("syn_silent_movie_15bit", "SYNTHETIC: 15-bit colour MDEC every 2 frames, depth24 off",
              600, 10, 2, K_COLOR15, 0, 0, 0, 0);
    run_trace(r, 15u, 4);
    e.movie_lo = 10; e.movie_hi = T.n; e.plain_lo = -1; e.max_movie_frames = -1;
    report(r, &e, legacy, 0);

    /* 6. SYNTHETIC positive: 24-bit movie with XA and a 30-frame CD stall. */
    syn_movie("syn_movie_24bit_cd_stall30", "SYNTHETIC: 30-frame decode gap inside a 24-bit movie",
              900, 10, 2, K_COLOR24, 1, 1, 400, 30);
    run_trace(r, 15u, 4);
    e.movie_lo = 10; e.movie_hi = T.n; e.plain_lo = -1; e.max_movie_frames = -1;
    report(r, &e, legacy, 0);

    /* 7. SYNTHETIC negative: 24-bpp still/menu, no MDEC, no XA. */
    syn_movie("syn_still_24bpp_no_mdec", "SYNTHETIC: depth24 on, no MDEC decode, no XA",
              600, 0, 1, K_COLOR24, 1, 0, 0, 600);
    run_trace(r, 15u, 4);
    e.movie_lo = -1; e.plain_lo = 0; e.plain_hi = T.n; e.max_movie_frames = 0;
    report(r, &e, legacy, 1);

    /* 8. SYNTHETIC negative: 24-bpp still with XA music (audio-only scene). */
    syn_movie("syn_still_24bpp_xa_no_mdec", "SYNTHETIC: depth24 on + XA, no MDEC decode",
              600, 0, 1, K_COLOR24, 1, 1, 0, 600);
    run_trace(r, 15u, 4);
    e.movie_lo = -1; e.plain_lo = 0; e.plain_hi = T.n; e.max_movie_frames = 0;
    report(r, &e, legacy, 1);

    /* 9. SYNTHETIC negative after hold: one MDEC-decoded 24-bpp still. */
    syn_movie("syn_mdec_oneshot_still_24bpp", "SYNTHETIC: one 24-bit decode, then a static 24-bpp screen",
              600, 0, 100000, K_COLOR24, 1, 0, 0, 0);
    run_trace(r, 15u, 4);
    e.movie_lo = -1; e.plain_lo = 40; e.plain_hi = T.n; e.max_movie_frames = 37;
    report(r, &e, legacy, 1);

    /* 10. SYNTHETIC negative: XA gameplay with 8-bit MDEC texture decodes. */
    syn_movie("syn_gameplay_xa_mono_mdec", "SYNTHETIC: XA on, depth24 off, 8-bit MDEC every 30 frames",
              900, 0, 30, K_MONO8, 0, 1, 0, 0);
    run_trace(r, 15u, 4);
    e.movie_lo = -1; e.plain_lo = 0; e.plain_hi = T.n; e.max_movie_frames = 0;
    report(r, &e, legacy, 1);

    /* Informational (no assertion): 120-frame stall inside a 24-bit movie. */
    syn_movie("info_movie_24bit_cd_stall120", "SYNTHETIC (informational): 120-frame decode gap",
              900, 10, 2, K_COLOR24, 1, 1, 400, 120);
    run_trace(r, 15u, 4);
    printf("  %-34s frames=%5d movie=%5d captures=%4d  (gap frames 400..519)\n",
           T.name, r->frames, r->movie_frames, r->captures);

#if defined(WITH_REWIND_STATS)
    counters_test();
#endif

    free(r);
    printf("%s: %d/%d checks passed\n", g_fail ? "FAILED" : "PASSED", g_checks - g_fail, g_checks);
    return g_fail ? 1 : 0;
}
