# Four Claude sessions — actual launch and recovery

The live roster is `coordination/CLAUDE-SESSIONS-20261114.json` in the canonical
`C:/github/Einhander` workspace. Three new native sessions have confirmed model
startup, unique Hermes inboxes, checkpoints, live hook routing and first artifacts.
The original Stage1 session has separately confirmed its own native/CLI identity.

- `claude-einhander`: Stage1, RISE and shared class-mip runtime.
- `claude-einhander-s23`: Stages2–3.
- `claude-einhander-s45`: Stages4–5, isolated worktree recorded in roster.
- `claude-einhander-s67`: Stages6–7, isolated worktree recorded in roster.

Main coordinator `codex-einhander` accepted ongoing inbox/checkpoint monitoring
and bounded-monitor renewal in `msg_7b8737f92c0ecbba`. Route new results and resource
requests there. The launch coordinator is `codex-einhander-crash-check`.

After a crash, read the current runtime handoff and real inbox before work.
Inspect the recorded native session and resume it when available; inspect its
actual running state before creating a replacement. Rejoin under its recorded
Hermes owner, reconcile locks/tasks, verify recent output hashes and write a new
checkpoint with the actual clock. Preserve corrupted/failed evidence unchanged.
Record any replacement desktop and CLI IDs in the roster before its model is
allowed to read a worker inbox. Never use another session's owner to get past a
registration warning. Unknown-ID help routes to the main integration owner.

The metadata monitor is `session-health.mjs --watch 1800` (maximum30minutes).
It does not resume models, write model presence, prove liveness or run while the
computer is off. Its initial PID28164 has an actual bound of14:07:14.706UTC on
November14; the main model owns renewing/replacing it. Actual-model inbox turns
and concrete outputs remain the evidence of progress.

Waiting checkpoints require an actual armed receiver and future bounded wake.
For an explicit human pause, use an identified owner, for example:
`node tools/coordination/claude-checkpoint.mjs --owner claude-einhander-s23 --user-stop "User explicitly paused"`.
An actual registered `--session` can also select its owner. Honor the human stop
even if a helper fails. Never guess an owner or overwrite the primary checkpoint.

The3090Ti remains reserved for Pizza Tycoon HD until at least07:00Phoenix AND
explicit user release, with no automatic expiry. Leave that project/session and
D: untouched. Source work proceeds concurrently; main grants heavy CPU jobs
sequentially below normal priority. GPU/live capture stays blocked by the hold.

Session organization is complete; seven-stage remaster acceptance is not.
No stage-clear, final-art, audio or in-game ray tracing acceptance is implied.
