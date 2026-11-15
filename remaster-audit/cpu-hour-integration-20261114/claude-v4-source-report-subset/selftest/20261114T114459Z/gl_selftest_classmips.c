/* gl_selftest_classmips.c v3 — GPU self-test of the PRIVATE class-aware mip shader + upload path (claude-einhander).
 *
 * BUILT on CPU by build_selftest.py; RUN BY ROOT on the GPU (never by Claude): hidden SDL3 window, GL 3.3 core
 * context, offscreen rendering only, then exit. Previous result (v1 build 110630, root N/class-mip-gpu-r1): FAIL -
 * acceptance was inconsistent (lod-0 no-bleed vs lod-0 identity) and over-scoped (m = 12 > s = 8); see DESIGN-V3.md.
 *
 * Links the EXACT TEX_VS + HD_FS strings extracted from the preprocessed patched v61 copy (argv) like
 * build_program_ex(..., dual_source = 1) and draws one opaque raw quad of a synthetic class texture (native 32 x 8 at
 * scale 8 = HD 256 x 64: a 2-px neon stroke in visible native cells, an opaque block, cutout RGB black). Variants:
 *   A  level 0 only, MIN LINEAR, u_hd_class_levels 0 (v61 without experiments)
 *   B  glGenerateMipmap, MIN LINEAR_MIPMAP_LINEAR, u_hd_facade_motion 1, levels 0 (v61 facade/world experiment)
 *   C  prepared class levels via hdcm_upload_prepared + the renderer's verifying upload, u_hd_facade_motion 1, levels 3
 *   N  same texture as C on the NEW non-facade path: u_hd_facade_motion 0, levels 3 (class at round(lod), RGB textureGrad)
 *   D  level 0 with R5 cutout-RGB fill (the separate offline content track), level-0 only, for the lod-0 fringe
 * at minification m in {1, 2, 4, 8, 12} and 8 sub-pixel phases, read back. Checks (exit 0 only if all pass):
 *   1 link, uniforms, FBO, no GL error;
 *   2 C and N: the stroke never vanishes for m <= s (2, 4, 8)            [m = 12 > s: reported only]
 *   3 C and N: darkest visible luma >= 90 % of the darkest authored luma for m >= 2   [m = 1: reported]
 *   4 point path unchanged: u_filter 0 renders identically for C (levels 3) and A (levels 0), both facade settings;
 *   5 lod 0 (m = 1): C and N render identically to A;
 *   6 D at m = 1 keeps >= 90 % authored luma (the lod-0 fringe is level-0 content, fixed by R5, not by levels);
 *   7 fail closed on real GL: an injected wrong-size level stops the chain with HDCM_E_GL after 1 verified level and
 *     the glue's restore leaves MAX_LEVEL 1000.
 * Reported only: A/B numbers, m = 12, lod-0 C/N darkness, and the GPU time to upload + verify a 2048^2 prepared
 * level set (levels 1..3, 5.25 MiB) through the renderer's callback (glFinish-bounded).
 * Usage: gl_selftest_classmips TEX_VS.vert HD_FS.frag out.json */
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_opengl.h>

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "hd_class_mips.inc"

#define NW 32
#define NH 8
#define S 8
#define HW (NW * S)
#define HH (NH * S)
#define TEXV 22
#define PHASES 8

