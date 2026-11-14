# Stages 4 and 5: keyed capture and admission checklist (s45, 20261114T143022Z)

Machine-readable: `CHECKLIST-S45.json` (sha256 `88b24b695c5e88e5c037b27116e2ede211f8e42a49bd049feaba671dc7e5829e`). Every key is predicted-static and nothing is confirmed live. Base checklists: `runtime-diagnostics-v58/capture-checklists/S4.md` and `S5.md`; this file adds per-key status and missing evidence.

## Admission sequence

1. capture: continuous recomp run into the stage, stock textures for that stage's keys, stock-first dump
2. validate_predicted.py confirm (key-confirmed = byte-identical words and CLUT) and gate on the gate list
3. drawn CLUT differs from the review CLUT -> re-render that key from the frozen palette-independent master
4. s45 strict audit of every admitted export: primary (R1 + conn-only, cm_flags_ex bound 1e9) must be 0; s/2 (bound 0.5) recorded as diagnostic; FX pages: post-render class snap (cm_repair) or class-aware rebuild if it fails
5. composer: opt-in cutout RGB fill (R5) on the new composition copy (root decision msg_80aa44e1)
6. integration, live A/B, motion and gameplay acceptance by codex-einhander (and the user's look decisions)

## Stage 4

Counts: gate keys 11, panorama keys 12, 8bpp items 0, phase holds 34, unauthored content pages 25.

### A. Gate keys (frozen candidate art)

| key | family | page | CLUT xy | pairs | phase | frozen exports (primary / s/2) | transparency probe | best competing CLUT |
|---|---|---|---|---|---|---|---|---|
| `E8769E55-8F297232` | s4-world-main | [640, 0] | [208, 493] | 18 | - | 1024 P/ok, 2048 P/ok | C23FBCB2 1024 P; C23FBCB2 2048 P | C23FBCB2 @[0, 498] (50 pairs, cut 0.9659) |
| `5536C111-0E4551D4` | s4-world-main | [704, 0] | [176, 483] | 204 | - | 1024 P/ok, 2048 P/ok | F7BC428D 1024 P; F7BC428D 2048 P | - |
| `E72FB1C1-E14B839C` | s4-world-main | [768, 0] | [176, 481] | 128 | - | 1024 P/ok, 2048 P/ok | 6120F214 1024 P; 6120F214 2048 P | - |
| `D349E0F6-ADC69046` | s4-world-main | [832, 0] | [48, 492] | 91 | - | 1024 P/ok, 2048 P/ok | C23FBCB2 1024 P; C23FBCB2 2048 P | - |
| `1DE4AA74-B075D96A` | s4-world-main | [896, 0] | [224, 492] | 182 | - | 1024 P/ok, 2048 P/ok | BC152D9C 1024 P; BC152D9C 2048 P | AFCB9DD0 @[240, 492] (98 pairs, cut 0.1209) |
| `3E287F33-C77255FE` | s4-world-main | [960, 0] | [96, 484] | 88 | - | 1024 P/ok, 2048 P/ok | 7F387439 1024 P; 7F387439 2048 P | - |
| `D57D51A6-5BCA596E` | s4-enemies-main | [320, 0] | [96, 495] | 448 | - | 1024 P/ok, 2048 P/ok | 72B1090A 1024 P; 72B1090A 2048 P | - |
| `0FD152CA-E48C96C4` | s4-enemies-main | [384, 0] | [96, 504] | 139 | - | 1024 P/ok, 2048 P/ok | 12A610FF 1024 P; 12A610FF 2048 P | - |
| `C7C81B36-95A45D3F` | s4-enemies-main | [448, 0] | [192, 495] | 200 | - | 1024 P/ok, 2048 P/ok | 8F9C8C34 1024 P; 8F9C8C34 2048 P | - |
| `B305DC32-2EC288F8` | s4-effects-main | [384, 256] | [208, 489] | 8 | - | 1024 P/ok, 2048 P/ok | C12DB7DC 1024 P; C12DB7DC 2048 P; C12DB7DC 1024 P; C12DB7DC 2048 P | - |
| `AFCCB3B5-8DD9DD06` | s4-effects-main | [448, 256] | [160, 495] | 40 | - | 1024 P/ok, 2048 P/ok | 70EEEA84 1024 P; 70EEEA84 2048 P | - |

Missing for every gate key: its complete source (or that of the drawn sibling key), draw rows, surface identity. Pages with palette-hold keys also need AQ-05 phase lists, and FX pages whose probe failed need the class fix verified (see the JSON `missing_evidence`).

### B. Panorama 05E1881C keys

| key | CLUT xy | pairs | phase | ramp rho | slice of an 8bpp row |
|---|---|---|---|---|---|
| `05E1881C-C77255FE` | [96, 484] | 88 | - | 0.643 | - |
| `05E1881C-190A55AD` | [176, 511] | 88 | hold | None | - |
| `05E1881C-7C8D4073` | [112, 484] | 46 | - | 0.647 | - |
| `05E1881C-60F3C8E8` | [96, 494] | 38 | - | 1.0 | - |
| `05E1881C-AB4C9A40` | [192, 494] | 35 | - | None | - |
| `05E1881C-303CBAD4` | [208, 484] | 26 | - | None | - |
| `05E1881C-8A0B5CA6` | [160, 484] | 24 | - | None | - |
| `05E1881C-C739060A` | [176, 484] | 18 | - | None | - |
| `05E1881C-0DF30EDD` | [272, 511] | 18 | hold | None | - |
| `05E1881C-7F387439` | [192, 484] | 12 | - | None | - |
| `05E1881C-5468C58F` | [128, 484] | 7 | - | None | - |
| `05E1881C-A9651F8C` | [304, 511] | 3 | hold | None | - |

### D. Palette-phase holds on authored pages: 34 keys

`E8769E55-0F736F08`, `E8769E55-190A55AD`, `E8769E55-C7A1F2F0`, `5536C111-190A55AD`, `E72FB1C1-0DF30EDD`, `E72FB1C1-190A55AD`, `D349E0F6-0DF30EDD`, `D349E0F6-190A55AD`, `D349E0F6-A9651F8C`, `D349E0F6-F055ACAD`, `1DE4AA74-0DF30EDD`, `1DE4AA74-190A55AD`, `3E287F33-0DF30EDD`, `3E287F33-190A55AD`, `3E287F33-A9651F8C`, `D57D51A6-0DF30EDD`, `D57D51A6-190A55AD`, `D57D51A6-77D0BEF4`, `D57D51A6-A9651F8C`, `D57D51A6-C12DB7DC`, `D57D51A6-CAFC4AA7`, `0FD152CA-190A55AD`, `0FD152CA-47FBD679`, `0FD152CA-718199E6`, `0FD152CA-A9651F8C`, `C7C81B36-190A55AD`, `B305DC32-190A55AD`, `B305DC32-A9651F8C`, `B305DC32-C12DB7DC`, `AFCCB3B5-0DF30EDD`, `AFCCB3B5-190A55AD`, `AFCCB3B5-70EEEA84`, `AFCCB3B5-B4B798B5`, `AFCCB3B5-C12DB7DC`

### E. Unauthored stage-specific 4bpp content pages: 25

`63155483` (2/13, s4-large-unit-main), `DA56446E` (2/23, s4-bigunit-A), `4D604948` (2/24, s4-bigunit-B), `76D13080` (2/15, s4-world-variant-c), `B8C589D7` (2/22, s4-world-section-b), `A7EDCEC0` (2/15, s4-world-variant-c), `8F704A7B` (2/19, s4-unit-set-d), `FC0FAB8A` (2/23, s4-boss-shared-sprites), `4A519D9C` (2/19, s4-unit-set-d), `1487349C` (2/23, s4-boss-shared-sprites), `B55A0A46` (2/13, s4-effects-main), `F14BC7EB` (2/22, s4-effects-section-b), `7FA8921D` (2/19, s4-unit-set-d), `CA6A566F` (2/23, s4-bigunit-A), `D9DD5078` (2/24, s4-bigunit-B), `9B8107D2` (2/22, s4-world-section-b), `BBA2A146` (2/23, s4-bigunit-A), `972812FD` (2/24, s4-bigunit-B), `BDDC16DB` (2/13, s4-large-unit-main), `6BA92E4C` (2/23, s4-bigunit-A), `B4BCBAB4` (2/24, s4-bigunit-B), `A5ECBA22` (2/22, s4-effects-section-b), `04010B4F` (2/22, s4-effects-section-b), `10932164` (2/18, s4-effects-global-explosion), `F1BEEE00` (2/27, s4-lettering-transmission)

### F. Run prerequisites

- **route:** continuous recomp run through Stages 1-3 into Stage 4 (AQ-02 stage-select and AQ-03b DuckStation states cannot confirm keys)
- **pack:** stock textures for every Stage 4 key (no HD pack); HD dump stock-first to <run>/stage4-source/
- **recorder:** draw rows with fields ['key', 'frame', 'source_kind', 'depth', 'semi', 'page_xy', 'clut_xy', 'uv_bounds', 'uv_vertices', 'xy']; marks stage:4:entry, seg:4:<id> at each 0x80081382 change, clear:4; CPU-VRAM snapshot at every mark
- **gate_list:** C:\github\Einhander\remaster-audit\runtime-diagnostics-v58\capture-checklists\keys\S4-gate-keys.txt
- **checklist:** C:\github\Einhander\remaster-audit\runtime-diagnostics-v58\capture-checklists\S4.md

## Stage 5

Counts: gate keys 12, panorama keys 15, 8bpp items 15, phase holds 52, unauthored content pages 19.

### A. Gate keys (frozen candidate art)

| key | family | page | CLUT xy | pairs | phase | frozen exports (primary / s/2) | transparency probe | best competing CLUT |
|---|---|---|---|---|---|---|---|---|
| `9F3D98EF-51E8E21E` | s5-world-main | [640, 0] | [192, 482] | 278 | - | 1024 P/ok, 2048 P/ok | A345AE9E 1024 P; A345AE9E 2048 P | - |
| `7E088757-51E8E21E` | s5-world-main | [704, 0] | [192, 482] | 136 | - | 1024 P/ok, 2048 P/ok | FAC936BC 1024 P; FAC936BC 2048 P | - |
| `452F3CC3-793A3662` | s5-world-main | [768, 0] | [112, 483] | 135 | - | 1024 P/ok, 2048 P/ok | 066C0B81 1024 P; 066C0B81 2048 P | - |
| `1A2ACF78-6A8B1A18` | s5-world-main | [832, 0] | [80, 494] | 75 | - | 1024 P/ok, 2048 P/ok | 0DA351E7 1024 FAIL conn 20 s2 1830; 0DA351E7 2048 FAIL conn 83 s2 8106 | 0DA351E7 @[192, 483] (134 pairs, cut 0.2869) |
| `503474BD-1A80CA9D` | s5-world-main | [896, 0] | [224, 484] | 74 | - | 1024 P/ok, 2048 P/ok | F5FB4FC8 1024 P; F5FB4FC8 2048 P | - |
| `1F11EE57-DEECFC4B` | s5-boss-duerer | [448, 0] | [96, 491] | 78 | - | 1024 P/ok, 2048 P/ok | F46F4FE9 1024 P; F46F4FE9 2048 P | C50BDF9E @[128, 485] (97 pairs, cut 0.0) |
| `2B4626A3-3FF2DBD5` | s5-boss-duerer | [512, 0] | [128, 484] | 28 | - | 1024 P/ok, 2048 P/ok | 62027D2B 1024 P; 62027D2B 2048 P | 382D7BFF @[144, 484] (54 pairs, cut 0.0) |
| `BFC445B0-A132B3B3` | s5-boss-duerer | [576, 0] | [96, 493] | 42 | - | 1024 P/fail 89, 2048 P/fail 386 | 066C0B81 1024 P s2 26; 066C0B81 2048 P s2 127 | - |
| `1168CC84-51E8E21E` | s5-boss-arena | [640, 0] | [192, 482] | 278 | - | 1024 P/ok, 2048 P/ok | A345AE9E 1024 P s2 94; A345AE9E 2048 P s2 423 | - |
| `3D108041-51E8E21E` | s5-boss-arena | [704, 0] | [192, 482] | 136 | - | 1024 P/ok, 2048 P/ok | BE3400E6 1024 FAIL conn 43 s2 2238; BE3400E6 2048 FAIL conn 220 s2 9846 | - |
| `5C04E373-3FF2DBD5` | s5-effects-set | [512, 0] | [128, 484] | 28 | - | 1024 P/ok, 2048 P/ok | 62027D2B 1024 P; 62027D2B 2048 P | 382D7BFF @[144, 484] (54 pairs, cut 0.0) |
| `BD968A3C-A132B3B3` | s5-effects-set | [576, 0] | [96, 493] | 42 | - | 1024 P/ok, 2048 P/ok | 066C0B81 1024 P; 066C0B81 2048 P | - |

Missing for every gate key: its complete source (or that of the drawn sibling key), draw rows, surface identity. Pages with palette-hold keys also need AQ-05 phase lists, and FX pages whose probe failed need the class fix verified (see the JSON `missing_evidence`).

### C. Duerer 8bpp candidates (depth 1; 128 x 256-word page; 256-entry CLUT)

| key | texpage x | halves L / R | sub-image | 8bpp u / v | CLUT xy | pairs | CLUT status |
|---|---|---|---|---|---|---|---|
| `269AFAAD-0B616D37` | 384 | ['17F79F81'] / ['1F11EE57'] | 1F11EE57 (R) | [132, 251] / [8, 247] | [0, 509] | 10 | static 256-word row (3/1 upload 0,504,256,8) |
| `269AFAAD-B2AA7578` | 384 | ['17F79F81'] / ['1F11EE57'] | 1F11EE57 (R) | [132, 251] / [8, 247] | [0, 509] | 10 | ALL-ZERO: all-zero static candidate at a position that also has a non-zero static candidate |
| `269AFAAD-D5C392C5` | 384 | ['17F79F81'] / ['1F11EE57'] | 1F11EE57 (R) | [132, 251] / [8, 247] | [0, 511] | 6 | static 256-word row (3/1 upload 0,504,256,8) |
| `E6BFD1DB-0B616D37` | 448 | ['1F11EE57'] / ['2B4626A3'] | 1F11EE57 (L) | [4, 123] / [8, 247] | [0, 509] | 5 | static 256-word row (3/1 upload 0,504,256,8) |
| `E6BFD1DB-1EDE052B` | 448 | ['1F11EE57'] / ['2B4626A3'] | 1F11EE57 (L) | [4, 123] / [8, 247] | [0, 510] | 14 | static 256-word row (3/1 upload 0,504,256,8) |
| `E6BFD1DB-B2AA7578` | 448 | ['1F11EE57'] / ['2B4626A3'] | 1F11EE57 (L) | [4, 123] / [8, 247] | [0, 509] | 14 | ALL-ZERO: all-zero static candidate at a position that also has a non-zero static candidate |
| `87FCFE63-1EDE052B` | 512 | ['2B4626A3'] / ['BFC445B0'] | BFC445B0 (R) | [132, 231] / [136, 223] | [0, 510] | 5 | static 256-word row (3/1 upload 0,504,256,8) |
| `87FCFE63-B2AA7578` | 512 | ['2B4626A3'] / ['BFC445B0'] | BFC445B0 (R) | [132, 231] / [136, 223] | [0, 496] | 5 | ALL-ZERO: runtime-written row (zero-only in static data) |
| `87FCFE63-D5C392C5` | 512 | ['2B4626A3'] / ['BFC445B0'] | BFC445B0 (R) | [132, 231] / [136, 223] | [0, 511] | 4 | static 256-word row (3/1 upload 0,504,256,8) |
| `AEC51081-B2AA7578` | 640 | ['1168CC84'] / ['3D108041'] | 3D108041 (R) | [132, 199] / [176, 247] | [0, 496] | 2 | ALL-ZERO: runtime-written row (zero-only in static data) |
| `A3D0E675-0B616D37` | 704 | ['3D108041'] / ['D8403129'] | 3D108041 (L) | [4, 71] / [176, 247] | [0, 509] | 90 | static 256-word row (3/1 upload 0,504,256,8) |
| `A3D0E675-B2AA7578` | 704 | ['3D108041'] / ['D8403129'] | 3D108041 (L) | [4, 71] / [176, 247] | [0, 509] | 90 | ALL-ZERO: all-zero static candidate at a position that also has a non-zero static candidate |

Each needs:
- a depth-1 draw row (key, texpage, `uv_bounds`, `semi`) during the S5-5 marks;
- a complete source with a 256-entry CLUT;
- a CPU-VRAM snapshot of CLUT rows 496 and 509-511 for the flash and fade phases.
If none of the three sub-images is drawn at depth 1 during the whole fight, the 8bpp reading is wrong: the sub-images stay 4bpp native pass-through, and this must be reported.

### B. Panorama 05E1881C keys

| key | CLUT xy | pairs | phase | ramp rho | slice of an 8bpp row |
|---|---|---|---|---|---|
| `05E1881C-6C7962CE` | [16, 495] | 46 | - | 0.712 | - |
| `05E1881C-5F31B1FF` | [32, 489] | 42 | - | 1.0 | - |
| `05E1881C-361A4661` | [0, 511] | 30 | - | 0.999 | yes |
| `05E1881C-0ADAA698` | [160, 511] | 24 | - | None | yes |
| `05E1881C-190A55AD` | [256, 511] | 24 | hold | None | yes |
| `05E1881C-A8FC7D30` | [224, 488] | 16 | - | None | - |
| `05E1881C-B4B798B5` | [256, 510] | 11 | hold | None | yes |
| `05E1881C-264276C9` | [0, 510] | 9 | - | None | yes |
| `05E1881C-61603135` | [256, 497] | 7 | hold | None | - |
| `05E1881C-645AA604` | [0, 489] | 3 | - | None | - |
| `05E1881C-ECEB4BB9` | [0, 508] | 3 | - | None | - |
| `05E1881C-3091E9CA` | [0, 509] | 3 | - | None | yes |
| `05E1881C-F055ACAD` | [288, 511] | 2 | hold | None | yes |
| `05E1881C-A538829E` | [256, 501] | 2 | hold | None | - |
| `05E1881C-DFE9270D` | [256, 501] | 2 | hold | None | - |

### D. Palette-phase holds on authored pages: 52 keys

`9F3D98EF-30E98693`, `9F3D98EF-3E221370`, `9F3D98EF-47FBD679`, `9F3D98EF-726A2440`, `9F3D98EF-8097C274`, `9F3D98EF-BE3400E6`, `7E088757-0DF30EDD`, `7E088757-190A55AD`, `7E088757-24FAE118`, `7E088757-8097C274`, `7E088757-9D752218`, `7E088757-BE3400E6`, `452F3CC3-02491337`, `452F3CC3-190A55AD`, `452F3CC3-2C49B2AB`, `1A2ACF78-190A55AD`, `1A2ACF78-8097C274`, `1A2ACF78-BE3400E6`, `1A2ACF78-F055ACAD`, `503474BD-0B23F291`, `503474BD-190A55AD`, `503474BD-53319E83`, `503474BD-53505D66`, `503474BD-66C1F81B`, `503474BD-693585C2`, `503474BD-EBEFD80E`, `503474BD-ED6FF7CF`, `503474BD-F91F96F0`, `1F11EE57-190A55AD`, `1F11EE57-F055ACAD`, `2B4626A3-02491337`, `2B4626A3-190A55AD`, `2B4626A3-1E4E0007`, `2B4626A3-2C49B2AB`, `2B4626A3-B4B798B5`, `1168CC84-30E98693`, `1168CC84-3E221370`, `1168CC84-47FBD679`, `1168CC84-726A2440`, `1168CC84-8097C274`, `1168CC84-BE3400E6`, `3D108041-0DF30EDD`, `3D108041-190A55AD`, `3D108041-24FAE118`, `3D108041-8097C274`, `3D108041-9D752218`, `3D108041-BE3400E6`, `5C04E373-02491337`, `5C04E373-190A55AD`, `5C04E373-1E4E0007`, `5C04E373-2C49B2AB`, `5C04E373-B4B798B5`

### E. Unauthored stage-specific 4bpp content pages: 19

`EE299B43` (3/1, s5-enemies-main), `F0587A74` (3/11, s5-unit-set-a), `FAF858EB` (3/12, s5-unit-set-b), `17F79F81` (3/16, s5-boss-duerer), `8E04A88B` (3/1, s5-enemies-main), `88EDE9D4` (3/11, s5-unit-set-a), `391A9CFF` (3/12, s5-unit-set-b), `8121BE19` (3/16, s5-boss-duerer), `327A20CE` (3/1, s5-enemies-main), `F2D8404D` (3/11, s5-unit-set-a), `385C73DC` (3/12, s5-unit-set-b), `11FA828A` (3/17, s5-boss-arena), `4DB524A5` (3/1, s5-large-unit-main), `D8403129` (3/17, s5-boss-arena), `81FB494C` (3/17, s5-boss-arena), `4F542B30` (3/6, s5-effects-set), `CC4D7802` (3/13, s5-world-sky-variant), `10932164` (3/10, s5-effects-global-explosion), `D8024236` (3/20, s5-lettering-transmission)

### F. Run prerequisites

- **route:** continuous recomp run through Stages 1-4 into Stage 5 (AQ-02 stage-select and AQ-03b DuckStation states cannot confirm keys)
- **pack:** stock textures for every Stage 5 key (no HD pack); HD dump stock-first to <run>/stage5-source/
- **recorder:** draw rows with fields ['key', 'frame', 'source_kind', 'depth', 'semi', 'page_xy', 'clut_xy', 'uv_bounds', 'uv_vertices', 'xy']; marks stage:5:entry, seg:5:<id> at each 0x80081382 change, clear:5; CPU-VRAM snapshot at every mark
- **gate_list:** C:\github\Einhander\remaster-audit\runtime-diagnostics-v58\capture-checklists\keys\S5-gate-keys.txt
- **checklist:** C:\github\Einhander\remaster-audit\runtime-diagnostics-v58\capture-checklists\S5.md

