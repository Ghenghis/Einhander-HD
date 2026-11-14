# Stage 4 / Stage 5 authoring backlog beyond the selected 23 keys (static prediction level)

Written 2026-11-14 14:07Z by `claude-einhander-s45`.
Sources: `backlog/20261114T135849Z/backlog.json` (sha256 `f23bca51ee0cd710550e80172cab1bd49c7329a2a6189b7c50b6e1508bed2d31`) and `page-reuse/20261114T140003Z/reuse.json` (sha256 `9c2e3d3144bf98c615207a0df92aa50dd5643d253ccbd07ff691c10505ced40f`).

These come from static disc predictions only. Runtime-only keys are outside this list by construction:
- animated or runtime-written CLUTs (on Stage 1, 60% of drawn keys);
- MoveImage cells;
- code paths the static model does not read.

Boss and route identity of a page is not recorded on the disc, so it comes from capture.

## Totals

| | Stage 4 | Stage 5 |
|---|---|---|
| texture CRCs with predicted keys | 148 | 160 |
| selected (authored, candidate) | 11 | 12 |
| shared, unbuilt (05E1881C) | 1 | 1 |
| unauthored, common members only (0/x; mostly also predicted for Stage 1) | 88 | 93 |
| unauthored, stage-specific | 48 | 54 |
| of which trivial (one index, or one value on >= 97% of the page) | 1 (`011FFCA6`) | 2 (`011FFCA6`, `D7978EEB`) |
| **of which 4bpp content pages, exact or likely static words** | **23** (750 keys) | **11** (246 keys) |
| of which runtime-composed or raw (need capture) | 7 (148 keys) | 22 (701 keys) |
| of which 8bpp / 15bpp page fallbacks (mostly 1-2 static keys) | 17 (16 keys) | 19 (23 keys) |

- `011FFCA6` is byte-identical in S4 and S5, and every one of its words is 0: it is a cleared VRAM page. It needs no authoring; native pass-through or a flat fill is enough.
- `10932164` (S4 member 2/18, S5 member 3/10; 1-2 keys) is noise-like data.
- `05E1881C` is covered by `PANORAMA-05E1881C-OWNERSHIP.md`.

## Stage 4: 4bpp content pages to author (most keys first)

