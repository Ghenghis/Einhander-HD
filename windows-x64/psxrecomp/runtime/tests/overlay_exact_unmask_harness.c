/* Real-loader regression harness: an exact, CRC-matching manifested lazy entry
 * (E = 0x80026714) must not be masked forever by a broader, still diff-gated
 * CPS range owner (H = 0x800262B0) in differential mode.
 *
 * This file links against the REAL runtime/src/overlay_loader.c (unmodified
 * tree, or a patched copy) plus overlay_path_canon.c, overlay_posix.c and
 * crc32.c. Everything else the loader needs is stubbed here exactly in the
 * style of runtime/tests/overlay_pair_dedup_harness.c. The shards are real DLLs
 * (overlay_exact_unmask_fixture.c) in a synthetic, namespaced cache that the
 * loader scans, indexes lazily and LoadLibrary's itself.
 *
 * Usage:
 *   harness leaf
 *       print the cache leaf "gcc/<arch-abi>/cg<ver>_<hash>_gc<cfg>_f<flavor>"
 *   harness <cache-root> <case> <code.bin> <H-dll-name> <E-dll-name>
 *       run one case and print key=value metrics on stdout.
 *
 * The case script (all cases):
 *   A. dispatch the H bundle's sibling root 0x8002673C once. This publishes the
 *      H bundle through its own exact entry without calling 0x800262B0 and
 *      without giving it any differential pass (as observed live: the owner is
 *      loaded but its root is rarely or never dispatched).
 *   B. case-specific owner history:
 *        N2: dispatch H's root once while the interpreter stub diverges, so the
 *            real shadow diff marks H device_touch=1 (the only runtime path that
 *            sets it);
 *        N5: dispatch H's root 32 times cleanly, so H reaches
 *            OVERLAY_DIFF_BUDGET (32) passes.
 *   C. arm overlay_cps_probe at the target and dispatch it 64 times:
 *        0x80026714 (exact orphan entry E) for every case except
 *        N4: 0x80026720 (a non-exact CPS continuation inside H).
 *
 * try_load_region() is static; it is counted through its first observable
 * side effect: overlay_loads_allowed() -> psx_netplay_is_resimulating(), which
 * the loader calls exactly once per try_load_region() (rescan/live publication
 * also call it, but this harness performs neither). */
#include "overlay_loader.h"
#include "overlay_api.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#define RAM_SIZE (2u * 1024u * 1024u)

#define GAME_ID   "MASK-TEST"
#define H_ENTRY   0x800262B0u   /* broad CPS owner, R 800262B0 48C            */
#define F2_ENTRY  0x8002673Cu   /* H bundle sibling root, R 8002673C 68        */
#define E_ENTRY   0x80026714u   /* exact orphan fragment, R 80026714 28        */
#define N4_ENTRY  0x80026720u   /* non-exact continuation inside H (and E)     */
#define CODE_BASE 0x000262B0u   /* code.bin covers [0x262B0, 0x267A4)          */
#define CODE_SIZE 0x000004F4u
#define TEST_RA   0x80031000u   /* return address distinct from every entry    */
#define TEST_SEED 0xC0DE0000u   /* must match overlay_exact_unmask_fixture.c   */
#define EDGES     64

/* Loader entry points that are deliberately not in overlay_loader.h. */
void overlay_loader_cps_probe_set(uint32_t pc);
void overlay_loader_cps_probe_get(uint32_t *pc, uint64_t *cnt, uint32_t *found,
                                  int *ci, int *nrange, int *matched,
                                  int *outcome, int *ncand);
int overlay_loader_dump_candidates_at(uint32_t addr, char *out, int cap);
const char *overlay_loader_arch_abi(void);
extern int g_psx_cps_mode;

/* ---- Runtime state and stubs (pattern of overlay_pair_dedup_harness.c) --- */

static uint8_t s_ram[RAM_SIZE];
static uint8_t s_scratch[1024];

uint32_t g_debug_current_func_addr;
uint32_t g_debug_last_store_pc;
/* A dirty boot-text capture window, as in the live run: the region is below
 * the overlay floor and is inside the cache window only because its pages are
 * dirty (overlay_cache_window_contains -> dirty_ram_is_dirty). */
uint32_t g_overlay_region_floor = 0x00098000u;
uint32_t i_stat, i_mask;
int g_exec_phase;
int g_idle_note_suppress;
uint32_t g_dirty_ram_code_gen;
uint64_t s_frame_count;
int g_shadow_mmio_watch;
uint64_t g_shadow_mmio_hits;

