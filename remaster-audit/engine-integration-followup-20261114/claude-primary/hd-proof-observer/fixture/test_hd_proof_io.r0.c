/* CPU-only fault/boundary fixture for the HD proof observer r3 I/O block (claude-einhander).
 * No GL, no game, no real files. The code under test is the exact HD-PROOF-IO block extracted by
 * build_hd_proof_io_fixture.r0.py from the pinned r3 patch applied to the pinned canonical base;
 * it is never retyped here. stdio calls in that block are redirected to fault-injecting shims.
 *
 * Usage: test-hd-proof-io.exe RESULT.json      exit 0 only when every check passed. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------- fault-injecting shims (fixture only) ---------------- */
typedef struct {
    const char *env_log;          /* value returned for PSXRECOMP_HD_PROOF_LOG */
    int getenv_calls, fopen_calls, fseek_calls, ftell_calls, fwrite_calls, fflush_calls, fclose_calls;
    int fopen_fail, fseek_fail, ftell_minus_one;
    long initial_size;
    int fwrite_fail_at; size_t fwrite_partial;   /* on that call accept only fwrite_partial bytes */
    int fflush_fail_at, fclose_fail;
    uint64_t accepted;                           /* bytes the shim accepted in total */
    char tail[512]; size_t tail_len;             /* last bytes accepted, for content oracles */
} Shim;
static Shim g;
static char g_fake_file;                         /* identity only; never dereferenced */
#define FAKE ((FILE *)(void *)&g_fake_file)

static const char *shim_getenv(const char *name) {
    ++g.getenv_calls;
    return strcmp(name, "PSXRECOMP_HD_PROOF_LOG") == 0 ? g.env_log : NULL;
}
static FILE *shim_fopen(const char *path, const char *mode) {
    ++g.fopen_calls; (void)path;
    if (strcmp(mode, "ab") != 0) return NULL;   /* the block must append */
    return g.fopen_fail ? NULL : FAKE;
}
static int shim_fseek(FILE *f, long off, int whence) {
    ++g.fseek_calls;
    return (f == FAKE && off == 0 && whence == SEEK_END && !g.fseek_fail) ? 0 : -1;
}
static long shim_ftell(FILE *f) {
    ++g.ftell_calls;
    return (f != FAKE || g.ftell_minus_one) ? -1L : g.initial_size;
}
static size_t shim_fwrite(const void *p, size_t size, size_t count, FILE *f) {
    ++g.fwrite_calls;
    if (f != FAKE || size != 1) return 0;
    size_t take = count;
    if (g.fwrite_fail_at == g.fwrite_calls && g.fwrite_partial < count) take = g.fwrite_partial;
    g.accepted += take;
    if (take >= sizeof g.tail) { memcpy(g.tail, (const char *)p + take - (sizeof g.tail - 1), sizeof g.tail - 1); g.tail_len = sizeof g.tail - 1; }
    else { memcpy(g.tail, p, take); g.tail_len = take; }
    g.tail[g.tail_len] = 0;
    return take;
}
static int shim_fflush(FILE *f) {
    ++g.fflush_calls;
    return (f == FAKE && g.fflush_fail_at != g.fflush_calls) ? 0 : EOF;
}
static int shim_fclose(FILE *f) {
    ++g.fclose_calls;
    return (f == FAKE && !g.fclose_fail) ? 0 : EOF;
}

#define getenv shim_getenv
#define fopen  shim_fopen
#define fseek  shim_fseek
#define ftell  shim_ftell
#define fwrite shim_fwrite
#define fflush shim_fflush
#define fclose shim_fclose
static uint64_t s_frame_count;
#include "hd_proof_io_extracted.inc"
#undef getenv
#undef fopen
#undef fseek
#undef ftell
#undef fwrite
#undef fflush
#undef fclose

/* Resets every static of the extracted block. The builder refuses to build if the block declares
 * any static not listed here, so a later revision cannot add state this reset misses. */
static void reset(void) {
    memset(&g, 0, sizeof g);
    s_hd_proof_file = NULL; s_hd_proof_init_done = 0; s_hd_proof_log_on = 0; s_hd_proof_capped = 0;
    s_hd_proof_open_error = 0; s_hd_proof_start_offset = -1; s_hd_proof_bytes = 0;
    s_hd_proof_write_errors = 0; s_hd_proof_dropped_lines = 0; s_hd_proof_close_errors = 0;
    s_hd_proof_epoch = 0; s_hd_proof_seen_epoch = 0; s_hd_proof_lines = 0; s_frame_count = 0;
}

static int checks, failures;
static char failed[4096];
static void check(int ok, const char *name) {
    ++checks;
    if (!ok) { ++failures; if (strlen(failed) + strlen(name) + 2 < sizeof failed) { strcat(failed, name); strcat(failed, ","); } }
}

static const char LINE[] = "{\"x\":1}\n";        /* 8 bytes */
#define LN ((int)(sizeof LINE - 1))
#define M  ((uint64_t)HD_PROOF_MARKER_BYTES)

