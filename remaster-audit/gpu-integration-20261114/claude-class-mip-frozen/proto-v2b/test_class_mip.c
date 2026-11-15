/* test_class_mip.c — host fixtures for the class-ownership / class-aware mip
 * prototype v2b (claude-einhander): v1 fixtures + F1b inset/chain + F1c multi-pass + F7 cm_flags_ex policy export. Synthetic, deterministic, small. Prints one
 * "METRIC" line per measured quantity (parsed by the runner) and a summary.
 * Test harness output only. */
#include "class_mip.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++g_fail; } } while (0)

enum { S = 8 };

static uint8_t *img_new(int w, int h) { return (uint8_t *)calloc((size_t)w * h, 4); }
static void px_set(uint8_t *im, int w, int x, int y, uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    uint8_t *p = &im[((size_t)y * w + x) * 4]; p[0] = r; p[1] = g; p[2] = b; p[3] = a;
}
static uint8_t px_a(const uint8_t *im, int w, int x, int y) { return im[((size_t)y * w + x) * 4 + 3]; }

/* ---------------------------------------------------------------- F1 classes */
/* native 6x6: columns 0-1 class 0, 2-3 class 127, 4-5 class 255. HD contours
 * wander +-2 px around each native boundary (sub-native detail), cutout RGB is
 * black as in real packs. */
static void f1_build(uint8_t *ncls, uint8_t *im) {
    const int tw = 6, th = 6, w = tw * S;
    for (int y = 0; y < th; y++)
        for (int x = 0; x < tw; x++) ncls[y * tw + x] = x < 2 ? 0 : (x < 4 ? 127 : 255);
    for (int y = 0; y < th * S; y++)
        for (int x = 0; x < w; x++) {
            const double b1 = 2 * S + 2.0 * sin(y * 0.35), b2 = 4 * S + 2.0 * cos(y * 0.27);
            if (x < b1) px_set(im, w, x, y, 0, 0, 0, 0);
            else if (x < b2) px_set(im, w, x, y, 40, (uint8_t)(180 + (y & 31)), 150, 127);
            else px_set(im, w, x, y, 230, (uint8_t)(120 + (x & 15)), 40, 255);
        }
}

