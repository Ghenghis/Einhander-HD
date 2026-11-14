# v66 / v67 class-mip counter review (claude-einhander, 2026-11-14 ~15:30Z)

- Reviewer: replacement claude-einhander. CLI 1c56db97-2f5d-4f18-aece-e2a77dbf7a70, desktop local_43668750-1a3c-49e9-8775-c31ee3df3847.
- Requested by codex-einhander in msg_08afefb5f2231fd7 and msg_f049741ec00f3ea2.
- Task: EIN-S1-V66-REVIEW-20261114.
- Scope: read-only source review. No compiler, build, game or GPU was used.
- Location: kept here because this session's Write tool is blocked from canonical C:/github/Einhander paths. A
  worktree-isolation PreToolUse guard does the blocking.

## Inputs read (sha256)
**v6 contract source (frozen, immutable)**
- `remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v6/`, READY 33ccad7e…
  - `src/hd_class_mips.inc`: reason enum
  - `src/make_patch.py`: `s_hdcm_diag` struct, the counters accessor, and RGB-only admission at lines 196-233
  - `src/glue_harness.c`: counter checks
  - `docs/DESIGN-V6.md`

**v66 base**
- `remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3/`, exe 51ec32e3…
  - `src/gpu_gl_renderer.c`: b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16
  - `src/debug_server.c`: 14d208f21ee21d8af2c2b38b52d01a9662b761a95bed02e824926831011f0e08
  - `src/hd_class_mips.inc`

**v67 prepared r2**
- `…/sampling-build-v67-decode-identity-r2/`:
  - `src/gpu_gl_renderer.c`: 9a878ca4… (equals v6 patched_tu)
  - `src/hd_class_mips.inc`: 91a2dc4f… (equals the v6 include)
  - `src/hd_texture_pack.cpp`: 6f65ee3c…
  - `src/hd_texture_identity.h`: 25c940c3…
  - `src/hdcm_x4.h`: 5619213b… (all three pack files equal v6 pack-v6)
  - `counter-handler.inc`: bd3ef70f21e777cbe700fe7aad341402bb4e91ac5e0f8d75373e13125728bec5
  - `counter-contract.json`: 4d19dce1b8478e8b720e9b96abb4d1ed582519999418865bdae032b16c129c1e
  - `prepared.json`: b2c52992…
  - `revision-receipt.json`: e1e5f926…

**Recipes**
- `remaster-audit/runtime-review/gpu-texture-remix-20261114/prepare_v67_source.py`
- `prepare_v67_r2.py`
- `build_private_v67.py`

**r1** (`…-v67-decode-identity-r1`) is preserved.
- Its build.json shows `build_complete false` and `AssertionError(('compile-counter-adapter', 0))`.
- rc 0, so the failure was in the child-exit observation. r2 corrects that.
- At ~15:29Z, r2 had no build.json yet.

## Verified (PASS)
1. **v6 counter contract = 98 values.**
   - Enum: HDCM_OK=0 … HDCM_E_CUTOUT=19, HDCM_E_IDENTITY=20, so HDCM_REASONS=21.
   - Accessor layout:
     - 14 head values, ending with `rgbonly_identity_used`;
     - then 4 tables of 21: preload_rejected, rejected, rgbonly_preload_rejected, rgbonly_rejected.
   - The accessor returns the number of values written, which is at most `cap`.
   - The frozen glue harness calls it with cap 102 and asserts a return of 98.
2. **v66 was internally consistent, so no published v66 counter is mislabelled.**
   - The v66 base compiled the v4 renderer: `head[10]` plus 2 tables × HDCM_REASONS = 19, so 48 values.
   - The old handler used `v[64]`, cap 64 and `values[1800]` under schema `hdcm-v4-counters`. That is exact for v4.
   - Truncation happens only if the v6 renderer is linked behind the v66 handler: it would emit 64 of 98 values.
     - Kept: the head values, both class tables and `rgbonly_preload_rejected[0..7]`.
     - Lost: `rgbonly_preload_rejected[8..20]` and the WHOLE `rgbonly_rejected` table, including IDENTITY, LEVEL0 and CUTOUT.
   - So v67's handler replacement is required. Root's finding is confirmed.
   - A narrow search (runtime-review json, scene-export results, the v66 build dir) found no published runtime
     `hd_class_mips` reply. The only hits were file-path references in post-restart-*.json.
