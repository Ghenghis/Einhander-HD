"""Publish measured normal-settings failures and exact callback PCM excerpts."""
import hashlib
import json
from pathlib import Path
import wave
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference
from publish_stage1_ui_cadence_results import closed,cadence

LEGS=[('normal2-rewind-on-v2','hd-on_rewind-on','rewind4'),
      ('normal2-rewind-cadence15-v2','hd-on_rewind-on','rewind15'),
      ('normal2-rewind-off-v2','hd-on_rewind-off','rewind-off')]


def main():
    target=OUT/'stage1-normal-settings-audio-results.json'
    destinations=[OUT/f'stage1-normal-{label}-audio.wav' for _,_,label in LEGS]
    if target.exists() or any(p.exists() for p in destinations):
        raise ValueError('Publication already exists; preserve the measured result')
    rows=[];pcm_outputs=[]
    for (batch,variant,label),destination in zip(LEGS,destinations):
        run=E/batch/variant;p=closed(run/'world-flypast-proof.json');config=read(run/'candidate.json')
        profile=config['pacing_profile'];spec=config['launches']['candidate']
        assert profile['supersampling']==2 and profile['rewind_interval']==15
        assert not profile['keep_bracket'] and not profile['filter_state_cache']
        assert not p['ordinary_fire'] and not p['state_loads']
        assert p['measurement_load']==dict(video=False,source_capture=False,composed_stills=False,timer_assistance=True)
        assert sha(Path(spec['arguments'][0]))==spec['executable_sha256']
        source=run/'actual-host-output.wav';host=p['host_audio'];assert sha(source)==host['sha256']
        observations=p['observations'];a,b=observations[0],observations[-1]
        # Select the first observation at/after 104 s in every run. Host sample
        # indices select PCM; wall time is descriptive, never a retiming input.
        anchor=next(x for x in observations if x['elapsed_seconds']>=104)
        host_total=next(t['frames'] for t in anchor['audio']['taps'] if t['name']=='host')
        offset=host_total-host['start_sample_frame'];count=12*48000
        with wave.open(str(source),'rb') as wav:
            assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(48000,2,2)
            assert wav.getnframes()==host['frames'] and 0<=offset and offset+count<=wav.getnframes()
            wav.setpos(offset);pcm=wav.readframes(count);assert len(pcm)==count*4
        row=cadence(run);row.update(label=label,render_preference=2,
            opaque_batch_enabled=profile['hd_opaque_batch'],
            rewind_enabled=profile['rewind_enabled'],rewind_depth=profile['rewind_depth'],
            normal_interval=15,fmv_interval=profile['rewind_fmv_interval'],
            executable_sha256=spec['executable_sha256'],
            readback_delta=b['hd_cpu_profile']['readbacks']-a['hd_cpu_profile']['readbacks'],
            hd_cpu_ms_delta={k:b['hd_cpu_profile'][k]-a['hd_cpu_profile'][k] for k in ['total_ms','draw_ms','source_ms','readback_ms']},
            media=dict(xa_active_observations=sum(bool(x['fmv_state']['xa_stream_active']) for x in observations),
                observations=len(observations),depth24_observations=sum(bool(x['gpu_state']['depth24']) for x in observations),
                mdec_decode_count_delta=b['fmv_state']['mdec_decode_count']-a['fmv_state']['mdec_decode_count']),
            audio=dict(source=reference(source),source_start_sample_frame=host['start_sample_frame'],
                clip_source_offset_frames=offset,clip_start_sample_frame=host_total,frames=count,seconds=12,
                anchor_elapsed_seconds=anchor['elapsed_seconds'],rate=48000,channels=2,sample_width_bytes=2,
                pcm_sha256=hashlib.sha256(pcm).hexdigest(),retimed=False,resampled=False))
        rows.append(row);pcm_outputs.append((destination,pcm))
    assert len({x['executable_sha256'] for x in rows})==1
    assert len({x['composition_plan_sha256'] for x in rows})==1
    for row,(destination,pcm) in zip(rows,pcm_outputs):
        with wave.open(str(destination),'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000);wav.writeframes(pcm)
        with wave.open(str(destination),'rb') as wav:assert wav.readframes(wav.getnframes())==pcm
        row['audio'].update(reference(destination))
    report=dict(schema_version=1,kind='Normal-resolution and rewind controls with experimental opaque batching',
        runs=rows,audio_resolved=False,audible_acceptance=False,production_installed=False,
        conclusions=['All three runs starved output audio; disabling rewind did not remove the symptom.',
            'XA remained active during ordinary depth15 gameplay without further MDEC decoding.',
            'Readback deltas were zero or one; frequent successful snapshot readbacks are not established.',
            'Near-60fps averages conceal individual slow seconds; no causal fix is accepted.'],
        limitations=['One ordered three-leg series; different initial buffer fill and route timing, no repeat/randomization.',
            'Experimental opaque batching was enabled in all three; these are not the default unbatched rendering path.',
            'No-fire, timer-only private visual route; not ordinary combat, progression or FMV acceptance.',
            'Exact game callback PCM, copied after measurement. No system loopback, effects, resampling or retiming.',
            'Callback PCM and starvation counters do not prove device-driver continuity or audible acceptance.'])
    write(target,report);provenance=OUT/'provenance.json';pr=read(provenance)
    for row in rows:
        audio=row['audio'];pr.setdefault('audio_assets',[]).append({k:audio[k] for k in ['path','sha256','bytes','rate','channels','seconds']})
        pr['audio_assets'][-1].update(category='actual_game_callback_pcm',status='Normal-settings diagnostic still fails; '+row['label'],
            result_manifest=target.relative_to(ROOT).as_posix(),retimed=False,resampled=False,processing='Exact contiguous PCM copy')
    pr.update(audio_count=len(pr['audio_assets']),total_audio_bytes=sum(x['bytes'] for x in pr['audio_assets']))
    write(provenance,pr)
    print(json.dumps(dict(result=str(target),runs=[{k:r[k] for k in ['label','guest_fps','starved_sample_frames_delta','readback_delta']} for r in rows])))


if __name__=='__main__':main()