static void f1(void) {
    const int tw = 6, th = 6, w = tw * S, h = th * S;
    uint8_t ncls[36];
    uint8_t *im = img_new(w, h);
    f1_build(ncls, im);
    CmReport r;
    CHECK(cm_validate(im, w, h, ncls, tw, th, S, &r) == 0);
    CHECK(r.r1_centre_bad == 0 && r.r2_displaced_px == 0 && r.r3_uniform_bad_px == 0 && r.r4_island_px == 0);
    CHECK(r.nonclass_px == 0 && r.r5_fringe_px > 0);          /* black cutout RGB fringes */
    printf("METRIC f1_clean_r5_fringe_px %llu\n", (unsigned long long)r.r5_fringe_px);
    uint8_t *filled = img_new(w, h);
    memcpy(filled, im, (size_t)w * h * 4);
    CHECK(cm_fill_cutout_rgb(filled, w, h) > 0);
    CHECK(cm_validate(filled, w, h, ncls, tw, th, S, &r) == 0 && r.r5_fringe_px == 0 && r.cells_bad == 0);
    for (int i = 0; i < w * h; i++)
        if (im[i * 4 + 3]) CHECK(memcmp(&im[i * 4], &filled[i * 4], 4) == 0 || !"visible pixel changed by fill");

    /* pinhole: cell (5,2) (native 255, uniform nbhd) authored all 127, centre stamped 255 */
    uint8_t *pin = img_new(w, h);
    memcpy(pin, im, (size_t)w * h * 4);
    for (int y = 2 * S; y < 3 * S; y++) for (int x = 5 * S; x < 6 * S; x++) pin[((size_t)y * w + x) * 4 + 3] = 127;
    pin[((size_t)(2 * S + S / 2) * w + 5 * S + S / 2) * 4 + 3] = 255;
    CHECK(cm_validate(pin, w, h, ncls, tw, th, S, &r) == 0);
    CHECK(r.r1_centre_bad == 0 && r.pinhole_cells >= 1 && r.r3_uniform_bad_px == (uint64_t)(S * S - 1));
    printf("METRIC f1_pinhole_cells %llu\n", (unsigned long long)r.pinhole_cells);
    /* island: a 2x2 cutout speck inside the uniform-127 cell (2,3)... cell 2 borders class 0 -> use cell (3,3) */
    for (int y = 3 * S + 3; y < 3 * S + 5; y++) for (int x = 3 * S + 3; x < 3 * S + 5; x++) px_set(pin, w, x, y, 0, 0, 0, 0);
    /* foreign class: 255 pixels inside cell (0,0) whose nbhd is {0,127}? nbhd of (0,0) is {0} only -> foreign */
    px_set(pin, w, 2, 2, 255, 255, 255, 255);
    CHECK(cm_validate(pin, w, h, ncls, tw, th, S, &r) == 0);
    CHECK(r.r2_displaced_px >= 1 && r.r4_island_px >= 4);
    CmRepairStats st;
    uint8_t *rep = img_new(w, h);
    memcpy(rep, pin, (size_t)w * h * 4);
    CHECK(cm_repair(rep, w, h, ncls, NULL, tw, th, S, &st) == 0);
    CHECK(st.visible_rgb_changed == 0 && st.became_visible == 4 && st.rgb_from_cell == 4 && st.became_cutout == 1);
    CHECK(st.class_changed == (uint64_t)(S * S - 1) + 4 + 1);
    CHECK(cm_validate(rep, w, h, ncls, tw, th, S, &r) == 0 && r.cells_bad == 0 && r.r5_fringe_px == 0);
    /* the clean authored contours survive the repair untouched (alpha and visible RGB) */
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            const int cx = x / S, cy = y / S;
            if ((cx == 5 && cy == 2) || (cx == 3 && cy == 3) || (cx == 0 && cy == 0)) continue;
            const size_t i = ((size_t)y * w + x) * 4;
            CHECK(rep[i + 3] == im[i + 3]);
            if (im[i + 3]) CHECK(memcmp(&rep[i], &im[i], 3) == 0);
        }
    /* M4: level log2(S) equals the native classes; no level crosses a cell */
    uint8_t *l3 = img_new(tw, th);
    CHECK(cm_build_level(rep, w, h, ncls, tw, th, S, 3, l3) == 0);
    for (int i = 0; i < tw * th; i++) CHECK(l3[i * 4 + 3] == ncls[i]);
    free(im); free(filled); free(pin); free(rep); free(l3);
}

/* ----------------------------------------------- F1b v2: inset contours / chains */
/* A native-opaque disc (cells whose centre is inside radius R) authored with an INSET edge: the HD disc radius is
 * R - inset. Inset <= s/2 is a legitimate sub-native contour (must pass R2/R4); inset well beyond s/2 must be
 * flagged as displaced. The cutout sliver between the native silhouette and the authored edge reaches native-0
 * territory by chaining through neighbouring cells (the case the v1 neighbour-only R4 wrongly flagged). */
static int disc_violations(double inset, CmReport *r) {
    enum { T = 16 };
    const int w = T * S;
    uint8_t ncls[T * T];
    const double cx = w / 2.0, cy = w / 2.0, R = 5.3 * S;
    for (int y = 0; y < T; y++) for (int x = 0; x < T; x++) {
        const double dx = (x + 0.5) * S - cx, dy = (y + 0.5) * S - cy;
        ncls[y * T + x] = dx * dx + dy * dy < R * R ? 127 : 0;
    }
    uint8_t *im = img_new(w, w);
    for (int y = 0; y < w; y++) for (int x = 0; x < w; x++) {
        const double dx = x + 0.5 - cx, dy = y + 0.5 - cy, rr = R - inset;
        /* authored edge; centre pixels keep the native class (R1) */
        int vis = dx * dx + dy * dy < rr * rr;
        const int ccx = x / S, ccy = y / S;
        if ((x % S) == S / 2 && (y % S) == S / 2) vis = ncls[ccy * T + ccx] != 0;
        if (vis) px_set(im, w, x, y, 90, 30, 10, 127); else px_set(im, w, x, y, 0, 0, 0, 0);
    }
    const int rc = cm_validate(im, w, w, ncls, T, T, S, r);
    free(im);
    return rc;
}

