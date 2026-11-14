/* test_hd_class_mips.c — host checks for hd_class_mips.inc v3 (prepared-level sidecars HDCMSC02, native authority,
 * fail-closed upload) (claude-einhander). Synthetic, deterministic. Test-harness output only.
 *  1 equivalence: hdcm_build_level == frozen proto-v2b cm_build_level BYTE FOR BYTE at every level with the same
 *    NATIVE map (incl. maps that differ from the HD centres), tight and strided inputs, scales 2..64;
 *  2 properties independent of the prototype (M3 never-empty, M4 == native, class-only output); 3 R5 fill;
 *  4 hash test vectors (checked by the runner against an independent Python reference) + stride independence;
 *  5 HDCMSC02: a valid sidecar parses and is admitted; every corruption is rejected with its own reason;
 *  6 prepared upload: data == prototype levels; fail closed at every level (stub GL); 7 argument validation. */
#include "class_mip.h"
#include "hd_class_mips.inc"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++g_fail; } } while (0)

static uint32_t g_rng = 0x12345678u;
static uint32_t rnd(void) { g_rng ^= g_rng << 13; g_rng ^= g_rng >> 17; g_rng ^= g_rng << 5; return g_rng; }
static uint8_t rcls(void) { const uint32_t r = rnd() % 3; return r == 0 ? 0 : (r == 1 ? 127 : 255); }

static void make_image(uint8_t *im, int w, int h, int s, uint32_t seed) {
    g_rng = seed ? seed : 1u;
    for (int cy = 0; cy < h / s; cy++)
        for (int cx = 0; cx < w / s; cx++) {
            const uint8_t base = rcls();
            for (int py = 0; py < s; py++)
                for (int px = 0; px < s; px++) {
                    uint8_t *p = &im[(((size_t)cy * s + py) * w + (size_t)cx * s + px) * 4];
                    p[0] = (uint8_t)rnd(); p[1] = (uint8_t)rnd(); p[2] = (uint8_t)rnd(); p[3] = base;
                }
        }
    const int blobs = (w * h) / (s * s) + 4;
    for (int b = 0; b < blobs; b++) {
        const int x0 = (int)(rnd() % (uint32_t)w), y0 = (int)(rnd() % (uint32_t)h), rad = (int)(rnd() % (uint32_t)(s + 1));
        const uint8_t a = rcls();
        const int stroke = (int)(rnd() % 2);
        for (int y = y0 - rad; y <= y0 + rad; y++)
            for (int x = x0 - rad; x <= x0 + rad; x++) {
                if (x < 0 || y < 0 || x >= w || y >= h) continue;
                const int in = stroke ? (y == y0) : ((x - x0) * (x - x0) + (y - y0) * (y - y0) <= rad * rad);
                if (in) im[((size_t)y * w + x) * 4 + 3] = a;
            }
    }
}

