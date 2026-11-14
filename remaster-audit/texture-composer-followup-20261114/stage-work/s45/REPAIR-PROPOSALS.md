# Stage 4 / Stage 5: documented defects and isolated, native-faithful repair proposals

Written 2026-11-14 ~13:57Z by `claude-einhander-s45` (tasks EIN-S4-WHOLE-CELL-20261114, EIN-S5-WHOLE-CELL-20261114).
Sources: the selected frozen manifests' `honest_read` / `known_limits`, lane STATE.md files, and the s45 measurements listed
in `README.md`. **Nothing here is built yet.** Every build needs an individual CPU grant from `codex-einhander`. The outputs
go only to `s45/repairs/<name>/`, and the frozen originals stay untouched. Every repair keeps the predicted-static rule:
import only after the live run confirms the key and CLUT (`validate_predicted.py confirm` + `gate`).

## Tooling: merged W7 copy `tools/w7m` (write-once; generator `tools/make_w7m.py`)

- **Why.** The two lane tool copies diverged.
  - lane-s4 (`w7-stage4/tools`) has the 1-texel line strokes, the glow-break weight, the smooth energy gate and
    `label_rects`.
  - lane-s5 (`w7-stage5/tools`) has the FX-contract boxes, the 8bpp pass-through, the glyph de-stair, the material
    exclude boxes and `shared_pages`.
  - No single copy can build a Stage 5 page with strokes, or a whole-page FX contract with the smooth gate.
- **How it was built.**
  - The base is lane-s5 (w7lib `99896867`, build `e4f70557`).
  - The lane-s4 functions are ported **verbatim**, with anchors checked to match exactly once (w7lib `e628962e`,
    build `f1e0ca39`).
  - One s45 opt-in key is added: `seed_name`, the material/turbulence seed, which defaults to `job['name']`. A repair can
    then keep the seeds of the revision it repairs.
  - Inputs and outputs are recorded in `tools/w7m/MERGE-RECORD.json`: w7lib `80de86c8...`, build `d3e09d2e...`.
  - `tools/w7m-r0-unused/` is the first generation without `seed_name`. It was never used and is kept.
- **Not yet proven:** that the merge builds byte-identically. That is checked by V1 and V2 below, each on one page with
  `tools/s45_w7m_verify.py`. No repair build may run before both pass.
  - **V1:** `w7-stage4/work/jobs/s4-world-2-13-v3.json`, page `1DE4AA74` (strokes on) vs frozen `s4-world-2-13-v3`. That set
    was built by the current lane-s4 tools, so it is a valid reference.
  - **V2:** `w7-stage5/work/jobs/s5-world-3-1-v2.json`, page `1A2ACF78` (FX boxes and exclude boxes) vs frozen
    `s5-world-3-1-v2` (current lane-s5 tools).

## Proposals (job specs in `repairs/jobs/`, sha256 in README)

### J-E finding (14:15Z): the FX contract fails whole-cell under transparent CLUTs (`probe-audit/20261114T141451Z-s5`)

- **Primary failures** (R1 + connectivity-only), both inside lane-s5 FX boxes:
  - `1A2ACF78-0DA351E7`, smoke box [0,128,256,192]: conn 83 px, R4 8 islands, R3 75, R2 8098 at 2048.
  - `3D108041-BE3400E6`, ring and debris boxes: conn 220 px, R4 1, R3 219, R2 9846 at 2048.
- **s/2-only failures:** `BFC445B0-066C0B81` (flame box) and `1168CC84-A345AE9E` (crater box).
- **Everything else passes.** Every non-FX region and every 3/6 effects probe pass both policies. Every S4 probe passes.
- **Consequence.** Every repair that rebuilds an FX box must use `w7m2` with `fx_region.class_aware = true`. That is R-A
  (1A2ACF78 smoke), R-B and R-E. A repair counts as done only when these exact probe keys pass both policies again:
  `tools/s45_probe_audit.py --set-dir <repair build> --keys ...`.

