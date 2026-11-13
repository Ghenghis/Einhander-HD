"""Publish closed targeting footage and the negative live audio comparison.

Private source dumps, native RAM and absolute workstation paths stay private.
The preview belongs to the frozen v32 policy, not subsequent refinements.
"""
from __future__ import annotations
from collections import Counter
import json
import shutil
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference,probe
from publish_stage1_emissive_results import still
from publish_stage1_ui_cadence_results import closed,cadence

def refinement_summary():
    run=E/'combat-aware-auto-mk3-v2/hd-on_rewind-off'
    proof=closed(run/'robin-proof.json');rows=proof['gameplay_observations'];a,b=rows[0],rows[-1]
    assert all(proof[k] is False for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    return dict(proof=reference(run/'robin-proof.json'),
        policy='Continuous main gun; pod when aligned; automatic proven starter hull recognition',
        guest_fps=(b['registers']['frame']-a['registers']['frame'])/(b['elapsed_seconds']-a['elapsed_seconds']),
        starved_sample_frames_delta=b['audio']['out']['underruns']-a['audio']['out']['underruns'],
        observed_hull_source_sets=sorted({r['hull_draw']['source_set'] for r in rows}),
        final_life_counter=b['lives']['hex'],stage_clear_verified=False,
        video_recording=True,performance_accepted=False,production_installed=False,
        limitation='Recorded run with different scene/combat/load conditions; not an isolated causal comparison of policy or audio changes')

def diagnostic_profiles():
    results=[]
    for name in ['audio010-hitch-profile-v1','audio010-full-runtime-profile-v1']:
        run=E/name/'hd-on_rewind-off';proof=closed(run/'world-flypast-proof.json');entry=cadence(run)
        first=proof['observations'][0]['hd_cpu_profile'];last=proof['observations'][-1]['hd_cpu_profile']
        entry.update(hd_cpu_ms_delta={k:last[k]-first[k] for k in ['total_ms','source_ms','draw_ms','readback_ms','decode_queue_acquire_ms']},
            runtime_perf_enabled=read(run/'candidate.json')['pacing_profile'].get('runtime_perf',False),
            samples=[dict(elapsed_seconds=r['elapsed_seconds'],guest_frame=r['registers']['frame'],
                output=r['audio']['out'],hd_cpu=r['hd_cpu_profile']) for r in proof['observations']])
        results.append(entry)
    return results

def cache_comparison():
    runs=[];executables=[]
    for name,enabled in [('filter-state-on-v1',True),('filter-state-off-v2',False)]:
        run=E/name/'hd-on_rewind-off';proof=closed(run/'world-flypast-proof.json');config=read(run/'candidate.json')
        entry=cadence(run);a,b=proof['observations'][0],proof['observations'][-1]
        first,last=a['hd_cpu_profile'],b['hd_cpu_profile'];frames=entry['guest_frames']
        executables.append(config['launches']['candidate']['executable_sha256'])
        entry.update(enabled=enabled,hd_cpu_ms_per_guest_frame=(last['total_ms']-first['total_ms'])/frames,
            hd_draw_ms_per_guest_frame=(last['draw_ms']-first['draw_ms'])/frames,
            filter_parameter_updates=last['base_filter_updates']-first['base_filter_updates'],
            repeated_filter_states_skipped=last['base_filter_skips']-first['base_filter_skips'])
        runs.append(entry)
    assert len(set(executables))==1 and len({r['composition_plan_sha256'] for r in runs})==1
    return dict(runtime_executable_sha256=executables[0],same_binary_and_artwork=True,runs=runs,
        excluded_control=reference(E/'filter-state-off-v1/hd-on_rewind-off/control-exclusion.json'),
        excluded_reason='Non-yielding motion jobs likely overlapped initial control; low initial audio fill. Retained, replaced with fresh control.',
        audio_resolved=False,production_installed=False,default_enabled=False,
        conclusion='Redundant sampler commands skipped and mean HD draw cost modestly lower; persistent starvation means this is insufficient.',
        limitations=['One sequential ON/OFF pair; initial fill196.5 versus158.3ms and host/scene variation limit causal attribution.',
            'Timer-assisted no-fire120-second route after City; not unassisted full-combat or audible acceptance.'])

def main():
    target=OUT/'stage1-robin-targeting-results.json'
    audio_target=OUT/'stage1-audio-correction-results.json'
    assert not target.exists() and not audio_target.exists()
    run=E/'combat-aware-mk3-v2/hd-on_rewind-off'
    proof=closed(run/'robin-proof.json');config=read(run/'candidate.json')
    assert all(proof[k] is False for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    assert not proof['verified_continues']['attempts'] and proof['video']['exit_code']==0
    source=run/'robin-original.mp4';assert sha(source)==proof['video']['sha256']
    clip=run/'targeting-review-v1/robin-targeting-preview.mp4'
    packet=read(run/'targeting-review-v1/packet-proof.json')
    assert packet['source_sha256']==sha(source) and packet['clip_sha256']==sha(clip)
    # Independently recheck packet content and relative timing before publishing.
    original_packets=probe(source,True)['packets'];clip_packets=probe(clip,True)['packets']
    offset=packet['source_start_packet'];matched=original_packets[offset:offset+len(clip_packets)]
    assert len(matched)==len(clip_packets)==packet['packets']
    for a,b in zip(matched,clip_packets):
        assert a['data_hash']==b['data_hash']
        for key in ['pts_time','dts_time']:
            assert abs((float(a[key])-float(matched[0][key]))-(float(b[key])-float(clip_packets[0][key])))<.000002
    destination=OUT/'stage1-robin-targeting.mp4';assert not destination.exists()
    shutil.copyfile(clip,destination);assert sha(destination)==sha(clip)
    video=dict(**reference(destination),duration_seconds=float(probe(destination)['format']['duration']),
        source=reference(source),packet_verification=packet,silent=True,
        processing='Contiguous stream-copy preview including nearest-keyframe preroll; no re-encoding, internal cuts, retiming or interpolation')
    picture=still(run/'captures/robin-0090.png',OUT/'stage1-robin-asp-score.png')
    commands=[json.loads(line) for line in (run/'robin-commands.jsonl').read_text().splitlines()]
    queries=[r['reply'] for r in commands if r['command']['cmd']=='threat_draw']
    sampled=[r for r in proof['gameplay_observations'] if 'bot' in r]
    modes=Counter(r['bot'].get('position',{}).get('combat',{}).get('mode','unavailable') for r in sampled)
    report=dict(schema_version=1,kind='Actual closed enemy-aware Robin prototype observation',
        proof=reference(run/'robin-proof.json'),candidate=reference(run/'candidate.json'),
        runtime_build_sha256=config['pacing_profile']['runtime_build']['sha256'],
        executed_policy=proof['combat_policy_source']['sha256'],
        policy_version='v32: main gun and pod fire when aligned; newer continuous-main refinement is not this footage',
        duration_seconds=proof['gameplay_observations'][-1]['elapsed_seconds'],
        threat_queries=len(queries),nonempty_threat_queries=sum(bool(q.get('objects')) for q in queries),
        sampled_modes=dict(modes),sample_interval_seconds=15,
        observed=['Target acquisition and vertical alignment','Main gun and pod firing','Evasive movement',
            'ASP pod equipped; native score 18,980 in the 90-second still'],
        initial_life_counter=proof['gameplay_observations'][0]['lives']['hex'],
        final_life_counter=proof['gameplay_observations'][-1]['lives']['hex'],
        timer_assistance=False,ram_writes=False,state_loads=False,verified_continues_used=0,
        stage_clear_verified=False,production_installed=False,video=video,still=picture,
        subsequent_refinement=refinement_summary(),
        limitations=['Read-only source-matched draw clusters cover selected enemies and tracers, not every threat or collision hitbox.',
            'Target tracks are approximate screen-space associations, not native object IDs.',
            'The run lost lives and did not establish a stage clear, perfect evasion or successful boss targeting.',
            'Recording and source capture load affect cadence; the silent video does not qualify audible audio.',
            'Normal launcher/runtime integration remains pending.'])
    write(target,report)
    pair=[]
    for cap,name in [(.005,'audio005-quiet-v1'),(.01,'audio010-quiet-v1')]:
        path=E/name/'hd-on_rewind-off';p=closed(path/'world-flypast-proof.json');entry=cadence(path)
        outs=[r['audio']['out'] for r in p['observations']]
        entry.update(max_correction=cap,fill_range_ms=[min(o['fill_ms'] for o in outs),max(o['fill_ms'] for o in outs)],
            correction_range=[min(o['correction'] for o in outs),max(o['correction'] for o in outs)])
        pair.append(entry)
    assert pair[0]['composition_plan_sha256']==pair[1]['composition_plan_sha256']
    write(audio_target,dict(schema_version=1,kind='Fresh same-source live audio correction-cap comparison',
        runs=pair,closed_cleanly=True,audio_resolved=False,audible_qa=False,production_installed=False,
        diagnostic_profiles=diagnostic_profiles(),
        filter_cache_comparison=cache_comparison(),
        synthesis_probe_receipt=reference(E/'audio-clock-probe-v2/result.json'),
        unchanged=['180ms target/prefill','280ms ring','32-tap resampler','75ms control low-pass','0.75 percentage points per second slew'],
        limitations=['One sequential ordered pair with different initial buffer fill and host state; not a causal improvement claim.',
            'Both used timer-only assistance and no firing, with recorder, source dumps and measurement stills off.',
            'Underrun deltas count output-starved sample frames, not audible gaps or gap events.',
            'Synthetic steady low-rate recovery improved at1%, but live starvation persisted at both limits.']))
    provenance=OUT/'provenance.json';pr=read(provenance)
    pr['assets'].append(dict(path=picture['path'],sha256=picture['sha256'],bytes=picture['bytes'],dimensions=picture['dimensions'],
        category='actual_gameplay_capture',status='Unassisted Robin prototype; ASP pod and score visible; no stage clear',
        source_path=picture['source']['path'],source_sha256=picture['source']['sha256'],unmodified_copy=False,
        pixel_identical_to_source=True,processing=picture['processing'],embedded_metadata_present=False))
    pr['video_assets'].append(dict(path=video['path'],sha256=video['sha256'],bytes=video['bytes'],category='actual_gameplay_capture',
        status='Enemy-aware unassisted prototype; continuous32-second preview; no stage-clear claim',
        result_manifest=target.relative_to(ROOT).as_posix(),processing=video['processing'],retimed=False,interpolated_frames=False))
    pr.update(image_count=len(pr['assets']),total_image_bytes=sum(x['bytes'] for x in pr['assets']),
        video_count=len(pr['video_assets']),total_video_bytes=sum(x['bytes'] for x in pr['video_assets']))
    for item in pr['assets']+pr['video_assets']:
        path=ROOT/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    write(provenance,pr)
    print(json.dumps(dict(targeting=str(target),audio=str(audio_target),modes=dict(modes),
        video_bytes=video['bytes'],images=pr['image_count'],videos=pr['video_count'])))

if __name__=='__main__':main()
