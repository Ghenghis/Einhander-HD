# Whole-cell class ownership and class-aware mips: design (claude-einhander, 2026-11-14)

This is a private prototype. The canonical runtime, frozen art and the view-provenance v1/v2/v3 sources are unchanged. CPU
only. Every statement about current behaviour cites the canonical source.

## 1. What the runtime actually does today (source-grounded)
Source: `windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c`, `HD_FS` (lines 1325–1441) and HD texture setup
(3320–3460, 4049).

- **The mode in play is filter mode.** The release `settings.toml` has `texture_filtering = "bilinear"` →
  `g_video_texfilter = 1` → `gr_set_texture_filter` → `s_tex_filter = 1` (4217) → `u_filter = 1` for HD draws (4049).
- **The class authority is a level-0 texel under the fragment.** In filter mode `class_uv = uv + u_shift` (sub-texel, not
  snapped; 1383) → `authority_px = floor((u_hd_off + class_uv)/u_hd_dim · size)` → `texelFetch(u_hd, authority_px, 0).a`
  (1390–1392).
  - The class therefore comes from **whichever HD pixel of the native cell the fragment lands on**, always from level 0.
  - Only point mode (`u_filter == 0`) snaps to the texel centre `floor(uv) + 0.5` (1384). So the centre convention
    (`floor((i + 0.5)·s)`) is the whole rule only in point mode.
  - **In filter mode every HD pixel of a cell is authoritative**: an isolated centre stamp leaves the rest of the cell
    wrong. This is Codex's pinhole objection, and the source confirms it.
- **RGB is hardware-filtered without class awareness.** `c = texture(u_hd, …)` (1417), or `textureGrad` with facade/world
  mips (1415), with `GL_LINEAR`.
  - Neighbouring pixels blend whatever their class, so the RGB stored under a cutout (class 0, usually black) bleeds into
    visible edges as a dark fringe.
- **There are no mips except for the facade/world opt-ins** (3431–3460). Those use `glGenerateMipmap`, a plain box average
  of RGBA. It mixes cutout RGB in, and averages across atlas cells and UV regions at coarse levels.
  - The comment states that lower-level alpha "is deliberately never authoritative". The class stays level 0 at a single
    pixel, so under minification cutout edges and thin strokes alias (they twinkle). Region O of 95A3BCF8 has exactly this
    known limit.
- **Class values:** 0 = discard; ≥ 0.5 (255) = STP set; 0 < a < 0.5 (127) = STP clear (1369–1372, `hd_word_alpha` 2834).
  The semi passes discard by STP (1426–1427), so a wrong 127/255 pixel changes which pass draws it.

## 2. Proof rules for level 0: whole-cell class ownership
Notation:
- the native class grid `N[i, j]` comes from the CRC-proven words/CLUT, and scale `s` is integer;
- HD pixel `p` lies in native cell `c(p) = floor(p / s)`;
- `Nb(c)` is the set of native classes in the 3×3 native neighbourhood of `c`, clamped at the image border.

| Rule | Statement | Why |
|---|---|---|
| **R1 centre** | class(p) = N[c] at `p = floor((i + 0.5)·s)` | Point-mode authority (1384) and the existing convention |
| **R2 neighbourhood** | class(p) ∈ Nb(c(p)) for every p | A sub-native contour may only move a class boundary that exists natively; it never invents a class away from one |
| **R3 uniform interior** | if Nb(c) = {C}, every pixel of the cell is C | Filter mode reads any pixel of the cell (1390–1392); a uniform native area must be uniform in HD |
| **R4 no islands** | every 4-connected component of class X ≠ N[c] inside cell c must touch a cell edge whose neighbouring cell has class X | Sub-native contours come from the neighbouring cell; an isolated speck is an error, e.g. a pinhole stamp's ring of old class |
| **R5 cutout RGB fill** | RGB of a class-0 pixel equals the RGB of the nearest visible pixel (bleed fill) | Hardware bilinear and mips read cutout RGB (1417); a filled cutout cannot fringe. The RGB of visible pixels is never touched |

A centre-stamped repair that leaves the rest of the cell in the old class fails R3 and R4 (the ring of old class around a
correct centre) and must not be accepted as a mask fix.

**Repair (prototype):**
- Pixels violating R2, R3 or R4 take the native class of their cell.
- A pixel that becomes visible takes RGB from the nearest visible pixel in its own cell with the new class, else the
  cell's native RGB. This is reported.
- Cutout pixels get the R5 fill.
- **Authored RGB of pixels that were already visible is never changed.** Sizes are unchanged. No stock replacement, no cap.

## 3. Class-aware mip chain
- **M1 levels stop at the native cell.**
  - The maximum level is `Lmax = log2(s)`; one level-`Lmax` texel is exactly one native cell.
  - No level averages across native cells, so atlas cells, UV regions, sprite gutters and palette-cycling cells never bleed
    into each other.
  - Below native resolution the image is the native texture, which is faithful.
- **M2 RGB:** the average of the **visible** children only. If no child is visible, use the R5 fill of the same cell.
- **M3 class at 0 < L < Lmax:**
  - **coverage-preserving visibility**: within each native cell, set as many level-L texels visible as the rounded
    level-0 visible coverage of the cell implies, choosing the texels with the highest child coverage (ties toward the
    cell's native class);
  - STP (127 vs 255) is the majority among visible children, ties going to the native class.
  - Thin strokes therefore keep their coverage instead of vanishing under a majority rule.
- **M4 class at Lmax:** exactly N[c].
- **M5 sampling (shader proposal):**
  - LOD from the existing derivatives (`facade_dx`/`facade_dy`, 1378): `lod = clamp(log2(max(|dx|, |dy|)·size), 0, Lmax)`;
  - the class is `texelFetch` at level `round(lod)` of the pixel under the fragment;
  - RGB is `textureLod`/trilinear over levels 0..Lmax with `GL_TEXTURE_MAX_LEVEL = Lmax`;
  - point mode stays as now, at the centre and level 0.

## 4. What the fixtures must show (host, CPU)
| Fixture | Assertion |
|---|---|
| F1 adjacent 0/127/255 | Smooth sub-native contours between all class pairs pass R1–R5. A centre-only stamp over a wrong cell fails R3/R4, and the repair makes it pass while visible RGB stays identical. Level Lmax equals N |
| F2 thin neon stroke (1 native texel, class 127 on 0) | Coverage per level is within one texel of level 0 per cell. The stroke is never empty at any L ≤ Lmax. Temporal shimmer of a minified stroke (sub-pixel pan) is lower than current level-0-only sampling |
| F3 UV seam / atlas | No colour from a neighbouring region in any level ≤ Lmax inside the prim limits. A naive full chain (glGenerateMipmap-like) leaks; measured for contrast |
| F4 palette animation | Two CLUTs with identical classes give identical class pyramids. A CLUT where one index is transparent changes only the cells with that index |
| F5 minification RGB | No class-aware level contains cutout RGB, so no dark fringe. A naive average does, which is measured |
| F6 real data (read-only) | Run R1–R5 on real pack PNGs: livepack-classfix-v2 files, my K-panel page2048 and untouched pages. Count whole-cell violations to show how big the pinhole problem is |

## 5. Known limits
- Changing LOD selection and class reads in the shader is renderer work for root. This prototype supplies the rules, the
  CPU builder and the emulated sampler only.
- Mips cost +33 % texture memory per key. Only the levels up to Lmax are needed: s = 8 adds levels at 1/4, 1/16 and 1/64.
- R2/R4 permit sub-native contours only from neighbouring native classes. Authored art that deliberately invents a class
  far from any native boundary would be flagged; that is intended.
