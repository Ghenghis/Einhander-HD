"""Publish the closed Mk.III qualification recording and six positive bindings."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference,probe,registered_key

def main():
    run=E/'mk3-authored-hd-v1/hd-on_rewind-off';proof=read(run/'robin-proof.json')
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    assert not proof.get('owned_process_forced_cleanup')
    assert all(proof[k] is False for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    candidate=E/'frozen-mk3-v2/candidate.json';pack=read(candidate);native=read(candidate.parent/'native-verification.json')
    assert native['candidate_sha256']==sha(candidate) and native['failures']==0 and native['region_checks']==220
    plan_path=Path(pack['composition_plan']['path']);assert sha(plan_path)==pack['composition_plan']['sha256']
    entries=read(plan_path)['entries'][-6:];assert pack['authored_entries']==729 and pack['final_count']==1562
    log=run/'first-submissions.jsonl';draws=[x for x in (json.loads(s) for s in log.read_text().splitlines()) if x['event']=='replacement GL draw submitted']
    evidence=[]
    for row in entries:
        key=registered_key(row);file=next(x for x in pack['files'] if x['name']==key+'.png')
        assert file['input']==row and sha(Path(file['composed_path']))==file['sha256']
        actual=next(x for x in draws if x['key']==key)
        evidence.append(dict(key=key,source_key=row['key'],png_sha256=file['sha256'],first_submission=actual))
    source=Path(proof['video']['path']);assert sha(source)==proof['video']['sha256']
    video=OUT/'stage1-mk3-gameplay.mp4';assert not video.exists()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss','8','-i',str(source),'-t','24',
                    '-map','0:v:0','-c','copy','-an','-avoid_negative_ts','make_zero','-movflags','+faststart',str(video)],check=True)
    original=probe(source,True)['packets'];excerpt=probe(video,True)['packets'];hashes=[x['data_hash'] for x in excerpt]
    starts=[i for i,p in enumerate(original) if p['data_hash']==hashes[0] and [q['data_hash'] for q in original[i:i+len(excerpt)]]==hashes]
    assert len(starts)==1;offset=starts[0];packets=original[offset:offset+len(excerpt)];timing={}
    for field in ['pts_time','dts_time']:
        delta=float(packets[0][field])-float(excerpt[0][field]);error=max(abs(float(a[field])-float(b[field])-delta) for a,b in zip(packets,excerpt));assert error<.000003;timing[field]=error
    still=OUT/'stage1-mk3-hull.png';assert not still.exists();shutil.copyfile(run/'captures/robin-0015.png',still)
    dense=[]
    for f in sorted((run/'observations').glob('gpu-frame-*.json')):
        d=read(f);assert d['ok'] and d['count']==len(d['entries'])
        dense.append(dict(**reference(f),frame=d['frame'],commands=d['count'],maximum_words_per_command=d['max_words']))
    first,last=proof['gameplay_observations'][0],proof['gameplay_observations'][-1]
    seconds=last['elapsed_seconds']-first['elapsed_seconds'];frames=last['registers']['frame']-first['registers']['frame']
    report=dict(schema_version=1,run_id='mk3-authored-hd-v1',source_proof=reference(run/'robin-proof.json'),candidate=reference(candidate),
        native_validation=native,authored_entries=729,pack_keys=1562,
        controls=dict(craft='Endymion FRS Mk.III',native_menus=True,new_menu_art_accepted=False,player_material='stock; authored PNG colours',
            movement='left_lane',fire='Cross and Square',ram_writes=False,state_loads=False,timer_assistance=False,automatic_continue=False,
            rewind=False,turbo=False,source_capture=True,video=True,dense_gp0_frames=True,opaque_batch=True),
        new_bindings=evidence,first_occurrence_log=reference(log),
        performance=dict(seconds=seconds,guest_frames=frames,guest_frames_per_second=frames/seconds,
            audio_starved_sample_frames_delta=last['audio']['out']['underruns']-first['audio']['out']['underruns'],
            scope='Whole observed interval with recording, source dumps, dense-frame queries and stills; not recorder-off pacing acceptance'),
        outcome=dict(clean_exit=True,exit_code=0,errors=[],remaining_lives=int(last['lives']['hex'],16),stage_clear_verified=False),
        video=dict(**reference(video),probe=probe(video),source=reference(source),contiguous_source_packets=len(excerpt),source_first_packet=offset,
            source_start_pts_seconds=min(float(x['pts_time']) for x in packets),
            source_end_pts_seconds=max(float(x['pts_time'])+float(x.get('duration_time','0')) for x in packets),
            max_relative_timestamp_error_seconds=timing,silent=True,retimed=False,interpolated=False,reencoded=False),
        still=dict(**reference(still),source_capture=reference(run/'captures/robin-0015.json')),
        dense_frames=dense,limitations=['All six positive submissions establish admission, not all poses, blend phases, UV seams or material-quality acceptance.',
            'Dense GP0 rings are sequential with screenshots; ring limits and the12-word payload bound apply; not atomic or complete replay.',
            'Retained native geometry, saturated palette phases and model-kit-like material appearance still need review.',
            'No stage clear, boss-clear, all-weapon, audio, normal launcher, installation or full-remaster completion claim.'])
    target=OUT/'stage1-mk3-results.json';assert not target.exists();write(target,report)
    print(json.dumps(dict(new_bindings=len(evidence),dense_frames=len(dense),video_bytes=video.stat().st_size,performance=report['performance'],outcome=report['outcome'])))

if __name__=='__main__':main()
