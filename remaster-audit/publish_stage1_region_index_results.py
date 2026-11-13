"""Publish the closed v45 region-index diagnostic and exact captured media."""
import json
import re
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from publish_stage1_wave2_results import ROOT, E, OUT, read, sha, write, reference
from publish_stage1_ui_cadence_results import closed, cadence


def copy_exact(source, target):
    if target.exists():
        assert sha(target) == sha(source), 'Preserve existing publication'
    else:
        shutil.copyfile(source, target)
    assert sha(target) == sha(source)
    return dict(**reference(target), source=reference(source), byte_identical=True)


def main():
    target = OUT / 'stage1-region-index-results.json'
    if target.exists():
        raise ValueError('Use a new publication for a new experiment')
    rows = {}
    audio_assets, video_assets = [], []
    for mode in ('off', 'on'):
        run = E / f'v45-region-{mode}-r1/hd-on_rewind-on'
        p = closed(run / 'world-flypast-proof.json')
        c = read(run / 'candidate.json')
        profile = c['pacing_profile']
        assert profile['region_index'] == (mode == 'on')
        assert profile['supersampling'] == 2 and profile['rewind_enabled']
        assert all(profile[k] for k in ('hd_opaque_batch', 'keep_bracket', 'filter_state_cache'))
        assert not any(p['measurement_load'][k] for k in ('video', 'source_capture', 'composed_stills'))
        assert not p['command_audit']['forbidden_mutations']
        a, b = p['observations'][0]['hd_cpu_profile'], p['observations'][-1]['hd_cpu_profile']
        assert b['pack_region_index'] == int(mode == 'on')
        counters = {k: b[k] - a[k] for k in (
            'pack_region_ms', 'pack_region_tests', 'pack_region_hits', 'pack_region_index_cuts',
            'pack_upload_ms', 'pack_upload_candidates', 'pack_index_rebuild_ms', 'pack_index_rebuilds')}
        assert (counters['pack_region_index_cuts'] > 0) == (mode == 'on')
        prefix = f'stage1-region-index-{mode}'
        callback = copy_exact(run / 'callback-over-process-capture.wav', OUT / (prefix + '-callback.wav'))
        assert callback['sha256'] == p['process_loopback']['callback_reference']['sha256']
        with wave.open(str(OUT / (prefix + '-callback.wav'))) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (48000, 2, 2)
            callback.update(rate=48000, channels=2, frames=w.getnframes(), seconds=w.getnframes()/48000)
        callback.update(scope='Actual game output callback PCM; exact copy, no capture-helper fill, resampling or retiming. Recorded after performance timing; physical output acceptance unverified.',
            starved_sample_frames_delta=p['process_loopback']['callback_reference']['starved_sample_frames_delta'])
        process = copy_exact(run / 'process-output-after-measurement.wav', OUT / (prefix + '-process.wav'))
        analysis = read(run / 'process-audio-analysis.json')
        assert analysis['integrity_ok']
        footer = json.loads((run / 'process-output-after-measurement.timing.jsonl').read_text().splitlines()[-1])
        assert footer['exit_code'] == 0 and footer['frames_written'] == 480000
        process.update(seconds=10, observer_fill_frames=footer['fill_frames'], observer_fill_ms=footer['fill_frames']/48,
            analysis=reference(run / 'process-audio-analysis.json'), timing=reference(run / 'process-output-after-measurement.timing.jsonl'),
            scope='Exact process-loopback file; observer inserted 60 ms of silence. This fill is not evidence of a runtime gap.')
        video = copy_exact(run / 'post-measurement-gameplay.mp4', OUT / (prefix + '-gameplay.mp4'))
        metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames', '-of', 'json',
            str(OUT / (prefix + '-gameplay.mp4'))], timeout=20))
        assert float(metadata['format']['duration']) == 10 and p['video']['exit'] == 0
        video.update(metadata=metadata, after_measurement=True, silent=True, audio_synchronization_verified=False,
            scope='Actual 1280x960 game window, normal speed, 30 Hz recorder; no motion interpolation or deliberate retiming. Separate audio overlaps this capture but is not asserted synchronized.')
        settings = {k: profile[k] for k in ('region_index', 'supersampling', 'rewind_enabled',
            'rewind_interval', 'rewind_fmv_interval', 'hd_opaque_batch', 'keep_bracket', 'filter_state_cache')}
        rows[mode] = dict(**cadence(run), executable_sha256=c['launches']['candidate']['executable_sha256'],
            settings=settings, pack_cost=counters, callback_audio=callback, process_audio=process, gameplay_video=video)
        for item, category in ((callback, 'actual_game_callback_pcm'), (process, 'owned_game_process_loopback')):
            audio_assets.append(dict(**reference(OUT / item['path'].split('/')[-1]), category=category,
                seconds=item['seconds'], rate=48000, channels=2, result_manifest=reference_name(target),
                status='Failing stutter diagnostic; timer-assisted/no-fire', processing=item['scope']))
        video_assets.append(dict(**reference(OUT / (prefix + '-gameplay.mp4')), category='actual_gameplay_capture',
            result_manifest=reference_name(target), status='Timer-assisted/no-fire diagnostic; audio failing',
            processing=video['scope'], retimed=False, interpolated_frames=False))
    assert rows['off']['executable_sha256'] == rows['on']['executable_sha256']
    assert rows['off']['composition_plan_sha256'] == rows['on']['composition_plan_sha256']
    counts = {mode: sum(int(n) for n in re.findall(r'mode='+str(mode)+r' flag_checks=(\d+)',
        (E/'region-index-review-r1/equivalence.log').read_text())) for mode in (0, 1)}
    assert counts[0] == counts[1] == 74913
    result = dict(schema_version=1, at_utc=datetime.now(timezone.utc).isoformat(),
        kind='Same-binary default-off HD region-index diagnostic', runs=rows,
        component_time_reduction_fraction=1-rows['on']['pack_cost']['pack_region_ms']/rows['off']['pack_cost']['pack_region_ms'],
        net_gameplay_improvement_established=False, audio_resolved=False, default_enabled=False, production_installed=False,
        correctness=dict(flag_checks_per_mode=counts[0], mismatches=0, equivalent_digests=True,
            real_source_receipt=reference(E/'region-index-review-r1/equivalence.log'),
            default_gl_receipt=reference(E/'sampling-build-v45-region-index/tests.json'),
            enabled_gl_receipt=reference(E/'sampling-build-v45-region-index/index-on-tests.json')),
        limitations=['One ordered pair with equal wall-time windows, not randomized or a full-stage combat test.',
            'Different guest-frame totals and initial buffer fill limit whole-game causal attribution; no net gain established.',
            'Both runs use the disclosed timer-only invulnerability aid and no firing; no state loads or stage-clear claim.',
            'CPU profile, rewind counters and 1 Hz GPU observation are diagnostic overhead.',
            'Pack timers are nested and must not be added as disjoint costs.',
            'Video and audio were captured after the timed window, with capture load; streams are supplied separately.',
            'Both process WAVs contain 2880 observer-inserted zero frames (60 ms). Primary callback WAVs do not contain that helper fill.'])
    write(target, result)
    provenance = read(OUT / 'provenance.json')
    for key, assets in [('audio_assets', audio_assets), ('video_assets', video_assets)]:
        existing = provenance.setdefault(key, [])
        assert not ({x['path'] for x in existing} & {x['path'] for x in assets})
        existing.extend(assets)
        kind = key.split('_')[0]
        provenance[kind + '_count'] = len(existing)
        provenance['total_' + kind + '_bytes'] = sum(x['bytes'] for x in existing)
    write(OUT / 'provenance.json', provenance)
    print(json.dumps(dict(report=reference_name(target), audio_resolved=False, net_gain=False)))


def reference_name(path):
    return path.relative_to(ROOT).as_posix()


if __name__ == '__main__':
    main()
