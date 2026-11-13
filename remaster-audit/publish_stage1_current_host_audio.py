"""Publish closed current-host failures and exact, unmodified callback PCM."""
import csv
import hashlib
import json
import wave
from pathlib import Path

from publish_stage1_wave2_results import ROOT, E, OUT, read, sha, write, reference
from publish_stage1_ui_cadence_results import cadence, closed

LEGS = [
    ('v40-code-off-r1', 'v40-code-off'),
    ('v40-code-on-r1', 'v40-code-on'),
    ('v37-current-host-control-r1', 'v37-current-host'),
]


def main():
    target = OUT / 'stage1-current-host-audio-results.json'
    outputs = [OUT / f'stage1-{label}-audio.wav' for _, label in LEGS]
    if target.exists() or any(p.exists() for p in outputs):
        raise ValueError('Publication exists; preserve measured artifacts')
    rows, clips = [], []
    for (batch, label), output in zip(LEGS, outputs):
        run = E / batch / 'hd-on_rewind-on'
        proof = closed(run / 'world-flypast-proof.json')
        config = read(run / 'candidate.json')
        profile = config['pacing_profile']
        assert profile['supersampling'] == 2 and profile['rewind_enabled']
        assert profile['rewind_interval'] == 15 and profile['rewind_fmv_interval'] == 4
        assert not profile['keep_bracket'] and not profile['filter_state_cache']
        assert proof['measurement_load'] == dict(video=False, source_capture=False,
            composed_stills=False, timer_assistance=True)
        assert not proof['ordinary_fire'] and not proof['state_loads']
        spec = config['launches']['candidate']
        assert sha(Path(spec['arguments'][0])) == spec['executable_sha256']
        observations = proof['observations']
        first, last = observations[0], observations[-1]
        host = proof['host_audio']
        source = run / 'actual-host-output.wav'
        assert sha(source) == host['sha256']
        anchor = next(x for x in observations if x['elapsed_seconds'] >= 104)
        start = next(t['frames'] for t in anchor['audio']['taps'] if t['name'] == 'host')
        offset, count = start - host['start_sample_frame'], 12 * 48000
        with wave.open(str(source), 'rb') as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 2, 2)
            assert wav.getnframes() == host['frames'] and 0 <= offset
            assert offset + count <= wav.getnframes()
            wav.setpos(offset)
            pcm = wav.readframes(count)
            assert len(pcm) == count * 4
        row = cadence(run)
        row.update(label=label, executable_sha256=spec['executable_sha256'],
            opaque_batch_enabled=profile['hd_opaque_batch'],
            keep_bracket_enabled=profile['keep_bracket'],
            filter_state_cache_enabled=profile['filter_state_cache'],
            render_preference=2, rewind=dict(depth=50, interval=15, fmv_interval=4),
            qualified_cache=config.get('qualified_code_cache'),
            cache_admission_observed_in_this_run=False,
            hd_cpu_ms_delta={k: last['hd_cpu_profile'][k] - first['hd_cpu_profile'][k]
                for k in ('total_ms', 'draw_ms', 'source_ms', 'readback_ms')},
            readback_delta=last['hd_cpu_profile']['readbacks'] - first['hd_cpu_profile']['readbacks'],
            frame_intervals=[dict(ending_seconds=b['elapsed_seconds'],
                frames=b['registers']['frame'] - a['registers']['frame'],
                seconds=b['elapsed_seconds'] - a['elapsed_seconds'])
                for a, b in zip(observations, observations[1:])],
            audio=dict(source=reference(source), source_start_sample_frame=host['start_sample_frame'],
                clip_source_offset_frames=offset, clip_start_sample_frame=start,
                anchor_elapsed_seconds=anchor['elapsed_seconds'], frames=count, seconds=12,
                rate=48000, channels=2, sample_width_bytes=2,
                pcm_sha256=hashlib.sha256(pcm).hexdigest(), retimed=False, resampled=False))
        rows.append(row)
        clips.append((output, pcm))
    assert rows[0]['executable_sha256'] == rows[1]['executable_sha256']
    assert len({r['composition_plan_sha256'] for r in rows}) == 1
    gpu_path = E / 'v37-current-host-control-r1/gpu-clock-observation.csv'
    with gpu_path.open(encoding='utf-8') as stream:
        gpu = list(csv.DictReader(stream, skipinitialspace=True))
    assert len(gpu) > 100
    number = lambda key: [float(r[key].split()[0]) for r in gpu]
    gpu_summary = dict(source=reference(gpu_path), samples=len(gpu),
        clock_time_zone='America/Phoenix; game proof timestamps use UTC',
        states={s: sum(r['pstate'] == s for r in gpu) for s in sorted({r['pstate'] for r in gpu})},
        graphics_mhz_range=[min(number('clocks.current.graphics [MHz]')), max(number('clocks.current.graphics [MHz]'))],
        memory_mhz_range=[min(number('clocks.current.memory [MHz]')), max(number('clocks.current.memory [MHz]'))],
        clock_lock_used=False, driver_settings_changed=False,
        scope='Read-only 1Hz NVML log during part of the v37 control and after its measurement; not a causal power-state experiment')
    for row, (output, pcm) in zip(rows, clips):
        with wave.open(str(output), 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(pcm)
        with wave.open(str(output), 'rb') as wav:
            assert wav.readframes(wav.getnframes()) == pcm
        row['audio'].update(reference(output))
    report = dict(schema_version=1, kind='Three sequential actual-game current-host diagnostic failures',
        runs=rows, gpu_observation=gpu_summary, audio_resolved=False, audible_acceptance=False,
        performance_improvement_accepted=False, production_installed=False,
        conclusions=[
            'All three runs starved audio, including the previous v37 build under current host conditions.',
            'Batching was disabled in these runs and enabled in the earlier normal-resolution series; cross-series differences do not isolate a host or core regression.',
            'The v40 pair differs only by staging the separately qualified 3A998 artifact; neither is an audio fix.',
            'GPU clock changes and non-Claude host load were observed; their causal contribution is unproven.'],
        limitations=[
            'One ordered series with different initial fill and diverging guest-frame routes; no causal speed gain is accepted.',
            'No-fire, timer-only route at normal render preference2; ordinary combat, boss fire and FMV remain unaccepted.',
            'The timing publication is present in both v40 runs; this pair cannot isolate that source change.',
            'Actual use of the staged routine was not queried in this pacing pair; its earlier correctness qualification is separate.',
            'Exact contiguous callback PCM copied after measurement; no filtering, retiming or resampling.',
            'Callback PCM is not process/device loopback and cannot prove mixer or hardware continuity.'])
    write(target, report)
    provenance_path = OUT / 'provenance.json'
    provenance = read(provenance_path)
    for row in rows:
        asset = {k: row['audio'][k] for k in ('path', 'sha256', 'bytes', 'rate', 'channels', 'seconds')}
        asset.update(category='actual_game_callback_pcm', status='Current-host diagnostic still fails; ' + row['label'],
            result_manifest=target.relative_to(ROOT).as_posix(), retimed=False, resampled=False,
            processing='Exact contiguous PCM copy')
        provenance.setdefault('audio_assets', []).append(asset)
    provenance.update(audio_count=len(provenance['audio_assets']),
        total_audio_bytes=sum(x['bytes'] for x in provenance['audio_assets']))
    write(provenance_path, provenance)
    print(json.dumps(dict(result=str(target), runs=[{k: r[k] for k in
        ('label', 'guest_fps', 'starved_sample_frames_delta')} for r in rows])))


if __name__ == '__main__':
    main()
