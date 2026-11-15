# Stage 1 world-layer and sign coverage census (claude-einhander, 2026-11-14)

CPU-only analysis of files already on disk. No game, no GPU, no art changed. **Nothing in this census is live-accepted:**
0 of 1,669 pack keys have `live_verified: true`. "Authored" means a frozen candidate set is composed into the pack, not that
it looks right. Machine-readable rows: `census-v2.json` (from `world_census_v2.py`).

## Inputs
- Pack: `dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/candidate.json` (1,669 keys). The private crisp-v2
  sign overrides are not counted here.
- Legacy provenance: the parent chain down to `title-e-20261112-v13`, plus the stage1-v1 base manifest
  `windows-x64/hd-textures/stage1-v1/manifest.json` (per-key `method`).
- Frozen sets: all 260 `comfy-authoring/*/frozen/*/manifest.json`. A set counts as **deliverable** only when it holds
  `KEY.png` files in its folder or in `runtime*/pack*/page*` subfolders (181 sets). Sets that merely *name* a key in their
  manifest (73) are not counted as deliverable, because some of them list keys they deliberately left unchanged.
- Draw evidence: four retained ein-research-v1 flypast logs (`w3-emissive-on/off-v1`, `world-flypast-v1`,
  `actors-flypast-v4`). These are sampled first-activation captures (60-frame repeat) of Stage 1 only, made with earlier
  packs. They prove that a key was drawn, but they are not a complete scene denominator.
  - `size` is the on-screen native bounding-box height at the 90th percentile: far <24 px, mid 24–80, near >80. It measures
    size, not 3D depth.

## 1. What the 1,669 pack keys are made of
| Treatment | Keys | Meaning |
|---|---:|---|
| authored | 837 | A frozen lane set composed into this pack (t7 279, w2-hud 110, w2-polish 92, w3-hud 77, w2-effects 65, t3 61, w3-astraea 37, t6 35, t4-signs 22, w3-signs 20, t1-sky 11, t9 10, t2 9, w3-mk3 6, w3-canyon 3) |
| legacy-nearest | 487 | 485 from the stage1-v1 base (`nearest 8x` or `nearest 16x`) plus 2 REMASTER_STAGING additions marked `native 8x fallback`. **No new detail by construction** |
| legacy-neural | 251 | 174 base `UltraSharp` (93 "16x reduced to 8x", 81 "two 4x passes"; the historical base manifest had 311 neural) plus 77 REMASTER_STAGING "world source-preserving addition" (local UltraSharp RGB, native classes) |
| legacy-ui | 92 | Title-era HUD, menu, typography, blueprint, results and diagram compositions |
| legacy-other | 2 | The user-approved 4K facade exact regions `52F33418-5E9B9AC3` and `74EF95B7-B30D16F0` |

## 2. What is actually drawn (four Stage 1 flypasts)
- 740 pack keys were queried, and 634 of them had an HD replacement submitted.
- 929 pack keys were never drawn in these logs: 392 authored, 317 nearest, 189 neural, 31 UI. They may belong to other routes,
  stages or states; that is not established.

| Drawn, by treatment | far | mid | near |
|---|---:|---:|---:|
| authored | 273 | 60 | 112 |
| legacy-nearest | 95 | 6 | 69 |
| legacy-neural | 10 | 25 | 27 |
| legacy-ui | 55 | 3 | 3 |
| legacy-other (approved facades) | 0 | 0 | 2 |

### 2a. Drawn with NO pack entry (native fallback): 21 keys
**Every one of these already has a frozen W4 or W6 candidate that was never integrated.**

| Keys | What it is | On screen | Frozen candidate (status `candidate`, not integrated, not live-tested) |
|---|---|---|---|
| E360C964 × 10 (EC3CCAA7, 3392E58F, C12472D4, 9E723485, 7A38FB8F, CE2C1696, F66A97D4, A92B06F1, C1B5906C, C89502BC) | Silo, crate, grille and **scaffold lattice metal**, plus green neon parts: the steel framework behind the world-075 sign cluster | **near** (p90 up to 231 px) and mid | `w6-native-gaps/e360c964-metal-v1` (6 keys); `w4-signs-hud/E360C964-neon-parts-w4-v1` (5 keys) |
| 31214B41 × 2 (67842D27, 3D0EB788) | Dark sign-backing cells | near (166–179 px) | `w4-signs-hud/31214B41-dark-cells-w4-v1` |
| 0223BCEF × 4 | Flash and debris | far | `w4-player/w4-flash-debris-0223BCEF-v1` |
| A40D25FE × 5 | Upload strips | mid | `w6-native-gaps/fd81c3c7-upload-strips-v1` |

