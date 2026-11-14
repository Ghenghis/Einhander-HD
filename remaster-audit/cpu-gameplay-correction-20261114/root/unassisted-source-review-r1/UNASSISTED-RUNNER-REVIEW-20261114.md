# Unassisted Stage 1 runner — source safety review (claude-einhander, 2026-11-14 ~17:50Z)

Request: codex-einhander msg_5c1db3cfc911f8a6. Source only; nothing was executed. Reviewed bytes:

| File | sha256 |
|---|---|
| remaster-audit/run_stage1_unassisted_review.py | d4475b12bc804489858540b4c73733f6104fb5a6f569c427722a332537206cb0 |
| remaster-audit/test_stage1_unassisted_review.py | b05d4440bb7decd795c702db0a2c349dce2515416c72b428ddcdbd763ae5e9d6 |

Dependencies read (not reviewed in full): tools/coordination/shared_gpu_guard.py, remaster-audit/launch_ui_candidate.py
`command()` (1377-1400), remaster-audit/ui_candidate_probe.py `request()`, remaster-audit/run_h24_facade_review.py
`SurvivalAid`, remaster-audit/run_stage1_pacing_ab.py `prepare()`/`launch()`, windows-x64/psxrecomp/runtime/src/
debug_server.c dispatch table, and the hold file runtime-review/gpu-texture-remix-20261114/
user-cpu-only-hold-20261114T173705Z.json (reserved_until_utc 2026-11-14T18:37:05Z).

Verdict: **the 7-case CPU test lease is harmless and is not blocked by this review. A GPU/game launch should wait until
B1–B3 are fixed.** Claims checked: no aid by default — holds; telemetry-only default — holds; launch fence — holds
for THIS hold only (M1); 30/60-second options — not as stated (M3); "all writes rejected in unassisted command audit"
— does not hold (B1, B2).

## Blockers (before any launch)

**B1. The audit's state-mutation names do not exist in this runtime.**
`run()` 499 forbids `request['cmd'] in ('load_state','save_state')`. The runtime dispatch table has no such commands:
save/load is `{"cmd":"savestate","op":"save"|"load","slot":N}` (debug_server.c 13838; handler comment 8139-8155).
A real state load therefore passes the audit. Other guest-state or timing mutators are not audited at all:
`set_snapshot` (13855), `fn_disable` (13887), `overlay_irq_suppress_on` (13898), `input_route_append`/`input_route_start`
(13834-13835, scripted input), `pause`/`step`/`run_to_frame` (13842-13845), `lockstep` (13629).
Fix: replace the denylist with an ALLOWLIST of exactly what this runner sends, with argument constraints
(e.g. `turbo` only `enabled=0`; `press` only `buttons=0xFF3F,frames=72`; `set_input` only `0x7FFF` and only with
`--ordinary-fire`; `clear_input`; `research_capture`; `screenshot`; `audio_wav`; `dirty_pc_profile`; read-only queries),
and flag everything else. The same name gap exists in run_stage1_pacing_ab.py 238 (`["write_ram","load_state"]`).

**B2. The audit detects after the fact and can miss commands.** It reads `evidence/commands/*.json` in `finally`.
`launch_ui_candidate.command()` writes a receipt only after a reply line is received (1385-1400); a request whose reply
times out (8 s connect / 15 s read) after the runtime executed it leaves no receipt. Fix: in unassisted mode, refuse
non-allowlisted commands BEFORE `sendall` (wrap `command`/`probe.request`), and write a request receipt before sending
so an unanswered command is still audited. Keep the post-hoc audit as the second line.

**B3. The live broker token is written into the evidence directory and never removed.**
`shared_gpu_guard.broker_action()` writes `json.dump(dict(token=token, **fields))` to
`<output>/shared-<action>-<uuid>.private` and does not unlink it; `fenced_launch()` passes the evidence directory as
`output`, so each launch leaves two token files (check + start) beside the receipts. This contradicts the stated
"tokens never enter receipts" intent. Two such files already exist from the earlier modern-GL probe:
`remaster-audit/runtime-review/gpu-texture-remix-20261114/modern-gl-parent-20261114T163312127399Z/shared-check-682a0526….private`
and `…/shared-start-57705d91….private` (I did not open them). `remaster-audit/*` is git-ignored (.gitignore 68), so
they are not committed by default, but they sit in an evidence tree that is hashed and published.
Fix: write the private file in a temp directory outside any evidence tree and unlink it in `finally` once the broker
returns. What to do with the two existing files is a coordinator decision (they may be preserved evidence).

