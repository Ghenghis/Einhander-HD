# 95A3BCF8 failed-region repair plan: inputs, provenance and recipes (source only; nothing run)

**Requested by:** root msg_ba5f6cd2. **Owner:** claude-einhander-s67.
**Read-only evidence:** gathered by a subagent within `C:/github/Einhander` only. Nothing in `C:/github/REMASTER_STAGING` was opened, and no PNG was decoded. **[V]** marks what I re-checked directly.
**Related:** builds on audit `4f39c1c3` and erratum r1 `ecf1fb3b`. No frozen art is touched.

## 1. What the existing class results can and cannot say
- Class-mip `runs-f6-v2/20261114T095517Z/result.json` (`c7dd79d6…`) reports **whole-page** counts only (`cells: 65536`).
  - **[V] Proof:** C 857DB48E, D 615C942A and F D60B38CC report **identical** counts (`cells_bad 6766`, `pinhole_cells 2165`, `r1_centre_bad 4601`, `r2_displaced_px 168786`). These are three different regions, so the counts are per page, not per region. U D9527F27 differs (`7927 / 5345 / 2582 / 68884`).
- The breakdown v2b (`runs-breakdown-v2b/20261114T102254Z/result.json`, `43612daa…`) has no cell coordinates, bounding boxes or masks.
  - Its only draw-footprint proxy is `policies["s/2 euclidean (v2 default)"].pinhole_cells_drawn`:
    - C 2 / 2961 drawn texels;
    - D 4 / 3008;
    - F-D60B 4 / 2047;
    - F-540C 0 / 2047;
    - T 1 / 1597;
    - **U 863 / 4032**;
    - K 0 / 2321.
  - L and X/Y have `no draws in captures`.
  - `visible_transparency_cells` is 0 for every 95A3 page key; these are STP-class failures only.
- **Conclusion:** failure inside each named region is **unmeasured** today, except for the E exact regions (§3), which are true region crops.

## 2. K-panel provenance: the mechanism is resolved **[V]**
- **Chain:** t3 `04be083e` → frozen-world v2 `f41a60ff` → frozen-wave2-polish-v1 `4f7989eb` (w2-v2 runtime) → **world-integrated-crisp-v4 `f17632…`** → rise-f32-r1 → o-roi-r1 → mijpq-roi-r1 / v68 / raw37c.
  - At crisp-v4 the row has origin `frozen artwork candidate`, `previous_sha256 4f7989eb`, `pixel_equal_parent_png_reused: false`.
  - The crisp-v4 composition receipt `k-panel-composition-result.json` (`2fa55ecb…`) records `input_png_sha256 791c01a8…` and `composed_png_sha256 f17632…`.
  - Every later stage carries the row forward as `unchanged immutable parent` with parent sha `f17632`.
- **Why the row names `791c01a8` but ships `f17632`:** see `remaster-audit/build_stage1_frozen_candidate.py` `c8c3cca5…`.
  - **L184–185 [V]:** `ledger[row['name']]=dict(row, composed_path=…, origin='unchanged immutable parent', parent=dict(...))`. The whole parent row is copied, so `input.image` is the stale authoring input from crisp-v4.
  - **L263–265 [V]:** at authoring time, if the image is not pixel-equal to the parent, it is re-encoded with Pillow (`image.save(buffer, format='PNG')`). So the shipped bytes (`f17632`, 2,570,730 B) are a re-encode of the input (`791c01a8`, 2,426,692 B).
- **Reading:** this is consistent with f17632 being a pixel-equal re-encode of 791c01a8. Their page-level class counts are identical, but that **is not proof**; pixel equality was not decoded.
- **Proposed reconciliation (no overwrite):** a one-line metadata decode check of pixel equality between 791c01a8 and f17632 under a CPU grant, plus an annotation in a NEW candidate revision noting that `input.image` is the pre-encode source. No parent row, frozen file or pack is edited.

## 3. Per-region inputs (all inside the repo)
**Common to all regions:**
- Shared native page words: `comfy-authoring/w2-polish/frozen/atlas-95A3BCF8-w2-v2/source/95A3BCF8-<pal>.words.bin`, 32,768 B, `29706a63…8658d2` (the same file for every palette).
- `valid.bin`: 16,384 B, `111ce3c2…49e09f`.
- Per-palette CLUT: 32 B.
- For every failed key the staged pin equals w2-v2 `runtime/95A3BCF8-<pal>-2048.png`, and equals the audited sha.

| region | uv | key | census draws | staged = w2-v2 2048 | clut.bin |
|---|---|---|---|---|---|
| C | 64,0–112,64 | 857DB48E | 148 | `59e799b4…` | `2f154549…` |
| D | 112,0–160,64 | 615C942A | 163 | `c99a8eb4…` | `d4166f8d…` |
| F | 192,0–256,32 | D60B38CC / 540CAA98 | 255 / 121 | `f9c8ca42…` / `6c284684…` | `02ad3e13…` / `93c070be…` |
| L | 192,64–224,96 | 97445449 | 5 | `87bca44c…` [V] | `e7048d90…` |
| T | 0,192–64,256 | 8A79B9D5 | 32 | `98aad5b3…` | `b857da62…` |
| U | 64,192–128,256 | D9527F27 | 72 | `19453a25…` | `e0b2d1da…` |
| X/Y | 192,192–256,256 | 0DA946C5 | 14 | `b8b67646…` | `3a458d08…` |

