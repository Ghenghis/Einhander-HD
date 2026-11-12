"""Observe a cold native title, then enter Configuration before title idle expires."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from launch_ui_candidate import load_report
from ui_candidate_probe import pulse, request, capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True)
    args=parser.parse_args()
    report=load_report(args.evidence)
    deadline=time.monotonic()+15
    while True:
        try:
            request(report,'get_registers')
            break
        except ConnectionRefusedError:
            if time.monotonic()>=deadline: raise
            time.sleep(.05)
    subprocess.run([sys.executable,str(Path(__file__).with_name('observe_native_boot.py')),
                    '--evidence',args.evidence,'--label','cold-font-review'],check=True,timeout=70)
    report=load_report(args.evidence)
    pulse(report,'left',.15)
    time.sleep(.3)
    pulse(report,'confirm',.15)
    time.sleep(1.2)
    result=capture(report,'configuration-entry-review',hires=True)
    root=Path(report['evidence'])
    stats=request(report,'gpu_ring_stats')
    frames=[request(report,'gpu_frame_dump',frame=stats['newest_frame']-k,count=8192) for k in (1,0)]
    display=request(report,'display_ring_stats')
    vram=request(report,'display_ring_aux',frame=display['newest_frame'],path=(root/'configuration-entry-vram.bin').as_posix())
    (root/'configuration-entry-proof.json').write_text(json.dumps(dict(capture=result,gp0_frames=frames,vram=vram,
        ram_writes=False,assisted=False,visual_review='pending actual state and image inspection'),indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