static PFNGLCREATESHADERPROC pCreateShader;
static PFNGLSHADERSOURCEPROC pShaderSource;
static PFNGLCOMPILESHADERPROC pCompileShader;
static PFNGLGETSHADERIVPROC pGetShaderiv;
static PFNGLGETSHADERINFOLOGPROC pGetShaderInfoLog;
static PFNGLCREATEPROGRAMPROC pCreateProgram;
static PFNGLATTACHSHADERPROC pAttachShader;
static PFNGLBINDFRAGDATALOCATIONINDEXEDPROC pBindFragDataLocationIndexed;
static PFNGLLINKPROGRAMPROC pLinkProgram;
static PFNGLGETPROGRAMIVPROC pGetProgramiv;
static PFNGLGETPROGRAMINFOLOGPROC pGetProgramInfoLog;
static PFNGLUSEPROGRAMPROC pUseProgram;
static PFNGLGETUNIFORMLOCATIONPROC pGetUniformLocation;
static PFNGLUNIFORM1IPROC pUniform1i;
static PFNGLUNIFORM1FPROC pUniform1f;
static PFNGLUNIFORM2FPROC pUniform2f;
static PFNGLGENVERTEXARRAYSPROC pGenVertexArrays;
static PFNGLBINDVERTEXARRAYPROC pBindVertexArray;
static PFNGLGENBUFFERSPROC pGenBuffers;
static PFNGLBINDBUFFERPROC pBindBuffer;
static PFNGLBUFFERDATAPROC pBufferData;
static PFNGLVERTEXATTRIBPOINTERPROC pVertexAttribPointer;
static PFNGLENABLEVERTEXATTRIBARRAYPROC pEnableVertexAttribArray;
static PFNGLGENFRAMEBUFFERSPROC pGenFramebuffers;
static PFNGLBINDFRAMEBUFFERPROC pBindFramebuffer;
static PFNGLFRAMEBUFFERTEXTURE2DPROC pFramebufferTexture2D;
static PFNGLCHECKFRAMEBUFFERSTATUSPROC pCheckFramebufferStatus;
static PFNGLGENERATEMIPMAPPROC pGenerateMipmap;
static PFNGLACTIVETEXTUREPROC pActiveTexture;

static int load_gl(void) {
#define L(v, n) do { v = (void *)SDL_GL_GetProcAddress(n); if (!v) return 0; } while (0)
    L(pCreateShader, "glCreateShader"); L(pShaderSource, "glShaderSource"); L(pCompileShader, "glCompileShader");
    L(pGetShaderiv, "glGetShaderiv"); L(pGetShaderInfoLog, "glGetShaderInfoLog"); L(pCreateProgram, "glCreateProgram");
    L(pAttachShader, "glAttachShader"); L(pBindFragDataLocationIndexed, "glBindFragDataLocationIndexed");
    L(pLinkProgram, "glLinkProgram"); L(pGetProgramiv, "glGetProgramiv"); L(pGetProgramInfoLog, "glGetProgramInfoLog");
    L(pUseProgram, "glUseProgram"); L(pGetUniformLocation, "glGetUniformLocation"); L(pUniform1i, "glUniform1i");
    L(pUniform1f, "glUniform1f"); L(pUniform2f, "glUniform2f"); L(pGenVertexArrays, "glGenVertexArrays");
    L(pBindVertexArray, "glBindVertexArray"); L(pGenBuffers, "glGenBuffers"); L(pBindBuffer, "glBindBuffer");
    L(pBufferData, "glBufferData"); L(pVertexAttribPointer, "glVertexAttribPointer");
    L(pEnableVertexAttribArray, "glEnableVertexAttribArray"); L(pGenFramebuffers, "glGenFramebuffers");
    L(pBindFramebuffer, "glBindFramebuffer"); L(pFramebufferTexture2D, "glFramebufferTexture2D");
    L(pCheckFramebufferStatus, "glCheckFramebufferStatus"); L(pGenerateMipmap, "glGenerateMipmap");
    L(pActiveTexture, "glActiveTexture");
#undef L
    return 1;
}

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *b = (char *)malloc((size_t)n + 1);
    if (b && fread(b, 1, (size_t)n, f) != (size_t)n) { free(b); b = NULL; }
    if (b) b[n] = 0;
    fclose(f);
    return b;
}

static char g_log[4096];
static GLuint compile(GLenum type, const char *src) {
    GLuint s = pCreateShader(type);
    pShaderSource(s, 1, &src, NULL);
    pCompileShader(s);
    GLint ok = 0;
    pGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) { pGetShaderInfoLog(s, sizeof g_log, NULL, g_log); return 0; }
    return s;
}

