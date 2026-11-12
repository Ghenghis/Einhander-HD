"""Record a finite isolated input pulse plus recent ordered GP0 command frames.

This trace omits A0 pixels and variable-polyline bodies. It is not a replay.
The game keeps running; frame-ring retention and truncation are checked.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import time

from live_level1_probe import command, ROOT


def raw_command(request):
    with socket.create_connection(('127.0.0.1',4370),timeout=3) as connection:
        connection.settimeout(5)
        connection.sendall((json.dumps(request)+'\n').encode())
        data=bytearray()
        while True:
            chunk=connection.recv(65536)
            if not chunk: break
            data.extend(chunk)
            if len(data)>8*1024*1024: raise ValueError('Per-response8MiB budget reached')
        return json.loads(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--buttons',type=int,default=32767)
    parser.add_argument('--frames',type=int,default=60)
    args=parser.parse_args()
    directory=Path(args.evidence).resolve()
    if not directory.is_relative_to((ROOT/'remaster-audit/dev-center-evidence').resolve()) or not directory.is_dir():
        raise ValueError('Use the owned evidence directory')
    if not 0<=args.buttons<=65535 or not 1<=args.frames<=120 or not args.name.replace('-','').isalnum():
        raise ValueError('Invalid bounded trace request')
    target=directory/('gp0-'+args.name)
    target.mkdir(exist_ok=False)
    before=command('get_registers').get('frame')
    try:
        command('set_input',buttons=f'0x{args.buttons:04X}')
        time.sleep(2)
    finally:
        command('clear_input')
    after=command('get_registers').get('frame')
    ring=raw_command(dict(cmd='gpu_ring_stats'))
    end=min(after-1,ring['newest_frame']-1)
    start=max(before,end-args.frames+1,ring['oldest_frame']+1)
    records=[]; size=0
    for frame in range(start,end+1):
        if frame%10==0:
            current=raw_command(dict(cmd='gpu_ring_stats'))
            if frame<=current['oldest_frame']: break
        data=raw_command(dict(cmd='gpu_frame_dump',frame=frame,count=65536))
        encoded=(json.dumps(data,separators=(',',':'))+'\n').encode()
        if size+len(encoded)>32*1024*1024: break
        path=target/f'frame-{frame}.json'; path.write_bytes(encoded); size+=len(encoded)
        records.append(dict(frame=frame,count=data.get('count'),bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest(),
                            potentially_truncated=data.get('count',65536)>=65536,ok=data.get('ok'),file=path.name))
    report=dict(at_utc=datetime.now(timezone.utc).isoformat(),buttons=args.buttons,input_seconds=2,
                before_frame=before,after_frame=after,requested_recent_frames=args.frames,ring=ring,frames=records,total_bytes=size,
                complete_requested_window=len(records)==args.frames and not any(r['potentially_truncated'] for r in records),
                limitation='Ordered GP0 commands only; A0 pixel payloads and variable polyline bodies are absent. Actor identity and synchronization with source captures require review.')
    (target/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(target),frames=len(records),before=before,after=after,bytes=size,
                          complete_requested_window=report['complete_requested_window']),indent=2))


if __name__=='__main__':main()
