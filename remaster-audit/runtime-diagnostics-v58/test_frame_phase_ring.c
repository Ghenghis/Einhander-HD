/* Host test of the ACTUAL v58 ring + query handler text, extracted from new/debug_server.c (claude-einhander).
 * CPU only, fake QPC clock. Modes: "disabled" (env unset), "unbound" (env=1, no init_owner), "main" (env=1).
 * Prints "JSON <reply>" lines for the Python runner and "FAIL ..." lines; exit code = failure count. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <windows.h>
#include "psx_bss.h"
#include "frame_phase_ring.h"

static uint64_t g_now = 1000;
uint64_t s_frame_count = 0;
static uint64_t SDL_GetPerformanceCounter(void) { return g_now; }
static uint64_t SDL_GetPerformanceFrequency(void) { return 10000000ull; }
static char g_out[1 << 20];
static void send_fmt(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vsnprintf(g_out, sizeof g_out, fmt, ap); va_end(ap); }
static void send_err(int id, const char *m) { snprintf(g_out, sizeof g_out, "{\"id\":%d,\"ok\":false,\"error\":\"%s\"}", id, m); }
static int json_get_int(const char *json, const char *key, int def) {
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\":", key);
    const char *p = strstr(json, pat);
    return p ? atoi(p + strlen(pat)) : def;
}

#include "ring_extracted.inc"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %s:%d ", __func__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void query(const char *j) { handle_frame_phase_ring(7, j); printf("JSON %s\n", g_out); }
static void at(uint64_t t, int phase) { g_now = t; debug_server_frame_phase_mark(phase); }

/* One normal offline cycle starting at t: frame increments inside housekeeping (record_frame). */
static void cycle(uint64_t t) {
    at(t, FP_ENTER);
    s_frame_count++;
    at(t + 10, FP_DEBUG_END);
    at(t + 20, FP_PACE_BEGIN);
    at(t + 50, FP_PACE_END);
    at(t + 70, FP_SWAP_BEGIN);
    at(t + 75, FP_SWAP_END);
    at(t + 80, FP_EXIT);
}

static DWORD WINAPI foreign_thread(LPVOID arg) {
    (void)arg;
    debug_server_frame_phase_mark(FP_SWAP_BEGIN);
    debug_server_frame_phase_mark(FP_SWAP_END);
    debug_server_frame_phase_mark(FP_ENTER);
    debug_server_frame_phase_mark(FP_EXIT);
    debug_server_frame_phase_mark(-1);
    return 0;
}

