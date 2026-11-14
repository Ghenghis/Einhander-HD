/* glue_harness.c — host test of the EXACT renderer glue text (make_patch.GLUE, written by run_host.py to glue.c in
 * the run folder) with minimal renderer type definitions and RECORDING GL stubs (claude-einhander). No GL context,
 * no GPU. Proves on host: preload from a real sidecar directory (bounded cache, reasons), draw-time admission of real
 * decoded pixels, verified upload of the prepared bytes, sampler state per filter mode, fail-closed restore under an
 * injected level-upload failure, rejection reasons, counters, and that the glue needs no level builder
 * (HDCM_NO_BUILDER: hdcm_build_level is not even declared here).
 * Usage: glue_harness MODE rgba.bin W H TH PH NATIVE_W NATIVE_H DEPTH UPLOAD_WORDS LEVELS EXPECT_PRELOAD_OK
 *   MODE "on": PSXRECOMP_HD_CLASS_MIPS=1 + _DIR set by the caller; MODE "off": both unset. Test-harness output only. */
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
static int g_base = -7, g_max = -7, g_min = -7, g_uniform = -7, g_uniform_calls = 0;
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
static void uniform1i_impl(GLint loc, GLint v) { (void)loc; g_uniform = v; g_uniform_calls++; }
static void (*p_glUniform1i)(GLint, GLint) = uniform1i_impl;
/* real host clock (QueryPerformanceCounter), so the glue's own tick counters measure actual preload / admit time */
#include <windows.h>
static uint64_t SDL_GetPerformanceCounter(void) { LARGE_INTEGER t; QueryPerformanceCounter(&t); return (uint64_t)t.QuadPart; }
static double ticks_ms(uint64_t t) { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return (double)t * 1000.0 / (double)f.QuadPart; }

/* ---- the renderer state the glue touches (same field names as v61) ---- */
typedef struct {
    uint32_t w, h;
    int facade_mips_ready, facade_mips_failed;
    unsigned facade_mip_levels;
    size_t facade_mip_bytes;
    unsigned class_mip_levels;
} HdTexSlot;
typedef struct { const uint8_t *rgba; uint32_t width, height, stride; } HdTexturePixels;
typedef struct { uint32_t texture_hash, palette_hash; uint16_t upload_width_words, upload_height; } HdTextureSourceMatch;
typedef struct { int depth; } HdTextureDrawQuery;
static struct { size_t resident_mip_bytes; } s_hd_facade_motion;
static int s_tex_filter = 1;
static GLint s_hd_uClassLevels = 7;

#include "glue.c"   /* make_patch.GLUE, byte-exact */

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++g_fail; } } while (0)

static void reset_gl(void) {
    memset(g_lw, 0, sizeof g_lw); memset(g_lh, 0, sizeof g_lh); memset(g_last_data, 0, sizeof g_last_data);
    g_fail_level = -1; g_teximage = 0; g_texparam = 0; g_base = g_max = g_min = g_uniform = -7; g_uniform_calls = 0;
}

