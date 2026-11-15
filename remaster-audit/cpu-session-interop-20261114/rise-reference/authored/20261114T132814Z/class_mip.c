/* class_mip.c — PRIVATE prototype v2b (claude-einhander): v2 rules unchanged + cm_flags_ex analysis export. See class_mip.h and
 * ../DESIGN-V2.md (R2 displacement + R4 cross-cell connectivity; iterative repair). Host-only; no GL, no printf. */
#include "class_mip.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef CM_MAX_PASSES
#define CM_MAX_PASSES 8
#endif
/* v2 R2 policy used by cm_validate/cm_repair: bound = CM_R2_BOUND * s, metric 0 Euclidean (1 Chebyshev). */
#define CM_R2_BOUND 0.5
#define CM_R2_METRIC 0

static int cls_bit(uint8_t c) { return c == 0 ? 1 : (c == 127 ? 2 : (c == 255 ? 4 : 8)); }

static int nb_mask(const uint8_t *ncls, int tw, int th, int cx, int cy) {
    int m = 0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++) {
            int x = cx + dx, y = cy + dy;
            if (x < 0) x = 0; if (y < 0) y = 0; if (x >= tw) x = tw - 1; if (y >= th) y = th - 1;
            m |= cls_bit(ncls[(size_t)y * tw + x]);
        }
    return m;
}

int64_t cm_fill_cutout_rgb(uint8_t *rgba, int w, int h) {
    const size_t n = (size_t)w * h;
    int32_t *queue = (int32_t *)malloc(n * sizeof(int32_t));
    uint8_t *done = (uint8_t *)calloc(n, 1);
    if (!queue || !done) { free(queue); free(done); return -1; }
    size_t head = 0, tail = 0;
    for (size_t i = 0; i < n; i++)
        if (rgba[i * 4 + 3] != 0) { done[i] = 1; queue[tail++] = (int32_t)i; }
    int64_t written = 0;
    while (head < tail) {
        const int32_t p = queue[head++];
        const int x = p % w, y = p / w;
        const int nx[4] = {x - 1, x + 1, x, x}, ny[4] = {y, y, y - 1, y + 1};
        for (int k = 0; k < 4; k++) {
            if (nx[k] < 0 || ny[k] < 0 || nx[k] >= w || ny[k] >= h) continue;
            const size_t q = (size_t)ny[k] * w + nx[k];
            if (done[q]) continue;
            done[q] = 1;
            memcpy(&rgba[q * 4], &rgba[(size_t)p * 4], 3);
            written++;
            queue[tail++] = (int32_t)q;
        }
    }
    free(queue); free(done);
    return written;
}

/* v2 ownership rules (DESIGN-V2.md). A pixel is DEVIANT when its class X differs from the native class C of its cell.
 *   R1 centre:       pixel floor((i+0.5)s) of every cell has the native class.
 *   R2 displacement: a deviant pixel's centre lies within s/2 (Euclidean) of a native cell of class X. Sub-native
 *                    contours may move a native class boundary by at most half a native texel.
 *   R4 connectivity: a deviant pixel's class-X component (4-connected, ACROSS cells) reaches a non-deviant class-X
 *                    pixel. Islands are errors; contours that chain through neighbouring cells are not.
 *   R3 (diagnostic): uniform native 3x3 but the pixel differs (implied by R2).
 * flag bits: 1 deviant, 2 displaced (R2), 4 island (R4), 8 uniform-bad (R3), 16 centre-bad (R1), 32 BFS visited. */
#define CM_VIOL (2 | 4 | 16)

static double rect_dist(double x, double y, double rx0, double ry0, double rx1, double ry1, int metric) {
    const double dx = x < rx0 ? rx0 - x : (x > rx1 ? x - rx1 : 0.0);
    const double dy = y < ry0 ? ry0 - y : (y > ry1 ? y - ry1 : 0.0);
    return metric == 1 ? (dx > dy ? dx : dy) : sqrt(dx * dx + dy * dy);
}

