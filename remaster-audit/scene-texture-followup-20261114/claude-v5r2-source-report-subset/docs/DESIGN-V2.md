# Private opt-in class-aware mips on the frozen v61 renderer: design v2, native authority (claude-einhander, 2026-11-14)

**Supersedes `DESIGN.md`** (kept unchanged). Its "level-0 centre pixel = cell class" authority was **never built**.
Root's msg_4a893884 is correct that HD centres can differ from the native classes; RISE has 295 such cells per key.
This version implements root's msg_ff9702ba requirements.

## Scope and ownership
- **Ownership:** only `class-mip/renderer-v61-classmip/` (approved in msg_ff9702ba).
- **Input:** the frozen v61 renderer, read only:
  - `sampling-build-v61-view-metrics-r2/src/gpu_gl_renderer.c`, sha256 `90c6a4e1…`, byte-identical to v58;
  - its include dir. The canonical runtime is untouched.
- **Root owns:** linking, any executable, the cache, the live census, qualification, GPU runs and GitHub publication.
- **Output:** a patched **private copy** produced by the anchored, pure-addition generator `make_patch.py`, plus host
  evidence.

## Opt-in
- Behaviour is **default OFF**. It requires both:
  - `PSXRECOMP_HD_CLASS_MIPS=1`
  - `PSXRECOMP_HD_CLASS_MIPS_DIR=<private sidecar dir>`
- It is considered only on draws the existing v61 facade/world experiment already admits (`hd_facade_motion_match`:
  filter mode, 95A3BCF8 atlas and the two facade regions), on the non-resident upload path.
- **Admission is per key**, and only for keys with a sidecar. The first and only list is 95A3 region O:
  `95A3BCF8-60245B3A` (green) and `95A3BCF8-07A9568D` (pink).
- Other world palettes find no sidecar, are counted as `NOFILE`, and keep the original v61 path. There is **no broad
  world-palette admission.**

## Sidecar `<TH>-<PH>.hdcm` (format HDCMSC01; parser in `hd_class_mips.inc`)
- **Built offline** by `run_host.py` step 4, only for listed keys that are preverified:
  - R1-clean (every level-0 centre class equals the native class);
  - frozen whole-cell breakdown status PASS;
  - the runtime decoder output equals the PIL decode.
- **Binds:**
  - texture/palette hash, native w/h, scale (power of two, at most 64), levels = log2(scale), HD w/h;
  - a 64-bit hash of the **exact decoded level-0 RGBA**. It is computed with the runtime's own `stb_image.h`
    (sha256 866095d4…, same defines as the runtime), because `hd_texture_pack.cpp` passes `stbi_load_from_memory(…, 4)`
    through unchanged;
  - an R1-verified flag;
  - the **native class map** from the CRC-proven words + CLUT (strict checker v2);
  - a self-hash over the whole file.
- **Size cap:** 48 + 256·256 + 8 bytes.