int main(int argc, char **argv) {
    if (argc < 13) return 2;
    const int on = strcmp(argv[1], "on") == 0;
    const uint32_t W = (uint32_t)atoi(argv[3]), H = (uint32_t)atoi(argv[4]);
    const uint32_t TH = (uint32_t)strtoul(argv[5], NULL, 16), PH = (uint32_t)strtoul(argv[6], NULL, 16);
    const int NWv = atoi(argv[7]), NHv = atoi(argv[8]), DEPTH = atoi(argv[9]), WORDS = atoi(argv[10]);
    const int LEVELS = atoi(argv[11]), EXPECT_OK = atoi(argv[12]);
    FILE *f = fopen(argv[2], "rb");
    if (!f) return 2;
    uint8_t *rgba = (uint8_t *)malloc((size_t)W * H * 4);
    if (fread(rgba, 1, (size_t)W * H * 4, f) != (size_t)W * H * 4) return 2;
    fclose(f);
    HdTexturePixels px = {rgba, W, H, W * 4};
    HdTextureSourceMatch m = {TH, PH, (uint16_t)WORDS, (uint16_t)NHv};
    HdTextureDrawQuery q = {DEPTH};
    (void)NWv;

    hd_class_mips_preload();
    if (!on) {
        CHECK(!hd_class_mips_enabled());
        CHECK(s_hdcm_diag.preload_ok == 0 && s_hdcm_cache.n == 0);           /* default OFF: nothing loaded */
        printf("checks %d failures %d\n", g_checks, g_fail);
        return g_fail ? 1 : 0;
    }
    CHECK(hd_class_mips_enabled());
    CHECK((int)s_hdcm_diag.preload_ok == EXPECT_OK && s_hdcm_cache.n == EXPECT_OK);
    CHECK(s_hdcm_cache.bytes <= s_hdcm_cache.cap_bytes && s_hdcm_cache.bytes == s_hdcm_diag.preload_bytes);
    hd_class_mips_preload();                                                  /* idempotent: loads once */
    CHECK((int)s_hdcm_diag.preload_ok == EXPECT_OK);
    printf("TIMING preload_total_ms %.3f (index + file reads + full verification of every listed sidecar, at init)\n",
           ticks_ms(s_hdcm_diag.preload_ticks));
    printf("PRELOAD ok %llu bytes %llu", (unsigned long long)s_hdcm_diag.preload_ok, (unsigned long long)s_hdcm_diag.preload_bytes);
    for (int i = 0; i < HDCM_REASONS; i++)
        if (s_hdcm_diag.preload_rejected[i]) printf(" rej%d=%llu", i, (unsigned long long)s_hdcm_diag.preload_rejected[i]);
    printf("\n");
    const HdcmSidecar *sc = hdcm_cache_find(&s_hdcm_cache, TH, PH);
    CHECK(sc != NULL);

    /* 1 admitted: verified upload of the prepared bytes */
    reset_gl();
    HdTexSlot slot = {W, H, 0, 0, 0, 0, 0};
    hd_class_mips_admit_slot(&slot, &px, &m, &q);
    CHECK(s_hdcm_diag.admitted == 1 && s_hdcm_diag.levels_uploaded == (uint64_t)LEVELS);
    CHECK(g_teximage == LEVELS && g_base == 0 && g_max == LEVELS);
    CHECK(slot.class_mip_levels == (unsigned)LEVELS && slot.facade_mips_ready == 1 && slot.facade_mip_levels == (unsigned)LEVELS + 1);
    for (int L = 1; sc && L <= LEVELS; L++) CHECK(g_last_data[L] == sc->level[L] && g_lw[L] == (int)(W >> L) && g_lh[L] == (int)(H >> L));
    CHECK(slot.facade_mip_bytes == s_hd_facade_motion.resident_mip_bytes && slot.facade_mip_bytes > 0);
    printf("TIMING draw_admit_ms %.3f (cache lookup + level-0 hash + R1 + %d stub uploads; real GL upload time is GPU-measured)\n",
           ticks_ms(s_hdcm_diag.ticks), LEVELS);
    /* second call on the same slot does nothing */
    reset_gl();
    hd_class_mips_admit_slot(&slot, &px, &m, &q);
    CHECK(g_teximage == 0 && s_hdcm_diag.attempted == 1);

    /* 2 sampler state: filter mode selects the mip filter + uniform; point mode leaves both alone / 0 */
    reset_gl(); s_tex_filter = 1;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_min == GL_LINEAR_MIPMAP_LINEAR && g_uniform == LEVELS);
    reset_gl();
    hd_class_mips_sampling(&slot, 1);                                         /* facade path already chose it */
    CHECK(g_min == -7 && g_uniform == LEVELS);
    reset_gl(); s_tex_filter = 0;
    hd_class_mips_sampling(&slot, 0);
    CHECK(g_min == -7 && g_uniform == 0);                                     /* point path untouched */
    s_tex_filter = 1;
    HdTexSlot plain = {W, H, 0, 0, 0, 0, 0};
    reset_gl();
    hd_class_mips_sampling(&plain, 0);
    CHECK(g_min == -7 && g_uniform == 0);                                     /* non-admitted slot untouched */

    /* 3 fail closed: level 2 upload not allocated -> GL reason, BASE 0 + MAX 1000 restored, slot not marked */
    reset_gl(); g_fail_level = LEVELS >= 2 ? 2 : 1;
    HdTexSlot s2 = {W, H, 0, 0, 0, 0, 0};
    hd_class_mips_admit_slot(&s2, &px, &m, &q);
    CHECK(s_hdcm_diag.rejected[HDCM_E_GL] == 1 && g_base == 0 && g_max == 1000);
    CHECK(s2.class_mip_levels == 0 && s2.facade_mips_ready == 0 && s2.facade_mips_failed == 0);
    CHECK(g_teximage == g_fail_level);                                        /* nothing uploaded after the failure */

    /* 4 wrong pixels -> LEVEL0, no GL call */
    reset_gl();
    rgba[123] ^= 1;
    HdTexSlot s3 = {W, H, 0, 0, 0, 0, 0};
    hd_class_mips_admit_slot(&s3, &px, &m, &q);
    rgba[123] ^= 1;
    CHECK(s_hdcm_diag.rejected[HDCM_E_LEVEL0] == 1 && g_teximage == 0 && g_texparam == 0);

    /* 5 key not in the cache -> NOFILE, no GL call (original path) */
    reset_gl();
    HdTextureSourceMatch m2 = m; m2.palette_hash ^= 0x1u;
    HdTexSlot s4 = {W, H, 0, 0, 0, 0, 0};
    hd_class_mips_admit_slot(&s4, &px, &m2, &q);
    CHECK(s_hdcm_diag.rejected[HDCM_E_NOFILE] == 1 && g_teximage == 0 && g_texparam == 0);

    /* 6 slot dims differ from the decoded image -> HD_DIMS, no GL call */
    reset_gl();
    HdTexSlot s5 = {W / 2, H, 0, 0, 0, 0, 0};
    hd_class_mips_admit_slot(&s5, &px, &m, &q);
    CHECK(s_hdcm_diag.rejected[HDCM_E_HD_DIMS] == 1 && g_teximage == 0);

    /* 7 a slot the experiment already mipmapped / failed is never touched */
    reset_gl();
    HdTexSlot s6 = {W, H, 1, 0, 0, 0, 0}, s7 = {W, H, 0, 1, 0, 0, 0};
    const uint64_t att = s_hdcm_diag.attempted;
    hd_class_mips_admit_slot(&s6, &px, &m, &q);
    hd_class_mips_admit_slot(&s7, &px, &m, &q);
    CHECK(s_hdcm_diag.attempted == att && g_teximage == 0);

    /* 8 counters accessor */
    uint64_t out[8 + 2 * HDCM_REASONS + 4];
    CHECK(gl_renderer_class_mips_counters(out, (int)(sizeof out / sizeof out[0])) == 8 + 2 * HDCM_REASONS);
    CHECK(out[0] == s_hdcm_diag.preload_ok && out[4] == s_hdcm_diag.admitted && out[8 + HDCM_REASONS + HDCM_E_GL] == 1);
    CHECK(gl_renderer_class_mips_counters(out, 3) == 3);
    printf("checks %d failures %d\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