static int open_ok(long size) {                  /* healthy open; returns observing */
    reset(); g.env_log = "C:/fixture/hd-proof.jsonl"; g.initial_size = size;
    return hd_proof_observer_on();
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;

    /* 1 unset: one getenv, one init write, no I/O, observing never starts */
    reset(); g.env_log = NULL;
    check(hd_proof_observer_on() == 0 && hd_proof_observer_on() == 0, "unset_returns_0");
    check(g.getenv_calls == 1 && g.fopen_calls == 0 && g.fwrite_calls == 0, "unset_one_getenv_no_io");
    check(s_hd_proof_init_done == 1 && s_hd_proof_open_error == 0, "unset_only_init_flag");

    /* 2 fopen failure */
    reset(); g.env_log = "p"; g.fopen_fail = 1;
    check(hd_proof_observer_on() == 0 && s_hd_proof_open_error == HD_PROOF_OPEN_FAILED, "fopen_fail_reason1");
    check(g.fwrite_calls == 0 && g.fclose_calls == 0 && s_hd_proof_file == NULL, "fopen_fail_no_io");

    /* 3 fseek failure, then 4 ftell -1, then 5 offset failure + fclose failure (reason 2 kept) */
    reset(); g.env_log = "p"; g.fseek_fail = 1;
    check(hd_proof_observer_on() == 0 && s_hd_proof_open_error == HD_PROOF_OFFSET_UNKNOWN, "fseek_fail_reason2");
    check(g.fwrite_calls == 0 && g.fclose_calls == 1 && s_hd_proof_file == NULL, "fseek_fail_closed_once_no_write");
    reset(); g.env_log = "p"; g.ftell_minus_one = 1;
    check(hd_proof_observer_on() == 0 && s_hd_proof_open_error == HD_PROOF_OFFSET_UNKNOWN && g.fwrite_calls == 0, "ftell_minus1_reason2");
    reset(); g.env_log = "p"; g.ftell_minus_one = 1; g.fclose_fail = 1;
    check(hd_proof_observer_on() == 0 && s_hd_proof_open_error == HD_PROOF_OFFSET_UNKNOWN, "offset_close_fail_keeps_reason2");
    check(s_hd_proof_close_errors == 1 && s_hd_proof_write_errors == 0 && g.fclose_calls == 1, "offset_close_fail_counted_once");

    /* 6 healthy open with a pre-existing file: offset recorded, exactly one header line */
    check(open_ok(1234) == 1 && s_hd_proof_start_offset == 1234, "open_offset_recorded");
    check(g.fopen_calls == 1 && g.fwrite_calls == 1 && s_hd_proof_lines == 1 && s_hd_proof_bytes == g.accepted, "open_one_header");
    check(strncmp(g.tail, "{\"event\":\"proof log opened\",\"schema\":\"hd-proof-receipt-v5\"", 58) == 0, "open_header_schema_v5");
    check(hd_proof_observer_on() == 1 && g.fopen_calls == 1 && g.fwrite_calls == 1, "open_idempotent");

    /* 7 line cap: MAX-3 and MAX-2 accept; MAX-1 writes the marker inside the cap and closes */
    open_ok(0); s_hd_proof_lines = HD_PROOF_MAX_LINES - 3;
    hd_proof_put(LINE, LN); check(s_hd_proof_lines == HD_PROOF_MAX_LINES - 2 && !s_hd_proof_capped, "linecap_max3_accepts");
    hd_proof_put(LINE, LN); check(s_hd_proof_lines == HD_PROOF_MAX_LINES - 1 && !s_hd_proof_capped, "linecap_max2_accepts");
    hd_proof_put(LINE, LN);
    check(s_hd_proof_lines == HD_PROOF_MAX_LINES && s_hd_proof_capped == 1, "linecap_marker_counted_at_max");
    check(strcmp(g.tail, HD_PROOF_MARKER) == 0 && s_hd_proof_file == NULL && g.fclose_calls == 1, "linecap_marker_then_closed");
    check(s_hd_proof_log_on == 1 && s_hd_proof_open_error == 0, "linecap_observing_continues");
    { const int w = g.fwrite_calls; hd_proof_put(LINE, LN); check(g.fwrite_calls == w, "linecap_no_io_after"); }

    /* 8 byte cap at MAX-M-n-1, MAX-M-n (accept) and MAX-M-n+1 (marker) */
    open_ok(0); s_hd_proof_bytes = HD_PROOF_MAX_BYTES - M - LN - 1; hd_proof_put(LINE, LN);
    check(!s_hd_proof_capped && s_hd_proof_bytes == HD_PROOF_MAX_BYTES - M - 1, "bytecap_minus1_accepts");
    open_ok(0); s_hd_proof_bytes = HD_PROOF_MAX_BYTES - M - LN; hd_proof_put(LINE, LN);
    check(!s_hd_proof_capped && s_hd_proof_bytes == HD_PROOF_MAX_BYTES - M, "bytecap_exact_accepts");
    open_ok(0); s_hd_proof_bytes = HD_PROOF_MAX_BYTES - M - LN + 1; hd_proof_put(LINE, LN);
    check(s_hd_proof_capped && s_hd_proof_bytes == HD_PROOF_MAX_BYTES - LN + 1 && s_hd_proof_bytes <= HD_PROOF_MAX_BYTES,
          "bytecap_plus1_marker_within_cap");

    /* 9 both caps at the same put: one marker, both caps exactly reached */
    open_ok(0); s_hd_proof_lines = HD_PROOF_MAX_LINES - 1; s_hd_proof_bytes = HD_PROOF_MAX_BYTES - M;
    { const int w = g.fwrite_calls; hd_proof_put(LINE, LN);
      check(g.fwrite_calls == w + 1 && s_hd_proof_lines == HD_PROOF_MAX_LINES && s_hd_proof_bytes == HD_PROOF_MAX_BYTES, "bothcaps_one_marker"); }

    /* 10 cap marker written, then fclose fails: stop reason 4, observing off, closed once */
    open_ok(0); g.fclose_fail = 1; s_hd_proof_lines = HD_PROOF_MAX_LINES - 1; hd_proof_put(LINE, LN);
    check(s_hd_proof_capped && s_hd_proof_close_errors == 1 && s_hd_proof_open_error == HD_PROOF_CLOSE_FAILED, "capclose_fail_reason4");
    check(s_hd_proof_log_on == 0 && s_hd_proof_file == NULL && g.fclose_calls == 1 && hd_proof_observer_on() == 0, "capclose_fail_stops_observing");

    /* 11 partial fwrite: accepted bytes counted, line not counted, reason 3, closed once, no I/O after */
    open_ok(0); g.fwrite_fail_at = g.fwrite_calls + 1; g.fwrite_partial = 3;
    { const uint64_t b = s_hd_proof_bytes; const unsigned l = s_hd_proof_lines; hd_proof_put(LINE, LN);
      check(s_hd_proof_bytes == b + 3 && s_hd_proof_lines == l, "partial_bytes_counted_line_not");
      check(s_hd_proof_write_errors == 1 && s_hd_proof_open_error == HD_PROOF_WRITE_FAILED && s_hd_proof_log_on == 0, "partial_reason3_stopped");
      check(s_hd_proof_file == NULL && g.fclose_calls == 1, "partial_closed_once");
      const int w = g.fwrite_calls; hd_proof_put(LINE, LN); check(g.fwrite_calls == w, "partial_no_io_after"); }

    /* 12 fflush failure; 13 fflush failure + fclose failure (reason 3 kept, both counted) */
    open_ok(0); g.fflush_fail_at = g.fflush_calls + 1;
    { const uint64_t b = s_hd_proof_bytes; hd_proof_put(LINE, LN);
      check(s_hd_proof_bytes == b + LN && s_hd_proof_open_error == HD_PROOF_WRITE_FAILED && g.fclose_calls == 1, "flush_fail_reason3"); }
    open_ok(0); g.fflush_fail_at = g.fflush_calls + 1; g.fclose_fail = 1; hd_proof_put(LINE, LN);
    check(s_hd_proof_open_error == HD_PROOF_WRITE_FAILED && s_hd_proof_write_errors == 1 && s_hd_proof_close_errors == 1, "flush_close_fail_first_reason_kept");
    check(g.fclose_calls == 1 && s_hd_proof_file == NULL, "flush_close_fail_closed_once");

    /* 14 dropped lines: n >= LINE_MAX, 0, negative; nothing written, observing continues */
    open_ok(0);
    { const int w = g.fwrite_calls; hd_proof_put(LINE, HD_PROOF_LINE_MAX); hd_proof_put(LINE, 0); hd_proof_put(LINE, -1);
      check(s_hd_proof_dropped_lines == 3 && g.fwrite_calls == w && s_hd_proof_log_on == 1 && s_hd_proof_write_errors == 0, "dropped_counted_no_io"); }

    /* 15 marker fwrite failure at the cap: reason 3, capped, closed once */
    open_ok(0); s_hd_proof_lines = HD_PROOF_MAX_LINES - 1; g.fwrite_fail_at = g.fwrite_calls + 1; g.fwrite_partial = 0;
    hd_proof_put(LINE, LN);
    check(s_hd_proof_capped && s_hd_proof_open_error == HD_PROOF_WRITE_FAILED && g.fclose_calls == 1 && s_hd_proof_log_on == 0, "marker_write_fail");

    /* 16 shim self-check: header content length equals the counted bytes of a fresh open */
    check(open_ok(0) == 1 && g.accepted == s_hd_proof_bytes && g.tail[g.tail_len - 1] == '\n', "shim_accounting_consistent");

    FILE *r = fopen(argv[1], "wb");
    if (!r) return 4;
    fprintf(r, "{\"fixture\":\"hd-proof-io\",\"revision\":\"r0\",\"observer_revision\":\"r3\",\"checks\":%d,"
               "\"failures\":%d,\"failed\":\"%s\",\"passed\":%s,\"gl_used\":false,\"real_file_io\":false}\n",
            checks, failures, failed, failures ? "false" : "true");
    fclose(r);
    return failures ? 1 : 0;
}