static void f1b(void) {
    CmReport r;
    CHECK(disc_violations(0.0, &r) == 0);
    const uint64_t base = r.r2_displaced_px + r.r4_island_px;    /* blocky native vs round edge (<= s/2 by geometry) */
    printf("METRIC f1b_disc_inset0_violations %llu\n", (unsigned long long)base);
    CHECK(disc_violations(2.0, &r) == 0);
    printf("METRIC f1b_disc_inset2px_violations %llu (r4 %llu)\n", (unsigned long long)(r.r2_displaced_px + r.r4_island_px),
           (unsigned long long)r.r4_island_px);
    CHECK(r.r4_island_px == 0);                                  /* chained slivers are fed, not islands */
    CHECK(disc_violations(7.0, &r) == 0);
    printf("METRIC f1b_disc_inset7px_displaced %llu\n", (unsigned long long)r.r2_displaced_px);
    CHECK(r.r2_displaced_px > 0);                                /* deeper than s/2: flagged */
}

/* ----------------------------------------------- F1c v2: repair needs two passes */
/* Native: top cell row 0, everything else 127. A cutout BLOB within s/2 of the top row (legal by R2) but separated
 * from it by opaque rows, fed only through a CHANNEL that runs deeper than s/2 (displaced) and back up elsewhere.
 * Pass 1 removes the displaced channel; the blob is then an island; pass 2 removes it. */
static void f1c(void) {
    enum { TW = 8, TH = 4 };
    const int w = TW * S, h = TH * S;
    uint8_t ncls[TW * TH];
    for (int y = 0; y < TH; y++) for (int x = 0; x < TW; x++) ncls[y * TW + x] = y == 0 ? 0 : 127;
    uint8_t *im = img_new(w, h);
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        if (y < S) px_set(im, w, x, y, 0, 0, 0, 0); else px_set(im, w, x, y, 200, 120, 60, 127);
    }
#define CUT(x0, y0, x1, y1) for (int yy = (y0); yy <= (y1); yy++) for (int xx = (x0); xx <= (x1); xx++) px_set(im, w, xx, yy, 0, 0, 0, 0)
    CUT(17, 10, 21, 11);      /* blob in cell (2,1), rows ly 2..3: within s/2 of the top row */
    CUT(20, 12, 21, 20);      /* channel down into row 2 (displaced) */
    CUT(20, 19, 45, 20);      /* across */
    CUT(44, 8, 45, 20);       /* and up into the native-0 row (its top part is fed) */
#undef CUT
    CmReport r;
    CHECK(cm_validate(im, w, h, ncls, TW, TH, S, &r) == 0);
    CHECK(r.r2_displaced_px > 0);
    CmRepairStats st;
    CHECK(cm_repair(im, w, h, ncls, NULL, TW, TH, S, &st) == 0);
    printf("METRIC f1c_repair_passes %llu became_visible %llu\n", (unsigned long long)st.passes,
           (unsigned long long)st.became_visible);
    CHECK(st.passes == 2 && st.residual_violations == 0 && st.visible_rgb_changed == 0);
    CHECK(cm_validate(im, w, h, ncls, TW, TH, S, &r) == 0 && r.cells_bad == 0);
    /* the blob is gone (it was an island after pass 1) */
    CHECK(px_a(im, w, 18, 10) == 127);
    free(im);
}

/* ------------------------------------------------------------ F2 thin stroke */
enum { T2 = 32 };
static void f2_build(uint8_t *ncls, uint8_t *im) {
    const int w = T2 * S;
    /* diagonal + horizontal 3-px neon strokes, plus a dashed HAIRLINE in native row 25 whose authored coverage is
     * only 4 of 64 px per cell (1 px tall, 4 px long, through the centre pixel): it exercises the never-empty rule
     * (M3) and the native class at the cell level (M4). */
    /* v2 fixture domain: the diagonal runs over cells 2..29 only (no image-corner cells, whose missing outside
     * neighbour leaves no native cutout within s/2), and the hairline (row 25, x 0..20) does not cross the diagonal
     * (a cutout gap between two natively joined opaque strokes is a >s/2 displacement, correctly flagged by R2). */
    for (int y = 0; y < T2; y++) for (int x = 0; x < T2; x++)
        ncls[y * T2 + x] = ((x == y && x >= 2 && x <= 29) || y == 20 || (y == 25 && x <= 20)) ? 127 : 0;
    for (int y = 0; y < w; y++)
        for (int x = 0; x < w; x++) {
            const double d = fabs((x + 0.5) - (y + 0.5)) / sqrt(2.0);        /* distance to the diagonal */
            const int dg = d <= 1.5 && x >= 2 * S && x < 30 * S && y >= 2 * S && y < 30 * S;
            const double dh = fabs((y + 0.5) - (20 * S + S / 2.0));          /* to the horizontal stroke */
            const int hair = (y == 25 * S + S / 2) && x < 21 * S && (x % S) >= S / 2 - 2 && (x % S) <= S / 2 + 1;
            if (dg || dh <= 1.5 || hair) px_set(im, w, x, y, 255, 40, 200, 127);   /* neon magenta */
            else px_set(im, w, x, y, 0, 0, 0, 0);
        }
}