/* The existing pair-dedup harness defines `int g_psx_call_bail;` while the
 * loader is compiled with -DPSX_OVERLAY_DLL_BUILD. cpu_state.h then maps that
 * name to (*g_psx_call_bail_p), so its definition silently becomes a NULL
 * pointer -- harmless there (no shadow diff runs) but a NULL dereference in
 * run_shadow_diff. Provide real storage behind the pointers instead. */
#ifdef PSX_OVERLAY_DLL_BUILD
static int s_call_bail_storage;
static uint64_t s_bail_first_storage, s_bail_resolved_storage;
int *g_psx_call_bail_p = &s_call_bail_storage;
uint64_t *g_psx_bail_first_p = &s_bail_first_storage;
uint64_t *g_psx_bail_resolved_p = &s_bail_resolved_storage;
#else
int g_psx_call_bail;
uint64_t g_psx_bail_first, g_psx_bail_resolved;
#endif

/* Harness observation counters. */
static uint64_t s_try_load_region_calls;  /* via psx_netplay_is_resimulating */
static uint64_t s_walkback_words;         /* dirty_ram_get_bitmap_word calls */
static uint64_t s_interp_calls;           /* dirty_ram_dispatch (shadow interp) */
static uint64_t s_interp_e, s_interp_h, s_interp_f2, s_interp_other;
static int      s_diverge_root;           /* N2: interp disagrees with H root */

static int page_dirty(uint32_t page) { return page >= 0x11u && page <= 0x27u; }

uint8_t *memory_get_ram_ptr(void) { return s_ram; }
uint8_t *memory_get_scratchpad_ptr(void) { return s_scratch; }
uint32_t overlay_watch_pagegen_sum(uint32_t phys, uint32_t len) {
    (void)phys; (void)len; return 0;
}
void overlay_watch_set_range(uint32_t phys, uint32_t len) {
    (void)phys; (void)len;
}
void ds_init(const char *cache_dir, const char *game_id) {
    (void)cache_dir; (void)game_id;
}
uint32_t dirty_ram_get_bitmap_word(uint32_t word) {
    uint32_t bits = 0;
    s_walkback_words++;
    for (uint32_t b = 0; b < 32u; b++)
        if (page_dirty(word * 32u + b)) bits |= 1u << b;
    return bits;
}
int dirty_ram_is_dirty(uint32_t phys) {
    return page_dirty((phys & 0x1FFFFFFFu) >> 12);
}
/* The interpreter oracle for the shadow diff: the same architectural effect as
 * the fixture's native body ($v0 = seed ^ phys(entry), pc = return address). */
int dirty_ram_dispatch(CPUState *cpu, uint32_t addr, uint32_t stop) {
    uint32_t phys = addr & 0x1FFFFFFFu;
    s_interp_calls++;
    if (phys == (E_ENTRY & 0x1FFFFFFFu)) s_interp_e++;
    else if (phys == (H_ENTRY & 0x1FFFFFFFu)) s_interp_h++;
    else if (phys == (F2_ENTRY & 0x1FFFFFFFu)) s_interp_f2++;
    else s_interp_other++;
    cpu->gpr[2] = TEST_SEED ^ phys;
    if (s_diverge_root && phys == (H_ENTRY & 0x1FFFFFFFu)) cpu->gpr[2] ^= 1u;
    cpu->pc = stop;
    return 1;
}
void dirty_ram_xprobe_call_note(CPUState *cpu, uint32_t target,
                                uint32_t ra, uint8_t phase) {
    (void)cpu; (void)target; (void)ra; (void)phase;
}

int psx_netplay_is_resimulating(void) {
    s_try_load_region_calls++;
    return 0;
}

void psx_dispatch_call(CPUState *cpu, uint32_t addr, uint32_t ra) {
    (void)cpu; (void)addr; (void)ra;
}
void psx_check_interrupts(CPUState *cpu) { (void)cpu; }
void psx_check_interrupts_at(CPUState *cpu, uint32_t pc) {
    (void)cpu; (void)pc;
}
int psx_interrupt_delivery_needed(const CPUState *cpu) { (void)cpu; return 0; }
int psx_get_in_exception(void) { return 0; }
uint64_t psx_exception_setjmp_epoch(void) { return 0; }
void psx_restore_state_escape(void) {}
void psx_rfe_mark_escape(void) {}
int psx_syscall(CPUState *cpu, uint32_t code) {
    (void)cpu; (void)code; return 0;
}
void psx_unknown_dispatch(CPUState *cpu, uint32_t addr, uint32_t phys) {
    (void)cpu; (void)addr; (void)phys;
}

