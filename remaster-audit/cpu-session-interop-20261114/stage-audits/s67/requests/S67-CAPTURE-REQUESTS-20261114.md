# s67 capture and source requests: Stages 6-7 (2026-11-14)

Owner `claude-einhander-s67`. Tasks `EIN-S6-WHOLE-CELL-20261114`, `EIN-S7-WHOLE-CELL-20261114`. These requests go to `codex-einhander`, who owns live capture. They refine the lane requests CR-S6-1..5 and CR7-1..5 and the published checklists `runtime-diagnostics-v58/capture-checklists/S6-appendix.md` and `S7.md`. Nothing here was captured, and none of it is a stage or key acceptance. Every Stage 6 and Stage 7 key is still predicted-static.

Evidence used (all in `remaster-audit/parallel-stages-20261114/s67/`):

| file | sha256 |
|---|---|
| `stage6/selection-map-20261114T133638Z.json` | `3d0961e7f734a173b0dd161ceb7951776024a5f727cebb5dcad882bda0312eb7` |
| `stage6/part-regions-20261114T134420Z.json` | `b78b3bee5571680f90fcb4d6d6b7b79f7eeff063366f44c5c480f04dbf76ac94` |
| `stage7/selection-map-20261114T133927Z.json` | `1069a9044ec05bfd35faae8882c1ff3f7df14e1bc5de87c64d76225f86266da2` |
| `runs/20261114T134056Z-dry/result.json` | `9d57c65fbff1393dbeb6bda43e90bfcf02de561f94d3664a27102dcd57118d69` |

`stage6/part-regions-20261114T134358Z-INVALID-union-rule.json` is kept as a failed run. Its union visibility rule made every texel visible, because some selected CLUTs have no zero entry. Do not use it.

## A. Stage 6, main run (AQ-03 continuous chain): one run answers S6-A1..A4

### S6-A1: import gate for the 101 selected keys (CR-S6-1)

- **Keys:** `keys/S6-gate-keys.txt` (sha256 `81421b98...8483f`, 101 keys). It equals the s67 selection: 83 batch 2 + 18 batch 1, 87 new keys + 14 replacement versions.
- **Four keys are shared with Stage 1:** `10932164-0386F43A`, `-5F4DE3D3`, `-66175427`, `-AF93AEF2`. Their files are Stage 1 frozen files reused byte for byte. Their CLUT words come from `w2-effects/frozen/large-explosion-10932164-v2/source` and are CRC-proven. A Stage 1 confirmation of these keys does NOT confirm the Stage 6 draw. They need Stage 6 draw rows.
- **Record:** draw rows (`key`, `frame`, `uv_bounds`, `xy`, `clut_xy`, `semi`, `depth`) for the 12 TEX, plus the stock-first `stage6-source` dump.
- **Pass:** a complete source for each drawn key, and `semi` for each drawn key. Undrawn keys are reported as undrawn, not as failures.

### S6-A2: GP0 textured polygons for hull part masks (CR-S6-3), now sized

**Finding (static, s67 part-regions):** native texels cannot separate hull parts. The selected CLUTs with a transparent entry leave each page mostly as one welded component:

| TEX (page) | keys | visible texels | largest component | share | other components >= 12 texels |
|---|---|---|---|---|---|
| `CB07BBCB` (448,256) | 6 | 43,358 | 43,350, whole page | 100.0 % | 0 |
| `E0849F81` (704,0 B) | 7 | 59,758 | 59,721, whole page | 99.9 % | 1 |
| `43C26C42` (320,0 A) | 10 | 51,007 | 48,758, whole page | 95.6 % | 16 |
| `F07625EE` (384,0 B) | 16 | 46,108 | 42,552, whole page | 92.3 % | 15 |
| `8F498326` (384,0 A) | 7 | 50,760 | 46,710, whole page | 92.0 % | 7 (2 inside the fx-v2 plume rect) |
| `03F5CF11` (448,0 A) | 7 | 43,795 | 39,696, whole page | 90.6 % | 21 |
| `A5969BC9` (448,0 B) | 14 | 48,171 | 39,069, v0-191 | 81.1 % | 29 |
| `20961255` (704,0 A) | 3 | 36,869 | 26,379, whole page | 71.5 % | 6 (plumes inside rect 145,0-243,255) |
| `61A869E5` (320,0 B) | 19 | 41,611 | 19,254, v0-119, plus 12,744, v120-255 | 46.3 % + 30.6 % | 31 |

