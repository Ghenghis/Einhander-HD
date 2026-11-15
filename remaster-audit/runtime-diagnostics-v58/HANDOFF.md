# v58 frame phase ring — source freeze r2 (claude-einhander)

Private diagnostic A for the remaining live pause. Source only: no build, game, install or git write by Claude.
Root owns build, live runs and publication.

## Changed sources (target `windows-x64/psxrecomp/runtime/src/`)

| file | base (exact) | base sha256 | new sha256 |
|---|---|---|---|
| main.cpp | `C:/github/Einhander-wt/upload-index-hitch/.../src/main.cpp` (git b1b981b, clean; the v57 runtime-main.cpp.obj source) | f4ecc89c69b394ca3c334fdfd54958bf496f5573c03a54c5c79cb96892c67b9c | 5c94d2dd17f52338515ac52df4f8fde04b4eb269ee49ba6bc42b6924bc6523c0 |
| gpu_gl_renderer.c | `native-upload-stream/new/gpu_gl_renderer.c` (v57) | 4a19590b0a80e9431eb116af321367e9eef1532e2fadea12f9e5e6bcd1e7dbc8 | 90c6a4e15d8e956ca7be28f1cd5219add1e1c2ee37f31fbd361711db0510e3a1 |
| debug_server.c | `native-upload-stream/new/debug_server.c` (v57) | 5365caa1d464d99183d10e6fb971ac07a201e0c0c9280789559dcc81d66e4640 | 3217e4d7da546c6a… (full hash in patch-receipt.json) |
| frame_phase_ring.h | new file | — | c307ae7f0937521106af9f7ebc511de10fbc23d49a55dcc77f2f22994492eef7 |

Unchanged: native_upload_ledger.h 72150915… (copied into new/ only for include resolution), latency_ring.c 7d32ad67…
(reuse its build-ss8c object 33c0cc9e…). Every other link input is as pinned by root.
Exact hashes, diff hashes and CRLF state: `patch-receipt.json`. Unified diffs: `diffs/`. Patched files: `new/`.

r1 → r2: the r1 `static FramePhaseRecord s_fp_ring` collided with the existing fingerprint ring `FpEntry s_fp_ring[32768]`
(root full-TU build; also my r1 syntax check, preserved as `syntax-check-r1-collision.json` with
`patch-receipt-r1-collision.json`). All phase-ring state is now `s_fpr_*`. The ring array also takes `PSX_BSS`, the house
rule for large rings, so its ~1.5 MiB stays RAM-only. main.cpp, gpu_gl_renderer.c and the header are byte-identical to r1.

## Compile lineage
- main.cpp: the v47 compile-runtime-main argv, with runtime paths remapped to the upload-index-hitch worktree and its
  `runtime/include` and `runtime/src` prepended (the v48 build.py rule). frame_phase_ring.h must sit next to main.cpp in the
  build source dir, or be put on an `-I`.
- gpu_gl_renderer.c, debug_server.c: the v54/v57 compile-debug_server.c flags (the template the v57 check used).

## What it records
Opt-in only, with `PSX_FRAME_PHASE_RING` set to exactly `1`; otherwise every mark is one thread-local read, and the renderer hook
stays NULL. Each row is one `sdl_vblank_present()` cycle. It holds raw QPC stamps (0 = absent):
- enter: literally the first statement of the body
- debug_end: after the watchpoints; the frame is committed here as `s_frame_count`
- pace_begin / pace_end: around the offline wall pacer, which runs before the swap
- swap_begin / swap_end: around the exact `SDL_GL_SwapWindow` inside `gl_swap_with_osd`, which every GL present goes through. On the software renderer, around `SDL_RenderPresent`.
- alt_pace_begin / alt_pace_end: turbo, turbo-loads and netplay-epilogue pacers. These are stamped and flagged only.
- exit: before each of the 4 early returns and at the end. These are explicit calls, with no RAII, because of the longjmp paths.

No GL calls, queries, fences or readbacks, and no threads.

Thread scope: `debug_server_frame_phase_init_owner()` runs right after `debug_server_init`, before the hook is registered. It binds
the main thread as the only writer. A mark from any other thread returns after a thread-local read, with no shared access and no count.
Supported measurement scope: offline, `PSX_FRAME_INTERPOLATION=0`, netplay off.