**E exact regions (`22D9BF19-<61 palettes>`):**
- `ExactRegions.tsv` (`292adcbe…`) rows L87–147 have the form `KEY x=744 y=0 w=8 h=32 depth=0 cx=64 cy=490`. That is uv [160,0,192,32] of the page at VRAM (704,0), 4bpp. The format is defined by `build_stage1_frozen_candidate.py` L213.
- HD crop: w2-v2 `runtime/95A3BCF8-<pal>-Eregion-uv160_0_192_32-256.png`. For example 00A1D33C is `5e1ab56d…`, which equals its staged pin.
- Crop sidecars: words `9b21bf88…` (512 B) and clut `9e3e9d56…` (32 B).
- Region-scoped failure, identical for all 61 keys (f6 L7048): `cells 1024, r1 19, r2 163, r3 102, r5 438, cells_bad 30, pinholes 11, scale 8`.
- v2b: `visible_transparency_cells 21`, kinds hole 171 / added 10, `pinhole_cells_drawn 4`, about 830–900 draw events per key.

## 4. Recipes (proposals; each needs its own CPU grant; outputs are new s67 files only)
**R-A. Region-scoped measurement** (this is what makes "fails inside ROI" provable). For each page key and region:
1. Crop the native words for the uv rectangle from the shared page words.
2. Crop the HD pixels from the 2048 page at scale 8: [u·8, v·8, (u+w)·8, (v+h)·8].
3. Build the native class with `s67_strict_audit.native_class(words, ww, hh, clut_words)`.
4. Run `class_mip.cm_validate` and `cm_flags_ex` (0.5 and 1e9) on that crop only, using the same frozen proto-v2b DLL that s67 tools already load (`s67/tools/class_mip.dll`, compile manifest in `s67/tools/manifest.json`).
5. Output a per-region JSON with counts and the bad-cell coordinates relative to the region.

Reads PNG pixels, so it needs a CPU grant. No art is changed.

**R-B. E exact-region class repair: FIRST target `22D9BF19-00A1D33C`.** One recipe serves all 61 keys because the defect is identical.
- **Inputs:** HD crop `5e1ab56d…`, crop words `9b21bf88…`, crop CLUT `9e3e9d56…`.
- **Method:** the proven s67 Stage 6 native-fill pass (`s67/tools/s6_fx_classrepair.py` lineage, `--fill=native`, as used by r2a/r2b, which passed 8/8 and 2/2 strict).
  1. Make a COPY.
  2. Run `cm_repair` with the native class from the crop words and CLUT, using native texel RGB for newly visible pixels.
  3. Undo any RGB change on pixels that become cutout.
  4. Run `cm_validate` (whole-cell strict on the 1024-cell crop).
- **Report:** `became_visible`, `became_cutout`, `stp_toggled`, `visible_rgb_changed`.
- **Needs** a small adapter (`s67_eregion_classrepair_r0.py`, not yet written) that feeds crop inputs instead of an audit-result job. It is then reviewed and run under a grant.
- **Not an acceptance:** a live look still follows.

**R-C. Second target: T `95A3BCF8-8A79B9D5`.** It is drawn, single-palette, has 4096 texels and 1 drawn pinhole, which makes it a low-risk first full-page validation.
- Run R-A first. Then do a region-limited native-fill repair, with every texel outside T byte-identical, and validate both region and page.
- **Not chosen:**
  - L (smaller) has no draws in captures, so it cannot be checked against drawn texels.
  - U is the most visible (863 drawn pinholes) but larger; it goes after T.

## 5. Missing or blocking inputs (exact)
1. **No per-cell or per-region failure data exists** for the page regions. R-A must run first, under a CPU grant.
2. **The w2-v2 recipe has drifted [V]:**
   - `w2-polish/scripts/j_review.py` is now `52b85566…`, but manifest L429 pins `7564fd0c…`;
   - `j_freeze.py` is now `dc62c68d…`, but L430 pins `d7d51b77…`;
   - `j_rebuild.py` still matches (`9906be95…`).

   The frozen w2-v2 build cannot be reproduced from current scripts. Repairs should start from the frozen outputs, not a rebuild.
3. **The class audit's own `source_dir`** for the 95A3 rows points into REMASTER_STAGING, which is out of scope. The in-repo copies match it by hash, so a re-audit must be repointed to the in-repo w2-v2/t3-v1 `source/` files.
4. **95A3BCF8-7589E98F:** no CLUT copy. It is drawn by the game, but authoring and audit are blocked until a live CLUT capture exists. No palette is invented.
5. **O green/pink (60245B3A / 07A9568D):** a matched-route live capture is needed. No grain cause is claimed from metadata.

## 6. Ready next (independent, source only)
Write the R-A measurement script and the R-B adapter as new s67 source files. Both are parse-only until root review and a CPU grant.