static void run_main(void) {
    CHECK(debug_server_frame_phase_init_owner() == 1, "init_owner");
    CHECK(debug_server_frame_phase_init_owner() == 1, "init_owner idempotent");
    FramePhaseRecord r;

    /* basic ordered cycle, frame mapping */
    s_frame_count = 5;
    cycle(1000);
    CHECK(debug_server_frame_phase_total() == 1, "total 1");
    CHECK(debug_server_frame_phase_get(0, &r), "get 0");
    CHECK(r.seq == 0 && r.frame == 6 && r.frame_at_enter == 5 && r.frame_at_swap == 6, "frames %u %u %u", r.frame, r.frame_at_enter, r.frame_at_swap);
    CHECK(r.flags == FP_FLAG_CLOSED && r.swaps == 1, "flags %u swaps %u", r.flags, r.swaps);
    const uint64_t want[FP_COUNT] = {1000, 1010, 1020, 1050, 1070, 1075, 0, 0, 1080};
    CHECK(memcmp(r.t, want, sizeof want) == 0, "stamps");

    /* first stamp wins, multi swap, alternate pacer */
    at(2000, FP_ENTER);
    s_frame_count = 20;
    at(2010, FP_DEBUG_END);
    s_frame_count = 99;
    at(2011, FP_DEBUG_END);
    at(2020, FP_SWAP_BEGIN);
    at(2025, FP_SWAP_END);
    at(2030, FP_SWAP_BEGIN);
    at(2035, FP_SWAP_END);
    at(2040, FP_ALT_PACE_BEGIN);
    at(2041, FP_ALT_PACE_BEGIN);
    at(2050, FP_ALT_PACE_END);
    at(2060, FP_EXIT);
    CHECK(debug_server_frame_phase_get(1, &r), "get 1");
    CHECK(r.frame == 20 && r.t[FP_DEBUG_END] == 2010, "debug_end first wins: frame %u t %llu", r.frame, (unsigned long long)r.t[FP_DEBUG_END]);
    CHECK(r.swaps == 2 && r.t[FP_SWAP_BEGIN] == 2020 && r.t[FP_SWAP_END] == 2025 && r.frame_at_swap == 99,
          "multi swap keeps first (frame_at_swap is s_frame_count at the first swap: 99 here)");
    CHECK(r.flags == (FP_FLAG_CLOSED | FP_FLAG_MULTI_SWAP | FP_FLAG_ALT_PACE | FP_FLAG_MULTI_ALT), "flags %u", r.flags);
    CHECK(r.t[FP_ALT_PACE_BEGIN] == 2040 && r.t[FP_ALT_PACE_END] == 2050 && r.t[FP_PACE_BEGIN] == 0, "alt stamps");

    /* orphans: owner marks outside an open cycle, invalid phases */
    at(2100, FP_SWAP_BEGIN);
    at(2101, FP_EXIT);
    debug_server_frame_phase_mark(-1);
    debug_server_frame_phase_mark(FP_COUNT);
    CHECK(s_fpr_orphans == 4, "orphans %llu", (unsigned long long)s_fpr_orphans);
    CHECK(debug_server_frame_phase_get(1, &r) && r.t[FP_EXIT] == 2060, "orphan did not touch last row");

    /* unclosed: a cycle that never exits (longjmp) */
    at(3000, FP_ENTER);
    s_frame_count++;
    at(3010, FP_DEBUG_END);
    cycle(4000);
    CHECK(debug_server_frame_phase_get(2, &r) && (r.flags & FP_FLAG_UNCLOSED) && !(r.flags & FP_FLAG_CLOSED), "unclosed flags %u", r.flags);
    CHECK(s_fpr_unclosed == 1, "unclosed count");
    CHECK(debug_server_frame_phase_get(3, &r) && r.flags == FP_FLAG_CLOSED && r.t[FP_ENTER] == 4000, "next row clean");

    /* foreign thread while a main cycle is open: no row, ring or counter change */
    at(5000, FP_ENTER);
    s_frame_count++;
    at(5010, FP_DEBUG_END);
    FramePhaseRecord before, after;
    debug_server_frame_phase_get(4, &before);
    const uint64_t tot0 = debug_server_frame_phase_total(), orph0 = s_fpr_orphans, unc0 = s_fpr_unclosed;
    const int open0 = s_fpr_open;
    g_now = 5015;
    HANDLE h = CreateThread(NULL, 0, foreign_thread, NULL, 0, NULL);
    WaitForSingleObject(h, INFINITE);
    CloseHandle(h);
    debug_server_frame_phase_get(4, &after);
    CHECK(memcmp(&before, &after, sizeof before) == 0, "foreign thread changed the open row");
    CHECK(debug_server_frame_phase_total() == tot0 && s_fpr_orphans == orph0 && s_fpr_unclosed == unc0 && s_fpr_open == open0,
          "foreign thread changed ring state");
    at(5070, FP_SWAP_BEGIN);
    at(5075, FP_SWAP_END);
    at(5080, FP_EXIT);

    /* open current row at query time (handler runs between ENTER and DEBUG_END) */
    at(6000, FP_ENTER);
    query("{\"cmd\":\"frame_phase_ring\",\"n\":2048}");
    at(6010, FP_DEBUG_END);
    at(6080, FP_EXIT);

    /* wrap: CAP=8 in this build; 20 more cycles */
    for (int i = 0; i < 20; i++) cycle(10000 + 1000 * (uint64_t)i);
    const uint64_t total = debug_server_frame_phase_total();
    CHECK(total == 26, "total %llu", (unsigned long long)total);
    CHECK(!debug_server_frame_phase_get(total - FRAME_PHASE_RING_CAP - 1, &r), "evicted row readable");
    CHECK(!debug_server_frame_phase_get(total, &r), "future row readable");
    for (uint64_t s = total - FRAME_PHASE_RING_CAP; s < total; s++)
        CHECK(debug_server_frame_phase_get(s, &r) && r.seq == s && r.t[FP_ENTER] == 10000 + 1000 * (s - 6), "wrap row %llu", (unsigned long long)s);

    /* paging and filters: the runner checks the JSON */
    query("{\"cmd\":\"frame_phase_ring\",\"n\":3}");
    query("{\"cmd\":\"frame_phase_ring\",\"from_seq\":21,\"n\":3}");
    query("{\"cmd\":\"frame_phase_ring\",\"from_seq\":24,\"n\":3}");
    query("{\"cmd\":\"frame_phase_ring\",\"from_seq\":2,\"n\":2048}");
    {   /* frame filter on the retained rows' actual frame ids */
        char j[128];
        FramePhaseRecord a, b;
        debug_server_frame_phase_get(total - 6, &a);
        debug_server_frame_phase_get(total - 4, &b);
        snprintf(j, sizeof j, "{\"cmd\":\"frame_phase_ring\",\"from_frame\":%u,\"to_frame\":%u,\"n\":2048}", a.frame, b.frame);
        query(j);
    }

    /* max-width values fit the row budget */
    for (int i = 0; i < FRAME_PHASE_RING_CAP; i++) {
        s_frame_count = 4294967295ull;
        const uint64_t big = 18446744073709551000ull + (uint64_t)i * 10;
        at(big, FP_ENTER); at(big + 1, FP_DEBUG_END); at(big + 2, FP_PACE_BEGIN); at(big + 3, FP_PACE_END);
        at(big + 4, FP_SWAP_BEGIN); at(big + 5, FP_SWAP_BEGIN); at(big + 6, FP_SWAP_END); at(big + 7, FP_ALT_PACE_BEGIN);
        at(big + 8, FP_ALT_PACE_END); at(big + 9, FP_EXIT);
    }
    query("{\"cmd\":\"frame_phase_ring\",\"n\":8}");
}

