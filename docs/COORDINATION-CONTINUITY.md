# Project continuity

November 13, 2026. The project now has persistent Claude instructions and a
conditional Stop guard. Component handoffs leave the overall remaster active.

The launcher previously referenced missing `CLAUDE.md` and
`coordination/CLAUDE-HANDOFF.md` files. They now define startup/resume inbox
checks, quiet acknowledgements, task ownership, actual acceptance and durable
continuation. The shared hook is `tools/coordination/claude-continuity-hook.mjs`.

The active Claude desktop chat started in `D:/Games/Einhander`; shared mail and
current acceptance are in `C:/github/Einhander`. Its local D project settings
invoke the canonical C hook directly. Both project roots are explicitly accepted.
No duplicate empty D mailbox is used to decide whether work remains.

The guard blocks a voluntary stop with unread actionable requests or unfinished
work lacking a valid waiting checkpoint. Repeated Stop hooks do not bypass it.
A waiting checkpoint requires the current session ID, pending tasks, a next
action, a fresh checkpoint, an actual monitor ID and a wake within 30 minutes.
Explicit user stop/pause remains available; overall completion requires the
actual full-remaster acceptance state. Local state stays outside Git.

The inbox watcher writes separate connection health and retries stream failures.
It no longer overwrites the model's task/presence with a mail-watcher heartbeat.
Model hook activity and watcher health are recorded separately. Routine message
acknowledgements can suppress reply notifications to avoid acknowledgement loops.

Verification: eight Node tests cover unfinished work, repeated Stop calls,
explicit pause, completion, checkpoint expiry/session matching, actual mailbox
reads, acknowledgement filtering and notification throttling. A live bounded
inbox call succeeded. The active Claude chat produced fresh PostToolUse activity
and the re-armed watcher produced a connected health record. The D settings were
read back with direct canonical hook commands and no wrapper bypass.

These mechanisms support continued work and recovery; they cannot prevent a
user closing the client, API failure, shutdown or platform limits. Claude Code
also limits consecutive hook continuations without tool work. Its documented
[hook lifecycle and Stop behavior](https://code.claude.com/docs/en/hooks#stop)
remain authoritative. A running watcher alone does not prove an active model or
a completed project.

The user's subsequent request exposed an empty durable pending queue despite
the broad production backlog. Twelve owner-targeted workstreams are now queued,
with an execution brief in `coordination/CLAUDE-WORK-QUEUE.md`. Audio and stutter
root-cause reviews have highest priority. The guard also checks eligible queued
work and blocks an otherwise valid waiting turn while independent items remain.
Nine tests now cover this condition and exact owner/blocked/claimed filtering.
Recent message bodies are included directly in hook context. Activity and
checkpoint writes now replace files atomically, and JSON reads briefly retry
partial writes from other producers. Concurrent hook/read tests preserve
fail-closed behavior for persistently malformed state. Claude confirmed claiming
all twelve tasks, with nine active tracks; claims are not completed deliverables.