### FX class-ownership plan: two options, measured (14:20Z)

The build passes every non-zero candidate CLUT of the page to `fx_region`, so `class_aware=True` keeps only the index pairs
whose class matches under all of them. For the FX boxes, the blendable pairs out of 120 are:

| page | candidate CLUTs | blendable pairs |
|---|---|---|
| 1A2ACF78 | 17 | 22 |
| BFC445B0 | 10 | 49 |
| 3D108041 | 18 | 20 |
| 1168CC84 | 29 | **2** |
| 5C04E373 | 19 | 32 |
| BD968A3C | 10 | 49 |

- **Option 1: `class_aware`** (R-A, R-B, R-E as written).
  - Whole-cell safety holds by construction for every CLUT.
  - **Price:** the fades mostly stop blending. On 1168CC84 the crater dither returns as dots, near the v1 "leopard" look.
- **Option 2 (recommended for FX pages): keep any-pair blending and class-snap each rendered key.**
  - Keep the soft any-pair master (v2 look). After `export_rgba`, run the frozen proto-v2b `cm_repair` on each key's export.
    R1/R2/R4 violators take their cell's native class.
  - **Proof field:** `visible_rgb_changed = 0`.
  - This is class-mip renderer proposal step 2 ("whole-cell repair only where proven necessary"). Only *drawn* keys need it,
    so it runs on the live-confirmed keys after capture, with `tools/s45_cm_repair.py` generalised to any rendered key.
  - Masters are not rebuilt and the look is unchanged. Each repaired key is re-audited under both policies.
- **Decision.** Choose per page after review. Option 2 keeps the approved soft FX look. Option 1 is the fallback if a
  reviewer prefers crisp FX.
- **Option 2 demonstrated (J-F, 14:35:54-14:36:02Z, CPU 13, runner PID 32968, record `repairs/J-F-20261114T143602Z.json`).**
  `cm_repair` was run on copies of the four failing J-E probe exports. All 8 files end with R1 = 0, centre mismatches 0,
  connectivity-only = 0 and s/2 = 0. On every file, `visible_rgb_changed = 0` and the independent diff of pixels visible
  both before and after is 0.
  - `1A2ACF78-0DA351E7`: 2048 went from conn 83 / R4 8 / R3 75 / R2 8098 to 0 (2 passes).
  - `3D108041-BE3400E6`: conn 220 / R3 219 / R2 9846 to 0.
  - `BFC445B0-066C0B81`: s/2 127 to 0.
  - `1168CC84-A345AE9E`: s/2 423 to 0.
  - **Limits.** `cm_repair` also fills cutout RGB (R5) on invisible pixels. Pixels that became visible take cell or native
    colours, so the FX fades still owe a look review. These are probe copies of unconfirmed keys, not deliverables.

### R-A `s5-world-3-1-v3-s45`: bead chains on the Stage 5 world pages

- **Defect** (from the v2 `honest_read`): 1-texel frames of alternating tones become bead chains at 16x, for example the
  452F3CC3 window frame and the 503474BD rail. This is the same defect Stage 4 world v3 fixed.
- **Change:**
  - `soft.strokes = true`. The lane-s4 world v3 stroke rule rebuilds continuous strokes along the line, and the tones
    change exactly at the native texel boundaries.
  - Since J-E (14:17Z), also `fx_region.class_aware = true` for the 1A2ACF78 smoke boxes, built with `tools/w7m2`.
  - `seed_name = s5-world-3-1-v2`, so the material is unchanged.
  - The FX box positions, exclude boxes and swatches are unchanged.
- **Risk.** The stroke detector skips checkerboard and noisy rows. A strictly alternating 2-tone frame may count as
  checker-like and be skipped. The build record's `soft_stats.strokes` counts the runs that were found; if 452F3CC3 or
  503474BD gets 0 runs on the frame rows, the repair does not apply and we report that.
