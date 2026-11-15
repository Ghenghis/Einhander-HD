# Private opt-in class-aware mips on the frozen v61 renderer: design (claude-einhander, 2026-11-14)

Status: **DESIGN ONLY.** No renderer copy has been patched yet. No compile until root releases CPU-QUIET. Root owns linking,
any executable, cache staging, live census and qualification, and GPU runs and GitHub publication.

## Inputs (read-only, never modified)
- `remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/src/gpu_gl_renderer.c`
  - sha256 `90c6a4e15d8e956ca7be28f1cd5219add1e1c2ee37f31fbd361711db0510e3a1`, 6,992 lines.
  - Byte-identical to `sampling-build-v58-frame-phases/gpu_gl_renderer.c`.
  - The canonical `windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c` (92d08057…) lacks the v58 diagnostics and is not
    used.
- `.../sampling-build-v61-view-metrics-r2/include/gpu_gl_renderer.h`, sha256 `fb533ebe…`.
- The prototype: `class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b`, `cm_build_level` (M1–M4, R5).

## v61 facts this design rests on (line numbers in the v61 file)
- **HD_FS (1342–1460).**
  - The class authority is `texelFetch(u_hd, authority_px, 0).a` (1412).
  - In filter mode, RGB is either `textureGrad(u_hd, …, facade_dx, facade_dy)` when `u_hd_facade_motion != 0`
    (1432–1436), or plain `texture()` (1437).
  - The point path (`u_filter == 0`, 1414–1422) samples exact texels with `texture()`.
  - `facade_dx = dFdx(uv)/u_hd_dim` is a normalised derivative (1398).
- **Opt-in facade/world experiment.**
  - Gate: `hd_stage1_world_sampling_match` (3606–3614) selects the **95A3BCF8 64×256-word atlas**, all admitted
    palettes, depth 0. `PSXRECOMP_HD_WORLD_SAMPLING=1` and filter mode are required.
  - `hd_facade_motion_sampling` (3684–3718) runs `glGenerateMipmap` once per slot.
  - The comment at 3681–3683 says generated-level alpha is never authoritative and the class stays at level 0.
  - Consequence:
    - the RGB mips average cutout RGB into visible texels (dark fringes, F5);
    - the class never minifies, so thin strokes and distant windows pop (F2: the stroke vanishes at 8× and 12×).
- **HD upload.**
  - Level 0 is uploaded in `hd_tex_object` (3838–3912).
  - Decoded pixels (`px.rgba`, `px.stride`) are valid only on the non-resident path of the draw
    (4178–4204, then `hd_tex_object` at 4346); slots keep a `pixels` pointer that can outlive the decode lease.
  - **So class-aware levels must be built at upload time, from `px`**, not lazily from `slot->pixels`.

## Opt-in and scope
- **New environment variable `PSXRECOMP_HD_CLASS_MIPS=1`.** It is read once, in the same place as
  `hd_facade_motion_init`.
- **It is active only when all of these hold:**
  - the existing world or facade experiment matches the draw (`hd_facade_motion_match(&m,&q)`);
  - filter mode is on (`s_tex_filter`);
  - the slot is square, with power-of-two scale `s = slot->w / (upload_width_words · (4 >> depth))` ≥ 2, and the HD
    width is exactly `native_w · s`.
- **The first target is 95A3BCF8 region O** (60245B3A green and 07A9568D pink, the distant windows). Both keys are
  whole-cell clean: `runs-breakdown-v2b` shows 0 R1/R2/R4.
- **Unset, or not matched: behaviour is unchanged.**
  - No new GL calls run, and the HD_FS branch is skipped (uniform 0).
  - The point path is untouched: the new shader branch requires `u_filter != 0`, and the MIN_FILTER stays
    GL_NEAREST/GL_LINEAR when filtering is off.

## Changes to the private copy
All changes are made by an anchored patch generator; each anchor is asserted to occur exactly once.
1. **`#include "hd_class_mips.inc"`.** This holds the builder as static C99 with no printf, no GL and no allocation per
   texel: a port of `cm_build_level` with one difference. The cell class authority is the **level-0 centre pixel**
   `floor((i+0.5)s)`, i.e. the point-mode class. The renderer has no native class map; for R1-clean keys this equals the
   native class.
   - The rules: M1 never crosses a cell; M2 RGB is the mean of visible children; M3 preserves coverage and keeps a
     visible cell never-empty; M4 sets level log2(s) to the cell classes; R5 fills the cutout RGB of every level.