static int equivalence(int tw, int th, int s, uint32_t seed, int pad, int native_differs) {
    const int w = tw * s, h = th * s;
    const size_t stride = (size_t)w * 4 + (size_t)pad;
    uint8_t *im = (uint8_t *)malloc((size_t)w * h * 4), *ims = (uint8_t *)malloc(stride * h + 1);
    uint8_t *ncls = (uint8_t *)malloc((size_t)tw * th);
    uint8_t *a = (uint8_t *)malloc((size_t)w * h * 4), *b = (uint8_t *)malloc((size_t)w * h * 4);
    int32_t *queue = (int32_t *)malloc((size_t)w * h * sizeof(int32_t));
    uint8_t *done = (uint8_t *)malloc((size_t)w * h);
    make_image(im, w, h, s, seed);
    memset(ims, 0xA5, stride * h + 1);
    for (int y = 0; y < h; y++) memcpy(ims + (size_t)y * stride, im + (size_t)y * w * 4, (size_t)w * 4);
    for (int cy = 0; cy < th; cy++)
        for (int cx = 0; cx < tw; cx++) {
            const uint8_t c = hdcm_class(im[(((size_t)cy * s + s / 2) * w + (size_t)cx * s + s / 2) * 4 + 3]);
            ncls[cy * tw + cx] = native_differs && ((cx + cy) % 3 == 0) ? (uint8_t)(c == 0 ? 127 : (c == 127 ? 255 : 0)) : c;
        }
    int diff_levels = 0;
    const int nl = hdcm_levels_for_scale(s);
    for (int L = 1; L <= nl; L++) {
        const int lw = w >> L, lh = h >> L;
        memset(a, 0x5A, (size_t)lw * lh * 4); memset(b, 0xC3, (size_t)lw * lh * 4);
        CHECK(cm_build_level(im, w, h, ncls, tw, th, s, L, a) == 0);
        CHECK(hdcm_build_level(ims, stride, w, h, ncls, tw, th, s, L, b, queue, done) == 0);
        const int same = memcmp(a, b, (size_t)lw * lh * 4) == 0;
        CHECK(same);
        diff_levels += !same;
        const int cs = s >> L;
        for (int cy = 0; cy < th; cy++)
            for (int cx = 0; cx < tw; cx++) {
                int visL = 0;
                for (int ty = 0; ty < cs; ty++)
                    for (int tx = 0; tx < cs; tx++) {
                        const uint8_t al = b[(((size_t)cy * cs + ty) * lw + (size_t)cx * cs + tx) * 4 + 3];
                        visL += al != 0;
                        if (!(al == 0 || al == 127 || al == 255)) CHECK(!"non-class alpha in a level");
                    }
                if (ncls[cy * tw + cx]) CHECK(visL >= 1);
                if (L == nl) CHECK(b[((size_t)cy * lw + cx) * 4 + 3] == ncls[cy * tw + cx]);
            }
    }
    free(im); free(ims); free(ncls); free(a); free(b); free(queue); free(done);
    return diff_levels;
}

static void fill_property(void) {
    uint8_t im[5 * 4] = {255, 0, 0, 127, 9, 9, 9, 0, 9, 9, 9, 0, 9, 9, 9, 0, 0, 0, 255, 255};
    int32_t q[5]; uint8_t d[5];
    hdcm_fill_cutout_rgb(im, 5, 1, q, d);
    CHECK(im[4] == 255 && im[6] == 0 && im[12] == 0 && im[14] == 255 && im[8] == 255);
    CHECK(im[3] == 127 && im[7] == 0 && im[19] == 255);
    CHECK(im[0] == 255 && im[16] == 0 && im[18] == 255);
}

static void hash_vectors(void) {
    uint8_t buf[64 * 3 + 16];
    for (int i = 0; i < (int)sizeof buf; i++) buf[i] = (uint8_t)(i * 37 + 11);
    printf("HASHVEC empty %016llx\n", (unsigned long long)hdcm_hash64(buf, 0, 0, 0));
    printf("HASHVEC one13 %016llx\n", (unsigned long long)hdcm_hash64(buf, 13, 13, 1));
    printf("HASHVEC rows3x20s24 %016llx\n", (unsigned long long)hdcm_hash64(buf, 24, 20, 3));
    printf("HASHVEC rows3x64s64 %016llx\n", (unsigned long long)hdcm_hash64(buf, 64, 64, 3));
    uint8_t tight[16 * 4 * 3], pad[(16 * 4 + 8) * 3];
    for (int i = 0; i < (int)sizeof tight; i++) tight[i] = (uint8_t)(i ^ 0x5A);
    memset(pad, 0xEE, sizeof pad);
    for (int r = 0; r < 3; r++) memcpy(pad + r * (16 * 4 + 8), tight + r * 64, 64);
    CHECK(hdcm_hash64(tight, 64, 64, 3) == hdcm_hash64(pad, 72, 64, 3));
    tight[100] ^= 1;
    CHECK(hdcm_hash64(tight, 64, 64, 3) != hdcm_hash64(pad, 72, 64, 3));
}

