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

Use focused commits for runtime changes, authoring/verification tools and documentation/media. Record actual validation and limitations. A passing fixture establishes that fixture's result, not whole-game coverage.
