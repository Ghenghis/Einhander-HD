# Glue r2 CPU build closure r1 (claude-einhander), written 2026-11-14 ~23:54Z

**Status: SOURCE-ONLY PROPOSAL.** Nothing here has been compiled or run, and no heavy build happens during the
coordinator's quiet period. It follows root msg_75dee0c2: compile-check the `scene_runtime.h` consumer against the
actual v69 source and depfile, not only the older v66 debug source. Build closure r0 (`../ledger-glue-r2-build/`,
driver 70592507, harness 7cce4f6b) is preserved unchanged. r1 reuses r0's harness by path and pin.

## Files (this folder)

| File | sha256 |
|---|---|
| `build_glue_fixture.r1.py` | 8c7bbfb8dad37e3aefe206b1a66052f9f5574f15f8a65c6e025e3e7db55ca4c1 |
| `build_glue_fixture.r0-to-r1.diff` | c0aa5cb870ba9c84209a1dc068215ccfe7d863c15dfbaf11e5a1cd697a5ebc01 |

The diff changes 3 lines and adds 141. The 3 changed lines are the docstring title, the harness path (now the r0
folder) and the `dirs` tuple. The inherited byte copy of T2 r4 driver lines 77-271 is still identical by diff.

## Lineage (read-only checks run before writing)

- **The 37c retained table:**
  - `C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/proposals/p1-player-color/build/retained-inputs.v69.tsv`
  - sha256 d9eb77e0…, 155 rows.
  - Row 25 is v69 `debug_server.c.obj` dc75afc2.
  - Rows 7 and 153-155 are the v66-r3 gpu, capture, json and runtime objects, which I already traced in
    `../ledger-glue-r2-parents/` (269b354f).
- **The v69 debug build:**
  - `parallel-stages-20261114/s67/runs/v69-build-2206/manifest.json` e6ab30e9…, entry `build.debug`.
  - obj dc75afc2 and depfile 939b9cd1, both equal on disk.
  - Its closure has 403 entries: the source `debug_server.c` b50aef2a (equal on disk), **56 project headers** under
    `sampling-build-v67-decode-identity-r3/include|src`, and 346 toolchain headers, 60 of them SDL3 under
    `latest/deps/include`.
  - All 56 project headers equal their recorded hashes today (0 mismatches). The basenames are unique.
- **The consumer saw the glue r2 base header:** v67 `src/scene_runtime.h` = **6ddedc78**, the same base glue r2
  patched. `scene_capture.h` is b90ebe9d and `pgxp.h` is 1f50599f.

## What r1 adds (when run)

1. **Pins.** v69 `debug_server.c` b50aef2a, the v69 manifest e6ab30e9, and the 56 headers, each pinned to the
   manifest's recorded hash.
2. **Pre-checks.** The driver re-parses the manifest and requires:
   - `build.debug` `obj_sha256` and `depfile_sha256` equal the pins;
   - every pinned header is recorded under its v67 path with that same hash;
   - the consumer's `scene_runtime.h` and `scene_capture.h` equal the glue r2 base (6ddedc78, b90ebe9d).
3. **`compile-debug-base`** compiles v69 `debug_server.c` with its 56 raw headers (base `scene_runtime.h`). It uses
   the exact v69 `build:debug` defines, `-O3 -DNDEBUG -fzero-initialized-in-bss` and
   `-isystem latest/deps/include`, as C, with no warning flags. The pinned header set is the only `-I` directory,
   because the v69 `.d` shows that no header came from the other native directories.
4. **`compile-debug-patched`** is the same compile with glue r2 `scene_runtime.h` 730b5b4f plus ledger r0
   `scene_ledger.r0.h` 220d1a5e.
5. **Checks on both.**
   - Exit 0.
   - r0's hermetic dependency check: every dependency lies under the run folder or the toolchain root.
   - **New:** every toolchain dependency (sysroot, clang resource headers, SDL3) must appear in the recorded v69
     `build.debug` closure with an IDENTICAL sha256. This fails on any unrecorded or changed toolchain header.
   - `equals_v69_object` compares the base object with dc75afc2. It is information only: an embedded path such as
     `__FILE__` may differ.
   - Neither object is linked or run.
6. **Everything in r0 is unchanged:** the gpu.c base/patched compiles, the native capture/json TUs, the strict
   ledger/runtime/bridge/harness TUs, the link, and `run-glue` (28 authored checks).

## Run request (only after root's review AND a fresh grant naming the CPU; one attempt, no retry)

O = `C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary`.

1. Copy the envelope to `O/remix-transport/glue-r2-build-r1-run1-runner/executed-watchdog.py` and verify fa5e42fa.
2. Set OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1.
3. Run:

```
C:/Python314/python.exe -I -B O/remix-transport/glue-r2-build-r1-run1-runner/executed-watchdog.py --out O/remix-transport/glue-r2-build-r1-run1-envelope.json --cpu N --timeout 120 --max-job-mib 1024 --no-window --max-cpu 60 --min-free-gib 16 -- C:/Python314/python.exe -I -B O/remix-transport/capture/ledger-glue-r2-build-r1/build_glue_fixture.r1.py --cpu N --out-root O/remix-transport/glue-r2-build-r1-run1
```

Expected cost:
- v69 recorded 2.7 s for the debug compile, and v66-r3 under 1.2 s for each other TU.
- There are 10 compiles, a link and a run, each step capped at 45 s, all inside the 120 s envelope.

If root prefers to run r0 first (r0 is a strict subset), r1 stays valid unchanged.

## Not claimed

- Compile success.
- A merge.
- Other `scene_runtime.h` consumers beyond the 37c set root named.
- Live adoption.
- GPU, game, GL or SDK work.
- Stage or project completion.