/* --- HDCMSC02 writer for the tests (the offline tool writes the same layout) --- */
static void wr16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void wr32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static void wr64(uint8_t *p, uint64_t v) { for (int i = 0; i < 8; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static void reseal(uint8_t *sc, size_t len) { wr64(sc + len - 8, hdcm_hash64(sc, len - 8, (uint32_t)(len - 8), 1)); }
static size_t make_sc2(uint8_t *out, uint32_t th, uint32_t ph, const uint8_t *im, int nw, int nh, int s,
                       const uint8_t *ncls, uint32_t flags) {
    const int w = nw * s, h = nh * s, L = hdcm_levels_for_scale(s);
    memset(out, 0, HDCM_SC2_HEADER);
    memcpy(out, "HDCMSC02", 8);
    wr32(out + 8, th); wr32(out + 12, ph);
    wr16(out + 16, (uint32_t)nw); wr16(out + 18, (uint32_t)nh); wr16(out + 20, (uint32_t)s); wr16(out + 22, (uint32_t)L);
    wr32(out + 24, (uint32_t)w); wr32(out + 28, (uint32_t)h);
    wr64(out + 32, hdcm_hash64(im, (size_t)w * 4, (uint32_t)w * 4, (uint32_t)h));
    wr32(out + 40, (uint32_t)(nw * nh)); wr32(out + 44, flags);
    memcpy(out + HDCM_SC2_HEADER, ncls, (size_t)nw * nh);
    size_t off = HDCM_SC2_HEADER + (size_t)nw * nh;
    uint64_t total = 0;
    int32_t *q = (int32_t *)malloc((size_t)w * h * sizeof(int32_t));
    uint8_t *dn = (uint8_t *)malloc((size_t)w * h);
    for (int l = 1; l <= L; l++) {
        const int lw = w >> l, lh = h >> l;
        CHECK(hdcm_build_level(im, (size_t)w * 4, w, h, ncls, nw, nh, s, l, out + off, q, dn) == 0);
        wr64(out + 56 + 8 * (l - 1), hdcm_hash64(out + off, (size_t)lw * 4, (uint32_t)lw * 4, (uint32_t)lh));
        off += (size_t)lw * lh * 4;
        total += (uint64_t)lw * lh * 4;
    }
    free(q); free(dn);
    wr64(out + 48, total);
    wr64(out + off, hdcm_hash64(out, off, (uint32_t)off, 1));
    return off + 8;
}

/* --- fail-closed prepared upload with an injected (stub) GL upload --- */
typedef struct {
    int fail_at, calls, mismatches, bad_dims;
    const uint8_t *im, *ncls;
    int w, h, nw, nh, s;
} UpCtx;
static int stub_upload(void *vctx, int L, int lw, int lh, const uint8_t *rgba) {
    UpCtx *c = (UpCtx *)vctx;
    c->calls++;
    if (lw != c->w >> L || lh != c->h >> L) c->bad_dims++;
    uint8_t *ref = (uint8_t *)malloc((size_t)lw * lh * 4);
    if (cm_build_level(c->im, c->w, c->h, c->ncls, c->nw, c->nh, c->s, L, ref) != 0 ||
        memcmp(ref, rgba, (size_t)lw * lh * 4)) c->mismatches++;           /* uploaded data == prototype level */
    free(ref);
    return L == c->fail_at ? -1 : 0;                                       /* injected GL upload failure */
}
static void upload_prepared(const HdcmSidecar *p, const uint8_t *im, const uint8_t *ncls) {
    const int w = (int)p->hw, h = (int)p->hh;
    size_t all = 0;
    for (int L = 1; L <= p->levels; L++) all += (size_t)(w >> L) * (h >> L) * 4;
    for (int fail_at = 0; fail_at <= p->levels; fail_at++) {
        UpCtx c = {fail_at, 0, 0, 0, im, ncls, w, h, p->nw, p->nh, p->s};
        int up = -7; size_t bytes = 99;
        const int rc = hdcm_upload_prepared(p, stub_upload, &c, &up, &bytes);
        CHECK(c.mismatches == 0 && c.bad_dims == 0);
        if (fail_at == 0) {
            CHECK(rc == HDCM_OK && up == p->levels && bytes == all && c.calls == p->levels);
        } else {
            size_t ok_bytes = 0;
            for (int L = 1; L < fail_at; L++) ok_bytes += (size_t)(w >> L) * (h >> L) * 4;
            CHECK(rc == HDCM_E_GL);
            CHECK(up == fail_at - 1 && bytes == ok_bytes);
            CHECK(c.calls == fail_at);
        }
    }
    int up = 5; size_t bytes = 5;
    CHECK(hdcm_upload_prepared(p, NULL, NULL, &up, &bytes) == HDCM_E_BUILD && up == 0 && bytes == 0);
}

static void sidecar(void) {
    enum { NW = 12, NH = 6, S = 8, W = NW * S, H = NH * S };
    uint8_t *im = (uint8_t *)malloc((size_t)W * H * 4), ncls[NW * NH];
    make_image(im, W, H, S, 4242u);
    for (int cy = 0; cy < NH; cy++)
        for (int cx = 0; cx < NW; cx++)
            ncls[cy * NW + cx] = hdcm_class(im[(((size_t)cy * S + S / 2) * W + (size_t)cx * S + S / 2) * 4 + 3]);
    const uint64_t l0 = hdcm_hash64(im, (size_t)W * 4, W * 4, H);
    static uint8_t sc[1 << 16], bad[(1 << 16) + 16];
    const size_t len = make_sc2(sc, 0x95A3BCF8u, 0x60245B3Au, im, NW, NH, S, ncls, HDCM_FLAG_R1_VERIFIED);
    const size_t map0 = HDCM_SC2_HEADER, lev1 = HDCM_SC2_HEADER + NW * NH;
    const size_t lev3 = lev1 + (size_t)(W / 2) * (H / 2) * 4 + (size_t)(W / 4) * (H / 4) * 4;
    HdcmSidecar p;
    CHECK(hdcm_sidecar2_parse(sc, len, &p) == HDCM_OK);
    CHECK(hdcm_sidecar_admit(&p, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H) == HDCM_OK);
    CHECK(p.levels == 3 && p.level[1] == sc + lev1 && p.level[3] == sc + lev3);
#define REJECT(edit, expect) do { memcpy(bad, sc, len); size_t bl = len; edit; \
        HdcmSidecar bp; int rc = hdcm_sidecar2_parse(bad, bl, &bp); \
        if (rc == HDCM_OK) rc = hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H); \
        CHECK(rc == (expect)); } while (0)
    REJECT(bl = 20, HDCM_E_SIZE);
    REJECT(bl = len - 1, HDCM_E_SIZE);
    REJECT((bad[0] = 'X', reseal(bad, bl)), HDCM_E_MAGIC);
    REJECT(bad[map0 + 3] ^= 0x80, HDCM_E_SELFHASH);                                      /* no reseal */
    REJECT((wr32(bad + 8, 0x95A3BCF9u), reseal(bad, bl)), HDCM_E_KEY);
    REJECT((wr32(bad + 12, 0x07A9568Du), reseal(bad, bl)), HDCM_E_KEY);
    REJECT((wr16(bad + 20, 6), reseal(bad, bl)), HDCM_E_SCALE);
    REJECT((wr32(bad + 24, NW * S + 8), reseal(bad, bl)), HDCM_E_SCALE);
    REJECT((wr16(bad + 22, 2), reseal(bad, bl)), HDCM_E_LEVELS);
    REJECT((wr32(bad + 44, 0), reseal(bad, bl)), HDCM_E_FLAGS);
    REJECT((wr32(bad + 44, HDCM_FLAG_R1_VERIFIED | 4u), reseal(bad, bl)), HDCM_E_FLAGS);      /* unknown flag bit */
    { /* v4 has-cutout flag: accepted, and readable after parse */
        memcpy(bad, sc, len);
        wr32(bad + 44, HDCM_FLAG_R1_VERIFIED | HDCM_FLAG_HAS_CUTOUT);
        reseal(bad, len);
        HdcmSidecar bp;
        CHECK(hdcm_sidecar2_parse(bad, len, &bp) == HDCM_OK && (bp.flags & HDCM_FLAG_HAS_CUTOUT));
        CHECK(hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H) == HDCM_OK);
    }
    REJECT((bad[map0 + 5] = 128, reseal(bad, bl)), HDCM_E_CLASS);
    REJECT((bad[lev1 + 9] ^= 1, reseal(bad, bl)), HDCM_E_LEVELHASH);                     /* level byte, hash stale */
    REJECT((wr64(bad + 32, l0 ^ 1), reseal(bad, bl)), HDCM_E_LEVEL0);
    { /* a non-class alpha in level 1 with its hash recomputed -> LEVELDATA */
        memcpy(bad, sc, len);
        size_t i = 0;
        while (bad[lev1 + i * 4 + 3] == 0) i++;
        bad[lev1 + i * 4 + 3] = 200;
        wr64(bad + 56, hdcm_hash64(bad + lev1, (size_t)(W / 2) * 4, (W / 2) * 4, H / 2));
        reseal(bad, len);
        HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(bad, len, &bp) == HDCM_E_LEVELDATA);
    }
    { /* M4: last level differs from the native map (valid class, hash recomputed) -> LEVELDATA */
        memcpy(bad, sc, len);
        bad[lev3 + 3] = ncls[0] == 255 ? 127 : 255;
        wr64(bad + 56 + 16, hdcm_hash64(bad + lev3, (size_t)(W / 8) * 4, (W / 8) * 4, H / 8));
        reseal(bad, len);
        HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(bad, len, &bp) == HDCM_E_LEVELDATA);
    }
    { /* level-byte total inflated by 4 with 4 extra bytes before the self-hash -> SIZE */
        memcpy(bad, sc, len - 8);
        memset(bad + len - 8, 0, 4);
        wr64(bad + 48, hdcm_rd64(sc + 48) + 4);
        const size_t bl = len + 4;
        reseal(bad, bl);
        HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(bad, bl, &bp) == HDCM_E_SIZE);
    }
    { HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(sc, len, &bp) == HDCM_OK);
      CHECK(hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW + 1, NH, im, (size_t)W * 4, W, H) == HDCM_E_NATIVE_DIMS);
      CHECK(hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H - S) == HDCM_E_HD_DIMS); }
    { uint8_t keep = im[1000]; im[1000] ^= 1; HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(sc, len, &bp) == HDCM_OK);
      CHECK(hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H) == HDCM_E_LEVEL0);
      im[1000] = keep; }
    { /* a self-consistent sidecar (levels built from its own map) whose map disagrees with a centre -> R1 */
      uint8_t n2[NW * NH]; memcpy(n2, ncls, sizeof n2); n2[7] = ncls[7] == 0 ? 127 : 0;
      static uint8_t s2[1 << 16];
      const size_t l2 = make_sc2(s2, 0x95A3BCF8u, 0x60245B3Au, im, NW, NH, S, n2, HDCM_FLAG_R1_VERIFIED);
      HdcmSidecar bp; CHECK(hdcm_sidecar2_parse(s2, l2, &bp) == HDCM_OK);
      CHECK(hdcm_sidecar_admit(&bp, 0x95A3BCF8u, 0x60245B3Au, NW, NH, im, (size_t)W * 4, W, H) == HDCM_E_R1); }
    CHECK(hdcm_sidecar2_parse(NULL, len, &p) == HDCM_E_SIZE);
    CHECK(hdcm_sidecar2_parse(sc, HDCM_SC2_MAX + 1, &p) == HDCM_E_SIZE);
