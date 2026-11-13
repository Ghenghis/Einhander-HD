"""Record a fresh assembled-world visual pass; never install a candidate.

Actual window recording, ordinary no-fire positioning, turbo/rewind off and
the disclosed 180-second timer-only aid. This is not stage-clear or recorder-off
performance acceptance. Prepare verifies frozen PNGs without using the GPU.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from types import SimpleNamespace

import run_stage1_pacing_ab as pacing
import launch_ui_candidate as ui
import ui_candidate_probe as probe
from native_ui_facade_route import enter_city
from run_facade_ab_probe import close
from run_h24_facade_review import SurvivalAid

CENTRAL='52F33418-5E9B9AC3'
NEIGHBOR='74EF95B7-B30D16F0'

def emit(row):print(json.dumps(row),flush=True)

def recorder_command(report,output,backend,seconds):
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise ValueError('Existing FFmpeg required')
    arguments=report['launches']['candidate']['arguments']
    title=arguments[arguments.index('--window-title')+1]
    prefix=[ffmpeg,'-hide_banner','-loglevel','error','-n']
    if backend=='gfxcapture':
        import ctypes
        user=ctypes.windll.user32
        user.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p]
        user.FindWindowW.restype=ctypes.c_void_p
        user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        hwnd=user.FindWindowW(None,title);pid=ctypes.c_ulong()
        if not hwnd:raise RuntimeError('Owned game window not found')
        user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        marker=pacing.base.read(Path(report['evidence'])/'launch-candidate.json')
        if pid.value!=marker['pid']:raise RuntimeError('Capture window does not belong to the owned runtime')
        source=f'gfxcapture=hwnd={hwnd}:capture_cursor=0:capture_border=0:display_border=0:max_framerate=60:output_fmt=bgra'
        return prefix+['-f','lavfi','-i',source,'-t',str(seconds),'-an','-c:v','h264_nvenc',
            '-preset','p4','-rc','vbr','-cq','18','-b:v','10M','-maxrate','12M','-bufsize','24M',
            '-fps_mode','passthrough','-movflags','+faststart',str(output)]
    return prefix+['-f','gdigrab','-framerate','30','-draw_mouse','0','-i','title='+title,
        '-t',str(seconds),'-an','-c:v','libx264','-preset','veryfast','-crf','18',
        '-pix_fmt','yuv420p','-movflags','+faststart',str(output)]

def prepare(args):
    candidate=json.loads(args.candidate.read_bytes())
    if candidate.get('production_installed') is not False:
        raise ValueError('Explicit private composed candidate required')
    files=candidate['files']
    if len(files)!=candidate['final_count']:raise ValueError('Candidate census changed')
    for row in files:
        if ui.sha(row['composed_path'])!=row['sha256']:
            raise ValueError('Frozen PNG changed: '+row['name'])
    config=SimpleNamespace(batch=args.batch,runtime=args.runtime,candidate=args.candidate,
        gpu_queries=0,world_sampling=args.world_sampling,opaque_batch=args.opaque_batch,guest_frames=0)
    report=pacing.prepare('hd-on_rewind-off',config)
    if args.route_profile:report['route_reference_profile']=args.route_profile
    directory=Path(report['evidence'])
    report['visual_profile']=dict(kind='assisted assembled-world fly-past',
        normal_clock_settings=True,stable_60fps_established=False,ordinary_fire=False,
        timer_only_assistance=True,lease_seconds=180,stage_clear_acceptance=False)
    report['visual_profile'].update(recorder_backend=args.recorder,capture_seconds=args.capture_seconds)
    report['visual_profile']['native_menus']=bool(args.native_menus)
    if args.native_menus:
        control=directory/'replacement-control.txt';control.write_text('0\n')
        report['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_PROOF_CONTROL']=str(control)
        report['route_reference_profile']='native-stock'
    pacing.base.write(directory/'candidate.json',report)
    emit(dict(prepared=str(directory),verified_frozen_pngs=len(files)))

def run(args):
    directory=pacing.ROOT/args.batch/'hd-on_rewind-off'
    report=pacing.base.read(directory/'candidate.json')
    if (directory/'world-flypast-proof.json').exists() or (directory/'launch-candidate.json').exists():
        raise ValueError('Fresh prepared run required')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise ValueError('Existing FFmpeg required')
    ui.copy_verified(Path(__file__),directory/'executed-world-flypast.py')
    ui.copy_verified(Path(__file__).with_name('run_h24_facade_review.py'),directory/'executed-survival-helper.py')
    proof=dict(started_at_utc=ui.stamp(),candidate=pacing.base.ref(directory/'candidate.json'),
        errors=[],observations=[],target_draws=[],ordinary_fire=False,state_loads=False,
        stage_clear_verified=False,live_visual_accepted=False,production_installed=False)
    process=None;aid=None;recorder=None;recording=False
    try:
        process=pacing.launch(report)
        proof['route']=enter_city(report,poll_seconds=.25)
        if report['visual_profile'].get('native_menus'):
            control=directory/'replacement-control.txt'
            if control.read_text()!='0\n':raise RuntimeError('Native-menu control changed before gameplay')
            control.write_text('1\n')
            proof['replacement_enabled_after_native_menus']=dict(at_utc=ui.stamp(),
                control=pacing.base.ref(control),menu_art_acceptance=False)
        def owned_identity(unused):
            # launch() already validated PID/path before observing title. The
            # retained Popen handle proves this same owned process is still live.
            marker=pacing.base.read(directory/'launch-candidate.json')
            if process.poll() is not None or marker['pid']!=process.pid:
                raise RuntimeError('Owned runtime is no longer live')
            return marker
        aid=SurvivalAid(report,owned_identity,ui.command,ui.stamp)
        proof['turbo_off']=probe.request(report,'turbo',enabled=0)
        assert probe.request(report,'turbo_state')['enabled']==0
        native=directory/'native-world-flypast';native.mkdir()
        proof['research_start']=probe.request(report,'research_capture',op='start',path=native.as_posix(),
            max_sources=256,max_records=20000,max_events=3,max_frames=16000,
            max_seconds=180,max_bytes=134217728,source_policy='all')
        recording=True
        output=directory/'world-flypast-original.mp4'
        backend=report['visual_profile'].get('recorder_backend','gdigrab')
        seconds=report['visual_profile'].get('capture_seconds',170)
        command=recorder_command(report,output,backend,seconds)
        proof['video']=dict(path=str(output),arguments=command,started_at_utc=ui.stamp(),
            scope='Actual window, no interpolation, retiming or scene cuts; silent; capture load affects cadence')
        recorder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        start=time.monotonic()
        proof['park_input']=probe.request(report,'press',buttons=0xFF3F,frames=72)
        cursor=0;tail='';shots=directory/'observations';shots.mkdir()
        for second in range(seconds+1):
            time.sleep(max(0,start+second-time.monotonic()))
            if (directory/'STOP').exists():
                proof['local_stop_marker']=True;break
            journal=native/'capture.jsonl'
            if journal.exists():
                with journal.open(encoding='utf-8') as stream:
                    stream.seek(cursor);data=tail+stream.read();cursor=stream.tell()
                lines=data.split('\n');tail=lines.pop()
                for line in lines:
                    if '"replacement_gl_draw_submitted"' not in line:continue
                    row=json.loads(line)
                    if row.get('key') in (CENTRAL,NEIGHBOR):
                        proof['target_draws'].append(dict(row,observed_elapsed_seconds=time.monotonic()-start))
            row=dict(elapsed_seconds=time.monotonic()-start,
                registers=probe.request(report,'get_registers'),
                lives=probe.request(report,'read_ram',addr='0x800813C4',len=1),
                audio=probe.request(report,'audio_stats'))
            if second%15==0:
                row['screenshot']=probe.request(report,'screenshot',path=(shots/f'native-{second:03}.png').as_posix())
                row['composed']=probe.capture(report,f'world-{second:03}',hires=False)
                emit(dict(elapsed=second,frame=row['registers'].get('frame'),
                    target_samples=len(proof['target_draws']),capture=row['composed']['path']))
            proof['observations'].append(row)
            with (directory/'visual-observations.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
            if recorder.poll() is not None:break
    except Exception as error:proof['errors'].append(str(error))
    finally:
        if recorder is not None:
            try:
                _,err=recorder.communicate(input=b'q\n' if recorder.poll() is None else None,timeout=25)
                proof['video'].update(exit=recorder.returncode,stderr=err.decode(errors='replace')[-2000:],ended_at_utc=ui.stamp())
                if recorder.returncode or not output.is_file() or output.stat().st_size<1024:
                    proof['errors'].append('Window recorder failed to produce a usable video')
            except Exception as error:proof['errors'].append('Video: '+str(error))
        worker_stopped=True
        if aid is not None:
            try:proof['survival_assistance']=aid.stop()
            except Exception as error:
                worker_stopped=False;proof['errors'].append('Survival helper: '+str(error))
        if recording and worker_stopped:
            try:
                proof['input_release']=probe.request(report,'clear_input')
                proof['turbo_end']=probe.request(report,'turbo_state')
                proof['research_stop']=probe.request(report,'research_capture',op='stop')
            except Exception as error:proof['errors'].append('Research stop: '+str(error))
        if process is not None and worker_stopped:
            try:proof['close']=close(report)
            except Exception as error:proof['errors'].append('Close: '+str(error))
            try:proof['owned_process_exit']=process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate();proof['owned_process_forced_cleanup']=True
                proof['owned_process_exit']=process.wait(timeout=5)
        writes=[];forbidden=[]
        for receipt in (directory/'commands').glob('*.json'):
            row=pacing.base.read(receipt);request=row['request']
            if request['cmd'] in ('load_state','save_state'):forbidden.append(request)
            if request['cmd']=='write_ram':
                writes.append(row)
                if request.get('addr')!='0x80085718' or request.get('val')!='0xA5':forbidden.append(request)
        proof['command_audit']=dict(timer_write_requests=len(writes),
            successful_timer_writes=sum(row['reply'].get('ok') is True for row in writes),
            forbidden_mutations=forbidden)
        if forbidden:proof['errors'].append('Command audit found a mutation outside the timer aid')
        proof['ended_at_utc']=ui.stamp()
        pacing.base.write(directory/'world-flypast-proof.json',proof)
        emit(dict(evidence=str(directory),errors=proof['errors'],target_samples=len(proof['target_draws'])))
    if proof['errors'] or not proof.get('close',{}).get('port_closed'):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--batch',required=True)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--runtime',type=Path)
    p.add_argument('--world-sampling',type=int,choices=[0,1],default=0)
    p.add_argument('--opaque-batch',type=int,choices=[0,1],default=0)
    p.add_argument('--route-profile',choices=['hd','assembled-v1'],default=None)
    p.add_argument('--native-menus',action='store_true',help='Verified stock menu route, then enable the entire frozen pack for gameplay; no new-menu acceptance')
    p.add_argument('--recorder',choices=['gdigrab','gfxcapture'],default='gdigrab')
    p.add_argument('--capture-seconds',type=int,choices=[120,150,170],default=170)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--run-prepared',action='store_true')
    args=p.parse_args()
    if not __import__('re').fullmatch('[a-zA-Z0-9_-]+',args.batch):p.error('Use one directory name')
    if not args.run_prepared:
        if not args.candidate or not args.runtime:p.error('Preparation needs candidate and runtime')
        prepare(args)
    if not args.prepare_only:run(args)