| TEX | member | VRAM | keys | best pair | nearest authored page (texel / strip identity) |
|---|---|---|---|---|---|
| `63155483` | 2/13 | (512, 0) | 105 | 129 | B305DC32 [384, 256] 0.2203 / 0/32 |
| `DA56446E` | 2/23 | (512, 0) | 105 | 129 | B305DC32 [384, 256] 0.215 / 0/32 |
| `4D604948` | 2/24 | (512, 0) | 105 | 129 | B305DC32 [384, 256] 0.1178 / 0/32 |
| `76D13080` | 2/15 | (896, 0) | 51 | 182 | E8769E55 [640, 0] 0.0994 / 0/32 |
| `B8C589D7` | 2/22 | (896, 0) | 51 | 182 | E8769E55 [640, 0] 0.2265 / 0/32 |
| `A7EDCEC0` | 2/15 | (832, 0) | 38 | 91 | D57D51A6 [320, 0] 0.0794 / 0/32 |
| `8F704A7B` | 2/19 | (320, 0) | 30 | 448 | B305DC32 [384, 256] 0.2323 / 0/32 |
| `FC0FAB8A` | 2/23 | (320, 0) | 30 | 448 | B305DC32 [384, 256] 0.3607 / 0/32 |
| `4A519D9C` | 2/19 | (384, 0) | 29 | 139 | AFCCB3B5 [448, 256] 0.2335 / 0/32 |
| `1487349C` | 2/23 | (384, 0) | 29 | 139 | B305DC32 [384, 256] 0.2943 / 1/32 |
| `7FA8921D` | 2/19 | (448, 0) | 26 | 200 | B305DC32 [384, 256] 0.1309 / 0/32 |
| `CA6A566F` | 2/23 | (448, 0) | 26 | 200 | B305DC32 [384, 256] 0.177 / 0/32 |
| `D9DD5078` | 2/24 | (448, 0) | 26 | 200 | B305DC32 [384, 256] 0.1668 / 0/32 |
| `9B8107D2` | 2/22 | (640, 0) | 23 | 50 | E8769E55 [640, 0] 0.7219 / 16/32 |
| `BBA2A146` | 2/23 | (768, 0) | 19 | 128 | B305DC32 [384, 256] 0.2155 / 0/32 |
| `972812FD` | 2/24 | (768, 0) | 19 | 128 | B305DC32 [384, 256] 0.1971 / 0/32 |
| `BDDC16DB` | 2/13 | (576, 0) | 9 | 63 | D57D51A6 [320, 0] 0.0689 / 0/32 |
| `6BA92E4C` | 2/23 | (576, 0) | 9 | 63 | B305DC32 [384, 256] 0.1416 / 0/32 |
| `B4BCBAB4` | 2/24 | (576, 0) | 9 | 63 | 5536C111 [704, 0] 0.0909 / 0/32 |
| `A5ECBA22` | 2/22 | (448, 256) | 5 | 40 | B305DC32 [384, 256] 0.3588 / 1/32 |
| `04010B4F` | 2/22 | (384, 256) | 4 | 17 | B305DC32 [384, 256] 0.3361 / 1/32 |
| `10932164` | 2/18 | (704, 256) | 1 | 3 | B305DC32 [384, 256] 0.1949 / 0/32 |
| `F1BEEE00` | 2/27 | (704, 256) | 1 | 3 | C7C81B36 [448, 0] 0.4025 / 2/32 |

**Stage 4: runtime-composed or raw pages.** Author these only after a capture shows the composed words: `F089B050` (2/25 (320, 256)), `762FE898` (2/25 (320, 256)), `5BB71BC3` (2/25 (320, 256)), `B55A0A46` (2/13 (320, 256)), `F14BC7EB` (2/22 (320, 256)), `40978623` (2/13 (320, 256)), `136D1326` (2/22 (320, 256))

**Stage 4: 8bpp / 15bpp page fallbacks.** These are depth readings that the static TSB harvest predicts at a 4bpp position. Each one is real only if a capture shows a draw at that depth. The Duerer 8bpp set is the main exception; see `DUERER-8BPP-PLAN.md`. The fallbacks: `0C3B0C5B`, `A7E282EA`, `0BF56F1F`, `8BE04C6E`, `25546D5B`, `2247983C`, `04D61FA1`, `EB49CC06`, `9EA1965E`, `A9A4B2F1`, `23F0D914`, `5F3C7579`, `6B954054`, `6C89A675`, `1D41AE0E`, `FE7445D6`, `30846B78`

## Stage 5: 4bpp content pages to author (most keys first)

| TEX | member | VRAM | keys | best pair | nearest authored page (texel / strip identity) |
|---|---|---|---|---|---|
| `327A20CE` | 3/1 | (448, 0) | 45 | 97 | BD968A3C [576, 0] 0.1426 / 0/32 |
| `F2D8404D` | 3/11 | (448, 0) | 45 | 97 | BD968A3C [576, 0] 0.2189 / 0/32 |
| `385C73DC` | 3/12 | (448, 0) | 45 | 97 | 1168CC84 [640, 0] 0.1242 / 0/32 |
| `11FA828A` | 3/17 | (896, 0) | 26 | 74 | BD968A3C [576, 0] 0.3486 / 0/32 |
| `4DB524A5` | 3/1 | (512, 0) | 19 | 54 | BD968A3C [576, 0] 0.3805 / 3/32 |
| `D8403129` | 3/17 | (768, 0) | 17 | 135 | 2B4626A3 [512, 0] 0.3934 / 0/32 |
| `81FB494C` | 3/17 | (832, 0) | 17 | 134 | 5C04E373 [512, 0] 0.2271 / 0/32 |
| `4F542B30` | 3/6 | (960, 0) | 14 | 46 | BD968A3C [576, 0] 0.4516 / 3/32 |
| `CC4D7802` | 3/13 | (960, 0) | 14 | 46 | 452F3CC3 [768, 0] 0.1657 / 0/32 |
| `10932164` | 3/10 | (704, 256) | 2 | 19 | 2B4626A3 [512, 0] 0.2078 / 0/32 |
| `D8024236` | 3/20 | (704, 256) | 2 | 19 | BD968A3C [576, 0] 0.5324 / 3/32 |

