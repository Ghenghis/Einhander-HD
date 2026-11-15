# Glue r3 build closures r2 and r3, fixture r2 (claude-einhander), written 2026-11-15 ~00:33Z

**Status: SOURCE-ONLY PROPOSAL.** Nothing here has been compiled, linked or run. No Python was executed either, not
even a syntax check, because every executable run needs a grant. **No native output is suppressed** anywhere.

This is GLUE-R3-SOURCE step 3, per root msg_b02d1bcc, msg_08008ad5, msg_2fe98abb and the review msg_b1a99057.

Preserved unchanged:
- glue r3 (`../ledger-glue-r3/`);
- harness r1 44ab03a6;
- closure r1 8c7bbfb8;
- closure r2 (below), which was **frozen before root's review and never run**;
- T2 r3, r4 and r6;
- ledgers r0 to r3;
- the 37c and v68 parents.

**The grant request targets closure r3 only.** Closure r2 is superseded and must not be run.

## Files

| File | sha256 |
|---|---|
| `../ledger-glue-r3-build/build_glue_fixture.r2.py` (closure r2, superseded) | b057695aa257b9e7167f6610b6af20b6fe5c92297e4c9cb4e597fc5304f3e86a |
| `../ledger-glue-r3-build/build_glue_fixture.r1-to-r2.diff` | 355c51b30f913ca6874030a6eee2aaea750e773936747be1a7b00d703be3e08a |
| `test_glue.r2.cpp` (fixture glue, revision r2, 19 authored checks) | 3ec929d534be51104cd368f05c236db8bcf67837440e5db381046f3f42b15e4b |
| `test_glue.r1-to-r2.diff` | 7f4ac03011e1aa35b9be8e70dee69135ca868e08c3c7f894f6ea33be9219bd72 |
| `build_glue_fixture.r3.py` (closure r3) | 11c26259ac40c3db1d9cba06d90e5fd6f54629e90dd0279a05fec6904921157c |
| `build_glue_fixture.r2-to-r3.diff` | d30f18bb6f60f76e3ff5b51c36a7844a63e78c426460cbb79dddafd9cf9c1956 |

## Closure r2: closure r1 retargeted to glue r3

Only pins, paths and names change; the logic is closure r1's. The changes are:
- the glue r3 `scene_runtime.cpp` / `.h` (b0d820a7 / 6c69adcb) and `scene_t2_bridge.r3.cpp` / `.h`
  (5182d80d / f09f3296);
- ledger r3 `scene_ledger.r3.h` / `.cpp` (9a0af4a9 / 23499310) in place of ledger r0, with `scene_ledger_t2.r0.h`
  94bc9c24 kept;
- T2 r6 `remix_t2.r6.h` 419dea94 added to the strict closure;
- harness r1 (19 checks, revision r1);
- gpu.c stays the glue r2 de9dfd77. `compile-gpu-patched` and `compile-debug-patched` now see `scene_runtime.h` r3
  and `scene_ledger.r3.h`.

The native/strict split, the raw pins, the hermetic roots, the v69 toolchain-closure equality and
`PSXRECOMP_SCENE_CAPTURE=1` (for run-glue only) are all closure r1's.

## Fixture r2 (root msg_b1a99057)

The 19 `CHECK` lines are byte-identical to r1 (checked with diff), and so is every scenario step. The diff removes 5
lines (the usage line, the CHECK macro and the two JSON writers) and adds 109.

1. **`stamp(nullptr)` returns an all-zero `CompletionR6`** and never dereferences a failed take. In r1, `stamp(f)`,
   `stamp(f3)` and `stamp(f5)` dereferenced the frame; a producer refusal would have crashed and lost the summary.
   The CHECK before each stamp already records the failed take. `scene_t2_gate` (returns false) and
   `scene_t2_release` (ignores the pointer) are already null-safe in bridge r3 5182d80d, lines 231-241.