/* ---------------------------------------------------------------- synthetic class texture */
static uint8_t g_l0[HH][HW][4], g_l0_r5[HH][HW][4], g_ncls[NH][NW];
static uint8_t g_levels[(HW / 2) * (HH / 2) * 4 * 2];       /* prepared levels 1..3 (fits: 1/4 + 1/16 + 1/64) */
static double g_auth_min_luma = 1e9;
static double luma(const uint8_t *p) { return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]; }
static int in_stroke_cell(int cx, int cy) { return cy == 3 && cx >= 2 && cx <= 29; }
static int in_block_cell(int cx, int cy) { return cy >= 5 && cy <= 6 && cx >= 4 && cx <= 7; }
static void make_texture(void) {
    for (int y = 0; y < HH; y++)
        for (int x = 0; x < HW; x++) {
            uint8_t *p = g_l0[y][x];
            const int cx = x / S, cy = y / S;
            if (in_stroke_cell(cx, cy) && (y == cy * S + S / 2 || y == cy * S + S / 2 - 1)) {
                p[0] = 255; p[1] = 40; p[2] = 200; p[3] = 127;             /* 2-px neon stroke */
            } else if (in_block_cell(cx, cy)) {
                p[0] = 200; p[1] = 200; p[2] = 60; p[3] = 127;             /* opaque block */
            } else {
                p[0] = p[1] = p[2] = 0; p[3] = 0;                            /* cutout, black RGB */
            }
            if (p[3] && luma(p) < g_auth_min_luma) g_auth_min_luma = luma(p);
        }
    for (int cy = 0; cy < NH; cy++)
        for (int cx = 0; cx < NW; cx++) g_ncls[cy][cx] = (in_stroke_cell(cx, cy) || in_block_cell(cx, cy)) ? 127 : 0;
    memcpy(g_l0_r5, g_l0, sizeof g_l0);
    static int32_t q[HW * HH];
    static uint8_t d[HW * HH];
    hdcm_fill_cutout_rgb(&g_l0_r5[0][0][0], HW, HH, q, d);                  /* variant D: R5 content fix */
}

/* An in-memory prepared sidecar (offline builder output) - what the renderer's cache would hold. */
static HdcmSidecar prepared_sidecar(void) {
    static int32_t q[(HW / 2) * (HH / 2)];
    static uint8_t d[(HW / 2) * (HH / 2)];
    HdcmSidecar sc;
    memset(&sc, 0, sizeof sc);
    sc.nw = NW; sc.nh = NH; sc.s = S; sc.levels = 3; sc.hw = HW; sc.hh = HH; sc.map = &g_ncls[0][0];
    size_t off = 0;
    for (int L = 1; L <= 3; L++) {
        hdcm_build_level(&g_l0[0][0][0], HW * 4, HW, HH, &g_ncls[0][0], NW, NH, S, L, g_levels + off, q, d);
        sc.level[L] = g_levels + off;
        off += (size_t)(HW >> L) * (HH >> L) * 4;
    }
    return sc;
}

/* The renderer glue's own verifying upload (hd_class_mips_gl_upload in make_patch.GLUE): upload, then verify the
 * level by its dimensions without touching the GL error state. g_inject_bad_level forces a wrong-size upload. */
static int g_inject_bad_level = 0;
static int gl_upload_verify(void *ctx, int L, int lw, int lh, const uint8_t *rgba) {
    (void)ctx;
    const int uw = (L == g_inject_bad_level) ? lw + 1 : lw;
    glTexImage2D(GL_TEXTURE_2D, L, GL_RGBA8, uw, lh, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    GLint got_w = 0, got_h = 0;
    glGetTexLevelParameteriv(GL_TEXTURE_2D, L, GL_TEXTURE_WIDTH, &got_w);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, L, GL_TEXTURE_HEIGHT, &got_h);
    return got_w == lw && got_h == lh ? 0 : -1;
}

/* v4: an all-opaque page with varying RGB and mixed 127/255 STP (no cutout anywhere) */
static uint8_t g_opq[HH][HW][4];
static void make_opaque(void) {
    for (int y = 0; y < HH; y++)
        for (int x = 0; x < HW; x++) {
            uint8_t *p = g_opq[y][x];
            p[0] = (uint8_t)(x * 7 + y * 3); p[1] = (uint8_t)(x * 3 ^ y * 11); p[2] = (uint8_t)(255 - x - y);
            p[3] = ((x / S + y / S) & 1) ? 255 : 127;
        }
}

