/* hd_class_mips.inc — PRIVATE, opt-in class-aware HD mip levels with hash-bound NATIVE authority and PREPARED
 * levels (claude-einhander, renderer-v61-classmip; design DESIGN-V3.md).
 *
 * v3 (root msg_28928d65): levels are built OFFLINE (host tool) into the sidecar; the runtime never builds. The
 * renderer includes this file with HDCM_NO_BUILDER defined, so the builder below does not even exist in the runtime
 * translation unit. Runtime work: parse+verify sidecars at init (preload), then at first draw validate level-0 identity
 * and upload the prepared levels with verification (fail closed).
 *
 * Authority: the native class of every cell comes from the CRC-proven native words + CLUT (offline), never from HD
 * pixels. The sidecar binds native key, native dims, scale, HD dims, a 64-bit hash of the exact decoded level-0
 * RGBA, a per-level hash and length; parse checks every level class and that the last level equals the native map
 * (M4); admission re-checks R1 (every level-0 centre pixel has the native class).
 *
 * Levels (built offline by hdcm_build_level, a port of class-mip proto-v2b cm_build_level, byte-identical):
 *   M1 a level-L texel never mixes two native cells (L <= log2 s); M2 RGB = mean of VISIBLE level-0 pixels;
 *   M3 visible-texel count preserves the cell's coverage, a visible native cell keeps >= 1 visible texel,
 *   STP by majority (ties -> native); M4 level log2(s) == native classes; R5 cutout RGB = nearest visible RGB.
 * Alpha is a PS1 class (0 cutout, 127 STP clear, 255 STP set). No GL, no printing, no globals. */
#ifndef HD_CLASS_MIPS_INC
#define HD_CLASS_MIPS_INC
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define HDCM_MAX_CELL 64                       /* largest supported native -> HD scale            */
#define HDCM_MAX_NATIVE 256                    /* a PS1 texture page is at most 256 x 256 texels  */
#define HDCM_MAX_LEVELS 6                      /* log2(HDCM_MAX_CELL)                             */
#define HDCM_SC2_HEADER 104
#define HDCM_SC2_MAX_LEVEL_BYTES ((uint64_t)32 * 1024 * 1024)
#define HDCM_SC2_MAX ((size_t)HDCM_SC2_HEADER + HDCM_MAX_NATIVE * HDCM_MAX_NATIVE + HDCM_SC2_MAX_LEVEL_BYTES + 8)
#define HDCM_FLAG_R1_VERIFIED 1u

enum {
    HDCM_OK = 0,
    HDCM_E_NOFILE,      /* no prepared sidecar for this key (not admitted)       */
    HDCM_E_SIZE,        /* sidecar length wrong / over the cap                   */
    HDCM_E_MAGIC,
    HDCM_E_SELFHASH,    /* sidecar bytes corrupted                               */
    HDCM_E_KEY,         /* texture/palette hash differs                          */
    HDCM_E_NATIVE_DIMS, /* native w/h differ from the draw's upload              */
    HDCM_E_HD_DIMS,     /* decoded level-0 w/h differ from the sidecar           */
    HDCM_E_SCALE,       /* scale not a power of two in 2..64, or w != nw * s     */
    HDCM_E_LEVELS,      /* levels != log2(scale)                                 */
    HDCM_E_FLAGS,       /* R1 not verified offline                               */
    HDCM_E_CLASS,       /* a native class outside {0,127,255}                    */
    HDCM_E_LEVEL0,      /* decoded level-0 RGBA hash differs                     */
    HDCM_E_R1,          /* a level-0 centre pixel disagrees with the native map  */
    HDCM_E_ALLOC,       /* allocation / cache capacity                           */
    HDCM_E_BUILD,       /* level build failed (offline tool, internal)           */
    HDCM_E_GL,          /* a level upload could not be verified (fail closed)    */
    HDCM_E_LEVELHASH,   /* a prepared level's bytes do not match its hash        */
    HDCM_E_LEVELDATA,   /* a prepared level holds a non-class alpha, or the last
                         * level differs from the native map (M4)                */
    HDCM_REASONS
};

static uint8_t hdcm_class(uint8_t a) { return a == 0 ? 0 : (a >= 128 ? 255 : 127); }

/* log2(s) for a supported power-of-two scale, else 0. */
static int hdcm_levels_for_scale(int s) {
    int L = 0;
    if (s < 2 || s > HDCM_MAX_CELL || (s & (s - 1))) return 0;
    while ((1 << L) < s) L++;
    return L;
}

static uint64_t hdcm_rd64(const uint8_t *p) {
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) v = (v << 8) | p[i];          /* little endian, any host */
    return v;
}
static uint32_t hdcm_rd32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t hdcm_rd16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }

