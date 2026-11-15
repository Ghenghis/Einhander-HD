# v3 runs before the passing one (claude-einhander, 2026-11-14)

**Process error, stated plainly:**
- `run_host_test_v3.py` wrote fixed output names (`host-test-v3.json`, `tcp-replies.json`, `host-run-v3.log`).
- Each corrected rerun therefore **overwrote** the previous run's output.
- The exact bytes of the failing runs are **not preserved**.

What each run showed, as observed in the tool output at the time:

| Run | Inputs changed before it | Outcome |
|---|---|---|
| 1 | first v3 runner | Runner did not start: `SyntaxError: unterminated string literal` (line 63). Two mutant strings held literal newlines from my scripted edit. No results file was written. |
| 2 | runner newline fix | `view_v3_test` 73 checks, 0 failures, exit 0, **but `tcp_errors = ['reply2 recent']` → verdict FAIL**. The reported 19/19 mutants include 3 ("v3 lag bucket off by one", "v3 flag table swaps XY_SAT and IR_SAT", "v3 TCP omits lag") **caught only by that same reply2 error**, so not real catches. Codex inspected this `host-test-v3.json` (msg_aa7efae1). |
| 3 | runner: reply2 expects `min(5, ring.total)` (after `t_v3` resets the census, only 2 records remain). Test: lag 2 and 3 cases, IR-only flag case, committed count 24 | 74/74 checks, TCP ok. **"v3 lag bucket off by one" NOT CAUGHT**: that mutant (`d > 2u ? 3 : d`) is equivalent to the original `d > 3u ? 3 : d` for every d. Verdict FAIL 18/19. |
| 4 (current) | runner: the lag mutant changed to a real off-by-one (`d >= 2u ? 3 : d`) | 74/74, TCP ok, v1 137/137, canonical controls pass, syntax 0 new, **19/19**. Verdict pass: `host-test-v3.json` 4b22794b… |

**Diagnosis of run 2:**
- The new `t_v3()` calls `pgxp_view_census_reset()` twice before `t_tcp()`, leaving 2 primitive records in the ring.
- The inherited v2 check required exactly 5 records for `recent:5`.
- The fix compares against `min(5, ring.total)` and also requires a non-empty list.

From now on the runner writes each run's outputs under `runs/<UTC timestamp>/` as well as the latest names, so no run's
result can be overwritten.
