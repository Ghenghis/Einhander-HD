# Glue r2 CPU build closure r0 (claude-einhander), written 2026-11-14 ~23:26Z

**Status: SOURCE-ONLY PROPOSAL, for root's review.** Nothing here has been compiled or run. Root cleared the frozen
glue r2 source for a CPU compile and fixture *proposal* only (msg_31e3312e): no live adoption, no merge. Glue r2 is
unchanged and read-only:

| File | sha256 |
|---|---|
| `gpu.c` | de9dfd77 |
| `scene_runtime.cpp` | 3bbc6821 |
| `scene_runtime.h` | 730b5b4f |
| `scene_t2_bridge.r2.cpp` | a88b6911 |
| `scene_t2_bridge.r2.h` | c6a59759 |

## Files (this folder)

| File | sha256 |
|---|---|
| `test_glue.r0.cpp` (fixture glue, revision r0, 28 authored checks, none in loops or helpers) | 7cce4f6b163ec606296b9e3cb03e45cae56ba3058c85d4414062e13abbde5f3c |
| `build_glue_fixture.r0.py` | 70592507cfd3aab0198aea781dda160d3dfd2ce9951d19c92c098c69aa868730 |

The driver's lines 77-271 are a byte copy of `build_t2_fixture.r4.py` (7b39f6a4) lines 77-271, checked with diff.
They cover sha, now, the BLOCKS and TEMPLATE, lf_lines, native_block, divide_block, derive_pgxp, write_exact and
run_child.

## Parents (msg_31e3312e: compare the current parents before any later merge)

- **v68:** `sampling-build-v68-recorder-reserve-r1/build.json` (21944d69) links the v66-r3 objects unchanged, so the
  glue r2 bases ARE the v68 parents of these TUs:
  - `gpu.c.obj` (:130);
  - `scene_capture.cpp.obj` (:718);
  - `scene_json.cpp.obj` (:722);
  - `scene_runtime.cpp.obj` (:726);
  - and v61's `gte.cpp.obj` (:314).

  The v68 `src/` folder carries copies of `scene_runtime.h` (6ddedc78) and `scene_capture.h` (b90ebe9d) equal to
  v66-r3. Both builds use the same `include/pgxp.h` 1f50599f.
- **"37c":** I was not given its GPU or runtime paths, so it is **not compared**. Before any merge root has to supply
  them; the closure would then be re-pinned against them. Nothing is replaced blindly with a v66 copy.

## What the driver proves (when run)

1. **Pins.** Every input is checked against a raw sha256 before use and read once:
   - the frozen glue r2 files;
   - the v66-r3 bases;
   - the 23 `include/*.h` headers that `gpu.c.obj.d` lists;
   - the native capture TUs (scene_capture.cpp 78c4158d, scene_json.cpp 4305f17e);
   - ledger r0;
   - the T2 closure;
   - the harness.

   Every executed copy is re-hashed. The ledger `.inc` is generated from the raw-pinned v66-r3 BLOCKS, and the
   divide block is cfa7686a.
2. **`compile-gpu-base` and `compile-gpu-patched`.** Each compiles a `gpu.c` next to its own `scene_runtime.h`
   (v66-r3 6ddedc78 for the base, glue r2 730b5b4f plus ledger r0 for the patched copy). Both compile as C with the
   exact 22 native defines and `-O3 -DNDEBUG -fzero-initialized-in-bss` from v66-r3 `build.json` compile-gpu.c,
   against raw headers and no warning flags, as natively.
   - The base compile is the control: it shows the reduced include set reproduces the native closure.
   - The objects are hashed, but neither linked nor run.
3. **Native capture TUs.** `scene_capture.cpp` and `scene_json.cpp` compile with the native C++ defines and flags
   (`-std=gnu++17`, raw pgxp.h).
4. **Strict TUs.** Ledger r0, glue r2 `scene_runtime.cpp`, `scene_t2_bridge.r2.cpp` and the harness compile under
   `-std=c++17 -Wall -Wextra -Werror` with the DERIVED pgxp.h (50a6ef6d), as root's comment-only pgxp rule requires.
   - Risk: `scene_runtime.cpp` keeps native-origin lines that were never built with warnings. A `-Werror` failure
     would be a preserved, reportable finding, not a retry.
