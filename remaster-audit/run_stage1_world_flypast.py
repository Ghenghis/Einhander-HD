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
    for row in candidate.get('emissive_files',[]):
        if ui.sha(row['composed_path'])!=row['sha256']:raise ValueError('Frozen emissive mask changed: '+row['name'])
    config=SimpleNamespace(batch=args.batch,runtime=args.runtime,candidate=args.candidate,
        gpu_queries=0,world_sampling=args.world_sampling,opaque_batch=args.opaque_batch,emissive=args.emissive,
        cpu_profile=args.cpu_profile,runtime_perf=args.runtime_perf,filter_state_cache=args.filter_state_cache,keep_bracket=args.keep_bracket,supersampling=args.supersampling,rewind_fmv_interval=args.rewind_fmv_interval,guest_frames=0)
    report=pacing.prepare('hd-on_rewind-'+('on' if args.rewind else 'off'),config)
    if args.route_profile:report['route_reference_profile']=args.route_profile
    directory=Path(report['evidence'])
    report['visual_profile']=dict(kind='assisted assembled-world fly-past',
        normal_clock_settings=True,stable_60fps_established=False,ordinary_fire=False,
        timer_only_assistance=True,lease_seconds=180,stage_clear_acceptance=False)
    report['visual_profile'].update(recorder_backend=args.recorder,capture_seconds=args.capture_seconds)
    report['visual_profile']['native_menus']=bool(args.native_menus)
    report['visual_profile'].update(emissive=bool(args.emissive),hires_stills=args.hires_stills)
    report['visual_profile'].update(record_video=not args.telemetry_only,source_capture=not args.telemetry_only,
        composed_stills=not args.telemetry_only,telemetry_only=args.telemetry_only,cpu_profile=bool(args.cpu_profile),runtime_perf=bool(args.runtime_perf))
    report['visual_profile'].update(retain_host_audio=bool(args.retain_host_audio),dirty_profile=bool(args.dirty_profile))
    report['visual_profile'].update(media_profile=bool(args.media_profile),rewind_capture=bool(args.rewind))
    if args.native_menus:
        control=directory/'replacement-control.txt';control.write_text('0\n')
        report['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_PROOF_CONTROL']=str(control)
        report['route_reference_profile']='native-stock-scale2' if args.supersampling==2 else 'native-stock'
    pacing.base.write(directory/'candidate.json',report)
    emit(dict(prepared=str(directory),verified_frozen_pngs=len(files)))