static int classify(const uint8_t *rgba, int w, int h, const uint8_t *ncls, int tw, int th, int s,
                    double bound_frac, int metric, uint8_t *flag, int32_t *queue) {
    const size_t n = (size_t)w * h;
    memset(flag, 0, n);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            const size_t i = (size_t)y * w + x;
            const int cx = x / s, cy = y / s;
            const uint8_t C = ncls[(size_t)cy * tw + cx], X = rgba[i * 4 + 3];
            if (X == C) continue;
            flag[i] |= 1;
            double best = 1e30;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++) {
                    const int nx = cx + dx, ny = cy + dy;
                    if ((dx == 0 && dy == 0) || nx < 0 || ny < 0 || nx >= tw || ny >= th) continue;
                    if (ncls[(size_t)ny * tw + nx] != X) continue;
                    const double d = rect_dist(x + 0.5, y + 0.5, (double)nx * s, (double)ny * s,
                                               (double)(nx + 1) * s, (double)(ny + 1) * s, metric);
                    if (d < best) best = d;
                }
            if (best > s * bound_frac) flag[i] |= 2;
            if (nb_mask(ncls, tw, th, cx, cy) == cls_bit(C)) flag[i] |= 8;
        }
    for (int cy = 0; cy < th; cy++)
        for (int cx = 0; cx < tw; cx++) {
            const size_t i = ((size_t)cy * s + s / 2) * w + (size_t)cx * s + s / 2;
            if (rgba[i * 4 + 3] != ncls[(size_t)cy * tw + cx]) flag[i] |= 16;
        }
    /* R4: multi-source BFS from every non-deviant pixel through same-class pixels */
    size_t head = 0, tail = 0;
    for (size_t i = 0; i < n; i++)
        if (!(flag[i] & 1)) { flag[i] |= 32; queue[tail++] = (int32_t)i; }
    while (head < tail) {
        const int32_t p = queue[head++];
        const int x = p % w, y = p / w;
        const uint8_t a = rgba[(size_t)p * 4 + 3];
        const int nx[4] = {x - 1, x + 1, x, x}, ny[4] = {y, y, y - 1, y + 1};
        for (int k = 0; k < 4; k++) {
            if (nx[k] < 0 || ny[k] < 0 || nx[k] >= w || ny[k] >= h) continue;
            const size_t q = (size_t)ny[k] * w + nx[k];
            if ((flag[q] & 32) || rgba[q * 4 + 3] != a) continue;
            flag[q] |= 32;
            queue[tail++] = (int32_t)q;
        }
    }
    for (size_t i = 0; i < n; i++)
        if ((flag[i] & 1) && !(flag[i] & 32)) flag[i] |= 4;
    return 0;
}