/* 64-bit hash of `rows` rows of `row_bytes` bytes (row stride `stride`), words little endian, a zero-padded tail
 * word per row. Not cryptographic: an identity check of decoded pixels and prepared levels. */
static uint64_t hdcm_hash64(const uint8_t *p, size_t stride, uint32_t row_bytes, uint32_t rows) {
    uint64_t h = 0x9E3779B97F4A7C15ull ^ ((uint64_t)row_bytes * 0x100000001B3ull) ^ (uint64_t)rows;
    for (uint32_t r = 0; r < rows; r++) {
        const uint8_t *q = p + (size_t)r * stride;
        uint32_t i = 0;
        for (; i + 8 <= row_bytes; i += 8) {
            h ^= hdcm_rd64(q + i);
            h *= 0xFF51AFD7ED558CCDull;
            h ^= h >> 29;
        }
        if (i < row_bytes) {
            uint8_t t[8] = {0, 0, 0, 0, 0, 0, 0, 0};
            memcpy(t, q + i, row_bytes - i);
            h ^= hdcm_rd64(t);
            h *= 0xFF51AFD7ED558CCDull;
            h ^= h >> 29;
        }
    }
    h ^= h >> 33;
    h *= 0xC4CEB9FE1A85EC53ull;
    h ^= h >> 33;
    return h;
}

/* Sidecar HDCMSC02 (little endian):
 *    0  "HDCMSC02"            8  texture hash u32     12 palette hash u32
 *   16  native w u16         18  native h u16        20  scale u16          22 levels u16
 *   24  HD w u32             28  HD h u32            32  level-0 hash u64
 *   40  class-map bytes u32  44  flags u32 (bit0 R1 verified offline)
 *   48  level bytes total u64 (= sum over L of (HD w >> L) * (HD h >> L) * 4)
 *   56  level hash u64 x 6 (L = 1..levels; unused 0)
 *  104  native class map (native w * native h bytes, row major, 0/127/255)
 *   ..  prepared levels 1..levels, tight RGBA rows, concatenated
 *  end  u64 hdcm_hash64 of every preceding byte (one row) */
typedef struct {
    uint32_t th, ph, hw, hh, map_bytes, flags;
    uint16_t nw, nh, s, levels;
    uint64_t level0_hash, level_bytes;
    const uint8_t *map;
    const uint8_t *level[HDCM_MAX_LEVELS + 1];  /* level[L], L = 1..levels */
} HdcmSidecar;

/* Full structural + content verification (done at preload, never on the draw thread). */
static int hdcm_sidecar2_parse(const uint8_t *buf, size_t len, HdcmSidecar *sc) {
    if (!buf || !sc || len < HDCM_SC2_HEADER + 8 || len > HDCM_SC2_MAX) return HDCM_E_SIZE;
    if (memcmp(buf, "HDCMSC02", 8)) return HDCM_E_MAGIC;
    memset(sc, 0, sizeof *sc);
    sc->th = hdcm_rd32(buf + 8); sc->ph = hdcm_rd32(buf + 12);
    sc->nw = hdcm_rd16(buf + 16); sc->nh = hdcm_rd16(buf + 18);
    sc->s = hdcm_rd16(buf + 20); sc->levels = hdcm_rd16(buf + 22);
    sc->hw = hdcm_rd32(buf + 24); sc->hh = hdcm_rd32(buf + 28);
    sc->level0_hash = hdcm_rd64(buf + 32);
    sc->map_bytes = hdcm_rd32(buf + 40); sc->flags = hdcm_rd32(buf + 44);
    sc->level_bytes = hdcm_rd64(buf + 48);
    if (!sc->nw || !sc->nh || sc->nw > HDCM_MAX_NATIVE || sc->nh > HDCM_MAX_NATIVE ||
        sc->map_bytes != (uint32_t)sc->nw * sc->nh || sc->level_bytes > HDCM_SC2_MAX_LEVEL_BYTES ||
        (uint64_t)len != (uint64_t)HDCM_SC2_HEADER + sc->map_bytes + sc->level_bytes + 8)
        return HDCM_E_SIZE;
    if (hdcm_hash64(buf, len - 8, (uint32_t)(len - 8), 1) != hdcm_rd64(buf + len - 8)) return HDCM_E_SELFHASH;
    const int L = hdcm_levels_for_scale(sc->s);
    if (!L || sc->hw != (uint32_t)sc->nw * sc->s || sc->hh != (uint32_t)sc->nh * sc->s) return HDCM_E_SCALE;
    if (sc->levels != L) return HDCM_E_LEVELS;
    uint64_t want = 0;
    for (int l = 1; l <= L; l++) want += (uint64_t)(sc->hw >> l) * (sc->hh >> l) * 4u;
    if (want != sc->level_bytes) return HDCM_E_SIZE;
    if (!(sc->flags & HDCM_FLAG_R1_VERIFIED)) return HDCM_E_FLAGS;
    sc->map = buf + HDCM_SC2_HEADER;
    for (uint32_t i = 0; i < sc->map_bytes; i++)
        if (sc->map[i] != 0 && sc->map[i] != 127 && sc->map[i] != 255) return HDCM_E_CLASS;
    const uint8_t *p = sc->map + sc->map_bytes;
    for (int l = 1; l <= L; l++) {
        const uint32_t lw = sc->hw >> l, lh = sc->hh >> l;
        sc->level[l] = p;
        if (hdcm_hash64(p, (size_t)lw * 4u, lw * 4u, lh) != hdcm_rd64(buf + 56 + 8 * (l - 1))) return HDCM_E_LEVELHASH;
        for (size_t i = 0; i < (size_t)lw * lh; i++) {
            const uint8_t a = p[i * 4 + 3];
            if (a != 0 && a != 127 && a != 255) return HDCM_E_LEVELDATA;
        }
        p += (size_t)lw * lh * 4u;
    }
    for (uint32_t i = 0; i < sc->map_bytes; i++)                       /* M4: last level == native map */
        if (sc->level[L][(size_t)i * 4 + 3] != sc->map[i]) return HDCM_E_LEVELDATA;
    return HDCM_OK;
}

