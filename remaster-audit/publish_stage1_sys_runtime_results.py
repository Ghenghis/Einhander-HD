"""Publish the first closed SYS native/control firing tests, including failed parity."""
import json
import wave
from datetime import datetime, timezone
from publish_stage1_wave2_results import ROOT, E, OUT, read, write, reference
from publish_stage1_ui_cadence_results import closed, cadence
from publish_stage1_region_index_results import copy_exact


def main():
    target = OUT / 'stage1-sys-runtime-results.json'
    if target.exists():
        raise ValueError('Preserve existing experiment')
    rows, proofs, audio_assets, video_assets = {}, {}, [], []
    for mode, batch in [('off', 'sys-native-off-boot-r1'), ('on', 'sys-native-on-fire-r1')]:
        run = E / batch / 'hd-on_rewind-off'
        p = closed(run / 'world-flypast-proof.json')
        c = read(run / 'candidate.json')
        assert p['ordinary_fire'] and not p['command_audit']['forbidden_mutations']
        assert p['fire_input']['ok'] and not c['pacing_profile']['rewind_enabled']
        assert not any(p['measurement_load'][k] for k in ('video', 'source_capture', 'composed_stills'))
        s = p['observations'][-1]['static_image_status']
        assert s['state'] == 'armed' and s['native'] == int(mode == 'on')
        assert s['native_dispatches_before_arm'] == 0
        assert (s['native_dispatches'] > 0) == (mode == 'on')
        row = cadence(run)
        row['ordinary_fire'] = True
        prefix = f'stage1-sys-native-{mode}'
        audio = copy_exact(run / 'callback-over-process-capture.wav', OUT / (prefix + '-callback.wav'))
        assert audio['sha256'] == p['process_loopback']['callback_reference']['sha256']
        with wave.open(str(OUT / (prefix + '-callback.wav'))) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (48000, 2, 2)
            audio.update(seconds=w.getnframes()/48000, frames=w.getnframes(), rate=48000, channels=2)
        audio['scope'] = 'Exact game output callback PCM after timing; no loopback-helper fill, resampling, retiming or added audio. Physical output acceptance unverified.'
        video = copy_exact(run / 'post-measurement-gameplay.mp4', OUT / (prefix + '-gameplay.mp4'))
        assert p['video']['exit'] == 0 and p['video']['after_measurement']
        video.update(seconds=10, silent=True, dimensions=[1280, 960], recorder_hz=30,
            scope='Actual normal-speed game window, held fire, timer-only invulnerability aid. Silent; separate audio is not asserted synchronized. Recorded after timing, no motion interpolation or deliberate retiming.')
        footer = json.loads((run / 'process-output-after-measurement.timing.jsonl').read_text().splitlines()[-1])
        row.update(executable_sha256=c['launches']['candidate']['executable_sha256'],
            static_image=s, callback_audio=audio, gameplay_video=video,
            separate_process_capture_observer_fill_frames=footer['fill_frames'],
            rewind_enabled=False, cached_overlay_native_execution=False)
        rows[mode], proofs[mode] = row, p
        audio_assets.append(dict(**reference(OUT / (prefix + '-callback.wav')), seconds=audio['seconds'],
            rate=48000, channels=2, category='actual_game_callback_pcm', result_manifest=target.relative_to(ROOT).as_posix(),
            status='Experimental SYS firing test; audio failing; parity blocker', processing=audio['scope']))
        video_assets.append(dict(**reference(OUT / (prefix + '-gameplay.mp4')), category='actual_gameplay_capture',
            result_manifest=target.relative_to(ROOT).as_posix(), status='Held-fire timer-assisted diagnostic; no stage-clear acceptance',
            processing=video['scope'], retimed=False, interpolated_frames=False))
    assert rows['off']['executable_sha256'] == rows['on']['executable_sha256']
    assert rows['off']['static_image']['arm_ram2m_sha256'] == rows['on']['static_image']['arm_ram2m_sha256']
    a, b = [{e['frame']: e for e in proofs[m]['boot_fingerprints']['entries']} for m in ('off', 'on')]
    keys = ['wr', 'wc', 'mmio', 'mc', 'cyc', 'pc', 'sp', 'sc']
    common = sorted(set(a) & set(b))
    divergent = [f for f in common if any(a[f][k] != b[f][k] for k in keys)]
    assert common[0] == 1 and divergent[0] == 1049
    first = divergent[0]
    result = dict(schema_version=1, at_utc=datetime.now(timezone.utc).isoformat(),
        kind='Experimental SYS native execution versus same-binary interpreted control, held weapon fire',
        scope='Both use the new isolated executable, native cached overlays disabled, rewind disabled; not a comparison against the installed/current release.',
        runs=rows, boot_comparison=dict(first_common_frame=1, identical_through_frame=1048,
            first_divergent_frame=first, differing_fields=[k for k in keys if a[first][k] != b[first][k]],
            off=a[first], on=b[first], first_input_trigger_frames=dict(off=1895, on=1896),
            divergence_before_any_input=True, differential_acceptance_pass=False),
        audio_resolved=False, production_installed=False, runtime_merge_approved=False,
        limitations=['One ordered pair; equal wall-time windows cover different guest-frame totals and scenes.',
            'Both runs hold ordinary fire and use the same disclosed 180-second timer-only aid; no lives writes or state loads.',
            'Rewind and native cached overlays are off for this first qualification; normal-user/full-stage acceptance remains open.',
            'A faster average does not establish sustained smoothness or runtime correctness. Pre-input differential failed at frame 1049.',
            'Audio and silent video are actual post-measurement captures with observer load and unverified synchronization.',
            'Callback WAVs contain no loopback-helper fill. Separate unpublished process recordings contain 10 ms off / 40 ms on of observer fill.'])
    write(target, result)
    provenance = read(OUT / 'provenance.json')
    for kind, assets in [('audio', audio_assets), ('video', video_assets)]:
        existing = provenance.setdefault(kind + '_assets', [])
        assert not ({x['path'] for x in existing} & {x['path'] for x in assets})
        existing.extend(assets)
        provenance[kind + '_count'] = len(existing)
        provenance['total_' + kind + '_bytes'] = sum(x['bytes'] for x in existing)
    write(OUT / 'provenance.json', provenance)
    print(json.dumps(dict(report=target.relative_to(ROOT).as_posix(), first_divergence=first, audio_resolved=False)))


if __name__ == '__main__':
    main()