#undef REJECT
    CHECK(hdcm_sidecar2_parse(sc, len, &p) == HDCM_OK);
    upload_prepared(&p, im, ncls);
    /* bounded preload cache */
    HdcmCache c;
    hdcm_cache_init(&c, (size_t)len * 3);                          /* byte cap: room for exactly 3 */
    for (uint32_t k = 0; k < 4; k++) {
        uint8_t *b = (uint8_t *)malloc(len);
        const size_t lk = make_sc2(b, 0x95A3BCF8u, 0x60245B30u + k, im, NW, NH, S, ncls, HDCM_FLAG_R1_VERIFIED);
        CHECK(lk == len);
        const int rc = hdcm_cache_add(&c, 0x95A3BCF8u, 0x60245B30u + k, b, lk);
        CHECK(k < 3 ? rc == HDCM_OK : rc == HDCM_E_ALLOC);         /* 4th exceeds the byte cap (freed) */
    }
    CHECK(c.n == 3 && c.bytes == len * 3 && c.bytes <= c.cap_bytes);
    CHECK(hdcm_cache_find(&c, 0x95A3BCF8u, 0x60245B31u) != NULL && hdcm_cache_find(&c, 0x95A3BCF8u, 0x60245B33u) == NULL);
    HdcmCache c2;
    hdcm_cache_init(&c2, (size_t)1 << 30);
    for (uint32_t k = 0; k < HDCM_CACHE_MAX + 1; k++) {            /* entry cap */
        uint8_t *b = (uint8_t *)malloc(len);
        make_sc2(b, 1u, 100u + k, im, NW, NH, S, ncls, HDCM_FLAG_R1_VERIFIED);
        const int rc = hdcm_cache_add(&c2, 1u, 100u + k, b, len);
        CHECK(k < HDCM_CACHE_MAX ? rc == HDCM_OK : rc == HDCM_E_ALLOC);
    }
    CHECK(c2.n == HDCM_CACHE_MAX);
    { HdcmCache c3; hdcm_cache_init(&c3, (size_t)1 << 30);
      uint8_t *b1 = (uint8_t *)malloc(len), *b2 = (uint8_t *)malloc(len), *b3 = (uint8_t *)malloc(len), *b4 = (uint8_t *)malloc(len);
      memcpy(b1, sc, len); memcpy(b2, sc, len); memcpy(b3, sc, len); memcpy(b4, sc, len);
      b4[map0 + 3] ^= 0x80;                                         /* corrupt -> rejected and freed */
      CHECK(hdcm_cache_add(&c3, 0x95A3BCF8u, 0x60245B3Au, b1, len) == HDCM_OK);
      CHECK(hdcm_cache_add(&c3, 0x95A3BCF8u, 0x60245B3Au, b2, len) == HDCM_E_KEY);       /* duplicate */
      CHECK(hdcm_cache_add(&c3, 0x95A3BCF8u, 0x07A9568Du, b3, len) == HDCM_E_KEY);       /* file key != index key */
      CHECK(hdcm_cache_add(&c3, 0x11111111u, 0x22222222u, b4, len) == HDCM_E_SELFHASH);
      CHECK(hdcm_cache_add(&c3, 1u, 2u, NULL, len) == HDCM_E_ALLOC);
      CHECK(c3.n == 1);
      free(c3.e[0].buf); }
    for (int i = 0; i < c.n; i++) free(c.e[i].buf);
    for (int i = 0; i < c2.n; i++) free(c2.e[i].buf);
    free(im);
}

