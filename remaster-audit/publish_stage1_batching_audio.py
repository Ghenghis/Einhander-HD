"""Publish the focused batching pair and exact owned-process audio evidence."""
import hashlib
import json
import shutil
import wave
from pathlib import Path
from publish_stage1_wave2_results import ROOT, E, OUT, read, sha, write, reference
from publish_stage1_ui_cadence_results import closed, cadence


def pcm_clip(run, proof, output):
    host = proof['host_audio']
    source = run / 'actual-host-output.wav'
    assert sha(source) == host['sha256']
    anchor = next(x for x in proof['observations'] if x['elapsed_seconds'] >= 104)
    start = next(t['frames'] for t in anchor['audio']['taps'] if t['name'] == 'host')
    offset, count = start - host['start_sample_frame'], 576000
    with wave.open(str(source), 'rb') as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 2, 2)
        assert 0 <= offset and offset + count <= wav.getnframes()
        wav.setpos(offset)
        pcm = wav.readframes(count)
    assert len(pcm) == count * 4
    with wave.open(str(output), 'wb') as wav:
        wav.setframerate(48000); wav.setnchannels(2); wav.setsampwidth(2); wav.writeframes(pcm)
    return dict(**reference(output), source=reference(source), clip_source_offset_frames=offset,
        clip_start_sample_frame=start, anchor_elapsed_seconds=anchor['elapsed_seconds'],
        frames=count, seconds=12, rate=48000, channels=2, sample_width_bytes=2,
        pcm_sha256=hashlib.sha256(pcm).hexdigest(), retimed=False, resampled=False)


