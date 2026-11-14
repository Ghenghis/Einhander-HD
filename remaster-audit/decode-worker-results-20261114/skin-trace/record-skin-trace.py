"""Read-only source/selection trace; emit an isolated proposal, never launch a game."""
from pathlib import Path
import datetime, difflib, hashlib, json, sys

ROOT = Path('C:/github/Einhander')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'windows-x64/tools'))
from launch_hd import prepare_hd_launch
from material_profiles import saved_selection, runtime_receipt

paths = [
    'windows-x64/tools/launch_hd.py', 'windows-x64/tools/launch_material.py',
    'windows-x64/tools/material_profiles.py', 'windows-x64/tools/material_lab.js',
    'windows-x64/tools/loadout_lab.js', 'windows-x64/tools/Start-Development.ps1',
    'windows-x64/psxrecomp/runtime/src/hd_skin_material.h',
    'windows-x64/psxrecomp/runtime/src/hd_skin_detail.h',
    'windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c',
    'windows-x64/recomp-ui/src/common/backends/imgui/launcher_devtools.cpp',
    'windows-x64/skin-workspace/aurora-teal/skin.json',
    'windows-x64/tools/material-selection.json', 'windows-x64/tools/material-runtime.json',
]
pins = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
root = ROOT / 'windows-x64'
saved = saved_selection(root)
runtime = runtime_receipt(root, verify_hash=True)
plan = prepare_hd_launch(root)

# Proposal against the pinned, currently dirty sources only. Do not apply here.
hd_path, dev_path = paths[0], paths[5]
before = (ROOT / hd_path).read_text(encoding='utf-8')
after = before.replace('stock=False, game_arguments=()', 'stock=False, frontend=False, game_arguments=()', 1)
after = after.replace('    prepared["arguments"].extend(game_arguments)',
    '    if frontend:\n        slot = prepared["arguments"].index("--no-launcher")\n'
    '        prepared["arguments"][slot] = "--launcher"\n'
    '    prepared["arguments"].extend(game_arguments)', 1)
after = after.replace('    args, game_arguments = parser.parse_known_args(argv)',
    '    parser.add_argument("--frontend", action="store_true", help="Open the launcher with the validated saved material preset")\n'
    '    args, game_arguments = parser.parse_known_args(argv)', 1)
after = after.replace('stock=args.stock,\n', 'stock=args.stock, frontend=args.frontend,\n', 1)
assert after != before and 'frontend=args.frontend' in after
patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                  fromfile='a/' + hd_path, tofile='b/' + hd_path))
before = (ROOT / dev_path).read_text(encoding='utf-8-sig')
old = next(line for line in before.splitlines() if 'Start-Process -FilePath $runtimePath -ArgumentList' in line)
new = '''    $launchPlanText = & python (Join-Path $PSScriptRoot 'launch_hd.py') --check --frontend
    if ($LASTEXITCODE -ne 0) { throw "Saved material launch validation failed: $launchPlanText" }
    $launchPlan = ($launchPlanText -join "`n") | ConvertFrom-Json
    foreach ($entry in $launchPlan.environment_overrides.PSObject.Properties) {
        [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
    }
    # These validated arguments contain switches and local file paths, with no embedded quotes.
    $launchArgs = @($launchPlan.arguments | Select-Object -Skip 1 | ForEach-Object {
        if ([string]$_ -match '"') { throw 'Unexpected quote in validated launch argument' }
        '"' + [string]$_ + '"'
    })
    Start-Process -FilePath ([string]$launchPlan.arguments[0]) -ArgumentList $launchArgs -WorkingDirectory ([string]$launchPlan.cwd)'''
after = before.replace(old, new, 1)
assert after != before
patch += ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                   fromfile='a/' + dev_path, tofile='b/' + dev_path))
(OUT / 'saved-material-development-route.patch').write_text(patch, encoding='utf-8')
report = {
    'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'owner': 'codex-einhander-crash-check', 'scope': 'Read-only C: source and launch-plan validation; no GPU/game or asset changes',
    'source_sha256': pins,
    'actual_checks': {
        'saved_selection': {k: saved.get(k) for k in ('exists', 'valid', 'profile', 'enemy_profile', 'detail_map', 'enemy_detail_map', 'descriptor_sha256')},
        'runtime_receipt': {k: runtime.get(k) for k in ('ready', 'executable_hash_verified', 'sha256')},
        'normal_play_hd_plan': {k: plan.get(k) for k in ('selection_source', 'profile', 'enemy_profile', 'arguments')},
    },
    'findings': [
        {'id': 'S1', 'result': 'Normal Play-HD is already wired to the saved preset',
         'trace': ['Play-HD.cmd -> launch_hd.prepare_hd_launch', 'saved_selection -> launch_material.prepare_launch',
                   'environment -> init_gpu_raster getenv', 'hd_skin_for_draw exact-key match -> shader RGB uniforms']},
        {'id': 'S2', 'result': 'Start-Development directly launches the runtime with HD variables but does not read the saved material descriptor',
         'proposal': 'saved-material-development-route.patch', 'applied': False,
         'limits': 'Proposal only; existing dirty files untouched. Root review/lock transfer and existing launch tests plus frontend/live checks required.'},
        {'id': 'S3', 'result': '14 palette profiles scope to 5 player and 6 enemy atlas keys, not all actors/components',
         'source': 'hd_skin_material.h:26,48,56',
         'missing': ['per-craft hull/gun UV ownership', 'independent Gunpod identities', 'boss-part actor/material mapping', 'all-stage ownership and visual acceptance']},
        {'id': 'S4', 'result': 'Concept art does not enter the runtime as model textures',
         'evidence': 'aurora-teal/skin.json has assets=[], draft_uninstalled, concept_unmapped, in_game=false; loadout_lab labels equipment concept/unmapped'},
        {'id': 'S5', 'result': 'Existing selectors are browser material controls; native graphics pane links to that workspace; no native/in-game independent ship/weapon/boss skin selector found in these traced files',
         'source': 'material_lab.js submit/save/apply; launcher_devtools.cpp draw_graphics/draw_armory',
         'limit': 'Scoped source trace, not a full binary/UI audit'},
        {'id': 'S6', 'result': 'Runtime receipt contains historical limited live checks; not replayed here',
         'limit': 'This run verifies current executable digest and read-only launch-plan source/asset checks only. Full gameplay/audio/skin acceptance remains open.'},
    ],
    'project_complete': False,
}
(OUT / 'skin-selector-trace-20261114.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'saved_valid': saved.get('valid'), 'runtime_hash_verified': runtime.get('executable_hash_verified'),
                  'normal_hd_selection': plan.get('selection_source'), 'proposal_applied': False,
                  'report_sha256': hashlib.sha256((OUT / 'skin-selector-trace-20261114.json').read_bytes()).hexdigest(),
                  'patch_sha256': hashlib.sha256((OUT / 'saved-material-development-route.patch').read_bytes()).hexdigest()}))
