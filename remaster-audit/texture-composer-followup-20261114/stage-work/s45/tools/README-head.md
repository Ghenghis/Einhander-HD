# s45: Einhander Stages 4-5 worker outputs (`claude-einhander-s45`)

Native Claude Code session "Einhander Stages 4-5":
- desktop session `local_23875684-e1a4-4e97-971e-d9abd3f77f52`;
- CLI session `3cf72e9f-f6a6-4f00-9cf2-66f68dea820d`;
- worktree `C:/github/Einhander/.claude/worktrees/einhander-stages-4-5-f992fe`.

Tasks EIN-S4-WHOLE-CELL-20261114 and EIN-S5-WHOLE-CELL-20261114 were claimed at 13:30Z and picked from the durable queue
at 13:35Z. The recovery checkpoint is `.hermes3d_orchestrator/continuity/claude-einhander-s45.json`.

Rules this folder follows:
- **CPU only.** The 3090 Ti is user-reserved, and every heavy job runs only on an individual grant from `codex-einhander`.
- **Read-only inputs.** Frozen lanes, static exports, runtime source and failed evidence are never edited.
- **Not acceptance.** Nothing here is installed, integrated or accepted. Every key is predicted-static.

## Results so far (newest last)

1. **Source map** `source-map/20261114T133831Z/source-map.json`: 0 issues.
   - S4 has 11/11 unique selected keys (effects v2/v3 are alternatives) and S5 has 12/12. Both equal the checklist gate
     lists.
   - Renderable-later: 233 / 245. Palette-hold: 23 / 44, plus the all-zero `190A55AD` keys.
   - Words and CLUT CRCs are proven, and the manifests match lane-readiness.
2. **Panorama 05E1881C** `PANORAMA-05E1881C-OWNERSHIP.md`: NOT BUILT.
   - The words are byte-identical in both stages. The doc proposes a single owner (s45) and one master, and gives the
     exact capture request.
   - The S5 "ramp" CLUTs are 16-word slices of the 8bpp CLUT rows 509-511.
3. **Duerer 8bpp** `DUERER-8BPP-PLAN.md`.
   - Runtime key rule: CRC32 of 128 columns x 256 rows, read from `hd_native_page.h`.
   - The exact static depth-1 keys decompose into the Duerer 4bpp half-pages.
   - The doc separates assumptions from proofs, refines the S5-5 capture requirements, and gives the authoring plan.
4. **J-A, the S4 strict whole-cell audit** `strict-audit/20261114T135014Z-s4/result.json`:
   - 26/26 files pass strict and primary checks, R5 = 0, and every PNG sha256 equals the manifest.
   - Limit: all review CLUTs are opaque. 8/11 keys are single-class, and no key has a cutout texel.
5. **CLUT class coverage** `clut-coverage/20261114T135254Z/coverage.json`:
   - 186 static candidate keys on the 23 selected pages create cutout texels; every review CLUT has none.
   - 5 pages have a more-paired candidate CLUT than their review CLUT.
   - Run `20261114T135223Z` is superseded (bugs); it is kept as failed evidence.
6. **Repair proposals** `REPAIR-PROPOSALS.md`: three isolated repair jobs (R-A, R-B, R-C) and the merged tool copy
   `tools/w7m`. The byte-identity checks V1/V2 must pass before any repair build.

7. **J-B, the S5 strict audit** `strict-audit/20261114T140010Z-s5`, 24 files:
   - 22/24 pass at s/2. `BFC445B0-A132B3B3` fails R2 inside the FX flame box: 386 px / 61 cells at 2048, 89 / 47 at 1024.
   - R1 = R3 = R4 = R5 = 0.
   - Correction: the "primary" columns of the J-A and J-B runs used the s/2 flags, so both folders carry a
     `CORRECTION.txt`.
   - **J-AB2 (corrected)**, runs `strict-audit/20261114T141041Z-s5` (PID 19004) and `20261114T141046Z-s4` (PID 32752):
     - primary (R1 + connectivity-only at bound 1e9) passes for S4 26/26 and S5 24/24;
     - the s/2 diagnostic (bound 0.5) passes for S4 26/26 and S5 22/24. The two S5 failures are the BFC445B0 R2 cases.
     - R5 = 0 everywhere, but no cutout texels exist under the review CLUTs.
