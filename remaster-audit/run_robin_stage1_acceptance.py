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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True)
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--hd',choices=['on','off'],default='on')
    parser.add_argument('--seconds',type=int,choices=[180,600,900],default=180)
    parser.add_argument('--sources',action='store_true')
    parser.add_argument('--weave',type=int,choices=[0,1],default=1)
    parser.add_argument('--movement',choices=['weave','left_lane','position_lane'],default='position_lane')
    parser.add_argument('--fire-mode',choices=['cross','both'],default='both')
    parser.add_argument('--world-sampling',type=int,choices=[0,1],default=0)
    args=parser.parse_args()
    if not __import__('re').fullmatch('[a-zA-Z0-9_-]+',args.batch):parser.error('Use a single batch directory name')
    config=SimpleNamespace(batch=args.batch,runtime=args.runtime,candidate=args.candidate,gpu_queries=0,world_sampling=args.world_sampling,guest_frames=0)
    report=pacing.prepare('hd-'+('on' if args.sources else args.hd)+'_rewind-off',config)
    directory=Path(report['evidence'])
    overrides=report['launches']['candidate']['environment_overrides']
    overrides.update(PSXRECOMP_SKIN_ENEMY_PROFILE='stock',PSXRECOMP_SKIN_ENEMY_DETAIL_PATH='')
    if args.sources:
        dump=directory/'source-pages';dump.mkdir()
        overrides.update(PSXRECOMP_HD_DUMP=dump.as_posix(),PSXRECOMP_HD_SOURCE_SIDECARS='1')
        report['pacing_profile'].update(source_sidecars=True,recorder=True,
            native_page_dump=True,source_tracker_pack_enabled=True)
        if args.hd=='off':
            control=directory/'replacement-control.txt';control.write_text('0\n')
            overrides['PSXRECOMP_HD_PROOF_CONTROL']=str(control)
            report['route_reference_profile']='native-stock'
    report['robin_profile']=dict(hd_replacements=args.hd=='on',sources=args.sources,
        invincible=False,revive='ordinary Continue inputs only',enemy_material='original colors')
    pacing.base.write(directory/'candidate.json',report)
    ui.copy_verified(Path(__file__),directory/'executed-robin.py')
    proof=dict(started_at_utc=ui.stamp(),kind='Robin live bring-up',ram_writes=False,state_loads=False,
        timer_assistance=False,stage_clear_verified=False,gameplay_observations=[],errors=[])
    proof['bot_source']=pacing.base.ref(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py')
    ui.copy_verified(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py',directory/'executed-robin-bridge.py')
    bridge=None;server=None;source_started=False;process=None;segment=0
    lock=threading.Lock()
    try:
        process=pacing.launch(report)
        proof['route']=enter_city(report,poll_seconds=1)
        proof['turbo_off']=probe.request(report,'turbo',enabled=0)
        proof['turbo_state']=probe.request(report,'turbo_state')
        assert proof['turbo_state']['enabled']==0
        sys.path.insert(0,str(pacing.base.ROOT/'windows-x64/tools'))
        assert ui.sha(pacing.base.ROOT/'windows-x64/tools/ein_bridge.py')==proof['bot_source']['sha256'], 'Bot source changed during boot'
        import ein_bridge as bridge
        bridge.DEBUG_PORT=report['debug_port']
        original=bridge.cmd
        allowed={'read_ram','press','clear_input','get_registers'}
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
            row=probe.request(report,'research_capture',op='start',path=capture.as_posix(),
                max_sources=256,max_records=20000,max_events=3,max_frames=18000,
                max_seconds=300,max_bytes=134217728,source_policy='all')
            proof.setdefault('research_segments',[]).append(dict(segment=segment,start=row))
            segment+=1;source_started=True
        if args.sources:start_sources()
        proof['bot_start']=api(dict(action='start',name='Robin',autofire=True,weave=bool(args.weave),
            dodge=True,revive=True,invincible=False,tick=.15,movement=args.movement,fire_mode=args.fire_mode))
        assert proof['bot_start']['bot']['invincible'] is False
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
            if index>=next_shot:
                target=captures/(f'frame-{index:04d}.png')
                row['screenshot']=ui.command(report,json.dumps(dict(cmd='screenshot',path=target.as_posix())))
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