def main():
    target = OUT / 'stage1-batching-audio-results.json'
    outputs = [OUT / f'stage1-batching-{x}-audio.wav' for x in ('off', 'on')]
    process_output = OUT / 'stage1-batching-process-output.wav'
    if target.exists() or process_output.exists() or any(p.exists() for p in outputs):
        raise ValueError('Preserve the existing publication')
    rows = []
    runs = [E / x / 'hd-on_rewind-on' for x in ('v40-code-off-r2', 'v40-opaque-on-r2')]
    for enabled, run, output in zip((False, True), runs, outputs):
        proof = closed(run / 'world-flypast-proof.json')
        config = read(run / 'candidate.json'); profile = config['pacing_profile']
        assert profile['hd_opaque_batch'] == enabled
        assert profile['supersampling'] == 2 and profile['rewind_enabled']
        assert profile['rewind_interval'] == 15 and profile['rewind_fmv_interval'] == 4
        assert not profile['keep_bracket'] and not profile['filter_state_cache']
        assert not config.get('qualified_code_cache')
        assert proof['measurement_load'] == dict(video=False, source_capture=False,
            composed_stills=False, timer_assistance=True)
        foreground = read(run.parent / 'foreground-before-measurement.json')
        assert foreground['completed_uninterrupted_by_agent']
        assert not foreground['agent_ui_switches_during_measurement']
        a, b = proof['observations'][0], proof['observations'][-1]
        hd = {k: b['hd_cpu_profile'][k] - a['hd_cpu_profile'][k] for k in
            ('submitted', 'batched_primitives', 'batch_flushes', 'draw_ms', 'source_ms', 'readbacks')}
        assert (hd['batched_primitives'] > 0) == enabled
        row = cadence(run)
        row.update(opaque_batch_enabled=enabled, render_preference=2,
            executable_sha256=config['launches']['candidate']['executable_sha256'],
            hd_delta=hd, draw_ms_per_guest_frame=hd['draw_ms'] / row['guest_frames'],
            foreground_observation=reference(run.parent / 'foreground-before-measurement.json'),
            gpu_observation=reference(run.parent / 'gpu-clock-observation.csv'),
            audio=pcm_clip(run, proof, output))
        rows.append(row)
    assert rows[0]['executable_sha256'] == rows[1]['executable_sha256']
    assert rows[0]['composition_plan_sha256'] == rows[1]['composition_plan_sha256']
    run = runs[1]; proof = closed(run / 'world-flypast-proof.json')
    capture = proof['process_loopback']; analysis = read(run / 'process-output-analysis.json')
    assert capture['exit'] == 0 and capture['after_measurement'] and analysis['integrity_ok']
    source = run / 'process-output-after-measurement.wav'
    assert sha(source) == capture['audio']['sha256']
    records = [json.loads(x) for x in (run / 'process-output-after-measurement.timing.jsonl').read_text().splitlines()]
    header, footer = records[0], records[-1]
    assert header['pid'] == capture['pid'] and header['strict']
    assert footer['exit_code'] == 0 and footer['frames_written'] == 480000
    assert footer['fill_frames'] == 0 and footer['discontinuity_packets'] == 0
    assert footer['ts_error_packets'] == 0
    shutil.copyfile(source, process_output)
    assert sha(process_output) == sha(source)
    process_audio = dict(**reference(process_output), source=reference(source), seconds=10,
        frames=480000, rate=48000, channels=2, sample_width_bytes=2,
        kind='Windows process loopback of the owned game tree with verified console-host exception',
        after_measurement=True, capture_integrity_pass=True, capture_gap_fill_frames=0,
        dropout_candidates=len(analysis['audio']['dropout_candidates']),
        device_position_overlaps=len(analysis['timeline']['overlaps']),
        device_position_note='The virtual process device reported one constant position; QPC packet positions were continuous. Overlap flags are retained, not treated as lost or duplicated WAV audio.',
        processed=False, hardware_output_acceptance=False,
        timing_source=reference(run / 'process-output-after-measurement.timing.jsonl'),
        analysis_source=reference(run / 'process-output-analysis.json'))
    native_run = E / 'v40-native-textures-r2/hd-off_rewind-on'
    native = read(native_run / 'world-flypast-proof.json')
    assert native['owned_process_exit'] == 0 and native['close']['port_closed']
    assert native['process_loopback']['exit'] == 4 and len(native['errors']) == 1
    a, b = native['observations'][0], native['observations'][-1]
    report = dict(schema_version=1, kind='Focused same-binary batching off/on diagnostic pair', runs=rows,
        process_audio=process_audio,
        native_texture_control=dict(proof=reference(native_run / 'world-flypast-proof.json'),
            guest_fps=(b['registers']['frame'] - a['registers']['frame']) / (b['elapsed_seconds'] - a['elapsed_seconds']),
            starved_sample_frames_delta=b['audio']['out']['underruns'] - a['audio']['out']['underruns'],
            postmeasurement_observer_refused=True, observer_error=native['errors'][0],
            scope='Timing completed; the earlier strict helper refused a console child before activating audio'),
        audio_resolved=False, audible_acceptance=False, production_installed=False,
        conclusions=['Batching was active and reduced HD draw submission work; both runs still starved output audio.',
            'Native textures with the same v40 core sustained about60fps with zero new starvation in the bounded control.',
            'Actual process-output capture succeeded after timing; its silence candidates do not establish their cause.'],
        limitations=['One ordered pair; different initial fill and guest-frame routes, not an identical replay.',
            'Owned game foregrounded during boot; no agent UI switches during measurement; continuous foreground state was not logged.',
            'Read-only NVML sampled GPU state at1Hz; no driver settings or clock locks changed.',
            'Timer-only/no-fire route; ordinary combat, boss fire, FMV and full-stage acceptance remain open.',
            'Loopback covers the game tree and verified Windows console child, after the120s measurement, not the whole run.',
            'Eight short PCM silence candidates are not proof of eight audible gaps or device-driver failures.'])
    write(target, report)
    path = OUT / 'provenance.json'; provenance = read(path)
    for audio, category in [(r['audio'], 'actual_game_callback_pcm') for r in rows] + [(process_audio, 'owned_game_process_loopback')]:
        asset = {k: audio[k] for k in ('path', 'sha256', 'bytes', 'rate', 'channels', 'seconds')}
        asset.update(category=category, status='Diagnostic audio; whole-run smoothness still failing',
            result_manifest=target.relative_to(ROOT).as_posix(), processing='Exact PCM excerpt' if category == 'actual_game_callback_pcm' else 'Unmodified capture WAV')
        provenance.setdefault('audio_assets', []).append(asset)
    provenance.update(audio_count=len(provenance['audio_assets']), total_audio_bytes=sum(x['bytes'] for x in provenance['audio_assets']))
    write(path, provenance)
    print(json.dumps(dict(result=str(target), runs=[{k: r[k] for k in ('opaque_batch_enabled', 'guest_fps', 'starved_sample_frames_delta')} for r in rows])))


if __name__ == '__main__':
    main()