8. **Backlog** `BACKLOG-S45.md`, with sources `backlog/` and `page-reuse/`:
   - Beyond the 23 selected keys, the 4bpp content pages left to author are 23 for S4 (750 keys) and 11 for S5 (246).
   - Runtime-composed or raw pages that need capture: 7 for S4 and 22 for S5.
   - 8bpp / 15bpp fallbacks: 17 for S4 and 19 for S5, mostly 1-2 static keys each.
   - Common-member textures are mostly also predicted for Stage 1.
   - `011FFCA6` is an all-zero cleared page shared by S4 and S5, so it needs no art.
9. **Page reuse** `page-reuse/20261114T140003Z/reuse.json`: the best word overlap is S4 2/22 `9B8107D2` vs the authored
   `E8769E55`, at 72% of texels.
10. **w7m2, R-D, R-E and R-F:**
    - `w7m2` adds the class-aware FX blend (`fx_region` docstring/code mismatch found).
    - R-D is a `cm_repair` copy tool for BFC445B0; R-E is Duerer v3 with class-aware FX.
    - R-B now uses class-aware FX.
    - R-F is a DRAFT job for the unauthored member 3/17 pages 768/832/896.

11. **J-D, the S4 transparency probes** `probe-audit/20261114T141200Z-s4` (PID 32752, 73 s):
    - The run is partial: 12 of 13 probes. The skipped probe is effects v3 `AFCCB3B5-70EEEA84` (time budget).
    - The 24 files are audit-only renders, from the frozen masters, of each page's most-cutout candidate CLUT.
    - R1 = R2 = R3 = R4 = 0, with the s/2 flags and connectivity-only both 0: strict and primary pass 24/24.
    - R5 fringe is > 0 on all 24 (median 2.9% of cutout px). Cutout px are raw black, so the pack composer needs an R5
      fill (class-mip renderer proposal, step 1).

12. **J-E, the S5 transparency probes** `probe-audit/20261114T141451Z-s5` (PID 33016, 63 s), complete with 12 probes and
    24 files:
    - primary passes 20/24 and s/2 passes 16/24. Every failure is inside a lane-s5 FX-contract box.
    - Primary FAIL: `1A2ACF78-0DA351E7`, the smoke page, under its 134-pair transparent candidate CLUT. At 2048:
      conn 83 / R4 8 / R3 75 / R2 8098.
    - Primary FAIL: `3D108041-BE3400E6`, shock rings and debris. At 2048: conn 220 / R4 1 / R3 219 / R2 9846.
    - s/2-only fails: `BFC445B0-066C0B81` and `1168CC84-A345AE9E`.
    - The fix is `w7m2` `fx_region(class_aware=True)` in R-A and R-E, re-audited on these exact probe keys.
    - R5 fill is the composer's job (root decision, msg_80aa44e1). s45 ships no filled copies.

13. **Keyed capture and admission checklist** `checklist/20261114T143022Z/CHECKLIST-S45.json` and `.md`:
    - Per key it gives the page, depth, CLUT xy, PAL, phase, s45 audit and probe status, competing CLUTs and missing
      evidence.
    - Stage 4: 11 gate keys, 12 panorama keys, 34 phase holds, 25 unauthored pages.
    - Stage 5: 12 gate keys, 15 panorama keys, 52 phase holds, 19 unauthored pages, and 15 Duerer 8bpp items (12
      candidate keys and 3 sub-images).
    - Run `20261114T142955Z` is superseded because it labelled CLUT row 509 as runtime-written.

14. **J-F, the option-2 class snap** `repairs/J-F-20261114T143602Z.json` (runner PID 32968 on CPU 13, 8.0 s, all exit
    codes 0):
    - It repaired copies of the 4 failing J-E probe keys; all 8 files then pass both policies.
    - Visible RGB is unchanged (proof field and independent diff).
    - A launch earlier at 14:33:52Z stalled on Git Bash quoting and ran nothing. Its empty `repairs/J-F.log` is kept.

## Pending on CPU grants, in order

J-D2 (the skipped S4 probe: `--stage 4 --sets s4-effects-2-13-v3 --pages AFCCB3B5`), J-C (8bpp static ranking), V1 / V2 (w7m
equivalence) and V3 (w7m2 with class_aware off), R-D (cm_repair copy), R-A / R-B / R-C / R-E repair builds, R-F (after
S5-5).

## Blocked on the live capture (Codex)

- the S4 / S5 stock-first runs: key / CLUT confirmation for 23 selected keys, 478 renderable-later keys and 25 panorama
  keys;
- the 05E1881C pan, CLUT dump and stills;
- the S5-5 8bpp Duerer draws;
- S4-4 sprite sizes and the S5-4 disk phases;
- the look decisions (user).

## Files (sha256)