void psx_advance_cycles(uint32_t cycles) { (void)cycles; }
uint64_t psx_get_cycle_count(void) { return 0; }
int psx_cycle_replay_begin(uint64_t cycle) { (void)cycle; return 1; }
uint64_t psx_cycle_replay_end(void) { return 0; }
uint32_t psx_cyc_load_word(CPUState *cpu, uint32_t addr, uint32_t rt,
                           uint32_t mask) {
    (void)cpu; (void)addr; (void)rt; (void)mask; return 0;
}
uint32_t psx_cyc_load_word_slow(CPUState *cpu, uint32_t addr, uint32_t rt,
                                uint32_t mask) {
    return psx_cyc_load_word(cpu, addr, rt, mask);
}
uint16_t psx_cyc_load_half(CPUState *cpu, uint32_t addr, uint32_t rt,
                           uint32_t mask) {
    (void)cpu; (void)addr; (void)rt; (void)mask; return 0;
}
uint16_t psx_cyc_load_half_slow(CPUState *cpu, uint32_t addr, uint32_t rt,
                                uint32_t mask) {
    return psx_cyc_load_half(cpu, addr, rt, mask);
}
uint8_t psx_cyc_load_byte(CPUState *cpu, uint32_t addr, uint32_t rt,
                          uint32_t mask) {
    (void)cpu; (void)addr; (void)rt; (void)mask; return 0;
}
uint32_t psx_cyc_lwc2_read(CPUState *cpu, uint32_t addr) {
    (void)cpu; (void)addr; return 0;
}
int psx_icache_shadow_record_begin(void) { return 1; }
int psx_icache_shadow_replay_begin(void) { return 1; }
void psx_icache_shadow_replay_end(void) {}
void psx_icache_shadow_abort(void) {}
void psx_icache_fetch(CPUState *cpu, uint32_t addr) { (void)cpu; (void)addr; }
void psx_icache_fetch_fn(CPUState *cpu, uint32_t addr) {
    psx_icache_fetch(cpu, addr);
}
void psx_muldiv_set(CPUState *cpu, uint32_t latency) {
    (void)cpu; (void)latency;
}
void psx_muldiv_stall(CPUState *cpu) { (void)cpu; }
uint32_t psx_mult_latency_s(uint32_t rs) { (void)rs; return 1; }
uint32_t psx_mult_latency_u(uint32_t rs) { (void)rs; return 1; }
void psx_gte_stall(CPUState *cpu) { (void)cpu; }
void psx_gte_read(CPUState *cpu, uint32_t rt) { (void)cpu; (void)rt; }
int psx_slice_block(CPUState *cpu, uint32_t addr, uint32_t cycles,
                    int side_effects) {
    (void)cpu; (void)addr; (void)cycles; (void)side_effects; return 0;
}
int psx_slice_block_impl(CPUState *cpu, uint32_t addr, uint32_t cycles,
                         int side_effects) {
    return psx_slice_block(cpu, addr, cycles, side_effects);
}

void gte_execute(CPUState *cpu, uint32_t cmd) { (void)cpu; (void)cmd; }
uint32_t gte_read_data(CPUState *cpu, uint8_t reg) {
    (void)cpu; (void)reg; return 0;
}
uint32_t gte_read_ctrl(CPUState *cpu, uint8_t reg) {
    (void)cpu; (void)reg; return 0;
}
void gte_write_data(CPUState *cpu, uint8_t reg, uint32_t val) {
    (void)cpu; (void)reg; (void)val;
}
void gte_write_ctrl(CPUState *cpu, uint8_t reg, uint32_t val) {
    (void)cpu; (void)reg; (void)val;
}
int32_t psx_ws_plane_nx(int32_t nx) { return nx; }
uint32_t psx_ws_xclip_bound(uint32_t vanilla) { return vanilla; }
uint32_t psx_ws_cull_keep_result(uint32_t vanilla, uint32_t forced) {
    (void)forced; return vanilla;
}
uint32_t psx_ws_aspect_cone_result(uint32_t site, uint32_t vanilla,
                                   uint32_t object, int32_t x, int32_t z,
                                   int32_t y) {
    (void)site; (void)object; (void)x; (void)z; (void)y; return vanilla;
}
uint32_t psx_ws_angle_widen(uint32_t vanilla) { return vanilla; }
void gte_precision_store_word(uint32_t addr, uint8_t reg) {
    (void)addr; (void)reg;
}
void gte_precision_speculative_begin(void) {}
void gte_precision_speculative_end(void) {}
int gte_replay_side_effects_begin(void) { return 1; }
void gte_replay_side_effects_end(void) {}

