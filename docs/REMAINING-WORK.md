# Remaining work and completion gates

> Current reboot/runtime/E2E handoff: [verified state and all seven-stage continuation](RUNTIME-CONTINUATION-20261113.md). Work from C:/github/Einhander. Full gameplay/audio E2E is incomplete; the dated detail below may describe earlier experiments. Read the linked current scope before resuming.

November 13, 2026. Stage 1 and the full remaster remain incomplete. There is no
verified whole-project completion percentage or reliable final delivery date.
Claude has claimed twelve durable production/review workstreams; a claim is not
a completed deliverable. The detailed brief is
[the Claude execution backlog](../coordination/CLAUDE-WORK-QUEUE.md).

- **Runtime and audio — Codex with Claude review.** Normal installed-pack bounded tests now have zero new gameplay starvation and boss-window maxima21ms (Play-HD) and20ms (saved material). Normal launchers disable continuous forensic readback; the material receipt uses the tested existing b287 runtime/own cache with rollback. The larger frozen artwork still fails: v57 OFF/ON full-run maxima85/184ms, ON703 starved sample frames. v58 raw CPU phase capture builds and passes source checks; its first live timing attempt was rejected after3seconds for focus loss. The next diagnostic is prepared, not run. Foreground/unassisted full-stage, listening, FMV, progression and all seven-stage acceptance remain open. See the canonical handoff for exact hashes, failures, evidence and the smallest next test.

- **Robin and progression — Codex, with enemy/weak-point review from Claude.**
  Actual targeting, firing, weapon pickup and evasion are observed. Lives are
  still lost; Greif defeat and Stage 1 clear remain unverified. Complete boss,
  post-boss, death/Continue/restart/results/save/load and a separate Game Over
  route before ordinary-input stage acceptance.
- **Environment, signs, players, pods, enemies and effects — Claude; integration
  and in-game acceptance by Codex.** The full facade footage is published.
  Remaining revisions include lights, metal/road/atlas details, lettering
  and palette phases, player/pod states, enemy parts and effects. The delivered
  electric-arc binding still needs integration. Every asset needs native
  UV/alpha/palette checks and actual visual acceptance.
  W4 world/menu/player/signs-HUD revisions have been delivered for review;
  these are not integrated or accepted. The earlier searchlight-beam texture
  identification was corrected: current evidence points to untextured polygons,
  so a texture replacement cannot yet be claimed to improve those cones.
- **HUD and menus — Claude; capture and acceptance by Codex.** The latest scoped
  census leaves 133 HUD fade keys / 58 CLUTs after a 24-key delivery. Three
  reconstructed CLUTs still rely on individual CRC matches and need review. Finish available
  typography, selection, pause/configuration, Continue/Game Over, evaluation,
  rankings, save/name entry and warnings. Missing inputs require captures.
- **Remaining source acquisition — integration owner.** The current census reports
  218 Drache keys with source pixels for 141. The 128 post-Drache keys include
  Stage 2 material, with source pixels for 9; they are not all Stage 1 gaps.
  Five cloud keys and other named effect/strip sources remain outstanding.
  These are capture gaps in this census, not a count of all remaining art.
- **Ready-to-play release — Codex.** Reconcile one frozen pack, install a
  versioned runtime and artwork with verified rollback, test the normal launcher
  and Robin button, then repeat cold-boot gameplay and audible/visual acceptance.
  Current experimental runtimes remain uninstalled.
- **Later stages and full-game coverage — Claude's source/production backlog,
  with Codex integration and acceptance.** Continue acquisition and art beyond
  Stage 1, alternate loadouts, unlocks and end states, then verify the full game.

Immediate experiment results are reported when each owned run closes and its
evidence is checked. Art work proceeds in coordinated CPU/GPU windows. Final
timing remains gated by performance, progression, missing source acquisition and
actual acceptance; it cannot be inferred from artwork counts or area shares.

The [engineering handbook](handbook/index.html) and [handoff](handbook/handoff.html)
record exact private builds, source commits, rejected hypotheses and the next
integration steps. Devin has a dedicated tested observer-only connector and
[onboarding brief](../coordination/DEVIN-HANDOFF.md), but is on the user's explicit
hold until the user is home. Codex and Claude continue. On reactivation, actual
client discovery and inbox acknowledgement remain a gate; configuration alone
is not proof that he is synchronized or authorized to edit shared runtime files.