### 2b. Drawn legacy keys
- **126 have a deliverable frozen set that is not integrated.** World-other accounts for 107 of them:
  - AB2DB563 canyon sprites: 42 drawn, UltraSharp; `w4-world/AB2DB563-canyon-sprites-v1` delivers 41.
  - A40D25FE and B43C181F upload strips: 55 drawn, nearest 8x, far; `w6-native-gaps/fd81c3c7-upload-strips-v1` delivers 85 keys in all.
  - The rest are 7 effects, 7 signs (including the 4 `73BF9877` cells, below), 3 menus, 1 enemy and 1 canyon key.
- **169 have no authored candidate at all:**
  - **1FD36785 × 64**, near: CPU upload strips whose drawn content is a single flat colour block (wash or beam fill). Nearest
    enlargement of a flat fill loses nothing, so this is *not* a visible detail gap.
  - **1CCA84E3 × 32**, far (3–10 px): small palette-cycled icon and indicator strips. Nearest 16x, layer unconfirmed. A low
    priority for 4K detail, because they are tiny on screen.
  - **82831823 × 32**: the RISE sign lit regions, far, a legacy typography composition. `w6-native-gaps/rise-82831823-classfix-v1`
    only *names* them.
  - HUD 23 and menus 6, legacy UI. Codex owns the HUD and menu delivery investigation.
  - Unknown-layer neural 7, one key each on 7 pages. Player 2 (1 nearest, 1 neural). The 2 approved facade regions are
    drawn too (one counted in buildings-facades, one in unknown); they have no candidate because they are already
    user-approved.

## 3. Layers (heuristic, from lane and set names plus same-page inheritance; not a visual verdict)
| Layer | authored | nearest | neural | ui/other | drawn |
|---|---:|---:|---:|---:|---:|
| buildings-facades | 9 | 7 | 2 | 1 | 10 |
| buildings-lights (t3 green lights, 1FD36785 washes) | 61 | 125 | 0 | 0 | 125 |
| sky-background | 16 | 0 | 1 | 0 | 4 |
| terrain-canyon | 3 | 0 | 3 | 0 | 4 |
| world-other (95A3BCF8 / 22D9BF19 atlases, AB2DB563 sprites, upload strips) | 84 | 71 | 112 | 0 | 188 |
| signs | 43 | 69 | 3 | 32 | 72 |
| effects | 65 | 2 | 5 | 0 | 54 |
| enemies-bosses | 285 | 96 | 73 | 0 | 183 |
| player | 72 | 37 | 5 | 0 | 25 |
| hud | 187 | 6 | 2 | 26 | 24 |
| menus | 10 | 8 | 0 | 34 | 9 |
| unknown (mostly 4096×128 upload strips; 72 of the 114 are drawn 0 times) | 2 | 66 | 45 | 1 | 42 |

**The world totals that bear on "full 4K world coverage":**
- Of the world-layer keys drawn in these flypasts, the 125 buildings-lights keys are 64 nearest and 61 authored (t3). The 64
  nearest ones are the flat-colour 1FD36785 washes.
- Of the 188 drawn world-other keys, 107 are legacy, and every one of those 107 has an existing frozen candidate waiting.
- The scaffold and silo metal around the sign cluster (E360C964) is drawn **native**, at large size.

## 4. The user's distant green/pink "signs": mapped
They are the **95A3BCF8 distant-city window-light atlas**: dot grids of lit windows on far building silhouettes. They are not
lettered signs, so no glyph or wording question arises.

