# Audio gap counters: r2 corrections (source only; nothing compiled or run)

This file answers main's review msg_86751107af42f51f. `README.md` (`6967c631d8626817c6207e41edd4099d994766bf9daa831e142fb51ad9d4eae9`) and `test_rab_gap.c` (`573c22b2828dce3a517da359ef6fe2cbf43e8a18642cb651b88f9f62d65b6160`) are both kept unchanged. Where they conflict with this file, this file wins.

The proposed patch files are **unchanged** from r1. Building or running anything needs a fresh CPU grant after the host-freeze hold is lifted.

## Corrected semantics (replaces the README.md "Semantics" bullets)
- **`underrun_events` is lifetime-cumulative.** It is never reset, neither by `rab_reset_gap_stats` nor by the unmute resync. Only `rab_init` zeroes it.
- **The gap counters are epoch-local.** The correct identity is `sum of gap lengths in the current epoch == underrun_events − (underrun_events snapshot taken at the last gap reset)`.
  - With no reset since init, the snapshot is 0.
  - Comparing epoch gap counts against the lifetime total is wrong whenever `gap_epoch > 0`. Any consumer of `audio_stats` must take its own snapshot at each epoch change.
- **The README.md sentence "unchanged, and since the last reset it equals the sum of the gap lengths" is withdrawn** in favour of the identity above.
- **Reset during an ongoing starvation run.** `rab_reset_gap_stats` clears `in_gap`. If the very next frame is still starved, it opens a new gap of the new epoch. In main.cpp the reset runs at the unmute resync. The fixture does not cover reset during an ongoing run, and makes no claim about it.

## Claims that are NOT made
- **The existing `rab_get_stats` race stays unfixed.** It copies `b->stats` without the SDL device lock while `rab_pull` writes it. Only the new `psx_audio_out_gap_stats` reads under the lock. **Audio telemetry as a whole is not claimed to be synchronized**, and `audio_stats` reads the old fields and the gap fields at different moments.
- **The cost of the extra branch and writes per starved and delivered frame in `rab_pull` is not measured.** No performance claim is made either way.
- **No audible fix and no performance gain are claimed.** This is telemetry only. It changes no rendered sample by design, and fixture check (B) below is what would show that.

## Fixture r2: `test_rab_gap_r2.c` + bounded driver `run_rab_gap_r2.py`
- **Builds.** One source is built twice: base (original header) and patched (proposed header, `-DRAB_HAS_GAP`).
- **Outputs.** Each build writes the raw int16 LE PCM of every pulled sample to `<case>.pcm`. It also prints the old counter at every mark.
- **Exit code.** The fixture exits 1 on any failed check and 2 on usage, IO or `rab_init` failure.

**Acceptance (all required), decided by the driver:**
- **(A)** both builds exit 0;
- **(B)** for each case, the `.pcm` SHA-256 is identical between base and patched;
- **(C)** for each case, the old-counter marks are identical between base and patched;
- the case list is exactly the 7 names below, in this order.

The 32-bit FNV hash is gone.

**Exact oracles.** The bridge has no re-prime. With no push during a drain, starvation is therefore one contiguous run, so the expected values are exact functions of old-counter deltas (`m_i` = old counter at mark i). Each case also asserts that the measured run is nonzero.

