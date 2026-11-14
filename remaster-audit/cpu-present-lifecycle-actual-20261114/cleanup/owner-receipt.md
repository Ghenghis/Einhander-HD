# Granted run: cleanup controls r1, 2026-11-14 (claude-einhander-support)

- Grant: EIN-SUPPORT-CLEANUP-R1-CONTROLS-2316 (crash-check msg_d8ff7f27, relayed source-clear root msg_0434098e). One
  attempt, CPU12, no retry.
- Consumed once. CPU12 returned; wrapper pid 8520 (start 2026-11-14T23:18:…Z) absent after handle release; child
  37908 absent.
- Pre-run gate: all six pins verified unchanged (controls c44d0fec, holder 8aff5a5a, collector r1 9f455093, guard r1
  05f7f7d1, identity c78300cb, watchdog fa5e42fa); CPU load 11%, free 57 GiB.
- Note on the --no-window stdout loss (s67 msg_664d3023): the controls write `result.json` exclusively with fsync, so
  the verdict survived; `wrapper.stdout.txt` / `wrapper.stderr.txt` are both 0 bytes (e3b0c442…), as predicted. The
  result is read from the FILE, not stdout.

## Result = PASS, 17/17
- `controls-cleanup-2316/result.json` (sha 9944c3a4a188b835483e45f78540e90eec7dd71f7e854a21906456291359fa49):
  all_ok true, case_count == expected_cases == 17, no fatal, 0.234 s, schema `support-owned-cleanup-controls-r1`,
  controls_sha256 c44d0fec, cpu 12, allowed_affinity [12]. No failed cases.
- All 17: H1 clean exit→absent, H2 descendant killed→absent, H3 nonzero Job→not absent, H4 missing Job→not absent,
  H5 AccessDenied→not absent, H6 reused PID→absent, H7 retained alias→not absent, H8 stuck handle→not absent, H9
  reused descendant never killed, H10 requires Popen, H11 Job callable, H12 double cleanup refused, H13 verdict only
  for owned, H14 run_owned_qualification requires holder, **H15** one shared deadline (elapsed 0.2 s, 9 sleeps across
  two lingering descendants — not 2×), **H16** Job readback RuntimeError→tree not absent, **H17**
  run_owned_qualification cleanup failure→passed false/status failed.

## Envelope receipt
- `controls-cleanup-2316-envelope.json` (sha 5116ecc2c9b5351c9353ecd72e98c64f9129b6cebff8b0f895bcc9855f4ed680):
  rc 0, child_exit 0, child 37908 / 1794698348.77861; **tree_absent, job_empty, child_absent all true**, 0 descendants
  seen, descendants_left empty; job_memory_limit 536870912 (512 MiB), affinity mask 4096 (CPU12), readback [12] /
  priority 16384 (BelowNormal), peak 20172800 B (~19 MB).
- Sequence log `controls-cleanup-2316-runner/sequence-log.txt` (sha 863fa7f5…).

## Scope
Pure controls and process doubles only. No real socket, Popen, listener, broker or GPU. This does NOT claim live tree
qualification; per the agreed Job-scope, the raw run joins the owned identity's absence with the outer envelope's
emptiness only AFTER the parent exits, and never fakes an in-Job zero.
