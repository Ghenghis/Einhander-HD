# Devin: synchronize before assisting

**User-requested hold, 2026-11-13:** keep Devin inactive until the user is home
later today. Do not prompt, run commands, edit files, claim tasks or resume the
old conversation while this hold is in force. Connector configuration may stay
idle. On reactivation, perform the synchronization below against the then-current
revision; the current inbox acknowledgement remains unverified.

The user asked for Devin to assist without resuming stale work. Start with
observation and coordination. Do not run the old pending command or resume an
old implementation plan.

## Canonical project

- Active checkout: `C:/github/Einhander`.
- Remote: `https://github.com/Ghenghis/Einhander-HD.git`.
- Current engineering handoff: `docs/handbook/handoff.html`; runtime findings,
  tests and open gates are adjacent HTML pages. Read the actual current Git
  revision and dirty state, not a revision copied from an earlier chat.
- The older `D:/Games/Einhander` folder was present but was **not a Git
  repository** when checked on 2026-11-13. Its files have not been deleted,
  overwritten or declared obsolete. Inventory/diff any useful work before a
  later import; do not bulk-copy it into the canonical checkout.
- The pre-existing generic Hermes MCP entry in the IDE points to another
  project. Do not use that entry for Einhander. Use `einhander-hermesproof`.

## First connection and proof

In this installed Devin build, the native MCP configuration is
`%APPDATA%/devin/mcp_config.json`, as verified from the installed app's path
service. The legacy Codeium/Windsurf file also exists but was insufficient for
this chat. The dedicated entry is enabled in the native file; exact local
backups preserve existing entries. A file change and successful SDK smoke test
do not prove the current chat has refreshed its tool catalog. Report actual
discovery before claiming connection.

1. Read this file and the HTML handoff. Confirm the editor workspace and the
   actual checkout path. Keep source work read-only during onboarding.
2. Through `einhander-hermesproof`, call `hermes_get_workspace`; it must return
   `C:/github/Einhander`. Stop if it does not.
3. Use actor `devin-einhander`. Read that inbox; acknowledge the synchronization
   message and reply to both `codex-einhander` and `claude-einhander` with the
   actual path, HEAD, dirty-state summary, understood restrictions and proposed
   isolated task. This reply, not a server entry or watcher process, proves a
   real agent has synchronized.
4. Publish honest reviewing/working/waiting presence with a short expiry and
   refresh it while active. Use bounded `hermes_wait_for_inbox` calls (at most
   40 seconds) while waiting for a reply; act on messages promptly. An MCP
   server cannot guarantee model wakeup or keep a closed session alive.
5. Claude coordinates work after the Codex handoff. Ask for a distinct task and
   read the current locks. Initial connector capabilities intentionally exclude
   file edits, locks/claims, command execution, workspace switching and release.
   Existing IDE tools are separate capabilities; do not use them to evade this
   onboarding boundary.

## Useful first work

Prepare a read-only inventory of the old folder: useful source changes,
documentation and evidence, with relative paths and hashes, compared with the
canonical files. Do not inspect credentials or private unrelated folders. Send
findings for review. Then take isolated tests, documentation reconciliation or
a bounded assigned code review. Shared runtime edits require a reviewed scope
and locks; release/push/install remains with the integration owner.

## Current acceptance and resource rules

The whole remaster and Stage 1 remain incomplete. Audio still starves; one
rewind classifier bug and the retained-batch boundaries have focused tests.
Neither means ordinary combat, boss clears, FMVs or the installed release pass.

Read CPU-QUIET and GPU-RESERVED before heavy work. Stop CPU compiles, image
exports and GPU/GL work for a measured game window; send a fresh quiet ACK.
Do not launch another game, touch a frozen pack, modify another agent's files,
kill processes broadly, relax byte/timing guards or restart the rejected
process-suspending gate. Preserve failed evidence and label assisted captures.

The user estimates limited Codex/Devin usage and greater Claude availability.
No remaining percentage or reset count has been independently verified. Keep
work and next actions durable rather than assuming any session stays alive.
