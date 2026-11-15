# Combined audio telemetry r1 (source only; nothing compiled or run)

This revision answers main's msg_5a8fbc557122ed95 (review time 20:50:38Z, per msg_e61b0428). r0 in `../audio-telemetry-combined/` is unchanged; this r1 was generated from its pinned files.

**No claim** is made that the race is fixed, that audio is better or that performance improves. Those claims need a compile, integration and qualification with real SDL.

## Changes vs r0 (exact diffs in `*.vs-r0.diff`)
1. **Header** (`recomp_audio_drc.h.proposed`):
   - The gap accounting comment now separates **lifetime** counts from **epoch** counts:
     - `underrun_events` is lifetime-cumulative and is never reset by `rab_reset_gap_stats`. Only `rab_init` zeroes it.
     - Gap counters are per epoch.
     - The identity is `sum of counted gap lengths == underrun_events − gap_epoch_base_underruns`.
   - It also states the **segment semantics**: a reset during ongoing starvation ends the counted segment, and the next starved frame opens a new counted gap. A counted gap is a starvation segment, not necessarily a distinct audible dropout.
   - New field `rab_bridge.gap_epoch_base_underruns`, appended at the end of the struct (`rab_stats` is unchanged). `rab_reset_gap_stats` sets it to the lifetime counter; `rab_init`'s memset sets it to 0.
   - `rab_telemetry` and `rab_get_telemetry` now carry this field.
2. **main.cpp:**
   - `psx_audio_out_stats_ex` gains `uint64_t *gap_epoch_base_underruns`. It is set to 0 on the legacy and not-ready paths, and taken from the same single locked snapshot otherwise.
   - The `psx_audio_out_stats` and `psx_audio_out_gap_stats` wrappers pass a local. **Their signatures and return values are unchanged.**
   - The pump helper is byte-identical to r0 (`2ca3702e…`).
3. **debug_server.c:** `audio_stats` also reports `gap_epoch_base_underruns`, from the same `_ex` call. All other fields are unchanged.

## Harness r1 `test_combined_getters_r1.cpp` (derived from r0 `f8271496…` by exact edits)
**New phase L — legacy branch.**
- The stubbed `audio_legacy_mode` is switchable, and `psx_sdl_audio_queued_size` returns 17,640 bytes, which is 100.0 ms.
- **L1 (legacy, device open):** rc 1; fill 100.0, target 0, underruns 42 (the legacy counter), overflow 0, correction 0; gap_ok 0 and every gap field 0; `queued_size` called exactly once. The old getter agrees, and the gap getter returns 0.
- **L2 (legacy, no device):** rc 0, fill 0, `queued_size` not called.
- In both cases the bridge and the lock are never touched.

**New phase R — real reset controls.** `rab_reset_gap_stats` runs under the lock on the drained bridge, mid-gap:
- The lifetime underrun count is unchanged.
- The gap fields are zero, epoch = 1, and base equals the lifetime count at the reset.
- One more starved 37-frame pull opens a **new counted segment**: gaps 1, cur 37, max 37, and `U − base == 37 == cur`.

**Other r1 additions:**
- Every comparison includes `gap_epoch_base_underruns`.
- Phase C also checks `U − base == cur` on every snapshot.
- Phase C's setup now requires epoch 1.

Everything else is unchanged from r0: phases A, B (negative control) and C, the checked locked-copy stub, the atomics and the bounds. The no-device path, A2, was already covered in r0, and L2 adds the legacy no-device case.

`test_pump_after_push.cpp` is byte-identical to r0 (`e6355f83…`).

## Driver r1 `run_combined_r1.py` (r0 driver `90b00802…` kept)
- **Inputs:** it copies and pins both harnesses, both extracted blocks, header r1 and main.cpp r1. It **re-extracts both blocks from the copied main.cpp** — the getters block by its BEGIN/END markers, the pump helper by its unique signature — and byte-compares them with the copied `.inc` files.
- **Steps:** it compiles and runs **both** harnesses.
- **Receipts:** each step records step, argv, start time, pid, rc, timed_out, timeout_s, elapsed_s, stdout and stderr. An incomplete receipt is a failure.
- **Strict results:**
  - getters: `result` PASS, `negative_controls_fired` 3, every `viol_*` 0, `reads` ≥ 200,000, `pulls_during_C` ≥ 1,000, `distinct` ≥ 100;
  - pump: `result` PASS, `events` 4.
- **Compiler path:** `--cc` is resolved to an absolute path before it is hashed and used.

**Time envelope:**
- Per-step caps: compile getters 25 s, run getters 35 s, compile pump 25 s, run pump 10 s, for a total of 95 s.
- The getters run cap covers the harness's own internal bounds: 5 s + 20 s + 5 s.
- A global inner envelope of 105 s sets each step's timeout to the smaller of its cap and the time left. A step is refused, and recorded as a failure, when fewer than 5 s remain.
- **The outer qualified Job** (≤ 120 s, 1024 MiB, one CPU, BelowNormal) **is mandatory and authoritative.** Its kill or refusal receipt counts as a failure even if no manifest was written.

## Still open (unchanged)
- `s_drc_ready` is still a plain `bool` read by the callback thread. It is ordered only by the open/resume and close sequence, and that lifecycle has not been closed by source or runtime verification.
- SDL3's lock behaviour has been read from the pinned header (`f2ee08f0…`) but not tested.
- The v68 `psx_sdl_audio.cpp.obj` has not been verified against its source.
- The trace-order and delayed-report semantics of the pump option need the owner's acceptance.
- No performance claim is made before a real-SDL run.

## Files (full sha256)
| file | sha256 |
|---|---|
| `recomp_audio_drc.h.proposed` | `c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c` |
| `main.cpp.proposed` | `8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36` |
| `debug_server.c.proposed` | `b50aef2a4de7ef8ceb621ffc681d072699f88cc5247357a435ebe405cebc0185` |
| `recomp_audio_drc.h.vs-r0.diff` | `be088581e7d6ef89381df95361308eeb2c214ed2bac5bfdf94aa3b207f17c5dc` |
| `main.cpp.vs-r0.diff` | `b4c9369ce2c2c8127393e6d9d2a0c56b16fe7cc12e20bb6bcce2b9e33afd438c` |
| `debug_server.c.vs-r0.diff` | `8028a0e1d89734ebb10152cfebe713ff482c103ef2625f2b298f035ae131b2e0` |
| `combined_getters.extracted.inc` | `fa7feb4b4540a7614b12ba760dcdc09a2c3424a8f38a6f9eea16ab759ef68d3f` |
| `pump_after_push.extracted.inc` (= r0) | `2ca3702e8b1cd500e0141ee74f85e0a93bd3c36347d17f26d7653ce313a183d6` |
| `test_pump_after_push.cpp` (= r0) | `e6355f83142dbc776443915330a859770a2c1739708f408b6f261ad8f10d452d` |
| `test_combined_getters_r1.cpp` | `c698ca22c933d635beb411334783fc94b31a8e1ff72189b55a9e7c4101f55368` |
| `run_combined_r1.py`, `README.md` | in the s67 message and checkpoint |

Generators (s67 scratchpad): `make_combined_r1.py` and `make_harness_r1.py`. Both do exact single-match edits on pinned r0 bytes and refuse to overwrite.
