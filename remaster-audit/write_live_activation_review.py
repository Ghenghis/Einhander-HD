"""Reconcile saved activation evidence; do not operate the bridge or game."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'remaster-audit/dev-center-evidence'
RUN = OUT / 'level1-live-d59b8e1c'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    status_path = sorted((RUN/'boss-pass').glob('status-*.json'))[-1]
    saved = read(status_path)
    state = saved['research']['status']
    processes_path = RUN/'verified-pass/process-identity-final.json'
    processes = read(processes_path)
    if isinstance(processes, dict): processes = [processes]
    launch = read(RUN/'verified-pass/game-launch.json')
    segments = []
    for identity in ['research-20261112-152726-0276c11a',
                     'research-20261112-153038-6a202447',
                     'research-20261112-153406-11eebc24']:
        path = ROOT/'windows-x64/tools/research-runs'/identity/'manifest.json'
        data = read(path)
        segments.append(dict(id=identity, manifest_path=str(path),
                             manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             status=data.get('status'), stop_reason=data.get('stop_reason')))
    report = dict(
        reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
        observation_at_utc=saved['at_utc'],
        activation_pending=False,
        historical_activation_report='research-recorder-activation-pending.json',
        reason='The user explicitly authorized restarting the bridge and activating the recorder; both were subsequently observed working.',
        bridge_routes_active=saved['dev'].get('connected') is True,
        watcher_alive=state.get('watcher_alive'),
        automatic_recording_preference_prepared=state.get('armed'),
        automatic_recording_active=state.get('running'),
        watch_status=state.get('watch_status'),
        timed_holds_remaining=saved['dev'].get('locks'),
        game_paused_visually=True,
        pilot_finished=True,
        processes_observed=processes,
        process_identity_path=str(processes_path),
        launch_receipt_path=str(RUN/'verified-pass/game-launch.json'),
        status_receipt_path=str(status_path),
        runtime_artifact_sha256=launch.get('executable_sha256', launch.get('exe_sha256')),
        segments=segments,
        gameplay_scope='Verified MkII/stock selection, city play, carried Wasp, Greif and Drache encounters, then a subsequent debris/turret area. Numeric stage identity, boss destruction versus timeout and all boss phases are not established.',
        coverage_complete=False,
        semantic_bindings_complete=False,
        pending_composed_capture='The timed-out post-drache-paused.png request may complete on a future present; it is excluded from accepted visual evidence.',
        scope='Saved process and service observations plus finalized run manifests; this report does not independently attest the connected process binary or promote any game address.'
    )
    assert report['bridge_routes_active'] and report['watcher_alive']
    assert report['automatic_recording_active'] is False
    assert report['timed_holds_remaining'] == []
    assert len(processes) == 2 and {p['ProcessId'] for p in processes} == {49424, 49068}
    target = OUT/'research-recorder-activation-accepted.json'
    target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(path=str(target), active=False, armed=report['automatic_recording_preference_prepared'],
                          segments=len(segments), coverage_complete=False), indent=2))


if __name__ == '__main__':
    main()