static GLuint make_tex(int variant /* 0 A, 1 B, 2 C/N, 3 D, 4 all-opaque level 0 */) {
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, HW, HH, 0, GL_RGBA, GL_UNSIGNED_BYTE,
                 variant == 3 ? (void *)g_l0_r5 : variant == 4 ? (void *)g_opq : (void *)g_l0);
    if (variant == 4) variant = 0;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    if (variant == 0 || variant == 3) {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    } else if (variant == 1) {
        pGenerateMipmap(GL_TEXTURE_2D);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    } else {
        const HdcmSidecar sc = prepared_sidecar();
        int uploaded = 0;
        size_t bytes = 0;
        g_inject_bad_level = 0;
        if (hdcm_upload_prepared(&sc, gl_upload_verify, NULL, &uploaded, &bytes) != HDCM_OK || uploaded != 3) return 0;
        glTexParameteri(GL_TEXTURE_2D, 0x813C /*BASE*/, 0);
        glTexParameteri(GL_TEXTURE_2D, 0x813D /*MAX*/, 3);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    }
    return t;
}

/* Fail closed on real GL (see check 7). */
static int fail_closed_on_gl(int *out_rc, int *out_uploaded, int *out_max_level) {
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, HW, HH, 0, GL_RGBA, GL_UNSIGNED_BYTE, g_l0);
    const HdcmSidecar sc = prepared_sidecar();
    size_t bytes = 0;
    g_inject_bad_level = 2;
    *out_rc = hdcm_upload_prepared(&sc, gl_upload_verify, NULL, out_uploaded, &bytes);
    g_inject_bad_level = 0;
    if (*out_rc != HDCM_OK) {                          /* the glue's restore */
        glTexParameteri(GL_TEXTURE_2D, 0x813C /*BASE*/, 0);
        glTexParameteri(GL_TEXTURE_2D, 0x813D /*MAX*/, 1000);
    }
    GLint mx = -1;
    glGetTexParameteriv(GL_TEXTURE_2D, 0x813D /*MAX*/, &mx);
    *out_max_level = mx;
    glDeleteTextures(1, &t);
    return *out_rc == HDCM_E_GL && *out_uploaded == 1 && mx == 1000;
}

/* GPU time to upload + verify a 2048^2 prepared level set (levels 1..3) through the renderer's callback. */
static double upload_timing_ms(void) {
    enum { BW = 2048, BH = 2048 };
    const size_t n1 = (size_t)(BW / 2) * (BH / 2) * 4, n2 = n1 / 4, n3 = n2 / 4;
    uint8_t *lv = (uint8_t *)malloc(n1 + n2 + n3);
    if (!lv) return -1.0;
    for (size_t i = 0; i < n1 + n2 + n3; i++) lv[i] = (uint8_t)(i * 2654435761u >> 24);
    HdcmSidecar sc;
    memset(&sc, 0, sizeof sc);
    sc.levels = 3; sc.hw = BW; sc.hh = BH; sc.level[1] = lv; sc.level[2] = lv + n1; sc.level[3] = lv + n1 + n2;
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, BW, BH, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    glFinish();
    const uint64_t t0 = SDL_GetPerformanceCounter();
    int uploaded = 0;
    size_t bytes = 0;
    const int rc = hdcm_upload_prepared(&sc, gl_upload_verify, NULL, &uploaded, &bytes);
    glFinish();
    const double ms = (double)(SDL_GetPerformanceCounter() - t0) * 1000.0 / (double)SDL_GetPerformanceFrequency();
    glDeleteTextures(1, &t);
    free(lv);
    return rc == HDCM_OK && uploaded == 3 ? ms : -1.0;
}

/* ---------------------------------------------------------------- rendering */
#define VW 288
#define VH 96
static GLuint g_prog, g_vbo, g_fbo, g_rt;
static uint8_t g_px[VH][VW][4];

static void quad(float x0, float y0, float x1, float y1) {
    const float yk = 512.0f / VH;
    const float P[6][4] = {{x0, y0, 0, 0}, {x1, y0, NW, 0}, {x0, y1, 0, NH}, {x1, y0, NW, 0}, {x1, y1, NW, NH}, {x0, y1, 0, NH}};
    float v[6 * TEXV];
    memset(v, 0, sizeof v);
    for (int i = 0; i < 6; i++) {
        float *o = &v[i * TEXV];
        o[0] = P[i][0]; o[1] = P[i][1] * yk; o[2] = P[i][2]; o[3] = P[i][3];
        o[4] = o[5] = o[6] = o[7] = 0.5f;
        o[13] = 1.0f;                                                      /* raw: no modulation */
        o[14] = 0; o[15] = 0; o[16] = NW - 1; o[17] = NH - 1;
        o[18] = 0.0f;
    }
    pBindBuffer(GL_ARRAY_BUFFER, g_vbo);
    pBufferData(GL_ARRAY_BUFFER, sizeof v, v, GL_STREAM_DRAW);
    glDrawArrays(GL_TRIANGLES, 0, 6);
}