int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "main";
    if (!strcmp(mode, "main")) {
        run_main();
    } else if (!strcmp(mode, "capacity")) {   /* default-CAP build: eviction at the real 16384 boundary */
        CHECK(debug_server_frame_phase_init_owner() == 1, "init_owner");
        const uint64_t n = (uint64_t)FRAME_PHASE_RING_CAP + 5;
        for (uint64_t i = 0; i < n; i++) cycle(1000 + 100 * i);
        FramePhaseRecord r;
        CHECK(debug_server_frame_phase_total() == n, "total");
        CHECK(!debug_server_frame_phase_get(4, &r), "seq 4 should be evicted");
        CHECK(debug_server_frame_phase_get(5, &r) && r.seq == 5 && r.t[FP_ENTER] == 1000 + 500, "oldest retained");
        CHECK(debug_server_frame_phase_get(n - 1, &r) && r.seq == n - 1 && r.flags == FP_FLAG_CLOSED, "newest");
        query("{\"cmd\":\"frame_phase_ring\",\"n\":2048}");
    } else {   /* disabled or unbound: marks must leave no rows */
        if (!strcmp(mode, "disabled")) CHECK(debug_server_frame_phase_init_owner() == 0, "init_owner while disabled");
        cycle(1000);
        cycle(2000);
        CHECK(debug_server_frame_phase_total() == 0 && s_fpr_orphans == 0, "rows recorded in %s mode", mode);
        query("{\"cmd\":\"frame_phase_ring\",\"n\":16}");
    }
    printf("DONE %s fails=%d\n", mode, fails);
    return fails;
}
