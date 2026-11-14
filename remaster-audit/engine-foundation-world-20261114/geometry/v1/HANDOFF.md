# Opt-in GTE view provenance, private v1: implemented and host-tested (claude-einhander, 2026-11-14)

**Status: private candidate source.**
- Canonical runtime files were read only, never written.
- Not built into any game binary, not run in-game, and no live coverage has been measured.
- **Not ray tracing**, and not a Remix backend. It is the per-vertex 3D foundation those need
  (`../../remix-bridge-feasibility/REMIX-CAPABILITY-MATRIX.md`, track A1).
- **Default OFF:** nothing is allocated or recorded until `pgxp_set_view_payload(1)`.
- This supersedes the design in `../PROPOSAL.md` (sha256 11a831b5…, left byte-unchanged), with every correction from
  Codex's review (msg_654f53b4d658deab) applied. They are listed below.

## Files (all under `remaster-audit/runtime-review/remix-provenance/impl/`)
| File | sha256 |
|---|---|
| `make_view_provenance_patch.py` (generator: hash-asserted canonical bases, exact-count anchors) | b30505a5…bca4 |
| `src/gte.cpp` | ecec9636…6b12 |
| `src/pgxp.cpp` | 99e46152…a7a3 |
| `include/pgxp.h` | 8d2d90fb…5897 |
| `diffs/gte.cpp.diff` (129 lines) / `pgxp.cpp.diff` (433) / `pgxp.h.diff` (120) | 0d573917… / 836f98ff… / d118ec51… |
| `tests/test_pgxp_view.cpp` | 8bed4809…af5 |
| `run_host_test.py` | cae3e7ad…eb46 |
| `host-test.json` (results) | 9903d4f6…3529 |
| `patch-receipt.json` | a0992d43…15e6 |

The bases are hash-asserted against the canonical runtime: `src/gte.cpp` 0563d9a1…, `src/pgxp.cpp` b3a6dae3…,
`include/pgxp.h` b9bacf31….

## What it does
- **Producer: `gte_rtps_internal`, per projected vertex.** When opted in, it passes:
  - the **raw int64 MAC1..3 = TR·4096 + RT·V**, unshifted and unsaturated. V is a signed int16 model coordinate and RT
    has 12 fraction bits, so the view coordinate is `mac / 2^12` with no loss (`PGXP_VIEW_MAC_FRAC_BITS`);
  - V, H, OFX and OFY;
  - the flags `SF`, `LM`, `IR_SAT`, `SZ_SAT`, `DIV_OVF` (2·SZ3 ≤ H, the same test as `gte_divide`), `XY_SAT`, `XY_CLAMP`
    (16.16 transport clamp), `WS_SQUASH` and `DOME`;
  - the **RTPT lane** (V0/V1/V2 → 0/1/2), the command, the frame, an FNV xform hash of RT/TR/H/OFX/OFY, and the **predicted
    ring identity** (`s_gte_rtp_seq`).
- **Commit: `gte_rtp_record`, after execute.** It validates the pending records against the ring record the same command
  writes: seq, cmd, lane count, per-lane V and xform hash. Only then does it set `RTP_COMMITTED`.
  - Records that fail are counted (`commit_mismatch`) and are never marked.
  - In builds without debug tools there is no ring, so nothing commits. The payload itself stays self-contained and valid.
- **Ring accessors.** `gte_rtp_ring_seq_live(seq)` checks seq < total, total − seq ≤ 256K and the stored seq.
  `gte_rtp_ring_get_xform` returns RT/TR, frame and caller RA, and only for a live record. A stale transform is never
  returned after the ring wraps.
- **Transport (pgxp.cpp).**
  - The flag `PGXP_F_VW` lives in the existing 16-bit flags, so the `PGXPValue` size is unchanged.
  - Lazily allocated **parallel 32-bit tag arrays**: 2 MiB for RAM plus small static arrays for scratch, GPR and GTE.
  - **A 64K-entry record ring.** The record is **80 B in this build**, measured with `sizeof`, not assumed, so opt-in
    costs 7,340,032 B. Off costs 0 B.
  - All 15 whole-shadow copies go through `pv_copy`, which moves the tag only while VW is set.
  - Every place that drops VZ (a stale half in `pv_validate`, SH, SB) now drops VW too.
  - Non-identity arithmetic rebuilds flags from scratch, so VW is dropped by construction. The FIFO shift and reg 15 copies
    move tags exactly like the SXY FIFO.
  - After 2^32 tags the tag space restarts: invalidate, clear the ring, restart at 1.
- **Consumer: `pgxp_get_precise_vertex_view(addr, word, &out)`.**
  - **DATAFLOW only**: a live address-keyed shadow whose word equals the packet word, VXY complete and VW set. It never
    falls back to the position cache.
  - It then checks that the record has not been reused (`evicted`) and that it **describes this shadow** (word, x16, y16
    and sz3; otherwise `incoherent`).
  - Immediate GP0 words (no address) never carry a view.
- **Lifecycle.**
  - `pgxp_set_view_payload(1)` allocates lazily and **fails closed**: it stays off and counts `alloc_fail`.
  - Any toggle calls `pgxp_invalidate_all()`, so no tag outlives its mode. Disabling keeps the allocation.
  - The speculative bracket and the replay sandbox produce and commit nothing.
