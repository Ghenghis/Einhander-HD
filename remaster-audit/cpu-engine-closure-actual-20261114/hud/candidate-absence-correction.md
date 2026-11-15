# Coverage-gap map: the four "no candidate" HUD keys (source-only, 2026-11-14 ~23:55Z)

Read-only. Methods: grep, sha256 and JSON reads of existing records. No image was decoded and nothing was run.

## Correction
The S45 state register (`parallel-stages-20261114/s45/menu-hud/state-register/20261114T154752Z/REGISTER.md`, lines 25-39) and my own COVERAGE-MENU-HUD.md (lines 27-28 and 49) said these keys had **no candidate at all**. That is wrong: an earlier HUD-restoration lane already authored candidates for all four.

| key | role (S45 register / e2e-coverage) | restored region (native texels) | authored candidate (coherent-v4) | copies of that exact file found in packs |
|---|---|---|---|---|
| 44C16454-72FBA1C5 | HUD small numeral strip (ammo popup candidate), source 256x8 | whole strip | `hud-restoration/candidate-20261112-coherent-v4/pack/einhander-texture-replacements/44C16454-72FBA1C5.png` sha256 f9d459b45d3a6ae1… | 55 |
| 8BA3BB4D-190A55AD | Hit Gauge numeral/multiplier/HIT rect on a mixed 256x256 page | only [0,64,64,96) | same folder, 9511a22f75360eab… | 62 |
| 8BA3BB4D-36D62A31 | same | only [0,64,64,96) | 4255b3e5102cb78b… | 54 |
| 8BA3BB4D-E0AE221F | same | only [0,64,64,96) | c82058bfb3a14257… | 54 |

Sources for these facts:
- the copy counts: sha256 over 253 matching pack PNGs under remaster-audit (this session);
- the roles and regions: `hud-restoration/e2e-coverage.json`;
- the v4 status: `candidate-20261112-coherent-v4/build-verification.json`.

## Status of that candidate (from its own records, not re-verified)
- `geometry_version` coherent-glyph-rim-v4; 34 source keys; 68 output hashes verified; 0 hash failures.
- `python -m unittest test_hud_ui_candidate`: 12 tests, exit 0 (as recorded).
- The visual review removed detached tonal blobs from the numerals. "Runtime acceptance remains pending."
- **`in_game_acceptance`: "pending root isolated runtime trial". `production_installed`: false.**
- History: coherent-v3 was REJECTED (a solid-glyph profile had filled outlined word interiors); v4 is the stated correction.
- The lane's e2e-coverage overall_status is `incomplete_remaining_legacy_assets_and_unverified_journeys`.

## What is actually missing (the real gap)
1. **Class audit under the current policy is UNKNOWN.** I have no record that these four v4 PNGs were checked under the current R1 / connectivity policy (frozen class_mip c84efa60) inside their restored regions. That is the region-scoped check my lane ran on the menu art.
2. **Live acceptance: none.** No composed in-game check of the Hit Gauge or ammo strip with these files exists. Today's 37c startup aborted before the menu (main msg_aec42fab).
3. **Pack propagation risk.** The same v4 bytes sit in about 55 other packs, including w3-lit world packs (pages shared with the player hull). Any defect found in step 1 would affect all of them. Which pack is the installed one remains UNKNOWN to me.
4. The 12 other 8BA3BB4D variants are "region-covered" by B2473AF8 (w4 hud-lives-glyphs) according to the S45 register. That overlap with v4 is also unaudited here.

## Proposed next step (needs review and, later, a CPU grant; not now, during the game quiet period)
- One **read-only region-scoped class audit** of exactly these 4 v4 PNGs against their native words/CLUT:
  - for 8BA3BB4D, R1 / connectivity counts inside [0,64,64,96) only;
  - for 44C16454, the whole 256x8 strip.
  - The protected rest of each mixed page is reported but not judged.
- Measure only. No art is written. The tool would be a new revision, sharing the r6 / C1 decode, with fixed pins for the 4 files above plus their stock words/CLUT.
- If it passes, the remaining blocker is live acceptance (coordinator game run). If it fails, any repair is a separate, reviewed one-key-at-a-time job like C1.

No admission, readability or composed claim is made by this map.
