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

### R-A `s5-world-3-1-v3-s45`: bead chains on the Stage 5 world pages

- **Defect** (from the v2 `honest_read`): 1-texel frames of alternating tones become bead chains at 16x, for example the
  452F3CC3 window frame and the 503474BD rail. This is the same defect Stage 4 world v3 fixed.
- **Change:** `soft.strokes = true` only. The lane-s4 world v3 stroke rule rebuilds continuous strokes along the line, and
  the tones change exactly at the native texel boundaries.
  - `seed_name = s5-world-3-1-v2`, so the material is unchanged.
  - The FX boxes, exclude boxes and swatches are unchanged.
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
| J-A S4 strict audit, 26 files (`strict-audit/20261114T135014Z-s4`) | 26/26 strict and primary; R5 0; sha256 == manifest | all review CLUTs are opaque: 8/11 keys are single-class, and none has cutout texels |
| CLUT class coverage (`clut-coverage/20261114T135254Z`) | 186 candidate keys across the 23 pages create cutout texels | static candidates; not rendered yet |
| J-D / J-E transparency probes (`tools/s45_probe_audit.py`) | **pending a CPU grant** | probes are audit-only renders from the frozen masters |
| J-B S5 strict audit | **pending a CPU grant** | |
