"""Bounded local test controls and composed-frame receipts for the owned run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8094'
ROOT = Path(__file__).resolve().parent.parent


def api(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE+path, data=data, headers={'Content-Type':'application/json'} if data else {})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return json.load(error)


def command(cmd, **fields):
    reply = api('/cmd', dict(line=json.dumps(dict(cmd=cmd, **fields))))
    return reply.get('data', reply)


def shot(evidence, name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise ValueError('Use a short ASCII capture label')
    directory = evidence / 'captures'
    directory.mkdir(exist_ok=True)
    target = directory / (name+'.png')
    if target.exists():
        raise ValueError('Capture labels must be unique; existing evidence is preserved')
    if len(list(directory.glob('*.png'))) >= 64 or sum(p.stat().st_size for p in directory.glob('*.png')) >= 128*1024*1024:
        raise ValueError('Composed-frame capture budget reached')
    before = command('present_shot_seq')
    frame_before = command('get_registers').get('frame')
    queued = command('present_shot', path=target.as_posix())
    if not queued.get('ok'):
        return dict(ok=False, queued=queued)
    deadline = time.monotonic()+8
    while time.monotonic()<deadline:
        completed = command('present_shot_seq')
        if completed.get('seq',0)>before.get('seq',0):
            if not completed.get('wrote') or not target.is_file():
                return dict(ok=False, error='Composed screenshot failed', completion=completed)
            data = target.read_bytes()
            dimensions = struct.unpack('>II', data[16:24]) if data[:8]==b'\x89PNG\r\n\x1a\n' else None
            receipt = dict(ok=bool(dimensions), path=str(target), width=dimensions[0] if dimensions else None,
                           height=dimensions[1] if dimensions else None, sha256=hashlib.sha256(data).hexdigest(),
                           at_utc=datetime.now(timezone.utc).isoformat(), frame_before=frame_before,
                           frame_after=command('get_registers').get('frame'), completion=completed,
                           scope='Composed next-present screenshot; sequential with other channels, not an atomic all-channel capture')
            target.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
            return receipt
        time.sleep(.1)
    return dict(ok=False,error='Screenshot completion timeout',queued=queued)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('action',choices=['status','shot','cmd','api','pulse'])
    parser.add_argument('value',nargs='?')
    parser.add_argument('body',nargs='?')
    args=parser.parse_args()
    evidence=Path(args.evidence).resolve()
    if not evidence.is_relative_to((ROOT/'remaster-audit/dev-center-evidence').resolve()) or not evidence.is_dir():
        raise ValueError('Use the owned existing evidence directory')
    if args.action=='status':
        full=dict(at_utc=datetime.now(timezone.utc).isoformat(), dev=api('/dev/status'), research=api('/dev/research'),
                  gpu=command('gpu_state'), material=command('skin_material'))
        path=evidence/('status-'+datetime.now(timezone.utc).strftime('%H%M%S%f')+'.json')
        path.write_text(json.dumps(full,indent=2)+'\n',encoding='utf-8')
        research=full['research'].get('status',{})
        result=dict(path=str(path),connected=full['dev'].get('connected'), research=research,
                    gpu=full['gpu'], material=full['material'])
    elif args.action=='shot': result=shot(evidence,args.value)
    elif args.action=='pulse':
        body=json.loads(args.value)
        buttons=int(body['buttons']); seconds=float(body.get('seconds',.5))
        if not 0<=buttons<=65535 or not .05<=seconds<=2:
            raise ValueError('Input pulses must be 0.05–2 seconds with a u16 pad word')
        try:
            result=command('set_input',buttons=f'0x{buttons:04X}')
            time.sleep(seconds)
        finally:
            released=command('clear_input')
        result=dict(pressed=result,released=released,seconds=seconds,buttons=buttons)
    elif args.action=='cmd':
        body=json.loads(args.value); result=command(body.pop('cmd'),**body)
    else: result=api(args.value,json.loads(args.body) if args.body else None)
    receipt=dict(at_utc=datetime.now(timezone.utc).isoformat(), action=args.action, value=args.value,
                 request=json.loads(args.body) if args.body else None, result=result)
    receipts=evidence/'probes'
    receipts.mkdir(exist_ok=True)
    (receipts/(datetime.now(timezone.utc).strftime('%H%M%S%f')+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    if args.action=='api' and args.value=='/dev/research':
        event=result.get('event',{})
        state=result.get('status',{})
        native=state.get('native_capture') or {}
        last=native.get('last') or {}
        native_summary=dict(supported=native.get('supported'),active=native.get('active'),path=last.get('path'),
                            counts=last.get('counts'),caps=last.get('caps'),reason=last.get('reason'),error=last.get('error'))
        evidence_summary={k:event.get('native_evidence',{}).get(k) for k in ('file','sha256','frame','available','error')}
        result=dict(ok=result.get('ok'),error=result.get('error'),pair_id=result.get('pair_id'),event_id=event.get('id'),
                    label=event.get('label'),frame=event.get('frame'),changes=event.get('changes',{}).get('changed_bytes'),
                    whole_ram_candidates=event.get('whole_ram_candidates'), native_evidence=evidence_summary,
                    status=dict({k:state.get(k) for k in ('running','armed','id','scenario','elapsed_seconds','counters')},native_capture=native_summary))
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
