# Stage 1 distant green/pink neon and far-building audit (metadata only)

**Requested by:** root msg_eb25e105. **Owner:** claude-einhander-s67.
**Method:** JSON/text metadata and sha256 only. No PNG decode, no run, no GPU, no live capture. A read-only subagent gathered the evidence. **[V]** marks claims I re-checked directly, against the staging receipt `2710782e`, the candidate `261dc3d2`, the class-mip result `c7dd79d6`, and file hashes.

**Status words:**
- **ACCEPTED-LOOK**: a recorded visual acceptance exists.
- **CLASS-ONLY**: only strict, class or whole-cell checks passed.
- **UNVERIFIED**: nothing beyond pack membership.
- **FAILED**: a recorded failure exists.

**Headline: no key below has a recorded look acceptance (ACCEPTED-LOOK).** Pack membership is not coverage.

## What the distant green/pink lights are
The world-sign census maps the user's distant green/pink "signs" to the **95A3BCF8 distant-city window-light atlas**: dot grids of lit windows, not lettering. Sources: WORLD-SIGN-CENSUS.md §4 lines ~92–110 and STAGE1-COMPLETION-STATUS.md line ~105.

Limit: the screenshot and draw-log runs differ, so there is no atomic draw-to-pixel proof. Regions come from `comfy-authoring/t3-green-lights/regions.json` (`52aa9d25…`). Draw counts come from `t3-green-lights/draw-census.json` (`a698ca0f…`, 77 logs).

## 95A3BCF8 atlas (far; high confidence where a region is drawn)
| key | region / role | draws | staged sha **[V] where marked** | source | status |
|---|---|---|---|---|---|
| 60245B3A | O, green dot grid | 714 | `6b8aa13e2590d14b…` [V] | claude-backlog `95a3-o-city/…/O-city-v1` page2048 | CLASS-ONLY: the manifest says "simulation only, not seen live" and `live_verified` is false |
| 07A9568D | O, pink/orange/white windows | 510 | `52b92c145f051c01…` [V] | O-city-v1 | CLASS-ONLY |
| 723E222C | K, teal panel | 64 | `f17632027bbbd232…` [V] | the candidate row names K-panel-v1 page2048 (`791c01a8…`) but carries `f17632…`, origin "unchanged immutable parent" [V]; `f17632` is the `world-integrated-crisp-v4` page [V] | **FAILED** whole-cell [V] |
| E01F52F8, 0361652D | I, lit window grid | 324 / 178 | `621bd1d6…` / `f2966718…` | `95A3BCF8-I-windows-v1` | CLASS-ONLY |
| 33BC1036, 8C6DBF6D | J, office windows | 216 / 72 | `07d9329a…` / `1547f221…` | J-windows-v1; aliases most | CLASS-ONLY |
| 29595B58, 0D0D6AE1 | M, lower window grid | 221 / 104 | `48bdb1ef…` / `3b58987f…` | M-windows-v1 | CLASS-ONLY |
| 397FBE8A, 79B18A47 | P antenna / Q tank | 54 / 4 | `761391e2…` / `211321a8…` | P/Q cutouts | CLASS-ONLY |
| D60B38CC, 540CAA98, 615C942A, 857DB48E, D9527F27, 8A79B9D5, 0DA946C5, 97445449 | F, D, C, U, T, X/Y, L (pipes, window rows, cage, bands, flare, panes, lamp) | 5–255 | e.g. 97445449 `87bca44c…` [V] | w2-polish `atlas-95A3BCF8-w2-v2` | **FAILED** whole-cell (subagent counts, 3.5k–12k bad cells) |
| E005E658, 520515BB, C1CC2C79, 9C70FEB6 | T / A / B / G | 23–362 | `23047bb9…` etc. | w2-v2 | CLASS-ONLY; the census calls this set "soft and grainy" |
| 61 E palettes (e.g. 2EC339B9) | E, blinking lamp/dish, tiny | ~150–320 each | e.g. `3115e8d0…` | no manifest; 4096 parent chain | UNVERIFIED |
| 22D9BF19 + the same 61 | exact region for E | — | e.g. 22D9BF19-2EC339B9 `1d6d1123…` [V] | t3/w2 E-region crops | **FAILED**: all 61 are whole-cell violations (subagent) |

**[V] correction to the subagent's top repair.** In class-mip `runs-f6-v2/20261114T095517Z/result.json` (`c7dd79d6…`), three K-panel pages give an **identical** WHOLE-CELL VIOLATION (r2 displaced 82,158 px, r3 uniform-bad 35,294 px):
- the staged `f17632…`;
- the **authored** K-panel-v1 page2048 `791c01a8…`;
- livepack-classfix-v2 `8d4c7aee…`, whose counts differ slightly.

