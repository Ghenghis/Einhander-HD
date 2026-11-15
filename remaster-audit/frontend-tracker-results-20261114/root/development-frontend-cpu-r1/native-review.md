# Saved-material development route: source review (claude-einhander, 2026-11-14 ~15:52Z)

- Task: EIN-S1-SAVED-MATERIAL-ROUTE-REVIEW-20261114, from coordinator msg_48ff3d07.
- Scope: read-only source review. No canonical edit, and no test or game run.
- Root owns the implementation (msg_f07e372d, main claim 5fcdb1b0).
- `saved-material-development-route.r1-proposed.patch` in this folder only illustrates the findings below. It is NOT
  for application.

## Inputs (sha256 = the trace a3303aee pins, re-hashed 15:50Z)
- `remaster-audit/runtime-review/session-continuation-20261114/saved-material-development-route.patch`: 4b12e75a…
- `windows-x64/tools/launch_hd.py`: e4015831… (git: untracked)
- `windows-x64/tools/Start-Development.ps1`: bfdffa76… (git: modified)
- `windows-x64/tools/material_profiles.py`: 540584cf… (git: modified)
- `windows-x64/tools/launch_material.py`: 648ae54a…
- `windows-x64/tools/test_launch_hd.py`: 4837eef6…
- `Play-HD.cmd`, `Play-Saved-Skin.cmd`

## What the coordinator's patch preserves (PASS)
- **Preset validation.** `launch_hd.prepare_hd_launch` still runs:
  - `saved_selection`: pointer scope, descriptor sha and contract;
  - then `launch_material.prepare_launch`: detail receipts, pack manifest, source texture hashes and the runtime receipt
    with `verify_hash=True`.
  - An invalid saved preset raises. It never falls back silently to stock.
- **Explicit stock.** `--stock` skips the saved pointer, gives `explicit_stock`, and leaves an invalid pointer unchanged.
  This is the existing test.
- **No preset.** That case gives `no_saved_preset` and the stock environment, which clears inherited `PSXRECOMP_SKIN_*`.
- **The `--frontend` swap is unambiguous.**
  - The saved branch has already turned `--launcher` into `--no-launcher` (line 27), and the stock branch builds
    `--no-launcher`.
  - The swap runs before `game_arguments` are appended, so `.index()` finds the plan's own flag.
- **The command line comes from the validated plan.**
  - `arguments[0]` is the receipt executable for the saved preset (hash b287ddfa per the trace), or
    `build-release/Einhander_Recompiled.exe` for stock.
  - `cwd` is the project root, the same as before.
  - The saved path adds `--renderer opengl`; the stock path does not. Both behaviours already existed.
- **Values are consistent.** `PSXRECOMP_HD_TEXTURE_ROOT`, `PAGE_FALLBACK=1`, `DECODE_BUDGET_MB=256`, `CPU_AUTHORITY=0`
  and `EIN_DEBUG_PORT=4370` in `environment()` equal what Start-Development already sets. `PSX_DISPLAY_RING` is
  re-read from the inherited process, so an explicit diagnostic 1 is kept.
- **The JSON is safe to parse.** `json.dumps` uses ensure_ascii, and backslashes are escaped, so `ConvertFrom-Json`
  reads it correctly.
- **No new skin claims.** The patch adds no profile, key or mapping claim.

## Findings
**F1 (MUST): the override loop overwrites `-Port`.**
- `material_profiles.environment()` hard-codes `EIN_DEV_URL = "http://127.0.0.1:8094"`.
- Start-Development sets `$env:EIN_DEV_URL = $workspaceUrl` (port `-Port`, default 8094) and then applies every override.
- With `-Port 9000`, the bridge listens on 9000 but the game is told 8094: another service, an old bridge, or nothing.
- Fix: re-assert `$env:EIN_DEV_URL = $workspaceUrl` after the loop, or exclude that key.
- Test: a `-Port` non-default plan must keep `EIN_DEV_URL` equal to the workspace URL.

**F2 (SHOULD): it calls bare `python`, not the resolved interpreter.**
- The script resolves `$pythonCommand = Get-Command python.exe` and uses `$pythonCommand.Source` for the bridge.
- The patch runs `& python`, which can resolve differently: a PowerShell alias or function, or the Store stub.
- The preset could then be validated by a different interpreter or environment from the bridge's. Use
  `& $pythonCommand.Source`.

**F3 (SHOULD): there is no explicit-stock escape in Start-Development.**
- Before the patch, the dev game launch ignored presets. Now an invalid saved preset throws after the browser and bridge
  have started, so the dev game cannot start at all.
- Play-HD has `--stock`. Start-Development needs `[switch]$Stock`, forwarded as `--stock`, and the error text should
  name it.
- This keeps "fail visibly" and also preserves the explicit-stock semantics.

**F4 (LOW): the quoting guard is incomplete.**
- Every argument is wrapped as `"<arg>"`, which is correct for `Start-Process -ArgumentList` arrays (PowerShell does not
  quote elements).
- The guard rejects embedded `"`, but not a trailing `\`. Under MSVCRT/CommandLineToArgvW rules, `"C:\dir\"` escapes the
  closing quote and swallows the next argument.