/* Bind a parsed sidecar to one draw's key / upload dims and the exact decoded level-0 pixels (draw thread: one
 * level-0 hash + one R1 pass; no allocation). */
static int hdcm_sidecar_admit(const HdcmSidecar *sc, uint32_t th, uint32_t ph, uint32_t native_w, uint32_t native_h,
                              const uint8_t *rgba, size_t stride, uint32_t w, uint32_t h) {
    if (!sc || !rgba) return HDCM_E_BUILD;
    if (sc->th != th || sc->ph != ph) return HDCM_E_KEY;
    if (sc->nw != native_w || sc->nh != native_h) return HDCM_E_NATIVE_DIMS;
    if (sc->hw != w || sc->hh != h || stride < (size_t)w * 4) return HDCM_E_HD_DIMS;
    if (hdcm_hash64(rgba, stride, w * 4u, h) != sc->level0_hash) return HDCM_E_LEVEL0;
    for (uint32_t cy = 0; cy < sc->nh; cy++)
        for (uint32_t cx = 0; cx < sc->nw; cx++) {
            const uint8_t a = rgba[((size_t)cy * sc->s + sc->s / 2) * stride + ((size_t)cx * sc->s + sc->s / 2) * 4 + 3];
            if (hdcm_class(a) != sc->map[(size_t)cy * sc->nw + cx]) return HDCM_E_R1;
        }
    return HDCM_OK;
}

/* Upload callback: put level L (lw x lh, tight RGBA) on the caller's bound texture and VERIFY it; 0 = verified.
 * (The renderer verifies by the level's dimensions, which does not consume the GL error state.) */
typedef int (*hdcm_upload_fn)(void *ctx, int L, int lw, int lh, const uint8_t *rgba);

/* Fail-closed upload of the PREPARED levels 1..sc->levels. Stops at the first unverified level; *uploaded / *bytes
 * count only verified levels. Returns HDCM_OK or HDCM_E_GL (HDCM_E_BUILD on bad arguments); on failure the caller
 * restores its original sampling state (the chain may be partial). */
static int hdcm_upload_prepared(const HdcmSidecar *sc, hdcm_upload_fn up, void *ctx, int *uploaded, size_t *bytes) {
    *uploaded = 0;
    *bytes = 0;
    if (!sc || !up || sc->levels < 1 || sc->levels > HDCM_MAX_LEVELS) return HDCM_E_BUILD;
    for (int L = 1; L <= (int)sc->levels; L++) {
        const int lw = (int)(sc->hw >> L), lh = (int)(sc->hh >> L);
        if (!sc->level[L]) return HDCM_E_BUILD;
        if (up(ctx, L, lw, lh, sc->level[L])) return HDCM_E_GL;
        ++*uploaded;
        *bytes += (size_t)lw * (size_t)lh * 4u;
    }
    return HDCM_OK;
}

/* Bounded preload cache (filled at renderer init, read on the draw thread; never grows during play). A sidecar is
 * taken only if it fully verifies, carries the expected key, is not a duplicate and fits both caps. The cache owns
 * accepted buffers (malloc'd by the caller); rejected buffers are freed here. */
