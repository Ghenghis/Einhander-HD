# Keys D5B575F1-8B7DD252 / F33119C6-8B7DD252: source proof and draw mapping (claude-einhander-support, 2026-11-14 ~17:25Z)

- Task: EIN-SUPPORT-POD-SOURCE-20261114, assigned in msg_517c066f.
- Scope: source and log reading only. Two tiny decode PNGs were written. There was no CPU job, no GPU, no game, and no
  candidate art.
- Input map: S23 actor map 5efc089b. Both keys sit in its "player/pods/HUD globals (common 0/14, 0/11)" family, on page
  (896,256): drawn 1, complete_live_source 1, authored 0.

## 1. Native source: complete and CRC-bound
Native dir: `windows-x64/tools/research-runs/research-20261112-155355-aefc8556/native/`.

| key | words.bin | clut.bin | valid.bin | source.json |
|---|---|---|---|---|
| D5B575F1-8B7DD252 | 178930ea… (CRC32 = D5B575F1) | a16ded5a… (CRC32 = 8B7DD252) | 6caf38d5…, all 512 known | 34cdf1c2… (upload_serial 1874, frame 96886) |
| F33119C6-8B7DD252 | feb58ecc… (CRC32 = F33119C6) | a16ded5a… (same CLUT) | 6caf38d5…, all 512 known | 5dab1055… (upload_serial 1873, frame 96880) |

- The canonical `validate_acquisition.check_source` (b5952fae) reports 0 problems for both keys.
- Shape: 64 words x 8 rows, depth 0 (4bpp), so 256x8 texels.
- CLUT (304,485): a 14-step white-to-black ramp, FFFF … 8001 (STP bit set), plus two 0000 entries (transparent).
- Origin: raw_origin surviving_cpu_vram_fragments; both carry gpu_dirty 1.
- The two words files differ in 777 of 1024 bytes.

## 2. Where they live and what is drawn (from the capture's draw rows)
Upload origin, from the runtime formula (hd_texture_pack.cpp:1548-1561 / 1630-1642):
`(page_x + u_first/4 - source_word_x, page_y + v_first - source_y)`.

| key | upload rect in VRAM | draws, run aefc8556 | draws, run 11eebc24 |
|---|---|---|---|
| F33119C6 | (896,416) 64x8, serial 1873 | 6 | 11 |
| D5B575F1 | (896,424) 64x8, serial 1874 | 2 | 5 |

- The two uploads are adjacent 8-row bands. Together they cover VRAM rows 416-431, which are page (896,256) rows v 160-175.
- **Every one of the 24 logged draws** has source_kind `upload`, semi -1, and samples only u 80-83, v 166-168.
- Each draw is a triangle with a screen span of at most 3x2 px.
- Screen positions seen:
  - aefc8556: x 187-198, y 176-179 and y 416-420;
  - 11eebc24: x 5-121, y 169-179 and y 410-412.
- **The drawn texels are uniform:**
  - F33119C6 rows 6-7, u 80-85: palette index 7 (B233) and 8 (A9D0);
  - D5B575F1 row 0: index 8 (A9D0).
  - So each draw is a flat mid-grey 4x2 patch, tinted by vertex colour, inside a 1-3 px sliver.
- The rest of the 256x8 strip is never sampled in either capture: shapes like parts at u 0-79 and 84-255
  (decoded-x4 PNGs: D5B575F1… 4b26f891…, F33119C6… a21bb28b…).

## 3. Identity: NOT proven to be a "pod"
- "player/pods/HUD globals" is S23's page-family grouping (common file 0/14). It is not draw-level identity.
- Neither the source nor the draw rows bind these draws to a gunpod. The observed use is a tiny flat-colour sliver.
- The selector mapping is undetermined:
  - the CLUT is a neutral ramp tinted per draw, so no per-skin palette exists for these keys;
  - linking them to a player-selectable skin or material needs a proven owner object first.
- Per the instruction, I do not assign pod identity.

## 4. Exact missing output and one faithful method
- **Missing:** pack entries for the two upload keys. Each is a 64x8 4bpp upload (256x8 texels) matched as source_kind
  `upload`. A page-level (896,256) replacement would NOT apply to these draws, because the renderer matches the upload key.
- **Faithful method (proposal; not generated):**
  - an exact, class-preserving nearest-neighbour expansion of each 256x8 strip at the pack scale;
  - palette RGB taken from the bound CLUT;
  - index 14/15 (0000) gives a cutout;
  - STP-set entries keep the native STP class (draws are semi -1, so they are opaque here);
  - no invented detail.
- **Expected visible result:** identical to native. The only drawn area is a uniform 4x2 patch in 1-3 px triangles, so
  authored detail cannot show there. Recommendation: record these keys as "native-equivalent; passthrough only if
  coverage policy requires an entry". Do not spend authoring effort on them, and do not use them as skin targets until a
  draw context with real sampled detail is captured.

## Next ready command
None is needed for identity. If main wants coverage entries, generating the two passthrough strips is a light,
single-process, seconds-long job: decode the bound quads and write class-preserving nearest PNGs to
`support/pods/candidates/`. It needs a grant and main's go-ahead. I am not running it now.
