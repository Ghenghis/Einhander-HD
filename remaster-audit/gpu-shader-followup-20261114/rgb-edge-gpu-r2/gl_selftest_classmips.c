/* gl_selftest_classmips.c — GPU self-test of the PRIVATE class-aware mip shader path (claude-einhander).
 *
 * BUILT on CPU by build_selftest.py; RUN BY ROOT on the GPU (never by Claude): it opens a hidden SDL3 window with
 * a GL 3.3 core context, renders offscreen and exits.
 *
 * It links the EXACT TEX_VS + HD_FS strings extracted from the preprocessed patched v61 renderer copy (argv), like
 * build_program_ex(…, dual_source = 1), and draws one textured quad (opaque, raw, no blending) of a synthetic
 * class texture: native 32 x 8 texels at scale 8 (HD 256 x 64); a 2-px neon stroke whose native cells are visible;
 * an opaque block; cutout RGB black (fringe bait). Texture variants:
 *   A  level 0 only, MIN LINEAR, u_hd_class_levels 0        (v61 without the experiment)
 *   B  glGenerateMipmap, MIN LINEAR_MIPMAP_LINEAR, levels 0 (the v61 facade/world experiment)
 *   C  class-aware levels from hd_class_mips.inc + native map, MAX_LEVEL 3, u_hd_class_levels 3 (this patch)
 * at minification m in {1, 2, 4, 8, 12} (screen px per HD px = 1/m) and 8 sub-pixel phases, read back.
 * Checks (exit 0 only if all pass):
 *   1 programs link, all needed uniforms exist, no GL error;
 *   2 C: the stroke never vanishes at m = 8 and m = 12 (min visible stroke pixels > 0 over phases);
 *   3 C: the darkest visible pixel keeps >= 90 % of the darkest authored luma (no cutout bleed);
 *   4 point path unchanged: u_filter 0 renders identically with texture C + u_hd_class_levels 3 and texture A + 0;
 *   5 at m = 1 (lod 0) C renders identically to A.
 * A and B results are recorded for comparison only. Usage: gl_selftest_classmips TEX_VS.vert HD_FS.frag out.json */
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
static uint8_t g_l0[HH][HW][4], g_ncls[NH][NW];
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
}

static GLuint make_tex(int variant /* 0 A, 1 B, 2 C */) {
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, HW, HH, 0, GL_RGBA, GL_UNSIGNED_BYTE, g_l0);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    if (variant == 0) {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    } else if (variant == 1) {
        pGenerateMipmap(GL_TEXTURE_2D);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    } else {
        static uint8_t dst[(HW / 2) * (HH / 2) * 4], done[(HW / 2) * (HH / 2)];
        static int32_t queue[(HW / 2) * (HH / 2)];
        for (int L = 1; L <= 3; L++) {
            if (hdcm_build_level(&g_l0[0][0][0], HW * 4, HW, HH, &g_ncls[0][0], NW, NH, S, L, dst, queue, done)) return 0;
            glTexImage2D(GL_TEXTURE_2D, L, GL_RGBA8, HW >> L, HH >> L, 0, GL_RGBA, GL_UNSIGNED_BYTE, dst);
        }
        glTexParameteri(GL_TEXTURE_2D, 0x813C /*BASE*/, 0);
        glTexParameteri(GL_TEXTURE_2D, 0x813D /*MAX*/, 3);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    }
    return t;
}

/* ---------------------------------------------------------------- rendering */
#define VW 288
#define VH 96
static GLuint g_prog, g_vbo, g_fbo, g_rt;
static int g_rgb_edges=1;
static uint8_t g_px[VH][VW][4];

