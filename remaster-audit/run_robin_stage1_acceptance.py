"""Private, bounded Robin bring-up with an audited pad-only command boundary.

Native title/selection gates precede POST /bot. No cheat holds, RAM writes,
state loads, stage jumps or turbo are permitted. Screenshots are observations;
stage-clear acceptance must be established by reviewing them and the run log.
"""
from __future__ import annotations
import argparse
import http.server
import json
from pathlib import Path
import sys
import subprocess
import threading
import time
from types import SimpleNamespace
import urllib.request

import run_stage1_pacing_ab as pacing
import launch_ui_candidate as ui
import ui_candidate_probe as probe
from native_ui_facade_route import enter_city
from run_facade_ab_probe import close
from run_stage1_world_flypast import recorder_command

def source_filter(path):
    if path is None:return []
    keys=json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(keys,list) or not 1<=len(keys)<=256 or
        any(not isinstance(k,str) or not __import__('re').fullmatch('[0-9A-F]{8}-[0-9A-F]{8}',k) for k in keys) or len(set(keys))!=len(keys)):
        raise ValueError('Source filter must contain1..256 unique uppercase CRC pairs')
    return keys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True)
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--hd',choices=['on','off'],default='on')
    parser.add_argument('--craft',choices=['mk2','mk3','astraea'],default='mk2')
    parser.add_argument('--seconds',type=int,choices=[90,180,600,900],default=180)
    parser.add_argument('--sources',action='store_true')
    parser.add_argument('--source-cache-keys',default='',help='Up to32 comma-separated raw-upload CRCs retained from boot; requires --sources')
    parser.add_argument('--source-keys-json',type=Path,help='Bound raw archives to1..256 exact CRC pairs; draw receipts remain sampled and unfiltered')
    parser.add_argument('--weave',type=int,choices=[0,1],default=1)
    parser.add_argument('--movement',choices=['weave','left_lane','upper_lane','greif_lane','stage_lane','draw_lane'],default='left_lane',
        help='draw_lane uses opt-in, read-only MkII hull geometry; live qualification is required')
    parser.add_argument('--revive',type=int,choices=[0,1],default=1)
    parser.add_argument('--hull-guard',action='store_true',help='Require the selected starter source set and use fresh hull draws at zero spare lives')
    parser.add_argument('--fire-mode',choices=['cross','both'],default='both')
    parser.add_argument('--world-sampling',type=int,choices=[0,1],default=0)
    parser.add_argument('--opaque-batch',type=int,choices=[0,1],default=0)
    parser.add_argument('--short-upload-priority',type=int,choices=[0,1],default=0)
    parser.add_argument('--emissive',type=int,choices=[0,1],default=0)
    parser.add_argument('--native-menus',action='store_true')
    parser.add_argument('--terminal-ui-stills',action='store_true',help='Retain one-Hz native frames at zero lives; never confirms Continue')
    parser.add_argument('--composed-stills',action='store_true')
    parser.add_argument('--hires-stills',action='store_true',help='Also retain sequential 2160p GL readbacks; requires --composed-stills and is not recorder-off pacing evidence')
    parser.add_argument('--record-video',action='store_true',help='Record the owned window with validated gfxcapture/NVENC; not recorder-off acceptance')
    parser.add_argument('--submission-log',action='store_true',help='Retain unsampled first-occurrence replacement receipts, bounded to4096 identities')
    parser.add_argument('--player-material',choices=['configured','stock'],default='configured')
    parser.add_argument('--dense-gpu-frames',action='store_true',help='Retain bounded previous-frame GP0 rings alongside sequential stills; not atomic or complete replay')
    parser.add_argument('--continues',type=int,choices=range(0,11),default=0,
        help='Experimental bounded Continue confirmations after three increasing native prompt frames; never presses Start')
    args=parser.parse_args()
    if args.source_keys_json and not args.sources:parser.error('--source-keys-json requires --sources')
    try:source_keys=source_filter(args.source_keys_json)
    except (ValueError,OSError) as error:parser.error(str(error))
    filter_pin=pacing.base.ref(args.source_keys_json.resolve()) if source_keys else None
    if args.hires_stills and not args.composed_stills:parser.error('--hires-stills requires --composed-stills')
    if args.movement in ('upper_lane','greif_lane','stage_lane') and not args.hull_guard:parser.error('Upper/Greif/stage movement requires --hull-guard for selected-craft geometry')
    if args.native_menus and args.hd!='on':parser.error('--native-menus enables replacements only after the stock route, so requires --hd on')
    if args.continues and (args.revive or args.movement not in ('draw_lane','left_lane','upper_lane','greif_lane','stage_lane') or not args.terminal_ui_stills):
        parser.error('--continues requires --revive 0, a lane movement policy and --terminal-ui-stills')
    if args.source_cache_keys and (not args.sources or not __import__('re').fullmatch(r'[0-9A-Fa-f]{8}(,[0-9A-Fa-f]{8}){0,31}',args.source_cache_keys)):
        parser.error('Source cache shortlist requires --sources and1..32 exact eight-digit CRCs')
    if args.craft != 'mk2' and (args.movement=='draw_lane' or (args.hd=='on' and not args.native_menus)):
        parser.error('Alternate craft require native menus and no MkII hull controller; HD-on needs --native-menus')
    if not __import__('re').fullmatch('[a-zA-Z0-9_-]+',args.batch):parser.error('Use a single batch directory name')
    config=SimpleNamespace(batch=args.batch,runtime=args.runtime,candidate=args.candidate,gpu_queries=0,world_sampling=args.world_sampling,opaque_batch=args.opaque_batch,short_upload_priority=args.short_upload_priority,emissive=args.emissive,guest_frames=0)
    tracking=args.sources or args.movement in ('draw_lane','upper_lane','greif_lane','stage_lane') or args.hull_guard
    report=pacing.prepare('hd-'+('on' if tracking else args.hd)+'_rewind-off',config)
    directory=Path(report['evidence'])
    overrides=report['launches']['candidate']['environment_overrides']
    overrides['PSXRECOMP_HD_SOURCE_CACHE_KEYS']=args.source_cache_keys.upper()
    overrides.update(PSXRECOMP_SKIN_ENEMY_PROFILE='stock',PSXRECOMP_SKIN_ENEMY_DETAIL_PATH='')
    if args.player_material=='stock':
        overrides.update(PSXRECOMP_SKIN_PROFILE='stock',PSXRECOMP_SKIN_DETAIL_PATH='')
    if args.submission_log:overrides['PSXRECOMP_HD_PROOF_LOG']=str(directory/'first-submissions.jsonl')
    overrides.update(PSXRECOMP_PLAYER_DRAW_TRACKING='1' if args.movement in ('draw_lane','upper_lane','greif_lane','stage_lane') or args.hull_guard else '0',
        PSXRECOMP_PLAYER_DRAW_CRAFT=args.craft,
        PSXRECOMP_PLAYER_DRAW_ONLY='1' if args.movement=='draw_lane' and args.hd=='off' and not args.sources else '0')
    if args.sources:
        dump=directory/'source-pages';dump.mkdir()
        overrides.update(PSXRECOMP_HD_DUMP=dump.as_posix(),PSXRECOMP_HD_SOURCE_SIDECARS='1')
        report['pacing_profile'].update(source_sidecars=True,recorder=True,
            native_page_dump=True,source_tracker_pack_enabled=True)
    if (tracking and args.hd=='off') or args.native_menus:
        control=directory/'replacement-control.txt';control.write_text('0\n')
        overrides['PSXRECOMP_HD_PROOF_CONTROL']=str(control)
        report['route_reference_profile']='native-stock'
    report['robin_profile']=dict(hd_replacements=args.hd=='on',sources=args.sources,craft=args.craft,
        invincible=False,revive=bool(args.revive),enemy_material='original colors',
        native_menus=args.native_menus,terminal_ui_stills=args.terminal_ui_stills,composed_stills=args.composed_stills,
        video_recording=args.record_video,
        hires_stills=args.hires_stills,
        verified_continue_limit=args.continues,
        first_submission_log=args.submission_log,player_material=args.player_material,dense_gpu_frames=args.dense_gpu_frames,
        hull_draw_tracking=args.movement in ('draw_lane','upper_lane','greif_lane','stage_lane') or args.hull_guard,hull_guard=args.hull_guard,native_observer_only=overrides['PSXRECOMP_PLAYER_DRAW_ONLY']=='1')
    if source_keys:
        assert ui.sha(args.source_keys_json.resolve())==filter_pin['sha256'],'Source filter changed during preparation'
        report['source_capture_filter']=dict(**filter_pin,source_key_count=len(source_keys),scope='Raw archives only; not exhaustive draw coverage')
        ui.copy_verified(args.source_keys_json.resolve(),directory/'executed-source-keys.json')
    pacing.base.write(directory/'candidate.json',report)
    ui.copy_verified(Path(__file__),directory/'executed-robin.py')
    proof=dict(started_at_utc=ui.stamp(),kind='Robin live bring-up',ram_writes=False,state_loads=False,
        timer_assistance=False,stage_clear_verified=False,gameplay_observations=[],errors=[])
    proof['bot_source']=pacing.base.ref(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py')
    ui.copy_verified(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py',directory/'executed-robin-bridge.py')
    policy=pacing.base.ROOT/'windows-x64/tools/robin_stage_policy.py'
    proof['stage_policy_source']=pacing.base.ref(policy)
    ui.copy_verified(policy,directory/'executed-robin-stage-policy.py')
    if args.record_video:report['pacing_profile'].update(recorder=True,video_capture=True)
    pacing.base.write(directory/'candidate.json',report)
    bridge=None;server=None;source_started=False;process=None;segment=0;recorder=None
    lock=threading.Lock()
    try:
        process=pacing.launch(report)
        proof['route']=enter_city(report,poll_seconds=1,craft=args.craft)
        if args.native_menus:
            control=directory/'replacement-control.txt'
            if control.read_text()!='0\n':raise RuntimeError('Native menu replacement control changed')
            control.write_text('1\n')
            proof['replacement_enabled_after_native_menus']=dict(at_utc=ui.stamp(),control=pacing.base.ref(control),new_menu_art_accepted=False)
        proof['turbo_off']=probe.request(report,'turbo',enabled=0)
        proof['turbo_state']=probe.request(report,'turbo_state')
        assert proof['turbo_state']['enabled']==0
        if args.hull_guard:
            proof['hull_guard_initial']=probe.request(report,'player_draw')
            assert proof['hull_guard_initial']['enabled'] and proof['hull_guard_initial'].get('source_set')=={'mk2':2,'mk3':3,'astraea':4}[args.craft], 'Runtime did not enable the selected craft source set'
        sys.path.insert(0,str(pacing.base.ROOT/'windows-x64/tools'))
        assert ui.sha(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py')==proof['bot_source']['sha256'], 'Bot source changed during boot'
        assert ui.sha(policy)==proof['stage_policy_source']['sha256'], 'Stage policy changed during boot'
        import ein_bridge as bridge
        bridge.DEBUG_PORT=report['debug_port']
        original=bridge.cmd
        allowed={'read_ram','press','clear_input','get_registers','player_draw'}
        def audited(command,timeout=8):
            if command.get('cmd') not in allowed:
                raise RuntimeError('Pad-only acceptance boundary rejected '+str(command))
            started=time.monotonic()
            reply=original(command,timeout)
            row=dict(at_utc=ui.stamp(),command=command,reply=reply,request_ms=(time.monotonic()-started)*1000)
            with lock,(directory/'robin-commands.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n')
            return reply
        bridge.cmd=audited
        class BotOnly(bridge.Handler):
            def do_POST(self):
                if self.path!='/bot':return self._json(404,dict(ok=False))
                return super().do_POST()
            def do_GET(self):
                if self.path!='/bot/status':return self._json(404,dict(ok=False))
                return super().do_GET()
            def log_message(self,*unused):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',8096),BotOnly)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        def api(body=None):
            request=urllib.request.Request('http://127.0.0.1:8096/bot' if body else 'http://127.0.0.1:8096/bot/status',
                data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
            return json.load(urllib.request.urlopen(request,timeout=8))
        def start_sources():
            nonlocal segment,source_started
            capture=directory/('native-source-'+str(segment));capture.mkdir()
            filters=dict(source_policy='include',source_keys=source_keys) if source_keys else dict(source_policy='all')
            row=probe.request(report,'research_capture',op='start',path=capture.as_posix(),
                max_sources=256,max_records=20000,max_events=3,max_frames=18000,
                max_seconds=300,max_bytes=134217728,**filters)
            proof.setdefault('research_segments',[]).append(dict(segment=segment,start=row))
            segment+=1;source_started=True
        if args.sources:start_sources()
        if args.record_video:
            output=directory/'robin-original.mp4';command=recorder_command(report,output,'gfxcapture',args.seconds)
            proof['video']=dict(path=str(output),arguments=command,started_at_utc=ui.stamp(),
                scope='Actual owned game window; silent; no retiming/interpolation; capture load affects cadence')
            recorder=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
        bot_options=dict(action='start',name='Robin',autofire=True,weave=bool(args.weave),
            dodge=True,revive=bool(args.revive),invincible=False,hull_guard=args.hull_guard,tick=.15,movement=args.movement,fire_mode=args.fire_mode)
        proof['bot_start']=api(bot_options)
        assert proof['bot_start']['bot']['invincible'] is False
        continue_gate=None;pending_continue=None;resume_frames=[];resume_refs=None
        if args.continues:
            from native_continue_gate import ContinueGate,REFERENCE,REFERENCE_SHA
            continue_gate=ContinueGate()
            proof['verified_continues']=dict(limit=args.continues,reference=dict(path=str(REFERENCE),sha256=REFERENCE_SHA),attempts=[])
            import native_continue_gate
            proof['verified_continues']['helper']=pacing.base.ref(Path(native_continue_gate.__file__))
            ui.copy_verified(Path(native_continue_gate.__file__),directory/'executed-continue-gate.py')
            if args.movement in ('left_lane','upper_lane') and not args.hull_guard:
                from native_ui_facade_route import load_references
                resume_refs,receipts=load_references('native-stock')
                proof['verified_continues']['resume_gameplay_references']=receipts
        start=time.monotonic();next_shot=0
        captures=directory/'observations';captures.mkdir()
        for index in range(args.seconds+1):
            time.sleep(max(0,start+index-time.monotonic()))
            if (directory/'STOP').exists():
                proof['stopped_early_by_local_marker']=dict(at_utc=ui.stamp(),elapsed_seconds=time.monotonic()-start)
                break
            if args.sources and index and index%290==0:
                proof['research_segments'][-1]['stop']=probe.request(report,'research_capture',op='stop')
                source_started=False;start_sources()
            row=dict(elapsed_seconds=time.monotonic()-start,
                registers=probe.request(report,'get_registers'),
                lives=probe.request(report,'read_ram',addr='0x800813C4',len=1),
                player_object=probe.request(report,'read_ram',addr='0x800856E0',len=160),
                audio=probe.request(report,'audio_stats'))
            if args.movement=='draw_lane' or args.hull_guard:row['hull_draw']=probe.request(report,'player_draw')
            if args.terminal_ui_stills and (row['lives'].get('hex')=='00' or pending_continue is not None):
                row['terminal_ui_screenshot']=probe.request(report,'screenshot',path=(captures/f'terminal-{index:04d}.png').as_posix())
            if continue_gate is not None:
                from PIL import Image
                from native_ui_facade_route import native_pixels
                hull_valid=row.get('hull_draw',{}).get('valid') is True
                lives=int(row['lives']['hex'],16)
                if pending_continue is not None:
                    if resume_refs is not None:
                        from native_ui_facade_route import classify_native
                        with Image.open(captures/f'terminal-{index:04d}.png') as image:
                            row['continue_resume_gate']=classify_native(native_pixels(image),resume_refs,'native-stock')
                        frame=row['registers']['frame']
                        if lives>0 and row['continue_resume_gate']['state']=='city' and (not resume_frames or frame>resume_frames[-1]):
                            resume_frames=(resume_frames+[frame])[-3:]
                        else:resume_frames=[]
                    if lives>0 and (hull_valid or len(resume_frames)==3):
                        continue_gate.resumed(lives=lives,hull_valid=hull_valid,gameplay_frames=resume_frames)
                        pending_continue['resumed']=dict(elapsed_seconds=row['elapsed_seconds'],frame=row['registers']['frame'],lives=lives,
                            hull=row.get('hull_draw'),native_gameplay_frames=list(resume_frames),
                            basis='fresh source-matched hull' if hull_valid else 'three distinct native gameplay HUD/scene matches')
                        pending_continue['bot_restart']=api(bot_options)
                        assert pending_continue['bot_restart']['bot']['invincible'] is False
                        pending_continue=None
                    elif row['elapsed_seconds']-pending_continue['elapsed_seconds']>20:
                        pending_continue['resume_not_verified']=True
                        pending_continue['last_capture']=probe.capture(report,f'continue-unverified-{index:04d}',hires=False)
                        proof['continue_route_stopped']='No positive lives and fresh hull within20seconds; no further menu input'
                        break
                elif 'terminal_ui_screenshot' in row:
                    capture=captures/f'terminal-{index:04d}.png'
                    with Image.open(capture) as image:
                        row['continue_gate']=continue_gate.observe(native_pixels(image),row['registers'].get('frame'),hull_valid=hull_valid)
                    if row['continue_gate']['ready']:
                        if len(proof['verified_continues']['attempts'])>=args.continues:
                            proof['continue_route_stopped']='Bounded Continue limit reached at verified prompt'
                            proof['continue_limit_capture']=probe.capture(report,f'continue-limit-{index:04d}',hires=False)
                            break
                        pending_continue=dict(elapsed_seconds=row['elapsed_seconds'],frame=row['registers']['frame'],
                            consecutive_frames=list(continue_gate.streak),last_capture=ui.sha(capture))
                        resume_frames=[]
                        proof['verified_continues']['attempts'].append(pending_continue)
                        pending_continue['bot_stop']=api(dict(action='stop'))
                        continue_gate.mark_issued()
                        pending_continue['clear']=probe.request(report,'clear_input')
                        pending_continue['finite_confirm']=probe.request(report,'press',buttons=0xBFFF,frames=6)
                        assert pending_continue['finite_confirm'].get('ok') is True
                else:
                    continue_gate.streak.clear();continue_gate.ready=False
            if index>=next_shot:
                target=captures/(f'frame-{index:04d}.png')
                row['screenshot']=ui.command(report,json.dumps(dict(cmd='screenshot',path=target.as_posix())))
                if args.composed_stills:row['composed']=probe.capture(report,f'robin-{index:04d}',hires=args.hires_stills)
                if args.dense_gpu_frames:
                    frame=row['registers']['frame']-1
                    data=probe.request(report,'gpu_frame_dump',frame=frame,count=65536)
                    gpu_target=captures/f'gpu-frame-{frame:08d}.json';pacing.base.write(gpu_target,data)
                    row['gpu_frame']=dict(**pacing.base.ref(gpu_target),requested_frame=frame,
                        scope='Bounded prior guest-frame GP0 ring; sequential with stills, not atomic; ring/count limits apply')
                row['bot']=api()['bot'];assert row['bot']['invincible'] is False
                print(json.dumps(dict(elapsed=index,frame=row['registers'].get('frame'),
                    lives=row['lives'],bot_running=row['bot']['running'],screenshot=str(target))),flush=True)
                next_shot+=15
            proof['gameplay_observations'].append(row)
            with (directory/'observations.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row)+'\n')
        proof['bot_stop']=api(dict(action='stop'))
    except Exception as error:proof['errors'].append(str(error))
    finally:
        if bridge is not None:
            try:proof['final_bot_stop']=bridge.bot_stop()
            except Exception as error:proof['errors'].append('Bot stop: '+str(error))
        if server is not None:server.shutdown();server.server_close()
        if source_started:
            try:proof['research_stop']=probe.request(report,'research_capture',op='stop')
            except Exception as error:proof['errors'].append('Capture stop: '+str(error))
        if recorder is not None:
            try:
                _,error=recorder.communicate(input=b'q\n' if recorder.poll() is None else None,timeout=25)
                (directory/'video-stderr.log').write_bytes(error)
                proof['video'].update(exit_code=recorder.returncode,bytes=Path(proof['video']['path']).stat().st_size,
                    sha256=ui.sha(proof['video']['path']))
                if recorder.returncode or not proof['video']['bytes']:raise RuntimeError('Owned video recorder did not produce a valid file')
            except Exception as error:
                if recorder.poll() is None:recorder.kill();recorder.wait(timeout=5)
                proof['errors'].append('Video: '+str(error))
        if process is not None:
            try:proof['close']=close(report)
            except Exception as error:proof['errors'].append('Close: '+str(error))
            try:proof['owned_process_exit']=process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate();proof['owned_process_forced_cleanup']=True
                proof['owned_process_exit']=process.wait(timeout=5)
        elif (directory/'launch-failure-cleanup.json').exists():
            proof['launch_failure_cleanup']=pacing.base.read(directory/'launch-failure-cleanup.json')
        proof['ended_at_utc']=ui.stamp()
        pacing.base.write(directory/'robin-proof.json',proof)
        print(json.dumps(dict(evidence=str(directory),errors=proof['errors'],stage_clear_verified=False)),flush=True)
    if proof['errors'] or not proof.get('close',{}).get('port_closed'):raise SystemExit(1)

if __name__=='__main__':main()
