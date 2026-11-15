# Glue r3: the T2 r6 owned present lifecycle in the runtime (claude-einhander), written 2026-11-15 ~00:24Z

**Status: SOURCE-ONLY PROPOSAL, for root's review.** Nothing here has been compiled or run, and **no native output is
suppressed** anywhere. GLUE-R3-SOURCE step 2, per root msg_b02d1bcc, the decisions in msg_08008ad5, msg_2fe98abb,
and design 19db18ce.

Preserved unchanged:
- glue r2 (de9dfd77 / 3bbc6821 / 730b5b4f / a88b6911 / c6a59759);
- gpu.c de9dfd77, which is reused as is (no new hook is needed);
- T2 r3, r4 and r6;
- ledgers r0, r1, r2 and r3;
- the 37c and v68 parents.

## Files

| File | sha256 |
|---|---|
| `patched/scene_runtime.cpp` | b0d820a705714fa024475393ce3359f1d8a5a0764f75dccb0cf4e2990e9895b4 |
| `patched/scene_runtime.h` | 6c69adcbe2dc078c4062734bf09bf5b3e1c75e7ac45cbddbdf8b437b36076dfc |
| `patched/scene_t2_bridge.r3.cpp` | 5182d80ddb8c4aa6bde518be23ccc54157f21c693d643c222d7d67a97f0476cb |
| `patched/scene_t2_bridge.r3.h` | f09f3296bb2894fd228799e34bc047d7d655cc87dc88199539f7702cb5156c73 |
| `test_glue.r1.cpp` (fixture glue, revision r1, 19 authored checks, none in loops or helpers) | 44ab03a6ef6e76e340750ff5d45ad4864f061727729d1d6384f3fc5056be62cf |
| `scene_runtime.r2-to-r3.cpp.diff` | f7eb6e59654080340e33cb59a32585886aaef06e268fec5356fe889137c95815 |
| `scene_runtime.r2-to-r3.h.diff` | 1662c26d3dbc69a40ce90e510517be41a7c6c19306f135bb27347ceef37a09e9 |
| `scene_t2_bridge.r2-to-r3.cpp.diff` | 35ba160f0d85db5c54e750e375cde6d49d4df0a3bd39466604192fa69e2b20a0 |
| `scene_t2_bridge.r2-to-r3.h.diff` | b1a02347e7b78d20b6bb733e8d29fdf9b819d2faeb44d1050f11b715fab8d68a |

The harness's `xform_hash` is a verbatim copy of v66-r3 `scene_capture.cpp` 78c4158d lines 15-21, checked with diff.

## Call sites (scene_runtime r3 → bridge r3)

| Runtime event (owner unless stated) | r3 behaviour |
|---|---|
| `scene_runtime_arm` | When PGXP is off: reference mode, then `PROVENANCE_UNAVAILABLE`. When capture and ledger both arm: reference off, then `prime_scanout` (the first observation only, which bumps), then `capture_begin` (current epoch, **no bump**, requires runtime owner_errors == 0). A refused ledger arm: retire all + epoch (as r2), plus reference mode when the ledger is disabled. |
| GP1 `scene_runtime_scanout_changed` | `observe_scanout`. Only the bound candidate's exact target, as the first change after its boundary, avoids the bump. r2's raw-snapshot fields are gone. |
| every GP0 `scene_runtime_ledger_command` (any ledger mode) | 1. ledger record; 2. `check_seal` (hand-off); 3. `note_command`, where the ledger r3 pure footprint goes to `note_write`, and unknown (polyline, unmapped, mapping ≠ 1, malformed, unsupported) retires all. gpu.c calls the capture hook (:5160) before the ledger hook (:5162), so a command that seals frame N first binds N, and then its own write is checked against N. |
| `scene_runtime_tick` | ticks, then `check_seal` |
| `check_seal` | Once per armed generation, when capture and ledger have both SEALED it. `invalid` = bit 0 capture incomplete, bit 1 ledger incomplete, **bit 2 `gpu_scene_gp0_open()` at the seal** (root msg_2fe98abb). |
| `scene_runtime_cancel` / owner `scene_runtime_invalidate` | retire all + epoch. A foreign thread bumps the epoch only; the owner retires at its next boundary (T2R_EPOCH). |

