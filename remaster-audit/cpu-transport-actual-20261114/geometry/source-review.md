# T2 r4: ownership, provenance and VRAM-policy layer (claude-einhander). Tool clock 2026-11-14 22:17Z

**Status: SOURCE ONLY.** Nothing here has been compiled or run, and no live gate is enabled. T2 r3
(`../remix_t2.r3.h` 8baba81c) and its test/driver are unchanged. The ledger r0 adapter
(`scene_ledger_t2.r0.h` 94bc9c24) stays diagnostic-only.

Queue task: EIN-PRIMARY-T1T2-DERIVED-HEADER-20261114. Root requests: msg_a04dd76a, msg_54b45d88 and msg_fb74eece.
Comment-only `pgxp.h` rule: msg_bc27e6c1 and msg_ae46b96a.

## Files (this directory, read-only, LF)

| File | sha256 | Role |
|---|---|---|
| `remix_t2.r4.h` | eebb2c8fd26a2df58bd6748cfefe7a670e236029cd6dcffe279617abd8478a96 | layer over r3 (`namespace t2::r4`) |
| `test_t2.r4.cpp` | 6a5aec97ee7beb46b4ae67a367bf4e2adf90e783ec1d78651dea97df71230771 | unit fixture, 55 checks |
| `test_t2r4_ledger.r4.cpp` | 74c4ab408009d656bd2f502af7ae3f78d3b7694bd44116b27c1d0d7510e7a34d | integration with the REAL ledger r0 policy, 21 checks |
| `build_t2_fixture.r4.py` | 7b39f6a48dce6e8f02ed35788ab9886951a30d21398b6e6f4dea4ba3750d1636 | driver: two compiles, two runs |

## Rules

1. **owner_errors == 0 and an unchanged immutable epoch at every boundary.**
   - The boundaries are build/acceptance (read before the r3 build and again *after the policy walk*), `publish`,
     `take`, `resolve`, and `gate_allow_suppress`.
   - At the gate, the completion must also carry the same epoch.
   - Each boundary re-reads the live atomics; nothing is checked once and then trusted.
2. **`T2Liveness`** is the only state a consumer touches: two private monotonic 64-bit atomics, `epoch` and
   `owner_errors`, with no API to decrease or set either.
   - `arm_epoch()` gives the epoch of a new generation.
   - `invalidate()` and `note_foreign()` bump it, so every frame bound to an older epoch is dead for good.
   - `owner_errors` is process-lifetime: any foreign GP0 disables transport for the rest of the process.
3. **`SealedBinding`** is filled by the producer on the owner thread from the sealed capture info, the sealed ledger
   header and the arm epoch.
   - `build` checks it against the capture info, the T2 ledger header, the ledger count and the r3 frame (frame,
     generation, command count, sealed/complete).
   - The frame then carries an immutable `T2Provenance`.
4. **VRAM policy binding.**
   - For a live r3 frame only, `build` collects the **exact final transported ordinal set**: input order, after r3
     classification and every r3 whole-frame rule, and cross-checked against `frame.transported`.
   - It calls the producer-thread `PolicyHook` with the binding's exact frame and generation, and requires
     `LP_TRANSPORT_OK`. Anything else is `PR_POLICY` (whole frame native); a missing hook is `PR_POLICY_MISSING`.
   - The evaluated set's verdict, count and fnv hash are recorded in the provenance.
   - `publish`, `resolve` and the gate all require `policy_ok`.
5. **Not relaxed.**
   - r3 coverage, ledger, order and interleave rules run unchanged.
   - Any r4 failure forces the whole frame native (r3 `frame_native`, `live_eligible` 0).
   - Diagnostic builds are refused here; they stay on r3.
   - G4 material and composition validity remain unproven.
6. **Residual.** The gate check is the linearization point; an invalidation after it applies from the next frame on.

## Glue duty (not implemented here; for a glue r1)

- `note_foreign()` on **every** runtime entry that can mutate or observe the GP0/frame stream from a foreign thread:
  enabled, command, ledger_command, tick, arm, cancel and invalidate. Not only enabled/tick (root msg_fb74eece).