So a part mask must come from the drawn polygons' UVs, not from texel connectivity. The failed texture-space grain pilot (`failed/stage6-camo-craft-CB07BBCB-v2-grain-pilot`) shows what happens without part masks.

- **Record:** for each of the nine TEX above, at least **60 consecutive untruncated GP0 frames** while that page is drawn. Use the per-frame ring dump (`gpu_frame_dump` as in `record_gp0_burst.py`), pulled before the frames leave the ring.
  - Per textured primitive (GP0 0x24-0x27, 0x2C-0x2F, 0x34-0x37, 0x3C-0x3F, and textured rectangles 0x64-0x7F): the command word, every vertex `xy`, every vertex `uv`, the CLUT word, and the tpage word (page x/y, semi mode bits, depth bits). Keep primitive order within the frame.
  - For set A and set B pages, one window each in a segment where that set is resident (see S6-A3).
- **Pass:** for each TEX, the union of drawn polygon UVs covers every texel that a draw row's `uv_bounds` reaches. No frame is truncated. The draw order is preserved.
- **What s67 does with it:** rasterise each distinct UV polygon into a per-part texel mask on the 256x256 page, and assign welded-sheet texels to parts. These masks feed the hull material pass. They do not change any frozen class plane.

### S6-A3: set A/B residency per segment, and the 704,256 page (CR-S6-2, shared with CR7-4)

- **Record:** VRAM uploads (rect, frame and CRC, or the TEX half of the next draw row) for pages 320,0 / 384,0 / 448,0 / 704,0 / 704,256, with `seg:6:<id>` marks at each change of `0x80081382`.
- **Pass:** a resident TEX per segment per page. For 704,256: `10932164` (4/5 large explosion), `9E43A5C3` (4/12 Hyperion message page), or something else.

### S6-A4: real quad sizes and cell order (CR-S6-4)

- **Keys:** `D552405C` (320,256; v4 is preferred, v1 is the retained fallback) and `E653AA46` (384,256).
- **Record:** full-rate draw rows (`repeat_sample_frames 1`) over at least one complete animation cycle: `xy` extents per draw, the `uv_bounds` sequence, `clut_xy`, the CLUT CRC per frame, and `semi`.
- **Why:** the D552405C v4 and fx-v2 motion verdicts are a SIMULATION. It assumes 40 native px quads, page-order animation and a fixed palette. The v4 "thin bright filaments (~3 px at 2048)" shimmer risk can only be judged at the real quad size.

## B. Stage 6 timeout leg: SEPARATE run (AQ-13), not part of the AQ-03 gate

**Do not merge this with A.** A timeout run ends the game: no clear, no tally, maybe no boss. The acquisition gates T and X fail by design (readiness M6-13). Run it as its own second continuous chain from Stage 1, or as a separate run in the same campaign, after AQ-08.

### S6-B1: timeout-outcome end states (readiness M6-11)

- **Record:**
  - the frame when the mission timer expires;
  - MOV03 placement (frames, and the screen before and after);
  - the narration passage index (the argument to `0x80048138`; candidate passage 2 at SYS.EXE 0x4B0F4);
  - the resident 704,256 page, with draw rows;
  - the GAME OVER still, with a 2880x2160 still;
  - the following screen;
  - draw rows for any key drawn after expiry.
- **Candidate TEX** (content-identified only):
  - `7AD161DF` (4/22 at 704,256). Medium confidence. Its static TEX is `runtime-composed-needs-capture`, because a 4/21 raw upload overlaps it.
  - `DD1C423A` + `0823895F`: the 16bpp sepia still in 4/21. Low confidence. Read it from `stages-v3/ending` only, never from the v2 raw words (finding F1).
- **Pass:** the passage index, and a complete source for every drawn key, including whether `7AD161DF` and the still are drawn at all.
- **Tooling prerequisite (M6-13):** the acquisition validator needs a branch-leg profile in which end states are the result instead of clear and tally. Without it, the run cannot be validated. The owner of `acquisition/` must add this before the run.
- **Scope:** no s67 Stage 6 candidate key belongs only to the timeout leg (`readiness.json` `families.timeout_ending_only.stage_member_keys` is empty). This run unlocks ending art only. It does not unlock the 101 keys.

## C. Stage 7 (continues from the A run through MOV04)

