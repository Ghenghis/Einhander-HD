# Combined audio telemetry proposal: gap counters + single-lock getter + pump snapshot (source only)

Requested by main in msg_7e92b15d71c03b60. Owner `claude-einhander-s67`.

**Status:** nothing has been applied, compiled or run. **No claim** is made that the race is fixed, that audio sounds better, or that performance improves. Those claims need a compile, integration and qualification with real SDL.

**Parents are unchanged and only read:** `../audio-gap-counter/*` (r1–r3) and `../audio-stats-snapshot/*` (r1–r2). Each file here is generated from the **pinned gap-proposal file** (`*.proposed`), and a diff is given against both that parent and the original v68 source.

| file | parent (pinned) | original v68 source (pinned) |
|---|---|---|
| `recomp_audio_drc.h.proposed` | gap header `7de21fb8aac0f442bf50b0259257b4768480c89b21ce8aeba6753339f1f371c9` | canonical/v68 `70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29` |
| `main.cpp.proposed` | gap main `2b5ec71825dd627d88f6018667e2e264d9844953994f10d94ee93c6af2dc6068` | v58 `5c94d2dd17f52338515ac52df4f8fde04b4eb269ee49ba6bc42b6924bc6523c0` |
| `debug_server.c.proposed` | gap debug `2d54ae68c5762b7661faac3713307118ba777d91d8ecd266c2300c2d3c38a25f` | v67 `10e31f8dc50cdf451776f18e4b468f95bb2c97d33f50816d9b9d193557af2eba` |

## What changes beyond the gap parent
1. **One coherent snapshot (header).**
   - New plain-C `rab_telemetry { rab_stats stats; rab_gap_stats gap; uint64_t gap_epoch; }` and `rab_get_telemetry()`. The caller holds the lock that guards `rab_pull`.
   - `rab_stats`, `rab_get_stats` and the rest of the gap API are unchanged, so the old ABI holds.
2. **Getters (main.cpp, between the `s67 combined getters: BEGIN/END` markers).**
   - `s67_audio_out_snapshot` takes **one** lock and makes one `rab_get_telemetry` copy. If no device is open, it copies unlocked: there is no audio thread then.
   - `psx_audio_out_stats_ex(...)` returns the old seven outputs plus gaps, max, cur, epoch, `bridge_generation` and `gap_ok`. Its legacy and not-ready branch is byte-identical in behaviour to the old one.
   - `psx_audio_out_stats` keeps its old signature and return values and is now a wrapper over `_ex`. Its two callers are unchanged.
   - `psx_audio_out_gap_stats` is kept for compatibility, over the same snapshot.
3. **debug_server `audio_stats`.**
   - It calls `_ex`, so `out.*` and the gap fields come from **one** lock section.
   - It appends `bridge_generation`, `"snapshot":"single-lock-v1"` and `"render_b"`: `"bridge:post-push-cached-fill-ms-v1"` in bridge mode, `"legacy:queued-bytes-before"` in legacy mode.
   - All earlier fields keep their names and order.
4. **Pump.**
   - The unlocked `rab_get_stats` at the top of the bridge branch is removed.
   - In the **existing** push critical section, the main thread now runs: lock; **if a mute/cycle resync is pending, `rab_reset_gap_stats` before anything else**; `rab_push`; `rab_get_telemetry`; unlock.
   - After the unlock, `s67_pump_after_push` emits `AUDIO_EV_UNDERRUN`, updates the cache and, only on that fresh snapshot, clears `g_audio_unmute_resync`. A cached snapshot is never used to clear the flag or to set the baseline.
   - **No new lock pairs** are added. The section grows by one `rab_telemetry` copy plus a branch. The cost is **not measured**.
5. **Bridge generation.**
   - `s_drc_generation++` runs at the single `rab_init` site (v58 main.cpp:13217) and at both `rab_free` sites (2869 shutdown, 2886 soft-return teardown).
   - Each time, it also invalidates the pump cache.
   - Soft return re-initialises through the same init site: the `goto session_reboot` (14438) jumps to label 12770, and the init at 13217 follows it.
   - `s67_pump_after_push` resets its underrun baseline to 0 when the generation changes. A new bridge whose counter restarts at 0 is therefore never hidden behind the previous session's larger baseline.
6. **RENDER.b is explicitly versioned.**
   - In bridge mode, RENDER.b is the fill of the last locked post-push snapshot of the **current** generation.
   - It is **0** when no valid snapshot exists: before the first push, after re-init, or while a resync is pending.
   - `audio_stats.render_b` names this semantics. Trace consumers that read RENDER.b without `audio_stats` must be told this version separately: the trace ring has no metadata slot, and `audio_trace.h` is unchanged. Its stale comment, "b=host queued bytes before", already did not match bridge mode before this change.

## Path audit (bridge mode unless noted)

