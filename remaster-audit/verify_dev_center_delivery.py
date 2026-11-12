"""Verify the delivered workspace and art receipts without launching the game."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'windows-x64'
TOOLS = PROJECT / 'tools'
OUT = ROOT / 'remaster-audit' / 'dev-center-evidence'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_asset(record):
    url = record.get('image', '')
    if not url.startswith('/files/tools/skin_collection/'):
        raise ValueError('Artwork must remain in the project skin collection')
    path = (PROJECT / url.removeprefix('/files/')).resolve()
    if not path.is_relative_to((TOOLS / 'skin_collection').resolve()):
        raise ValueError('Artwork escaped its collection')
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG: ' + str(path))
    dimensions = struct.unpack('>II', data[16:24])
    if dimensions != (record['width'], record['height']):
        raise ValueError('PNG dimensions differ from receipt: ' + str(path))
    if hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('PNG content differs from receipt: ' + str(path))
    return dict(path=str(path), dimensions=list(dimensions), sha256=record['sha256'],
                in_game_verified=record.get('game_ready', False))


def check_launcher(filename):
    wrapper = PROJECT / filename
    if not wrapper.is_file():
        return dict(ok=False, error='Launcher missing: ' + filename)
    line = next(line for line in wrapper.read_text().splitlines() if line.startswith('call '))
    relative = line.split('"%~dp0', 1)[1].split('"', 1)[0]
    config = (PROJECT / relative).with_name('material.json')
    if not config.resolve().is_relative_to((TOOLS / 'material-profiles').resolve()):
        raise ValueError('Launcher configuration escaped its project workspace')
    run = subprocess.run([sys.executable, str(TOOLS / 'launch_material.py'), '--config', str(config), '--check'],
                         capture_output=True, text=True, timeout=15)
    data = json.loads(run.stdout)
    return dict(ok=run.returncode == 0 and data.get('status') == 'validated_not_launched',
                exit_code=run.returncode, config=str(config), profile=data.get('profile'),
                enemy_profile=data.get('enemy_profile'), player_keys=data.get('targets'),
                enemy_keys=data.get('enemy_targets'), game_launched=False)


def native_capture_report(name):
    data = read(ROOT / 'remaster-audit' / 'verification' / name / 'result.json')
    sources_match = bool(data.get('sources')) and all(digest(Path(item['path'])) == item['sha256'] for item in data['sources'])
    return dict(checks=data.get('checks'), failures=data.get('failures'), sources_match=sources_match,
                ok=data.get('compile_exit') == 0 and data.get('test_exit') == 0 and
                   data.get('failures') == 0 and sources_match,
                scope=data.get('scope'))


def main():
    collection = read(TOOLS / 'skin_collection' / 'collection.json')
    equipment = read(TOOLS / 'skin_collection' / 'equipment-art.json')
    bosses = read(TOOLS / 'skin_collection' / 'bosses' / 'boss-art.json')
    detail = read(TOOLS / 'skin_collection' / 'materials' / 'materials.json')
    loadouts = read(TOOLS / 'loadout_catalog.json')
    runtime = read(TOOLS / 'material-runtime.json')
    gpu = read(ROOT / 'remaster-audit' / 'verification' / 'material-shader' / 'result.json')
    art = [png_asset(row) for row in collection['skins']]
    models = [png_asset(row) for row in equipment['items']]
    boss_art = [png_asset(row) for row in bosses['items']]
    maps = [png_asset(row) for row in detail['maps']]
    source_matches = gpu['source_sha256'] == digest(PROJECT / 'psxrecomp/runtime/src/gpu_gl_renderer.c')
    kernel_matches = gpu['kernel_sha256'] == digest(PROJECT / 'psxrecomp/runtime/src/hd_skin_material.h')
    detail_matches = gpu['detail_sha256'] == digest(PROJECT / 'psxrecomp/runtime/src/hd_skin_detail.h')
    installed = [PROJECT / 'Einhander_Recompiled.exe', PROJECT / 'build-release/Einhander_Recompiled.exe']
    installed_match = all(digest(path) == runtime['sha256'] for path in installed)
    launchers = [check_launcher(name) for name in ('Play-Aurora-Crimson.cmd', 'Play-Aurora-Gold.cmd', 'Play-Neon-Cyberpunk.cmd')]
    saved_run = subprocess.run([sys.executable, str(TOOLS / 'launch_material.py'), '--saved', '--check'],
                               capture_output=True, text=True, timeout=15)
    saved = json.loads(saved_run.stdout)
    saved_ok = saved_run.returncode == 0 and saved.get('status') == 'validated_not_launched'
    research = read(TOOLS / 'research_catalog.json')
    live = read(ROOT / 'remaster-audit' / 'verification' / 'material-live' / 'result.json')
    live_sources_match = bool(live.get('sources')) and all(digest(Path(item['path'])) == item['sha256'] for item in live['sources'])
    live_ok = live.get('pass') is True and live.get('failures') == 0 and live.get('checks', 0) > 0 and live_sources_match
    capture_reports = [native_capture_report(name) for name in ('research-capture-sink', 'research-capture-command')]
    interoperability = read(ROOT / 'remaster-audit/verification/research-interoperability/result.json')
    interoperability_sources_match = bool(interoperability.get('sources')) and all(
        digest(Path(item['path'])) == item['sha256'] for item in interoperability['sources'])
    interoperability_ok = interoperability.get('pass') is True and interoperability_sources_match
    backend = read(ROOT / 'remaster-audit/verification/backend-suite/result.json')
    frontend = read(ROOT / 'remaster-audit/verification/frontend-qa/result.json')
    checks_current = all(data.get('pass') is True and bool(data.get('sources')) and all(
        digest(Path(item['path'])) == item['sha256'] for item in data['sources']) for data in (backend, frontend))
    activation = read(OUT / 'research-recorder-activation-pending.json')
    expected = {row['id'] for row in loadouts['gunpods']} | {'endymion_mk2', 'endymion_mk3', 'astraea_mk1', 'schabe'}
    present = {row['entity_id'] for row in equipment['items']}
    report = dict(
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='Workspace, source, artifact, GPU-test and manual-launch readiness. No commercial game launch.',
        finish_profiles=len(art), equipment_studies=len(models), boss_studies=len(boss_art), authored_detail_maps=len(maps),
        expected_equipment_studies=len(expected),
        missing_equipment_ids=sorted(expected - present),
        artwork_native_dimensions=sorted({tuple(item['dimensions']) for item in art + models + boss_art + maps}),
        artwork_hashes_and_dimensions_verified=True,
        hull_catalog_count=len(loadouts['ships']), gunpod_catalog_count=len(loadouts['gunpods']),
        runtime_contract=runtime['contract'], installed_executable_hashes_match=installed_match,
        material_gpu_report=gpu, gpu_report_matches_current_renderer=source_matches,
        gpu_report_matches_current_kernel=kernel_matches, gpu_report_matches_current_detail_kernel=detail_matches,
        live_command_report=live, live_command_sources_match=live_sources_match, live_command_checks_passed=live_ok,
        launchers=launchers, saved_preset_validated_without_launch=saved_ok,
        research_scenarios=len(research.get('scenarios', [])), research_tasks=len(research.get('tasks', [])),
        native_capture_reports=capture_reports,
        native_backend_interoperability_passed=interoperability_ok,
        backend_suite_tests=backend['tests'], frontend_workflow_checks=len(frontend['checks']),
        backend_and_frontend_evidence_current=checks_current,
        bridge_activation_pending=activation['activation_pending'],
        automatic_recording_preference_prepared=activation['preference']['enabled'],
        automatic_recording_active=False,
        research_scope='Capture plan and read-only instrumentation. Runtime collection and independent verification are still required.',
        status='workspace_verified_activation_and_gameplay_pending' if not (expected - present) and len(art) == 14 and
               len(boss_art) == 2 and len(maps) == 6 and installed_match and source_matches and kernel_matches and
               detail_matches and gpu['pass'] and live_ok and saved_ok and all(row['ok'] for row in launchers) and
               all(row['ok'] for row in capture_reports) and interoperability_ok and checks_current else 'in_progress',
        limitations=[
            'Generated concepts are 1672x941 originals; they are not native 4K UV replacements.',
            'Six generated RGB surface-detail maps are 1254x1254 originals; they add color detail, not geometry or PBR depth.',
            'The 3840x2160 material canvas is an atlas preview, not a gameplay screenshot or proof of new source detail.',
            'New dual-profile gameplay appearance and pacing remain unverified after automatic review rejected a game launch.',
            'Independent craft, built-in gun, pickup Gunpod and boss-part UV assignments remain partly or wholly unverified.',
            'Only four observed body atlas keys and six observed enemy atlas keys are selected by the prepared launchers.',
            'The recorder collects candidate evidence; it cannot discover and validate every game address or assign all effects automatically.',
            'Automatic review rejected the task-owned bridge restart. Saved recording preferences are prepared; the new recorder routes are not active in the existing bridge.',
            'Automatic review rejected test-cache cleanup; the duplicate test caches remain untouched.'
        ],
    )
    (OUT / 'delivery-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'finish_profiles', 'equipment_studies',
          'expected_equipment_studies', 'missing_equipment_ids', 'installed_executable_hashes_match')}, indent=2))
    return 0 if report['status'] == 'workspace_verified_activation_and_gameplay_pending' else 2


if __name__ == '__main__':
    raise SystemExit(main())