static double luma(const uint8_t *p) { return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]; }

static void render_metrics(const uint8_t *const *lv, const int *lw, const int *lh, int nl, int mode, double m,
                           double *var_count, double *min_count, double *var_energy) {
    /* screen = texture / m; pan by sub-pixel offsets; one sample per screen pixel centre */
    const int sw = (int)(T2 * S / m);
    const int frames = 16;
    double sum = 0, sum2 = 0, esum = 0, esum2 = 0, mn = 1e30;
    const double lod = log2(m);
    for (int f = 0; f < frames; f++) {
        const double off = (double)f / frames;
        double cnt = 0, energy = 0;
        for (int sy = 0; sy < sw; sy++)
            for (int sx = 0; sx < sw; sx++) {
                const double tx = (sx + 0.5 + off) * m, ty = (sy + 0.5 + off * 0.37) * m;
                uint8_t rgb[3], c;
                if (cm_sample(lv, lw, lh, nl, tx, ty, lod, mode, 0, 0, T2 * S - 1e-6, T2 * S - 1e-6, rgb, &c)) {
                    cnt++; energy += luma(rgb);
                }
            }
        sum += cnt; sum2 += cnt * cnt; esum += energy; esum2 += energy * energy;
        if (cnt < mn) mn = cnt;
    }
    const double mean = sum / frames, emean = esum / frames;
    *var_count = sum2 / frames - mean * mean;
    *var_energy = esum2 / frames - emean * emean;
    *min_count = mn;
}

static void f2(void) {
    const int w = T2 * S;
    uint8_t *ncls = (uint8_t *)malloc(T2 * T2);
    uint8_t *im = img_new(w, w);
    f2_build(ncls, im);
    CmReport r;
    CHECK(cm_validate(im, w, w, ncls, T2, T2, S, &r) == 0);
    CHECK(r.r1_centre_bad == 0 && r.r2_displaced_px == 0 && r.r3_uniform_bad_px == 0 && r.r4_island_px == 0);
    cm_fill_cutout_rgb(im, w, w);
    const uint8_t *lv[4]; int lw[4], lh[4];
    uint8_t *levels[4];
    levels[0] = im; lw[0] = lh[0] = w;
    for (int L = 1; L <= 3; L++) {
        lw[L] = lh[L] = w >> L;
        levels[L] = img_new(lw[L], lh[L]);
        CHECK(cm_build_level(im, w, w, ncls, T2, T2, S, L, levels[L]) == 0);
    }
    for (int L = 0; L <= 3; L++) lv[L] = levels[L];
    /* never empty + coverage preserved per cell at every level */
    int worst_cov = 0;
    for (int L = 1; L <= 3; L++) {
        const int cs = S >> L, fp = 1 << L;
        for (int cy = 0; cy < T2; cy++)
            for (int cx = 0; cx < T2; cx++) {
                int vis0 = 0, visL = 0;
                for (int y = 0; y < S; y++) for (int x = 0; x < S; x++) vis0 += px_a(im, w, cx * S + x, cy * S + y) != 0;
                for (int y = 0; y < cs; y++) for (int x = 0; x < cs; x++) visL += px_a(levels[L], lw[L], cx * cs + x, cy * cs + y) != 0;
                if (ncls[cy * T2 + cx]) CHECK(visL >= 1);
                if (L < 3) {
                    const int d = abs(visL * fp * fp - vis0);
                    if (d > worst_cov) worst_cov = d;
                    CHECK(d <= fp * fp);
                }
            }
    }
    printf("METRIC f2_worst_cell_coverage_error_px %d\n", worst_cov);
    /* temporal stability under sub-pixel panning, minified 4x / 8x / 12x */
    const double ms[3] = {4.0, 8.0, 12.0};
    for (int i = 0; i < 3; i++) {
        double vc0, mn0, ve0, vc1, mn1, ve1;
        render_metrics(lv, lw, lh, 4, 0, ms[i], &vc0, &mn0, &ve0);
        render_metrics(lv, lw, lh, 4, 1, ms[i], &vc1, &mn1, &ve1);
        printf("METRIC f2_minify_%gx_current_count_var %.3f min %.0f energy_var %.1f\n", ms[i], vc0, mn0, ve0);
        printf("METRIC f2_minify_%gx_proposed_count_var %.3f min %.0f energy_var %.1f\n", ms[i], vc1, mn1, ve1);
        CHECK(mn1 > 0);                         /* the stroke never vanishes */
        CHECK(vc1 < vc0);                       /* fewer pixels popping in/out */
    }
    for (int L = 1; L <= 3; L++) free(levels[L]);
    free(im); free(ncls);
}

