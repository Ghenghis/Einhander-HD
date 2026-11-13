"""Publish closed W3 gameplay evidence with packet and artwork identity checks."""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
import shutil
import subprocess
from publish_stage1_wave2_results import E,OUT,read,sha,write,reference,probe,registered_key

def closed(run):
    proof=read(run/'robin-proof.json')
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    assert not proof.get('owned_process_forced_cleanup')
    assert all(proof[k] is False for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    return proof

def attempt(name):
    run=E/name/'hd-on_rewind-off';p=closed(run);a=p['gameplay_observations'];first,last=a[0],a[-1]
    attempts=p.get('verified_continues',{}).get('attempts',[])
    return dict(run_id=name,proof=reference(run/'robin-proof.json'),observed_seconds=last['elapsed_seconds']-first['elapsed_seconds'],
        verified_continue_limit=p.get('verified_continues',{}).get('limit',0),
        verified_continues=sum('resumed' in x for x in attempts),
        stage_clear_verified=False,clean_exit=True,remaining_lives=int(last['lives']['hex'],16))

def main():
    run=E/'astraea-w3-hd-v1/hd-on_rewind-off';proof=closed(run)
    candidate=E/'frozen-w3-extras-v1/candidate.json';pack=read(candidate)
    native=read(candidate.parent/'native-verification-v2.json');assert native['exit_code']==0 and native['candidate_sha256']==sha(candidate)
    native_counts=json.loads(native['stdout']);assert native_counts==dict(keys=1669,region_checks=226,failures=0)
    planfile=Path(pack['composition_plan']['path']);assert sha(planfile)==pack['composition_plan']['sha256']
    plan=read(planfile);assert len(plan['entries'])==837 and pack['authored_entries']==837 and pack['final_count']==1669
    commands=[json.loads(x)['command'] for x in (run/'robin-commands.jsonl').read_text().splitlines()]
    assert set(x['cmd'] for x in commands)<={'read_ram','press','clear_input','get_registers','player_draw'}
    assert proof['turbo_state']['enabled']==0 and proof['hull_guard_initial']['source_set']==4
    events=[json.loads(x) for x in (run/'first-submissions.jsonl').read_text().splitlines()]
    draws=[x for x in events if x['event']=='replacement GL draw submitted'];first_draw={}
    for x in draws:first_draw.setdefault(x['key'],x)
    groups=defaultdict(lambda:dict(entries=0,positively_submitted_entries=0));submitted=[]
    files={x['name']:x for x in pack['files']}
    for row in plan['entries']:
        key=registered_key(row);f=files[key+'.png'];assert f['input']==row and sha(Path(f['composed_path']))==f['sha256']
        family=Path(row['manifest']['path']).parent.name;groups[family]['entries']+=1
        if key in first_draw:
            groups[family]['positively_submitted_entries']+=1
            submitted.append(dict(key=key,source_key=row['key'],family=family,png_sha256=f['sha256'],first_submission=first_draw[key]))
    source=Path(proof['video']['path']);assert sha(source)==proof['video']['sha256']
    video=OUT/'stage1-wave3-astraea-gameplay.mp4';assert not video.exists()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss','8','-i',str(source),'-t','32',
        '-map','0:v:0','-c','copy','-an','-avoid_negative_ts','make_zero','-movflags','+faststart',str(video)],check=True)
    original=probe(source,True)['packets'];excerpt=probe(video,True)['packets'];hashes=[x['data_hash'] for x in excerpt]
    starts=[i for i,p in enumerate(original) if p['data_hash']==hashes[0] and [q['data_hash'] for q in original[i:i+len(excerpt)]]==hashes]
    assert len(starts)==1;offset=starts[0];packets=original[offset:offset+len(excerpt)];timing={}
    for field in ['pts_time','dts_time']:
        delta=float(packets[0][field])-float(excerpt[0][field]);error=max(abs(float(a[field])-float(b[field])-delta) for a,b in zip(packets,excerpt));assert error<.000003;timing[field]=error
    still=OUT/'stage1-wave3-astraea.png';assert not still.exists();shutil.copyfile(run/'captures/robin-0030.png',still)
    dense=[]
    for f in sorted((run/'observations').glob('gpu-frame-*.json')):
        d=read(f);assert d['ok'] and d['count']==len(d['entries']);dense.append(dict(**reference(f),frame=d['frame'],commands=d['count']))
    first,last=proof['gameplay_observations'][0],proof['gameplay_observations'][-1];seconds=last['elapsed_seconds']-first['elapsed_seconds']
    result=dict(schema_version=1,run_id='astraea-w3-hd-v1',source_proof=reference(run/'robin-proof.json'),candidate=reference(candidate),
        authored_entries=837,pack_keys=1669,native_validation=native_counts,first_occurrence_log=reference(run/'first-submissions.jsonl'),
        controls=dict(craft='Astraea FGA Mk.I',native_menus=True,new_menu_art_accepted=False,fire='Cross and Square',
            movement='upper_lane; completed-frame hull geometry feedback',hull_source_set=4,ram_writes=False,state_loads=False,timer_assistance=False,
            rewind=False,turbo=False,player_material='stock; authored PNG colours',source_capture=True,video=True,dense_gp0_frames=True,hires_stills=True,
            opaque_batch=True,short_upload_priority=True),
        authored_submission_count=len(submitted),groups=dict(groups),positive_submissions=submitted,dense_frames=dense,
        performance=dict(seconds=seconds,guest_frames_per_second=(last['registers']['frame']-first['registers']['frame'])/seconds,
            audio_starved_sample_frames_delta=last['audio']['out']['underruns']-first['audio']['out']['underruns'],
            scope='Recorded interval with source dumps, dense GP0 rings and sequential 2160p readbacks; not final pacing acceptance'),
        outcome=attempt('astraea-w3-hd-v1'),previous_stage_attempts=[attempt('mk3-stage1-long-v1'),attempt('mk3-upper-v1')],
        video=dict(**reference(video),probe=probe(video),source=reference(source),contiguous_source_packets=len(excerpt),source_first_packet=offset,
            source_start_pts_seconds=min(float(x['pts_time']) for x in packets),source_end_pts_seconds=max(float(x['pts_time'])+float(x.get('duration_time','0')) for x in packets),
            max_relative_timestamp_error_seconds=timing,silent=True,retimed=False,interpolated=False,reencoded=False),
        still=dict(**reference(still),source_capture=reference(run/'captures/robin-0030.json')),
        exclusions=['Greif v2 failed native-centre transparency checks and is not included.',
            '157 historical HUD fade aliases still lack actual CLUT bytes; no palettes were invented.'],
        limitations=['Positive GL submission proves admission, not every pose, palette, UV seam or material-quality acceptance.',
            'Missing receipts do not prove a texture was never drawn.',
            'Dense GP0 rings, composed frames and 2160p readbacks are sequential, not atomic or a full replay.',
            'No stage clear, all-weapon, audio, normal-launcher, installation or full-remaster completion claim.'])
    target=OUT/'stage1-wave3-results.json';assert not target.exists();write(target,result)
    print(json.dumps(dict(results=str(target),submitted=len(submitted),groups=dict(groups),performance=result['performance'],outcome=result['outcome'])))

if __name__=='__main__':main()
