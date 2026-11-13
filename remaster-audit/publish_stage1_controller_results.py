"""Publish closed controller qualification attempts without claiming stage clear."""
import json
from publish_stage1_wave2_results import E,OUT,read,write,reference

def main():
    target=OUT/'stage1-controller-results.json';assert not target.exists();trials=[]
    reasons=['Forty-poll hull absence stopped control during a camera/respawn gap.',
        'Camera/clipping absence falsely advanced the inferred checkpoint without native life loss.',
        'Two verified Continues consumed; stopped at the third verified prompt without stage clear.']
    for number,reason in enumerate(reasons,1):
        run=E/f'stage-lane-mk3-v{number}/hd-on_rewind-off';p=read(run/'robin-proof.json')
        assert not p['errors'] and p['owned_process_exit']==0 and p['close']['port_closed']
        assert not any(p[k] for k in ('ram_writes','state_loads','timer_assistance','stage_clear_verified'))
        observations=p['gameplay_observations'];a,b=observations[0],observations[-1]
        attempts=p.get('verified_continues',{}).get('attempts',[])
        assert all(x['finite_confirm']['ok'] and x.get('resumed',{}).get('lives',0)>0 for x in attempts)
        checkpoints=[]
        for x in observations:
            if 'bot' not in x:continue
            policy=(x['bot'].get('position') or {}).get('stage_policy')
            if policy:checkpoints.append(dict(elapsed_seconds=x['elapsed_seconds'],native_lives=x['lives']['hex'],
                running=x['bot']['running'],policy=policy))
        trials.append(dict(run=run.parent.name,proof=reference(run/'robin-proof.json'),
            measurement_seconds=b['elapsed_seconds']-a['elapsed_seconds'],end_lives=b['lives']['hex'],
            verified_continues=[dict(confirmed_seconds=x['elapsed_seconds'],resumed_seconds=x['resumed']['elapsed_seconds'],
                resumed_frame=x['resumed']['frame'],resumed_lives=x['resumed']['lives']) for x in attempts],
            closed_cleanly=True,qualification_passed=False,stage_clear_verified=False,reason=reason,
            policy_observations=checkpoints))
    assert len(trials[-1]['verified_continues'])==2
    write(target,dict(schema_version=1,kind='Actual bounded unassisted stage-policy qualification',
        trials=trials,all_stage_clear_attempts_failed=True,ram_writes=False,state_loads=False,timer_assistance=False,
        production_installed=False,limitations=['Checkpoint A timing remains approximate.',
            'Source-matched hull geometry is not visibility or collision proof; the native lives counter now gates death/checkpoint changes.',
            'The25 passing controller tests verify input/clock/absence guards, not successful gameplay.',
            'The run used source capture and sequential stills; it is not baseline pacing or audible audio acceptance.']))
    print(json.dumps(dict(result=str(target),trials=len(trials),continues=2,stage_clear=False)))

if __name__=='__main__':main()
