# Private opt-in class-aware mips on the frozen v61 renderer: design v3, prepared levels (claude-einhander, 2026-11-14)

This supersedes `DESIGN-V2.md`. Frozen v1 and v2 are **rejected performance designs**: they built levels synchronously on
the draw thread, 56–344 ms per 2048² page. They are kept unchanged; see `frozen/REJECTED-PERFORMANCE.md` and
`frozen/SUPERSEDED.md`.

## What changed, and why
1. **No level building on the draw thread** (root msg_28928d65).
   - Levels 1..log2(s) are built **offline** with the same builder (byte-identical to proto-v2b `cm_build_level`).
   - They ship in sidecar **HDCMSC02**, which carries: native map, prepared levels with per-level hash and exact length,
     decoded level-0 hash, key, dims, scale, R1 flag and a self-hash.
   - The renderer includes `hd_class_mips.inc` with `HDCM_NO_BUILDER`, so the builder does not exist in the runtime
     translation unit. The host run checks this in the preprocessed TU.
2. **Preload before gameplay.**
   - `hd_class_mips_preload()` runs from `hd_facade_motion_init()`, which `init_gpu_raster()` calls, before the
     world/facade early return.
   - It reads `<PSXRECOMP_HD_CLASS_MIPS_DIR>/index.txt` (at most 64 lines). Each file is size-checked **before**
     allocation, then fully verified (self-hash, per-level hashes, classes, M4: last level equals the native map).
   - Verified files go into a **bounded cache**: at most 8 entries and 96 MiB, fixed, never growing during play.
   - Every rejection is counted by reason.
3. **Draw thread:** on the first non-resident draw of a cached key, the work is bounded:
   - cache lookup;
   - one level-0 hash plus one R1 pass, measured on host (see the run result);
   - `glTexImage2D` of the prepared bytes, each level verified by its dimensions. This does not consume the GL error
     state.
   - There is no allocation, file access or building at this point.
   - **Fail closed:** the chain stops at the first unverified level with reason `GL`. BASE 0 and the default MAX_LEVEL
     are restored and the slot stays unmarked, so the original path applies.
4. **The admission gate changed, with evidence.**
   - `runs-ab/20261114T111427Z` measured all 804 whole-cell PASS keys on drawn cells.
   - **Region O (60245B3A/07A9568D) is fully opaque:** 0 mixed cells and 0 bleed. The class chain equals a box (RGB)
     chain within 2/255, so class levels give O **no visible benefit**, as root suspected.
   - **None of the 72 PASS keys inside the v61 world/facade experiment gate has a mixed drawn cell.**
   - 68 PASS keys outside that gate (mostly neon/sign pages) do, with level-1 bleed means up to 54/255 and class
     flicker up to 4% of cell pixels.
   - Admission is therefore keyed by **an explicit verified sidecar alone**, not by the world experiment. It is still
     default OFF, filter mode only, and per key.
   - **Initial list (eight keys, one per page variant):** 11CFE2E3-0E09E912, E360C964-C1B5906C, 31214B41-73AF4FAA,
     67DC56D7-96998A63, 327E6D9E-5039A9C5, E360C964-DF4F533F, 73BF9877-803A474F, A34295C8-FBCA4A8A.
5. **Sampler state** (`hd_class_mips_sampling`):
   - For an admitted slot in filter mode it selects LINEAR_MIPMAP_LINEAR and sets `u_hd_class_levels`. Inside the
     facade/world path the experiment has already selected the mip filter.
   - In point mode it writes no filter and sets the uniform to 0.
   - Non-admitted slots are untouched.
6. **HD_FS** (pure addition):
   - The class comes from `texelFetch` at round(lod) when `u_filter != 0 && u_hd_class_levels > 0`.
   - RGB comes from `textureGrad` with the existing derivatives when `u_hd_class_levels > 0` outside the facade path.
     The facade path already uses textureGrad.

## Scope of the GPU acceptance (root msg_dceeff35, my msg_e0abd316)
- **Lod 0 is unchanged by design;** the level-0 PNG is authored content. Lod-0 cutout bleed is the R5 content defect, a
  separate offline track, and is *reported*.
- **"No bleed" is required for m ≥ 2** (lod ≥ 1).
- **"Never vanishes" is guaranteed only for m ≤ s.**
  - Beyond the native cell (m > s) the class is the native map point-sampled below native resolution, which aliases
    exactly as native rendering would. That is reported, not passed.
  - A beyond-native coverage policy would be class dilation. It is evaluated separately and is not part of this patch.
- **The GL self-test also covers:**
  - the non-facade path (`u_hd_facade_motion` 0, class levels via textureGrad);
  - the renderer's exact verified-upload callback with an injected wrong-size level (fail closed);
  - a 2048² prepared-level upload timing on the GPU.

## Evidence, all under `runs/<UTC>/`
- Fixtures and mutants (builder, R5, hash, parser, levels, M4, admission, upload, cache).
- Real pages: decoder equality, R1, builder equality, preload-verify and draw-admit timings, prepared bytes equal to the
  builder output.
- Sidecars and index, with negatives.
- The **exact glue text** in a host harness with recording GL stubs (`glue_harness.c`).
- The patch (pure addition), compile-only of patched and control, the builder-absence check, and GLSL validation.
- **Root owns:** link, live runs, GPU and GitHub.