int cm_validate(const uint8_t *rgba, int w, int h, const uint8_t *ncls, int tw, int th, int s,
                CmReport *out) {
    if (!rgba || !ncls || !out || s < 1 || w != tw * s || h != th * s) return -1;
    memset(out, 0, sizeof(*out));
    const size_t n = (size_t)w * h;
    out->pixels = n;
    out->cells = (uint64_t)tw * th;
    uint8_t *flag = (uint8_t *)malloc(n);
    int32_t *queue = (int32_t *)malloc(n * sizeof(int32_t));
    uint8_t *fill = (uint8_t *)malloc(n * 4);
    if (!flag || !queue || !fill) { free(flag); free(queue); free(fill); return -1; }
    for (size_t i = 0; i < n; i++) {
        const uint8_t a = rgba[i * 4 + 3];
        if (a != 0 && a != 127 && a != 255) out->nonclass_px++;
    }
    classify(rgba, w, h, ncls, tw, th, s, CM_R2_BOUND, CM_R2_METRIC, flag, queue);
    for (size_t i = 0; i < n; i++) {
        if (flag[i] & 2) out->r2_displaced_px++;
        if (flag[i] & 8) out->r3_uniform_bad_px++;
        if (flag[i] & 4) out->r4_island_px++;
        if (flag[i] & 16) out->r1_centre_bad++;
    }
    for (int cy = 0; cy < th; cy++)
        for (int cx = 0; cx < tw; cx++) {
            int centre = 0, other = 0;
            for (int ly = 0; ly < s; ly++)
                for (int lx = 0; lx < s; lx++) {
                    const uint8_t f = flag[((size_t)cy * s + ly) * w + (size_t)cx * s + lx];
                    if (f & 16) centre = 1;
                    if (f & (2 | 4)) other = 1;
                }
            if (centre || other) out->cells_bad++;
            if (!centre && other) out->pinhole_cells++;
        }
    memcpy(fill, rgba, n * 4);
    if (cm_fill_cutout_rgb(fill, w, h) < 0) { free(flag); free(queue); free(fill); return -1; }
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            const size_t i = (size_t)y * w + x;
            if (rgba[i * 4 + 3] != 0) continue;
            int adj = 0;
            if (x > 0 && rgba[(i - 1) * 4 + 3]) adj = 1;
            if (x < w - 1 && rgba[(i + 1) * 4 + 3]) adj = 1;
            if (y > 0 && rgba[(i - w) * 4 + 3]) adj = 1;
            if (y < h - 1 && rgba[(i + w) * 4 + 3]) adj = 1;
            if (adj && memcmp(&rgba[i * 4], &fill[i * 4], 3) != 0) out->r5_fringe_px++;
        }
    free(flag); free(queue); free(fill);
    return 0;
}

int cm_repair(uint8_t *rgba, int w, int h, const uint8_t *ncls, const uint8_t *nrgb, int tw, int th,
              int s, CmRepairStats *st) {
    if (!rgba || !ncls || !st || s < 1 || w != tw * s || h != th * s) return -1;
    memset(st, 0, sizeof(*st));
    const size_t n = (size_t)w * h;
    uint8_t *before = (uint8_t *)malloc(n * 4);
    uint8_t *flag = (uint8_t *)malloc(n);
    int32_t *queue = (int32_t *)malloc(n * sizeof(int32_t));
    if (!before || !flag || !queue) { free(before); free(flag); free(queue); return -1; }
    memcpy(before, rgba, n * 4);
    int clean = 0;
    for (int pass = 0; pass < CM_MAX_PASSES; pass++) {
        classify(rgba, w, h, ncls, tw, th, s, CM_R2_BOUND, CM_R2_METRIC, flag, queue);
        uint64_t viol = 0;
        for (size_t i = 0; i < n; i++) if (flag[i] & CM_VIOL) viol++;
        if (!viol) { clean = 1; break; }
        st->passes++;
        for (int cy = 0; cy < th; cy++)
            for (int cx = 0; cx < tw; cx++) {
                const uint8_t C = ncls[(size_t)cy * tw + cx];
                uint64_t sr = 0, sg = 0, sb = 0, sn = 0;     /* colour of the cell's correct class-C pixels */
                for (int ly = 0; ly < s; ly++)
                    for (int lx = 0; lx < s; lx++) {
                        const size_t i = ((size_t)cy * s + ly) * w + (size_t)cx * s + lx;
                        if (C != 0 && rgba[i * 4 + 3] == C && !(flag[i] & CM_VIOL)) {
                            sr += rgba[i * 4]; sg += rgba[i * 4 + 1]; sb += rgba[i * 4 + 2]; sn++;
                        }
                    }
                for (int ly = 0; ly < s; ly++)
                    for (int lx = 0; lx < s; lx++) {
                        const size_t i = ((size_t)cy * s + ly) * w + (size_t)cx * s + lx;
                        if (!(flag[i] & CM_VIOL)) continue;
                        const uint8_t old = rgba[i * 4 + 3];
                        if (old == C) continue;
                        rgba[i * 4 + 3] = C;
                        st->class_changed++;
                        if (C == 0) { st->became_cutout++; continue; }
                        if (old != 0) continue;                    /* 127<->255: alpha only */
                        st->became_visible++;
                        if (sn) {
                            rgba[i * 4] = (uint8_t)(sr / sn); rgba[i * 4 + 1] = (uint8_t)(sg / sn);
                            rgba[i * 4 + 2] = (uint8_t)(sb / sn);
                            st->rgb_from_cell++;
                        } else if (nrgb) {
                            memcpy(&rgba[i * 4], &nrgb[((size_t)cy * tw + cx) * 3], 3);
                            st->rgb_from_native++;
                        }
                    }
            }
    }
    if (!clean) {   /* report the state after the last pass */
        classify(rgba, w, h, ncls, tw, th, s, CM_R2_BOUND, CM_R2_METRIC, flag, queue);
        uint64_t viol = 0;
        for (size_t i = 0; i < n; i++) if (flag[i] & CM_VIOL) viol++;
        clean = viol == 0;
        st->residual_violations = viol;
    }
    const int64_t f = cm_fill_cutout_rgb(rgba, w, h);
    if (f < 0) { free(before); free(flag); free(queue); return -1; }
    for (size_t i = 0; i < n; i++) {
        if (rgba[i * 4 + 3] == 0 && memcmp(&rgba[i * 4], &before[i * 4], 3) != 0) st->cutout_rgb_filled++;
        if (before[i * 4 + 3] != 0 && rgba[i * 4 + 3] != 0 && memcmp(&rgba[i * 4], &before[i * 4], 3) != 0)
            st->visible_rgb_changed++;
    }
    free(before); free(flag); free(queue);
    return clean ? 0 : 1;
}

