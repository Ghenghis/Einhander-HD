# PR7-1-2200 durable receipt note (claude-einhander), written 2026-11-14 ~22:09Z

This note is **authoritative over the summary in msg_4b20c1e2 / msg_ade0fd1c** for the two points corrected below,
following root msg_d5b3d3b3. The run files themselves are unchanged and read-only.

## The run

- One attempt under grant msg_d8d4c593 (coordinator msg_02a840da), using the full exact command of msg_f34ee272.
- Launched 22:03:08.385Z with OMP / OPENBLAS / MKL / NUMEXPR thread counts set to 1.
- Runner: `PR7-1-2200-runner/executed-watchdog.py` fa5e42fa.
- Envelope receipt: `PR7-1-2200-envelope.json` 75c12ec84059943dd919c72c7be71a404776b0dd8f572980c1121c06c70b4b28.
- Builder result: `PR7-1-2200/20261114T220309Z/result.json` 2cbb9e220705e8bc1b07214d6680e87a915fec08650d7227385530bcb081cea0.
- Results:
  - syntax 0, compile-object 0, link 0;
  - cpu-contract 0: 65 checks, `dll_loaded` false, `gl_context` false;
  - guard-contract 77, as expected: `gpu_started` false.
- Outputs: exe eb28476c…, obj d818d4aa…
- Job: empty, tree absent; CPU13 returned.
- Root independently verified the build and contracts at 22:05:05.

## Corrections

1. **The compiler input was the ORIGINAL pinned path.** The syntax and compile-object argv in result.json (:24, :48)
   both name `P/remix-probe-r5/sdk_modern_gl_probe.r7.cpp` (751d3231). `executed-source.cpp` in the run directory is
   an **archived matching copy** (also 751d3231); it was **not** the compiler input. My report sentence saying "the
   compiler ran on the copied source in the run directory" was wrong.
2. **9d012821 is the 66.1% RESOURCE REFUSAL** (`PR7-1-20261114T193144Z-rc.json`), not an object failure. The 20:24
   object-path failure has its own receipts: `PR7-1-20261114T202434Z-rc.json` 97a2738c and the builder result
   9391f12c in `PR7-1-20261114T202434Z/`. The 78.6% refusal is f211c634; the 64.6% refusal is 7d7dae89.

## Other caveats (unchanged)

- Builder r1 does not record sub-step creation times. They are UNAVAILABLE; only the step pids are known
  (45152, 45584, 44432, 45740, 5080).
- `PR7-1-2200-wrapper/run_rc2_envelope_r1.py` (fa5e42fa) is an unused spare copy made before the full command
  arrived. It was never executed.
- The fa5 Job cleanup covers only the granted PR7 tree. It does not qualify the separate stray interpreter call
  recorded in `../../incidents/stray-python3-20261114T2205Z.md`.
