# T2 r6: owned present lifecycle (claude-einhander), written 2026-11-14 ~23:07Z

**Status: SOURCE-ONLY PROPOSAL, for root's full review.** Nothing here has been compiled or run. There is no live
gate, no native suppression and no GPU permission. This is root's "new r5 source" from msg_31e3312e. It does not
modify or include T2 r5 (`../r5/remix_t2.r5.h` f429cc3b, preserved). T2 r3 (8baba81c) and T2 r4 (eebb2c8f,
including `arm_epoch()` and its F7 test) are unchanged. Root said no grant for the r5 32-check fixture until the new
source is fully reviewed; the same applies to this 50-check fixture.

## Files (this folder)

| File | sha256 |
|---|---|
| `remix_t2.r6.h` | 419dea9499010e5f5524b3913f81b09db0279ce87a25861a2cb49c17554f76dd |
| `test_t2.r6.cpp` (fixture t2, revision r6, 50 checks) | 06d3b8f0749876a2746c3a425e648f3b1731b9c683883743f05359222508fc94 |
| `build_t2_fixture.r6.py` (unit only) | 7d9f6beec484d73403514de8f5f668c9f1b4be858f47231babfbe27bc3a6dd6f |
| `build_t2_fixture.r5-to-r6.diff` | 833afce4ca55a1129b9ff8f0bfaebf695facf1fd10cb03c4a48a36332b6a1236 |

## Root decisions and where they are implemented

1. **Keep r4's `arm_epoch()`/F7 API and tests unchanged.** r4 is unchanged. r6 calling `arm_epoch()` still kills
   every r6 record (fixture F7).
2. **A separate capture-begin protocol using the current lifecycle epoch, only while the owner is healthy.**
   - `capture_begin(L, owner_healthy, &epoch)` returns `L.epoch_now()` without a bump.
   - It refuses, with epoch 0, if the glue's health flag is false or the live owner_errors is nonzero. owner_errors
     is read before and after the epoch.
   - An ordinary new capture therefore leaves an owned pending or displayed frame alive (fixture N).
3. **Cancel, reset, savestate, foreign calls, an invalid capture, external writes and unexpected GP1 still
   invalidate.**
   - On the owner thread, `invalidate_all(L, why)` retires every record and bumps the r4 epoch.
   - A foreign thread can only call `L.invalidate()`. The gate fails at once through r4, and the owner retires the
     records (T2R_EPOCH) at its next `boundary()`.
   - `observe_scanout()` bumps the epoch itself on every unexpected change, including the first observation.
4. **The present candidate stays bound until its flip or retirement, never overwritten by the latest capture.**
   - `PresentState`, owned by the emulation thread, holds one PENDING record and one DISPLAYED record.
   - `bind()` refuses with T2B_PENDING_BUSY while a candidate is pending.
   - Only the pending candidate's exact target, as the first change after its boundary, is the expected flip. That
     flip moves pending to displayed and retires the previous displayed frame (T2R_SUPERSEDED).
5. **Exact frame, generation, target and completion are required.** The gate requires all of:
   - the r4 gate;
   - a displayed record with the frame's serial, frame, generation, epoch, boundary generation and target;
   - flip generation == boundary + 1;
   - the current scanout generation equal to the flip generation;
   - the current state equal to the target;
   - a completion carrying that serial, scanout generation and state.
6. **Bounded stale and abandoned rules.**
   - A pending candidate retires (T2R_ABANDONED) at the second boundary after its bind with no flip
     (`kMaxPendingBoundaries = 1`).
   - A displayed frame retires (T2R_STALE) at its third boundary with no next flip (`kMaxDisplayedBoundaries = 2`).
   - A late flip of a retired candidate is unexpected and bumps the epoch.
   - Both bounds are conservative constants that the glue has to confirm against the real seal cadence.
7. **Front-buffer writes.**
   - `note_write(rect, footprint_known)` covers every native GP0 draw, fill, copy and upload, and every external
     direct write. A known footprint (a VRAM halfword rect: non-empty, non-wrapping, inside 1024x512) retires each
     record whose target rect it overlaps.
   - This applies to the pending record too: its sealed buffer changing before the flip retires it.
   - An unknown, wrapping or out-of-range footprint retires everything.
   - `set_reference_mode(true)` retires everything and refuses binds (T2B_REFERENCE) until it is turned off.
8. **No relaxed hazard gates.** r4 provenance, epoch, owner_errors and VRAM policy, and the display-hazard hook, are
   all still required. The scan checks are r5's, plus a VRAM-bounds check on the target rect.

