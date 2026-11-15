# run_rc2_envelope_r1.py (envelope-r1): dummy-child test plan, r1

- Task: EIN-SUPPORT-WATCHDOG-VARIANT-20261114.
- r1 follows root's review msg_ae95a9f5. The r0 files are preserved unchanged: run_rc2_envelope.py 0d4078fc,
  selftest_envelope.py 1f6d58bb, TEST-PLAN.md a920061b.
- **SOURCE ONLY.** Nothing has run beyond compile checks. The host-freeze diagnostics hold is in force.
- The canonical run_rc2.r1.py is untouched.

## Pinned inputs
The self-test asserts these full sha256 values before any case runs.

| file | sha256 |
|---|---|
| run_rc2.r1.py (baseline guard, canonical, read-only) | cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd |
| run_rc2_envelope_r1.py | fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36 |
| this TEST-PLAN-r1.md | pinned by the self-test (it cannot contain its own hash) |

`selftest_envelope_r1.py` pins all three. Its own hash is reported in the review message, so this file does not
reference it and there is no hash cycle.

## envelope-r1 change versus r0 (one place)
- After AssignProcessToJobObject, while the child is still SUSPENDED: `cp.cpu_affinity(want_cpus)` is applied
  explicitly.
- Reason: the child inherits the watcher's single pinned CPU, and the job mask is only a ceiling.
- The receipt records `child_affinity_before_set` and `child_affinity_set_to`. The readback before resume must equal
  `want_cpus`, or the run exits 125.
- Diffs: `run_rc2_envelope_r1.vs-r0.diff`, and `run_rc2_envelope_r1.vs-r1-cd3988af.diff` against the canonical r1 guard.

## Self-test r1: safety properties
- Pins are verified before anything starts (exit 2 on any mismatch). The output directory must not exist yet, and is
  created exclusively.
- Wrappers are launched with creationflags 0x08004000 (CREATE_NO_WINDOW | BELOW_NORMAL). No outer one-CPU Job is used.
  The self-test refuses to run if its own allowed affinity has fewer than 2 CPUs.
- Global wall bound: 240 s. Each wrapper call gets min(case timeout + 30 s, remaining budget).
  - On TimeoutExpired, the self-test kills only the wrapper PID it launched, after checking that PID's creation time.
  - The wrapper's kill-on-close Job then removes the child tree.
  - An incomplete-case record is written.
- Every case is in its own try/except. A missing or unparseable receipt is recorded as a failure, never a pass.
- The sentinel is created before the cases and handled in `finally`:
  - its PID and creation time are re-verified before it is killed (it is killed only if it is still the same process);
  - its absence is then checked;
  - it is never orphaned, even if a case raises.

## Cases and oracles
| case | oracle |
|---|---|
| T1 normal return | wrapper rc 0, receipt rc 0, tree_absent, job mask readback = 1<<cpu |
| T2 failure | child exit 7 gives wrapper rc 7 and child_exit_code 7, tree_absent |
| T3 timeout + grandchild | `--timeout 3`; the child spawns a sleeping grandchild. rc 124, timeout_killed, ≥1 descendant seen, descendants_left empty, tree_absent |
| T4 injected post-spawn failure | `RUN_RC2_FAULT=after_spawn` gives rc 125 with a wrapper_error containing `after_spawn`, `start_utc` absent (never resumed), tree_absent |
| T5a 1-core affinity | default mode: the child writes its own affinity `[cpu]`; the readback equals `[cpu]` |
| T5b original affinity | `--child-affinity original`: `child_affinity_before_set == [cpu]` (inherited), the readback equals the original mask, and the child's self-report equals the original mask = `allowed_before_pin` |
| T6 hard memory cap | `--max-job-mib 64`. The child catches MemoryError from `bytearray(256 MiB)`, writes `memerror.txt` and exits 3. Pass needs ALL of: job_memory_limit readback = 64 MiB; wrapper rc 3 and child_exit_code 3; `memerror.txt` present; `after_alloc.txt` absent; tree_absent. Peak memory is reported only, not used as the oracle. A wrapper rc 125 is never accepted as an allocation pass. |
| T7a usage: timeout | `--timeout 301` gives exit 2, no receipt file, nothing started |
| T7b usage: invalid cap | `--max-job-mib 5000` gives exit 2, no receipt file, nothing started |
| T8 r1 baseline | the same trivial child under the canonical r1 guard: rc 0, tree_absent, affinity `[cpu]` |
| Sentinel | alive with the same PID and creation time after all cases; then killed by the self-test after re-verification, and absent |

Cost:
- 10 wrapper runs; T3 waits for its 3 s timeout, the others take a few seconds each;
- expected about 30-40 s, with a global bound of 240 s;
- trivial CPU (exit/sleep), plus one 256 MiB allocation that the 64 MiB job cap refuses;
- under 0.5 GiB.

Command, only after the hold is cleared and an explicit grant names a CPU:
`python -B -I selftest_envelope_r1.py --out <new dir> --cpu <granted cpu>`