#define HDCM_CACHE_MAX 8
typedef struct { uint8_t *buf; size_t len; HdcmSidecar sc; } HdcmCacheEntry;
typedef struct { HdcmCacheEntry e[HDCM_CACHE_MAX]; int n; size_t bytes, cap_bytes; } HdcmCache;
static void hdcm_cache_init(HdcmCache *c, size_t cap_bytes) { memset(c, 0, sizeof *c); c->cap_bytes = cap_bytes; }
/* Would a sidecar of `len` bytes still fit? (checked BEFORE the caller allocates or reads the file) */
static int hdcm_cache_fits(const HdcmCache *c, size_t len) {
    return c->n < HDCM_CACHE_MAX && len <= HDCM_SC2_MAX && len <= c->cap_bytes - c->bytes;
}
static int hdcm_cache_add(HdcmCache *c, uint32_t th, uint32_t ph, uint8_t *buf, size_t len) {
    if (!buf) return HDCM_E_ALLOC;
    if (!hdcm_cache_fits(c, len)) { free(buf); return HDCM_E_ALLOC; }
    HdcmSidecar sc;
    int rc = hdcm_sidecar2_parse(buf, len, &sc);
    if (rc == HDCM_OK && (sc.th != th || sc.ph != ph)) rc = HDCM_E_KEY;
    for (int i = 0; rc == HDCM_OK && i < c->n; i++)
        if (c->e[i].sc.th == th && c->e[i].sc.ph == ph) rc = HDCM_E_KEY;            /* duplicate */
    if (rc != HDCM_OK) { free(buf); return rc; }
    c->e[c->n].buf = buf;
    c->e[c->n].len = len;
    c->e[c->n].sc = sc;
    c->n++;
    c->bytes += len;
    return HDCM_OK;
}
static const HdcmSidecar *hdcm_cache_find(const HdcmCache *c, uint32_t th, uint32_t ph) {
    for (int i = 0; i < c->n; i++)
        if (c->e[i].sc.th == th && c->e[i].sc.ph == ph) return &c->e[i].sc;
    return NULL;
}

#ifndef HDCM_NO_BUILDER
/* ---------------- offline / host-only: never compiled into the runtime (HDCM_NO_BUILDER) ---------------- */

/* R5: every cutout texel takes the RGB of the nearest visible texel. Multi-source 4-neighbour BFS seeded with the
 * visible texels in scan order; neighbour order x-1, x+1, y-1, y+1. queue: w*h int32, done: w*h bytes. */
static void hdcm_fill_cutout_rgb(uint8_t *rgba, int w, int h, int32_t *queue, uint8_t *done) {
    const size_t n = (size_t)w * (size_t)h;
    size_t head = 0, tail = 0;
    for (size_t i = 0; i < n; i++) {
        done[i] = (uint8_t)(rgba[i * 4 + 3] != 0);
        if (done[i]) queue[tail++] = (int32_t)i;
    }
    while (head < tail) {
        const int32_t p = queue[head++];
        const int x = p % w, y = p / w;
        const int nx[4] = {x - 1, x + 1, x, x}, ny[4] = {y, y, y - 1, y + 1};
        for (int k = 0; k < 4; k++) {
            if (nx[k] < 0 || ny[k] < 0 || nx[k] >= w || ny[k] >= h) continue;
            const size_t q = (size_t)ny[k] * (size_t)w + (size_t)nx[k];
            if (done[q]) continue;
            done[q] = 1;
            rgba[q * 4 + 0] = rgba[(size_t)p * 4 + 0];
            rgba[q * 4 + 1] = rgba[(size_t)p * 4 + 1];
            rgba[q * 4 + 2] = rgba[(size_t)p * 4 + 2];
            queue[tail++] = (int32_t)q;
        }
    }
}

/* Level L (1..log2 s) of a w x h level-0 image (row stride `stride` BYTES) with the NATIVE class map ncls
 * (tw x th = w/s x h/s). dst: (w >> L) x (h >> L) RGBA, tight rows. queue/done: scratch of at least
 * (w >> L) * (h >> L) entries. Returns 0, or -1 on bad arguments. */