### S7-C1: planet limb drawn CLUT and the inferred pairing (CR7-1)

- **`C4FDEDD2-EAD968A1` is INFERRED and UNCONFIRMED.**
  - `stages-v4/stage7/keys.json` (563 keys) lists no key for `C4FDEDD2`.
  - The CLUT slot 0,504 is listed for 6 keys, among them `89EA4685-6E066984`, which is a different CLUT at the same slot. The slot is rewritten, so sharing it with `4C783149` is weak evidence.
- **Admission rule (accepted by coordinator msg_aa12f9cefaaf6e1b):** a complete live source for exactly `C4FDEDD2-EAD968A1`, AND a draw row with page_xy 832,0 and clut_xy [0,504]. If the page is drawn with another CLUT, re-render from the frozen `C4FDEDD2` master. Do not ship the inferred export.
- **Tooling gap:** `validate_predicted.py` `confirm`/`gate` puts an unlisted key of a known TEX into `tex_confirmed`, which is on the import allowlist. `gate` passes it on a complete live source alone. It never checks `clut_xy` or draw rows. Until that is reviewed, the planet admission needs a separate draw-row check (main owns this code; it is queued for review).
- **Record:** draws on 768,0 / 832,0 / 448,256 (`4C783149`, `C4FDEDD2`, `9B2F0BFD`): `clut_xy`, `uv_bounds`, `xy`, `semi`, and the live CLUT words at the first visible frame, mid-segment, and on every frame where the CLUT changes (fades).

### S7-C2: the five export-less master folders (CR7-2 / CR7-3 / CR7-5)

These folders have masters and no keyed runtime export: `stage7-explosion-966EEDF1-v1`/`-v2`, `stage7-hull-index-masters-v1` (`7622FFA1`, `E8241ECC`, `636344D8`), and `stage7-transmission-page-3F4CA363-v1`/`-v2`. `9B2F0BFD`, in `stage7-planet-limb-v1`, is also master-only: its only listed key is the zero slot `-190A55AD`. Each needs the drawn CLUT words before any export:

| TEX | listed key(s) | blocker | request |
|---|---|---|---|
| `966EEDF1` (640,0) | `-190A55AD` (zero slot 64,511, written at runtime) | drawn CLUT per frame cell, and whether cell 192,192-256,256 is drawn | CR7-2 |
| `3F4CA363` (704,0) | `-190A55AD` (zero slot 240,511) | runtime CLUT at fade-in, full and fade-out; which text lines the US build draws | CR7-3 |
| `7622FFA1`, `E8241ECC`, `636344D8` | 17 / 21 / 17 listed 4/18 CLUTs | which CLUTs are drawn, per segment (hull identity) | CR7-5 |
| `9B2F0BFD` (448,256) | `-190A55AD` (zero slot 288,508) | drawn CLUT | CR7-1 |

### S7-C3: the 14 dense-kanji fallbacks (CR7-3)

- `3F4CA363` v2 keeps 14 dense kanji components on the v1 label master. Their native boxes are in the s67 S7 map and in `manifest.text.dense_v1_fallback`; the threshold is 4 native separators. They stay explicit fallbacks: they are not HD-crisp and are not claimed fixed.
- CR7-3 decides whether this matters. If the US build draws only English, they are unused. If the Japanese lines are drawn, they need a separator-aware stroke model.
- **Record:** `uv_bounds` of every 704,0 draw during the message (no Select), and of the time card, v228-255.

### S7-C4: whole-cell risk from forced centres (no capture needed)

- `30BB2999-418C69D6` records 75 (2048) and 124 (1024) forced texel centres, with 0 class mismatches. The strict whole-cell audit (s67 J-S67, waiting for a CPU grant) will say whether those pins leave R2/R4 violations.

## D. Not requested (already answered or out of scope)

- Stage 6 key count: 101 = 83 + 18 (the ledger text's "83 + 21" is wrong). It equals both copies of `S6-gate-keys.txt`.
- The 23 selected keys in `stage6-vram384-0-8F498326-F07625EE-v1` and `stage6-vram704-0-20961255-E0849F81-v1`: the coordinator recorded them in a new readiness addendum. The original `lane-readiness-20261114T131712Z.json` is kept unchanged.
- No GPU, game, ComfyUI or AudioSR work is requested by s67 while the user's 3090 Ti hold stands.