2. **Diagnosis without a blind rerun:**
   - the first 32 failing CHECK line numbers;
   - one read-only snapshot after each group L/O/M/Q/P/R/F, holding:
     - the checks and failures so far;
     - the full `SceneT2Audit`: seals, invalid_seals, built, bound, published, busy, refused_scanout,
       `last_invalid` bits, `last_scan_reason`, `last_bind_reason`;
     - the epoch, owner errors and armed epoch;
     - the PresentState snapshot: scanout generation and words, the retired serial, reference mode, the last
       retire reason, and the pending and displayed records with their targets and rects;
   - the final audit.

   The snapshots run on the owner thread only, so the runtime `guard()` has no side effect (`scene_runtime.cpp` r3
   lines 54-64). Nothing in them is asserted or counted. 64-bit values are written without a printf length
   modifier.

## Closure r3: closure r2 plus fixture r2

- The harness pin is now `test_glue.r2.cpp` 3ec929d5 (this folder), and the expected fixture revision is "r2" with
  the same 19 checks.
- **run-glue always parses and attaches the fixture JSON** to `result.json`, even when the executable exits
  non-zero. In closures r0-r2, a failing exit returned before parsing. The step passes only if the exit is 0 **and**
  the fixture JSON passes. `exit_passed` records the exit verdict separately.

## Read-only checks I ran before freezing

- **sha256 of every input** listed above and in the glue r3 doc 23a49f1c. All equal their pins.
- **The inherited byte copy of T2 r4 driver 7b39f6a4 lines 77-271** is identical by diff in r2 (lines 230-424) and
  in r3 (lines 239-433).
- **The native unpack `BLOCKS`/`TEMPLATE`** in r2 and r3 equal ledger r3 driver f08a5a2e lines 84-176 by diff.
- **Every `data[...]` key** used by r2 and r3 is present in `INPUTS`.
- **The include sets of the strict TUs** (bridge r3, runtime r3, ledger r3, harness r2) are all provided in
  `strict/`. `scene_ledger.r3.h` is C-compatible (`extern "C"`, no references); the C compiles of gpu.c and
  debug_server.c include it.
- **Fixture r2 has 19 CHECKs**, and their lines equal r1's by diff.

**Not checked:** the Python syntax, any compile, link or run. These need a grant.

## Consumer API contract (documented; NOT enforced, no public handle contract yet)

The bridge r3 consumer API is a raw pointer into a private pool of 4 immutable frames. It is valid only under these
rules, which the fixture follows:
1. **Owned taken frames only.** Gate, read and release only a pointer that `scene_t2_take()` returned to you.
2. **Gate before release.** After `scene_t2_release()`, the slot may be rebuilt, so never read or gate it again.
3. **Release exactly once.** A repeated release is harmless only while the slot stays FREE. Once the producer
   republishes the slot and a consumer takes it again, a stale release would free a frame that is in use.
4. **One consumer.** `take()` is an exchange, so only one caller receives a frame.

`scene_t2_gate` accepts any non-null pointer: it does not check that the pointer is a currently TAKEN pool slot. A
stale or foreign pointer is therefore undefined use, not a refused gate. A general, public, checked handle (for
example slot plus serial plus a TAKEN check) is future work and is not claimed here.

## Integration gaps (recorded per root; not addressed by this revision)

- **Arming is driven explicitly** by the caller (the fixture, or a future controller). There is no continuous opt-in
  per-frame capture, and no backpressure or interval scheduling. Arming at a seal records the interval after next.
- **No consumer is attached:** no SDK or G4 material-identity consumer, no compositor, no Remix or RT path. RT is not
  enabled, and nothing suppresses native output.
- **Not qualified:** composition, G4 and live suppression.

## Grant request (one attempt, no retry)

One below-normal, single-CPU job, using a fresh exclusive runner directory with a verified copy of the envelope
fa5e42fa:

```
C:/Python314/python.exe -I -B <runner>/executed-watchdog.py --out <receipt> --cpu N --timeout 120 --max-job-mib 1024
  --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B
  <O>/remix-transport/capture/ledger-glue-r3-build-r3/build_glue_fixture.r3.py --cpu N
  --out-root <O>/remix-transport/capture/glue-r3-closure-r3-run1
```

The job makes 10 compiles (two gpu.c and two debug_server.c at -O3), 1 link and 1 run, each child capped at 45 s
(run 10 s). **The envelope's 120 s total may be tight.** If it is exceeded, the run fails and is preserved, with no
retry, and I would ask for a new ruling. It uses no GPU, game, SDK, ComfyUI or Remix.
