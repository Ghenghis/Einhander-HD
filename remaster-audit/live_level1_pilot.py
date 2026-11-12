"""Finite, explicitly assisted collection pilot. No menu or scene warps.

Wait for plausible live player state, acquire a bounded invincibility hold,
then inject only finite stock-gun/movement pulses. A pilot.pause file releases
the pilot's input so individual event tests can own it. Every action is logged.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from live_level1_probe import api, command, ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--duration',type=int,default=300,choices=range(30,601))
    args=parser.parse_args()
    directory=Path(args.evidence).resolve()
    if not directory.is_relative_to((ROOT/'remaster-audit/dev-center-evidence').resolve()):
        raise ValueError('Pilot evidence must stay in the owned workspace')
    started=time.monotonic()
    log=directory/'assisted-pilot.jsonl'
    if log.exists(): raise ValueError('An existing pilot log is preserved')
    def note(kind,**details):
        with log.open('a',encoding='utf-8') as output:
            output.write(json.dumps(dict(at_utc=datetime.now(timezone.utc).isoformat(),kind=kind,**details))+'\n')
    lease=min(300,args.duration)
    note('waiting',wait_seconds=120,run_seconds=args.duration,hold_fields=['invincibility','lives'],hold_seconds=lease,
         input='Square stock gun; short balanced vertical sweeps; no ammo or stage writes',
         limitation='Assisted visual/data collection, not damage/survival/weapon-balance proof')
    hold=False
    acquired=[]
    try:
        while time.monotonic()-started<120:
            if (directory/'pilot.stop').exists(): return
            state=api('/dev/status')
            lives=state.get('values',{}).get('lives',{}).get('value',0)
            if state.get('connected') and isinstance(lives,int) and 1<=lives<=99:
                reply=api('/dev/lock',dict(field='invincibility',value=165,enabled=True,ttl_seconds=lease))
                note('hold_request',response=reply)
                if reply.get('ok'):
                    hold=True
                    acquired.append('invincibility')
                    life_reply=api('/dev/lock',dict(field='lives',value=3,enabled=True,ttl_seconds=lease))
                    note('lives_hold_request',response=life_reply)
                    if life_reply.get('ok'): acquired.append('lives')
                    break
            time.sleep(1)
        if not hold:
            note('stopped',reason='No plausible player state/hold before startup deadline')
            return
        run_started=time.monotonic()
        renewed=run_started
        was_paused=False
        while time.monotonic()-run_started<args.duration:
            if (directory/'pilot.stop').exists(): break
            if time.monotonic()-renewed>240 and args.duration-(time.monotonic()-run_started)>30:
                remaining=min(300,max(5,int(args.duration-(time.monotonic()-run_started))))
                for field,value in [('invincibility',165),('lives',3)]:
                    note('renew_hold',field=field,response=api('/dev/lock',dict(field=field,value=value,enabled=True,ttl_seconds=remaining)))
                renewed=time.monotonic()
            if (directory/'pilot.pause').exists():
                if not was_paused:
                    note('paused',release=command('clear_input'))
                was_paused=True
                time.sleep(.2)
                continue
            was_paused=False
            phase=int((time.monotonic()-run_started)*2)%12
            direction=0x10 if phase in (0,1) else 0x40 if phase in (6,7) else 0
            buttons=0x7FFF & ~direction
            response=command('press',buttons=buttons,frames=60)
            note('input',buttons=buttons,frames=60,response=response)
            if not response.get('ok'):
                note('stopped',reason='Input connection failed')
                break
            time.sleep(.5)
    finally:
        note('released',input=command('clear_input'),
             holds=[api('/dev/lock',dict(field=field,enabled=False)) for field in acquired])


if __name__=='__main__':main()
