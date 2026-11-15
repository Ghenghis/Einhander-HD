# Whole-cell v2 violations: what is actually visible (claude-einhander, 2026-11-14)

Private, read-only analysis. CPU only, one below-normal process at a time. No pack, frozen set, runtime source or earlier run
was modified. This follows `DESIGN-V2.md` and the v2 real-data audit `runs-f6-v2/20261114T095517Z`.

## Questions
1. Which v2 violations are **transparency** errors and which are **STP-only**?
   - **hole**: the native texel is visible, the HD pixel is cutout.
   - **added**: the native texel is cutout, the HD pixel is visible.
   - **STP-only**: the class differs only between 127 and 255.
2. Which violations fall on texels the game was **seen to draw**?
3. How much depends on the R2 **policy** (the s/2 Euclidean bound)?
4. Are the mismatches **registration offsets** (the right shape, moved) or **shape changes**?

## Method
**Classifier.** `proto-v2b` is the delivered `proto-v2` plus one analysis export, `cm_flags_ex`: per-pixel flags with a
selectable R2 bound and metric. The rules are unchanged; the default policy is exactly `cm_validate`.
- Run `runs-v2b/20261114T100659Z`: pass, 7,410 checks, 16/16 mutants.
- New fixture F7: hand-computed R2 counts for each policy, Euclidean vs Chebyshev, and cm_validate equivalence.
- New mutants: default bound 1.0, default metric Chebyshev, metric ignored, bound ignored, bad metric accepted.

**Draw evidence.** The source is every `capture.jsonl` under `stage1-completion-20261112/*/hd-on_rewind-off/*/`: 27 logs,
326,109 draw events.
- Each event's uv triangle is mapped to key-local native texels:
  - **exact_region** keys: origin from the pack's `ExactRegions.tsv`, `((vram_x - page_x)·tpw, vram_y - page_y)`. All
    113,239 events land inside the key, and `source_word_xy == floor(local uv min / tpw)` holds for every one.
  - **upload** keys: `source_word_xy` is the word offset of the drawn rectangle inside the key. The origin is the
    per-key intersection over all events; when it is ambiguous by less than one word, the fitting origins are unioned
    (conservative).
  - **native_page** keys: page origin.
- A texel counts as drawn when its square overlaps a drawn triangle (3×3 sub-sample test).
- `semi >= 0` marks a semi-transparent primitive.
- Only 4 keys are unmapped; those are treated as fully drawn.

**Visibility classes.** These follow HD_FS:
- **visible-transparency**: hole or added on a drawn texel.
- **visible-blend**: STP-only on a texel drawn by a semi-transparent primitive. `u_semipass` selects the pass by STP.
- **mask-bit-only**: STP-only on texels drawn only by opaque primitives. The colour is identical; only the written mask
  bit differs.
- **not-drawn-in-capture**: no captured draw covers the texel.

> **Caveat (coverage):** the captures are Stage 1 only and sampled. One title-menu quad has only one of its two triangles
> logged. Drawn masks are lower bounds, so the visible counts are **lower bounds**, and "not drawn" does not mean "never
> drawn".

**Superseded run.** `runs-breakdown/20261114T101011Z` (result f7169d3e) mapped every uv relative to the page origin. That
treated 608 exact-region and upload keys as fully drawn and overstated visibility. It is kept as produced; use v2b.

## Results: `runs-breakdown-v2b/20261114T102254Z`
Result sha256 `43612daa24bf69b63fabd7e7b1c14daa0dd05fffe05468bff78cd7a9c7e43ee3`. The default-policy R1/R2/R4 totals equal
`runs-f6-v2` exactly for all three groups (`crosscheck_vs_f6_v2`).

### Violation kinds and visibility (v2 default policy)

| Group | Keys checked / violating | hole px | added px | STP px |
|---|---:|---:|---:|---:|
| world-v4 pack | 1,481 / 677 | 4,093,116 | 2,376,461 | 5,225,163 |
| livepack-classfix-v2 | 86 / 85 | 107,623 | 476,097 | 1,258,838 |
| K panel page2048 | 1 / 1 | 0 | 0 | 82,821 |