- **Checks after the build:**
  - strict whole-cell audit (`s45_strict_audit.py`) on the new exports;
  - motion SIMULATION (`twinkle_sim.py`, region set `world`) vs v2;
  - `focus_compare` crops of the frame and rail.
- **Alternative kept:** v2 (frozen).

### R-B `s5-effects-3-6-v2-s45`: banding and speckle on the 3/6 spinning-disk effects

- **Defect** (from the v1 `honest_read`): the non-ramp review CLUTs disable the glow field. Radial gradients then band into
  octagonal tone plateaus, the fire-ring speckle stays as rounded dots, and the scalar 32-texel energy gate can leave
  straight steps at the cell borders.
- **Change:**
  - an FX-contract box over each whole page, `fx_boxes [[0,0,256,256]]`. This is the Duerer v2 method: any-pair tone
    blending, no cores, and centres not forced in the master. Exports still stamp the native classes;
  - `energy_smooth = true` (the lane-s4 smooth gain field);
  - `seed_name = s5-effects-3-6-v1`.
- **Caveat.** v1 was built with the older lane-s5 w7lib `af3c2ec9`, so a v2-vs-v1 diff is not only these two options.
- **Expected price:** softer sprites and lower local contrast, as Duerer v2 FX had (debris bursts -40%, rings -18%).
  Both v1 (crisp) and v2 (soft) stay as alternatives; the choice waits for the S5-4 disk capture (on-screen size and
  every CLUT phase).
- **Checks:**
  - strict audit;
  - energy record (every cell within ±6% and no step);
  - twinkle SIMULATION vs v1;
  - render of a transparency-bearing candidate CLUT (probe).
- **Blocking caveat (J-B, 14:00Z).** The same FX-contract blending fails the s/2 whole-cell diagnostic on Duerer v2
  `BFC445B0` at STP/opaque borders (see R-D). The 3/6 page `BD968A3C` has 27.6% STP texels under its review CLUT, so R-B as
  written would most likely add R2 violations there. **Resolved in the job spec (14:06Z).** R-B now sets
  `fx_region.class_aware = true` and builds with `tools/w7m2`.

### Tool `tools/w7m2` (= w7m + one opt-in patch; generator `make_w7m2.py`, record `MERGE-RECORD2.json`)

- **What it fixes.** The lane-s5 `fx_region` docstring says blending stays inside the "same class under every renderable
  static CLUT", but the code sets `N = np.ones((16,16))`, so any index pair may blend. That is the cause of the BFC445B0
  R2 drift.
- **The patch.** `fx_region(class_aware=True)` builds
  `N[i,j] = class(P_k[i]) == class(P_k[j])` for every candidate CLUT k.
- **Defaults.** The default `False` is meant to keep w7m's exports and masters byte-identical. The fx region records gain
  a `near_pairs` field.
- **Proof still needed.** That needs a V check on an FX page: rebuild `s5-world-3-1-v2` page 1A2ACF78 with w7m2 and
  `class_aware` off, and compare the exports and masters.

### R-E `s5-duerer-armour-v3-s45`: the method-level fix for BFC445B0 (alternative to R-D)

- **Change:** Duerer v2 job + `fx_region.class_aware = true` only.
  - `seed_name = s5-duerer-armour-v2`, so material, swatches, 8bpp pass-through and glyph de-stair are unchanged.
- **Expected price.** FX fades blend only inside same-class tone groups, so STP/opaque borders stay crisp. Some dot texture
  may come back at those borders, so twinkle must be re-simulated against v2.
- **Choice.** R-D is the minimal post-export class snap on one key. R-E is the method fix and applies to every renderable
  CLUT of the page. Both stay alternatives until review.

### R-C `s4-enemies-2-13-v3-s45`: scratch strokes and mottle on the Stage 4 enemies

- **Defect** (from the v2 `honest_read`):
  - the `gunmetal_worn` swatch leaves small dark diagonal scratch strokes on flat fillers (C7C81B36, 0FD152CA);
  - light flats read as stained-paper mottle.
  - Lane-s4 STATE next steps 3 and 4 already proposed this change.