void psx_pgxp_load(struct CPUState *cpu, uint32_t instr, uint32_t addr,
                   uint32_t value) {
    (void)cpu; (void)instr; (void)addr; (void)value;
}
void psx_pgxp_store(struct CPUState *cpu, uint32_t instr, uint32_t addr,
                    uint32_t value) {
    (void)cpu; (void)instr; (void)addr; (void)value;
}
void psx_pgxp_alu(struct CPUState *cpu, uint32_t instr, uint32_t result,
                  uint32_t s1, uint32_t s2) {
    (void)cpu; (void)instr; (void)result; (void)s1; (void)s2;
}
void psx_pgxp_muldiv(struct CPUState *cpu, uint32_t instr, uint32_t hi,
                     uint32_t lo, uint32_t s1, uint32_t s2) {
    (void)cpu; (void)instr; (void)hi; (void)lo; (void)s1; (void)s2;
}
void psx_pgxp_cop2(struct CPUState *cpu, uint32_t instr, uint32_t value,
                   uint32_t addr) {
    (void)cpu; (void)instr; (void)value; (void)addr;
}

int ls_shadow_record_begin(void) { return 1; }
int ls_shadow_record_end(uint32_t *ops, int *exc) {
    if (ops) *ops = 0;
    if (exc) *exc = 0;
    return 1;
}
int ls_shadow_replay_begin(void) { return 1; }
int ls_shadow_replay_end(uint32_t *ops, int *kind, uint32_t *pc,
                         uint32_t *addr, uint32_t *expected,
                         uint32_t *actual) {
    (void)ops; (void)kind; (void)pc; (void)addr; (void)expected; (void)actual;
    return 1;
}
void ls_shadow_abort(void) {}

int psx_ws_backdrop_x(int x) { return x; }
int psx_ws_x_margin(void) { return 0; }
void psx_ws_sprite_tag(CPUState *cpu) { (void)cpu; }
uint32_t psx_ws_backdrop_value(uint32_t orig, int end, int cols) {
    (void)end; (void)cols; return orig;
}
int32_t psx_ws_depth_bound(int32_t imm) { return imm; }
int32_t psx_ws_player_x_bound(int32_t vanilla) { return vanilla; }

/* ---- Fixture introspection (only modules the loader itself loaded) ------- */

typedef int (*CountFn)(void);
typedef int (*IndexFn)(int);
typedef uint32_t (*PcFn)(int);

typedef struct {
    int loaded;
    int init;
    int calls0, calls1;
    uint32_t last_pc0;
} FixtureView;

static FixtureView fixture_view(const char *path) {
    FixtureView v;
    memset(&v, 0, sizeof v);
#ifdef _WIN32
    HMODULE h = GetModuleHandleA(path);   /* never maps a fresh copy */
    if (!h) return v;
    CountFn init = (CountFn)GetProcAddress(h, "test_init_count");
    IndexFn calls = (IndexFn)GetProcAddress(h, "test_calls");
    PcFn last = (PcFn)GetProcAddress(h, "test_last_pc");
#else
#ifndef RTLD_NOLOAD
#error "fixture introspection requires RTLD_NOLOAD"
#endif
    void *h = dlopen(path, RTLD_NOW | RTLD_NOLOAD);
    if (!h) return v;
    CountFn init = (CountFn)dlsym(h, "test_init_count");
    IndexFn calls = (IndexFn)dlsym(h, "test_calls");
    PcFn last = (PcFn)dlsym(h, "test_last_pc");
#endif
    v.loaded = 1;
    v.init = init ? init() : -1;
    v.calls0 = calls ? calls(0) : -1;
    v.calls1 = calls ? calls(1) : -1;
    v.last_pc0 = last ? last(0) : 0;
#ifndef _WIN32
    dlclose(h);
#endif
    return v;
}

/* ---- Loader introspection ------------------------------------------------ */

typedef struct {
    int count;            /* candidates registered at exactly this entry */
    int state;
    int diff_passes;
    int device_touch;
} CandView;

