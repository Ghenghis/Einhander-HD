/* class_mip.h — PRIVATE prototype (claude-einhander): whole-cell class ownership
 * and class-aware mips for PS1 HD replacement textures (DESIGN.md). Host-only C;
 * no GL. Alpha is a PS1 CLASS (0 cutout, 127 STP clear, 255 STP set), never
 * opacity. Images are RGBA8, row-major, width = tw*s, height = th*s for an
 * integer scale s (power of two for mips). */
#ifndef CLASS_MIP_H
#define CLASS_MIP_H
#include <stdint.h>

#ifdef _WIN32
#define CM_API __declspec(dllexport)
#else
#define CM_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct CmReport {
    uint64_t pixels;
    uint64_t cells;
    uint64_t r1_centre_bad;      /* centre pixel class != native               */
    uint64_t r2_displaced_px;    /* deviant px farther than s/2 from a native  *
                                  * cell of its class (v2)                     */
    uint64_t r3_uniform_bad_px;  /* uniform native nbhd but pixel differs      */
    uint64_t r4_island_px;       /* deviant px whose class component (across   *
                                  * cells) reaches no non-deviant px (v2)      */
    uint64_t r5_fringe_px;       /* cutout px 4-adjacent to a visible px whose *
                                  * RGB differs from the deterministic fill    */
    uint64_t cells_bad;          /* cells with any R1..R4 violation            */
    uint64_t pinhole_cells;      /* R1 ok but R3/R4 violated (centre-only fix) */
    uint64_t nonclass_px;        /* alpha not in {0,127,255}                   */
} CmReport;

typedef struct CmRepairStats {
    uint64_t class_changed;
    uint64_t became_visible;
    uint64_t became_cutout;
    uint64_t rgb_from_cell;      /* new visible px coloured from its cell      */
    uint64_t rgb_from_native;    /* ... from the native texel colour           */
    uint64_t cutout_rgb_filled;  /* R5 fill writes (invisible pixels only)     */
    uint64_t visible_rgb_changed;/* must stay 0: authored RGB of pixels that   *
                                  * stay visible is never modified             */
    uint64_t passes;             /* v2: repair passes run (iterate to clean)   */
    uint64_t residual_violations;/* v2: violations left after CM_MAX_PASSES    */
} CmRepairStats;

/* Validate level 0 against rules R1..R5. ncls: tw*th native classes. */
CM_API int cm_validate(const uint8_t *rgba, int w, int h, const uint8_t *ncls,
                       int tw, int th, int s, CmReport *out);

/* Whole-cell class-ownership repair in place, iterated until clean (v2): R1/R2/R4
 * violators take the native class of their cell; R5 fill of cutout RGB. nrgb:
 * optional tw*th*3 native colours. Returns 0 clean, 1 residual violations after
 * CM_MAX_PASSES, -1 error. */
CM_API int cm_repair(uint8_t *rgba, int w, int h, const uint8_t *ncls,
                     const uint8_t *nrgb, int tw, int th, int s,
                     CmRepairStats *st);

/* Deterministic R5 fill: every cutout pixel takes the RGB of the nearest visible
 * pixel (4-neighbour BFS, scan-order ties). Visible pixels untouched. Returns
 * the number of pixels written, -1 on allocation failure. */
CM_API int64_t cm_fill_cutout_rgb(uint8_t *rgba, int w, int h);

/* Class-aware mip level L (1..log2(s)) from level 0, into dst ((w>>L)*(h>>L)*4).
 * M1 never crosses a native cell; M2 RGB = mean of visible level-0 pixels in
 * the footprint; M3 coverage-preserving visibility per cell (a cell whose
 * native class is visible keeps >= 1 visible texel), STP by majority (ties ->
 * native); M4 level log2(s) == native classes; cutout texels R5-filled. */
CM_API int cm_build_level(const uint8_t *lvl0, int w, int h, const uint8_t *ncls,
                          int tw, int th, int s, int L, uint8_t *dst);

/* Naive reference: glGenerateMipmap-like box average of RGBA over the whole
 * image (crosses cells, averages cutout RGB and alpha). dst (w>>1)*(h>>1)*4. */
CM_API int cm_naive_level(const uint8_t *src, int w, int h, uint8_t *dst);

/* Sampler emulation. levels[0] = level 0, levels[k] = level k. Coordinates in
 * level-0 pixel units. lod is the requested LOD. Returns 1 visible (rgb set,
 * cls set), 0 discarded.
 *   mode 0 = CURRENT runtime: class texelFetch level 0 under the point, RGB
 *            bilinear at level 0 (GL_LINEAR, no mips).
 *   mode 1 = PROPOSED: lod clamped to [0, nlevels-1]; class texelFetch at
 *            round(lod); RGB trilinear between floor/ceil(lod).
 *   mode 2 = NAIVE full chain (glGenerateMipmap + LINEAR_MIPMAP_LINEAR, class
 *            from the trilinear alpha >= threshold). */
/* v2b ANALYSIS export (does not change any rule): per-pixel flags of the v2 classifier with a chosen R2 policy,
 * bound = bound_frac * s, metric 0 Euclidean / 1 Chebyshev. bound_frac 0.5 + metric 0 is exactly what
 * cm_validate/cm_repair use. flag_out: w*h bytes; bits 1 deviant (class != native class of the cell), 2 R2
 * displaced, 4 R4 island, 8 R3 diagnostic, 16 R1 centre, 32 reached by the R4 search. Returns 0, -1 on bad args. */
CM_API int cm_flags_ex(const uint8_t *rgba, int w, int h, const uint8_t *ncls, int tw, int th, int s,
                       double bound_frac, int metric, uint8_t *flag_out);

CM_API int cm_sample(const uint8_t *const *levels, const int *lw, const int *lh,
                     int nlevels, double x, double y, double lod, int mode,
                     double clamp_x0, double clamp_y0, double clamp_x1, double clamp_y1,
                     uint8_t rgb[3], uint8_t *cls);

#ifdef __cplusplus
}
#endif
#endif