3. **Head 13 counts identity ATTEMPTS.**
   - Per `make_patch.py:217`, `++rgbonly_identity_used` runs before `hd_texture_pixels_identity()` and before
     `hdcm_rgb_admit_identity()`. Rejections are counted too.
   - So `counter-contract.json` names head 13 `rgbonly_identity_attempts`, and its note is correct.
   - Documentation defect in the frozen v6: the struct comment `make_patch.py:83` says "admissions decided by the
     decode-worker identity", and DESIGN-V6 gives no semantics.
     - v6 is immutable, so the v67 contract note is the correction of record.
     - Fix the comment in any later renderer revision.
4. **No reply truncation.**
   - `debug_server_send_fmt` formats into a 64 KiB stack buffer, with an exact-size heap fallback.
   - The v67 `values[TOTAL*21+1]` = 2059 bytes. The worst case is 98 × 20 digits + 97 commas + NUL = 2058.
   - The UINT64_MAX control (id 12) exercises this.
5. **Control rows map the right slots.**
   - id 11 sets head 13 and `rgbonly_rejected[HDCM_E_IDENTITY]`, which is index 14 + 3·21 + 20 = 97.
   - The build asserts values[13] and values[97] = 2^64−1 and length 98.
   - ids 20-23 force -1, 0, 97 and 99, and each is rejected with `hdcm-counter-contract` and no values.
6. **Root pins are honoured by the recipe.**
   - It asserts parent exe 51ec32e3, v6 READY 33ccad7e (my pin), `v6-cpu-verification-r1` passed, and pack header
     equality with v6-pack-base-from-v48.
   - The reason names are re-derived from the copied include, with an assert that there are 21 and that IDENTITY is
     last.

## Findings
**F1 (should fix; cheap): the drift check catches shrink but NOT growth.**
- The handler calls `gl_renderer_class_mips_counters(v, TOTAL)` with cap == TOTAL == 98.
- The accessor stops at `cap`. A future renderer with more than 98 values would therefore return exactly 98 and pass as
  `hdcm-v6-counters`, with truncated tables and the reason indices shifted.
- The forced 99 control cannot happen with a real cap-honouring accessor, so it does not test growth.
- Today's v67 links the pinned v6 TU (exactly 98), so it produces no wrong output now. The risk is a later renderer
  behind a stale adapter, which is exactly how the v66→v6 problem arose.
- Fix:
  - `uint64_t v[TOTAL + 1]`;
  - `count = gl_renderer_class_mips_counters(v, TOTAL + 1)`;
  - require `count == TOTAL`.
- Control: a stub that models a 99-value, cap-honouring accessor (`return min(cap, 99)` after writing).
  - It must be rejected.
  - With the current handler it would be ACCEPTED, which demonstrates the gap.
- Root decides whether this goes into r2 or a later revision.

**F2 (suggestion for live acceptance or a collector check): exact identity invariant from the source.**
- Let `R = 14 + 3·21 = 77` be the base of `rgbonly_rejected`.
- With `PSXRECOMP_HD_DECODE_IDENTITY=1` and the RGB-only dir on, every found RGB-only sidecar goes through the identity
  call, and a missing sidecar counts as NOFILE without a call. So:
  - `v[13] == v[11] + Σ_{i=2..20} v[R+i]`, where v[11] is rgbonly_admitted and NOFILE (i=1) is excluded;
  - `v[R+20]`, the IDENTITY reason, counts fail-closed lease or availability rejects. A healthy run targets 0.
- With identity off or the env unset, `v[13] == 0`.
- Caveat for consumers: the RGB-only reject paths return before `ticks += …`, which is pre-existing v5 behaviour.
  head[7] `ticks` is therefore admission-only time, not the total admission-decision cost.

**F3 (cosmetic): one error reply lacks a reason.**
- The snprintf-overflow reply `{"id":..,"ok":false}` carries no `error` field.
- It is unreachable given the buffer sizing in point 4; optionally add `"error":"hdcm-counter-format"`.

## Not covered
- No compile or run by me. The adapter controls are root's, under grant msg_7c878bd6.
- Pack incremental/tracker ABI: root's separate bounded regression (msg_567f818e). Not reviewed here.
- Nothing here is live acceptance.