## Runtime admission (`hd_class_mips_build_slot`)
- **Steps, in order:**
  - read the file (bounded malloc, freed before return; no cache);
  - parse: size, magic, self-hash, scale/levels, flag, every class in {0,127,255};
  - admit: key, native dims against the draw's upload, HD dims, decoded level-0 hash, and a **runtime R1 re-check**
    (every centre pixel's class equals the native map).
- **Any failure:** `rejected[reason]++` and the slot is left untouched, so it takes the original v61 path (its own
  `glGenerateMipmap` and level-0 class). A defensive mid-build failure resets MAX_LEVEL to the GL default, so the
  original path regenerates every level.
- **Admitted:**
  - levels 1..log2(s) are built from the decoded level 0 + the **native map**, byte-identical to proto-v2b
    `cm_build_level`, and uploaded with explicit `glTexImage2D(level L)`;
  - `MAX_LEVEL = log2(s)` (BASE 0);
  - `facade_mips_ready` is set, so **`glGenerateMipmap` can never replace the chain**.
- **Review fixes (root msg_6dc79298, after frozen v1; v1 is superseded and kept unchanged):**
  - `hdcm_build_level` rejects any L outside 1..log2(s) **before** shifting by L; L = 32, INT_MAX and INT_MIN are
    tested.
  - The build+upload runs through `hdcm_build_upload_chain`, which **fails closed**:
    - each level upload is verified by its level dimensions (`glGetTexLevelParameteriv`), which does **not** consume
      the GL error state, so the renderer's existing error observability is unchanged;
    - the chain stops at the first unverified level with reason `GL`;
    - only verified levels are counted;
    - the glue then restores BASE 0 and the GL default MAX_LEVEL, leaving the slot flags untouched, so the original
      path regenerates every level.

    Host-tested with an injected stub upload that fails at each level.
  - `run_host.py` now exits non-zero when its verdict is FAIL.
- **Sampler state:** `hd_facade_motion_sampling` still only switches MIN_FILTER per draw (LINEAR_MIPMAP_LINEAR when
  active, else LINEAR or NEAREST) and never touches MAX_LEVEL; the base-filter cache path is only used when the
  facade/world experiment is off.
- **Counters** (no printing): attempted, admitted, levels_uploaded, bytes, ticks and `rejected[16]`, through
  `gl_renderer_class_mips_counters()`, for a future TCP verb that root owns.

## Shader (HD_FS)
- `uniform int u_hd_class_levels` stays 0 unless enabled.
- The branch, placed after the existing level-0 `class_alpha` fetch, runs only when
  `u_filter != 0 && u_hd_facade_motion != 0 && u_hd_class_levels > 0`:
  - the class LOD is `log2` of the larger HD-pixel derivative, clamped to [0, levels];
  - the class comes from `texelFetch` at `round(lod)`;
  - RGB comes from the existing `textureGrad`, now sampling class-aware RGB levels with no cutout bleed.
- **Known difference:** with anisotropy, the class uses the isotropic max LOD (conservative; it suppresses shimmer).
- **Point path unchanged:** in point mode no mip filter is ever selected, and the branch requires `u_filter != 0`.

## Evidence (`runs/<UTC>/`, one below-normal worker, per-run folders, failures kept)
1. **Fixtures:**
   - port vs prototype byte equality with native maps, including maps that differ from the centres;
   - properties;
   - R5 fill;
   - sidecar acceptance and every reject reason;
   - hash test vectors equal an independent Python reference.
2. **Mutants:** 17 mutants (builder, R5, hash, parser, admission) must each be caught.
3. **Real pages** (region O ×2, 95A3BCF8-397FBE8A, RISE, K page):
   - stb decode equals PIL;
   - R1 counts;
   - port equals prototype at every level;
   - hash and build times. Build time is a one-time cost at first upload per admitted key: a stutter risk, measured
     here.
4. **Sidecars** for region O, with round-trip admission. **Real-data negatives:**
   - the green sidecar against pink pixels gives LEVEL0;
   - the green sidecar on the pink key gives KEY;
   - RISE is refused offline (R1);
   - a falsely flagged RISE sidecar is rejected at runtime with R1.
5. **Patch:** anchored, pure addition, CRLF preserved.
6. **Compile only:** exact v61 flags (-O3), patched and an unpatched control; no new warning kinds.
7. **GLSL:** HD_FS extracted from both preprocessed TUs and validated offline with glslangValidator.
8. **GL self-test executable for root** (next): a GPU run that renders minified strokes with and without class levels
   and checks them by readback. Root runs it, not me.

## RISE (separate track)
- **Policy:** root's msg_36952fa4. Connectivity-only plus R1/source checks is the primary defect criterion; the s/2
  bound is diagnostic.
- **Deliverable:** a three-way review (stock / authored / repaired) that keeps authored RGB and labels deliberate
  letter-shape differences. No global native font mask.