int cm_build_level(const uint8_t *lvl0, int w, int h, const uint8_t *ncls, int tw, int th, int s, int L,
                   uint8_t *dst) {
    if (!lvl0 || !ncls || !dst || s < 2 || w != tw * s || h != th * s || L < 1) return -1;
    if ((s >> L) < 1 || ((s >> L) << L) != s) return -1;   /* s must be divisible by 2^L */
    const int cs = s >> L, f = 1 << L, lw = w >> L;
    const int k2 = cs * cs;
    int *order = (int *)malloc((size_t)k2 * sizeof(int));
    int *vis = (int *)malloc((size_t)k2 * sizeof(int));
    if (!order || !vis) { free(order); free(vis); return -1; }
    for (int cy = 0; cy < th; cy++)
        for (int cx = 0; cx < tw; cx++) {
            const uint8_t C = ncls[(size_t)cy * tw + cx];
            int vis0 = 0;
            uint64_t ar = 0, ag = 0, ab = 0, an = 0;   /* all-pixel mean (fallback colour) */
            uint64_t vr = 0, vg = 0, vb = 0;
            for (int py = 0; py < s; py++)
                for (int px = 0; px < s; px++) {
                    const uint8_t *p = &lvl0[(((size_t)cy * s + py) * w + (size_t)cx * s + px) * 4];
                    ar += p[0]; ag += p[1]; ab += p[2]; an++;
                    if (p[3]) { vis0++; vr += p[0]; vg += p[1]; vb += p[2]; }
                }
            for (int t = 0; t < k2; t++) {
                const int tx = t % cs, ty = t / cs;
                int v = 0;
                for (int py = 0; py < f; py++)
                    for (int px = 0; px < f; px++)
                        if (lvl0[(((size_t)cy * s + ty * f + py) * w + (size_t)cx * s + tx * f + px) * 4 + 3]) v++;
                vis[t] = v;
                order[t] = t;
            }
            int k;
            if (cs == 1) k = C != 0;                                         /* M4 */
            else {
                k = (int)floor((double)vis0 * k2 / ((double)s * s) + 0.5);    /* M3 coverage */
                if (C != 0 && k == 0) k = 1;                                  /* never empty */
            }
            /* rank texels: more visible children first; ties toward the cell centre, then scan order */
            for (int i = 1; i < k2; i++) {
                int j = i, cur = order[i];
                while (j > 0) {
                    const int a = order[j - 1];
                    const double ca = fabs((a % cs) + 0.5 - cs / 2.0) + fabs((a / cs) + 0.5 - cs / 2.0);
                    const double cc = fabs((cur % cs) + 0.5 - cs / 2.0) + fabs((cur / cs) + 0.5 - cs / 2.0);
                    if (vis[a] > vis[cur] || (vis[a] == vis[cur] && (ca < cc || (ca == cc && a < cur)))) break;
                    order[j] = a; j--;
                }
                order[j] = cur;
            }
            for (int r = 0; r < k2; r++) {
                const int t = order[r], tx = t % cs, ty = t / cs;
                uint8_t *o = &dst[(((size_t)cy * cs + ty) * lw + (size_t)cx * cs + tx) * 4];
                if (r >= k) { o[0] = o[1] = o[2] = 0; o[3] = 0; continue; }
                uint64_t sr = 0, sg = 0, sb = 0, n127 = 0, n255 = 0;
                for (int py = 0; py < f; py++)
                    for (int px = 0; px < f; px++) {
                        const uint8_t *p = &lvl0[(((size_t)cy * s + ty * f + py) * w + (size_t)cx * s + tx * f + px) * 4];
                        if (!p[3]) continue;
                        sr += p[0]; sg += p[1]; sb += p[2];
                        if (p[3] == 255) n255++; else n127++;
                    }
                const uint64_t nv = n127 + n255;
                uint8_t cls;
                if (cs == 1) cls = C;
                else if (n255 > n127) cls = 255;
                else if (n127 > n255) cls = 127;
                else cls = C != 0 ? C : 127;
                if (nv) { o[0] = (uint8_t)(sr / nv); o[1] = (uint8_t)(sg / nv); o[2] = (uint8_t)(sb / nv); }
                else if (vis0) { o[0] = (uint8_t)(vr / vis0); o[1] = (uint8_t)(vg / vis0); o[2] = (uint8_t)(vb / vis0); }
                else { o[0] = (uint8_t)(ar / an); o[1] = (uint8_t)(ag / an); o[2] = (uint8_t)(ab / an); }
                o[3] = cls;
            }
        }
    free(order); free(vis);
    return cm_fill_cutout_rgb(dst, lw, h >> L) < 0 ? -1 : 0;
}

