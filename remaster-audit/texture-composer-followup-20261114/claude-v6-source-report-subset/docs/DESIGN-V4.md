# Private opt-in class-aware mips + RGB edges on the frozen v61 renderer: design v4 (claude-einhander, 2026-11-14)

This builds on `DESIGN-V3.md`, which is unchanged. **Frozen v3 is preserved exactly.** v4 adds root's reviewed RGB-edge
renormalization (root `N/rgb-edge-gpu-r4/HD_FS.frag` 5b3929b5, approved for integration in msg_5e12afbf), with the
conflict fix from my review.

## Opt-ins: both default OFF, both exactly "1", both limited to verified sidecar keys
- `PSXRECOMP_HD_CLASS_MIPS=1` turns on prepared class levels, as in v3.
- `PSXRECOMP_HD_RGB_EDGES=1` turns on RGB edges (new).
- Either one needs `PSXRECOMP_HD_CLASS_MIPS_DIR`. Any other value, such as "true" or "0", leaves the feature off;
  this is tested.
- **Has-cutout flag:** sidecar flag bit 1 (`HDCM_FLAG_HAS_CUTOUT`) is set offline when the decoded level 0 has any
  cutout texel. It sits inside the self-hashed sidecar and is bound to the level-0 hash, which admission re-checks, so
  it is identity-bound. Opaque pages get `rgb_edges = 0` and skip the extra fetches entirely. Unknown flag bits are
  rejected.
- **Admission:** the same strict path as v3 (preload verify; draw-time level-0 hash and R1). The RGB flag is set only
  after admission passes. Class-level uploads happen only when class levels are on; in RGB-only mode there is no GL
  level work at all.

## HD_FS (pure addition)
- **Helper `hd_visible_rgb(pos, level)`:**
  - a 4-tap bilinear over visible taps only, renormalized;
  - same taps and clamp as GL_LINEAR with CLAMP_TO_EDGE;
  - `.a` returns the summed visible weight.
- **Branch,** taken when `u_hd_rgb_edges != 0 && u_filter != 0 && !native_edge`, placed after RGB selection and before
  the `native_edge` override:
  - **`u_hd_class_levels > 0`** (facade or non-facade, the conflict fix): only for lod < 1, where lod is the same rule
    as the class LOD. When the level-0 footprint has a cutout tap, RGB becomes `mix(visible L0, visible L1, lod)`, with
    the fallbacks root defined. Otherwise the hardware RGB is kept exactly.
  - **`u_hd_class_levels == 0`, non-facade only:** the level-0 visible renormalization when the footprint mixes visible
    and cutout taps.
  - Class/STP, discard support, the point path and the native-edge path are unchanged.
- **Known differences:**
  - On edge fragments (a cutout tap in the footprint, lod < 1) the isotropic 4-tap visible bilinear replaces the
    hardware's anisotropic RGB taps.
  - Cost is up to 8 extra texelFetches plus one textureLod per fragment, only for opted-in has-cutout slots in filter
    mode.

## Evidence
- **Host run** (`runs/<UTC>`, exit code follows the verdict):
  - fixtures, including flag parsing;
  - 28 `.inc` mutants;
  - the **exact glue** in the host harness across modes: off, bad env, both on, levels only, RGB only, and an opaque
    RGB control (region-O sidecar, expected flag 0);
  - 8 **glue mutants**;
  - real pages, sidecars, patch, compile-only with control, glslangValidator.
- **GL self-test v4,** compiled only (the user holds the GPU). It adds:
  - RGB-edge variants A_rgb, C_rgb and N_rgb;
  - checks for: the lod-0 fringe gone; discard support and output alpha identical with RGB edges on and off; the point
    path unchanged; an all-opaque page exactly unchanged at every scale.
  - Root runs it once the user returns the GPU.
