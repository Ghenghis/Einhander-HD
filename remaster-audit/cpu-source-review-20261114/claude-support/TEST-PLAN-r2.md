# Self-test r2 for run_rc2_envelope_r1.py: delta over TEST-PLAN-r1.md (root review msg_e084f171)

- Status: **SOURCE ONLY**. The guard `run_rc2_envelope_r1.py` (fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36)
  is unchanged.
- The r1 self-test (47d88561) and TEST-PLAN-r1.md (9b2420b9) are preserved.
- Every case, oracle and pin of TEST-PLAN-r1.md still applies, except for the changes below.
- `selftest_envelope_r2.py` pins three files: run_rc2.r1.py cd3988af…, run_rc2_envelope_r1.py fa5e42fa…, and this file.

## Changes in r2
1. **Owned wrapper always cleaned up.**
   - Each case starts with `w = None, w_ct = None`.
   - A per-case `finally` handles a wrapper still running after any exception, including one raised between Popen and
     communicate:
     - if the PID still matches its recorded creation time, the self-test kills it, then waits (bounded);
     - the wrapper's kill-on-close Job then removes its child tree;
     - a wrapper that no longer matches is never killed.
   - Partial receipts are kept as they are. There are no retries and no extra child runs.
2. **Explicit time budget.**
   - Case work: 240 s. A case starts only if at least 5 s of work budget remain.
   - Hard overall limit: 300 s from start.
   - Every cleanup wait (wrapper communicate after a kill, wrapper wait in `finally`, sentinel wait) is bounded by
     min(30 s, time left to the hard limit).
   - So the run cannot exceed 300 s plus scheduling jitter.
   - No outer Job of any kind is used. The self-test still refuses to run with fewer than 2 CPUs.
3. **T5b oracle.**
   - `child_affinity_before_set` is recorded only, and not required to equal `[cpu]`, in case AssignProcessToJobObject
     already widens it.
   - Required:
     - `child_affinity_set_to == original`;
     - the readback before resume equals `original`;
     - `allowed_before_pin == original`;
     - the child's own self-report equals `original`.
4. **Exact case count.** `all_ok` additionally requires exactly 10 recorded cases (T1, T2, T3, T4, T5a, T5b, T6, T7a,
   T7b, T8), each with `ok` true, plus the sentinel flags `untouched_by_cases` and `absent_after`.

The cost is unchanged: about 30-40 s expected, a hard maximum of 300 s, trivial CPU, under 0.5 GiB.

Command, only after the coordinator clears the hold and gives a fresh grant:
`python -B -I selftest_envelope_r2.py --out <new dir> --cpu <granted cpu>`
