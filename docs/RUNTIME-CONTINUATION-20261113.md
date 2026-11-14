# Runtime and seven-stage continuation — November 13, 2026

**The remaster, full-stage E2E testing and audio acceptance remain incomplete.** This is the current handoff after the reboot. Work from `C:/github/Einhander`; older D: paths in dated receipts are historical. The user requested light tests, usable Windows, work with Claude on all seven stages, and actual-results publication. The latest steering prioritizes complete verified documentation and continuation with the remaining usage.

## Current state and safe resume

No owned test game is running. CPU-QUIET and GPU reservations were released. Do not interpret a prepared candidate as an executed test. The observed-focus v58 retry is prepared but **not run**. The user authorized retry/continuation (relayed through Claude). The observed-focus retry remains unlaunched at this documentation checkpoint; it may record focus changes while keeping Windows available, but mixed/background focus cannot establish foreground performance acceptance. No additional permission response is required for the authorized bounded retry.

Canonical latest data: [actual runtime results](media/gallery/stage1-display-history-results.json), [Stage 1 status](STAGE1-COMPLETION-STATUS.md), and the [frozen diagnostic package](../remaster-audit/runtime-diagnostics-v58/README.md). Source/code checks, diagnostic gameplay and release acceptance are separate gates.

The normal installed executable is still SHA256 `b287ddfa4dfc0fc80dcbf16f8809da12122078b31b6a0c8f0c9e19914d030134`. No experimental executable or artwork replaced it. Four normal/forensic launch source edits and the ignored Play-HD launcher/receipt edits were applied locally with rollback copies. Normal material launches now use that existing runtime and its own cache; material and Play-HD share settings. Current settings SHA256 is `68f831cda591f1b5649714f9b8895ed2962f66436d3452906a7019f950d75f20`; current material receipt SHA256 is `8c2a0376fea9618cf5194df499a3c5d23edbe7addf0b13269f70217ebab50b2c`. Replacing the executable requires renewed receipt verification. The older receipt hash in a run records what existed at that run, not today's receipt.

Rollback/application receipts are local under `remaster-audit/dev-center-evidence/stage1-completion-20261112/normal-launch-readback-hotfix/`. User cards were not mounted by the private tests. Do not delete private evidence, copy a foreign-binary cache into a runtime, relax native qualification, or change user cards/settings to make a test pass.

Use GPU queue reservation and a fresh manual Claude process-inventory quiet acknowledgement before timing. AudioSR stays off (`remaster-audit/audio-enhancement/work/V2-GPU-STOP`). The user's RTX 3060 / ComfyUI 8189 project is unrelated and must not be changed. GPU0 RTX 3090 Ti is shared with authoring on 8188. New artifacts stay on C:. Prefer sequential, below-normal CPU builds; no heavy ETW capture or full-function nonleaf live shadow work.

## What the actual runs establish

- Continuous display-history capture previously performed two synchronous GPU readbacks per vblank. Two independent profile parsers attributed about 25.7% of fight main-thread samples to that readback. The source now requires exact `PSX_DISPLAY_RING=1`; normal launches choose0, forensic launches explicitly choose1. One-shot capture remains available. This source change is in the draft PR; existing local normal launchers enforce0 without installing a new executable.
- Existing normal Play-HD, installed964-PNG pack, scale2 and rewind50/15:120-second assisted test, zero new gameplay starvation,350 consecutive boss-window submissions, p95 17ms/max21ms. Saved Aurora/Crimson material state on the same runtime/own cache:60.0072fps, zero new starvation, max20ms in that window. These are bounded assisted checks, not unassisted stage clear or listening acceptance.
- Former material runtime f018 failed with15,378 new starved output sample frames. Its empty cache and missing toolchain were observed; cache absence alone is not proven causal. The tested b287 binding now has rollback and shared-settings notes.
- Real frontend Play-button handoff passed in private r3, exit0/port closed. Earlier r1 helper error and r2 close-guard rejection remain excluded. Crimson, Gold and Neon shortcuts each passed configured title state and five seconds of early gameplay without RAM writes/state loads. One retained frame per pair was inspected. Other scenes, all15 profiles and whole-stage appearance remain unqualified.
- Larger frozen1669-PNG candidate:39 boss-window HD uploads/~801MiB, including29 reuploads. Private bounded5GiB retention removed repeat uploads, but169ms and94ms gaps remained. No such candidate is installed.
- v57 same-binary buffered-upload pair: both real GPU pixel/state-restore selftests passed; both350-frame nominal boss windows happened to max17ms. Whole measured runs still failed smoothness: OFF max85ms/zero new starvation; ON max184ms/+703 starved sample frames. Exact OFF raw-VRAM `glTexSubImage2D` wait58.2742ms atframe6596 fell inside a75ms presentation interval. ON removed slow native-helper calls, but other waits remained. Two64MiB first-use HD uploads preceded the184ms gap; that correlation does not prove the wait's cause. Input/handoff timing differed, preventing a causal regression estimate.
- Frame numbers and submission sequence stayed continuous. Display pages alternated in both boss windows and across the184ms pause. This supports late delivery; it does not prove unique framebuffer pixels or physical scanout of every submitted frame. Recorded video also missed capture frames, while recorder-free game stalls independently persisted.