5. **Hermeticity.** Every compile writes `-MD -MF`, and a step passes only if every dependency resolves inside this
   run's output folder or the pinned toolchain root. The toolchain root is checked both as invoked (`latest`) and
   as its real path (junction to `AppData/Local/retcomm/toolchains/cmake-clang-v1/.staging-host`, verified with
   Get-Item). No header may come from the repository, VulkanSDK or `deps/`.
   - The native `-I` directories outside v66-r3 are omitted because the native `.obj.d` files show that none of
     their headers is used.
6. **Link and `run-glue`.** The link uses capture, json, ledger, runtime, bridge and harness. `gpu.c` is not linked:
   `gpu_scene_gp0_open` and `gpu_scene_scanout_state` are faked, as are the five PGXP / GTE-ring functions the runtime
   binds, and every lookup misses. The driver sets `PSXRECOMP_SCENE_CAPTURE=1` for the run child only.

## Fixture coverage (28 authored checks)

| Group | Checks |
|---|---|
| O | The first call binds this thread as the owner. Epoch 1, owner_errors 0, no armed epoch. |
| A | Arm returns SCENE_OK, binds armed epoch 2 (r4 `arm_epoch` bump) and the ledger is ARMED with capture generation 1. |
| S | Under the conservative GP1 rule, the arm snapshot means no change. A moved start bumps the epoch, so the bound frame goes stale. A same-value rewrite changes nothing. A mode bit alone bumps. A null pointer is ignored. |
| N | `scene_t2_build` refuses a null ledger, zero capacity, a null output, and an armed but unsealed capture. Each case is explicit native (PR_CAPTURE, unbound, not live-eligible). The owner getter refuses an unsealed capture. |
| E | An empty sealed interval (ticks 6 and 7) is SEALED, complete, has 0 records and generation 1. The build is explicit native because there are zero records. The getter refuses when index >= count, and the JSON read-side fails and empties its buffer. |
| L | An external VRAM write bumps the epoch. Cancel bumps it and clears the armed epoch. Re-arm binds a new epoch. Owner invalidate bumps the epoch, clears the armed epoch and leaves the capture IDLE at generation 2. |
| F | Each foreign-thread call is reported: enabled returns 0, a foreign invalidate still bumps the epoch, arm returns WRONG_THREAD, and armed_epoch reads 0. Each raises T2 owner_errors and the epoch, and the runtime's own counter reaches 4. The owner can still arm and seal, but the bridge then refuses with PR_OWNER_ERRORS. |

Not covered: a capture with transported primitives (that needs real PGXP views), the GP1 hook inside `gpu.c` (only
compiled), the ledger policy verdicts (ledger r0 integ already covers them), and T2 r6 integration (glue r3).

## Run request (only after root's review AND a fresh grant naming the CPU; one attempt, no retry)

O = `C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary`.

1. Copy the envelope to `O/remix-transport/glue-r2-build-run1-runner/executed-watchdog.py` and verify fa5e42fa.
2. Set OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1.
3. Run:

```
C:/Python314/python.exe -I -B O/remix-transport/glue-r2-build-run1-runner/executed-watchdog.py --out O/remix-transport/glue-r2-build-run1-envelope.json --cpu N --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B O/remix-transport/capture/ledger-glue-r2-build/build_glue_fixture.r0.py --cpu N --out-root O/remix-transport/glue-r2-build-run1
```

The v66-r3 build recorded these compile times: gpu.c 0.98 s, scene_runtime.cpp 1.12 s, scene_capture.cpp 0.34 s.
Each step here is capped at 45 s, the run at 10 s, and the envelope at 120 s.

## Not claimed

- Compile or link success.
- Live adoption, merge or install.
- Any GP1 handoff (T2 r6 is not wired: glue r3).
- Parity with "37c".
- GPU, game, GL or SDK work.
- Stage or project completion.