## Concurrency

- Owner-only state is the snapshot `cur_`, the first-observation flag and the serial counter.
- Readers get a consistent `PresentSnapshot` (248 bytes, static_assert'ed with no padding) through a seqlock over 62
  atomic words: Boehm's fence pattern, 64 attempts, and a failed read refuses.
- The gate reads the r4 atomics and then one snapshot. As in r4, the gate check is the linearization point.

## Fixture coverage (50 checks, each executed once; prim()/vert() byte-identical to test_t2.r3.cpp 215df688 :28-66)

| Group | Covered |
|---|---|
| N | The first observation is unexpected and bumps the epoch. capture_begin does not bump, and refuses when unhealthy. Build and bind of N into B: serial 1, pending, hazard hook arguments. Before the flip: no completion and no flip both refuse. A next capture begin before the flip leaves the pending record intact. The expected flip allows with no epoch bump. A same-value rewrite changes nothing. N+1 binds while N is still allowed. N+1's flip allows N+1, retires N (superseded) and refuses N. |
| S | Each of these refuses: N's completion presented for N+1, a wrong serial, an older scanout generation, another scanout state. |
| P | A later capture cannot overwrite the pending candidate (PENDING_BUSY), and the displayed frame survives meanwhile. A third boundary abandons the pending and stales the displayed. A late flip after that is unexpected. Separate cases for stale only and abandoned only. |
| F | Each of these refuses: a late flip after an allow; depth, range or disable changes at the flip (pending retired, epoch bumped); owner `invalidate_all`; a foreign-thread `L.invalidate()` (gate refuses at once, owner retires T2R_EPOCH at the boundary); `arm_epoch()`; `note_foreign()`, which also makes capture_begin refuse. |
| W | A back-buffer write keeps the displayed frame; a front write retires it with no epoch bump. A write into the pending target before the flip retires it, so the flip becomes unexpected. Unknown and wrapping footprints retire everything. Reference mode refuses the gate and binds; binding works again after it is turned off. |
| D | Bind refusals: NOT_CANDIDATE (single buffer), SCANOUT_MOVED (wrong boundary generation), NOT_LIVE (invalidated between build and bind). |
| B | Build refusals: DRAW_AREA_VARIED, TARGET_NOT_BUFFER, TARGET_STATE, TARGET_DISABLED, RECT (empty), RECT (outside VRAM), PRIM_AREA, HAZARD (verdict 6), HAZARD_MISSING, NOT_LIVE (r4 PR_POLICY). |
| K | Seqlock smoke test, not a memory-model proof. One writer thread makes 5000 unexpected changes between all-word-distinct X and Y; one reader thread checks state/generation parity, empty records and monotonic generations. Final check: (X, 5001) and epoch 5002. |

## Open items for root (not implemented)

- **Glue r3**, which is still to be written. It must:
  - call `observe_scanout` from the gpu.c GP1 hook in place of r2's conservative invalidation;
  - call `boundary` at each seal before build and bind;
  - call `note_write` on every VRAM write path with its footprint;
  - call `invalidate_all` at cancel, reset, savestate and invalid capture;
  - use `capture_begin` instead of `scene_t2_arm_epoch`;
  - add transport for T2FrameR6, and the consumer stamping of CompletionR6 from a snapshot taken at composition.
- **Ledger r1** `scene_ledger_display_hazard` for the hazard hook.
- **Display-rect computation** for 24-bit and interlaced modes, in halfwords.
- **Merge rule** (msg_31e3312e): any glue merge must compare the current v68/37c GPU and runtime parents first and
  must never replace them blindly with the older v66 copies.

## Run request (only after root's full review AND a fresh grant naming the CPU; one attempt, no retry)

O = `C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary`.

1. Copy the envelope to `O/remix-transport/t2r6-run1-runner/executed-watchdog.py` and verify fa5e42fa.
2. Set OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1.
3. Run:

```
C:/Python314/python.exe -I -B O/remix-transport/t2r6-run1-runner/executed-watchdog.py --out O/remix-transport/t2r6-run1-envelope.json --cpu N --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B O/remix-transport/t2/r6/build_t2_fixture.r6.py --cpu N --out-root O/remix-transport/t2r6-run1
```

## Not claimed

- Compile success.
- Composition validity.
- Interop image content.
- G4 material identity.
- Glue r3 and ledger r1.
- Any live suppression or Stage 1 progress beyond source.
