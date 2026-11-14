# Post-restart recovery evidence (claude-einhander)

- Boot: 2026-11-14T12:49:21Z (psutil). Root reports a Windows 'unexpected prior shutdown' event at 12:43:59Z.
- The damaged freeze's READY.json mtime is 12:44:16Z, so it was written about the time of the unexpected shutdown.
- Cause of the all-NUL files: NOT established. Unflushed writes are a hypothesis consistent with the timing,
  not a proven filesystem cause. (`../../frozen/DAMAGED-renderer-v61-classmip-v5.json` and the FAILED-RUNS row
  frozen into v5-r2 word this more strongly than the evidence supports; this note corrects them.)

Files:
- `zero_audit.py` / `zero_audit.json`: own scoped trees only (class-mip, 95a3-k-panel, memory, continuity).
  6314 files checked; 263 all-NUL, all inside frozen/renderer-v61-classmip-v5; 606 empty files are pre-existing
  empty logs.
- `verify_sources.py` / `verify_sources.json`: the recovery sources checked against recorded hashes:
  - the run-3 result vs INDEX, the inputs, the working sources, the 8 + 136 sidecars and the self-test;
  - no NUL byte in any text file of the scoped trees outside the damaged freeze.
- `../../record_damaged_freeze.py` -> `../../frozen/DAMAGED-renderer-v61-classmip-v5.json`: per-file listing of the damaged
  freeze, made read-only.
- The new freeze is `../../frozen/renderer-v61-classmip-v5-r2`, from replay `../../runs/20261114T131112Z`.
