# Capture checklists for Codex: index

Written 2026-11-13 by claude-einhander (lane capture-checklists), at Codex's request for consolidated, exact acquisition checklists in the order S1, S2, S3, S4, S5, S7, with Stage 6 as an appendix. Text only: nothing was launched, nothing outside this folder was changed.

Each stage file stands alone: purpose, prerequisites, a numbered capture list (trigger, what to record, pass criterion), the post-capture steps the lane runs, and open questions. The checklists are **route-agnostic**: they say what to capture and when to recognise the moment, never how to get there. Items whose lane assumed an assisted route, stage select or a state load are marked **needs an authorized route**.

## Order and what each run unblocks

| # | File | Lane | Unblocks | Items | Estimated capture length |
|---|---|---|---|---|---|
| 1 | `S1.md` | W6-DRACHE (Stage 1 boss) | **23 keys** (death-flash CLUTs, the last Drache gap); live A/B of the **11 current candidates / 195 keys**; 1 inferred sprite cell; real GP0 for the eye and side gun | 5 (+ P0, not a capture) | One stock pass to the Drache death: the reference route took about 34,000 frames, about 13 min wall, from Stage 1 start to Stage 2. The Drache recorder window is 11,880 frames (198 s at 60 fps). Plus a second pass with W6 installed for the A/B (S1-5). About 26-30 min of runtime for both passes |
| 2 | `S2.md` | lane-s2 | **39 keys in 7 frozen sets**; 60 unknown palette-phase CLUTs; 119 + 16 live keys without complete sources; full-rate replay data; the ground crawl gate | 5 | Continues from S1's pass: post-Drache sequence to Stage 2 section 3 + 600 frames. Reference: post-Drache to entry 1,227 frames, section 2 569 frames; section 1 on a normal pace is unknown. Estimate 3-6 min of Stage 2 play, plus about 20.5 s for the HD fly-past (S2-5) on a later pass |
| 3 | `S3.md` | lane-s3 | **39 keys in 3 frozen sets** (walls-v1 25, walls-material-v1 the same 25, signage-props-v1 14); real UV cells; 5 competing CLUT positions | 4 | Whole Stage 3 (no live data exists): 15-30 min of runtime by the stage-access plan's per-stage budget, plus two short review passes of the scrolling wall (S3-3) |
| 4 | `S4.md` | lane-s4 | **11 exported keys in 3 frozen sets** + 233 renderable-later keys; the realism-rebuild look inputs; effects v2/v3 choice; the shared panorama `05E1881C` (master not built) | 5 | Whole Stage 4: 15-30 min of runtime |
| 5 | `S5.md` | lane-s5 | **12 rendered keys in 3 frozen sets** + 245 renderable-later + 15 `05E1881C` keys; 3 8bpp Dürer hull regions; the Stage 5 look decision | 6 | Whole Stage 5: 15-30 min of runtime, with about 20 look marks held about 2 s each |
| 6 | `S7.md` | lane-s7 | **26 gate keys in 3 frozen sets** (planet limb 2, backdrop 2, fleet parts 22) and the CLUTs for 5 export-less masters (explosion v1/v2, transmission page v1/v2, hull masters) | 6 | Whole Stage 7 by straight play from Stage 6: 15-30 min of runtime |
| A | `S6-appendix.md` | lane-s6 (still authoring) | **101 keys in 9 current frozen sets** (ledger says "83 + 21"; manifests list 83 + 18); set A/B residency; GP0 part masks; real sprite animation | 5 | Whole Stage 6 (thrusters run done normally, then straight into Stage 7): 15-30 min of runtime |

The 15-30 min figure is the stage-access plan's budget for one later stage on the rank-1 continuous route (`fullgame-prep/stage-access/STAGE-ACCESS.md` section 7), not a measurement. Stages 3-7 have never been reached, so no frame window exists for them.

## Items shared by two lanes (capture once)