/* ------------------------------------------------------------ F3 UV seam */
static void f3(void) {
    const int tw = 16, th = 8, w = tw * S, h = th * S;
    uint8_t ncls[16 * 8];
    for (int i = 0; i < tw * th; i++) ncls[i] = 127;
    uint8_t *im = img_new(w, h);
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        if (x < w / 2) px_set(im, w, x, y, 220, 30, 30, 127); else px_set(im, w, x, y, 30, 30, 220, 127);
    }
    /* proposed: levels 0..3 (stop at the native cell) */
    const uint8_t *pv[4]; uint8_t *pl[4]; int pw[4], ph[4];
    pl[0] = im; pw[0] = w; ph[0] = h;
    for (int L = 1; L <= 3; L++) { pw[L] = w >> L; ph[L] = h >> L; pl[L] = img_new(pw[L], ph[L]);
        CHECK(cm_build_level(im, w, h, ncls, tw, th, S, L, pl[L]) == 0); }
    for (int L = 0; L <= 3; L++) pv[L] = pl[L];
    /* naive full chain to 1 px rows (glGenerateMipmap-like) */
    int nl = 1; const uint8_t *nv[16]; uint8_t *nlv[16]; int nw[16], nh[16];
    nlv[0] = im; nw[0] = w; nh[0] = h;
    while (nw[nl - 1] > 1 && nh[nl - 1] > 1) {
        nw[nl] = nw[nl - 1] / 2; nh[nl] = nh[nl - 1] / 2; nlv[nl] = img_new(nw[nl], nh[nl]);
        cm_naive_level(nlv[nl - 1], nw[nl - 1], nh[nl - 1], nlv[nl]); nl++;
    }
    for (int i = 0; i < nl; i++) nv[i] = nlv[i];
    double worst_p = 0, worst_n = 0;
    for (double lod = 0; lod <= nl - 1; lod += 0.5)
        for (double x = 0.5; x <= w / 2.0 - S / 2.0; x += 1.0)          /* inside A, <= last texel centre */
            for (double y = 4; y < h; y += 8) {
                uint8_t rgb[3], c;
                cm_sample(pv, pw, ph, 4, x, y, lod, 1, 0, 0, w / 2.0, h, rgb, &c);
                if (rgb[2] - 30 > worst_p) worst_p = rgb[2] - 30;
                cm_sample(nv, nw, nh, nl, x, y, lod, 2, 0, 0, w / 2.0, h, rgb, &c);
                if (rgb[2] - 30 > worst_n) worst_n = rgb[2] - 30;
            }
    printf("METRIC f3_seam_max_blue_leak proposed %.0f naive %.0f (of 190)\n", worst_p, worst_n);
    CHECK(worst_p == 0 && worst_n > 0);
    for (int L = 1; L <= 3; L++) free(pl[L]);
    for (int i = 1; i < nl; i++) free(nlv[i]);
    free(im);
}

