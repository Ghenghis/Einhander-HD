"""Publish a closed, unassisted W2 gameplay observation without retiming it."""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
RUN=E/'robin-wave2-hd-v1/hd-on_rewind-off'
OUT=ROOT/'docs/media/gallery'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def reference(path):return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size)
def probe(path,packets=False):
    command=['ffprobe','-v','error','-select_streams','v:0','-of','json']
    command+=['-show_packets','-show_data_hash','sha256','-show_entries','packet=pts_time,dts_time,duration_time,data_hash'] if packets else ['-show_entries','format=duration:stream=codec_name,width,height,avg_frame_rate,nb_frames']
    return json.loads(subprocess.check_output(command+[str(path)]))

def main():
    proof=read(RUN/'robin-proof.json')
    assert not proof['errors'] and proof['close']['port_closed'] and proof['owned_process_exit']==0
    assert not proof.get('owned_process_forced_cleanup')
    assert all(proof[k] is False for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    commands=[json.loads(x)['command'] for x in (RUN/'robin-commands.jsonl').read_text().splitlines()]
    assert set(x['cmd'] for x in commands)<={'read_ram','press','clear_input','get_registers','player_draw'}
    assert proof['turbo_state']['enabled']==0
    source=Path(proof['video']['path']);assert sha(source)==proof['video']['sha256']
    candidate_path=E/'frozen-wave2-fx-v1/candidate.json';candidate=read(candidate_path)
    plan_path=Path(candidate['composition_plan']['path']);assert sha(plan_path)==candidate['composition_plan']['sha256']
    entries=read(plan_path)['entries'];assert len(entries)==723 and candidate['final_count']==1559
    events=[json.loads(x) for x in (RUN/'native-source-0/capture.jsonl').read_text().splitlines()]
    draws=[x for x in events if x.get('event')=='replacement_gl_draw_submitted']
    submitted=Counter(x['key'] for x in draws)
    groups=defaultdict(lambda:dict(entries=0,submitted_entries=0))
    ledger=[]
    for row in entries:
        key=row['key']
        if row.get('exact'):
            exact=row['exact'];w,h=exact['source_shape_words'];ppw=4>>exact['depth']
            l,t,r,b=exact['uv'];words=Path(exact['source_words']['path']).read_bytes()
            clut=Path(exact['source_clut']['path']).read_bytes()
            cropped=b''.join(words[(y*w+l//ppw)*2:(y*w+r//ppw)*2] for y in range(t,b))
            key=f'{zlib.crc32(cropped):08X}-{zlib.crc32(clut) if exact["depth"]<2 else 0:08X}'
        composed=next(x for x in candidate['files'] if x['name']==key+'.png')
        assert composed['input']==row,'Coverage must identify the actual composed registration'
        group=Path(row['manifest']['path']).parent.name;group_row=groups[group]
        group_row['entries']+=1;group_row['submitted_entries']+=int(bool(submitted[key]))
        ledger.append(dict(key=key,source_page_or_upload_key=row['key'],group=group,sampled_submissions=submitted[key],
                           authored_image_sha256=row['image']['sha256']))
    observations=proof['gameplay_observations'];first,last=observations[0],observations[-1]
    seconds=last['elapsed_seconds']-first['elapsed_seconds'];frames=last['registers']['frame']-first['registers']['frame']
    video=OUT/'stage1-wave2-gameplay.mp4'
    if not video.exists():
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-ss','70','-i',str(source),
                        '-t','34','-map','0:v:0','-c','copy','-an','-avoid_negative_ts','make_zero','-movflags','+faststart',str(video)],check=True)
    original_packets=probe(source,True)['packets'];excerpt_packets=probe(video,True)['packets']
    starts=[i for i,p in enumerate(original_packets) if p['data_hash']==excerpt_packets[0]['data_hash']]
    matches=[i for i in starts if [p['data_hash'] for p in original_packets[i:i+len(excerpt_packets)]]==[p['data_hash'] for p in excerpt_packets]]
    assert len(matches)==1,'Excerpt must be one unchanged contiguous source packet sequence'
    start=matches[0];a=original_packets[start:start+len(excerpt_packets)];b=excerpt_packets
    timing={}
    for field in ['pts_time','dts_time']:
        delta=float(a[0][field])-float(b[0][field])
        timing[field]=max(abs(float(x[field])-float(y[field])-delta) for x,y in zip(a,b))
        assert timing[field]<.000003,'Excerpt timing changed'
    stills=[]
    for original,name in [('captures/robin-0030.png','effects'),('captures/robin-0150.png','continue'),('captures/robin-0165.png','evaluation')]:
        target=OUT/f'stage1-wave2-{name}.png'
        if target.exists():assert sha(target)==sha(RUN/original)
        else:shutil.copyfile(RUN/original,target)
        stills.append(dict(**reference(target),source=original))
    result=dict(schema_version=2,run_id='robin-wave2-hd-v1',kind='Actual unassisted gameplay observation; stage-clear attempt failed',
        supersedes='stage1-wave2-results.json',correction='Use composed exact-region CRC keys for coverage instead of full source-page keys; original v1 receipt retained.',
        source_proof=reference(RUN/'robin-proof.json'),candidate=reference(candidate_path),composition_plan=reference(plan_path),
        controls=dict(ram_writes=False,state_loads=False,timer_assistance=False,invincible=False,automatic_continue=False,
            turbo=False,rewind=False,opaque_batch=True,source_capture=True,video_recording=True,
            native_menus=True,new_menu_art_accepted=False,movement='MkII completed-frame draw_lane',fire='cross and square'),
        performance=dict(seconds=seconds,guest_frames=frames,guest_frames_per_second=frames/seconds,
            audio_starved_sample_frames_delta=last['audio']['out']['underruns']-first['audio']['out']['underruns'],
            scope='Whole observed interval including death, Continue and Total Evaluation; recorder/source capture active'),
        outcome=dict(stage_clear_verified=False,continue_observed_seconds=150,evaluation_observed_seconds=165,
            player_last_hull_frame=last['hull_draw']['frame'],clean_exit=True,owned_process_exit=0,errors=[]),
        video=dict(**reference(video),probe=probe(video),source=reference(source),
            contiguous_original_packets=len(b),source_first_packet=start,
            source_start_pts_seconds=min(float(p['pts_time']) for p in a),
            source_end_pts_seconds=max(float(p['pts_time'])+float(p.get('duration_time','0')) for p in a),
            max_relative_timestamp_error_seconds=timing,silent=True,retiming=False,interpolation=False,reencoding=False),
        stills=stills,coverage=dict(authored_entries=len(entries),authored_entries_submitted=sum(bool(x['sampled_submissions']) for x in ledger),
            all_submitted_keys=len(submitted),groups=dict(sorted(groups.items())),entries=ledger),
        limitations=['GL submission samples are not visible-pixel or complete animation proof.',
            'Unassisted refers to survival: ordinary automated controller input was used.',
            'No full-stage, boss-clear, audible-audio, all-menu, all-palette or installed-release acceptance.',
            'This v2 effects observation is not a matched v1/v2 A/B test; bright-background class-boundary outlines remain under review.',
            'Source capture is bounded and sampled; it is not a complete replay.'])
    target=OUT/'stage1-wave2-results-v2.json';assert not target.exists(),'Keep published proof immutable; use a new revision'
    write(target,result)
    print(json.dumps({k:result[k] for k in ['performance','outcome']}))
    print(json.dumps(dict(video_bytes=video.stat().st_size,submitted=result['coverage']['authored_entries_submitted'],
                          authored=len(entries),groups=result['coverage']['groups'])))

if __name__=='__main__':main()