static int hdcm_build_level(const uint8_t *lvl0, size_t stride, int w, int h, const uint8_t *ncls, int tw, int th,
                            int s, int L, uint8_t *dst, int32_t *queue, uint8_t *done) {
    /* L is bounded by log2(s) <= 6 BEFORE any shift by L (no undefined shift for any int L) */
    if (!lvl0 || !ncls || !dst || !queue || !done || L < 1 || L > hdcm_levels_for_scale(s)) return -1;
    if (w <= 0 || h <= 0 || w != tw * s || h != th * s || stride < (size_t)w * 4) return -1;
    const int cs = s >> L, f = 1 << L, lw = w >> L, k2 = cs * cs;
    int order[(HDCM_MAX_CELL / 2) * (HDCM_MAX_CELL / 2)];
    int vis[(HDCM_MAX_CELL / 2) * (HDCM_MAX_CELL / 2)];
#define HDCM_PX(x, y) (&lvl0[(size_t)(y) * stride + (size_t)(x) * 4])
    for (int cy = 0; cy < th; cy++)
        for (int cx = 0; cx < tw; cx++) {
            const uint8_t C = ncls[(size_t)cy * tw + cx];
            int vis0 = 0;
            uint64_t ar = 0, ag = 0, ab = 0, an = 0, vr = 0, vg = 0, vb = 0;
            for (int py = 0; py < s; py++)
                for (int px = 0; px < s; px++) {
                    const uint8_t *p = HDCM_PX(cx * s + px, cy * s + py);
                    ar += p[0]; ag += p[1]; ab += p[2]; an++;
                    if (p[3]) { vis0++; vr += p[0]; vg += p[1]; vb += p[2]; }
                }
            for (int t = 0; t < k2; t++) {
                const int tx = t % cs, ty = t / cs;
                int v = 0;
                for (int py = 0; py < f; py++)
                    for (int px = 0; px < f; px++)
                        if (HDCM_PX(cx * s + tx * f + px, cy * s + ty * f + py)[3]) v++;
                vis[t] = v;
                order[t] = t;
            }
            int k;
            if (cs == 1) k = C != 0;                                                     /* M4 */
            else {
                /* M3: round(vis0 * k2 / s^2); exact in integers (s is a power of two) */
                k = (int)(((int64_t)vis0 * k2) / ((int64_t)s * s));
                if (C != 0 && k == 0) k = 1;                                             /* never empty */
            }
            /* rank texels: more visible children first; ties toward the cell centre (distances x2,
             * exact integers), then scan order */
            for (int i = 1; i < k2; i++) {
                int j = i;
                const int cur = order[i];
                const int cc = abs(2 * (cur % cs) + 1 - cs) + abs(2 * (cur / cs) + 1 - cs);
                while (j > 0) {
                    const int a = order[j - 1];
                    const int ca = abs(2 * (a % cs) + 1 - cs) + abs(2 * (a / cs) + 1 - cs);
                    if (vis[a] > vis[cur] || (vis[a] == vis[cur] && (ca < cc || (ca == cc && a < cur)))) break;
                    order[j] = a;
                    j--;
                }
                order[j] = cur;
            }
            for (int r = 0; r < k2; r++) {
                const int t = order[r], tx = t % cs, ty = t / cs;
                uint8_t *o = &dst[(((size_t)cy * cs + ty) * (size_t)lw + (size_t)cx * cs + tx) * 4];
                if (r >= k) { o[0] = o[1] = o[2] = 0; o[3] = 0; continue; }
                uint64_t sr = 0, sg = 0, sb = 0, n127 = 0, n255 = 0;
                for (int py = 0; py < f; py++)
                    for (int px = 0; px < f; px++) {
                        const uint8_t *p = HDCM_PX(cx * s + tx * f + px, cy * s + ty * f + py);
                        if (!p[3]) continue;
                        sr += p[0]; sg += p[1]; sb += p[2];
                        if (hdcm_class(p[3]) == 255) n255++; else n127++;
                    }
                const uint64_t nv = n127 + n255;
                uint8_t cls;
                if (cs == 1) cls = C;
                else if (n255 > n127) cls = 255;
                else if (n127 > n255) cls = 127;
                else cls = C != 0 ? C : 127;
                if (nv) { o[0] = (uint8_t)(sr / nv); o[1] = (uint8_t)(sg / nv); o[2] = (uint8_t)(sb / nv); }
                else if (vis0) { o[0] = (uint8_t)(vr / (uint64_t)vis0); o[1] = (uint8_t)(vg / (uint64_t)vis0); o[2] = (uint8_t)(vb / (uint64_t)vis0); }
                else { o[0] = (uint8_t)(ar / an); o[1] = (uint8_t)(ag / an); o[2] = (uint8_t)(ab / an); }
                o[3] = cls;
            }
        }
#undef HDCM_PX
    hdcm_fill_cutout_rgb(dst, lw, h >> L, queue, done);
    return 0;
}
#endif /* HDCM_NO_BUILDER */
#endif /* HD_CLASS_MIPS_INC */
