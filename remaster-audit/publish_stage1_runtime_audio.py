"""Publish exact callback PCM from a closed, explicitly failed diagnostic."""
import json
import shutil
import wave
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference
from publish_stage1_ui_cadence_results import closed,cadence

def main():
    run=E/'keep-bracket-greif-audio-v1/hd-on_rewind-off';proof=closed(run/'world-flypast-proof.json')
    source=run/'audio-review-v1/greif-transition-actual-host.wav';packet=read(source.with_name('proof.json'))
    assert sha(source)==packet['clip_sha256'] and packet['seconds']==12 and not packet['retimed'] and not packet['resampled']
    destination=OUT/'stage1-transition-audio-failed.wav';target=OUT/'stage1-runtime-audio-results.json'
    assert not destination.exists() and not target.exists()
    with wave.open(str(source),'rb') as wav:
        pcm=wav.readframes(wav.getnframes());assert wav.getframerate()==48000 and wav.getnchannels()==2 and wav.getsampwidth()==2
        assert __import__('hashlib').sha256(pcm).hexdigest()==packet['pcm_sha256']
    shutil.copyfile(source,destination);assert sha(destination)==sha(source)
    report=cadence(run);a,b=proof['observations'][0],proof['observations'][-1]
    report.update(schema_version=1,kind='Actual device-output PCM from failed Stage1 diagnostic',
        audio=dict(**reference(destination),rate=48000,channels=2,sample_width_bytes=2,seconds=12,
            source=reference(source),pcm_verification=packet),
        private_render_preference=9,rewind_enabled=False,keep_bracket_enabled=True,filter_state_cache_enabled=False,
        bracket_keeps=b['hd_cpu_profile']['hr_bracket_keeps']-a['hd_cpu_profile']['hr_bracket_keeps'],
        interpreter_snapshots=sum('dirty_ram_stats' in r for r in proof['observations']),
        host_audio_copied_after_final_measurement=True,audio_resolved=False,audible_acceptance=False,production_installed=False,
        limitations=['This is failed diagnostic audio, not an enhanced or repaired soundtrack.',
            'Exact contiguous callback PCM, including actual starvation. No system audio, filters, resampling or retiming.',
            'One opt-in run without a same-binary bracket-off control; no causal performance improvement claim.',
            'Private render preference9 differs from normal user2; normal rewind50/15 remains to be compared.',
            'This game-travel/Greif observation does not establish native FMV playback acceptance.'])
    write(target,report);provenance=OUT/'provenance.json';pr=read(provenance)
    pr.setdefault('audio_assets',[]).append(dict(**reference(destination),rate=48000,channels=2,seconds=12,
        category='actual_game_callback_pcm',status='Failed diagnostic; audio remains unresolved',
        result_manifest=target.relative_to(ROOT).as_posix(),retimed=False,resampled=False,processing='Exact contiguous PCM copy'))
    pr.update(audio_count=len(pr['audio_assets']),total_audio_bytes=sum(x['bytes'] for x in pr['audio_assets']))
    write(provenance,pr);print(json.dumps(dict(result=str(target),audio=str(destination),fps=report['guest_fps'],starved=report['starved_sample_frames_delta'])))

if __name__=='__main__':main()