int cm_naive_level(const uint8_t *src, int w, int h, uint8_t *dst) {
    if (!src || !dst || w < 2 || h < 2) return -1;
    const int lw = w / 2, lh = h / 2;
    for (int y = 0; y < lh; y++)
        for (int x = 0; x < lw; x++)
            for (int c = 0; c < 4; c++) {
                const unsigned v = src[((size_t)(2 * y) * w + 2 * x) * 4 + c] + src[((size_t)(2 * y) * w + 2 * x + 1) * 4 + c] +
                                   src[((size_t)(2 * y + 1) * w + 2 * x) * 4 + c] + src[((size_t)(2 * y + 1) * w + 2 * x + 1) * 4 + c];
                dst[((size_t)y * lw + x) * 4 + c] = (uint8_t)((v + 2) / 4);
            }
    return 0;
}

static void texel(const uint8_t *img, int w, int h, int x, int y, double out[4]) {
    if (x < 0) x = 0; if (y < 0) y = 0; if (x >= w) x = w - 1; if (y >= h) y = h - 1;
    const uint8_t *p = &img[((size_t)y * w + x) * 4];
    out[0] = p[0]; out[1] = p[1]; out[2] = p[2]; out[3] = p[3];
}

static void bilinear(const uint8_t *img, int w, int h, double x, double y, double out[4]) {
    const double fx = x - 0.5, fy = y - 0.5;
    const int x0 = (int)floor(fx), y0 = (int)floor(fy);
    const double ax = fx - x0, ay = fy - y0;
    double a[4], b[4], c[4], d[4];
    texel(img, w, h, x0, y0, a); texel(img, w, h, x0 + 1, y0, b);
    texel(img, w, h, x0, y0 + 1, c); texel(img, w, h, x0 + 1, y0 + 1, d);
    for (int i = 0; i < 4; i++)
        out[i] = a[i] * (1 - ax) * (1 - ay) + b[i] * ax * (1 - ay) + c[i] * (1 - ax) * ay + d[i] * ax * ay;
}