static int json_int(const char *obj, const char *key, int fallback) {
    char needle[64];
    snprintf(needle, sizeof needle, "\"%s\":", key);
    const char *p = strstr(obj, needle);
    if (!p) return fallback;
    return atoi(p + strlen(needle));
}

static CandView cand_view(uint32_t addr) {
    static char buf[8192];
    CandView v = {0, -1, -1, -1};
    overlay_loader_dump_candidates_at(addr, buf, (int)sizeof buf);
    for (const char *p = buf; (p = strstr(p, "\"index\":")) != NULL; p++)
        v.count++;
    if (v.count > 0) {
        v.state = json_int(buf, "state", -1);
        v.diff_passes = json_int(buf, "diff_passes", -1);
        v.device_touch = json_int(buf, "device_touch", -1);
    }
    return v;
}

static uint32_t loader_loads(void) {
    uint32_t loads = 0;
    overlay_loader_get_counters(&loads, NULL, NULL, NULL, NULL, NULL,
                                NULL, NULL, NULL, NULL, NULL);
    return loads;
}

static uint64_t shadow_calls(void) {
    uint64_t calls = 0;
    overlay_loader_get_shadow_summary(&calls, NULL, NULL);
    return calls;
}

static uint64_t shadow_divs(void) {
    uint64_t divs = 0;
    overlay_loader_get_shadow_summary(NULL, &divs, NULL);
    return divs;
}

/* One guest dispatch, as the interpreter would issue it: pc = target. */
typedef struct { int ret1, ret0, result_ok; } EdgeTally;

static void dispatch_once(uint32_t addr, EdgeTally *tally) {
    CPUState cpu;
    memset(&cpu, 0, sizeof cpu);
    cpu.gpr[29] = 0x801FFF00u;
    cpu.gpr[31] = TEST_RA;
    cpu.pc = addr;
    int r = overlay_loader_dispatch(&cpu, addr);
    if (!tally) return;
    if (r) {
        tally->ret1++;
        /* Native, CPS-native and shadow (interp-result) completions must all
         * leave the architecturally expected state. */
        if (cpu.gpr[2] == (TEST_SEED ^ (addr & 0x1FFFFFFFu)) && cpu.pc == TEST_RA)
            tally->result_ok++;
    } else {
        tally->ret0++;
    }
}

static int load_code(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return 0; }
    size_t got = fread(s_ram + CODE_BASE, 1, CODE_SIZE, f);
    int extra = fgetc(f);
    fclose(f);
    if (got != CODE_SIZE || extra != EOF) {
        fprintf(stderr, "%s: expected exactly %u bytes\n", path, CODE_SIZE);
        return 0;
    }
    return 1;
}

