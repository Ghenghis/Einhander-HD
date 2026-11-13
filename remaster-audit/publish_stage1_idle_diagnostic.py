"""Publish the bounded idle-option diagnostic, including observer-side audio loss."""
import json
import argparse
import shutil
import wave
from publish_stage1_wave2_results import ROOT, E, OUT, read, sha, write, reference
from publish_stage1_ui_cadence_results import closed, cadence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-report', action='store_true', help='Refresh this exact diagnostic report while preserving and verifying its existing WAV')
    args = parser.parse_args()
    run = E / 'v41-idle-on-r1/hd-on_rewind-on'
    target = OUT / 'stage1-idle-diagnostic-results.json'
    output = OUT / 'stage1-idle-process-output.wav'
    if (target.exists() or output.exists()) and not args.refresh_report:
        raise ValueError('Preserve the existing publication')
    proof = closed(run / 'world-flypast-proof.json')
    config = read(run / 'candidate.json')
    profile = config['pacing_profile']
    assert profile['supersampling'] == 2 and profile['rewind_enabled']
    assert all(profile[k] for k in ('hd_opaque_batch', 'keep_bracket', 'filter_state_cache'))
    assert config['visual_profile']['idle_skip_override'] == 1
    assert not config.get('qualified_code_cache')
    first, last = proof['observations'][0], proof['observations'][-1]
    idle_before, idle_after = first['idle_skip'], last['idle_skip']
    assert idle_before['enabled'] == idle_after['enabled'] == 1
    assert idle_after['skips'] == idle_before['skips'] == 2
    assert not last['hd_cpu_profile']['hr_kept_leaks']
    capture = proof['process_loopback']
    assert capture['exit'] == 0 and capture['after_measurement']
    source = run / 'process-output-after-measurement.wav'
    assert sha(source) == capture['audio']['sha256']
    records = [json.loads(line) for line in source.with_suffix('.timing.jsonl').read_text().splitlines()]
    header, footer = records[0], records[-1]
    assert header['pid'] == capture['pid'] and header['strict']
    assert footer['exit_code'] == 0 and footer['frames_written'] == 480000
    analysis = read(run / 'process-audio-analysis.json')
    assert analysis['integrity_ok']
    assert footer['fill_frames'] == 4320  # Observer inserted 90 ms. Never hide it.
    assert analysis['timeline']['fill_ms_total'] == 90
    with wave.open(str(source), 'rb') as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (48000, 2, 2, 480000)
    if output.exists():
        assert sha(output) == sha(source), 'Existing published WAV differs'
    else:
        shutil.copyfile(source, output)
    assert sha(output) == sha(source)
    row = cadence(run)
    result = dict(schema_version=1, kind='Existing guarded idle-loop option diagnostic',
        **row, executable_sha256=config['launches']['candidate']['executable_sha256'],
        settings=dict(render_preference=2, opaque_batch=True, filter_state_cache=True,
            keep_bracket=True, rewind=True, rewind_interval=15, rewind_fmv_interval=4,
            idle_skip=True, staged_native_cache=False),
        idle=dict(before=idle_before, after=idle_after, gameplay_skips=0,
            conclusion='No gameplay skips occurred. The higher run average cannot be attributed to skipped gameplay loops.'),
        process_audio=dict(**reference(output), source=reference(source), seconds=10,
            rate=48000, channels=2, frames=480000, sample_width_bytes=2,
            capture_integrity_pass=True, observer_gap_fill_frames=4320, observer_gap_fill_ms=90,
            observer_gap_start_seconds=6.05, observer_timestamp_errors=footer['ts_error_packets'],
            observer_discontinuities=footer['discontinuity_packets'],
            candidate_verdicts=analysis['audio']['candidate_verdicts'],
            findings=analysis['audio']['dropout_candidates'],
            callback_counter_bracket=dict(capture['callback_reference'],
                path=(run/'callback-over-process-capture.wav').relative_to(ROOT).as_posix()),
            timing_source=reference(source.with_suffix('.timing.jsonl')),
            analysis_source=reference(run / 'process-audio-analysis.json'),
            edited_after_capture=False, physical_output_acceptance=False,
            scope='Exact copy of process capture WAV; includes a documented 90 ms observer-inserted silence. Four separate likely runtime-bridge dropouts are inferential.'),
        diagnostic_observers=proof['measurement_load'],
        gpu_clock_log=reference(run/'gpu-clock-observation.csv'),
        audio_resolved=False, ordinary_combat_acceptance=False, production_installed=False,
        limitations=['Single assisted no-fire route, not an identical input replay or full-stage acceptance.',
            'Cached phase reads, CPU attribution, media telemetry and 1Hz NVML add observer load.',
            'Process capture starts after timing, covers the owned process tree and verified console child only.',
            'Callback reference brackets capture setup and teardown; its 8201 starved sample frames are not an exact one-to-one gap attribution.',
            'Whole-reference envelope alignment was weak; exact waveform alignment is not established.',
            'Observer filled a 90ms delivery hole with zeros; this is not evidence of a 90ms game-audio dropout.',
            'Averages and starvation are run-specific; no causal speed benefit from idle skip is accepted.'])
    alignment = run / 'independent-callback-alignment.json'
    if alignment.exists():
        aligned = read(alignment)
        clean = [x for x in aligned['windows'] if not (x['start_seconds'] <= 6.14 and x['start_seconds'] + .5 >= 6.05)]
        assert aligned['offset_callback_minus_process_frames'] == 4256
        assert len(aligned['windows']) == 18 and min(x['correlation'] for x in clean) > .999
        result['process_audio']['sample_alignment'] = dict(offset_callback_minus_process_frames=4256,
            sample_rate=48000, independently_checked_windows=18,
            minimum_correlation_outside_observer_hole=min(x['correlation'] for x in clean),
            windows_matching_within_one_lsb=sum(x['fraction_within_1_LSB'] == 1 for x in clean),
            matched_main_dropout_contexts=aligned.get('matched_main_dropout_contexts', []),
            source=reference(alignment),
            conclusion='Four main PCM gaps occur in both aligned callback and process recordings. The observer-filled interval has callback audio present. Local peak differences remain; this does not establish whole-device continuity.')
        result['limitations'] = [x for x in result['limitations'] if not x.startswith('Whole-reference')]
        result['limitations'].append('Initial unaligned envelope correlation was weak; independent interior-window sample alignment subsequently confirmed the supplied 4256-frame offset, with localized peak differences retained.')
    write(target, result)
    path = OUT / 'provenance.json'; provenance = read(path)
    provenance.setdefault('audio_assets', [])[:] = [x for x in provenance.get('audio_assets', []) if x['path'] != reference(output)['path']]
    provenance['audio_assets'].append(dict(**reference(output),
        rate=48000, channels=2, seconds=10, category='owned_game_process_loopback',
        result_manifest=target.relative_to(ROOT).as_posix(),
        status='Failing diagnostic; 90ms observer gap disclosed separately',
        processing='Exact capture WAV copy, including 4320 observer-inserted zero frames'))
    provenance['audio_count'] = len(provenance['audio_assets'])
    provenance['total_audio_bytes'] = sum(x['bytes'] for x in provenance['audio_assets'])
    write(path, provenance)
    print(json.dumps({k: result[k] for k in ('guest_fps', 'starved_sample_frames_delta', 'audio_resolved')}))


if __name__ == '__main__':
    main()