- **Change:**
  - swatch `gunmetal_worn` removed: `navy_armour` 1.0 instead of `navy_armour` 0.5 + `gunmetal_worn` 0.5. No new swatch
    is introduced, so no GPU work is needed. `s4_wet_painted_steel` is the calmest Stage 4 swatch (detail std 0.031), but
    it was rejected because it carries vertical run-off streaks, a directional cue that is unproven for rotating enemy
    sprites;
  - `soft.strokes = true`, for the rivet rows and 1-texel trims;
  - `seed_name = s4-enemies-2-13-v2`.
- **Caveat.** v2 was built by the older lane-s4 w7lib `97b6818e`.
- **Checks:** strict audit, `focus_compare` of the flat fillers, and a motion SIMULATION.

### R-D `cmrepair-BFC445B0-A132B3B3`: whole-cell class repair copy (tool `tools/s45_cm_repair.py`)

- **Defect** (J-B, `strict-audit/20261114T140010Z-s5`): every violation is R2 (s/2 displacement), and every one is inside
  FX box #0 `[192,0,256,128]`, the flame sprites.
  - At 2048: 386 px in 61 pinhole cells. At 1024: 89 px in 47 cells.
  - R1 = R3 = R4 = R5 = 0.
  - The class pair is STP (255) vs opaque (127) only.
  - The lane's centre check passes, because the centres are stamped.
- **Change:**
  - copy both frozen exports, after re-checking their sha256;
  - run the frozen proto-v2b `cm_repair`: violators take their cell's native class, iterated until clean;
  - native classes come from the CRC-proven words and CLUT.
- **Proof fields:**
  - `visible_rgb_changed = 0`, plus an independent pixel diff: the RGB changed on pixels visible both before and after must
    be 0;
  - after the repair: R1 = 0, the s/2 flags = 0 and the connectivity-only flags = 0.
- **Severity.** It depends on the draw's `semi`:
  - semi-transparent draws: the STP bit selects the blended pixels, so a displaced edge is visible;
  - opaque draws: only the mask bit changes.
  - S5-5 must record `semi` for these draws.
- **Status:** prepared; it needs a CPU grant. The output is a candidate copy for review and stays predicted-static, not
  installable.

### Deferred (not proposed for building yet)

- **S4 world v4 (5536C111 run-off):** dropping the wet run-off swatch on 5536C111 needs its identity first. It looks like
  red unit parts, not plating, and the S4-2 draw rows decide that. Diagonal 1-texel strokes need new code, which is not a
  port.
- **Duerer FX regions:** both looks are kept, crisp dots (v1) and soft glow (v2). The choice waits for the S5-5 capture
  (size and motion).
- **S4 effects v2 vs v3 (B305DC32 mines):** this waits for S4-4, the on-screen sprite size.

## Whole-cell audit status (facts, not acceptance)

| Item | Result | Limit |
|---|---|---|
| J-A S4 strict audit, 26 files (`strict-audit/20261114T135014Z-s4`) | 26/26 at s/2 (R1..R4 = 0); R5 0; sha256 == manifest | all review CLUTs are opaque: 8/11 keys are single-class, and none has cutout texels. Its "primary" column used the s/2 flags (see `CORRECTION.txt`); every S4 count is 0, so both policies pass |
| J-B S5 strict audit, 24 files (`strict-audit/20261114T140010Z-s5`) | 22/24 at s/2; `BFC445B0-A132B3B3` 2048 and 1024 fail R2 inside the FX flame box; R1 = R4 = 0 | its "primary" column is the s/2 flags (`CORRECTION.txt`); connectivity-only is measured by the J-AB2 rerun |
| CLUT class coverage (`clut-coverage/20261114T135254Z`) | 186 candidate keys across the 23 pages create cutout texels | static candidates; not rendered yet |
| J-AB2 (both stages, corrected policy), J-D / J-E transparency probes | **pending CPU grants** | probes are audit-only renders from the frozen masters |