| Group | Visible transparency | Visible blend | Mask-bit only | Not drawn in capture |
|---|---:|---:|---:|---:|
| world-v4 pack | 1,583,169 px (241 keys) | 12,929 px (27 keys) | 211,124 px | 9,887,518 px |
| livepack-classfix-v2 | 31,732 px (66 keys) | 0 | 178,017 px | 1,632,809 px |
| K panel page2048 | 0 | 0 | 0 | 82,821 px |

- In the world-v4 pack, 406 of the 677 violating keys violate only on texels not drawn in these captures, and 70 are
  STP-only.
- In livepack-classfix-v2, 4 of 85 keys violate only off-capture.
- The K panel's violations are all off-capture: drawn region K stays clean.

### Policy sensitivity (world-v4 pack)

| R2 policy | Violating keys | Pinhole cells | Drawn pinhole cells | Visible-transparency px | Keys with visible transparency |
|---|---:|---:|---:|---:|---:|
| s/4 Euclidean | 742 | 319,768 | 22,525 | 2,157,667 | 378 |
| **s/2 Euclidean (v2 default)** | **677** | **128,133** | **10,309** | **1,583,169** | **241** |
| s/2 Chebyshev | 676 | 126,165 | 10,297 | 1,562,215 | 241 |
| s Euclidean | 596 | 62,008 | 6,829 | 920,686 | 179 |
| connectivity only (no R2) | 595 | 58,376 | 6,514 | 880,538 | 179 |

What the table shows:
- **The metric is irrelevant:** Euclidean vs Chebyshev changes the result by about 1.5%.
- **There is a policy-independent core:** about 595 keys, 58k pinhole cells, 6.5k of them drawn, and 0.88M visible px.
  These are wrong-centre cells and islands, flagged under any bound.
- **The half-to-one-texel band is a policy choice:** about 66k pinhole cells, 3.5k of them drawn, and 0.66M visible px.
  These are defects only under the s/2 policy.

### Where the visible transparency is

40 (group, page) entries have visible-transparency pixels; the six largest hold about 99% of the pixels.

| Page | Source | Visible-transparency px | Kind |
|---|---|---:|---|
| **82831823** "RISE" sign, 33 palette keys | legacy-ui "fresh typography typography-composed-v4"; one key `t4-signs/rise-dim-v1` | 1,415,381 (about 89% of the pack) | holes 643k, added 800k |
| B43C181F | `w6-native-gaps/fd81c3c7-upload-strips-v1` | 53,031 | almost all added |
| 8E1A509D results footer | `w2-hud/results-footer-8E1A509D-v5` / `-v6` | 47,014 | holes; plus 12,441 visible-blend px |
| 95A3BCF8-397FBE8A | `w2-polish/atlas-95A3BCF8-w2-v2` and the identical livepack-classfix-v2 file | 24,149 | added |
| B24C6DA2 HUD | legacy-ui parent and `w3-mk3-hulls-v1` | 20,746 | holes |
| 323B5FB0 title menu | `t9-title-menus/title-menu-323B5FB0-v5` | 6,447 | holes |

The remaining pages are under about 4.3k px each: fd18-sinbal, the results score header, fd15-arabic-hex, the HUD label
fonts, fireball, the Astraea canopy, greif, uhu, electric arc, kaplo and font strips.

**RISE class-fix candidate.** `w6-native-gaps/rise-82831823-classfix-v1` changes only texel-centre pixels. Its own
`known_limits` says this leaves one-pixel pinholes, so it is not a whole-cell fix for the largest visible source.

### Review sheets: `reviews-breakdown/20261114T103414Z/`
Index sha256 `59e100cf…099e`; 14 sheets, all hash-verified.
- **Layout:** left is the HD replacement over a checkerboard; right shows violations as red (hole), cyan (added) and
  yellow (STP). Texels not drawn in the captures are dimmed.
- **`pack-82831823-06BDD2F5.png`:**
  - The HD lettering silhouette does not follow the native one.
  - Red holes sit above and between the letters, where the native texture draws opaque.
  - Cyan opaque pixels run along the lettering's bottom edges and the arrow, where the native texture is cutout.