static void quad(float x0, float y0, float x1, float y1) {
    /* two triangles; a_pos in viewport px (u_xhalf = VW/2; y maps through 512/VH), uv in native texels */
    const float yk = 512.0f / VH;
    const float P[6][4] = {{x0, y0, 0, 0}, {x1, y0, NW, 0}, {x0, y1, 0, NH}, {x1, y0, NW, 0}, {x1, y1, NW, NH}, {x0, y1, 0, NH}};
    float v[6 * TEXV];
    memset(v, 0, sizeof v);
    for (int i = 0; i < 6; i++) {
        float *o = &v[i * TEXV];
        o[0] = P[i][0]; o[1] = P[i][1] * yk; o[2] = P[i][2]; o[3] = P[i][3];
        o[4] = o[5] = o[6] = o[7] = 0.5f;          /* colour (unused: raw) */
        o[13] = 1.0f;                               /* a_raw: no modulation */
        o[14] = 0; o[15] = 0; o[16] = NW - 1; o[17] = NH - 1;   /* limits */
        o[18] = 0.0f;                               /* not semi-transparent */
    }
    pBindBuffer(GL_ARRAY_BUFFER, g_vbo);
    pBufferData(GL_ARRAY_BUFFER, sizeof v, v, GL_STREAM_DRAW);
    glDrawArrays(GL_TRIANGLES, 0, 6);
}

typedef struct { int vis_min, vis_max; double vis_mean, dark_luma; } Stat;