- **Observability:** `pgxp_get_view_stats()`, which gives produced, overwritten, commit ok/mismatch, lookups, hits,
  no_shadow, value_mismatch, no_view, evicted, incoherent, alloc_fail, seq_wraps, record_bytes and alloc_bytes.
  - It is **not yet wired into the TCP debug server.** That is the next step: a `pgxp view` census field. No printf
    anywhere.

## Codex's review points: how each is handled
| Point | Handling | Test |
|---|---|---|
| V is int16, RT has 12 fraction bits; do not truncate to `mac>>12` or call it exact XYZ | Raw int64 MAC plus a declared scale | T1 (MAC equals the independent int64 per lane); mutant "payload stores shifted MAC" is caught |
| Native projection uses IR saturation, UNR and XY saturation, so it cannot always match a reprojection | Flags record every divergence; matching is only asserted when unsaturated | T1: faithful reprojection (truncated IR, exact division) within 0.05 px; ideal pinhole within H/SZ3 + 0.05 px. T1b: IR_SAT+XY_SAT+XY_CLAMP, SZ_SAT+DIV_OVF (behind the camera), DIV_OVF only (near plane), LM+IR_SAT |
| The ring records after execute, the producer runs before; pin the identity plus the RTPT lane and validate the commit | Predicted seq, lane, V and xform hash are checked at `gte_rtp_record` | T1/T2: lanes 0/1/2 share the seq. T5: wrong seq, xform, V or lane count are all rejected (4 mismatches), exact is accepted |
| The finite 256K ring wraps; never return stale transforms after overwrite, wrap or reset | Liveness check plus the stored-seq compare; view-record reuse is detected | T5: after 64K+8 projections the old view is `evicted`, not stale; after 2^18 more, the ring identity is not live and `get_xform` returns 0 |
| Allocate lazily on opt-in only; measure the real size | Lazy, fail-closed, sizes measured | T8: 0 B before opt-in (and it notes that the always-on GTE ring is pre-existing and allocates regardless; no zero-allocation claim); T8b: injected allocation failure stays off |
| GPR copies, SWC2, non-identity arithmetic, suppression toggles, failed allocation | All covered | T4: LW→MOVE→SW and MFC2→MTC2→SWC2 keep the view; a wrong word, a foreign store, a half write and ADDIU +1 drop it (precision is kept and the view is not); transport checked directly. T7: speculative bracket, replay sandbox, invalidate, off/on toggle and tag wrap |
| Full-source TUs compile, real host tests, mutants | Done | below |

## Verification (host only; `host-test.json`)
- Compiler: clang 22.1.8 (x86_64-w64-windows-gnu), `-std=c++17 -O1 -Wall -Wextra`, below normal priority, one compiler at a
  time.
- **`view_test_modified`:** the full modified `gte.cpp` + `pgxp.cpp` with debug tools on (the real `gte_execute` ring and
  commit). **137 checks, 0 failures.**
  - Counters: produced 327,721, commit_ok 327,707, commit_mismatch 4 (the 4 deliberate rejections).
- **Regression controls with the canonical harnesses:** `pgxp_test` and `gte_register_access_test`.
  - The latter uses `PSX_NO_DEBUG_TOOLS=1 PSX_GTE_REGISTER_TEST=1 PSX_ENABLE_BLOCK_CYCLES=1`, so it is also the no-debug
    build of the modified `gte.cpp`.
  - **Both pass on the canonical sources and on the modified sources.**
- Compiler warnings: identical for the canonical and modified TUs. Both are pre-existing and none are new.
- **Mutants: 15/15 caught.**
  - RTPT lane mis-indexed; shifted MAC stored; SZ_SAT misses negative depth; XY_SAT never set.
  - Ring liveness ignores overwrite; tag not moved with copies; identity copy drops the view; half write keeps the view.
  - Consumer skips word validation; producer ignores suppression or the sandbox; commit ignores seq.
  - Allocation failure fails open; enabled by default; toggle keeps old tags; tag wrap not restarted.
  - The first "half write keeps the view" run was **not** caught: the consumer's sz3 coherence check masked it. A direct
    transport probe (`pgxp_test_view_flag`) was added, and the rule is now enforced and tested on its own.

## Limits, stated plainly
- **View space, not world space.** PS1 folds camera and object into RT/TR. Camera/object separation is a separate,
  game-specific track (matrix track E).
- Coverage in Einhänder is unknown.
  - The view rides the existing PGXP dataflow. Per ENHANCEMENTS.md G1.10 that needs the PGXP hook flavour
    (`PSX_PGXP_VARIANT` / `-DPSX_PGXP=1`) for compiled code. Otherwise only the v14 SWC2 sites and interpreted paths feed it.
  - Measuring it needs a live leg run by Codex.
- The tolerance clamp and truncation agreement of `pgxp_get_precise_vertex` are screen-precision safeguards and are
  deliberately not applied to the view consumer. Word identity plus record coherence is the provenance rule.
- Equivalent by construction (not a test gap): the consumer's coherence check backs up the eviction check, so a reused slot
  whose record happens to describe the same word, x16, y16 and sz3 is treated as the same vertex.

## Next steps
1. Root review. If accepted, Codex applies the diffs to a private build branch. The generator re-asserts the base hashes.
2. A TCP census field for the view stats, as a separate small patch with its own test.
3. A live coverage leg: share of textured GTE triangles whose 3 vertices all carry a view.
4. Matrix track A2: primitive assembly in `gpu.c` behind the same opt-in.