**Stage 5: runtime-composed or raw pages.** Author these only after a capture shows the composed words: `7456C37F` (3/18 (320, 0)), `59E4C716` (3/18 (320, 0)), `EE299B43` (3/1 (384, 0)), `F0587A74` (3/11 (384, 0)), `FAF858EB` (3/12 (384, 0)), `17F79F81` (3/16 (384, 0)), `8E04A88B` (3/1 (320, 0)), `88EDE9D4` (3/11 (320, 0)), `391A9CFF` (3/12 (320, 0)), `8121BE19` (3/16 (320, 0)), `61B4D32B` (3/1 (384, 0)), `61BA3ACE` (3/11 (384, 0)), `07BB32CE` (3/12 (384, 0)), `269AFAAD` (3/16 (384, 0)), `36E0FC35` (3/1 (320, 0)), `7D50F4B1` (3/11 (320, 0)), `F0B2C9D1` (3/12 (320, 0)), `D7DF7FBB` (3/16 (320, 0)), `7A698A8B` (3/1 (384, 0)), `D94CB548` (3/16 (384, 0)), `AED3EB92` (3/1 (320, 0)), `FE1E65F8` (3/16 (320, 0))

**Stage 5: 8bpp / 15bpp page fallbacks.** These are depth readings that the static TSB harvest predicts at a 4bpp position. Each one is real only if a capture shows a draw at that depth. The Duerer 8bpp set is the main exception; see `DUERER-8BPP-PLAN.md`. The fallbacks: `7728345A`, `4405032E`, `87FCFE63`, `0E2694E7`, `DC5B6B81`, `E6BFD1DB`, `69A65B37`, `14350691`, `6F5B76B9`, `B266B570`, `5F9E4F87`, `A7CB5C30`, `D69B3B04`, `6930C04C`, `82289E86`, `A3D0E675`, `C046B78E`, `3708172A`, `AEC51081`

## Suggested order (CPU, after J-AB2 / probes / repairs)

1. **Stage 5 Duerer member 3/17 pages 768 / 832 / 896** (`D8403129`, `81FB494C`, `11FA828A`).
   - These complete the boss armour set, using the Duerer v3 (class-aware FX) method.
   - They need identity marks from S5-5.
2. **Stage 4 section-b world** (member 2/22: `9B8107D2` at 640, `B8C589D7` at 896) and the 2/15 pages at 832 / 896.
   - Use the world v3 method and Stage 4 swatches.
   - `9B8107D2` shares 72% of its texels (16/32 strips) with the authored `E8769E55`.
3. **Stage 4 enemy variants** in members 2/19, 2/23 and 2/24 (320-768).
   - Their static key and pair counts equal those of the 2/13 enemy pages, but they share less than 40% of their words, so they are separate art.
   - The 512,0 pages (`63155483`, `DA56446E`, `4D604948`; 105 keys each) are the largest single pages.
4. **Stage 5 stage-entry 3/1 pages** at 448 / 512 (`327A20CE`, `4DB524A5`), and the 960,0 replacements (`4F542B30` member 3/6, `CC4D7802` member 3/13). These two also overwrite the panorama column.
5. Everything is predicted-static. Import only after `validate_predicted.py confirm` + `gate` on the live run.
