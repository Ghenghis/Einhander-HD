"""Stage three review pairings and manual shortcuts, without launching a game."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'windows-x64'
sys.path.insert(0, str(PROJECT / 'tools'))
from devtools_service import DevTools


def main():
    service = DevTools(PROJECT, lambda *args, **kwargs: dict(ok=False, error='Offline staging only'))
    pairings = [
        ('Play-Aurora-Crimson.cmd', 'aurora-teal', 'crimson-red', 'titanium-teal-nanoceramic', 'crimson-gold-plating'),
        ('Play-Aurora-Gold.cmd', 'aurora-teal', 'gold-obsidian', 'titanium-teal-nanoceramic', 'gold-obsidian-engraved'),
        ('Play-Neon-Cyberpunk.cmd', 'neon-circuit', 'ultraviolet-grid', 'neon-circuit-tracery', 'ultraviolet-plasma-grid'),
    ]
    receipts = []
    for name, player, enemy, detail, enemy_detail in pairings:
        result = service.material_profiles.stage(dict(action='stage', profile=player, strength=.75,
            enemy_profile=enemy, enemy_strength=.75, detail_map=detail, enemy_detail_map=enemy_detail,
            detail_strength=.12, enemy_detail_strength=.12, detail_scale=8, enemy_detail_scale=8))
        if not result.get('ok'):
            raise ValueError(result.get('error', 'Preset staging failed'))
        relative = Path(result['launcher_path']).relative_to(PROJECT).as_posix().replace('/', '\\')
        (PROJECT / name).write_text('@echo off\nsetlocal\ncall "%~dp0' + relative + '" %*\nif errorlevel 1 pause\n', encoding='utf-8')
        receipts.append(dict(shortcut=str(PROJECT / name), config=result['config_path'], profile=player,
                             enemy_profile=enemy, detail_map=detail, enemy_detail_map=enemy_detail,
                             game_launched=False, in_game_verified=False))
    (ROOT / 'remaster-audit/dev-center-evidence/prepared-material-presets.json').write_text(
        json.dumps(receipts, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipts, indent=2))


if __name__ == '__main__':
    main()
