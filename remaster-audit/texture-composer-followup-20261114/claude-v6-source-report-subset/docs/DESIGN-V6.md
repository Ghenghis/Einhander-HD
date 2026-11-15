# Private decode-worker identity for RGB-only sidecars: design v6 (claude-einhander, 2026-11-14)

This builds on `DESIGN-V5.md`, which is unchanged. **Frozen v5-r2 is preserved exactly.** v6 follows root's
authorization in msg_26707276 and moves the v5 RGB-only level-0 identity check off the draw thread.

In v5 that check costs a full-page hash on the draw thread at first texture build: a cold median of 6.6 ms for 4096²
pages and 1.2 ms for 2048². v6 moves it into the pack's below-normal decode worker.

## Private pack copy (`make_pack_patch.py` → `pack-v6/`)
- **Source and limits:**
  - **Base (rebased, root msg_7755bd3a / msg_0be9e145):** root's frozen READ-ONLY closure
    `remaster-audit/runtime-review/gpu-texture-remix-20261114/v6-pack-base-from-v48/` (`BASELINE.json`; it also pins
    `third_party/stb_image.h` 866095d4…). My own snapshot `pack-base-v48/` has the same hashes and is kept as an unused
    duplicate. Both come from `C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime`:
    - `src/hd_texture_pack.cpp` 22a97b56…, `src/hd_decode_queue.h` 434b57a1…;
    - `include/hd_texture_pack.h` 78234dfd…, byte-identical to the frozen v61 `include/hd_texture_pack.h`.
  - It keeps the incremental-index API and stats (`hd_texture_pack_upload_index_incremental`, `index_incremental*`,
    `index_pointer_fixups`).
  - **Rejected base:** the canonical source (392bb8f2… / f921262a…) drops that API, so rebuilding from it would remove
    an existing implementation. The canonical-based generator is kept as `make_pack_patch.canonical-base-REJECTED.py`
    (bef13b3d…).
  - All six anchors apply unchanged to the v48 base.
  - **Limitation:** v61 linked a *retained* object. Root rebuilds this TU from the private copy and runs the pack
    regression and lifetime checks before any private link.
- **Anchored pure-addition patch:** six unique anchors, CRLF preserved; removing the insertions reproduces the input
  byte for byte.
  - `DecodedImage` gains `id_x4`, `id_state` and `id_has_cutout` (internal C++ struct, not ABI).
  - `DecodeCache` gains `identity_enabled`, set once in `hd_texture_pack_create` from
    `PSXRECOMP_HD_DECODE_IDENTITY` (exactly "1"). This is the same pattern as `PSXRECOMP_HD_EMISSIVE`; the flag is
    immutable afterwards.
  - The decode worker, after the RGBA copy and before taking the cache lock that publishes the item Ready, computes
    HDCM-X4 + has-cutout over the decoded RGBA. **Default OFF:** with the env unset, nothing runs and there is no hash
    cost in normal decode.
  - A new C accessor `hd_texture_pixels_identity(px, &x4, &cut)` is declared in the additive `hd_texture_identity.h`.
    - It is O(1) and reads through `px->lease` to the leased `DecodedImage`.
    - It returns OK only if `id_state == 1` and the caller's `rgba`/`width`/`height`/`stride` still equal the leased
      image's.
    - Otherwise it returns NO_LEASE, UNAVAILABLE or MISMATCH.
    - It **cannot** validate a forged lease pointer; that is not claimed.
- **Lifetime:**
  - A `DecodedImage` is only written by the worker and published under the cache mutex as a `shared_ptr`.
  - A lease holds its own `shared_ptr`, so the image and its identity outlive eviction and stay immutable.
  - Re-decode after eviction creates a new image.
- **Shared hash:** `hdcm_x4.h` is GENERATED from `hd_class_mips.inc`: `hdcm_rd64` and the HDCM-X4 block, extracted
  byte for byte. One source of truth with the renderer's `hdcm_rgb_level0`.
- No output, no printing. Mask, alpha, emissive and every pre-existing behaviour are unchanged.

## Renderer glue (`make_patch.py`)
- `PSXRECOMP_HD_DECODE_IDENTITY=1` is read with the other opt-ins and only takes effect with the RGB-only dir on.
- For an RGB-only key, admission calls `hd_texture_pixels_identity(px, …)`, then `hdcm_rgb_admit_identity`, which
  checks key, native dims, HD dims, level-0 == x4 and has-cutout == cut. That is O(1) and reads no pixel.
- **Fail closed:** an unavailable identity or a mismatched lease is rejected as `HDCM_E_IDENTITY` and keeps the v61
  path. There is **no fallback hash**.
- **Env not set or not exactly "1":** the v5 pixel path is unchanged.
- Class sidecars (HDCMSC02) keep v4 behaviour. An HDCMSC03 class follow-up waits, as root said.
- Counters: head value 13 = `rgbonly_identity_used` (14 head values), and a new reason `IDENTITY`.

## Tests (host run, `run_host.py`; exit code follows the verdict)
- **Fixtures:** `hdcm_rgb_admit_identity` is checked for every reason, for its equality with the pixel path when the
  identity is true, and for the opaque page.
- **Glue harness `rgbid`:**
  - The stub returns the true identity, then the pixel pointer becomes an invalid SENTINEL, so any pixel read, hash or
    fallback would fault.
  - Checked: admission, unavailable/mismatch/no-lease → IDENTITY, wrong x4 → LEVEL0, wrong cut → CUTOUT, HD and native
    dims, an unlisted key (no accessor call), recycle, sampling, no I/O, counters.
  - `identity-env-true` keeps the v5 pixel path. Every v4/v5 mode asserts the accessor is never called.
- **Pack test** (`pack_identity_test.cpp`): the real patched copy, the real worker thread and real leases, over a
  temporary pack of real PNGs.
  - Inputs: the three smallest RGB-only keys plus the opaque control, with expected HDCM-X4 values computed
    independently by the offline tool over the same stb decode.
  - Modes: env "1" gives the identity, guards (width/height/stride/rgba/no-lease/null) and lifetime across eviction
    (budget 0) with a held lease, then re-decode into a new allocation with the same identity and a cross-lease
    MISMATCH; env unset and env "true" give UNAVAILABLE everywhere.
- **Mutants:** 4 `.inc`, 4 glue and 6 pack-side, each of which must fail:
  - `.inc`: the identity admit skipping each check.
  - glue: the accessor result ignored, a fallback pixel hash, the env not exact, identity mode ignored.
  - pack: the accessor ignoring `id_state`, or skipping the rgba binding or the stride check; the env not exact; the
    worker hashing a short row or dropping the cutout truth.
- **Compile:** the patched renderer TU is compiled with the exact v61 flags plus `-I pack-v6`. The pack TU must add no
  new warnings.

## Not covered (root's)
- The private link (rebuild the hd_texture_pack TU from `pack-v6`), the pack regression suite, live timing of the
  first build with identity on, and any GPU or game check.