int cm_sample(const uint8_t *const *levels, const int *lw, const int *lh, int nlevels, double x, double y,
              double lod, int mode, double clamp_x0, double clamp_y0, double clamp_x1, double clamp_y1,
              uint8_t rgb[3], uint8_t *cls) {
    if (x < clamp_x0) x = clamp_x0; if (y < clamp_y0) y = clamp_y0;
    if (x > clamp_x1) x = clamp_x1; if (y > clamp_y1) y = clamp_y1;
    double col[4] = {0, 0, 0, 0};
    uint8_t c;
    if (mode == 1) {
        double l = lod < 0 ? 0 : (lod > nlevels - 1 ? nlevels - 1 : lod);
        const int lc = (int)floor(l + 0.5);
        double t[4];
        texel(levels[lc], lw[lc], lh[lc], (int)floor(x / (1 << lc)), (int)floor(y / (1 << lc)), t);
        c = (uint8_t)t[3];
        const int l0 = (int)floor(l), l1 = l0 + 1 < nlevels ? l0 + 1 : l0;
        const double fr = l - l0;
        double a[4], b[4];
        bilinear(levels[l0], lw[l0], lh[l0], x / (1 << l0), y / (1 << l0), a);
        bilinear(levels[l1], lw[l1], lh[l1], x / (1 << l1), y / (1 << l1), b);
        for (int i = 0; i < 3; i++) col[i] = a[i] * (1 - fr) + b[i] * fr;
    } else {
        double t[4];
        texel(levels[0], lw[0], lh[0], (int)floor(x), (int)floor(y), t);
        c = (uint8_t)t[3];
        if (mode == 0 || nlevels == 1) bilinear(levels[0], lw[0], lh[0], x, y, col);
        else {
            double l = lod < 0 ? 0 : (lod > nlevels - 1 ? nlevels - 1 : lod);
            const int l0 = (int)floor(l), l1 = l0 + 1 < nlevels ? l0 + 1 : l0;
            const double fr = l - l0;
            double a[4], b[4];
            bilinear(levels[l0], lw[l0], lh[l0], x / (1 << l0), y / (1 << l0), a);
            bilinear(levels[l1], lw[l1], lh[l1], x / (1 << l1), y / (1 << l1), b);
            for (int i = 0; i < 3; i++) col[i] = a[i] * (1 - fr) + b[i] * fr;
        }
    }
    if (cls) *cls = c;
    for (int i = 0; i < 3; i++) rgb[i] = (uint8_t)(col[i] < 0 ? 0 : (col[i] > 255 ? 255 : col[i] + 0.5));
    return c != 0;
}

int cm_flags_ex(const uint8_t *rgba, int w, int h, const uint8_t *ncls, int tw, int th, int s,
                double bound_frac, int metric, uint8_t *flag_out) {
    if (!rgba || !ncls || !flag_out || s < 1 || w != tw * s || h != th * s) return -1;
    if (!(bound_frac >= 0.0) || (metric != 0 && metric != 1)) return -1;
    int32_t *queue = (int32_t *)malloc((size_t)w * h * sizeof(int32_t));
    if (!queue) return -1;
    classify(rgba, w, h, ncls, tw, th, s, bound_frac, metric, flag_out, queue);
    free(queue);
    return 0;
}