static void args(void) {
    uint8_t im[16 * 16 * 4] = {0}, dst[8 * 8 * 4], n[4] = {0, 127, 255, 0};
    int32_t q[64]; uint8_t d[64];
    CHECK(hdcm_levels_for_scale(1) == 0 && hdcm_levels_for_scale(3) == 0 && hdcm_levels_for_scale(6) == 0);
    CHECK(hdcm_levels_for_scale(2) == 1 && hdcm_levels_for_scale(16) == 4 && hdcm_levels_for_scale(64) == 6);
    CHECK(hdcm_levels_for_scale(128) == 0);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, 0, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, 4, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, 32, dst, q, d) == -1);   /* rejected before any shift */
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, INT_MAX, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, INT_MIN, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 60, 16, 16, n, 2, 2, 8, 1, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 6, 1, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 3, 2, 8, 1, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, NULL, 2, 2, 8, 1, dst, q, d) == -1);
    CHECK(hdcm_build_level(im, 64, 16, 16, n, 2, 2, 8, 1, dst, q, d) == 0);
    HdcmSidecar z; memset(&z, 0, sizeof z); int up; size_t by;
    z.levels = 7;                                                               /* > HDCM_MAX_LEVELS */
    CHECK(hdcm_upload_prepared(&z, (hdcm_upload_fn)stub_upload, NULL, &up, &by) == HDCM_E_BUILD);
}

int main(void) {
    int diff = 0;
    const int scales[4] = {2, 4, 8, 16};
    for (int si = 0; si < 4; si++)
        for (uint32_t seed = 1; seed <= 6; seed++) {
            diff += equivalence(9, 5, scales[si], seed * 7919u + (uint32_t)si, 0, 0);
            diff += equivalence(7, 6, scales[si], seed * 104729u + (uint32_t)si, (int)(seed % 3) * 12, (int)(seed & 1));
        }
    diff += equivalence(3, 2, 32, 99u, 20, 1);
    diff += equivalence(2, 2, 64, 77u, 4, 0);
    fill_property();
    hash_vectors();
    sidecar();
    args();
    printf("METRIC equivalence_levels_differing %d\n", diff);
    printf("checks %d failures %d\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