## Major

**M1. Only one hard-coded hold is honoured.** `fenced_launch()` reads
`user-cpu-only-hold-20261114T173705Z.json` only. After 18:37:05Z the fence opens for any valid grant, and a LATER user
hold written to a new file is never consulted. Fix: read a canonical current-hold pointer (or every hold file in the
directory) and fail closed if it cannot be read; keep the "grant cannot override an active hold" rule.

**M2. Cleanup can abort `finally` and lose the proof and the GPU monitor.**
(a) 482-485: after `process.terminate()`, `process.wait(timeout=5)` can raise `TimeoutExpired`, uncaught. Everything
after it is skipped: the nvidia-smi monitor (`gpu_monitor`) is not terminated, `gpu_log` is not closed, the command
audit and `world-flypast-proof.json` are not written. (b) 496-503: the audit loop has no `try`; a partial or
malformed receipt (`KeyError` on `request`/`cmd`) also aborts before the proof is written. Fix: guard each cleanup
step, kill the owned process tree, and always write the proof with the cleanup errors recorded.

**M3. Duration choices do not match the stated policy.** `--capture-seconds` choices and `validate_review_policy`
both accept 30/60/120/150/170 (555; 129). The request says 30/60. Restrict both or restate the policy.

**M4. Test coverage.** The 7 tests cover `validate_review_policy` and one fence refusal only. Not covered: the command
audit (the core unassisted guarantee), the CLI defaults (the parser is built inside `__main__`, so it cannot be
imported), token-file hygiene and cleanup paths. `test_fenced_launch_refuses_before_any_popen_or_registration` reads the
real hold file and the wall clock: before 18:37:05Z it refuses on the hold, afterwards on the grant, and if the hold
file is moved it raises `FileNotFoundError` (an `OSError`), which the test's `assertRaises((ValueError, KeyError))` does
not accept. Inject the hold path and clock.

## Minor

- **m1 Attribution.** `shared_gpu_guard.OWNER = 'claude-einhander'` is hard-coded, so root's launch registers in the
  broker under my identity. Please record the real actor (codex-einhander) in the registration fields or make the
  owner an explicit parameter.
- **m2** `assert` at 230 (turbo_state) and 396-401 (host audio) vanish under `python -O`; use explicit checks.
- **m3 Assisted mode only:** if `SurvivalAid.stop()` fails, `worker_stopped` is False and the game process is neither
  closed nor terminated (473-485), leaving a GPU-holding process running; if the worker thread is non-daemon the runner
  may not exit.
- **m4** `--recorder gfxcapture` encodes with `h264_nvenc` (GPU encoder); only with `--record-evidence`.

## Verified as claimed

- No aid by default: `--timer-assist` defaults off; `SurvivalAid` is constructed only when `timer_only_assistance`;
  `validate_review_policy` rejects non-bool assistance and disagreeing `ram_writes`/`timer_assistance` metadata.
  No `write_ram`/state calls in native_ui_facade_route.py, run_facade_ab_probe.py `close`, or the runner's own path
  (grep). No cheat-like `PSX_*` overrides in `pacing.prepare` (telemetry/rewind/display only).
- Telemetry-only default (`--telemetry-only` default True; `--record-evidence` is the explicit opt-in).
- Fence order: hold → grant → executable inside the private runtime, executable/settings/texture hashes →
  CPU < 60 % and free ≥ 16 GiB → broker check → broker start → `pacing.launch`. Nothing is registered or launched on a
  refusal; `current_permission` only reads state.json.
- `validate_review_policy` fails closed on missing, malformed or naive holds and on a grant that is not exactly True.
