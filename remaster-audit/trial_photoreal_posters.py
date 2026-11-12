"""Bounded real-gameplay photo/sign trial; no guest RAM or save writes."""
import argparse
import json
from pathlib import Path
import time

from launch_ui_candidate import load_report,command,stamp
from ui_candidate_probe import request,capture


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',required=True)
    p.add_argument('--label',required=True)
    args=p.parse_args()
    r=load_report(args.evidence)
    root=Path(r['evidence'])
    directory=root/('draws-'+args.label)
    directory.mkdir()
    poster_keys=['31214B41-6F5C3764','31214B41-24AAFBA4','A9D437BF-502B076B']
    manifest=json.loads(Path('remaster-audit/menu-restoration/latin-world-sign-regions-v1/manifest.json').read_bytes())
    keys=poster_keys+[x['key'] for x in manifest['files']]
    start=request(r,'research_capture',op='start',path=directory.as_posix(),max_sources=64,
        max_records=16000,max_events=16,max_frames=5000,max_seconds=50,max_bytes=67108864,
        source_policy='include',source_keys=keys)
    result=dict(at_utc=stamp(),start=start,ram_writes=False,assisted=False,
        input='finite ordinary fire input; no movement/invulnerability',captures=[])
    deadline=time.monotonic()+42
    try:
        request(r,'set_input',buttons='0x7FFF')
        for i in range(14):
            if time.monotonic()>deadline: break
            time.sleep(2)
            target=root/(args.label+f'-native-{i:02d}.png')
            reply=command(r,json.dumps(dict(cmd='screenshot',path=target.as_posix())))
            if reply.get('ok') is not True:
                result.setdefault('transitions',[]).append(reply)
                continue
            result['captures'].append(capture(r,args.label+f'-{i:02d}',hires=False))
    finally:
        request(r,'clear_input')
        result['stop']=request(r,'research_capture',op='stop')
        result['ended_at_utc']=stamp()
        (root/(args.label+'-trial.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(captures=len(result['captures']),path=str(root/(args.label+'-trial.json')))))


if __name__=='__main__':main()