These counts cover the whole 2048² atlas page (65,536 cells), so they are dominated by regions outside K. **Staging the authored `791c01a8` page alone would not clear the failure.** It does fix the provenance mismatch.

## Other far keys
- **CD7769E8 / 8FCDBD4A-D22835C2**, skyline panorama: staged `01acbe75…` / `96fcd997…`, from `t1-sky/…/skyline-panorama…-v1` (SDXL). CLASS-ONLY. Self-reported limit: mid-city "neon blobs stay blobby".
- **B4C7A0EB-FBBC76C7 / -0E9B8DA4**, distant light band and towers: `25cd4c33…` / `5b3936f6…`, procedural. Class-mip did not check FBBC76C7, so it is UNVERIFIED. The band is about 38% darker than stock. **B4C7A0EB-190A55AD:** no manifest, UNVERIFIED.
- **41827AD3 (61)**: a red beacon, not green or pink. CLASS-ONLY for the regions; 60 of the 61 full pages have no authored source, so UNVERIFIED.
- **1CCA84E3 (33)**: far palette-cycled strips, legacy nearest-neighbour 16x, no authored candidate. UNVERIFIED.
- **Lettered boards (FD81C3C7 layout, crisp-v2 EPX×4)**: CLASS-ONLY.
  - `sign-crisp-v2-live-results` records `visual_acceptance: false`, and STATUS line ~113 marks the green/pink overrides unaccepted.
  - 7A652858-600290FE has 1 whole-cell bad cell.
  - The W3 variants 0FB1EFC5-8A2A52C4 and 327E6D9E-5039A9C5 are FAILED: soft and pale, per SIGN-QUALITY lines ~111–134.
  - Their distance is not established. This is lettering, not the "neon" lights.
- **E360C964 (11)**: green neon parts, near or mid. **52F33418 / 74EF95B7 (H24 facades)**: near. The census "user-approved" claim conflicts with H24-IN-GAME-RESULTS `live_visual_accepted: false`, so neither is ACCEPTED-LOOK.

## Drawn but not staged
- **95A3BCF8-7589E98F** (region F): drawn 4 times and ABSENT from the 1701 pins [V]. There is no source CLUT, so it cannot be rendered until a live capture exists.
- Regions H, N, R, S, V and W were never seen drawn.

## Next concrete repairs, in priority order (none started; art and CPU work needs owner and grant)
1. **The O region (the green/pink dot grid itself)** is already authored (O-city-v1) but has never been seen live. Do a same-route live capture of 60245B3A and 07A9568D to separate shimmer/aliasing (the manifest warns that crisp frames shimmer without mips; t3 alias is 5.6–8.7%) from residual grain, before any new authoring.
2. **The whole-cell failures on the 95A3BCF8 page** need a class-exact rebuild of regions C, D, F, L, T, U and X/Y, plus the 61 E-region exact regions. Most of these regions have no authored source beyond the failing w2/t3 forms.
3. **K-panel provenance:** reconcile the composer row (it names `791c01a8`, carries `f17632`). Then judge K on a per-region audit, because the page-level verdict is the same for both shas.
4. **95A3BCF8-7589E98F:** live CLUT capture, then authoring.
5. **Skyline panorama blobby neon:** there is no crisper source, so this needs new authoring.

## Not determined
- Which keys the live P1/raw37c run actually drew.
- Whether the E-region exact regions override the 4096 full pages at runtime.
- How the K sha mismatch arose.
- The board distances.
- O-city draw counts under the raw37c-r6 staging.

## Sources (sha256 prefix)
- raw37c-staging.json `2710782e` [V]
- candidate.json `261dc3d2` [V]
- class-mip runs-f6-v2 result `c7dd79d6` [V]
- K-panel page2048 `791c01a8` [V]
- regions.json `52aa9d25`
- draw-census.json `a698ca0f`
- t3 atlas manifest `7267062a`
- ExactRegions.tsv `292adcbe`
- WORLD-SIGN-CENSUS.md `bd21ab53`
- STAGE1-COMPLETION-STATUS.md `cc9249f5`
- STAGE1-SIGN-QUALITY-20261114.md `fd69776c`
- H24-IN-GAME-RESULTS.md `c598320f`
- ROI-NATIVE-ADMISSION-20261114.md `f472ccbf`
- class-mip breakdown result `f7169d3e`
- execution-state.json `5814552b`