typedef struct { int vis_min, vis_max; double vis_mean, dark_luma; } Stat;

static int g_rgb = 0;                                   /* v4: u_hd_rgb_edges for the next renders */
static void render(GLuint tex, int filter, int facade, int class_levels, double m, int ph) {
    pBindFramebuffer(GL_FRAMEBUFFER, g_fbo);
    glViewport(0, 0, VW, VH);
    glClearColor(0.0f, 1.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    pUseProgram(g_prog);
    pActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, tex);
    pUniform1i(pGetUniformLocation(g_prog, "u_filter"), filter);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_facade_motion"), facade);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_class_levels"), class_levels);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_rgb_edges"), g_rgb);
    const float off = 4.0f + (float)ph / PHASES;
    quad(off, off, off + (float)(HW / m), off + (float)(HH / m));
    glReadPixels(0, 0, VW, VH, GL_RGBA, GL_UNSIGNED_BYTE, g_px);
}
static int drawn(const uint8_t *p) { return !(p[0] == 0 && p[1] == 255 && p[2] == 0); }
static int stroke_px(void) {
    int n = 0;
    for (int y = 0; y < VH; y++)
        for (int x = 0; x < VW; x++) {
            const uint8_t *p = g_px[y][x];
            if (drawn(p) && p[0] > 60 && p[2] > 40 && p[1] < 120) n++;
        }
    return n;
}
static double dark_luma(void) {
    double d = 1e9;
    for (int y = 0; y < VH; y++)
        for (int x = 0; x < VW; x++)
            if (drawn(g_px[y][x]) && luma(g_px[y][x]) < d) d = luma(g_px[y][x]);
    return d;
}
static Stat measure(GLuint tex, int filter, int facade, int levels, double m) {
    Stat s = {1 << 30, 0, 0.0, 1e9};
    for (int ph = 0; ph < PHASES; ph++) {
        render(tex, filter, facade, levels, m, ph);
        const int n = stroke_px();
        if (n < s.vis_min) s.vis_min = n;
        if (n > s.vis_max) s.vis_max = n;
        s.vis_mean += n / (double)PHASES;
        const double d = dark_luma();
        if (d < s.dark_luma) s.dark_luma = d;
    }
    return s;
}
static int same_images(GLuint ta, int fa, int la, GLuint tb, int fb, int lb, int filter, double m) {
    static uint8_t a[VH][VW][4];
    for (int ph = 0; ph < PHASES; ph++) {
        render(ta, filter, fa, la, m, ph);
        memcpy(a, g_px, sizeof a);
        render(tb, filter, fb, lb, m, ph);
        if (memcmp(a, g_px, sizeof a)) return 0;
    }
    return 1;
}
/* v4: RGB edges on vs off on the SAME texture/path: discard support and output alpha must be identical (RGB only);
 * exact = 1 additionally requires identical RGB (all-opaque pages). */
static int rgb_support_same(GLuint t, int filter, int facade, int levels, double m, int exact) {
    static uint8_t a[VH][VW][4];
    for (int ph = 0; ph < PHASES; ph++) {
        g_rgb = 0; render(t, filter, facade, levels, m, ph);
        memcpy(a, g_px, sizeof a);
        g_rgb = 1; render(t, filter, facade, levels, m, ph);
        g_rgb = 0;
        for (int y = 0; y < VH; y++)
            for (int x = 0; x < VW; x++) {
                if (drawn(a[y][x]) != drawn(g_px[y][x]) || a[y][x][3] != g_px[y][x][3]) return 0;
                if (exact && memcmp(a[y][x], g_px[y][x], 4)) return 0;
            }
    }
    return 1;
}
static void put_stats(FILE *out, const char *name, const Stat *s, int last) {
    fprintf(out, "\"%s\": [", name);
    for (int i = 0; i < 5; i++)
        fprintf(out, "[%d, %d, %.2f, %.2f]%s", s[i].vis_min, s[i].vis_max, s[i].vis_mean, s[i].dark_luma, i < 4 ? ", " : "");
    fprintf(out, "]%s\n", last ? "" : ",");
}