## Producer `scene_t2_on_seal(invalid)` (bridge r3)

1. `boundary()` runs first, then the bounded abandoned and stale rules.
2. `invalid != 0`: `invalidate_all`. The reason bits are kept in the audit (decision 3).
3. A frame binds only if a pool slot is FREE and nothing is pending (`busy`). A bound candidate therefore always
   reaches the consumer.
4. The sealed generation's own records come through `scene_runtime_capture_get`; then the ledger export and the
   `SealedBinding`, whose epoch comes from `capture_begin`.
5. **SealedScanout**, all derived from exact sealed state:
   - the boundary is the PresentState snapshot;
   - **24-bit, interlaced and 480-line modes are not qualified**, so they stay native;
   - the target start is the ledger r2/r3 constant draw-area origin (`scene_ledger_draw_area`), and an empty
     interval or no observed state is refused;
   - the target size is the ONE displayed area of the interval (native halfwords). Its start must equal the
     PresentState scanout start, otherwise the frame is native.
6. `r6::build` runs with the r4 ledger policy (unchanged, still required) and the ledger r1 display-hazard adapter.
   The adapter re-checks the sealed header frame and generation.
7. `bind`, then publish into a **private pool of 4 immutable `T2FrameR6`** (decision 4). The slot states are FREE,
   BUILDING, PUBLISHED and TAKEN. A PUBLISHED or TAKEN frame is never rebuilt or overwritten, and `release()`
   frees only a TAKEN frame.

## Consumer API (any thread; nothing suppresses)

- `scene_t2_take()` returns the published frame or nullptr.
- `scene_t2_gate(frame, overlay, completion)` is the r6 decision only.
- `scene_t2_scanout_now()` gives a consistent generation and state for the CompletionR6 stamp.
- `scene_t2_release()` returns a taken frame to the pool.

## Fixture test_glue.r1 (19 authored checks)

The fake PGXP views are T1-consistent:
- the GP0 vertex word is the reprojected SXY word;
- RTP_COMMITTED + SF, cmd 1, lane 0;
- the GTE-ring RT/TR match `xform_hash`;
- exact MAC values.

So `scene_capture` qualifies two real textured polygons, ledger r3 records them, and T2 r3/r4/r6 transport them. The
groups:

| Group | Checks |
|---|---|
| L | The complete lifecycle: first GP1 seen (epoch 1→2); one seal → built, bound, published (scan T2S_OK, bind T2B_OK). The frame has serial 1, 2 transported primitives and target rect (0,256,320,240). The gate refuses before the flip. An ordinary N+1 arm leaves the epoch and the pending candidate intact. The expected flip makes the gate true with no bump. A back-buffer fill keeps the frame; a front fill retires it (T2R_WRITE). Release, then take() is empty. |
| O | Upload body open at the seal: invalid = 4, nothing binds, the epoch bumps. Later data and ticks do not revive it. |
| M | A depth change at the flip is unexpected: retired, and the gate refuses. |
| Q | A 24-bit scanout at the seal is refused (`refused_scanout`); nothing binds. |
| P | A polyline header after the flip retires everything (T2R_UNKNOWN_WRITE). |
| R | PGXP off gives PROVENANCE_UNAVAILABLE and reference mode. Recovery binds only a NEW sealed frame (serial 4); nothing old is revived. |
| F | A foreign-thread consumer takes, stamps, gates (true) and releases. Then a foreign `scene_runtime_arm` gets WRONG_THREAD, so the owner's next arm returns OK with armed_epoch 0: no seal hand-off, no frame. |

## Remaining (not in this revision)

- **Build closure r2:** closure r1 plus the glue r3 TUs, ledger r3 and T2 r6, with harness r1. It needs the same
  native/strict split, the hermetic and v69-closure checks, and `PSXRECOMP_SCENE_CAPTURE=1` for the run child.
  Next on my side.
- **Interval re-arm policy:** which interval is captured next is a controller decision. Arming at a seal records the
  interval after next.
- **Not qualified:** composition, G4 material identity, the compositor, any live suppression.