/* -------------------------------------------------------- F4 palette cycling */
static void f4(void) {
    enum { T = 16 };
    const int w = T * S;
    uint8_t idx[T * T];
    unsigned seed = 12345u;
    for (int i = 0; i < T * T; i++) { seed = seed * 1103515245u + 12345u; idx[i] = (uint8_t)((seed >> 16) & 15); }
    uint16_t pal[3][16];
    for (int k = 0; k < 16; k++) {
        const uint16_t base = (uint16_t)(((k * 2) & 31) | (((31 - k) & 31) << 5) | ((k & 31) << 10));
        pal[0][k] = k == 0 ? 0 : (uint16_t)(base | (k >= 12 ? 0x8000 : 0) | 1);
        pal[1][k] = k == 0 ? 0 : (uint16_t)((base ^ 0x1CE7) | (k >= 12 ? 0x8000 : 0) | 1);
        pal[2][k] = (k == 0 || k == 5) ? 0 : pal[0][k];
    }
    uint8_t *lv3[3][4];
    for (int p = 0; p < 3; p++) {
        uint8_t ncls[T * T];
        for (int i = 0; i < T * T; i++) { const uint16_t wd = pal[p][idx[i]]; ncls[i] = wd == 0 ? 0 : (wd & 0x8000 ? 255 : 127); }
        uint8_t *im = img_new(w, w);
        for (int y = 0; y < w; y++) for (int x = 0; x < w; x++) {
            const uint16_t wd = pal[p][idx[(y / S) * T + x / S]];
            px_set(im, w, x, y, (uint8_t)((wd & 31) << 3), (uint8_t)(((wd >> 5) & 31) << 3), (uint8_t)(((wd >> 10) & 31) << 3),
                   ncls[(y / S) * T + x / S]);
        }
        lv3[p][0] = im;
        for (int L = 1; L <= 3; L++) { lv3[p][L] = img_new(w >> L, w >> L); CHECK(cm_build_level(im, w, w, ncls, T, T, S, L, lv3[p][L]) == 0); }
    }
    int same12 = 1, diff_outside = 0, idx5_cells_differ = 0, idx5_cells = 0;
    for (int L = 0; L <= 3; L++) {
        const int lw = w >> L, cs = S >> L;
        for (int y = 0; y < lw; y++) for (int x = 0; x < lw; x++) {
            const uint8_t a0 = px_a(lv3[0][L], lw, x, y), a1 = px_a(lv3[1][L], lw, x, y), a2 = px_a(lv3[2][L], lw, x, y);
            if (a0 != a1) same12 = 0;
            if (a0 != a2 && idx[(y / cs) * T + x / cs] != 5) diff_outside++;
        }
    }
    for (int i = 0; i < T * T; i++) if (idx[i] == 5) { idx5_cells++; if (px_a(lv3[0][3], T, i % T, i / T) != px_a(lv3[2][3], T, i % T, i / T)) idx5_cells_differ++; }
    printf("METRIC f4_palette idx5_cells %d differ_at_native_level %d class_diff_outside_idx5 %d\n", idx5_cells, idx5_cells_differ, diff_outside);
    CHECK(same12 && diff_outside == 0 && idx5_cells > 0 && idx5_cells_differ == idx5_cells);
    for (int p = 0; p < 3; p++) for (int L = 0; L <= 3; L++) free(lv3[p][L]);
}

/* ------------------------------------------------------ F5 cutout RGB fringe */
/* Real packs store black RGB under cutouts. Visible samples next to a cutout then
 * pick up black through hardware bilinear (current, level 0) and through a naive
 * mip chain; the class-aware path fills cutout RGB (R5) and averages visible
 * children only (M2). Measured through the sampler at many sub-pixel points. */