int main(int argc, char **argv) {
    if (argc < 4) return 2;
    FILE *out = fopen(argv[3], "wb");
    if (!out) return 2;
    char *vs = slurp(argv[1]), *fs = slurp(argv[2]);
    int ok_link = 0, ok_uniforms = 0;
    if (!vs || !fs) { fprintf(out, "{\"error\":\"cannot read shaders\"}\n"); fclose(out); return 2; }
    if (!SDL_Init(SDL_INIT_VIDEO)) { fprintf(out, "{\"error\":\"SDL_Init\"}\n"); fclose(out); return 3; }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_Window *win = SDL_CreateWindow("hdcm-selftest", 64, 64, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    SDL_GLContext ctx = win ? SDL_GL_CreateContext(win) : NULL;
    if (!ctx || !load_gl()) { fprintf(out, "{\"error\":\"GL 3.3 core context or entry points\"}\n"); fclose(out); return 3; }
    fprintf(out, "{\n \"selftest\": \"v3\",\n \"gl_renderer\": \"%s\",\n \"gl_version\": \"%s\",\n",
            (const char *)glGetString(GL_RENDERER), (const char *)glGetString(GL_VERSION));
    GLuint v = compile(GL_VERTEX_SHADER, vs), f = v ? compile(GL_FRAGMENT_SHADER, fs) : 0;
    if (v && f) {
        g_prog = pCreateProgram();
        pAttachShader(g_prog, v); pAttachShader(g_prog, f);
        pBindFragDataLocationIndexed(g_prog, 0, 0, "frag");
        pBindFragDataLocationIndexed(g_prog, 0, 1, "blend_factor");
        pLinkProgram(g_prog);
        GLint ok = 0;
        pGetProgramiv(g_prog, GL_LINK_STATUS, &ok);
        ok_link = ok != 0;
        if (!ok) pGetProgramInfoLog(g_prog, sizeof g_log, NULL, g_log);
    }
    if (!ok_link) {
        for (char *c = g_log; *c; c++) if (*c == '"' || *c == '\\' || *c == '\n' || *c == '\r') *c = ' ';
        fprintf(out, " \"link\": false,\n \"log\": \"%s\",\n \"pass\": false\n}\n", g_log);
        fclose(out); return 1;
    }
    pUseProgram(g_prog);
    const char *need[] = {"u_hd", "u_hd_class_levels", "u_hd_facade_motion", "u_filter", "u_hd_dim", "u_xhalf",
                          "u_xscale", "u_hd_native", "u_hd_emissive"};
    ok_uniforms = 1;
    for (unsigned i = 0; i < sizeof need / sizeof need[0]; i++) ok_uniforms &= pGetUniformLocation(g_prog, need[i]) >= 0;
    pUniform1i(pGetUniformLocation(g_prog, "u_hd"), 0);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_native"), 2);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_emissive"), 3);
    GLint det = pGetUniformLocation(g_prog, "u_skin_detail");
    if (det >= 0) pUniform1i(det, 4);
    pUniform2f(pGetUniformLocation(g_prog, "u_hd_dim"), (float)NW, (float)NH);
    pUniform2f(pGetUniformLocation(g_prog, "u_hd_off_uniform"), 0.0f, 0.0f);
    pUniform1f(pGetUniformLocation(g_prog, "u_xhalf"), VW / 2.0f);
    pUniform1f(pGetUniformLocation(g_prog, "u_xscale"), 1.0f);
    GLuint dn, de, dd;
    const uint16_t z16 = 0;
    const uint8_t z8[4] = {0, 0, 0, 0};
    glGenTextures(1, &dn); pActiveTexture(GL_TEXTURE2); glBindTexture(GL_TEXTURE_2D, dn);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R16UI, 1, 1, 0, GL_RED_INTEGER, GL_UNSIGNED_SHORT, &z16);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glGenTextures(1, &de); pActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D, de);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, z8);
    glGenTextures(1, &dd); pActiveTexture(GL_TEXTURE4); glBindTexture(GL_TEXTURE_2D, dd);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, z8);
    pActiveTexture(GL_TEXTURE0);
    GLuint vao;
    pGenVertexArrays(1, &vao); pBindVertexArray(vao);
    pGenBuffers(1, &g_vbo); pBindBuffer(GL_ARRAY_BUFFER, g_vbo);
    const GLsizei st = TEXV * sizeof(float);
    const int comps[11] = {2, 2, 4, 2, 2, 1, 1, 4, 1, 1, 2}, offs[11] = {0, 2, 4, 8, 10, 12, 13, 14, 18, 19, 20};
    for (int i = 0; i < 11; i++) {
        pVertexAttribPointer((GLuint)i, comps[i], GL_FLOAT, GL_FALSE, st, (void *)(size_t)(offs[i] * sizeof(float)));
        pEnableVertexAttribArray((GLuint)i);
    }
    glGenTextures(1, &g_rt); glBindTexture(GL_TEXTURE_2D, g_rt);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, VW, VH, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    pGenFramebuffers(1, &g_fbo); pBindFramebuffer(GL_FRAMEBUFFER, g_fbo);
    pFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, g_rt, 0);
    const int fbo_ok = pCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    glDisable(GL_BLEND); glDisable(GL_DEPTH_TEST); glDisable(GL_SCISSOR_TEST);

    make_texture();
    make_opaque();
    GLuint tA = make_tex(0), tB = make_tex(1), tC = make_tex(2), tD = make_tex(3), tO = make_tex(4);
    const double ms[5] = {1, 2, 4, 8, 12};
    Stat sa[5], sb[5], sc[5], sn[5], sd[5], sar[5], scr[5], snr[5];
    for (int i = 0; i < 5; i++) {
        g_rgb = 0;
        sa[i] = measure(tA, 1, 0, 0, ms[i]);
        sb[i] = measure(tB, 1, 1, 0, ms[i]);
        sc[i] = measure(tC, 1, 1, 3, ms[i]);
        sn[i] = measure(tC, 1, 0, 3, ms[i]);
        sd[i] = measure(tD, 1, 0, 0, ms[i]);
        g_rgb = 1;                                                      /* v4 RGB-edge variants */
        sar[i] = measure(tA, 1, 0, 0, ms[i]);
        scr[i] = measure(tC, 1, 1, 3, ms[i]);
        snr[i] = measure(tC, 1, 0, 3, ms[i]);
        g_rgb = 0;
    }
    /* v4: RGB edges change RGB only (support + alpha identical), keep all-opaque pages exact, leave point mode alone */
    int rgb_support = 1, rgb_opaque_exact = 1, rgb_point = 1;
    for (int i = 0; i < 5; i++) {
        rgb_support &= rgb_support_same(tA, 1, 0, 0, ms[i], 0) && rgb_support_same(tC, 1, 1, 3, ms[i], 0) &&
                       rgb_support_same(tC, 1, 0, 3, ms[i], 0);
        rgb_opaque_exact &= rgb_support_same(tO, 1, 0, 0, ms[i], 1);
        rgb_point &= rgb_support_same(tA, 0, 0, 0, ms[i], 1) && rgb_support_same(tC, 0, 0, 3, ms[i], 1);
    }
    int point_same = 1;
    for (int i = 0; i < 4; i++) {
        point_same &= same_images(tC, 1, 3, tA, 1, 0, 0, ms[i]);
        point_same &= same_images(tC, 0, 3, tA, 0, 0, 0, ms[i]);
    }
    const int lod0_same = same_images(tC, 1, 3, tA, 0, 0, 1, 1.0) && same_images(tC, 0, 3, tA, 0, 0, 1, 1.0);
    int fc_rc = -1, fc_up = -1, fc_max = -1;
    const int fail_closed = fail_closed_on_gl(&fc_rc, &fc_up, &fc_max);
    const double up_ms = upload_timing_ms();
    const GLenum err = glGetError();

    const double lim = 0.9 * g_auth_min_luma;
    const int c2 = sc[1].vis_min > 0 && sc[2].vis_min > 0 && sc[3].vis_min > 0 &&
                   sn[1].vis_min > 0 && sn[2].vis_min > 0 && sn[3].vis_min > 0;
    int c3 = 1;
    for (int i = 1; i < 5; i++) c3 &= sc[i].dark_luma >= lim && sn[i].dark_luma >= lim;
    const int c6 = sd[0].dark_luma >= lim;
    /* v4 RGB edges: lod-0 fringe gone on A/C/N; class-level paths keep m <= s stroke and m >= 2 no-bleed */
    const int r1 = sar[0].dark_luma >= lim && scr[0].dark_luma >= lim && snr[0].dark_luma >= lim;
    int r2 = scr[1].vis_min > 0 && scr[2].vis_min > 0 && scr[3].vis_min > 0 &&
             snr[1].vis_min > 0 && snr[2].vis_min > 0 && snr[3].vis_min > 0;
    for (int i = 1; i < 5; i++) r2 &= scr[i].dark_luma >= lim && snr[i].dark_luma >= lim;
    const int pass = ok_link && ok_uniforms && fbo_ok && tC && tD && tO && err == GL_NO_ERROR && c2 && c3 && point_same &&
                     lod0_same && c6 && fail_closed && r1 && r2 && rgb_support && rgb_opaque_exact && rgb_point;
    fprintf(out, " \"link\": true,\n \"uniforms\": %s,\n \"fbo\": %s,\n \"gl_error\": %u,\n \"authored_min_luma\": %.2f,\n",
            ok_uniforms ? "true" : "false", fbo_ok ? "true" : "false", (unsigned)err, g_auth_min_luma);
    fprintf(out, " \"m\": [1, 2, 4, 8, 12],\n \"stat_fields\": \"per m: stroke pixels min, max, mean over %d phases; darkest visible luma\",\n", PHASES);
    put_stats(out, " A_level0", sa, 0);
    put_stats(out, " B_generate_mipmap_facade", sb, 0);
    put_stats(out, " C_class_levels_facade", sc, 0);
    put_stats(out, " N_class_levels_nonfacade", sn, 0);
    put_stats(out, " D_level0_r5_fill", sd, 0);
    put_stats(out, " A_level0_rgb_edges", sar, 0);
    put_stats(out, " C_class_levels_facade_rgb_edges", scr, 0);
    put_stats(out, " N_class_levels_nonfacade_rgb_edges", snr, 0);
    fprintf(out, " \"fail_closed_on_gl\": {\"rc\": %d, \"uploaded_verified\": %d, \"max_level_after_restore\": %d},\n",
            fc_rc, fc_up, fc_max);
    fprintf(out, " \"gpu_upload_verify_2048_levels1to3_ms\": %.3f,\n", up_ms);
    fprintf(out, " \"reported_only\": \"m=12 (> s) stroke; lod-0 (m=1) darkness for A/B/C/N without RGB edges; A/B numbers;"
                 " A_rgb minification (no class levels); upload ms; anisotropic edge taps (not exercised: no anisotropy here)\",\n");
    fprintf(out, " \"checks\": {\"stroke_never_vanishes_m_le_s\": %s, \"no_cutout_bleed_m_ge_2\": %s, \"point_path_unchanged\": %s,"
                 " \"lod0_identical\": %s, \"r5_variant_lod0_no_bleed\": %s, \"fail_closed_on_gl\": %s,"
                 " \"rgb_edges_lod0_fringe_gone\": %s, \"rgb_edges_class_paths_keep_scoped_goals\": %s,"
                 " \"rgb_edges_support_and_alpha_identical\": %s, \"rgb_edges_all_opaque_exact\": %s,"
                 " \"rgb_edges_point_path_unchanged\": %s},\n \"pass\": %s\n}\n",
            c2 ? "true" : "false", c3 ? "true" : "false", point_same ? "true" : "false", lod0_same ? "true" : "false",
            c6 ? "true" : "false", fail_closed ? "true" : "false", r1 ? "true" : "false", r2 ? "true" : "false",
            rgb_support ? "true" : "false", rgb_opaque_exact ? "true" : "false", rgb_point ? "true" : "false",
            pass ? "true" : "false");
    fclose(out);
    SDL_GL_DestroyContext(ctx);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return pass ? 0 : 1;
}