| Item | Lanes | Where it is written | Moment |
|---|---|---|---|
| **X-05E1881C** | lane-s4 (owner), lane-s5 | `S4.md` and `S5.md` (identical text) | The cloud panorama at VRAM 960,0, over one full horizontal pan, in whichever stage is captured first: Stage 4 after member 2/22 loads (section b), or the Stage 5 entry (member 3/1). Stage 5 adds a 2 s hold mark (L3) |
| **X-704256** | lane-s7 (CR7-4), lane-s6 (CR-S6-2) | `S7.md` and `S6-appendix.md` | VRAM page 704,256 through Stage 6 and at Stage 7 start, before the boss and after the boss: `10932164` (4/5 large explosion) vs `9E43A5C3` (4/12 transmission page) |
| Second arrival with HD installed | S1-5 (W6 A/B), S2-5 (train/ground fly-past), S3-3 (wall motion) | the three files | A later pass with the reviewed candidates installed can serve all three in one chain, after the stock pass's `confirm` / `gate` (or as a review-only install, if Codex allows it) |

## Suggested pass plan (Codex decides)

1. **Stock chain:** one continuous stock-first session from boot. Run S1 pass A, then S2, S3, S4, S5, S6 and S7 in order, rotating recorder windows per segment. Stop rule as in the stage-access plan: if a stage cannot be cleared, record the frame and the reason.
2. **Lane checks:** each lane runs `validate_predicted.py confirm` and `gate` (commands in each file) on the stock chain.
3. **HD review chain:** a second arrival with the confirmed candidates installed, for S1-5, S2-5 and S3-3.

## Companion key files (`keys/`, one key per line, usable with `validate_predicted.py gate --keys`)

| File | Keys | Use |
|---|---|---|
| `S1-C1-flash-keys.txt` | 23 | S1-1 (optional recorder source filter) |
| `S2-gate-keys.txt` | 39 | S2 `gate` |
| `S2-unknown-phase-keys-60.txt` | 60 | S2-2 phases |
| `S2-addendum-post-drache-119.txt` | 119 | S2-4 |
| `S2-addendum-unexported-tex-16.txt` | 16 | S2-4 |
| `S3-gate-keys.txt` | 39 | S3 `gate` |
| `S4-gate-keys.txt` | 11 | S4 `gate` |
| `S4-confirm-renderable-later.txt` | 233 | S4 confirm report check |
| `S4-palette-hold-keys.txt` | 23 | S4 AQ-05 |
| `S4-05E1881C-keys.txt` | 11 | X-05E1881C (Stage 4, non-zero CLUTs) |
| `S5-gate-keys.txt` | 12 | S5 `gate` |
| `S5-confirm-renderable-later.txt` | 245 | S5 confirm report check |
| `S5-palette-hold-keys.txt` | 44 | S5 AQ-05 |
| `S5-05E1881C-keys.txt` | 14 | X-05E1881C (Stage 5, non-zero CLUTs) |
| `S6-gate-keys.txt` | 101 | S6 `gate` |
| (lane file) `comfy-authoring/w7-stage7/work/gate-keys-stage7.txt` | 26 | S7 `gate`, sha256 `eac777a0f95b282e252489155bac330d4c539487080efce7023cb3c3098cfa0f` |

The files contain keys only (no comments), because `gate` extracts every `XXXXXXXX-XXXXXXXX` pattern from the text.

## Needs an authorized route

- **S1-5:** the lane's research route (Mk.II plus WASP) was assisted with an invincibility-timer hold.
- **S5 (all items):** the lane named AQ-01 / AQ-02 / AQ-03b / AQ-17. AQ-02 (stage select through RAM writes) and AQ-03b (DuckStation save states) cannot feed `stage5-source`; only a continuous recomp run can confirm keys.
- **S3, S4:** the readiness reviews list AQ-17 / AQ-03b as reconnaissance only. The lanes assumed nothing beyond a continuous run.
- **X-704256:** the optional "fresh stage 7 load".
- Every later stage depends on a continuous session from boot (there is no mid-game save); Codex reports any stage it cannot reach.

## Requests that could not be made fully exact

- **S1-1 form (a):** no existing command was found that guarantees a frame-locked read of VRAM row 498 on every frame. `vram_peek` is host-polled. The checklist offers two equivalent forms under the lane's CRC rule: marked events, which can cover at most 13 of the 23 keys, and complete source quads through the stock-first dump or the recorder's source filter.
- **Stages 3-7:** no reference frames exist; triggers are landmarks and section changes only.
- **S2 full rate:** only `repeat_sample_frames 60` has been observed; whether `1` and a raised rate limit are available per window is open.
- **AQ-17** is cited by lanes s3/s4/s5 and the readiness reviews but is defined in none of the files read here.
- **S6 key count:** the manifests give 101 keys (83 + 18), but the ledger text says "83 + 21".