## Query (after timing)
`{"cmd":"frame_phase_ring","from_seq":S,"n":N}`, where n is 1..2048. Optional `from_frame` / `to_frame` filter on `frame`.
Page with `next_seq`. `truncated` 1 means more rows remain. Capacity is 16384 rows. `first_seq`/`retained` show eviction.
`last_open` may be 0 or 1. During gameplay the handler runs inside `debug_server_poll`, between enter and debug_end, so the
newest row is usually the open current cycle. The debug server also answers outside an open cycle, though: the r1 title reply had
`last_open` 0. Exclude any open row, and never require `last_open` to equal 1. The frozen header and handler comments say
"1 is expected", which overstates this. The source is left unchanged to keep the frozen hashes. Precise rows are CLOSED, without UNCLOSED, MULTI_SWAP or MULTI_ALT. In-scope rows
also have no ALT_PACE. `derive_phases.py` computes these offline segments:
outside_vblank (guest plus other work), housekeeping, pre_pace, pace, present_prep, swap, post.

## Checks (actual)
- `host-test.json` (05c9e3f6…): **PASS**. It tests the ACTUAL extracted ring and query handler text from new/debug_server.c (142 lines), at below-normal priority on a fake QPC clock:
  - CAP=8 build:
    - ordered stamps and frame mapping (`frame` committed after housekeeping, `frame_at_enter` and `frame_at_swap` kept)
    - first stamp wins
    - MULTI_SWAP / ALT_PACE / MULTI_ALT flags
    - owner-thread orphans, plus the invalid-phase orphan check
    - UNCLOSED after a missing EXIT
    - a foreign thread during an open cycle changes no row, total, counter or open state
    - the open row at query time is reported with `last_open` 1
    - wrap and eviction
    - paging with `truncated` / `next_seq`, `from_seq` clamped to `first_seq`, and the frame filter
    - max-width values fitting the row budget
    - offline segments from `derive_phases.py` (exact tick values, precise/in-scope exclusions)
  - Disabled and unbound modes record nothing.
  - Default CAP 16384: eviction at the real boundary, plus a 2048-row page with `truncated`.
  - 9 of 9 mutants caught: index, wrap bound, truncation flag, row budget, owner guard, first-wins, UNCLOSED flag, multi-swap, frame filter.
  - Symbol pre-check:
    - The 14 file-scope declarations the patch introduces match a fixed list.
    - There are 0 collisions against the exact bases of all 3 TUs for those 14 names, the header names, the renderer hook and the main macro.
    - The control (r1 naming) still detects `debug_server.c:s_fp_ring`.
    - The r2-run scanner false positive is preserved as `host-test-r2-scanner-false-positive.json`: it counted locals and call sites. The full-TU compiler remains the authoritative gate.
- `syntax-check.json` (r2, debug_server.c only, because it is the only TU that changed): original exit 0, patched exit 0, 0 new diagnostics
  under build flags and under -Wall -Wextra. main.cpp and gpu_gl_renderer.c are byte-identical to r1, which had original 0 / patched 0 / 0 new
  diagnostics, both flavors (`syntax-check-r1-collision.json`). Clang ran sequentially at below-normal priority, with no objects and no link.
- Root's private full build `sampling-build-v58-frame-phases` (exe c2c386bd…) lists exactly these 4 new source hashes in its
  build.json (checked read-only).

## Verification manifest
`verification-manifest.json` (built by `make_verification_manifest.py`; it reruns nothing) binds:
- the frozen sources, their bases and diffs to both receipts;
- root's build copies, build.json and exe c2c386bd;
- the exact extracted block both host-test builds compiled, the test driver, the runner (mutant list and symbol fixture) and derive_phases.py;
- every report, including the preserved r1-collision and r2 scanner false-positive records, and the r1 live attempt.
All cross-checks pass (`all_checks_pass` true).

## Live attempts (actual)
- `display58-phases-pbo-on-r1`: **REJECTED**, with no performance verdict.
  - The title GPU self-test and phase API gates passed. Focus was 1/1 at the foreground handoff (04:47:01.9Z).
  - Three timed observations covered frames 3925 to 4044 (about 2 s). The next sample lost SDL focus, and the `require_foreground` gate rejected timing.
  - The owned game exited 0 with its port closed. Proof sha256 65de296e9838a79182ab52f37f38e59129dce4e1ac8c45109b09dd6a64e20767.
  - Claude made no tool calls between 04:46:45Z and 04:47:58Z, which spans the focus drop.
- `display58-phases-observed-r2` (`observe_only` focus policy, same exe): prepared by root, not launched. It is cancelled pending the
  Codex-to-Claude handoff. The user asked to "try again".

## Limits
- outside_vblank is guest execution plus anything else between vblank callbacks, not pure emulation.
- The software-renderer marks are syntax-checked only. The live path is GL.
- These are host and syntax checks only. Live behaviour and overhead are unmeasured until root's run.
