# Stage 5 Duerer: the three likely-8bpp sub-images inside the 4bpp armour pages

Written 2026-11-14 ~13:47Z by `claude-einhander-s45` (task EIN-S5-WHOLE-CELL-20261114). Static evidence only. No live data exists,
and nothing here is HD art or a new identity.
Evidence:
- `source-map/20261114T133831Z/source-map.json` (sha256 `14bf3441...d0cd`), section `duerer_8bpp`;
- runtime source `windows-x64/psxrecomp/runtime/src/hd_native_page.h`, read-only;
- Duerer v2 manifest `4d25b621...7db`.

## 1. What is assumed, and what is proven

| Statement | Status |
|---|---|
| The sub-images are 1-texel vertical stripes when read as 4bpp and coherent plates when read as 8bpp (lane-s5 `alt8_mask`) | heuristic (lane-s5); J-C re-measures it |
| The runtime keys a depth-1 (8bpp) draw by CRC32 of **128 VRAM columns x 256 rows** from the texpage x (`hd_page_hash` uses `width = 64 << depth`). Its CLUT is **256 words of one CLUT row** | **proven from source** |
| The static model's depth-1 page keys are exact concatenations of two adjacent 4bpp pages, row by row | **proven** (half-page sha256 matches, CRC32 of words = TEX, CRC32 of CLUT = PAL) |
| The disc's TMD/TSB harvest pairs these 8bpp pages with CLUT rows 509/510/511 (3/1 upload `0,504,256,8`) | static evidence (pair counts below), not a draw |
| The Duerer actually draws any of these keys | **unproven**: no capture has reached Stage 5 |
| The 4bpp keys of the same pages are still drawn for other parts (numerals, FX) | **unproven**; the page words serve both readings |

## 2. Candidate runtime keys (exact static predictions)

Here L and R are the left and right 64-column halves of the 128-column 8bpp page.

| Sub-image (4bpp page) | 8bpp key | texpage x | L / R halves | CLUT xy | pair count | notes |
|---|---|---|---|---|---|---|
| `1F11EE57` (448, 3/16): 517 blocks, 4bpp box u8-247 v8-247 | `E6BFD1DB-1EDE052B` | 448 | 1F11EE57 / 2B4626A3 | 0,510 | 14 | 8bpp u 4-123, v 8-247 |
| | `E6BFD1DB-0B616D37` | 448 | same | 0,509 | 5 | |
| | `269AFAAD-0B616D37` | 384 | 17F79F81 / 1F11EE57 | 0,509 | 10 | 8bpp u 132-251, v 8-247 |
| | `269AFAAD-D5C392C5` | 384 | same | 0,511 | 6 | |
| `BFC445B0` (576, 3/16): 163 blocks, 4bpp box u8-207 v136-223 | `87FCFE63-1EDE052B` | 512 | 2B4626A3 / BFC445B0 | 0,510 | 5 | 8bpp u 132-231, v 136-223 |
| | `87FCFE63-D5C392C5` | 512 | same | 0,511 | 4 | |
| `3D108041` (704, 3/17): 153 blocks, 4bpp box u8-143 v176-247 | `A3D0E675-0B616D37` | 704 | 3D108041 / D8403129 | 0,509 | **90** | 8bpp u 4-71, v 176-247 |
| | `AEC51081-B2AA7578` | 640 | 1168CC84 / 3D108041 | 0,496 | 2 | all-zero CLUT: draws nothing |

The ranges come from the lane's `alt8_mask` blocks (8x8 texels) and include every block. On 1F11EE57 the main component
is 4bpp v80-247; a small cluster of 15 blocks sits at 4bpp u208-247 v8-31.

Every 8bpp page above also has an all-zero `-B2AA7578` (0,509 or 0,496) variant, which draws nothing. A cross-member texpage
at 576 (BFC445B0 | 1168CC84, if 3/16 and 3/17 are resident together) is **not** predicted. If it is drawn, it would be a new
CRC, and the capture must report it.

## 3. Exact capture requirements (S5-5, refined)

For every Duerer phase mark, the draw rows of every depth-1 draw whose texpage x is in {384, 448, 512, 576, 640, 704} need:

1. `key` (the runtime CRC; it must equal one of the keys above, or it is new), `depth` = 1, `page_xy`, `clut_xy`,
   `uv_bounds`, `uv_vertices`, `xy`, `semi`;
2. a **complete source** for each such key in `stage5-source/`: words of 128 x 256, a `.clut.bin` of **256 entries**, `valid.bin`
   all non-zero, and CRC32 = key. A 16-entry CLUT read at that `clut_xy` is not enough;
3. the 4bpp draws of the same pages in the same frames (`1F11EE57-*`, `BFC445B0-*`, `3D108041-*`), so it is known which
   texels each reading actually uses;
4. a CPU-VRAM snapshot, so rows 509-511 can be checked for runtime CLUT writes (palette flashes or fades on hit).

Pass: at least one depth-1 row for each of the three sub-images, each with a complete source. If none is found across the
whole fight, the 8bpp reading is wrong, and the pass-through blocks stay as 4bpp.

## 4. Authoring plan (after the capture; nothing is rendered before it)

1. **Separate identities.**
   - Each confirmed 8bpp key gets its own master over its full 128 x 256 page. The u range uses two 8bpp texels per word, so
     the master is 256 x 256 texels.
   - The 4bpp keys keep their existing masters. The pass-through blocks in Duerer v2 (`native-8bpp-pending`) remain the
     4bpp delivery.
2. **Index space.**
   - 8-bit indices: the soft-label master works on 256 labels (top-3 weights).
   - Continuous-index smoothing is allowed only along the CLUT row's luminance order. Measure that order per captured CLUT,
     because the 256-colour rows look sorted.
3. **Class contract.** Same as 4bpp: CLUT word 0 = cutout, STP bit = 255, else 127, stamped at every texel centre. A strict
   whole-cell audit is required before freezing.
4. **Overlap rule.**
   - Texels outside the sub-image belong to the neighbouring 4bpp page's own art (2B4626A3 effects, D8403129, 17F79F81).
   - An 8bpp master for those texels is a *different key*, and is authored only if the capture shows the 8bpp draw covering
     them. The uv_bounds settle this.
5. **Material.** The hull plates take the Stage 5 camouflage/sandworn swatches at the Duerer v2 amplitude. Detail only;
   the paint scheme follows the captured CLUT.
6. **Freeze** under `parallel-stages-20261114/s45/duerer-8bpp/<rev>/`, then hand to `codex-einhander` for integration.

## 5. Static ranking (J-C, pending a CPU grant)

`tools/s45_8bpp_rank.py` decodes each candidate over the sub-image through each non-zero 256-entry CLUT. It writes
coherence metrics (mean |grad| along u and v, cutout share, index range) and reference-only crops. It ranks plausibility;
it does not confirm a key.
