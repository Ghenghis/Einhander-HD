# Einhander project continuity

> Current reboot/runtime/E2E handoff: [verified state and all seven-stage continuation](docs/RUNTIME-CONTINUATION-20261113.md). Work from C:/github/Einhander. Full gameplay/audio E2E is incomplete; the dated detail below may describe earlier experiments. Read the linked current scope before resuming.

The user requires autonomous follow-through until the authorized project is
complete. Keep working without repeated permission questions. A component
handoff, successful test or message acknowledgement is not project completion.

- Read `coordination/Codex-HANDOFF.md` on startup, resume and compaction.
- Join this workspace's HermesProof as `Codex-einhander`; read and act on the
  inbox before work, during waits, after handoffs and before yielding.
- Keep foreground result waits bounded to30 seconds and interleave inbox
  checks; delegated jobs waiting on resources must not hide urgent mail.
- Claim eligible work and lock files before editing. Respect Codex's live game
  and shared GPU/CPU reservations. Choose independent work while resources wait.
- Drain `coordination/Codex-WORK-QUEUE.md` and your durable Hermes queue. A
  bounded waiting checkpoint cannot replace available independent queued work.
- Refresh your own task/presence with actual work and task IDs. The inbox
  watcher records only its connection health and must not impersonate you.
- Send concrete results with paths, hashes, actual checks and remaining work.
  Acknowledge processed messages quietly; never generate acknowledgement loops.
- Keep a durable checkpoint and an armed inbox monitor/next wake before a
  bounded waiting turn. A mail-watcher process is not evidence the model works.
- Do not end the overall session or mark the project complete while work remains.
  If a platform interruption occurs, preserve the checkpoint and resume it.
- Respect an explicit user stop/pause and real access limits. Never bypass
  permissions, fabricate scheduler receipts or claim uninterrupted availability.
- Preserve frozen artwork, failed evidence, unrelated edits and native alpha.
  Do not claim stage clear, resolved audio or an installed release without proof.

Current acceptance and backlog: `docs/STAGE1-COMPLETION-STATUS.md` and
`remaster-audit/stage1-completion-20261112/execution-state.json`.