- The plan's paths are files today, but forwarded `game_arguments` could be anything. Also reject `EndsWith('\')`.

**F5 (LOW): `Start-Development -Check` does not validate the preset.**
- It returns before any launch plan, so a broken preset is found only at real start.
- Suggest `-Check` also prints `launch_hd.py --check --frontend [--stock]`, without launching.

**F6 (LOW/INFO): environment scope.**
- `[Environment]::SetEnvironmentVariable(...,'Process')` with an empty value DELETES the variable, while the Python
  launcher sets `NAME=`. These are equivalent only if the runtime treats empty as unset. The design intends that, but
  it has not been checked in the runtime getenv sites here.
- In an interactive session, the new `PSXRECOMP_SKIN_*` values persist in that shell after the script ends. The HD
  variables already did this.
- Root's choice: scope them, or document the behaviour.

**F7 (LOW): which plan was launched is not visible.**
- Print `selection_source`, profile and enemy profile before `Start-Process`, so the user sees whether a saved preset or
  stock started.
- This makes no new claim; it only echoes the validated plan.

**F8 (INFO): time-of-check vs time-of-use.**
- The receipt hash is verified at `--check` and the executable is started a moment later by path.
- That is acceptable for a dev launcher. Note it; do not claim the hash was verified at launch.

## Tests (reuse existing sources; no pack, GPU or game)
The illustrative patch adds `test_launch_hd_frontend.py`. It reuses the `HdLaunchTests` setUp/save fixtures and
covers six cases:
- a saved preset gives `--launcher` once, the receipt executable and a verified hash;
- no preset gives a stock launcher;
- explicit stock with an invalid pointer leaves the pointer unchanged;
- a changed descriptor still raises;
- game arguments come after the validated arguments;
- `main(["--check","--frontend"])` does not launch and passes `frontend=True`.

None of these were run, because a run needs a grant. The PowerShell side has no unit test; F1/F3/F4 need either a
dry-run mode or a Pester case.

## For root's implementation (msg_f07e372d): cases I will check once its source is published
| Case | Expected |
|---|---|
| saved valid | receipt executable, `--launcher`, hash verified, profile echoed |
| saved invalid | throws with the error JSON, names `-Stock`, no game process |
| `-Stock` with a pointer present | `explicit_stock`, pointer untouched |
| no preset | `no_saved_preset`, stock executable |
| wrong receipt or a different executable | throws, no fallback |
| `-Port` non-default | `EIN_DEV_URL` equals the workspace URL |
| argv | no stray quotes, no trailing backslash, cwd = project root |

Plan validation should run BEFORE the browser and bridge start; root says it does this.

## Addendum ~15:56Z: root's implementation (files rewritten 15:52:25Z, read-only)
Files read:
- `launch_hd.py`: 08f590ec8d49f7069b5dfce558f343c32d1f1043f08587d91963df5a80ce77ed
- `Start-Development.ps1`: 9bc1646bd07ef5308cb2e53f3a2aa6ea16e56e86a6b9e0e79ca32fef000af0b6
- `test_launch_hd.py`: 6b69cb84c1343bf3cc21edf787f159b706816b82af89f2d2bcf615e9f26bd846
- `material_profiles.py`: unchanged, 540584cf

Neither the coordinator's patch nor my illustrative patch applies to these files; both targeted the old pins. That is
expected.

**Fixed or covered**
- The `--frontend` flag is chosen inside each branch rather than swapped afterwards.
- `$pythonCommand.Source` is used (F2).
- The plan is validated before the bridge and browser start.
- `-Check` now validates the preset too (F5), though it does not print the selection source.
- The plan sanity check covers ok, game_launched and argument count.
- Python tests cover:
  - the frontend saved-preset plan, equal to the direct plan except the launcher flag;
  - the stock frontend;
  - an invalid saved preset raising;
  - explicit stock with frontend;
  - `--check --frontend` not launching.
  My proposed `test_launch_hd_frontend.py` is therefore redundant; drop it.

**Still open**
- **F1 (MUST): open.** `Start-Development.ps1:77` sets `$env:EIN_DEV_URL=$workspaceUrl`, and lines 84-86 then apply
  overrides that include `EIN_DEV_URL=http://127.0.0.1:8094` (`material_profiles.py:175`).
  - Consumer: `recomp-ui/src/common/backends/imgui/launcher_devtools.cpp:349,360`, which builds "Open development
    workspace" and the section links from it.
  - With `-Port 9000`, every launcher link opens 8094 instead.
  - Fix: assign `$env:EIN_DEV_URL = $workspaceUrl` after the override loop, or skip that key.
- **F3 (now MUST, since validation moved earlier): an invalid saved preset blocks the whole development workspace.**
  - It throws before the bridge starts, so the workspace used to fix presets cannot start without `-WebOnly`, and there
    is no explicit-stock path.
  - Add `[switch]$Stock` (forwards `--stock`).
  - Make the error text name `-Stock` and `-WebOnly`.
- **F4 (LOW): open.** The quoting guard does not reject a trailing `\`.
- **F7 (LOW): open.** `selection_source` and profiles are not echoed before launch.
- **F8 (INFO): wider window.** The window between the plan and the launch now includes up to 6 s of bridge startup.
