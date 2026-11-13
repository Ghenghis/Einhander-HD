"""Publish closed mask A/B stills and recorder-off opening measurements."""
from __future__ import annotations
import json
from pathlib import Path
import re
from PIL import Image
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference

def still(source,target):
    assert not target.exists()
    with Image.open(source) as image:
        image.load();before=image.tobytes();mode=image.mode;size=image.size
        clean=image.copy();clean.info.clear();clean.save(target,format='PNG',compress_level=9)
    with Image.open(target) as image:assert image.mode==mode and image.size==size and image.tobytes()==before and not image.info
    return dict(**reference(target),dimensions=list(size),source=reference(source),pixel_identical=True,
        processing='Lossless PNG compression; original pixel bytes and dimensions preserved')

def main():
    target=OUT/'stage1-emissive-results.json';assert not target.exists()
    pairs=[];visuals=[]
    for enabled in [0,1]:
        label='on' if enabled else 'off';run=E/('emissive-pacing-'+label+'-v1')/'hd-on_rewind-off'
        p=read(run/'pacing-proof.json');r=read(run/'candidate.json');profile=p['profile']
        assert not p['errors'] and p['owned_process_exit']==0 and p['close']['port_closed']
        assert not p.get('owned_process_forced_cleanup') and not p['ram_writes'] and not p['state_loads'] and not p['survival_assistance']
        assert profile['emissive_masks']==bool(enabled) and profile['native_menus']
        assert not any(profile[k] for k in ['recorder','video_capture','source_sidecars','gl_timer_queries','rewind_enabled','timer_assistance'])
        a,b=p['samples'][0],p['samples'][-1];frames=b['get_registers']['frame']-a['get_registers']['frame'];assert frames>=1800
        pairs.append(dict(enabled=bool(enabled),proof=reference(run/'pacing-proof.json'),runtime_build_sha256=profile['runtime_build']['sha256'],
            guest_frames=frames,seconds=b['started_monotonic']-a['started_monotonic'],guest_fps=p['guest_fps'],
            audio_starved_sample_frames_delta=b['audio_stats']['out']['underruns']-a['audio_stats']['out']['underruns'],
            initial_audio_fill_ms=a['audio_stats']['out']['fill_ms'],final_audio_fill_ms=b['audio_stats']['out']['fill_ms'],
            five_second_windows=p['five_second_windows'],ordinary_fire_input=True,ram_writes=False,state_loads=False,timer_assistance=False,recording=False))
        vr=E/('w3-emissive-'+label+'-v1')/'hd-on_rewind-off';vp=read(vr/'world-flypast-proof.json');config=read(vr/'candidate.json')
        assert not vp['errors'] and vp['owned_process_exit']==0 and vp['close']['port_closed']
        assert config['visual_profile']['emissive']==bool(enabled)
        shot=read(vr/'captures/world-015.json');source=vr/'captures/world-015-internal.png';assert sha(source)==shot['hires']['sha256']
        visuals.append(dict(enabled=bool(enabled),proof=reference(vr/'world-flypast-proof.json'),capture_metadata=reference(vr/'captures/world-015.json'),
            still=still(source,OUT/('stage1-canyon-emissive-'+label+'.png')),
            composed_frame_bracket=[shot['frame_before'],shot['frame_after']],hires_sequential_not_atomic=True,
            camera_frame_aligned=False,timer_only_assistance=True,ordinary_firing=False))
    assert pairs[0]['runtime_build_sha256']==pairs[1]['runtime_build_sha256']
    facade=OUT/'stage1-lit-facade-fly-past-results.json';f=read(facade)
    poster=still(E/'w3-emissive-on-v1/hd-on_rewind-off/captures/world-060.png',OUT/'stage1-lit-facade-poster.png')
    tests=E/'sampling-build-v27/tests.json';test=read(tests);summaries={}
    for k,v in test['results'].items():
        summaries[k]=str(v).splitlines()[-1];assert not re.search(r'failures[=: ]+[1-9]',str(v))
    assert all(x['exit']==0 for x in test['commands'])
    composer=E/'emissive-composer-regression-v1-fixtures/results.json';cr=read(composer)
    assert cr['all_passed'] and len(cr['cases'])==3 and all(x['passed'] for x in cr['cases'])
    report=dict(schema_version=1,kind='Actual emissive mask visual comparison and scoped opening cadence',facade_results=reference(facade),
        candidate_sha256=f['candidate']['sha256'],authored_entries=837,pack_keys=1669,native_region_checks=226,
        runtime=f['runtime'],validation=dict(receipt=reference(tests),summaries=summaries,composer_cases=reference(composer)),
        contract=dict(file='<replacement PNG stem>-emissive.png',encoding='8-bit grayscale PNG; same size as replacement',
            opt_in='PSXRECOMP_HD_EMISSIVE=1; default off',formula='RGB * mix(vertex_rgb * 2, 1, mask / 255)',
            alpha_stp_unchanged=True,raw_primitives_unchanged=True,native_fallback_unchanged=True,
            async_single_worker=True,mask_bytes_in_existing_cpu_budget=True,extra_gl_mask_budget_bytes=64*1024*1024),
        mask_files=f['emissive_masks'],visuals=visuals,poster=poster,pacing_pair=pairs,
        limitations=['A single two-run opening pair is not a full-stage cadence/audio test or a settled no-overhead claim.',
            'Initial audio-buffer fill differs between legs; starvation differences cannot be attributed solely to masks.',
            'One-Hz sequential telemetry has frame quantization and request-time differences; small FPS differences are not speed claims.',
            'The two 2160p captures are sequential and not frame-aligned; no pixel-matched brightness ratio is claimed.',
            'Visual fly-pasts used the disclosed timer-only aid; recorder-off pacing runs used no survival aid.',
            'The full170-second recording still accumulated audio starvation. Stage clear and production installation remain unverified.'])
    write(target,report)
    provenance=OUT/'provenance.json';pr=read(provenance)
    for item,label in [(x['still'],'Canyon emissive '+('on' if x['enabled'] else 'off')) for x in visuals]+[(poster,'Updated complete facade')]:
        assert not any(x['path']==item['path'] for x in pr['assets'])
        pr['assets'].append(dict(path=item['path'],sha256=item['sha256'],bytes=item['bytes'],dimensions=item['dimensions'],
            category='actual_capture',status='Private timer-assisted live capture; release acceptance open',label=label,
            source_identifier=item['source']['path'],source_sha256=item['source']['sha256'],unmodified_copy=False,
            pixel_identical_to_source=True,processing=item['processing'],embedded_metadata_present=False))
    video=f['video'];assert not any(x['path']==video['path'] for x in pr['video_assets'])
    pr['video_assets'].append(dict(path=video['path'],sha256=video['sha256'],bytes=video['bytes'],category='actual_gameplay_capture',
        status='Continuous full facade entry-to-exit; timer-only aid; no firing; full-stage/audio remain open',
        result_manifest=facade.relative_to(ROOT).as_posix(),processing='Contiguous stream-copy excerpt; no retiming, interpolation, scaling, re-encoding or internal cuts',
        retimed=False,interpolated_frames=False))
    pr.update(image_count=len(pr['assets']),total_image_bytes=sum(x['bytes'] for x in pr['assets']),
        video_count=len(pr['video_assets']),total_video_bytes=sum(x['bytes'] for x in pr['video_assets']))
    for x in pr['assets']+pr['video_assets']:
        path=ROOT/x['path'];assert path.stat().st_size==x['bytes'] and sha(path)==x['sha256']
    write(provenance,pr)
    print(json.dumps(dict(result=str(target),pacing=pairs,images=pr['image_count'],videos=pr['video_count'])))

if __name__=='__main__':main()