- **`pack-8E1A509D-8808F70A.png`:** the SQUARE logo box is cutout in HD where the native texture draws it opaque; the ©
  differs only in STP.
- **`pack-323B5FB0-1C7962B3.png`:** thin holes along the left edges of the GAME START glyph strokes. The capture logged
  only one triangle of that quad.
- `reviews-breakdown/20261114T103320Z` is **flawed**: a file-name clash overwrote three pack sheets with livepack sheets.
  See `FLAWED.txt` there; it is kept as produced.

### Registration-shift audit: `runs-shift/20261114T103545Z`
Result sha256 `b7f4673a…c972`.
- **Method:** for each page, the best whole-pixel HD shift within ±1.5 native texels is the one minimising the
  silhouette mismatch on drawn texels. Mismatch is computed for every shift with FFT correlation, which agrees with a
  direct count at zero shift on all 40 pages.
- **Result: no page is a clean registration offset.**
  - The best shift is zero on 28 of the 40 page entries.
  - RISE: 1.06 texels up, mismatch only 7% lower.
  - Title menu: 0.56 texel up, 6% lower.
  - 95A3BCF8-397FBE8A: 1.5 texels left, 6% lower.
  - Results footer and B43C181F: about 38% lower, but at the edge of the search window, likely driven by solid blocks
    such as the logo box.
- **Conclusion:** the visible mismatches are **shape changes in the authored art**, not misregistration. A global
  re-registration would not fix them.

## What this means for the remaster
1. Before any whole-cell work, **choose the R2 policy**: s/2 or connectivity only.
   - The core of about 595 keys and 0.88M visible px is flagged under any bound.
   - The extra 0.66M visible px exists only under s/2.
2. **RISE (82831823) dominates what players can see.** Its HD lettering is a different silhouette from the native sign:
   holes in native-opaque areas and opaque pixels in native-cutout areas. There are three options:
   - re-author it to the native silhouette, within the chosen tolerance;
   - apply the v2 whole-cell repair, which keeps visible RGB but snaps the silhouette (review before accepting);
   - knowingly accept the authored silhouette as an exception to the native-alpha rule.

   Centre stamps (rise-82831823-classfix-v1) do not fix it.
3. **Next by size:**
   - fd81c3c7 strips (B43C181F);
   - results footer 8E1A509D, including its SQUARE logo box;
   - 95A3BCF8-397FBE8A;
   - B24C6DA2 HUD;
   - title menu 323B5FB0.

   Each is small and reviewable.
4. **Lower priority:**
   - STP-only differences on opaque draws affect only the mask bit, so they matter only if the game mask-tests later
     draws.
   - Violations not drawn in these captures need wider capture coverage before anyone acts on them.
5. **Nothing here is composed or live-tested.** The repair candidates in `repairs-v2/` are private.

## Files (sha256)

| File | sha256 |
|---|---|
| `proto-v2b/class_mip.c` | `c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d` |
| `proto-v2b/class_mip.h` | `90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3` |
| `proto-v2b/test_class_mip.c` | `77068c229dbda3710f34d7fb0c3dfc2a4a829e5d83f637cb4a35237cf09bf746` |
| `run_class_mip_v2b.py` | `b51e0377426e60a152d5afe199d91e002d0399e6aa3b8d1ba411cdc6f77068cd` |
| `runs-v2b/20261114T100659Z/result.json` | `3906737df52c087b927227fb40c8bbbddda79f5ac72f6b4dab5dfd6a8f638e66` |
| `breakdown_v2.py` (superseded run) | `1f538d26d2f035170c9548ee596979c1ed418e61cf584370dc1326b98b3a368d` |
| `breakdown_v2b.py` | `0d92089115e53d19699d8c49429b4498dd2319b030d31c25922ac8e613f321b7` |
| `review_breakdown.py` | `ca205dbc67ce0774f29846459cc2880759ec140ea9ca14f4158f09f568805416` |
| `shift_audit.py` | `47e1bedb59c19d9cf3b5b738a43e53ff7e8144e2cf70e65e262e9df063aec9a3` |
