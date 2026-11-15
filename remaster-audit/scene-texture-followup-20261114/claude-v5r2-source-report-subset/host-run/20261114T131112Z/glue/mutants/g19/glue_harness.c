/* glue_harness.c v5 — host test of the EXACT renderer glue text (make_patch.GLUE, written by run_host.py to glue.c in
 * the run folder) with minimal renderer type definitions and RECORDING GL stubs (claude-einhander). No GL context,
 * no GPU. Every malloc/calloc/realloc/free/fopen/fread made by the glue (and the hd_class_mips.inc it includes) is
 * COUNTED, so the harness proves there is no allocation and no file access on the draw path.
 *
 * v4 modes (class sidecars, unchanged contract + v5 checks): preload from a real sidecar directory (bounded cache,
 * reasons), draw-time admission of real decoded pixels, verified upload of the prepared bytes (class levels on), the
 * v4 RGB-edge slot flag from the hash-bound has-cutout bit (RGB edges on), sampler state + both uniforms per filter
 * mode, fail-closed restore under an injected level-upload failure, rejection reasons, counters, default OFF and
 * exact-"1" env parsing, slot recycle; RGB-only state stays unused.
 *   glue_harness MODE rgba.bin W H TH PH NATIVE_W NATIVE_H DEPTH UPLOAD_WORDS LEVELS EXPECT_PRELOAD_OK EXPECT_RGB
 *   MODE: off | badenv (everything must be disabled), on (levels + rgb), levels, rgb - the caller sets the environment.
 *
 * v5 modes (RGB-only sidecars HDCMRG01, PSXRECOMP_HD_RGB_EDGES_DIR):
 *   glue_harness MODE rgba.bin W H TH PH NATIVE_W NATIVE_H DEPTH UPLOAD_WORDS EXPECT_RGBN EXPECT_CUT
 *                [both: rgba2.bin W2 H2 TH2 PH2 NATIVE_W2 NATIVE_H2 LEVELS2 EXPECT_CLASSN]
 *   rgbdir     the reviewed census list (fringe >= 8): preload, identity admission, flag, no GL, negatives, recycle
 *   rgbopaque  a verified fully-opaque entry bypasses (flag 0, uniform 0)
 *   rgbfalse   a FALSE "opaque" claim for a has-cutout page is rejected (CUTOUT)
 *   rgbcaps    the crafted read-cap directory (run_host.make_caps_dir; exact counter contract below)
 *   both       class dir + RGB dir: class authority first, RGB-only for the rest, a class rejection never falls back
 * Test-harness output only. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int GLint;
typedef unsigned GLenum;
typedef int GLsizei;
#define GL_TEXTURE_2D 0x0DE1
#define GL_RGBA8 0x8058
#define GL_RGBA 0x1908
#define GL_UNSIGNED_BYTE 0x1401
#define GL_TEXTURE_WIDTH 0x1000
#define GL_TEXTURE_HEIGHT 0x1001
#define GL_TEXTURE_MIN_FILTER 0x2801
#define GL_LINEAR_MIPMAP_LINEAR 0x2703
#define GL_TEXTURE_BASE_LEVEL 0x813C
#define GL_TEXTURE_MAX_LEVEL 0x813D

/* ---- recording GL stubs ---- */
static int g_lw[16], g_lh[16], g_fail_level = -1, g_teximage = 0, g_texparam = 0;
static int g_base = -7, g_max = -7, g_min = -7, g_u[16];
static const uint8_t *g_last_data[16];
static void glTexImage2D(GLenum t, GLint L, GLint ifmt, GLsizei w, GLsizei h, GLint b, GLenum f, GLenum ty, const void *d) {
    (void)t; (void)ifmt; (void)b; (void)f; (void)ty;
    g_teximage++;
    if (L >= 0 && L < 16) {
        g_last_data[L] = (const uint8_t *)d;
        if (L == g_fail_level) { g_lw[L] = 0; g_lh[L] = 0; } /* injected: the level is not allocated */
        else { g_lw[L] = w; g_lh[L] = h; }
    }
}
static void glGetTexLevelParameteriv(GLenum t, GLint L, GLenum p, GLint *v) {
    (void)t;
    *v = (L >= 0 && L < 16) ? (p == GL_TEXTURE_WIDTH ? g_lw[L] : g_lh[L]) : 0;
}
static void glTexParameteri(GLenum t, GLenum p, GLint v) {
    (void)t;
    g_texparam++;
    if (p == GL_TEXTURE_BASE_LEVEL) g_base = v;
    if (p == GL_TEXTURE_MAX_LEVEL) g_max = v;
    if (p == GL_TEXTURE_MIN_FILTER) g_min = v;
}
static void uniform1i_impl(GLint loc, GLint v) { if (loc >= 0 && loc < 16) g_u[loc] = v; }
static void (*p_glUniform1i)(GLint, GLint) = uniform1i_impl;
/* real host clock (QueryPerformanceCounter), so the glue's own tick counters measure actual preload / admit time */
#include <windows.h>
static uint64_t SDL_GetPerformanceCounter(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return (uint64_t)t.QuadPart; }
static double ticks_ms(uint64_t t) { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return (double)t * 1000.0 / (double)f.QuadPart; }

