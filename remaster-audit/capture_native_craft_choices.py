"""Capture native fighter-menu choices using finite ordinary inputs only.

Stops before confirming any alternate craft. These are reference-acquisition
images, not proof of alternate craft gameplay or a qualified menu classifier.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

import build_facade_ab_candidates as base
import launch_ui_candidate as ui
import run_stage1_pacing_ab as pacing
import ui_candidate_probe as probe
from native_ui_facade_route import enter_city
from run_facade_ab_probe import close


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    args=parser.parse_args()
    if not pacing.re.fullmatch(r'[a-zA-Z0-9_-]+',args.batch):parser.error('Use one batch directory name')
    options=SimpleNamespace(**vars(args),gpu_queries=0,world_sampling=0,cpu_profile=0,opaque_batch=0,guest_frames=0)
    report=pacing.prepare('hd-off_rewind-off',options);directory=Path(report['evidence'])
    ui.copy_verified(Path(__file__),directory/'executed-craft-choices.py')
    proof=dict(started_at_utc=ui.stamp(),purpose='Native fighter-menu reference acquisition',
        ram_writes=False,state_loads=False,alternate_craft_confirmed=False,observations=[],errors=[])
    process=None
    try:
        process=pacing.launch(report)
        proof['native_route']=enter_city(report,stop_at='fighter',poll_seconds=1)
        for step in range(3):
            if step:
                entry=dict(step=step,button='down',duration_seconds=.12)
                try:entry['press']=probe.request(report,'set_input',buttons='0xFFBF');time.sleep(.12)
                finally:entry['release']=probe.request(report,'clear_input')
                proof.setdefault('inputs',[]).append(entry)
                time.sleep(.8)
            for observation in range(3):
                path=directory/f'choice-{step}-native-{observation}.png'
                before=probe.request(report,'get_registers')['frame']
                reply=probe.request(report,'screenshot',path=path.as_posix())
                if not reply.get('ok'):raise RuntimeError('Native screenshot failed: '+str(reply))
                proof['observations'].append(dict(step=step,observation=observation,
                    image=base.ref(path),frame_before=before,
                    frame_after=probe.request(report,'get_registers')['frame']))
                time.sleep(.25)
    except Exception as error:proof['errors'].append(str(error))
    finally:
        if (directory/'launch-candidate.json').exists() and not (directory/'launch-failure-cleanup.json').exists():
            try:
                proof['input_release']=probe.request(report,'clear_input')
                proof['close']=close(report)
            except Exception as error:proof['errors'].append('Close: '+str(error))
        if process is not None:
            try:proof['owned_process_exit']=process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate();proof['forced_cleanup']=True;proof['owned_process_exit']=process.wait(timeout=5)
        commands=[json.loads(p.read_bytes()) for p in (directory/'commands').glob('*.json')]
        assert not any(p['request']['cmd'] in ('write_ram','load_state','save_state') for p in commands)
        proof['ended_at_utc']=ui.stamp();base.write(directory/'craft-choice-proof.json',proof)
        print(json.dumps(dict(directory=str(directory),observations=len(proof['observations']),errors=proof['errors'])),flush=True)
    if proof['errors'] or not proof.get('close',{}).get('port_closed'):raise SystemExit(1)


if __name__=='__main__':main()