| path | old (v58) | combined |
|---|---|---|
| normal pump, frames > 0 | UNDERRUN emitted at pump start, **before** RENDER | RENDER first, then push and snapshot, then UNDERRUN **after the unlock**. **The trace order within a pump changes.** The delta now runs up to the push moment. |
| frames ≤ 0 early return | read the stats, may have emitted | reads nothing; the underruns are reported at the next push (delayed, not lost) |
| `g_audio_cycle_resync` early return | sets `g_audio_unmute_resync` | unchanged; the resync is handled at the next push (gap reset, then fresh baseline) |
| unmute (gate) | baseline = the first pump-start read; the gap parent reset gaps there under its own lock | gap reset **inside the push lock, before the snapshot**; baseline = that fresh snapshot. Starvation between the unmute and the first push is treated as mute drain. |
| mute-tail push (v58 main.cpp:3499, gate function) | push only | unchanged; no snapshot |
| discard/sink, legacy, no device, `!s_drc_ready` | no bridge read in the pump | unchanged |
| shutdown / soft-return | `rab_free` | `rab_free`, then generation++ and the cache invalidated |
| `audio_stats` RPC / perf tick | two unlocked or separately locked reads | one locked snapshot |

PCM math is unchanged: render, fade, volume, `rab_push`, `rab_pull` and the resampler are untouched.

## Still not fixed or not verified
- `s_drc_ready` is still a plain `bool` read by the callback. It is ordered only by open/resume and close.
- The v68 `psx_sdl_audio.cpp.obj` source hash is not verified against the canonical wrapper `82a1c745…`.
- SDL3's real lock behaviour was read from the pinned header (`f2ee08f0…`), not tested.
- The ordering change in the trace, the delayed reports and the absorption of starvation between unmute and first push all need the owner's acceptance.

## Harness `test_combined_getters.cpp` + driver `run_combined_getters.py` (written, not run)
- **What it binds:** the harness `#include`s `combined_getters.extracted.inc`, the exact text between the markers. The driver re-extracts it from the **copied** pinned `main.cpp.proposed` and byte-compares it with the copied `.inc` before compiling.
- **Lock placement:** a **checked** `rab_get_telemetry`, substituted by a macro for the getter block only, asserts that the calling thread holds the lock at the moment of the copy whenever a device is open. This checks placement, not just pair counts.
- **No data races:** atomics and thread-locals throughout; a non-recursive stub mutex; every bridge access is under the lock once the writer starts.

**Phases:**
- **A — lifecycle:** both the old and new getters are checked on the not-ready, no-device and device paths, for exact values, lock counts and locked copies. The old getter must equal `_ex`, and the gap getter must equal `_ex`.
- **B — labelled deterministic negative control, single thread, no undefined behaviour:** hand-built torn copies must fire all three detectors (mod 37, ΔU vs ΔP, and U − cur_gap vs K).
- **C — concurrency:** at least 200,000 `_ex` snapshots against a writer thread inside one continuous gap. Every snapshot must satisfy `(U − U0) % 37 == 0`, `U − cur_gap == K`, `gaps == 1` and monotonic U. Writer progress is proven (≥ 1,000 pulls and ≥ 100 distinct values). Final checks: ΔU == ΔP == 37 × pulls, and Δcur_gap == ΔU.

**Bounds:**
- Writer start: 5 s. Phase C: 20 s. Stop flag: 5 s.
- `g_done` is set **before** the thread actually ends, so the join is **not** independently bounded.
- **The mandatory outer Job is what bounds the run:** wall ≤ 120 s, 1024 MiB, one CPU, BelowNormal. Its kill or refusal receipt counts as a failure even with no manifest.
- The driver's own timeouts are 60 s for the compile and 60 s for the run. It starts children hidden at BelowNormal with single-thread environment variables, records PID, start time, command line, elapsed time and exit code, and writes the manifest in try/finally.

**What a pass would show:** the proposed getter block takes its snapshot under one lock that is coherent against a concurrent `rab_pull`. It would **not** show that the integrated main.cpp or debug_server builds, links or behaves correctly under real SDL3, or anything about the pump paths. Those need the owner's private rebuild of v58 main and v67 debug against the combined header, with the GL worker, F3, census and every other retained input preserved, followed by qualification.

## Files (full sha256)
| file | sha256 |
|---|---|
| `recomp_audio_drc.h.proposed` | `0022c3bc8704439b50ead84b12ee7e123e79be331e2194a9578ee6292cd8a5e6` |
| `main.cpp.proposed` | `57f915a48f156eb7e99e23b0a36ae259dcd9d9ced179ed0808842f30fbc1d234` |
| `debug_server.c.proposed` | `b080725805b9253e1659528780f2b5fb28561cf5fe35ff82d92a4b875a069e4f` |
| `combined_getters.extracted.inc` | `ed046b2bb357f61567d794915f26bc3eb5b9e618226ddbc0f753b7ea59fa671f` |
| `*.vs-gap-parent.diff`, `*.vs-v68-original.diff`, `test_combined_getters.cpp`, `run_combined_getters.py`, `README.md` | in the s67 message and checkpoint |

Generator: s67 scratchpad `make_combined.py`. It does text substitution only, asserts every pin and an exact match count, and refuses to overwrite.
