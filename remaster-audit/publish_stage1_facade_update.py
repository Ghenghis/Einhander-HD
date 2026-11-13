"""Publish one visually reviewed continuous facade excerpt, preserving packets."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference,probe,registered_key

TARGETS=('52F33418-5E9B9AC3','74EF95B7-B30D16F0')
BUILDING_SOURCE_KEYS={'73BF9877-'+p for p in ['340FAA72','69C9A539','6DA2ED40','71A3A874','79FE4168',
    '8117EEA2','A4E0D3C8','BABFCA62','BE204159','E0D47A6A']}

def interval(rows):
    a,b=rows[0],rows[-1];seconds=b['elapsed_seconds']-a['elapsed_seconds']
    assert seconds>0 and b['registers']['frame']>a['registers']['frame']
    return dict(start_elapsed_seconds=a['elapsed_seconds'],end_elapsed_seconds=b['elapsed_seconds'],wall_seconds=seconds,
        first_guest_frame=a['registers']['frame'],last_guest_frame=b['registers']['frame'],
        guest_fps=(b['registers']['frame']-a['registers']['frame'])/seconds,
        audio_starved_sample_frames_delta=b['audio']['out']['underruns']-a['audio']['out']['underruns'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch',required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--prefix',required=True);p.add_argument('--clip-start',type=float,required=True);p.add_argument('--clip-seconds',type=float,required=True)
    p.add_argument('--native-verification',type=Path,required=True)
    p.add_argument('--entry-exit-reviewed',action='store_true')
    a=p.parse_args();assert __import__('re').fullmatch('[a-z0-9-]+',a.prefix) and 0<=a.clip_start<170 and 10<=a.clip_seconds<=90
    assert a.entry_exit_reviewed,'Review original footage/stills for complete entry and exit before publication'
    run=(E/a.batch/'hd-on_rewind-off').resolve();assert run.parent.parent==E.resolve()
    proof=read(run/'world-flypast-proof.json');report=read(run/'candidate.json')
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    assert not proof.get('owned_process_forced_cleanup') and proof['video']['exit']==0
    assert proof['ordinary_fire'] is False and proof['state_loads'] is False and proof['stage_clear_verified'] is False
    assert proof['turbo_end']['enabled']==0 and not proof['command_audit']['forbidden_mutations']
    assert report['pacing_profile']['hd_pack_enabled'] and not report['pacing_profile']['rewind_enabled']
    aid=proof['survival_assistance'];assert aid['successful_writes']>0 and not aid['lives_writes'] and not aid['stage_jumps']
    pack=read(a.candidate);assert pack['production_installed'] is False
    validation=read(a.native_verification);assert validation['exit_code']==0 and validation['candidate_sha256']==sha(a.candidate)
    native=json.loads(validation['stdout']);assert native['keys']==pack['final_count'] and native['failures']==0
    build_ref=report['pacing_profile']['runtime_build'];build_path=Path(build_ref['path']);assert sha(build_path)==build_ref['sha256']
    runtime=read(build_path);assert sha(Path(report['launches']['candidate']['arguments'][0]))==runtime['executable_sha256']
    planfile=Path(pack['composition_plan']['path']);assert sha(planfile)==pack['composition_plan']['sha256'];plan=read(planfile)
    events=[json.loads(x) for x in (run/'native-world-flypast/capture.jsonl').read_text().splitlines()]
    draws=[x for x in events if x.get('event')=='replacement_gl_draw_submitted'];bykey=defaultdict(list)
    for x in draws:bykey[x['key']].append(x)
    assert all(bykey[k] for k in TARGETS),'Both full-facade mappings need positive GL evidence'
    files={x['name']:x for x in pack['files']};coverage=[];building=[]
    for row in plan['entries']:
        key=registered_key(row);f=files[key+'.png'];assert f['input']==row and sha(Path(f['composed_path']))==f['sha256']
        record=dict(key=key,family=Path(row['manifest']['path']).parent.name,png_sha256=f['sha256'],submitted_samples=len(bykey[key]))
        coverage.append(record)
        # One tile moved into w2-polish. Ownership follows its native source
        # identity, not the current authoring folder's name.
        if row['key'] in BUILDING_SOURCE_KEYS:building.append(record)
    assert len(building)==10 and all(x['submitted_samples'] for x in building),'All ten delivered building tiles must submit'
    source=Path(proof['video']['path']);video=OUT/(a.prefix+'.mp4');target=OUT/(a.prefix+'-results.json')
    assert not video.exists() and not target.exists()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss',str(a.clip_start),'-i',str(source),'-t',str(a.clip_seconds),
        '-map','0:v:0','-c','copy','-an','-avoid_negative_ts','make_zero','-movflags','+faststart',str(video)],check=True)
    original=probe(source,True)['packets'];excerpt=probe(video,True)['packets'];hashes=[x['data_hash'] for x in excerpt]
    starts=[i for i,x in enumerate(original) if x['data_hash']==hashes[0] and [y['data_hash'] for y in original[i:i+len(excerpt)]]==hashes]
    assert len(starts)==1;offset=starts[0];packets=original[offset:offset+len(excerpt)];errors={}
    for field in ['pts_time','dts_time']:
        shift=float(packets[0][field])-float(excerpt[0][field]);error=max(abs(float(x[field])-float(y[field])-shift) for x,y in zip(packets,excerpt))
        assert error<.000003;errors[field]=error
    rows=proof['observations'];first=min(x['frame'] for k in TARGETS for x in bykey[k]);last=max(x['frame'] for k in TARGETS for x in bykey[k])
    before=[x for x in rows if x['registers']['frame']<first];after=[x for x in rows if x['registers']['frame']>last];assert before and after
    bracket=[x for x in rows if before[-1]['elapsed_seconds']<=x['elapsed_seconds']<=after[0]['elapsed_seconds']]
    targets={k:dict(submitted_samples=len(bykey[k]),first_frame=min(x['frame'] for x in bykey[k]),last_frame=max(x['frame'] for x in bykey[k]),
        replacement_sizes=sorted({tuple(x['replacement_size']) for x in bykey[k]}),png_sha256=files[k+'.png']['sha256']) for k in TARGETS}
    result=dict(schema_version=1,run_id=a.batch,kind='Actual private timer-assisted no-fire full facade capture',source_proof=reference(run/'world-flypast-proof.json'),
        candidate=reference(a.candidate.resolve()),authored_entries=pack['authored_entries'],pack_keys=pack['final_count'],native_validation=native,
        runtime=dict(build_sha256=build_ref['sha256'],executable_sha256=runtime['executable_sha256']),
        emissive_masks=[dict(name=x['name'],sha256=x['sha256'],dimensions=x['dimensions'],bytes=x['bytes']) for x in pack.get('emissive_files',[])],
        controls=dict(ordinary_fire=False,turbo=False,rewind=False,state_loads=False,new_menu_art_accepted=False,
            emissive_masks=report['visual_profile'].get('emissive',False),hires_stills=report['visual_profile'].get('hires_stills',False),
            timer_only_aid=aid,command_audit=proof['command_audit']),
        targets=targets,building_tiles=building,coverage=dict(positively_submitted=sum(bool(x['submitted_samples']) for x in coverage),entries=coverage,
            limitation='Sampled submissions establish positive admission only; missing rows do not prove no draw'),
        performance=dict(full_recording=interval(rows),facade_submission_bracket=interval(bracket),sustained_full_stage_60fps_established=False,audible_audio_accepted=False),
        video=dict(**reference(video),probe=probe(video),source=reference(source),contiguous_source_packets=len(excerpt),source_first_packet=offset,
            max_relative_timestamp_error_seconds=errors,entry_exit_visually_reviewed=True,silent=True,retimed=False,interpolated=False,reencoded=False),
        clean_exit=True,stage_clear_verified=False,production_installed=False,
        limitations=['The disclosed timer aid establishes visual reachability, not unassisted survival or stage clear.',
            'Normal clock settings and preserved video timing do not establish sustained60fps.',
            'Static room/reflection artwork does not establish dynamic reflections or parallax.',
            'Art defects, full-stage/audio, remaining UI/actors and installation still require acceptance.'])
    write(target,result);print(json.dumps(dict(result=str(target),seconds=result['video']['probe']['format']['duration'],
        submitted=result['coverage']['positively_submitted'],performance=result['performance'])))

if __name__=='__main__':main()
