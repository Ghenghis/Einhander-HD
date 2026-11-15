/* hdcm_tool.c — host DLL for the offline prepared-sidecar writer and the real-page checks (claude-einhander).
 * Decodes PNGs with the SAME stb_image as the runtime (third_party/stb_image.h sha256 866095d4..., runtime defines
 * STBI_ONLY_PNG + STBI_NO_STDIO, 4 components like hd_texture_pack.cpp), so the level-0 hash bound into a sidecar is
 * the hash of exactly what the renderer receives. Everything else is hd_class_mips.inc (builder included: host
 * tooling only). Timings use QueryPerformanceCounter around the exact functions the runtime calls. */
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#define STBI_NO_STDIO
#include "stb_image.h"
#include "hd_class_mips.inc"

#include <windows.h>

#define HDCM_TOOL_API __declspec(dllexport)

static double ms_since(LARGE_INTEGER t0) {
    LARGE_INTEGER t1, f;
    QueryPerformanceCounter(&t1);
    QueryPerformanceFrequency(&f);
    return (double)(t1.QuadPart - t0.QuadPart) * 1000.0 / (double)f.QuadPart;
}

/* Decode a PNG to RGBA8 into out (cap bytes). Returns 0 ok, -1 decode failure, -2 out too small. */
HDCM_TOOL_API int hdcm_tool_decode(const uint8_t *png, int len, uint8_t *out, size_t cap, int *w, int *h) {
    int c = 0;
    stbi_uc *p = stbi_load_from_memory(png, len, w, h, &c, 4);
    if (!p) return -1;
    const size_t need = (size_t)(*w) * (size_t)(*h) * 4u;
    if (need > cap) { stbi_image_free(p); return -2; }
    memcpy(out, p, need);
    stbi_image_free(p);
    return 0;
}

HDCM_TOOL_API uint64_t hdcm_tool_hash(const uint8_t *p, size_t stride, uint32_t row_bytes, uint32_t rows) {
    return hdcm_hash64(p, stride, row_bytes, rows);
}

/* Preload verification (renderer init) then draw-thread admission, each timed. Returns HDCM_OK or the reason. */
HDCM_TOOL_API int hdcm_tool_parse_admit(const uint8_t *sc, size_t len, uint32_t th, uint32_t ph, uint32_t nw, uint32_t nh,
                                        const uint8_t *rgba, size_t stride, uint32_t w, uint32_t h,
                                        double *parse_ms, double *admit_ms) {
    HdcmSidecar s;
    LARGE_INTEGER t0;
    QueryPerformanceCounter(&t0);
    int rc = hdcm_sidecar2_parse(sc, len, &s);
    if (parse_ms) *parse_ms = ms_since(t0);
    if (admit_ms) *admit_ms = 0.0;
    if (rc == HDCM_OK) {
        QueryPerformanceCounter(&t0);
        rc = hdcm_sidecar_admit(&s, th, ph, nw, nh, rgba, stride, w, h);
        if (admit_ms) *admit_ms = ms_since(t0);
    }
    return rc;
}

/* Copy the prepared levels out of a sidecar exactly as hdcm_upload_prepared hands them to GL (memcpy stands in for
 * glTexImage2D); returns levels copied or -reason. Lets the host check the bytes the renderer would upload. */
static uint8_t *g_copy_dst;
static int copy_level(void *ctx, int L, int lw, int lh, const uint8_t *rgba) {
    size_t *off = (size_t *)ctx;
    (void)L;
    memcpy(g_copy_dst + *off, rgba, (size_t)lw * lh * 4u);
    *off += (size_t)lw * lh * 4u;
    return 0;
}
HDCM_TOOL_API int hdcm_tool_prepared_levels(const uint8_t *sc, size_t len, uint8_t *dst) {
    HdcmSidecar s;
    int rc = hdcm_sidecar2_parse(sc, len, &s);
    if (rc != HDCM_OK) return -rc;
    size_t off = 0, bytes = 0;
    int uploaded = 0;
    g_copy_dst = dst;
    rc = hdcm_upload_prepared(&s, copy_level, &off, &uploaded, &bytes);
    return rc == HDCM_OK ? uploaded : -rc;
}

HDCM_TOOL_API int hdcm_tool_build_level(const uint8_t *lvl0, size_t stride, int w, int h, const uint8_t *ncls, int tw,
                                        int th, int s, int L, uint8_t *dst, int32_t *queue, uint8_t *done) {
    return hdcm_build_level(lvl0, stride, w, h, ncls, tw, th, s, L, dst, queue, done);
}

/* v5 RGB-only sidecar (HDCMRG01): parse + draw-time admission exactly as the runtime glue calls them, timed. Also
 * reports the runtime's own has-cutout truth for the pixels (hdcm_hash64_cutout). */
HDCM_TOOL_API int hdcm_tool_rgb_parse_admit(const uint8_t *buf, size_t len, uint32_t th, uint32_t ph, uint32_t nw,
                                            uint32_t nh, const uint8_t *rgba, size_t stride, uint32_t w, uint32_t h,
                                            int *has_cutout, double *admit_ms) {
    HdcmRgbSidecar s;
    int rc = hdcm_rgb_parse(buf, len, &s);
    if (has_cutout) {
        int cut = 0;
        (void)hdcm_rgb_level0(rgba, stride, w, h, &cut);
        *has_cutout = cut;
    }
    if (admit_ms) *admit_ms = 0.0;
    if (rc == HDCM_OK) {
        LARGE_INTEGER t0;
        QueryPerformanceCounter(&t0);
        rc = hdcm_rgb_admit(&s, th, ph, nw, nh, rgba, stride, w, h);
        if (admit_ms) *admit_ms = ms_since(t0);
    }
    return rc;
}
HDCM_TOOL_API int hdcm_tool_rgb_bytes(void) { return HDCM_RG_BYTES; }
/* The v5 RGB-only level-0 identity (HDCM-X4) for the offline writer; also returns the runtime's cutout truth. */
HDCM_TOOL_API uint64_t hdcm_tool_rgb_level0(const uint8_t *rgba, size_t stride, uint32_t w, uint32_t h, int *has_cutout) {
    int cut = 0;
    const uint64_t v = hdcm_rgb_level0(rgba, stride, w, h, &cut);
    if (has_cutout) *has_cutout = cut;
    return v;
}
/* Throughput probe: the single-chain v5-run-1 hash (hdcm_hash64) vs HDCM-X4 on the same pixels, best of `reps`. */
HDCM_TOOL_API void hdcm_tool_hash_speed(const uint8_t *rgba, size_t stride, uint32_t w, uint32_t h, int reps,
                                        double *single_ms, double *x4_ms) {
    double b1 = 1e30, b4 = 1e30;
    volatile uint64_t sink = 0;
    for (int i = 0; i < reps; i++) {
        LARGE_INTEGER t0;
        QueryPerformanceCounter(&t0);
        sink ^= hdcm_hash64(rgba, stride, w * 4u, h);
        const double a = ms_since(t0);
        int cut = 0;
        QueryPerformanceCounter(&t0);
        sink ^= hdcm_rgb_level0(rgba, stride, w, h, &cut);
        const double b = ms_since(t0);
        if (a < b1) b1 = a;
        if (b < b4) b4 = b;
    }
    (void)sink;
    *single_ms = b1;
    *x4_ms = b4;
}

HDCM_TOOL_API int hdcm_tool_reasons(void) { return HDCM_REASONS; }
HDCM_TOOL_API int hdcm_tool_header_bytes(void) { return HDCM_SC2_HEADER; }