/* Render the quad minified by m at phase ph (x and y sub-pixel offset ph/PHASES), read back. */
static void render(GLuint tex, int filter, int class_levels, double m, int ph) {
    pBindFramebuffer(GL_FRAMEBUFFER, g_fbo);
    glViewport(0, 0, VW, VH);
    glClearColor(0.0f, 1.0f, 0.0f, 1.0f);           /* pure green = nothing drawn */
    glClear(GL_COLOR_BUFFER_BIT);
    pUseProgram(g_prog);
    pActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, tex);
    pUniform1i(pGetUniformLocation(g_prog, "u_filter"), filter);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_class_levels"), class_levels);
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_rgb_edges"), g_rgb_edges);
    const float off = 4.0f + (float)ph / PHASES;
    quad(off, off, off + (float)(HW / m), off + (float)(HH / m));
    glReadPixels(0, 0, VW, VH, GL_RGBA, GL_UNSIGNED_BYTE, g_px);
}
static int drawn(const uint8_t *p) { return !(p[0] == 0 && p[1] == 255 && p[2] == 0); }
static int stroke_px(void) {                         /* neon-ish: red and blue high, green low */
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

static Stat measure(GLuint tex, int filter, int levels, double m) {
    Stat s = {1 << 30, 0, 0.0, 1e9};
    for (int ph = 0; ph < PHASES; ph++) {
        render(tex, filter, levels, m, ph);
        const int n = stroke_px();
        if (n < s.vis_min) s.vis_min = n;
        if (n > s.vis_max) s.vis_max = n;
        s.vis_mean += n / (double)PHASES;
        const double d = dark_luma();
        if (d < s.dark_luma) s.dark_luma = d;
    }
    return s;
}

static int same_images(GLuint ta, int la, GLuint tb, int lb, int filter, double m) {
    static uint8_t a[VH][VW][4];
    for (int ph = 0; ph < PHASES; ph++) {
        render(ta, filter, la, m, ph);
        memcpy(a, g_px, sizeof a);
        render(tb, filter, lb, m, ph);
        if (memcmp(a, g_px, sizeof a)) return 0;
    }
    return 1;
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
    fprintf(out, "{\n \"gl_renderer\": \"%s\",\n \"gl_version\": \"%s\",\n",
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
    pUniform1i(pGetUniformLocation(g_prog, "u_hd_facade_motion"), 1);
    pUniform2f(pGetUniformLocation(g_prog, "u_hd_dim"), (float)NW, (float)NH);
    pUniform2f(pGetUniformLocation(g_prog, "u_hd_off_uniform"), 0.0f, 0.0f);
    pUniform1f(pGetUniformLocation(g_prog, "u_xhalf"), VW / 2.0f);
    pUniform1f(pGetUniformLocation(g_prog, "u_xscale"), 1.0f);
    /* dummy textures of the right sampler types on units 2..4 (unit 0 = u_hd) */
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
    GLuint tA = make_tex(0), tB = make_tex(1), tC = make_tex(2);
    const double ms[10] = {.5, 1, 1.125, 1.25, 1.5, 1.75, 2, 4, 8, 12};
    Stat sa[10], sb[10], sc[10];
    for (int i = 0; i < 10; i++) {
        sa[i] = measure(tA, 1, 0, ms[i]);
        sb[i] = measure(tB, 1, 0, ms[i]);
        sc[i] = measure(tC, 1, 3, ms[i]);
    }
    int point_same = 1;
    for (int i = 0; i < 10; i++) point_same &= same_images(tC, 3, tA, 0, 0, ms[i]);
    const int lod0_same = same_images(tC, 3, tA, 0, 1, 1.0);
    // Compare only support/STP alpha: RGB intentionally changes at cutout edges.
    int support_same=1; static uint8_t before[VH][VW][4];
    for(int k=0;k<10;k++) for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tC,1,3,ms[k],ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tC,1,3,ms[k],ph);
      for(int y=0;y<VH;y++)for(int x=0;x<VW;x++)
        if(drawn(before[y][x])!=drawn(g_px[y][x]) || before[y][x][3]!=g_px[y][x][3])support_same=0;
    }
    // All-opaque level0 control, mixed STP classes, varying colors. Same texture,
    // same selected class; only the RGB-only uniform changes.
    for(int y=0;y<HH;y++)for(int x=0;x<HW;x++) {
      g_l0[y][x][0]=(uint8_t)(x*3);g_l0[y][x][1]=(uint8_t)(y*3);
      g_l0[y][x][2]=(uint8_t)((x+y)*2);g_l0[y][x][3]=((x/S+y/S)&1)?255:127;
    }
    for(int y=0;y<NH;y++)for(int x=0;x<NW;x++)g_ncls[y][x]=((x+y)&1)?255:127;
    GLuint tO=make_tex(2);int opaque_max_delta=0,opaque_alpha_same=1;
    for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tO,1,3,1,ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tO,1,3,1,ph);
      for(int y=0;y<VH;y++)for(int x=0;x<VW;x++) {
        for(int c=0;c<3;c++){int delta=abs((int)before[y][x][c]-(int)g_px[y][x][c]);if(delta>opaque_max_delta)opaque_max_delta=delta;}
        if(before[y][x][3]!=g_px[y][x][3])opaque_alpha_same=0;
      }
    }
    fprintf(out," \"rgb_edge_experiment\": {\"support_and_stp_unchanged\":%s,\"opaque_lod0_max_delta\":%d,\"opaque_stp_unchanged\":%s},\n",support_same?"true":"false",opaque_max_delta,opaque_alpha_same?"true":"false");
    const GLenum err = glGetError();

    const int c2 = sc[8].vis_min > 0 && sc[9].vis_min > 0;
    int c3=1;for(int i=0;i<10;i++)c3 &= sc[i].dark_luma >= 0.9 * g_auth_min_luma;
    const int pass = ok_link && ok_uniforms && fbo_ok && tC && err == GL_NO_ERROR && c2 && c3 && point_same && lod0_same;
    fprintf(out, " \"link\": true,\n \"uniforms\": %s,\n \"fbo\": %s,\n \"gl_error\": %u,\n \"authored_min_luma\": %.2f,\n",
            ok_uniforms ? "true" : "false", fbo_ok ? "true" : "false", (unsigned)err, g_auth_min_luma);
    fprintf(out, " \"minify\": [\n");
    for (int i = 0; i < 10; i++)
        fprintf(out, "  {\"m\": %.3f, \"A_level0\": [%d, %d, %.2f, %.2f], \"B_generate_mipmap\": [%d, %d, %.2f, %.2f],"
                     " \"C_class_levels\": [%d, %d, %.2f, %.2f]}%s\n", ms[i],
                sa[i].vis_min, sa[i].vis_max, sa[i].vis_mean, sa[i].dark_luma,
                sb[i].vis_min, sb[i].vis_max, sb[i].vis_mean, sb[i].dark_luma,
                sc[i].vis_min, sc[i].vis_max, sc[i].vis_mean, sc[i].dark_luma, i < 9 ? "," : "");
    fprintf(out, " ],\n \"stat_fields\": \"stroke pixels min, max, mean over %d phases; darkest visible luma\",\n", PHASES);
    fprintf(out, " \"checks\": {\"stroke_never_vanishes_m8_m12\": %s, \"no_cutout_bleed\": %s, \"point_path_unchanged\": %s,"
                 " \"lod0_identical\": %s},\n \"pass\": %s\n}\n",
            c2 ? "true" : "false", c3 ? "true" : "false", point_same ? "true" : "false", lod0_same ? "true" : "false",
            pass ? "true" : "false");
    fclose(out);
    SDL_GL_DestroyContext(ctx);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return pass ? 0 : 1;
}