/* ---- v5 instrumentation of the glue's heap and file calls (macros apply to glue.c and the .inc only) ---- */
static long g_n_alloc, g_n_free, g_n_fopen, g_n_fread;
static unsigned long long g_fread_bytes;
static void *h_malloc(size_t n) { ++g_n_alloc; return malloc(n); }
static void *h_calloc(size_t a, size_t b) { ++g_n_alloc; return calloc(a, b); }
static void *h_realloc(void *p, size_t n) { ++g_n_alloc; return realloc(p, n); }
static void h_free(void *p) { if (p) ++g_n_free; free(p); }
static FILE *h_fopen(const char *p, const char *m) { ++g_n_fopen; return fopen(p, m); }
static size_t h_fread(void *b, size_t s, size_t n, FILE *f) {
    ++g_n_fread;
    g_fread_bytes += (unsigned long long)s * n;
    return fread(b, s, n, f);
}

/* ---- the renderer state the glue touches (same field names as v61 + the patch's slot fields) ---- */
typedef struct {
    uint32_t w, h;
    int facade_mips_ready, facade_mips_failed;
    unsigned facade_mip_levels;
    size_t facade_mip_bytes;
    unsigned class_mip_levels;
    unsigned rgb_edges;
} HdTexSlot;
typedef struct { const uint8_t *rgba; uint32_t width, height, stride; } HdTexturePixels;
typedef struct { uint32_t texture_hash, palette_hash; uint16_t upload_width_words, upload_height; } HdTextureSourceMatch;
typedef struct { int depth; } HdTextureDrawQuery;
static struct { size_t resident_mip_bytes; } s_hd_facade_motion;
static int s_tex_filter = 1;
#define LOC_CLASS 7
#define LOC_RGB 9
static GLint s_hd_uClassLevels = LOC_CLASS, s_hd_uRgbEdges = LOC_RGB;

#define malloc h_malloc
#define calloc h_calloc
#define realloc h_realloc
#define free h_free
#define fopen h_fopen
#define fread h_fread
#include "glue.c"   /* make_patch.GLUE, byte-exact */
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef fopen
#undef fread

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++g_fail; } } while (0)

typedef struct { long heap, fopens; unsigned long long fread_bytes; } IoSnap;
static IoSnap io_now(void) { IoSnap s = {g_n_alloc + g_n_free, g_n_fopen, g_fread_bytes}; return s; }
/* no allocation, no free, no file open, no file read since the snapshot */
#define CHECK_NO_IO(s0) CHECK(g_n_alloc + g_n_free == (s0).heap && g_n_fopen == (s0).fopens && g_fread_bytes == (s0).fread_bytes)

static void reset_gl(void) {
    memset(g_lw, 0, sizeof g_lw); memset(g_lh, 0, sizeof g_lh); memset(g_last_data, 0, sizeof g_last_data);
    g_fail_level = -1; g_teximage = 0; g_texparam = 0; g_base = g_max = g_min = -7;
    for (int i = 0; i < 16; i++) g_u[i] = -7;
}
static HdTexSlot fresh(uint32_t w, uint32_t h) { HdTexSlot s; memset(&s, 0, sizeof s); s.w = w; s.h = h; return s; }
/* v61 hd_tex_release_slot: resident mip bytes returned, then memset(slot, 0) (the slot is reused for another key) */
static void release(HdTexSlot *s) {
    if (s_hd_facade_motion.resident_mip_bytes >= s->facade_mip_bytes) s_hd_facade_motion.resident_mip_bytes -= s->facade_mip_bytes;
    memset(s, 0, sizeof *s);
}
static uint8_t *load(const char *path, size_t n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    uint8_t *p = (uint8_t *)malloc(n);
    const size_t got = p ? fread(p, 1, n, f) : 0;
    fclose(f);
    if (got != n) { free(p); return NULL; }
    return p;
}
static int any_cutout(const uint8_t *p, uint32_t w, uint32_t h) {
    for (size_t i = 0; i < (size_t)w * h; i++) if (p[i * 4 + 3] == 0) return 1;
    return 0;
}
static uint64_t sum_reasons(const uint64_t *t) { uint64_t s = 0; for (int i = 0; i < HDCM_REASONS; i++) s += t[i]; return s; }
static int rgbonly_untouched(void) {
    return s_hdcm_rgb_cache.n == 0 && s_hdcm_diag.rgbonly_preload_ok == 0 && s_hdcm_diag.rgbonly_admitted == 0 &&
           s_hdcm_diag.rgbonly_opaque_bypass == 0 && sum_reasons(s_hdcm_diag.rgbonly_preload_rejected) == 0 &&
           sum_reasons(s_hdcm_diag.rgbonly_rejected) == 0;
}
static void timing21(HdTexSlot proto, const HdTexturePixels *px, const HdTextureSourceMatch *m, const HdTextureDrawQuery *q) {
    double t[21];
    for (int i = 0; i < 21; i++) {
        HdTexSlot sx = fresh(proto.w, proto.h);
        const uint64_t before = s_hdcm_diag.ticks;
        reset_gl();
        hd_class_mips_admit_slot(&sx, px, m, q);
        t[i] = ticks_ms(s_hdcm_diag.ticks - before);
    }
    for (int i = 1; i < 21; i++)
        for (int j = i; j > 0 && t[j - 1] > t[j]; j--) { const double x = t[j]; t[j] = t[j - 1]; t[j - 1] = x; }
    printf("TIMING draw_admit_ms_median %.3f min %.3f max %.3f (21 fresh slots, warm)\n", t[10], t[0], t[20]);
}

