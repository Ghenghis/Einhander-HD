"""Prepare the requested Aurora/Crimson saved preset without any game I/O."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'windows-x64'
sys.path.insert(0, str(PROJECT / 'tools'))
from devtools_service import DevTools
from material_profiles import saved_selection

service = DevTools(PROJECT, lambda *args, **kwargs: dict(ok=False, error='File-only preset preparation'))
saved = saved_selection(PROJECT)
preserved = saved.get('valid', False)
if not preserved:
    pairings = json.loads((ROOT / 'remaster-audit/dev-center-evidence/prepared-material-presets.json').read_text(encoding='utf-8'))
    config = json.loads(Path(pairings[0]['config']).read_text(encoding='utf-8'))
    fields = ('profile', 'strength', 'enemy_profile', 'enemy_strength', 'detail_map', 'enemy_detail_map',
              'detail_strength', 'enemy_detail_strength', 'detail_scale', 'enemy_detail_scale')
    result = service.material_profiles.save(dict(action='save', **{key: config[key] for key in fields}))
    if not result.get('ok'):
        raise ValueError(result.get('error', 'Could not prepare the saved preset'))
    saved = result['saved_selection']
report = dict(saved_selection=saved, existing_valid_selection_preserved=preserved, game_launched=False,
              running_game_changed=False, engine_commands_sent=0,
              bridge_controls_activation='pending manual restart; CLI saved-preset validation is independent')
(ROOT / 'remaster-audit/dev-center-evidence/saved-material-preparation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(saved=saved['valid'], profile=saved['profile'], enemy_profile=saved['enemy_profile'],
                     detail_map=saved['detail_map'], enemy_detail_map=saved['enemy_detail_map'],
                     game_launched=False, existing_valid_selection_preserved=preserved), indent=2))
