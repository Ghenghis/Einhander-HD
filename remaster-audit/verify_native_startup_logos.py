"""Observe both native startup logos before permitting an intro skip."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from launch_ui_candidate import load_report,stamp,command
from ui_candidate_probe import request,capture,pulse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--configuration',action='store_true')
    args=parser.parse_args()
    report=load_report(args.evidence)
    root=Path(report['evidence'])
    output=root/'startup-logo-gate.json'
    if output.exists(): raise ValueError('This startup attempt already has evidence')
    result=dict(started_at_utc=stamp(),observed={},samples=[],ram_writes=False,assisted=False,
                movie_skip_permitted=False,quality_acceptance=False)
    deadline=time.monotonic()+70
    while True:
        try:
            request(report,'get_registers')
            break
        except ConnectionRefusedError:
            if time.monotonic()>=deadline: raise
            time.sleep(.05)
    directory=root/'draws-cold-startup'
    directory.mkdir()
    # The debug socket becomes available before the GL source tracker. Retry
    # only this explicit initialization state; never skip the native logo gate.
    while True:
        try:
            start=request(report,'research_capture',op='start',path=directory.as_posix(),max_sources=16,
                max_records=12000,max_events=8,max_frames=5000,max_seconds=60,max_bytes=33554432,
                source_policy='include',source_keys=['1AEAD6A5-B20FDBC4','7F7452F9-B20FDBC4','4E783C96-E2D2473F'])
            break
        except RuntimeError as exc:
            if 'OpenGL HD source tracker is not ready' not in str(exc) or time.monotonic()>=deadline:
                raise
            time.sleep(.04)
    result['recorder_start']=start
    gate=root/'startup-native-gate.png'
    try:
        while time.monotonic()<deadline:
            frame=request(report,'get_registers')['frame']
            reply=command(report,json.dumps(dict(cmd='screenshot',path=gate.as_posix())))
            if reply.get('ok') is not True:
                if reply.get('error')=='display disabled':
                    result['samples'].append(dict(frame=frame,display_disabled=True))
                    time.sleep(.08)
                    continue
                raise RuntimeError('Native startup capture failed: '+str(reply))
            if reply.get('width')!=320 or reply.get('height') not in (240,480):
                time.sleep(.08)
                continue
            with Image.open(gate) as im:
                a=np.array(im.convert('RGB').resize((320,240))).astype(np.int16)
            center=a[95:140]
            red=int(((center[:,:,0]>60)&(center[:,:,0]>center[:,:,1]*1.5)&(center[:,:,0]>center[:,:,2]*1.5)).sum())
            white=int(((center.min(2)>75)&((center.max(2)-center.min(2))<25)).sum())
            black=float((a.max(2)<25).mean())
            result['samples'].append(dict(frame=frame,red=red,white=white,black_fraction=black))
            if 20<frame<440 and white>150 and red<4 and black>.7 and 'sony' not in result['observed']:
                time.sleep(.45)
                result['observed']['sony']=dict(first_native_frame=frame,capture=capture(report,'startup-sony-vector',hires=True))
                request(report,'research_capture',op='mark',label='sony-visible')
            if red>8 and white>100 and black>.7 and 'squaresoft' not in result['observed']:
                time.sleep(.35)
                result['observed']['squaresoft']=dict(first_native_frame=frame,capture=capture(report,'startup-squaresoft-vector',hires=True))
                request(report,'research_capture',op='mark',label='squaresoft-visible')
            if len(result['observed'])==2:
                first=result['observed']['squaresoft']['first_native_frame']
                if frame>first+60 and red<4:
                    fmv=request(report,'fmv_state')
                    if fmv.get('mdec_decode_count',0)>3:
                        result['movie_skip_permitted']=True
                        result['movie_skip']=dict(frame=frame,fmv=fmv,input=pulse(report,'start',.15))
                        break
            time.sleep(.09)
    finally:
        result['recorder_stop']=request(report,'research_capture',op='stop')
        request(report,'clear_input')
        result['ended_at_utc']=stamp()
        result['both_logos_observed']=len(result['observed'])==2
        output.write_text(json.dumps(result,indent=2)+'\n')
    if not result['both_logos_observed']: raise RuntimeError('Both startup logos were not observed; no skip permitted')
    if args.configuration:
        from ui_native_journey import Journey
        Journey(report).title(seconds=15)
        pulse(report,'left',.15)
        time.sleep(.3)
        pulse(report,'confirm',.15)
        time.sleep(2)
        result['configuration_entry']=capture(report,'configuration-after-full-boot',hires=True)
        output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(path=str(output),both_logos_observed=result['both_logos_observed'],movie_skip_permitted=result['movie_skip_permitted'])))


if __name__=='__main__': main()
