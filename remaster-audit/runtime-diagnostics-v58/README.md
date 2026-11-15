# Frozen v58 diagnostic and complete continuation evidence

Current status: [canonical runtime/seven-stage handoff](../../docs/RUNTIME-CONTINUATION-20261113.md). **Not an installed release, not completed E2E gameplay, and not a stutter/audio fix.**

This curated package contains exact v58 source snapshots and headers in new/, three source diffs, the generator, actual extracted CPU fixture/runner, offline phase analyzer, final check receipts, integration-build metadata, bounded live runner, all stage checklists and key files, and route documentation. manifest.json hashes every exported file and identifies its original local source. rejected/ preserves the integration name collision and false-positive scanner controls; these are excluded failures, not passing evidence.

The original local recipes are deliberately preserved unchanged. They require the canonical C:/github/Einhander workspace, upload-index-hitch worktree, installed Clang/SDL/Vulkan toolchain, exact v47/v54/v57 baseline recipes and151 local linked objects. The host scanner also reads the v57 bases. A clean clone alone cannot replay those local link inputs. Source snapshots and diffs are reviewable here; full executables, generated code cache, ROM/BIOS/cards, artwork packs, full system traces and bulky raw capture files are **local-only**. Their location/status/hashes are indexed in local-evidence-index.json. Do not distribute or transplant the private binary/cache.

On the existing canonical host, run_host_test.py runs the actual extracted core/handler at below-normal priority. It writes host-test.json/work outputs. syntax_check.py compares full TUs against exact local baselines. local-recipes/build.py reproduces the local pinned three-object replacement build; it does not install anything. local-recipes/run_frame_phases.py prepares/runs a private bounded game; read its candidate metadata and the canonical handoff before execution. Do not start games or compile jobs while a CPU/GPU reservation is held by another owner.

Final executable (local): c2c386bd1f0ea59d84f8e95f1a1103cb777904f3eacaacad0c8e4013448145a6. Final checks: host/default16384/disabled/unbound and9 mutants pass; full3-TU compile/link pass. v58 first live attempt passed title GPU/API gates but lost focus after3seconds and was rejected/closed. Observed-focus retry is prepared, not run. v57-comparison-summary.json records the still-failed85/184ms pair and703 starved sample frames. No result establishes foreground smoothness across all seven stages.

capture-checklists/ copies planning snapshots unchanged, with exact key lists. S7's formerly external key file is copied as capture-checklists/keys/S7-gate-keys.txt; count26 and source hash are verified. References in code spans to authoring-lane tools/data remain local prerequisites, not missing published binaries. routes/ documents continuous-play constraints and the already completed frontend checks' original plan. The canonical handoff supersedes historical pending-state wording in those dated planning snapshots.

See verification.json for exported-file hash checks, source/receipt consistency, key-list counts, changed-entry-point links and publication checks. Documentation verification is not E2E game acceptance.

Archive paths preserve original line endings and whitespace for byte-for-byte hash verification; they are not reformatted. Authored documentation is checked separately for whitespace.

Expanded independent documentation audit: [verifier source](../verify_documentation.mjs) and [results](../../docs/media/gallery/documentation-verification-results.json). These remain at canonical repository paths to avoid recursive hash reports. source-verification-manifest.json and make_verification_manifest.py preserve Claude’s additional source-bound crosschecks.