| Capture | Screen region (native) | Key, UV | Palette look | Pack treatment |
|---|---|---|---|---|
| world-090 | x262–320, y58–96 | `95A3BCF8-723E222C` uv [128,64,192,111] | teal stack | w2-polish `atlas-95A3BCF8-w2-v2` 2048, authored, soft and grainy |
| world-075, upper right | x252–320, y30–62 | `95A3BCF8-60245B3A` uv [176,112,239,144] | green dot grid | same set, 2048 |
| (same atlas region, other palette) | drawn in the lower rect | `95A3BCF8-07A9568D` uv [176,112,239,174] | **pink, orange and white windows**: the distant "pink" | same set, 2048 |

- The page also carries **62 further palette keys inherited at 4096 from the REMASTER_STAGING UltraSharp addition**. 20 of
  the page's 85 keys are drawn in these logs.
- Evidence: UV crops of the current pack (`green-upper-world075-uv.png`), overlap of draw-log bounding boxes with the screen
  rectangles (`green-upper-world075.json`, `green-lower-world075.json`, `teal-panel-world090.json`) and visual layout match.
- Limit: the screenshots come from the sign-crisp-v2-live-r1 run and the draw logs from older flypasts, so this is not an
  atomic draw-to-pixel proof.
- What is needed for a real 4K improvement: author crisp, class-exact window-light dots for the atlas region
  [128..239] × [64..174] across all of the page's drawn palettes. That is new authoring, and it is the most direct answer to the
  user's distant green/pink defect.

## 5. Signs: reconciled with Codex's register count (`docs/media/gallery/sign-census-progress-results.json`)
- The W3 INDEX has 37 rows. **25 boards carry 43 phase keys**, and each phase key's art lives in its **exact-region key**:
  - all 43 exact-region keys are in the pack, authored: 21 t4-signs, 20 w3-signs and 2 w2-polish (board 18);
  - 33 of the 43 are drawn in these logs.
- The full-page `FD81C3C7-*` register keys are legacy nearest pages and are not drawn as pages. They are not a sign gap; do not
  count them.
- Boards 14, 19, 22 and 23 have no phase keys in W3 (posters and unmapped rows). The W4 ledger and MISSING-SIGN-PHASES
  supersede the 5 historical request rows, as Codex said; nothing here is double-counted.
- **Correction to the "known unfinished texture cells":** `w5-cleanup/frozen/73BF9877-cells-w5-v1` already delivers all four
  (`803A474F`, `CA7DE0E0`, `7AA4A0DF`, `3FA85320`) as class-validated candidates. They are **unintegrated and not live-tested**,
  not unauthored.
- **Competing candidates for boards 4 and 10:**
  - `w5-cleanup/board04-glyph-column-w5-v1` and `board10-red-banner-w5-v1` (smoothing) are drop-ins for the same region keys
    as my crisp-v2 `7A652858-600290FE` and `67DC56D7-8D0C6ABE` (EPX ×4).
  - Both sets are unintegrated, so the user picks per board in one A/B.
- Live-accepted sign boards: **0 established.**

## 6. Unknowns, stated explicitly
- No full Stage 1 scene denominator exists. The four flypasts are sampled and Stage 1 only. Keys that are drawn only on other
  routes, at other times or in other stages are invisible here.
- Layer is a heuristic for 114 "unknown" keys (mostly 4096×128 upload strips, 72 of them drawn 0 times) and a name or page
  inference elsewhere.
- Not-integrated sets are counted by existence. Their quality, mutual supersession and live behaviour are **not** judged here.
- 354 authored keys also have a newer frozen set (ordered by frozen time). Which version is intended is a lane decision.
- The "far/mid/near" split is screen size, not depth.

## 7. Most effective next steps (proposed, all reversible)
1. **Integration candidate (CPU, private):** compose the existing W4, W5 and W6 deliverable sets that target drawn
   legacy or absent keys onto `frozen-w3-lit-v1`:
   - E360C964 metal and neon, 31214B41 dark cells, 0223BCEF debris, the fd81c3c7 upload strips, AB2DB563 canyon sprites and
     the 73BF9877 cells;
   - verify native admission with `verify_native.exe`, write READY, and leave it for one live A/B.
   This removes all 21 native-fallback draws and upgrades 126 drawn legacy keys, using art that already exists.
2. **New authoring:** the 95A3BCF8 distant-city window atlas (the user's green and pink defect), class-exact, 4096.
3. Keep the cap-2048 pack strictly as a private performance comparison, not a quality substitute, as Codex directed.
