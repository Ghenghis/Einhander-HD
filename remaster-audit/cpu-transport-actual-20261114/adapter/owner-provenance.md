# Granted runs A and B, 2026-11-14 (claude-einhander-support)

- Grants: A = msg_a31f21f7 (relayed as msg_a53c5099); B = msg_1fffbeb9 (relayed as msg_9011332a). Clarified by
  msg_7afa243c.
- Each was consumed ONCE, sequentially on CPU14, with no retry.
- Prerequisite checked before A: S45 envelope `diagbands-r3-fixtures-envelope.json` showed rc 0, tree_absent,
  job_empty and child_absent, ending 22:38:38Z. Root and crash-check confirmed S45 and P1 had returned.
- Wrapper launch, for both: `C:/Python314/python.exe -I -B <runner>/executed-watchdog.py …` exactly as granted.
  - The watchdog copy was verified at fa5e42fa….
  - Thread env vars were set to 1, and the wrapper was set to BelowNormal immediately after start.
  - Wrapper identity absence was checked only AFTER the launcher's own handle was disposed and GC ran.

## A: binding controls r1 (5e88fb9e). PASS
- **Pre-launch failure, preserved.** My first launcher script failed BEFORE any spawn: a helper named `H` resolved to
  PowerShell's built-in alias `h` (Get-History). Only the runner dir and one "start" log line existed. They were
  moved unchanged to `adapter-binding/runs/controls-2243-runner.prelaunch-failed-20261114T224118Z`, and the exact
  granted path was re-created for the single launch.
- Pins verified before spawn: controls 5e88fb9e, guard r1 05f7f7d1, collector r1 9f455093, canonical guard 9e6ca815,
  identity guard c78300cb.
- Wrapper: pid 34924, start 22:41:46.153Z, rc 0. Its identity was absent after handle release.
- Controls (`runs/controls-2243/result.json`, sha 764c42c0…): **all_ok true, 41/41 cases ok, case_count ==
  expected_cases == 41**, no fatal, 2.165 s. Schema `support-adapter-binding-controls-r1`, controls_sha256 5e88fb9e,
  cpu 14, allowed_affinity [14].
- Envelope (`runs/controls-2243-envelope.json`, sha 1609122d…):
  - rc 0, child_exit 0, child pid 40592 ctime 1794696107.43845;
  - **tree_absent, job_empty, child_absent all true**, descendants_left empty;
  - job_memory_limit 268435456 (256 MiB), affinity mask 16384 (CPU14);
  - readback before resume: CPU [14], priority 16384 (BelowNormal); peak 21639168 B.
- Sequence log: `runs/controls-2243-runner/sequence-log.txt` (sha 719bcf9b…).
- Scope: pure controls and doubles only. This is NOT live adapter qualification and NOT a canonical install.

## B: owned-stub probe r2 (06f7a44a, stub ed43bda0). Exit 5, INCONCLUSIVE (not a pass)
- Pins verified: probe 06f7a44a, stub r2 ed43bda0, collector c457b58e, guard c78300cb, watchdog fa5e42fa.
- Wrapper: pid 43032, start 22:42:32.465Z, rc 5. Its identity was absent after handle release.
- Envelope (`owned-stub/runs/probe-2244-envelope.json`, sha 84b91fd7…):
  - rc 5, child_exit 5, child pid 23888;
  - **tree_absent, job_empty true**, 5 descendants seen and 0 left;
  - 256 MiB, mask CPU14, readback [14] / BelowNormal; peak 51249152 B.
- Probe result (`owned-stub/runs/probe-2244/result.json`, sha a21b1dc9…): 13.732 s. Clock QueryPerformanceCounter,
  resolution 1e-7 s, ordering margin 200 ns, consistent across the probe and both stubs.
- **What was shown on this Windows host (loopback, FIXTURE stubs):**
  - **V-measure 3/3:** the server-side ESTABLISHED row (laddr = server, raddr = client) was listed with the
    **listener owner's PID BEFORE accept()**, and again after accept. In all three rounds the QPC ordering was proven
    beyond the margin: pre-snapshot end < accept_call, post-snapshot start > accepted, post-snapshot end < served.
    Table lookups took about 1 ms. Replies decoded.
  - **V-real 2/2** (the real c457b58e `sample()`): passed with peer pid = stub1, and the peer lookup was **proven to
    precede accept** (`passed_pre_accept_proven`). This answers the N8 assumption positively for this host.
  - **F-rebind:** SO_REUSEADDR rebind of 127.0.0.1:44214 by a second process (stub2, pid 37232) was **allowed**, and
    both LISTEN rows were present.
  - **F-listener:** the real `sample()` rejected "private debug listener missing or ambiguous" **without
    connecting** (0 new pending events in either stub).
  - **F-measure 4/4** and **F-real-peer 6/6**: Windows routed **all 10 connections to stub1**, the original listener.
    Each was an owned pass with consistent verdicts and the exact client matched.
  - **Cleanup proven:** stub1 (exited, absent) and stub2 (signaled, retained handle exited, absent).
- **Why inconclusive:** `foreign_negative_not_exercised`. No connection ever reached the foreign stub, so the
  collector's foreign-peer rejection with no send was **not observed on the real OS**. This is not a failure, not
  exit 4, and not a pass.
- No pre-accept invisibility was observed (`pre_invisible_events` 0); the c457b58e gate stays unchanged.
- Sequence log: `owned-stub/runs/probe-2244-runner/sequence-log.txt` (sha bda8a972…).

## Follow-up (not started; would need its own grant)
- Exercising the foreign negative needs the foreign listener to actually receive a connection, for example a stub2
  that binds first. This would be a new reviewed probe revision. No rerun of r2.
