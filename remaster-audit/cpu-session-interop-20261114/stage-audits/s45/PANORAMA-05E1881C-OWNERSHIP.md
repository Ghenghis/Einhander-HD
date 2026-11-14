# 05E1881C shared panorama: ownership reconciliation (Stage 4 / Stage 5)

Written 2026-11-14 ~13:45Z by `claude-einhander-s45` (tasks EIN-S4-WHOLE-CELL-20261114, EIN-S5-WHOLE-CELL-20261114).
Evidence: `source-map/20261114T133831Z/source-map.json` (sha256 `14bf34419adf0c3129b52fc5dd06a4c9aec4add68dcf96fc8ec022ab2645d0cd`),
lane STATUS `comfy-authoring/w7-stage4/work/panorama-05E1881C/STATUS.json` (sha256 `3cee20f1...e2f`, unchanged).
Text and static metadata only. Nothing was rendered, built or edited.

## Status: NOT BUILT

- No file named `*05E1881C*` exists under any `w7-stage4/frozen` or `w7-stage5/frozen` folder. There is no master, no render and no
  frozen deliverable. The only artefacts are `work/panorama-05E1881C/STATUS.json` and `reference-native-cluts.png`, which is a
  reference render and not a delivery.
- A reference is not a delivery. `s5-world-3-1-v1` and `-v2` list the page under `shared_pages_referenced_not_built`, which is
  correct. Neither stage's candidate key count includes it: S4 has 11 selected keys and S5 has 12, with 0 panorama keys.

## Source facts (re-proven 13:38Z)

| | Stage 4 | Stage 5 |
|---|---|---|
| words | `stages/stage4/textures/05E1881C.words.bin` | `stages/stage5/textures/05E1881C.words.bin` |
| sha256 | `e0d184fd...4d413` | `e0d184fd...4d413` (byte-identical) |
| CRC32 = TEX | proven | proven |
| writer member | 2/22 (section b reload) | 3/1 (stage entry; 3/6 and 3/13 also write 960,0) |
| static keys | 12 (11 non-zero + all-zero `190A55AD`) | 15 (14 non-zero + `190A55AD`) |
| equal to STATUS.json and checklist key files | yes | yes |

## Ownership decision (proposed; recorded here, not in any frozen file)

- **One master, two stages.** Both stages use the same words, so the HD master is shared: one index master at 960,0.
  It is rendered once per *captured* CLUT, into 2048 and 1024 exports.
- **Owner: `claude-einhander-s45`** (Stage 4/5 worker). This replaces the historical "lane-s4" owner: those lanes were
  sub-agents of the original `claude-einhander` and are not active models. The s45 session holds both stages, so there is
  no split ownership any more.
- **Build source: the Stage 5 export (member 3/1).** It is the stage-entry member and is drawn on every route; the words
  are identical either way.
- **Output location when built:** `remaster-audit/parallel-stages-20261114/s45/panorama-05E1881C/<rev>/`. These are new
  files only. `w7-stage4/work/panorama-05E1881C/` stays read-only.
- **Key accounting:** each drawn `05E1881C-<PAL>` key counts once, under the stage whose capture confirms it. A key that
  both stages draw (same TEX and same PAL) is one HD file. Different PALs are separate keys. No CLUT is shared between the
  two static lists, so today the expected key sets are disjoint: S4 11 and S5 14.

## What blocks the build (unchanged; exact capture request)

1. `source_draw_query_matched` rows for every `05E1881C-*` key over one full horizontal pan, at full rate
   (`repeat_sample_frames 1`): key, frame, uv_bounds, xy. These give the drawn region and the u wrap period. All 256
   columns differ, so the period cannot be read from the page.
2. The CLUT words actually drawn, from a stock-first dump of the candidate positions while the panorama is on screen.
   - S4: 96,484 112,484 96,494 192,494.
   - S5: 16,495 32,489 0,511 160,511 **plus 0,509 0,510**. Both are needed because of the finding below.
3. One 4K still per section with the panorama visible.

## New evidence that changes how the ramp test is read

- Several Stage 5 "ramp" candidates are exact 16-word slices of the 256-entry 8bpp CLUT rows that the Duerer 8bpp keys use
  (rows 509-511 of the 3/1 CLUT upload `0,504,256,8`). The sky pairing therefore cannot be inferred from ramp shape.
  The slices are:
  - `361A4661` at 0,511 is words 0-15 of `D5C392C5` (row 511);
  - `0ADAA698` repeats at x = 96, 112, 128, 160, 192 and 208 of row 511;
  - `264276C9` at 0,510 is words 0-15 of `1EDE052B` (row 510);
  - `3091E9CA` at 0,509 is words 0-15 of `0B616D37` (row 509).
- A 256-colour palette is usually sorted, so its first 16 words look like a luminance ramp whether or not a 4bpp draw ever
  uses them. Only a drawn `clut_xy` settles the pairing.

## Build plan once the capture lands (CPU; one slot)

1. Run `validate_predicted.py confirm` on both stages for the `05E1881C` keys. Each drawn key needs a complete source.
2. Build the t1-sky method master: a continuous index 0..15 at 16x, periodic procedural billow detail on the de-posterised
   guide, low frequencies locked to native, and periodic in u with the captured wrap period. The template is
   `t1-sky/frozen/night-cloud-sky-page640-v1`.
3. Render only through the captured CLUTs. Rows 0-34 are one flat index (the sky band) and must stay flat with no added
   detail. The cloud rows are 35-247.
4. Run the strict whole-cell audit (`tools/s45_strict_audit.py`) and freeze under s45. Hand integration to `codex-einhander`.
