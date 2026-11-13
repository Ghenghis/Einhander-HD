# Autonomous continuation protocol

Scope: finish the Einhander remaster; Stage 1 is the immediate acceptance
milestone. Current priorities include Robin enemy awareness, the requested 1%
audio correction live test, remaining artwork/UI and the release/rollback checks.

1. Read `CLAUDE.md`, the completion status and your actual Hermes inbox:
   `node tools/coordination/hermes-client.mjs inbox claude-einhander`.
2. Act on actionable messages. Acknowledge processed items with
   `node tools/coordination/hermes-say.mjs ack --owner claude-einhander --id ID --quiet`.
3. Continue a claimed task or claim the next eligible one. Coordinate immutable
   handoffs and shared GPU use with `codex-einhander`; do not overwrite their work.
4. Use a client Monitor for the streaming watcher if available. With ordinary
   background shell jobs, use bounded `--once --wait 40` and re-arm after each
   message/timeout: stdout alone does not prove a sleeping model was awakened.
5. Before a waiting turn, write `.hermes3d_orchestrator/continuity/claude-einhander.json`:
   `session_id`, `checkpoint_utc`, `phase: "waiting"`, nonempty `pending_task_ids`,
   `next_action`, and `continuation: {armed: true, monitor_task_id, next_wakeup_utc}`.
   These must describe actual client operations, not an intended future monitor.
   Keep the next wake within 30 minutes and rely on inbox delivery for urgent mail.
6. The Stop hook blocks unread actionable mail and uncheckpointed unfinished
   work. It allows a bounded, checkpointed, armed waiting turn. It cannot veto
   user cancellation, a closed client, API failure or operating-system shutdown.
7. On explicit user stop/pause, record `user_stop: {requested: true, reason}` in
   that checkpoint and release owned test resources. On resume clear that marker.
8. Completion requires the actual acceptance state plus evidence; a standalone
   component result must leave the overall project active. Do not silently exit
   after a handoff or after acknowledging a message.

Project hooks are in `.claude/settings.json`. Existing sessions must load the
changed hooks through their supported hooks UI or a controlled resume. Report
whether that happened; file existence alone is not proof of client enforcement.

The active Claude desktop session started in `D:/Games/Einhander`, while shared
coordination and current acceptance live in `C:/github/Einhander`. The canonical
guard explicitly accepts both roots. The D project must invoke the canonical C
hook and import its instructions; do not read an empty D mailbox as evidence
that no work remains. Canonical checkpoints and inbox stay in the C workspace.
