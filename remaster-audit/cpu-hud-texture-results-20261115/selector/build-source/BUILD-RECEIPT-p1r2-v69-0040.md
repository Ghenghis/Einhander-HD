# BUILD RECEIPT: P1 r2 (player + enemy colour rows) on v69, private CPU build 0040

- Grant: crash-check msg_fa6c768cdda46a14. Task: EIN-UI-P1R2-V69-CPU-BUILD-20261115.
- Runner: receipts/p1r2run.sh (b5566927…). It took 1 attempt and did not need the precheck retry.
- Envelope: receipts/P1r2-v69-0040-envelope.json, sha 9fba33e8c58b31282921b7e6d27c6f888eca7170db793f98885d014fc124fa97.
  - Wrapper: the fa5 copy in receipts/P1r2-v69-0040-runner, pin verified.
  - Limits: CPU 13 (mask 0x2000), BELOW_NORMAL, 120 s, 1024 MiB, no window.
  - Precheck: system CPU 49.6% (limit 60), free 51.39 GiB (minimum 16).
  - Child pid 49896, exit 0, elapsed 10.48 s, not killed by the timeout.
  - Job: 12 processes, 0 active, 0 terminated. User 5.0 s, kernel 2.03 s. Peak job memory 275169280 B.
  - child_absent, job_empty and tree_absent: all true.
- Builder: build_p1r2_v69_r4.py a8a8f8628de324d640dcdd9e9ae11a18a413f2b66ccc68e894ca32dcbbe50a2f. Its argument was --grant-id msg_fa6c768cdda46a14.
- Output directory: builds/p1r2-v69-0040/ (new).
  - **Einhander_Recompiled.exe sha256 34e5d8f50ee013749bdd53eb139796ca15adea684d1a93bb8335b6127bcd3be2**
  - manifest.json 7af19709de4db34b785f7e92e0c36c0a5d4b474a77dd20087f115667501802e1: verdict PASS, reasons [].
  - src/main.cpp fe85c7e4… matches the reviewed merge.
- Manifest steps, all ok: pins, retained_inputs, copy main / keymap_c / keymap_h, compile main / keymap, deps main / keymap, rsp, link, outputs. The 3 child processes all returned rc 0.
  - deps:main: 1142 entries, equal to the v69 closure (1142). Only-new 0, only-expected 0, changed or missing shared 0.
  - deps:keymap: 118 entries, complete and C:-only. The historical D: closure of old object e03f07c5 is UNKNOWN, because D: was never read.
  - rsp: 119eb5cd…, with exactly 2 objects replaced.
  - outputs: v69_exe_untouched true.
- 37c baseline: builds/p1-v69-2240/Einhander_Recompiled.exe is still 37c137e8af8c53d1…, unchanged.

## Not done or not claimed
- Not launched, not installed, no GPU use. No menu behaviour is verified.
- Live cases L5-L7 and E1-E6 (README-v69-merge-and-live-plan.md 7d70ee83…) are all NOT RUN. Running them is the coordinator's job.
- This is an incremental colour-preset selector only. Zero-strength usability, persistence, realistic skins and per-role bindings remain open.