static void print_cand(const char *prefix, CandView v) {
    printf("%s_cands=%d\n%s_state=%d\n%s_diff_passes=%d\n%s_device_touch=%d\n",
           prefix, v.count, prefix, v.state, prefix, v.diff_passes,
           prefix, v.device_touch);
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "leaf") == 0) {
        printf("gcc/%s/cg%d_%08x_gc%08x_f%u\n", overlay_loader_arch_abi(),
               PSX_OVERLAY_CODEGEN_VER, (unsigned)PSX_OVERLAY_CODEGEN_HASH,
               0u, (unsigned)PSX_OVERLAY_FLAVOR);
        return 0;
    }
    if (argc != 6) {
        fprintf(stderr,
                "usage: %s leaf\n"
                "       %s <cache-root> <case> <code.bin> <H-dll> <E-dll>\n",
                argv[0], argv[0]);
        return 2;
    }
    const char *cache = argv[1];
    const char *name = argv[2];
    char leaf[256], h_path[1024], e_path[1024];
    snprintf(leaf, sizeof leaf, "gcc/%s/cg%d_%08x_gc%08x_f%u",
             overlay_loader_arch_abi(), PSX_OVERLAY_CODEGEN_VER,
             (unsigned)PSX_OVERLAY_CODEGEN_HASH, 0u,
             (unsigned)PSX_OVERLAY_FLAVOR);
    /* Same string the loader builds ("%s/%s/gcc/...", then "%s/%s"). */
    snprintf(h_path, sizeof h_path, "%s/%s/%s/%s", cache, GAME_ID, leaf, argv[4]);
    snprintf(e_path, sizeof e_path, "%s/%s/%s/%s", cache, GAME_ID, leaf, argv[5]);

    int is_n2 = strcmp(name, "N2") == 0;
    int is_n4 = strcmp(name, "N4") == 0;
    int is_n5 = strcmp(name, "N5") == 0;
    uint32_t target = is_n4 ? N4_ENTRY : E_ENTRY;

    memset(s_ram, 0, sizeof s_ram);
    if (!load_code(argv[3])) return 3;
    g_psx_cps_mode = 1;
    overlay_loader_init(cache, GAME_ID, 0);

    /* A. publish the H bundle through its sibling root only. */
    EdgeTally setup = {0, 0, 0};
    dispatch_once(F2_ENTRY, &setup);
    /* B. owner history. */
    if (is_n2) {
        s_diverge_root = 1;
        dispatch_once(H_ENTRY, &setup);
        s_diverge_root = 0;
    } else if (is_n5) {
        for (int i = 0; i < 32; i++) dispatch_once(H_ENTRY, &setup);
    }

    CandView pre_h = cand_view(H_ENTRY);
    CandView pre_e = cand_view(E_ENTRY);
    uint64_t tlr0 = s_try_load_region_calls;
    uint32_t loads0 = loader_loads();
    uint64_t shadow0 = shadow_calls();
    uint64_t interp_e0 = s_interp_e;
    uint64_t interp_h0 = s_interp_h;
    FixtureView pre_hf = fixture_view(h_path);

    /* C. the measured phase. */
    overlay_loader_cps_probe_set(target);
    EdgeTally phase = {0, 0, 0};
    for (int i = 0; i < EDGES; i++) dispatch_once(target, &phase);

    CandView h = cand_view(H_ENTRY);
    CandView e = cand_view(E_ENTRY);
    FixtureView hf = fixture_view(h_path);
    FixtureView ef = fixture_view(e_path);
    uint32_t probe_pc = 0, probe_found = 0;
    uint64_t probe_count = 0;
    int probe_ci = 0, probe_nrange = 0, probe_matched = 0, probe_outcome = 0;
    int probe_ncand = 0;
    overlay_loader_cps_probe_get(&probe_pc, &probe_count, &probe_found,
                                 &probe_ci, &probe_nrange, &probe_matched,
                                 &probe_outcome, &probe_ncand);

    printf("case=%s\n", name);
    printf("target=0x%08X\n", target);
    printf("edges=%d\n", EDGES);
    printf("setup_ret1=%d\nsetup_ret0=%d\n", setup.ret1, setup.ret0);
    print_cand("pre_h", pre_h);
    print_cand("pre_e", pre_e);
    printf("pre_h_root_calls=%d\n", pre_hf.calls0);
    printf("phase_ret1=%d\nphase_ret0=%d\nphase_result_ok=%d\n",
           phase.ret1, phase.ret0, phase.result_ok);
    printf("phase_try_load_region=%llu\n",
           (unsigned long long)(s_try_load_region_calls - tlr0));
    printf("total_try_load_region=%llu\n",
           (unsigned long long)s_try_load_region_calls);
    printf("phase_loads=%u\ntotal_loads=%u\n", loader_loads() - loads0,
           loader_loads());
    printf("phase_shadow_calls=%llu\n",
           (unsigned long long)(shadow_calls() - shadow0));
    printf("total_shadow_divs=%llu\n", (unsigned long long)shadow_divs());
    printf("phase_e_interp=%llu\n", (unsigned long long)(s_interp_e - interp_e0));
    printf("phase_h_interp=%llu\n", (unsigned long long)(s_interp_h - interp_h0));
    printf("interp_other=%llu\n", (unsigned long long)s_interp_other);
    print_cand("h", h);
    print_cand("e", e);
    printf("h_module=%d\nh_init=%d\nh_root_calls=%d\nh_root_last_pc=0x%08X\n",
           hf.loaded, hf.init, hf.calls0, hf.last_pc0);
    printf("f2_calls=%d\n", hf.calls1);
    printf("e_module=%d\ne_init=%d\ne_native_calls=%d\ne_last_pc=0x%08X\n",
           ef.loaded, ef.init, ef.calls0, ef.last_pc0);
    printf("probe_pc=0x%08X\nprobe_count=%llu\nprobe_found=0x%08X\n",
           probe_pc, (unsigned long long)probe_count, probe_found);
    printf("probe_ci=%d\nprobe_nrange=%d\nprobe_matched=%d\n",
           probe_ci, probe_nrange, probe_matched);
    printf("probe_outcome=%d\nprobe_ncand=%d\n", probe_outcome, probe_ncand);
    printf("loader_msg=%s\n", overlay_loader_last_msg());
    return 0;
}
