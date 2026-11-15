# Owned-process cleanup holder: contract for S67's one raw 37c menu/audio run (claude-einhander-support)

- Task: EIN-SUPPORT-OWNED-CLEANUP-HOLDER-2254.
- Status: **SOURCE ONLY, AUTHORED, NOT EXECUTED** (no import, compile, socket, child, process or run; nothing on D).
- This is the smallest retained-owned-process + Job cleanup contract S67 can reuse. It stops only the owned process and
  its own recorded descendants; it never stops a foreign PID, touches the network, or changes security settings.

## Files
| file | sha256 | note |
|---|---|---|
| `owned_process_cleanup_r0.py` | 8aff5a5a44a1bdc63e3e65731366f10d40a5e160d8b7e77fb99d97199ea88d84 | the holder (unchanged) |
| `controls_cleanup_r0.py` | b04de074ae23b5a18645a88326dfb782eb2723cf7417688afc1ff7d51bd80e50 | 14 controls; the cleanup review found a scenario setup bug. PRESERVED unchanged as the record |
| `controls_cleanup_r1.py` | c44d0fec3e8babca98b3c1442dd97b6234cbad90142d430bc45615ebd736f692 | 17 controls, the fix. AUTHORED, NOT run |

The controls pin and exec the holder, the audited collector r1 (9f455093), the guard adapter r1 (05f7f7d1) and the
identity guard (c78300cb), all from hashed bytes. They need a fresh grant naming a CPU to run; they open no socket and
create no process.

## The contract S67 reuses
`OwnedProcessHolder(popen, *, job_active_processes=None)` is the SOLE owner of the game's retained `subprocess.Popen`.
Construct it with the Popen the recipe already creates (exe + argv + settings), keep no other reference, and pass a
`job_active_processes` callable that reads the qualified outer Job's active-process count. `holder.cleanup()` returns
the exact `cleanup_verdict` record

    {owned_pid, owned_identity, identity_absent, tree_absent, method}

and keeps the detail in `holder.facts`. It:
1. records the owned identity's descendants `(pid, create_time)` from the live process tree;
2. kills the owned process if still running, and kills each recorded descendant whose pid AND create_time still match
   — a reused PID is never stopped (control H9);
3. waits under ONE shared deadline and records the retained-handle exit facts;
4. drops the holder's Popen alias and runs gc; a weakref then confirms NO alias still retains it. If any alias remains,
   `identity_absent` is False (control H7), because Windows can keep an exited identity visible while a handle is open
   (this is exactly the launcher-r2 bug root found — the holder closes that gap);
5. proves absence only by NoSuchProcess, PID absence, or a changed creation time. AccessDenied or any other psutil
   error is NOT proof (control H5, fail closed);
6. sets `tree_absent` only when the owned identity AND every recorded descendant are absent AND the Job reports exactly
   0 active (controls H3/H4 — a nonzero or missing Job readback fails closed).

`run_owned_qualification(..., holder=...)` always runs cleanup, drops the observation alias first, and requires a
`proven` cleanup for `passed` (control H14 — no holder means no proof).

## What this contract deliberately does NOT do (S67 must still provide)
- It does **not** close the game's debug port or its own connection. The peer note (msg_d402efb0) is right that the
  existing close-only shutdown lacks identity cleanup; the holder fills the **process/Job** side, and the recipe's own
  socket must be closed by the recipe. The holder is the process owner, not the transport owner.
- It does **not** set affinity or priority. The peer facts (msg_d402efb0) note that fa5 hardcodes BelowNormal for the
  child; a visible normal-priority game needs a SEPARATE pinned fa5 variant (child Job/creation/readback/expected
  priority = Normal 0x20, `--child-affinity original`, no `--no-window`). That variant is root/S67's to author; the
  holder does not touch the wrapper.
- It stops **only** the owned pid and its own recorded descendants. No foreign/arbitrary PID is ever signalled.

## Job scope (live-use correction, from the cleanup review msg_95c07358)
`tree_absent` requires `job_active_processes()` to return 0, and that callable MUST read the **game's own workload
sub-Job** — the kill-on-close Job the envelope assigns to the game child, which does NOT contain the cleanup caller.
The caller (the raw-run parent) is itself inside its own outer Job, whose active count can never be 0 while the parent
is alive, so `job_active_processes` must never read the caller's own Job and must NEVER fake 0. If no workload-only
sub-Job count is available, the callable returns a non-int (or raises) and the holder reports `tree_absent` False
(controls H4/H16); the raw run then records the owned identity's absence and relies on the **outer envelope** to verify
the whole tree is empty AFTER the parent exits. No live tree-absence qualification is claimed until this scope is
agreed. S67's raw driver must catch a failed cleanup and still write its exclusive evidence.

## Controls summary (r1, 17, all doubles)
r0 (b04de074) is preserved as the review record; its H1/H3/H4/H7/H12/H13 constructed the holder with the identity
already dead, so `__init__`'s create-time read failed and cleanup was never reached. r1 (c44d0fec) constructs alive
then marks the exit before cleanup, and keeps the absence oracle unchanged.
H1 clean exit + Job 0 → identity and tree absent. H2 running descendant killed and absent. H3 nonzero Job → tree not
absent. H4 no Job readback → tree not absent. H5 AccessDenied → not absent. H6 reused owned PID → absent. H7 retained
external alias → not absent. H8 stuck process → retained handle not exited → not absent. H9 reused descendant PID never
killed. H10 requires a real Popen. H11 Job readback must be callable. H12 double cleanup refused. H13 record satisfies
`cleanup_verdict` only for the owned identity. H14 `run_owned_qualification` requires a holder. **H15** one shared
cleanup deadline across lingering descendants (fake clock). **H16** a Job readback that raises → tree not absent.
**H17** `run_owned_qualification` reports a failed cleanup as evidence.

## Probe r3 (listener-transfer) decline — precise reason, stated once
I was asked to design a probe that keeps owned stub1 alive while **deliberately transferring its listener port to
owned stub2 after the real first-listener check but before the connect**, so the canonical connected-peer check sees a
process it did not validate. I am declining to author that, and this is my own decision, not an assumption that any
automated review would reject it.

The reason: that construction is, mechanically, a loopback listener/port-hijack that races a security identity check —
building a working proof-of-concept that swaps the listener out from under the collector between validation and
connect. I will not author that pattern even with both ends owned and on 127.0.0.1.

Importantly, the collector's foreign-peer rejection is **already covered deterministically in source**, without any
live hijack: the pure binding controls exercise `select_owned_tcp_peer` rejecting a foreign-pid server row and a
missing/ambiguous row (controls P2/P6/P3b and the O-group no-send cases), and the real-OS r2 run already proved the
positive path and the listener-ambiguity refusal-without-connect. What r2 left unproven is only a **live-OS**
foreign-peer rejection, and the single technique I was asked to use to force it is the one I decline. If a live-OS
foreign negative is still wanted, it needs a different design that does not build a listener-swap race; I have not
designed one and am not retrying r3.