2. **`HdTexSlot` gains `unsigned class_mip_levels`** (0 means none).
3. **In the draw path**, after `hd_tex_object` on a non-resident draw (`px` valid), when the gate matches and
   `class_mip_levels == 0`:
   - build levels 1..log2(s) from `px.rgba/px.stride` into one scratch buffer;
   - upload each with `glTexImage2D(level L)`;
   - set `GL_TEXTURE_MAX_LEVEL = log2(s)`;
   - set `facade_mips_ready = 1`, `facade_mip_levels = log2(s)+1`, `class_mip_levels = log2(s)`, and the mip byte
     accounting.

   The existing `glGenerateMipmap` then never runs for that slot. Allocation failure leaves the slot level-0 only and
   bumps a counter.
4. **`hd_facade_motion_sampling`**: with class mips enabled, a matched slot that has `class_mip_levels == 0` gets **no**
   `glGenerateMipmap` and is sampled as level-0 only. The two mip kinds never mix.
5. **Uniform `u_hd_class_levels`.** It is set on every HD draw: the slot's `class_mip_levels` when the facade/world
   sampling for that draw is active, else 0. Uniform state belongs to the program, so it is set every draw, as the
   existing comment at 4379 requires.
6. **HD_FS.** Insert directly after the existing `class_alpha = texelFetch(..., 0)` line:
   ```glsl
   if (u_filter != 0 && u_hd_facade_motion != 0 && u_hd_class_levels > 0) {
     vec2 gx = facade_dx * vec2(hd_size), gy = facade_dy * vec2(hd_size);     /* HD px per screen px */
     float lod = clamp(log2(max(max(length(gx), length(gy)), 1e-8)), 0.0, float(u_hd_class_levels));
     int lc = int(floor(lod + 0.5));
     if (lc > 0) {
       ivec2 lsz = textureSize(u_hd, lc);
       ivec2 lpx = clamp(ivec2(floor(authority_pos * vec2(lsz))), ivec2(0), lsz - ivec2(1));
       class_alpha = texelFetch(u_hd, lpx, lc).a;
     }
   }
   ```
   - **RGB:** the existing `textureGrad` now samples class-aware RGB levels (visible-only means plus R5 fill), so no
     cutout bleed.
   - **LOD rule:** the class LOD uses the isotropic max rule, so with anisotropy RGB may use a finer level than the
     class. This is conservative (it suppresses shimmer) and is documented as a known difference.
7. **Counters.** A static struct counts levels built, failures, bytes and build ticks, with no printing. Root can expose
   it through the existing diagnostics if wanted.

## Host verification (after root releases quiet; all in `renderer-v61-classmip/runs/<UTC>/`)
1. **Builder equivalence.** `hd_class_mips.inc` compiled on the host must produce levels **byte-identical** to
   proto-v2b `cm_build_level` when given ncls = the centre classes:
   - on fixtures F2 (strokes), F3 (seams) and F5 (fringe);
   - on the real 95A3 region-O keys 60245B3A and 07A9568D at 2048 px.

   Mutants must be caught.
2. **Build cost.** Host timing of the builder on the 2048² and 4096² 95A3 pages. This is a one-time first-upload cost
   per palette key, and it is reported as a stutter risk.
3. **Patch generator.** Anchors asserted; it writes the private copy plus `patch-receipt.json` (input/output sha256,
   line counts). A **guard audit** checks that every inserted statement is reachable only under
   `s_hd_class_mips && match`, or `u_hd_class_levels > 0 && u_filter != 0`.
4. **Compile only.** The patched TU is compiled with the exact v61 compile command (from its `.rsp`/log) into my run
   folder: one clang process at below-normal priority, producing an object only, with no link.
5. **Optional.** The extracted HD_FS string is validated with an offline GLSL validator, if one exists on CPU. Otherwise
   that validation waits for root's GPU run.

## Handover to root (not mine)
- Link a private executable.
- Run an A/B on 95A3 region O: world sampling with `glGenerateMipmap` (v61 as is) vs world sampling plus
  `PSXRECOMP_HD_CLASS_MIPS=1`.
- Use the same route and frames, and capture distant-window popping and edge fringes.
- No GPU performance acceptance is claimed by me.

## RISE (82831823): separate private alternatives, following root's msg_36952fa4
- **Policy:** connectivity-only plus R1/source is primary; s/2 is diagnostic.
- **Measured per key under connectivity-only:** about 24k visible violating px in about 375 cells, with 295
  centre-wrong cells and 464 island px. The rest are classes absent from the native 3×3 neighbourhood: holes inside
  native-opaque areas, and opaque pixels of a class the native neighbourhood lacks.
- **Alternatives to build:**
  - **A:** repair only the connectivity-only violators on drawn cells, whole-cell. Authored RGB and registration are kept
    wherever the pixel stays visible.
  - **B:** label-only. A per-cell map marking where the authored font shape deliberately differs: cells inside or
    outside the native silhouette but connected, with the class present nearby. This is for a human decision, with no
    pixel change.

  Neither restores stock letterforms globally. Both come with before/after review crops on drawn texels.
