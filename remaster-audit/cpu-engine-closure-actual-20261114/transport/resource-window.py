"""At most three eligibility checks; at most ONE actual pinned CPU test child.

Only a recorded prelaunch resource refusal with child_pid=None may defer and
check again. A started child, failure, missing receipt or uncertainty stops.
The unchanged fa5 whole-Job wrapper owns the 60s/1GiB CPU14 limits.
"""
import hashlib,json,os,subprocess,time,sys
from datetime import datetime,timezone
from pathlib import Path
import psutil

root=Path('C:/github/Einhander')
s67=root/'remaster-audit/parallel-stages-20261114/s67'
cwd=s67/'proposals/raw37c-diagnostic'
wrapper=s67/'runs/wrapper-fa5e42fa/run_rc2_envelope_r1.py'
driver=cwd/'raw37c_driver_r11.py'
control=cwd/'test_raw37c_driver_r9.py'
pins={wrapper:'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',driver:'8f753ce74ad3ab4728a0b5b485bab5764cf34294ad1de17d394e44001e4dd17d',control:'f2634fd68a486fc31e421f9507d8333cdddc8f588a481ed8b67b176298ffb6b9'}
base=Path(__file__).resolve().parent
out=base/('controls-r9-window-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
out.mkdir(exist_ok=False)
state={'started_utc':datetime.now(timezone.utc).isoformat(),'attempts':[],'actual_child_started':False,'scope':'CPU controls only, no game/GPU; maximum one actual child'}
def save():
    (out/'receipt.json').write_text(json.dumps(state,indent=2)+'\n')
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
save()
try:
    for attempt in range(1,4):
        for path,expected in pins.items():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('Pinned source changed: '+str(path))
        receipt=out/f'eligibility-{attempt}.json'
        command=['C:/Python314/python.exe','-I','-B',str(wrapper),'--out',str(receipt),'--cpu','14','--timeout','60','--max-cpu','60','--min-free-gib','16','--max-job-mib','1024','--no-window','--','C:/Python314/python.exe','-I','-B',str(control),str(driver),str(out/'controls.log')]
        state['actual_child_started']=None  # Unknown until this wrapper receipt is read.
        save()
        with (out/f'wrapper-{attempt}.stdout').open('x') as stdout,(out/f'wrapper-{attempt}.stderr').open('x') as stderr:
            completed=subprocess.run(command,cwd=cwd,env=env,stdout=stdout,stderr=stderr,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        e=json.loads(receipt.read_text())
        state['attempts'].append({'attempt':attempt,'receipt':str(receipt),'receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'process_exit':completed.returncode,'precheck':e.get('precheck'),'declined':e.get('declined',False),'child_pid':e.get('child_pid')})
        state['actual_child_started']=e.get('child_pid') is not None
        save();print(json.dumps(state['attempts'][-1]),flush=True)
        pre=e.get('precheck') or {}
        resource_declined=(e.get('declined') is True and e.get('child_pid') is None
            and e.get('wrapper_exit')==3 and completed.returncode==3
            and (pre.get('system_cpu_pct',0)>=60 or pre.get('free_gib',16)<16))
        if resource_declined:
            if attempt<3:
                time.sleep(15)
                continue
            state['outcome']='DEFERRED_RESOURCE_UNAVAILABLE'
        else:
            state['outcome']='CHILD_FINISHED' if state['actual_child_started'] else 'STOPPED_UNCERTAIN'
            state['test_exit']=e.get('rc')
            state['cleanup_proven']=(e.get('job_empty') is True and e.get('tree_absent') is True and e.get('child_absent') is True)
            state['wrapper_exit']=e.get('wrapper_exit')
        break
except Exception as error:
    state['outcome']='STOPPED_ERROR';state['error']=type(error).__name__+': '+str(error)
finally:
    state['finished_utc']=datetime.now(timezone.utc).isoformat();save();print(json.dumps({'receipt':str(out/'receipt.json'),**state}),flush=True)
sys.exit(0 if state.get('actual_child_started') is True and state.get('test_exit')==0 and state.get('wrapper_exit')==0 and state.get('cleanup_proven') is True else 3 if state.get('outcome')=='DEFERRED_RESOURCE_UNAVAILABLE' else 1)