def run(args):
    directory=pacing.ROOT/args.batch/('hd-on_rewind-on' if args.rewind else 'hd-on_rewind-off')
    report=pacing.base.read(directory/'candidate.json')
    if (directory/'world-flypast-proof.json').exists() or (directory/'launch-candidate.json').exists():
        raise ValueError('Fresh prepared run required')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg and report['visual_profile'].get('record_video',True):raise ValueError('Existing FFmpeg required')
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
        if report['visual_profile'].get('source_capture',True):
            native=directory/'native-world-flypast';native.mkdir()
            proof['research_start']=probe.request(report,'research_capture',op='start',path=native.as_posix(),
                max_sources=256,max_records=20000,max_events=3,max_frames=16000,
                max_seconds=180,max_bytes=134217728,source_policy='all')
            recording=True
        seconds=report['visual_profile'].get('capture_seconds',170)
        if report['visual_profile'].get('record_video',True):
            output=directory/'world-flypast-original.mp4'
            backend=report['visual_profile'].get('recorder_backend','gdigrab')
            command=recorder_command(report,output,backend,seconds)
            proof['video']=dict(path=str(output),arguments=command,started_at_utc=ui.stamp(),
                scope='Actual window, no interpolation, retiming or scene cuts; silent; capture load affects cadence')
            recorder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        proof['measurement_load']=dict(video=recorder is not None,source_capture=recording,
            composed_stills=report['visual_profile'].get('composed_stills',True),timer_assistance=True)
        start=time.monotonic()
        proof['park_input']=probe.request(report,'press',buttons=0xFF3F,frames=72)
        cursor=0;tail='';shots=directory/'observations';shots.mkdir()
        for second in range(seconds+1):
            time.sleep(max(0,start+second-time.monotonic()))
            if (directory/'STOP').exists():
                proof['local_stop_marker']=True;break
            journal=native/'capture.jsonl' if recording else None
            if journal is not None and journal.exists():
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
            if report['visual_profile'].get('cpu_profile'):
                row['hd_cpu_profile']=probe.request(report,'hd_cpu_profile')
            if report['visual_profile'].get('dirty_profile') and second in (0,65,75,85,95,120,150,169):
                row['dirty_ram_stats']=probe.request(report,'dirty_ram_stats')
            if report['visual_profile'].get('media_profile'):
                row['fmv_state']=probe.request(report,'fmv_state')
                row['gpu_state']=probe.request(report,'gpu_state')
                row['cdrom_state']=probe.request(report,'cdrom_state')
            if second%15==0:
                if report['visual_profile'].get('composed_stills',True):
                    row['screenshot']=probe.request(report,'screenshot',path=(shots/f'native-{second:03}.png').as_posix())
                    row['composed']=probe.capture(report,f'world-{second:03}',hires=report['visual_profile'].get('hires_stills',False))
                emit(dict(elapsed=second,frame=row['registers'].get('frame'),
                    target_samples=len(proof['target_draws']),capture=row.get('composed',{}).get('path')))
            proof['observations'].append(row)
            with (directory/'visual-observations.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
            if recorder is not None and recorder.poll() is not None:break
        if report['visual_profile'].get('retain_host_audio'):
            # Copy historical callback PCM only AFTER the final measured sample.
            # Explicit absolute sample indices avoid the native start=-1/oldest
            # convention. The last60 seconds fit in the87-second host ring.
            import wave
            rows=proof['observations'];last=rows[-1]
            first=next(r for r in rows if r['elapsed_seconds']>=max(0,last['elapsed_seconds']-60))
            host=lambda row:next(t for t in row['audio']['taps'] if t['name']=='host')
            a,b=host(first),host(last);assert a['rate']==b['rate'] and b['frames']>a['frames']
            audio_path=directory/'actual-host-output.wav'
            response=probe.request(report,'audio_wav',tap=2,path=audio_path.as_posix(),start=str(a['frames']),count=str(b['frames']-a['frames']))
            assert response.get('ok') is True and response['frames']==b['frames']-a['frames']
            with wave.open(str(audio_path),'rb') as wav:
                assert wav.getframerate()==b['rate'] and wav.getnchannels()==2 and wav.getsampwidth()==2 and wav.getnframes()==response['frames']
            proof['host_audio']=dict(**pacing.base.ref(audio_path),tap=2,rate=b['rate'],channels=2,sample_width_bytes=2,
                start_sample_frame=a['frames'],frames=response['frames'],seconds=response['frames']/b['rate'],
                observation_elapsed_bracket=[first['elapsed_seconds'],last['elapsed_seconds']],response=response,
                scope='Exact device-rate PCM from this owned game callback; no system loopback, resampling, retiming or added audio; copied after measurement',audible_acceptance=False)
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
        if process is not None and worker_stopped:
            try:
                proof['input_release']=probe.request(report,'clear_input')
                proof['turbo_end']=probe.request(report,'turbo_state')
                if recording:proof['research_stop']=probe.request(report,'research_capture',op='stop')
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
    p.add_argument('--emissive',type=int,choices=[0,1],default=0)
    p.add_argument('--cpu-profile',type=int,choices=[0,1],default=0,help='Cumulative HD CPU attribution; includes CPU timing overhead and is not baseline pacing acceptance')
    p.add_argument('--runtime-perf',type=int,choices=[0,1],default=0,help='One-second opt-in guest/pacer/overlay/provider attribution in stdout; not baseline acceptance')
    p.add_argument('--filter-state-cache',type=int,choices=[0,1],default=0,help='Opt-in owned HD texture nearest/linear state cache; private experiment')
    p.add_argument('--keep-bracket',type=int,choices=[0,1],default=0,help='Opt-in immediate native-flush/HD framebuffer bracket retention; private experiment')
    p.add_argument('--supersampling',type=int,choices=[1,2,3,4,6,8,9,12,16],default=9,help='Private render preference; normal user setting is2, visual baseline9')
    p.add_argument('--rewind',type=int,choices=[0,1],default=0,help='Enable snapshot capture with user depth50/interval15; never loads a state')
    p.add_argument('--rewind-fmv-interval',type=int,choices=[4,15],default=4,help='Private existing-env cadence control; same binary, snapshots remain enabled')
    p.add_argument('--media-profile',action='store_true',help='Observe actual XA/MDEC/depth24 and CD activity; diagnostic overhead disclosed')
    p.add_argument('--dirty-profile',action='store_true',help='Read interpreter PC counters at bounded transition/Greif checkpoints; diagnostic overhead disclosed')
    p.add_argument('--retain-host-audio',action='store_true',help='After measurement, preserve up to60seconds of actual game callback PCM for audible review')
    p.add_argument('--hires-stills',action='store_true')
    p.add_argument('--telemetry-only',action='store_true',help='Same disclosed timer-assisted route without video, source collection or measurement screenshots')
    p.add_argument('--route-profile',choices=['hd','assembled-v1'],default=None)
    p.add_argument('--native-menus',action='store_true',help='Verified stock menu route, then enable the entire frozen pack for gameplay; no new-menu acceptance')
    p.add_argument('--recorder',choices=['gdigrab','gfxcapture'],default='gdigrab')
    p.add_argument('--capture-seconds',type=int,choices=[120,150,170],default=170)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--run-prepared',action='store_true')
    args=p.parse_args()
    if args.telemetry_only and args.hires_stills:p.error('Telemetry-only disables all measurement screenshots')
    if not __import__('re').fullmatch('[a-zA-Z0-9_-]+',args.batch):p.error('Use one directory name')
    if not args.run_prepared:
        if not args.candidate or not args.runtime:p.error('Preparation needs candidate and runtime')
        prepare(args)
    if not args.prepare_only:run(args)