static void f5(void) {
    enum { T = 16 };
    const int w = T * S;
    uint8_t ncls[T * T];
    /* cutout DISKS whose edges cross native cells (partial cells: M2 must average visible children only); the
     * native class of each cell is the class of its centre pixel (R1). */
    uint8_t *im = img_new(w, w);
    for (int y = 0; y < w; y++) for (int x = 0; x < w; x++) {
        const double dx1 = x + 0.5 - 37.0, dy1 = y + 0.5 - 41.0, dx2 = x + 0.5 - 90.0, dy2 = y + 0.5 - 85.0;
        const int hole = dx1 * dx1 + dy1 * dy1 < 21.0 * 21.0 || dx2 * dx2 + dy2 * dy2 < 13.5 * 13.5;
        if (!hole) px_set(im, w, x, y, 250, 170, 40, 127); else px_set(im, w, x, y, 0, 0, 0, 0);
    }
    for (int y = 0; y < T; y++) for (int x = 0; x < T; x++) ncls[y * T + x] = px_a(im, w, x * S + S / 2, y * S + S / 2);
    /* current: level 0 only, unfilled */
    const uint8_t *cur[1] = {im}; int cw[1] = {w}, chh[1] = {w};
    /* naive full chain from the unfilled image */
    int nl = 1; const uint8_t *nv[16]; uint8_t *nlv[16]; int nw[16], nh[16];
    nlv[0] = im; nw[0] = nh[0] = w;
    while (nw[nl - 1] > 1) { nw[nl] = nh[nl] = nw[nl - 1] / 2; nlv[nl] = img_new(nw[nl], nh[nl]);
        cm_naive_level(nlv[nl - 1], nw[nl - 1], nh[nl - 1], nlv[nl]); nl++; }
    for (int i = 0; i < nl; i++) nv[i] = nlv[i];
    /* proposed: R5-filled level 0 + class-aware levels 1..3 */
    uint8_t *fl = img_new(w, w); memcpy(fl, im, (size_t)w * w * 4); cm_fill_cutout_rgb(fl, w, w);
    const uint8_t *pv[4]; uint8_t *pl[4]; int pw[4], ph[4];
    pl[0] = fl; pw[0] = ph[0] = w;
    for (int L = 1; L <= 3; L++) { pw[L] = ph[L] = w >> L; pl[L] = img_new(pw[L], ph[L]);
        CHECK(cm_build_level(fl, w, w, ncls, T, T, S, L, pl[L]) == 0); }
    for (int L = 0; L <= 3; L++) pv[L] = pl[L];
    const double ref = luma((const uint8_t[]){250, 170, 40});
    /* M2 on its own: levels built straight from the UNFILLED image (black under cutouts) must still give every
     * visible texel the authored colour - the builder averages visible children only. */
    for (int L = 1; L <= 3; L++) {
        uint8_t *u = img_new(w >> L, w >> L);
        CHECK(cm_build_level(im, w, w, ncls, T, T, S, L, u) == 0);
        double mnu = 1e9;
        for (int i = 0; i < (w >> L) * (w >> L); i++)
            if (u[i * 4 + 3]) { const double l = luma(&u[i * 4]); if (l < mnu) mnu = l; }
        printf("METRIC f5_unfilled_build_level%d_min_visible_luma %.1f\n", L, mnu);
        CHECK(fabs(mnu - ref) < 1.0);
        free(u);
    }
    double mn[3] = {1e9, 1e9, 1e9};
    for (double lod = 0; lod <= 4.0; lod += 0.5)
        for (double y = 0.25; y < w; y += 1.37)
            for (double x = 0.25; x < w; x += 1.37) {
                uint8_t rgb[3], c;
                if (lod == 0 && cm_sample(cur, cw, chh, 1, x, y, 0, 0, 0, 0, w, w, rgb, &c)) { double l = luma(rgb); if (l < mn[0]) mn[0] = l; }
                if (cm_sample(nv, nw, nh, nl, x, y, lod, 2, 0, 0, w, w, rgb, &c)) { double l = luma(rgb); if (l < mn[1]) mn[1] = l; }
                if (cm_sample(pv, pw, ph, 4, x, y, lod, 1, 0, 0, w, w, rgb, &c)) { double l = luma(rgb); if (l < mn[2]) mn[2] = l; }
            }
    printf("METRIC f5_min_visible_luma current_lod0 %.1f naive_mips %.1f class_aware %.1f (authored %.1f)\n", mn[0], mn[1], mn[2], ref);
    CHECK(fabs(mn[2] - ref) < 1.0);
    CHECK(mn[0] < ref - 20 && mn[1] < ref - 20);
    for (int i = 1; i < nl; i++) free(nlv[i]);
    for (int L = 1; L <= 3; L++) free(pl[L]);
    free(fl); free(im);
}