/* ======================= v5: RGB-only sidecars ======================= */
static int run_rgb(const char *mode, int argc, char **argv) {
    const int is_both = !strcmp(mode, "both"), is_false = !strcmp(mode, "rgbfalse"), is_caps = !strcmp(mode, "rgbcaps");
    if (argc < 13 || (is_both && argc < 22)) return 2;
    const uint32_t W = (uint32_t)atoi(argv[3]), H = (uint32_t)atoi(argv[4]);
    const uint32_t TH = (uint32_t)strtoul(argv[5], NULL, 16), PH = (uint32_t)strtoul(argv[6], NULL, 16);
    const int NHv = atoi(argv[8]), DEPTH = atoi(argv[9]), WORDS = atoi(argv[10]);
    const int EXPECT_N = atoi(argv[11]), EXPECT_CUT = atoi(argv[12]);
    uint8_t *rgba = load(argv[2], (size_t)W * H * 4);
    if (!rgba) return 2;
    CHECK(any_cutout(rgba, W, H) == EXPECT_CUT);                 /* the argument agrees with the pixels */
    HdTexturePixels px = {rgba, W, H, W * 4};
    HdTextureSourceMatch m = {TH, PH, (uint16_t)WORDS, (uint16_t)NHv};
    HdTextureDrawQuery q = {DEPTH};
    int EXPECT_CLASSN = 0;
    if (is_both) EXPECT_CLASSN = atoi(argv[21]);

    const IoSnap p0 = io_now();
    hd_class_mips_preload();
    const IoSnap p1 = io_now();
    CHECK(hd_class_mips_enabled() && s_hdcm_rgb_on && s_hdcm_rgb_dir_on);
    CHECK(s_hdcm_levels_on == is_both && s_hdcm_class_dir_on == is_both);
    CHECK(s_hdcm_rgb_cache.n == EXPECT_N && (int)s_hdcm_diag.rgbonly_preload_ok == EXPECT_N);
    CHECK(s_hdcm_cache.n == EXPECT_CLASSN && (int)s_hdcm_diag.preload_ok == EXPECT_CLASSN);
    CHECK(s_hdcm_diag.preload_bytes == s_hdcm_cache.bytes + (uint64_t)HDCM_RG_BYTES * (uint64_t)EXPECT_N);
    /* preload I/O: the RGB-only kind never touches the heap; each index line opens at most one file; only files of
     * exactly HDCM_RG_BYTES are read (the size is checked first) */
    CHECK(p1.heap - p0.heap == EXPECT_CLASSN);                  /* class sidecars: one accepted buffer each */
    if (is_caps) {
        /* run_host.make_caps_dir contract (300 index lines): 1 valid, 49-byte file, 1 MiB file, missing file, file of
         * another key, duplicate of the valid line, corrupt self-hash, unknown flag, bad magic, bad scale, one garbage
         * line, then fake keys without files. Only 256 lines are consumed (HDCM_RG_CACHE_MAX). */
        const uint64_t *r = s_hdcm_diag.rgbonly_preload_rejected;
        CHECK(r[HDCM_E_SIZE] == 2 && r[HDCM_E_NOFILE] == 1 + 245 && r[HDCM_E_KEY] == 2 && r[HDCM_E_SELFHASH] == 1);
        CHECK(r[HDCM_E_FLAGS] == 1 && r[HDCM_E_MAGIC] == 1 && r[HDCM_E_SCALE] == 1 && sum_reasons(r) == 2 + 246 + 2 + 4);
        CHECK(p1.fopens - p0.fopens == 1 + 10 + 245);           /* index + 10 named lines + 245 fake lines */
        CHECK(p1.fread_bytes - p0.fread_bytes == 7ull * HDCM_RG_BYTES); /* the 49-byte and 1 MiB files are never read */
    } else {
        CHECK(sum_reasons(s_hdcm_diag.rgbonly_preload_rejected) == 0);
        CHECK(p1.fopens - p0.fopens == (1 + EXPECT_N) + (is_both ? 1 + EXPECT_CLASSN : 0));
        CHECK(p1.fread_bytes - p0.fread_bytes == (unsigned long long)HDCM_RG_BYTES * EXPECT_N + s_hdcm_cache.bytes);
    }
    hd_class_mips_preload();                                    /* idempotent: loads once */
    CHECK(g_n_fopen == p1.fopens && (int)s_hdcm_diag.rgbonly_preload_ok == EXPECT_N);
    printf("TIMING preload_total_ms %.3f (index + %d RGB-only reads + verification%s, at init)\n",
           ticks_ms(s_hdcm_diag.preload_ticks), EXPECT_N, is_both ? " + class sidecars" : "");
    printf("PRELOAD rgbonly_ok %llu class_ok %llu bytes %llu\n", (unsigned long long)s_hdcm_diag.rgbonly_preload_ok,
           (unsigned long long)s_hdcm_diag.preload_ok, (unsigned long long)s_hdcm_diag.preload_bytes);
    const IoSnap d0 = io_now();                                 /* from here on: the draw path only */

    /* 1 admission (identity + has-cutout truth), never a GL call, class state untouched */
    reset_gl();
    HdTexSlot slot = fresh(W, H);
    hd_class_mips_admit_slot(&slot, &px, &m, &q);
    printf("TIMING draw_admit_ms %.3f (RGB-only: cache lookup + one-pass level-0 hash/cutout scan)\n", ticks_ms(s_hdcm_diag.ticks));
    CHECK(g_teximage == 0 && g_texparam == 0);
    CHECK(slot.class_mip_levels == 0 && slot.facade_mips_ready == 0 && slot.facade_mip_levels == 0 && slot.facade_mip_bytes == 0);
    CHECK(s_hdcm_diag.admitted == 0 && s_hdcm_diag.rgb_edge_slots == 0 && s_hdcm_diag.rgb_opaque_skipped == 0);
    CHECK(s_hdcm_diag.attempted == 1);
    if (is_false) {
        CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_CUTOUT] == 1 && s_hdcm_diag.rgbonly_admitted == 0 && slot.rgb_edges == 0);
    } else {
        CHECK(s_hdcm_diag.rgbonly_admitted == 1 && (int)slot.rgb_edges == EXPECT_CUT);
        CHECK(s_hdcm_diag.rgbonly_opaque_bypass == (uint64_t)!EXPECT_CUT && sum_reasons(s_hdcm_diag.rgbonly_rejected) == 0);
    }
    const int rg = is_false ? 0 : EXPECT_CUT;

    /* 2 sampler state + uniforms: RGB edges in filter mode only, class levels always 0, no filter change */
    reset_gl(); s_tex_filter = 1;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == rg && g_min == -7 && g_texparam == 0);
    reset_gl();
    hd_class_mips_sampling(&slot, 1);
    CHECK(g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == rg && g_min == -7);
    reset_gl(); s_tex_filter = 0;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == 0 && g_min == -7);         /* point path untouched */
    s_tex_filter = 1;

    /* 3 once per slot (a flagged slot is never re-admitted) */
    if (rg) {
        const uint64_t att = s_hdcm_diag.attempted;
        hd_class_mips_admit_slot(&slot, &px, &m, &q);
        CHECK(s_hdcm_diag.attempted == att && s_hdcm_diag.rgbonly_admitted == 1);
    }
    /* 4 slot recycle: v61 hd_tex_release_slot memsets the slot; the next build re-admits from the verified cache */
    if (!is_false) {
        release(&slot);
        CHECK(slot.rgb_edges == 0);
        slot.w = W; slot.h = H;
        reset_gl();
        hd_class_mips_admit_slot(&slot, &px, &m, &q);
        CHECK(s_hdcm_diag.rgbonly_admitted == 2 && (int)slot.rgb_edges == EXPECT_CUT && g_teximage == 0 && g_texparam == 0);
        CHECK(s_hdcm_diag.rgbonly_opaque_bypass == 2ull * (uint64_t)!EXPECT_CUT);
    }

    /* 5 negatives: counted reason, no GL call, no flag */
    {
        const uint64_t l0 = s_hdcm_diag.rgbonly_rejected[HDCM_E_LEVEL0];
        reset_gl();
        rgba[0] ^= 1;                                            /* red of texel 0: identity changes, cutout truth does not */
        HdTexSlot s3 = fresh(W, H);
        hd_class_mips_admit_slot(&s3, &px, &m, &q);
        rgba[0] ^= 1;
        CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_LEVEL0] == l0 + 1 && s3.rgb_edges == 0 && g_teximage == 0 && g_texparam == 0);
    }
    {
        reset_gl();
        HdTextureSourceMatch m2 = m; m2.palette_hash ^= 0x1u;     /* not listed in either kind */
        HdTexSlot s4 = fresh(W, H);
        hd_class_mips_admit_slot(&s4, &px, &m2, &q);
        CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_NOFILE] == 1 && s4.rgb_edges == 0 && g_teximage == 0 && g_texparam == 0);
        CHECK(s_hdcm_diag.rejected[HDCM_E_NOFILE] == 0);         /* the class table is not charged for RGB-only misses */
    }
    {
        reset_gl();
        const uint64_t c0 = s_hdcm_diag.rgbonly_rejected[HDCM_E_CUTOUT];
        HdTexSlot s5 = fresh(W / 2, H);                         /* slot dims differ from the decode */
        hd_class_mips_admit_slot(&s5, &px, &m, &q);
        if (is_false)                                           /* the sidecar check (false claim) comes first */
            CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_CUTOUT] == c0 + 1 && s_hdcm_diag.rgbonly_rejected[HDCM_E_HD_DIMS] == 0);
        else
            CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_HD_DIMS] == 1);
        CHECK(s5.rgb_edges == 0 && g_teximage == 0 && g_texparam == 0);
    }
    {
        reset_gl();
        HdTextureSourceMatch m3 = m; m3.upload_width_words = (uint16_t)(m3.upload_width_words + 1);
        HdTexSlot s6 = fresh(W, H);
        hd_class_mips_admit_slot(&s6, &px, &m3, &q);
        CHECK(s_hdcm_diag.rgbonly_rejected[HDCM_E_NATIVE_DIMS] == 1 && s6.rgb_edges == 0 && g_teximage == 0);
    }
    {
        reset_gl();
        HdTexSlot s7 = fresh(W, H), s8 = fresh(W, H);
        s7.facade_mips_ready = 1; s8.facade_mips_failed = 1;
        const uint64_t att = s_hdcm_diag.attempted;
        hd_class_mips_admit_slot(&s7, &px, &m, &q);
        hd_class_mips_admit_slot(&s8, &px, &m, &q);
        CHECK(s_hdcm_diag.attempted == att && g_teximage == 0 && s7.rgb_edges == 0 && s8.rgb_edges == 0);
    }
    timing21(fresh(W, H), &px, &m, &q);

    /* 6 both kinds: the class key (with an RGB-only entry of its own in the RGB dir) keeps class authority */
    if (is_both) {
        const uint32_t W2 = (uint32_t)atoi(argv[14]), H2 = (uint32_t)atoi(argv[15]);
        const uint32_t TH2 = (uint32_t)strtoul(argv[16], NULL, 16), PH2 = (uint32_t)strtoul(argv[17], NULL, 16);
        const int NW2 = atoi(argv[18]), NH2 = atoi(argv[19]), LEVELS2 = atoi(argv[20]);
        uint8_t *rgba2 = (uint8_t *)malloc((size_t)W2 * H2 * 4);  /* harness memory, not the glue's (uncounted) */
        FILE *f2 = fopen(argv[13], "rb");
        CHECK(f2 && rgba2 && fread(rgba2, 1, (size_t)W2 * H2 * 4, f2) == (size_t)W2 * H2 * 4);
        if (f2) fclose(f2);
        const IoSnap d1 = io_now();
        CHECK(d1.heap == d0.heap && d1.fopens == d0.fopens);
        HdTexturePixels px2 = {rgba2, W2, H2, W2 * 4};
        HdTextureSourceMatch mc = {TH2, PH2, (uint16_t)NW2, (uint16_t)NH2};
        HdTextureDrawQuery q2 = {2};
        CHECK(hdcm_rgb_cache_find(&s_hdcm_rgb_cache, TH2, PH2) != NULL);  /* an RGB-only entry exists for it ... */
        const uint64_t ra = s_hdcm_diag.rgbonly_admitted, rr = sum_reasons(s_hdcm_diag.rgbonly_rejected);
        const uint64_t rb = s_hdcm_diag.rgbonly_opaque_bypass;
        reset_gl();
        HdTexSlot c = fresh(W2, H2);
        hd_class_mips_admit_slot(&c, &px2, &mc, &q2);
        /* ... and is never used: class levels uploaded, rgb flag from the CLASS sidecar's has-cutout bit */
        CHECK(s_hdcm_diag.admitted == 1 && (int)c.class_mip_levels == LEVELS2 && g_teximage == LEVELS2 && g_max == LEVELS2);
        CHECK((int)c.rgb_edges == any_cutout(rgba2, W2, H2) && s_hdcm_diag.rgb_edge_slots + s_hdcm_diag.rgb_opaque_skipped == 1);
        CHECK(s_hdcm_diag.rgbonly_admitted == ra && sum_reasons(s_hdcm_diag.rgbonly_rejected) == rr && s_hdcm_diag.rgbonly_opaque_bypass == rb);
        reset_gl(); s_tex_filter = 1;
        hd_class_mips_sampling(&c, 0);
        CHECK(g_u[LOC_CLASS] == LEVELS2 && g_min == GL_LINEAR_MIPMAP_LINEAR && g_u[LOC_RGB] == (int)c.rgb_edges);
        /* a class sidecar that fails admission leaves the original path and NEVER falls back to its RGB-only entry */
        reset_gl();
        rgba2[4] ^= 1;
        HdTexSlot c2 = fresh(W2, H2);
        hd_class_mips_admit_slot(&c2, &px2, &mc, &q2);
        rgba2[4] ^= 1;
        CHECK(s_hdcm_diag.rejected[HDCM_E_LEVEL0] == 1 && c2.rgb_edges == 0 && c2.class_mip_levels == 0 && g_teximage == 0);
        CHECK(s_hdcm_diag.rgbonly_admitted == ra && sum_reasons(s_hdcm_diag.rgbonly_rejected) == rr);
        free(rgba2);
        /* the RGB-only key still uses its RGB-only entry with class levels on (no level, no GL) */
        reset_gl();
        HdTexSlot k1 = fresh(W, H);
        hd_class_mips_admit_slot(&k1, &px, &m, &q);
        CHECK(s_hdcm_diag.rgbonly_admitted == ra + 1 && (int)k1.rgb_edges == EXPECT_CUT && k1.class_mip_levels == 0 && g_teximage == 0);
        reset_gl();
        hd_class_mips_sampling(&k1, 0);
        CHECK(g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == EXPECT_CUT && g_min == -7);
    } else {
        CHECK(s_hd_facade_motion.resident_mip_bytes == 0 && s_hdcm_diag.levels_uploaded == 0);
    }
    CHECK_NO_IO(d0);                                             /* no allocation / file access on the draw path */

    /* 7 counters accessor: 13 head values, then 4 reason tables */
    uint64_t out[13 + 4 * HDCM_REASONS + 4];
    CHECK(gl_renderer_class_mips_counters(out, (int)(sizeof out / sizeof out[0])) == 13 + 4 * HDCM_REASONS);
    CHECK(out[10] == s_hdcm_diag.rgbonly_preload_ok && out[11] == s_hdcm_diag.rgbonly_admitted && out[12] == s_hdcm_diag.rgbonly_opaque_bypass);
    CHECK(out[13 + 2 * HDCM_REASONS + HDCM_E_SIZE] == s_hdcm_diag.rgbonly_preload_rejected[HDCM_E_SIZE]);
    CHECK(out[13 + 3 * HDCM_REASONS + HDCM_E_LEVEL0] == 1 && out[13 + 3 * HDCM_REASONS + HDCM_E_NATIVE_DIMS] == 1);
    CHECK(gl_renderer_class_mips_counters(out, 3) == 3);
    printf("checks %d failures %d\n", g_checks, g_fail);
    free(rgba);
    return g_fail ? 1 : 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    const char *mode = argv[1];
    if (!strncmp(mode, "rgb", 3) && strcmp(mode, "rgb") != 0) return run_rgb(mode, argc, argv);
    if (!strcmp(mode, "both")) return run_rgb(mode, argc, argv);
    if (argc < 14) return 2;
    const int want_levels = !strcmp(mode, "on") || !strcmp(mode, "levels");
    const int want_rgb = !strcmp(mode, "on") || !strcmp(mode, "rgb");
    const uint32_t W = (uint32_t)atoi(argv[3]), H = (uint32_t)atoi(argv[4]);
    const uint32_t TH = (uint32_t)strtoul(argv[5], NULL, 16), PH = (uint32_t)strtoul(argv[6], NULL, 16);
    const int NHv = atoi(argv[8]), DEPTH = atoi(argv[9]), WORDS = atoi(argv[10]);
    const int LEVELS = atoi(argv[11]), EXPECT_OK = atoi(argv[12]), EXPECT_RGB = atoi(argv[13]);
    uint8_t *rgba = load(argv[2], (size_t)W * H * 4);
    if (!rgba) return 2;
    HdTexturePixels px = {rgba, W, H, W * 4};
    HdTextureSourceMatch m = {TH, PH, (uint16_t)WORDS, (uint16_t)NHv};
    HdTextureDrawQuery q = {DEPTH};

    const IoSnap p0 = io_now();
    hd_class_mips_preload();
    if (!want_levels && !want_rgb) {                                         /* off / badenv: default OFF */
        CHECK(!hd_class_mips_enabled() && !s_hdcm_levels_on && !s_hdcm_rgb_on);
        CHECK(!s_hdcm_class_dir_on && !s_hdcm_rgb_dir_on);
        CHECK(s_hdcm_diag.preload_ok == 0 && s_hdcm_cache.n == 0 && rgbonly_untouched());
        CHECK_NO_IO(p0);                                                     /* disabled: not even the index is opened */
        printf("checks %d failures %d\n", g_checks, g_fail);
        return g_fail ? 1 : 0;
    }
    CHECK(hd_class_mips_enabled());
    CHECK(s_hdcm_levels_on == want_levels && s_hdcm_rgb_on == want_rgb);
    CHECK(s_hdcm_class_dir_on && !s_hdcm_rgb_dir_on);                        /* v4 modes: the RGB-only dir stays unused */
    CHECK((int)s_hdcm_diag.preload_ok == EXPECT_OK && s_hdcm_cache.n == EXPECT_OK);
    CHECK(s_hdcm_cache.bytes <= s_hdcm_cache.cap_bytes && s_hdcm_cache.bytes == s_hdcm_diag.preload_bytes);
    hd_class_mips_preload();                                                  /* idempotent: loads once */
    CHECK((int)s_hdcm_diag.preload_ok == EXPECT_OK);
    printf("TIMING preload_total_ms %.3f (index + file reads + full verification of every listed sidecar, at init)\n",
           ticks_ms(s_hdcm_diag.preload_ticks));
    printf("PRELOAD ok %llu bytes %llu\n", (unsigned long long)s_hdcm_diag.preload_ok, (unsigned long long)s_hdcm_diag.preload_bytes);
    const HdcmSidecar *sc = hdcm_cache_find(&s_hdcm_cache, TH, PH);
    CHECK(sc != NULL);
    const IoSnap d0 = io_now();                                               /* from here on: the draw path only */

    /* 1 admission */
    reset_gl();
    HdTexSlot slot = fresh(W, H);
    hd_class_mips_admit_slot(&slot, &px, &m, &q);
    printf("TIMING draw_admit_ms %.3f (cache lookup + level-0 hash + R1%s)\n", ticks_ms(s_hdcm_diag.ticks),
           want_levels ? " + stub level uploads" : "");
    CHECK(s_hdcm_diag.admitted == 1);
    if (want_levels) {
        CHECK(s_hdcm_diag.levels_uploaded == (uint64_t)LEVELS && g_teximage == LEVELS && g_base == 0 && g_max == LEVELS);
        CHECK(slot.class_mip_levels == (unsigned)LEVELS && slot.facade_mips_ready == 1 && slot.facade_mip_levels == (unsigned)LEVELS + 1);
        for (int L = 1; sc && L <= LEVELS; L++) CHECK(g_last_data[L] == sc->level[L] && g_lw[L] == (int)(W >> L) && g_lh[L] == (int)(H >> L));
        CHECK(slot.facade_mip_bytes == s_hd_facade_motion.resident_mip_bytes && slot.facade_mip_bytes > 0);
    } else {
        CHECK(g_teximage == 0 && g_texparam == 0);                            /* RGB only: no level upload at all */
        CHECK(slot.class_mip_levels == 0 && slot.facade_mips_ready == 0 && s_hdcm_diag.levels_uploaded == 0);
    }
    if (want_rgb) {
        CHECK((int)slot.rgb_edges == EXPECT_RGB);                            /* from the hash-bound has-cutout bit */
        CHECK(s_hdcm_diag.rgb_edge_slots == (uint64_t)EXPECT_RGB && s_hdcm_diag.rgb_opaque_skipped == (uint64_t)!EXPECT_RGB);
    } else {
        CHECK(slot.rgb_edges == 0 && s_hdcm_diag.rgb_edge_slots == 0);
    }
    reset_gl();
    hd_class_mips_admit_slot(&slot, &px, &m, &q);                              /* once per slot */
    CHECK(g_teximage == 0 && (s_hdcm_diag.attempted == 1 || (!want_levels && !EXPECT_RGB)));
    const uint64_t att0 = s_hdcm_diag.attempted, adm0 = s_hdcm_diag.admitted;

    /* 1b slot recycle (v61 hd_tex_release_slot: resident bytes returned, memset): re-admitted from the cache */
    release(&slot);
    slot.w = W; slot.h = H;
    reset_gl();
    hd_class_mips_admit_slot(&slot, &px, &m, &q);
    CHECK(s_hdcm_diag.attempted == att0 + 1 && s_hdcm_diag.admitted == adm0 + 1);
    if (want_levels)
        CHECK(slot.class_mip_levels == (unsigned)LEVELS && g_teximage == LEVELS && slot.facade_mip_bytes == s_hd_facade_motion.resident_mip_bytes);
    CHECK((int)slot.rgb_edges == (want_rgb ? EXPECT_RGB : 0));

    timing21(fresh(W, H), &px, &m, &q);

    /* 2 sampler state + uniforms */
    const int cl = want_levels ? LEVELS : 0, rg = want_rgb ? EXPECT_RGB : 0;
    reset_gl(); s_tex_filter = 1;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_u[LOC_CLASS] == cl && g_u[LOC_RGB] == rg);
    CHECK(g_min == (cl ? GL_LINEAR_MIPMAP_LINEAR : -7));
    reset_gl();
    hd_class_mips_sampling(&slot, 1);                                         /* facade path chose its own filter */
    CHECK(g_min == -7 && g_u[LOC_CLASS] == cl && g_u[LOC_RGB] == rg);
    reset_gl(); s_tex_filter = 0;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_min == -7 && g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == 0);          /* point path untouched */
    s_tex_filter = 1;
    HdTexSlot plain = fresh(W, H);
    reset_gl();
    hd_class_mips_sampling(&plain, 0);
    CHECK(g_min == -7 && g_u[LOC_CLASS] == 0 && g_u[LOC_RGB] == 0);          /* non-admitted slot */

    /* 3 fail closed (class levels only) */
    if (want_levels) {
        reset_gl(); g_fail_level = LEVELS >= 2 ? 2 : 1;
        HdTexSlot s2 = fresh(W, H);
        hd_class_mips_admit_slot(&s2, &px, &m, &q);
        CHECK(s_hdcm_diag.rejected[HDCM_E_GL] == 1 && g_base == 0 && g_max == 1000);
        CHECK(s2.class_mip_levels == 0 && s2.facade_mips_ready == 0 && s2.facade_mips_failed == 0 && s2.rgb_edges == 0);
        CHECK(g_teximage == g_fail_level);
    }

    /* 4 wrong pixels -> LEVEL0, no GL call, no RGB flag */
    reset_gl();
    rgba[123] ^= 1;
    HdTexSlot s3 = fresh(W, H);
    hd_class_mips_admit_slot(&s3, &px, &m, &q);
    rgba[123] ^= 1;
    CHECK(s_hdcm_diag.rejected[HDCM_E_LEVEL0] == 1 && g_teximage == 0 && g_texparam == 0 && s3.rgb_edges == 0);

    /* 5 key not in the cache -> NOFILE (original path) */
    reset_gl();
    HdTextureSourceMatch m2 = m; m2.palette_hash ^= 0x1u;
    HdTexSlot s4 = fresh(W, H);
    hd_class_mips_admit_slot(&s4, &px, &m2, &q);
    CHECK(s_hdcm_diag.rejected[HDCM_E_NOFILE] == 1 && g_teximage == 0 && g_texparam == 0 && s4.rgb_edges == 0);

    /* 6 slot dims differ -> HD_DIMS */
    reset_gl();
    HdTexSlot s5 = fresh(W / 2, H);
    hd_class_mips_admit_slot(&s5, &px, &m, &q);
    CHECK(s_hdcm_diag.rejected[HDCM_E_HD_DIMS] == 1 && g_teximage == 0 && s5.rgb_edges == 0);

    /* 7 a slot the experiment already mipmapped / failed is never touched */
    reset_gl();
    HdTexSlot s6 = fresh(W, H), s7 = fresh(W, H);
    s6.facade_mips_ready = 1; s7.facade_mips_failed = 1;
    const uint64_t att = s_hdcm_diag.attempted;
    hd_class_mips_admit_slot(&s6, &px, &m, &q);
    hd_class_mips_admit_slot(&s7, &px, &m, &q);
    CHECK(s_hdcm_diag.attempted == att && g_teximage == 0 && s6.rgb_edges == 0 && s7.rgb_edges == 0);
    CHECK_NO_IO(d0);                                                          /* no allocation / file access on the draw path */
    CHECK(rgbonly_untouched());                                              /* v5 kind unused in every v4 mode */

    /* 8 counters accessor (13 head values, 4 reason tables) */
    uint64_t out[13 + 4 * HDCM_REASONS + 4];
    CHECK(gl_renderer_class_mips_counters(out, (int)(sizeof out / sizeof out[0])) == 13 + 4 * HDCM_REASONS);
    CHECK(out[0] == s_hdcm_diag.preload_ok && out[4] == s_hdcm_diag.admitted && out[8] == s_hdcm_diag.rgb_edge_slots);
    CHECK(out[13 + HDCM_REASONS + HDCM_E_LEVEL0] == 1);
    CHECK(gl_renderer_class_mips_counters(out, 3) == 3);
    printf("checks %d failures %d\n", g_checks, g_fail);
    free(rgba);
    return g_fail ? 1 : 0;
}