Exact unchanged12-second callback excerpts and their offsets/hashes are linked in the runtime results. Callback PCM is captured before the physical device; no claim of hardware audible quality or subjective listening acceptance is made.

## v58: built and checked, gameplay timing still unaccepted

Frozen executable SHA256: `c2c386bd1f0ea59d84f8e95f1a1103cb777904f3eacaacad0c8e4013448145a6`. Main source5c94d2dd…, renderer90c6a4e1…, debug3217e4d7…, headerc307ae7f…. Full hashes,151 pinned link inputs and compile arguments are in the package. Only main/GPU/debug objects were replaced; no new collision/CPS or lock-free-audio object was added.

The opt-in `PSX_FRAME_PHASE_RING=1` records raw CPU QPC timestamps,16384 rows, actual post-housekeeping frame IDs and exact SDL swap boundaries. No GPU read/query/fence, new thread, pacing change or render-order change is added. Foreign-thread hooks return through TLS before shared state. The default disabled path performs no QPC reads or allocation. Retain validity flags and exclude open, unclosed, multi-swap and alternate-pacer rows from precise normal-mode analysis. A query may see a current open row; global last_open0 is not required.

Checks passed: actual extracted ring/handler; default16384 capacity; disabled/unbound cases;9/9 mutation controls; corrected file-scope collision scan; full three-TU compile and C++link. First integration compile failed because a phase variable collided with the existing fingerprint ring. The distinct-prefix fix passed. A later scanner falsely counted local variables/calls as globals; its failed output and positive control are preserved. Passing isolated tests did not bypass full compilation.

The first live v58 attempt passed title GPU selftest (8 cases/2048texels, all mismatch/error counts0, state restored) and phase API ownership/capacity checks. It retained3 foreground samples, then lost focus and stopped: exit0/port closed, timing rejected. Its failing sample/phase tail was not retained; the revised runner now preserves the rejected sample and at most4 read-only failure-tail queries before cleanup. The revised observed-focus retry is prepared only. Neither attempt proves the stutter fixed.

## E2E gates still open

1. Reproduce and attribute the remaining >25ms pauses using the v58 phase records. Require complete relevant rows, true frame mapping, valid flags and consistent QPC frequency. Pre-swap interval ending atF includes Swap(F−1), not Swap(F). The [analysis contract](../remaster-audit/runtime-diagnostics-v58/analysis-contract.json) specifies the non-overlapping partition. Outside-vblank means guest plus other work; QPC wall time does not distinguish busy CPU from descheduling by itself.
2. After evidence identifies the wait, change one reversible factor and compare actual total tails/audio. Buffered uploads reducing an API timer alone is not success. Do not blindly forgive pacing debt; previous forgiveness produced chronic under-speed audio starvation. Upload budgets can cause visible native/HD pop-in; prewarming/quality changes require explicit private labels and visual checks.
3. Verify normal launcher and saved material, ordinary-input full-stage play, boss approach/fire/death, native FMV, actual listening and device audio. Repeat only for changed code, failures or unresolved concerns. No claim of a universal60fps guarantee from one ordered pair.
4. Exercise death, Continue, restart, results, a separate Game Over, save/load/card identity and actual rewind use. Snapshot counters are not proof that rewind loading was tested. Do not mount user cards for private tests.
5. Qualify all seven stages, alternate craft/loadouts, boss/effect/palette states and final outcomes, then install a versioned release with rollback and verify the normal delivered launcher. The draft PR is unmerged and no full-remaster completion percentage is established.