- `invalidate()`:
  - at cancel, `gpu_reset_state` and savestate parse, **regardless of the calling thread**: a foreign reset or
    savestate must still kill exported frames;
  - at every external VRAM write;
  - at every GP1 display-area, range or mode change (`gp1_display_area_start`, h/v range, display mode).
    Neither the capture nor the ledger sees GP1, so a change after the last GP0 would otherwise go unnoticed.
- `arm_epoch()` right after successful capture and ledger arms. The epoch goes into the sealed binding.
- The policy hook: `scene_ledger_policy(owner token, generation, ordinals, count)`, after checking that the sealed
  ledger header still names this frame and generation (as `ledger_policy` in the integration fixture does).

## Fixtures

**Unit (55 checks):**
- **P:** the positive path through every boundary; r3 equivalence by memcmp.
- **B:** binding negatives: owner errors, capture, ledger, frame, generation, count, epoch, diagnostic, unbound,
  r3-native-not-exported, and policy not consulted for r3-native frames.
- **Q:** policy on a REAL transported set. Three primitives built verbatim like r3's `vert()`/`prim()`, the middle one
  unqualified, so the hook must receive exactly `{0, 2}` with frame 10 / generation 12, plus the set hash. Also:
  - verdicts 3/5/6/7/1 force native, and the frame is never published or gated;
  - missing hook;
  - an invalidation *during* the policy walk gives `PR_CHANGED_DURING_BUILD`.
- **F:** foreign GP0 or invalidation at each stage, each with its own `T2Liveness`:
  - after the seal;
  - after build;
  - after export (stale take, no resolve);
  - after take and resolve;
  - after completion (savestate);
  - stale-epoch and wrong-frame completions;
  - re-arm supersedes;
  - 2 x 1000 concurrent bumps;
  - no re-binding to a dead epoch;
  - a new arm cannot clear `owner_errors`.
- **S:** slot budget.

**Integration (21 checks)** use real ledger intervals plus T1-qualified primitives:
- **I0** baseline accepted, gate allows.
- **I1** CLUT mutation AFTER the last draw with a disjoint screen bbox: the adapter says complete, policy MUTATION,
  frame native.
- **I2** draw feedback: DRAW_DEST.
- **I3** display overlap: DISPLAY.
- **I4** readback: READBACK.
- **I5** foreign GP0 after export: the policy re-evaluates inside build and refuses (INCOMPLETE).
- **I6** external VRAM write after acceptance, then glue `invalidate()`: the gate refuses.
- **I8** GP1 display change after the last GP0, then glue `invalidate()`: the gate refuses.
- **I7** foreign GP0 after the seal: the export refuses, `PR_LEDGER`.

## Driver

`build_t2_fixture.r4.py` inherits:
- the T2 r3 closure pins;
- the T1 r3 comment-only `pgxp.h` derivation: raw 1f50599f, offset 3986 `*x16/*y16` → `*x16 and *y16`, derived
  50a6ef6d; strict warnings, no `-isystem`;
- the ledger r0 native closure. Its BLOCKS/TEMPLATE text (55901a53 lines 61-153) and helpers (lines 175-214) are
  `sed -n` byte copies, verified identical with `cmp`.

Steps: compile-unit, run-unit (t2 r4, 55), compile-integ (test plus `scene_ledger.r0.cpp`), run-integ
(t2r4_ledger r4, 21). It runs only under a grant naming the CPU, inside fa5e42fa (or a verified copy), at
`--timeout 120 --max-job-mib 1024 --no-window`.

## Checks actually run

File reads, sha256, CR counts, CHECK counts (55 / 21, all inside `main`, none in loops), and two `cmp` byte-identity
checks of the copied driver regions. **Nothing was compiled or run.** No pass is claimed, and thread linking and
the toolchain behaviour are unproven.

## Not claimed

No live, material (G4) or composition acceptance. The glue duties are unimplemented. No stage or project completion.