/* ----------------------------------------------- F7 v2b: cm_flags_ex R2 policy export */
/* 3x3 native cells (s = 16), only the centre cell is native 127. The HD image paints the centre cell plus an
 * extension of D = 8 px into the right neighbour (full cell height) and a D x D block into the bottom-right neighbour
 * (4-connected to the right extension, so never an island), plus a 2x2 speck in the top-left cell (an island).
 * Expected R2 counts are computed here from the closed-form distance to the centre cell rectangle. */
static int f7_count(const uint8_t *flag, int n, int bit) {
    int k = 0;
    for (int i = 0; i < n; i++) k += (flag[i] & bit) != 0;
    return k;
}

static double f7_d(double dx, double dy, int metric) { return metric ? (dx > dy ? dx : dy) : sqrt(dx * dx + dy * dy); }

/* s = 16 and D = 8 keep every neighbour cell's centre pixel (offset 8) native, so R1 stays clean. */
static void f7(void) {
    enum { S = 16, T = 3, D = 8, NC = 5 };
    const int w = T * S, n = w * w;
    uint8_t ncls[T * T] = {0};
    ncls[1 * T + 1] = 127;
    uint8_t *im = img_new(w, w), *flag = (uint8_t *)malloc((size_t)n);
    for (int y = 0; y < w; y++)
        for (int x = 0; x < w; x++) {
            const int centre = x >= S && x < 2 * S && y >= S && y < 2 * S;
            const int right = x >= 2 * S && x < 2 * S + D && y >= S && y < 2 * S;
            const int diag = x >= 2 * S && x < 2 * S + D && y >= 2 * S && y < 2 * S + D;
            const int speck = x >= 2 && x < 4 && y >= 2 && y < 4;
            if (centre || right || diag || speck) px_set(im, w, x, y, 200, 50, 50, 127);
        }
    const double fr[NC] = {0.25, 0.25, 0.5, 0.5, 1.0};
    const int met[NC] = {0, 1, 0, 1, 0};
    int got[NC];
    for (int k = 0; k < NC; k++) {
        const double b = fr[k] * S;
        int exp_r2 = 0;
        for (int i = 0; i < D; i++) exp_r2 += (i + 0.5 > b) * S;                     /* right extension */
        for (int i = 0; i < D; i++)
            for (int j = 0; j < D; j++) exp_r2 += f7_d(i + 0.5, j + 0.5, met[k]) > b;  /* diagonal block */
        for (int y = 2; y < 4; y++)
            for (int x = 2; x < 4; x++) exp_r2 += f7_d(S - (x + 0.5), S - (y + 0.5), met[k]) > b;  /* speck */
        CHECK(cm_flags_ex(im, w, w, ncls, T, T, S, fr[k], met[k], flag) == 0);
        CHECK(f7_count(flag, n, 1) == S * D + D * D + 4);
        got[k] = f7_count(flag, n, 2);
        CHECK(got[k] == exp_r2);
        CHECK(f7_count(flag, n, 4) == 4);                                            /* only the speck */
        CHECK(f7_count(flag, n, 16) == 0);
        printf("METRIC f7_r2_px bound=%.2f metric=%d %d\n", fr[k], met[k], got[k]);
    }
    /* the policy matters: Euclidean flags more than Chebyshev at the same bound; a wider bound flags less */
    CHECK(got[0] > got[1] && got[2] > got[3] && got[0] > got[2] && got[2] > got[4] && got[4] == 4);
    /* the default policy (s/2, Euclidean) is exactly what cm_validate counts */
    CmReport r;
    CHECK(cm_validate(im, w, w, ncls, T, T, S, &r) == 0);
    CHECK(r.r2_displaced_px == (uint64_t)got[2] && r.r4_island_px == 4 && r.r1_centre_bad == 0);
    /* argument validation */
    CHECK(cm_flags_ex(im, w, w, ncls, T, T, S, 0.5, 2, flag) == -1);
    CHECK(cm_flags_ex(im, w, w, ncls, T, T, S, -0.1, 0, flag) == -1);
    CHECK(cm_flags_ex(im, w + 1, w, ncls, T, T, S, 0.5, 0, flag) == -1);
    free(im); free(flag);
}

int main(void) {
    f1(); f1b(); f1c(); f2(); f3(); f4(); f5(); f7();
    printf("checks %d failures %d\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
