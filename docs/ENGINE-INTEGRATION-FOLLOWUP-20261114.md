# Actual CPU build failure and engine source followup â€” November 14

The granted Remix CPU build starts at 20:24:36 UTC and passes C++ syntax checking in 1.382 seconds. Object compilation then exits1 in 0.048 seconds: the builder combines a relative output path with that same directory as its working directory, so the output path is resolved twice. Linking, the 65 CPU controls and guard77 never run. No object, executable, Remix DLL, game or GPU execution results from this attempt.

The original wrapper34344 and builder42144 exit1 after 1.629 seconds. Its immediate gate reads 50.1% CPU and 57.36 GiB available memory; the wrapper uses CPU15, BelowNormal and a 120-second owned-tree deadline. This approved older wrapper has **no hard Job memory cap**. Its final receipt reports an empty Job and absent tree. Root independently verifies source/receipt hashes and the two recorded PID/creation identities are absent. Compiler creation times were not retained, so those identities are not independently replayed. [Original receipts and root readback](../remaster-audit/engine-integration-followup-20261114/README.md).

The old builder and failed outputs remain intact. New builder `b0e08a6aâ€¦` resolves the output root once to an absolute path and checks its copied source hash. The complete 31-line change is reviewed; source/header/flags/oracles are unchanged. It awaits a new resource grant and the normal native permission check. The earlier denial and 66.1% no-child refusal remain separate historical outcomes. A routine path correction within authorized work does not itself require another user approval question. A real permission rejection must still be respected.

The prior single granted pure-data adapter run remains **21/21 passed**. It is not a game or GPU result. [Executed controls](CPU-ENGINE-SOURCE-CONTINUATION-20261114.md).

## Read-only adapter collector

The new [collector](../remaster-audit/owned_gl_adapter_observation.py) retains the owned process handle, checks executable/PID/creation identity, rejects ambiguous listeners and binds the actual connected TCP server/client tuple to the owned PID before sending a fixed read-only query. Two explicit `gl_present_ring(n=1)` samples feed the tested validator. Replies have a two-second deadline and 16 KiB bound; invalid UTF-8, duplicate JSON keys, nonfinite constants and overflowing floats are rejected. The startup log's file identity must remain consistent.

Claude reviewed both revisions. The revised collector has AST/hash verification only: no real process lookup, socket query, unit run or game qualification. Its proposed controls use doubles and small owned files; they remain unrun. Future integration must also preserve the launcher's command-audit contract. OS metadata calls still require the external Job watchdog; a deadline checked after a Windows call cannot interrupt that call. File identity alone does not detect an in-place rewrite, and the offline core validator alone does not attest connected-peer observations. These limits remain explicit.

## Geometry, materials and presentation

The [ownership decision](REMIX-TRANSPORT-OWNERSHIP-DECISION-20261114.md) assigns immutable frame descriptions to the native producer and persistent mesh IDs/cache/SDK resources to the consumer. A busy pending slot cannot overwrite another owner's frame. Native geometry cannot be suppressed until the exact frame/generation has a completed Remix image and matching overlay order. Failed, dropped or late work must retain a complete native fallback.

Source review finds and corrects two material/geometry errors before integration: overflow must be recomputed before narrowing coordinates, and raw textured polygons retain per-texel STP transparency. The T1 oracle now models native UNR division and saturation with proposed boundary controls. Its first builders also mishandle CRLF source anchors; a new driver normalizes only after verifying raw hashes. No T1 controls have been compiled or executed.

The retained scene capture records textured polygons only. Other geometry types are counted without full ordered records, and its ordinal is a textured index rather than a global command index. Its `complete` flag means a command interval, not full renderer coverage. Therefore the current stream cannot establish safe live composition or full draw coverage. A new T2 CPU implementation proposal is delivered at20:36:57 with49authored checks; root review, compilation and execution are still pending. Diagnostic subset output must never authorize native suppression. Full ordered capture, source transforms, material semantics, actual images and lifecycle qualification remain implementation work.

The last actual modern Remix GPU probe still fails with black images and an overlong shutdown. Syntax, plans, API returns and CPU controls do not establish working ray tracing or DLSS.

## Logger, audio and texture work

The HD proof observer r3 fixes the reviewed cap-marker, close-failure and append-offset logic in source. Its exact-block 36-check I/O fixture and driver are prepared, not compiled or run. Full renderer integration, material generation/dedup/epoch controls and rendered appearance remain open. Native CRLF baselines and LF patches must be handled explicitly; earlier scratch post-patch hashes are withdrawn as integration pins.

Claude also drafts a combined audio proposal: one locked snapshot for old stats and gap counters, a snapshot inside the existing push lock, event reporting after unlock, and lifecycle generations to reset stale baselines. Earlier volatile/racy reference tests are rejected and preserved. The combined proposal and fixtures still need full review, compilation, real SDL qualification, PCM comparison and listening. No audible improvement, complete race fix or performance gain is claimed here.

The menu measurement tool now separates thin-font interiors, contours and counters in fixed manual regions. Its source is cleared only for a future bounded three-key measurement. Claude discloses that r6 synthetic checks, and earlier v2 checks, ran without scheduling grants. Existing stdout/exit reports are preserved; PID, creation, priority, affinity, memory and exact timing remain **unknown**. Those runs count as neither accepted measurements nor resource qualification. No art input was decoded or repaired in them. [Original disclosure](../remaster-audit/engine-integration-followup-20261114/claude-ui/UNGRANTED-SELFTEST-DISCLOSURE-20261114.md).

Root continues from C: without touching the other project's recovery drives. Other heavy/GPU/game/Comfy work remains held outside fresh narrow grants. Monitor39248 is observed at 20:18:17.452 UTC and bounded to 20:48:16.554; it proves metadata monitoring, not uninterrupted model activity.

Still unfinished: distant signs/buildings and other texture defects, readable menus/HUD, realistic player/enemy/boss/weapon/effect skins and selectors, mini-boss pacing/audio and listening, actual engine/Remix rendering, all seven stages and delivered release/rollback. [Current acceptance scope](RUNTIME-CONTINUATION-20261113.md). Hash/link/JSON checks are integrity checks, not visual or gameplay acceptance.
