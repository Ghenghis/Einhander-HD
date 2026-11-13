# Developer orientation

## Layout

- `windows-x64/`: active game integration, modified runtime/framework, launcher and development tools.
- `macos-arm64/`: separate platform snapshot; current feature parity is unverified.
- `remaster-audit/`: authoring, source registration, composition, capture and verification code and selected workflow graphs.
- `tools/coordination/`: workspace-scoped Hermes inbox helpers.
- `docs/`: public gallery, comparisons and development notes.

The framework/UI trees are inline copies. A recursive submodule clone does not reconstruct their historical pins. Their licenses and third-party notices are retained.

## Local build

Use your own original game dump and create a local `game.toml`. Machine-specific configuration and generated game C are excluded. A clean-checkout game build has not yet been verified.

Read [framework prerequisites](../windows-x64/psxrecomp/docs/BUILDING.md), [game-project setup](../windows-x64/psxrecomp/docs/GAME_PROJECT_SETUP.md) and the [local code-generation SDK](../windows-x64/psxrecomp/docs/LOCAL_CODEGEN_SDK.md).

Inspect the CLI without generating game data:

```sh
python windows-x64/psxrecomp/psxrecomp_cli.py --help
python windows-x64/psxrecomp/psxrecomp_cli.py generate --help
```

For a configured local game project, from its platform directory:

```sh
python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . --disc "disc/Einhander (USA).cue"
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime
```

Generation requires the emitter/toolchain and local disc/BIOS setup described by the framework. The game CMake files reference `assets/psxrecomp.ico`; supply that local icon or adjust the local build configuration. Some authoring scripts also require local staging data and model installations, which are not bundled.

## Asset acceptance

1. Capture the native source and actual draw context.
2. Verify raw words, palette, validity, native decode and used UV region.
3. Author against the registered layout; preserve PSX alpha/STP categories separately from RGB.
4. Compose a fresh candidate with unrelated keys and private writable state preserved.
5. Observe the native UI/game route before capturing.
6. Review visibility, close/distant movement, palette changes and seams.
7. Measure timing/audio under controlled conditions and record limits.

`build_facade_ab_candidates.py` and `run_facade_ab_probe.py` are local pilot tools, not portable installers. Their evidence/reference images stay local. `native_ui_facade_route.py` refuses unknown scenes and retains route proof. Its fixture tests require the hash-pinned local native PNGs, so they are not standalone clean-checkout tests.

The facade motion experiment is source-specific and disabled by default. Its GPU regressions preserve alpha categories and nonmatching/default rendering; those checks do not establish live quality or performance. The passive pacing collector also has offline fixtures, distinct from actual quiet-GPU runs.

## Public media and changes

Publish deliberately selected media with provenance under `docs/media/gallery/`. Keep raw dumps, full packs, saves, credentials, model weights and generated game/BIOS outputs local.

The matched facade uses the generated [neighbor RGB master](media/gallery/h24-neighbor-material.png), authored at 1254 × 1254. `build_h24_matched_facade.py` registers it at the verified neighbor source rectangle, preserves native alpha classes and checks that all 1,195 preceding keys are unchanged. It packs at 4096 × 4096 without claiming new native detail. `run_h24_matched_flypast.py` reuses the private no-fire route and declared timer-only aid. These local pilot tools depend on the existing private parent candidate, source guides, native route fixtures and game setup; they are not clean-checkout installers. Preparation and capture use immutable run directories and refuse overwrite.

```sh
python remaster-audit/build_h24_matched_facade.py --check
```

That command verifies an existing local matched candidate without launching the game. The [in-game results](H24-IN-GAME-RESULTS.md) distinguish the captured implementation from later CLI-only publication changes.

Use focused commits for runtime changes, authoring/verification tools and documentation/media. Record actual validation and limitations. A passing fixture establishes that fixture's result, not whole-game coverage.

## Stage 1 completion work

The [completion status](STAGE1-COMPLETION-STATUS.md) separates verified components from the remaining release work.
`run_stage1_pacing_ab.py` creates fresh private HD/rewind diagnostic legs. Select a new
`--batch`; `--gpu-queries 0` permits observer controls. `--guest-frames` bounds the
amount of emulated progress, without promising an identical scene or input replay.
Both the recorder and survival aid stay off. Its private build and route fixtures
are required; this is a local diagnostic, not a clean-checkout benchmark.

`build_stage1_sampling_probe.py` builds a private executable and separate hidden-GL
checks from pinned local objects. The world sampler is explicitly opt-in through
`PSXRECOMP_HD_WORLD_SAMPLING=1`. It affects admitted green-atlas/facade RGB sampling;
categorical alpha remains at level zero. No live performance improvement has been
established, and this option is not a production default.

`run_robin_stage1_acceptance.py` starts Robin through its HTTP API behind a
command boundary that rejects RAM writes and state loads. It keeps invincibility,
turbo and rewind off, uses private cards, records ordinary pad decisions and
observations, and requires an independent stage-clear review. A local `STOP` file
ends its bounded run. Both RAM position candidates failed live qualification and
`position_lane` was removed. The opt-in `draw_lane` reads completed-frame Mk.II
hull geometry; its revised respawn handling still needs full-stage qualification.
Alternate native craft selection verifies a distinct label after every down
input and rejects the Mk.II geometry controller for other craft.
The optional source-capture run is
separate from recorder-off acceptance and has explicit native recording bounds.

`build_stage1_frozen_candidate.py` composes a hash-pinned plan into a new private
pack. Exact sign crops retain other artwork on shared pages. Candidate replacements
break parent hardlinks atomically; all parent PNG hashes are checked afterward.
It rejects changed inputs and never installs a candidate. Frozen input revisions
and the local source proofs must be supplied separately.

`extend_stage1_actor_plan.py` pins delivered actor exports and verifies full-page
and derived-strip native CRC identities before composing a fresh private pack.
Derived upload occurrences remain explicitly unobserved; transparent null
palettes retain native fallback. The current assembled pack still awaits live
acceptance and installation.

Private GL tests and capture launchers require a GPU reservation, no holder and
an empty ComfyUI queue. HTTP errors, timeouts, changed reservations and expired
holder locks are refused. A coordinated CPU-quiet window is also required before
attributing performance changes while art exports are running. The opaque HD
batching and CPU attribution flags remain opt-in; actual measurements and their
limits are recorded in [Stage 1 runtime results](STAGE1-RUNTIME-RESULTS.md).

For targeted native extraction, `run_robin_stage1_acceptance.py --sources
--source-cache-keys DB715733,B24C6DA2` retains only those raw-upload CRCs from
boot. The optional shortlist accepts at most 32 CRCs and rejects malformed
settings. It keeps the existing 256-slot/32-MiB source-cache bounds; unrelated
uploads cannot evict a requested original. An empty setting preserves the
unfiltered LRU. This is authoring-only and does not enable capture by itself.
`verify_native_source_capture.py --keys` can verify an explicit full-key subset;
unrequested sources are not thereby accepted.