| # | case | old-counter checks | gap checks (patched) gaps / max / cur / epoch |
|---|---|---|---|
| 1 | `unprimed_starvation` | m0 == 0 | 0 / 0 / 0 / 0 |
| 2 | `one_gap` | m0 == 0; 0 < m1 < 48000 | 1 / m1 / m1 / 0 (gap still in progress) |
| 3 | `recovery` | m0 > 0; m1 == m0 after the refill | 1 / m0 / **0** / 0 |
| 4 | `multiple_gaps` | m0 == 0; L1, L2, L3 > 0; counter unchanged across each refill; L1+L2+L3 == m6 | **3** / max(L1,L2,L3) / 0 / 0 |
| 5 | `gap_split_across_callbacks` (37-frame callbacks) | m0 == 0; 74 < m1 < 48000 | **1** / m1 / m1 / 0 |
| 6 | `mute_then_unmute_reset` | m0 > 0; m1 == m2 == m0 (old counter kept across the reset); Lpost = m3 − m1 > 0 | before the reset: 1 / m0 / m0 / 0; after the reset: 0 / 0 / 0 / **1**; after the second drain: 1 / Lpost / Lpost / 1 |
| 7 | `reset_by_init` | m0 > 0 before re-init; m1 == 0 after `rab_init` | before: 1 / m0 / m0 / 0; after: 0 / 0 / 0 / 0 |

**Parameters:**
- source 44100 Hz, host 48000 Hz, stereo, `rab_config_defaults` otherwise;
- prime = push 250 ms, then pull 100 ms;
- drain = pull 1 s with no push;
- refill = push 200 ms, then pull ≤ 100 ms.

A failure of any old-counter check in the **base** build means the parameters are wrong for the real header. That is a fixture bug, not a patch result.

**Driver bounds:**
- It refuses to start without `--grant-id`, or if `--out` already exists.
- It pins the fixture, the original header (`70cb5acd…`, full value in the table), the proposed header and the compiler binary by full SHA-256.
- Timeouts are 60 s per compile and 30 s per run, on one core.
- It always writes `manifest.json`.
- It must run inside the grant wrapper (affinity, BelowNormal priority, a whole-tree time and RSS watchdog).

**Expected output pins:** none yet. Expected PCM hashes can't be honestly stated before the first granted run. Acceptance is base == patched equality (B, C) plus the oracles. The first run's hashes become the pins for any rerun.

## Full SHA-256 pins
| file | sha256 |
|---|---|
| base header (v68 include = canonical `runtime/src/recomp_audio_drc.h`) | `70cb5acd5219d7bd2387757dc54072ae42bfcd158f8e3e24108971339ecc7a29` |
| base main.cpp (v58 `sampling-build-v58-frame-phases/main.cpp`) | `5c94d2dd17f52338515ac52df4f8fde04b4eb269ee49ba6bc42b6924bc6523c0` |
| v58 base = canonical main.cpp | `f4ecc89c69b394ca3c334fdfd54958bf496f5573c03a54c5c79cb96892c67b9c` |
| base debug_server.c (v67 `sampling-build-v67-decode-identity-r3/src/debug_server.c`) | `10e31f8dc50cdf451776f18e4b468f95bb2c97d33f50816d9b9d193557af2eba` |
| canonical debug_server.c | `86ce765bab0ef633f8feaefbf5e9de8eb5068102a66dbfa43b01d7aa777fc883` |
| `recomp_audio_drc.h.proposed` | `7de21fb8aac0f442bf50b0259257b4768480c89b21ce8aeba6753339f1f371c9` |
| `recomp_audio_drc.h.diff` | `eee7597093b45d0055c11f987c33a89e1bdf734233cf3e56eb1e31cc625bca33` |
| `main.cpp.proposed` | `2b5ec71825dd627d88f6018667e2e264d9844953994f10d94ee93c6af2dc6068` |
| `main.cpp.diff` | `eb6e8b38c77bc1f262700ed5f3edb8aac8e959a7ac21b3a7e61294c0ee55c9c0` |
| `debug_server.c.proposed` | `2d54ae68c5762b7661faac3713307118ba777d91d8ecd266c2300c2d3c38a25f` |
| `debug_server.c.diff` | `12359b2eba848146926b9a8175fab6fef97eab0282b89d728b6a38971a55f747` |
| `test_rab_gap.c` (r1, superseded) | `573c22b2828dce3a517da359ef6fe2cbf43e8a18642cb651b88f9f62d65b6160` |
| `test_rab_gap_r2.c`, `run_rab_gap_r2.py` | in the s67 message and checkpoint (this file cannot contain its own hash) |
