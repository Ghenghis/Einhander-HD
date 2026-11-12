"""Launch the verified saved skin preset for an explicitly requested Level 1 test.

Use installed runtime/cache and original read-only disc/texture assets. Writable
cards/options live in a new evidence directory; the user's cards are not mounted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'windows-x64'
sys.path.insert(0, str(PROJECT / 'tools'))
from launch_material import prepare_launch
from material_profiles import saved_selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--cache-sources', action='store_true',
                        help='Keep the existing bounded raw-upload cache alive between recorder segments')
    parser.add_argument('--texture-root', help='Isolated candidate pack inside this project')
    parser.add_argument('--raster-scale', type=int, choices=range(1, 17))
    parser.add_argument('--window-width', type=int)
    args = parser.parse_args()
    evidence = Path(args.evidence).resolve()
    allowed = (ROOT / 'remaster-audit/dev-center-evidence').resolve()
    if not evidence.is_relative_to(allowed) or not evidence.is_dir():
        raise ValueError('Use the existing Level 1 evidence directory')
    selected = saved_selection(PROJECT)
    if not selected.get('valid'):
        raise ValueError(selected.get('error', 'Saved skin preset unavailable'))
    prepared = prepare_launch(PROJECT, selected['config_path'])
    if args.window_width is not None and not 640 <= args.window_width <= 7680:
        raise ValueError('Isolated window width must be between 640 and 7680')
    overrides = dict(prepared['environment_overrides'])
    if args.cache_sources:
        overrides['PSXRECOMP_HD_SOURCE_SIDECARS'] = '1'
    if args.texture_root:
        candidate = Path(args.texture_root).resolve()
        if not candidate.is_relative_to(ROOT.resolve()) or not candidate.is_dir():
            raise ValueError('Candidate texture root must be an existing directory inside this project')
        if not any(candidate.glob('*.png')):
            raise ValueError('Candidate texture root has no replacement PNGs')
        overrides['PSXRECOMP_HD_TEXTURE_ROOT'] = str(candidate)
    arguments = [item for item in prepared['arguments'] if item != '--launcher']
    isolated_runtime = evidence/'runtime' if args.raster_scale or args.window_width else None
    if isolated_runtime:
        arguments[0] = str(isolated_runtime/'Einhander_Recompiled.exe')
    arguments += ['--no-launcher', '--debug-port', '4370', '--memcard-dir', str(evidence / 'state'),
                  '--window-title', 'Einhander - Level 1 recorded research']
    report = dict(at_utc=datetime.now(timezone.utc).isoformat(), arguments=arguments, cwd=str(PROJECT),
                  executable_sha256=prepared['runtime']['sha256'], saved_selection=selected,
                  environment_overrides=overrides,
                  continuous_source_cache=args.cache_sources,
                  candidate_texture_root=overrides['PSXRECOMP_HD_TEXTURE_ROOT'] if args.texture_root else None,
                  isolated_runtime=str(isolated_runtime) if isolated_runtime else None,
                  requested_raster_scale=args.raster_scale, requested_window_width=args.window_width,
                  writable_state=str(evidence / 'state'), user_cards_mounted=False,
                  assists='None configured by this launcher; recorder also records bridge assist context',
                  game_launched=False)
    if args.check:
        print(json.dumps(report, indent=2))
        return
    try:
        with socket.create_connection(('127.0.0.1', 4370), timeout=1):
            raise RuntimeError('Port 4370 is already occupied; refusing to launch another runtime')
    except (ConnectionRefusedError, TimeoutError):
        pass
    if (evidence / 'game-launch.json').exists():
        raise ValueError('This evidence directory already owns a launch; choose a new run directory')
    (evidence / 'state').mkdir(exist_ok=False)
    settings = PROJECT / 'build-release/settings.toml'
    if settings.is_file():
        shutil.copy2(settings, evidence / 'settings-before-launch.toml')
        report['settings_sha256'] = hashlib.sha256(settings.read_bytes()).hexdigest()
    if isolated_runtime:
        isolated_runtime.mkdir(exist_ok=False)
        shutil.copy2(prepared['arguments'][0], isolated_runtime/'Einhander_Recompiled.exe')
        if hashlib.sha256((isolated_runtime/'Einhander_Recompiled.exe').read_bytes()).hexdigest() != report['executable_sha256']:
            raise ValueError('Isolated runtime copy hash mismatch')
        text = settings.read_text(encoding='utf-8')
        for key, value in [('supersampling', args.raster_scale), ('window_width', args.window_width), ('rewind_depth', 0)]:
            if value is not None:
                text, count = re.subn(r'(?m)^'+key+r'\s*=\s*[^\r\n]+', key+' = '+str(value), text)
                if count != 1:
                    raise ValueError('Expected exactly one isolated settings field: '+key)
        (isolated_runtime/'settings.toml').write_text(text, encoding='utf-8')
        report['isolated_settings_sha256'] = hashlib.sha256((isolated_runtime/'settings.toml').read_bytes()).hexdigest()
        source_cache = PROJECT/'build-release/cache'
        if source_cache.is_dir():
            shutil.copytree(source_cache, isolated_runtime/'cache')
    environment = os.environ.copy()
    environment.update(overrides)
    with (evidence / 'game.stdout.log').open('xb') as out, (evidence / 'game.stderr.log').open('xb') as err:
        process = subprocess.Popen(arguments, cwd=PROJECT, env=environment, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    report.update(pid=process.pid, game_launched=True)
    (evidence / 'game-launch.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(pid=process.pid, evidence=str(evidence), game_launched=True,
                          profile=prepared['profile'], enemy_profile=prepared['enemy_profile']), indent=2))


if __name__ == '__main__':
    main()