## Seven stages: exact missing capture work

The [published checklist index](../remaster-audit/runtime-diagnostics-v58/capture-checklists/INDEX.md) and companion key files preserve the detailed acquisition criteria. These are planning/source requirements, not evidence that the stages ran.

- Stage1:23 Drache flash CLUT keys; actual eye/side-gun GP0 and inferred sprite cell; live A/B of11 candidates/195 keys. Host-polled VRAM reads do not guarantee every-frame capture. A previous reference reached the Stage2 load nearframe40622 (~13min); this is a reference, not a newly completed chain.
- Stage2:39 gate keys,60 unknown palette phases,119+16 source-completeness keys, full-rate replay and ground crawl. Normal-pack later-stage native-cache coverage remains unknown.
- Stage3:39 gate keys, wall motion/UV cells and competing CLUT positions. No new live acceptance.
- Stage4:11 exported gate keys plus233 renderable-later keys, effects/look inputs and shared panorama05E1881C. Capture shared work once with Stage5.
- Stage5:12 rendered gate keys plus245 renderable-later keys, Dürer8bpp hull regions, palette/look decisions and shared panorama. The checklist's panorama count distinguishes a zero CLUT; preserve exact key files instead of summing captions into completion percentages.
- Stage6:101 manifest keys (83+18; older ledger says83+21 and remains a documented discrepancy), residency/part masks/animation, plus a separate deliberate timer-failure AQ-13 outcome pass. Static smoke comparison is not live play.
- Stage7:26 gate keys, planet/backdrop/fleet and explosion/transmission/hull CLUTs. S7 key file is included in the package; its source SHA is verified in the manifest. Shared page704,256 is captured once across S6/S7.

[Route constraints](../remaster-audit/runtime-diagnostics-v58/routes/STAGE-ACCESS.md): the US build has no ordinary pad shortcut or mid-game stage save; use continuous play from boot. Do not use RAM stage jumps, state-load shortcuts, a lives lock or a cache-qualification bypass. Current timer assistance is the disclosed countdown-byte-only180-second bounded lease, used for diagnostic capture, not acceptance; do not silently turn it into an unlimited chain. Normal pad play remains authorized. Record a blocked stage and retain all evidence. Capture entry/mid/boss overlay namespaces and qualify missing native pages on the exact executable before admission.

## Exact next action for Claude/Codex

Read the [package README](../remaster-audit/runtime-diagnostics-v58/README.md), final HANDOFF and manifest; verify hashes before running. All original source, scripts, checks and rejection controls are included or explicitly indexed as local-only. Do not run a local reconstruction recipe as if it were a portable clean-checkout release build.

The prepared local run is `remaster-audit/dev-center-evidence/stage1-completion-20261112/display58-phases-observed-r2/hd-on_rewind-on/candidate.json`, using `sampling-build-v58-frame-phases/run_frame_phases.py`. It permits Windows use, records focus changes, has no foreground-performance acceptance and stops on sustained no progress. A foreground run instead keeps the strict focus gate. Use the authorized explicit diagnostic mode; reserve resources, obtain a fresh manual quiet ACK, run one bounded leg, retain phase/present/native/audio data, close/verify the owned process, release reservations, analyze offline and publish actual results. No run is currently active.

Local durable state: `remaster-audit/stage1-completion-20261112/execution-state.json`. Root publication branch: `codex/display-history-opt-in`; [draft PR1](https://github.com/Ghenghis/Einhander-HD/pull/1). Do not mark the overall work complete when a component, source package or document check finishes.
