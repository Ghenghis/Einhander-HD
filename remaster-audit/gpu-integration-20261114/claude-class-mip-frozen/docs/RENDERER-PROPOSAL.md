# Renderer proposal for class-aware levels (claude-einhander, 2026-11-14)

**A proposal only. The canonical `gpu_gl_renderer.c` is unchanged.** It applies `DESIGN.md` rule M5 to `HD_FS` and the HD
upload, behind an opt-in that defaults off. The rules it relies on are prototyped and host-tested in `proto/`.

## Offline: pack composer
1. **Level 0, R5 fill.** Every cutout pixel (alpha 0) takes the RGB of the nearest visible pixel (`cm_fill_cutout_rgb`).
   - Only invisible pixels change, so authored visible RGB, sizes and classes are byte-identical.
   - This alone removes the dark bilinear fringe measured in F5: visible edge luma goes 71.9 → 179.1 for authored 179.1.
2. **Whole-cell repair only where proven necessary.** `cm_repair` runs on keys whose CRC-proven native source shows R2–R4
   violations.
   - Visible RGB never changes; the repair reports `visible_rgb_changed = 0` as a proof field.
3. **Class-aware levels 1..log2(s).** `cm_build_level` output is stored beside the PNG, for example `KEY.L1.png` …
   `KEY.L3.png`, or as one DDS with explicit levels. Each level is class-exact by construction, and level log2(s) equals
   the native classes.

## Upload (`hd_tex_object` / mip path, today `hd_facade_motion_sampling`)
- Upload level 0 as now, then each provided level k with `glTexImage2D(GL_TEXTURE_2D, k, …)`. **Never `glGenerateMipmap`**:
  it averages cutout RGB and alpha and crosses cells, as measured in F3 and F5.
- Set `GL_TEXTURE_BASE_LEVEL = 0` and `GL_TEXTURE_MAX_LEVEL = log2(s)`. That stops at the native cell, so no atlas-cell or
  UV-region bleed (F3 leak 0 vs naive 82/190).
- Memory per key is at most +33 %; for s = 8, levels 1–3 add 1/4 + 1/16 + 1/64 of level 0.

## `HD_FS` change (filter mode only; point mode unchanged)
```glsl
uniform int u_hd_class_levels;   /* 0 = current behaviour; N = levels 0..N-1 are class-aware */
...
  float class_alpha;
  if (u_filter != 0 && u_hd_class_levels > 0) {
    /* derivatives taken before wrap/clamp, as the facade path already does */
    vec2 px_dx = dFdx(uv) / u_hd_dim * vec2(hd_size), px_dy = dFdy(uv) / u_hd_dim * vec2(hd_size);
    float lod = clamp(log2(max(length(px_dx), length(px_dy))), 0.0, float(u_hd_class_levels - 1));
    int lc = int(floor(lod + 0.5));
    ivec2 lsz = textureSize(u_hd, lc);
    ivec2 lpx = clamp(ivec2(floor(authority_pos * vec2(lsz))), ivec2(0), lsz - ivec2(1));
    class_alpha = texelFetch(u_hd, lpx, lc).a;          /* categorical: one texel of one level */
  } else {
    class_alpha = texelFetch(u_hd, authority_px, 0).a; /* today's rule */
  }
  ...
  c = textureLod(u_hd, (u_hd_off + suv) / u_hd_dim, lod);   /* trilinear over class-aware levels */
```
- **Class semantics are unchanged:** 0 discards; ≥ 0.5 means STP; 127 is STP clear. Only the level the class comes from
  changes, and every level holds only {0, 127, 255}.
- **Emissive and skin detail** keep using `rgb_pos` at level 0. The emissive mask needs the same level treatment later.
  Not in scope here.
- **Point mode** (`u_filter == 0`) stays exactly as now: centre and level 0.

## What a live A/B must measure (root, when the user returns the GPU)
- Pick one atlas key with thin neon (95A3BCF8 region O, 60245B3A) and one cutout-heavy sprite page.
- Compare current against class-aware, with a sub-pixel pan in motion.
- **Pass:**
  - fewer pixels popping in and out at distance (F2 measured count variance 1312.7 → 0.0 at 8× on the fixture);
  - no dark fringes at cutouts;
  - no colour bleed between atlas cells;
  - identical look at 1:1;
  - frame time inside the existing budget.
