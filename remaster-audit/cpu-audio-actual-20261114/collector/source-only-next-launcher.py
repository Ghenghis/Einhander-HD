"""One future explicitly granted pure-control run; no retries or GPU/game work.

Preparation only until invoked with a fresh coordinator grant and start deadline.
r1: preserve executed watchdog/launcher bytes and share one three-second cleanup deadline.
r2: finite receipt decoding, pre-serialized failure receipt and exact control provenance.
r3: release an exited wrapper's retained handle before the bounded identity-absence observation.
"""
from pathlib import Path
import argparse
import datetime as dt
import gc
import hashlib
import json
import math
import os
import psutil
import subprocess
import sys
import time

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
S=R/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
GUARD=S/'watchdog/run_rc2_envelope_r1.py'
CONTROLS=S/'adapter-controls/controls_c457b58e_r1.py'
PINS={GUARD:'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36',
      CONTROLS:'f8b517c11cb32f0d3b2cfcee3ba51ebbf6cb2f5c13498cc2d9caff8bc223a907',
      R/'remaster-audit/owned_gl_adapter_observation.py':'c457b58ed670f878dd30fb4962639dbfc18f407e4223685710f498d29a0ded34',
      R/'remaster-audit/gl_adapter_identity_guard.py':'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08'}
def utc():return dt.datetime.now(dt.timezone.utc)
def require(ok,why):
    if not ok:raise RuntimeError(why)
def write(path,data):
    complete=True
    try:payload=json.dumps(data,indent=2,ensure_ascii=True,allow_nan=False)+'\n'
    except (ValueError,TypeError) as error:
        complete=False;data['passed']=False
        payload=json.dumps(dict(passed=False,receipt_serialization_failed=True,
            error=type(error).__name__+': '+str(error),gpu_run=False,game_run=False,
            live_qualified=False),indent=2,ensure_ascii=True,allow_nan=False)+'\n'
    with path.open('x',encoding='utf-8') as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    return complete
def strict_receipt(raw):
    def constant(value):raise ValueError('Non-finite receipt constant '+value)
    def finite_float(value):
        parsed=float(value);require(math.isfinite(parsed),'Non-finite receipt float');return parsed
    return json.loads(raw,parse_constant=constant,parse_float=finite_float)
def main():
    initial_launcher_bytes=Path(__file__).read_bytes()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grant-id',required=True)
    parser.add_argument('--start-before-utc',required=True)
    args=parser.parse_args()
    deadline=dt.datetime.fromisoformat(args.start_before_utc.replace('Z','+00:00'))
    require(deadline.tzinfo is not None and utc()<deadline,'Fresh grant start deadline required')
    me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
    out=N/'collector-controls-run-r2';out.mkdir(exist_ok=False)
    receipt=dict(at_utc=utc().isoformat(),grant_id=args.grant_id,start_before_utc=deadline.isoformat(),
                 attempt=1,retries=0,passed=False,gpu_run=False,game_run=False,real_socket_used=False,
                 live_qualified=False,command=[],source_pins=[],wrapper_started=False,
                 launcher_source_sha256=hashlib.sha256(initial_launcher_bytes).hexdigest())
    process=None;exit_code=1;started=time.monotonic();cleanup_deadline=None
    def copy_exact(path,raw,want):
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        require(hashlib.sha256(path.read_bytes()).hexdigest()==want,'Executed source copy changed '+str(path))
    def stop_owned_wrapper():
        nonlocal cleanup_deadline
        if cleanup_deadline is None:cleanup_deadline=time.monotonic()+3
        if process is not None and process.poll() is None:
            process.kill()
            left=cleanup_deadline-time.monotonic()
            if left>0:
                try:process.wait(timeout=left)
                except subprocess.TimeoutExpired:pass
            if process.poll() is None:receipt['wrapper_cleanup_unproven']=True
    try:
        copy_exact(out/'executed-launcher.py',initial_launcher_bytes,receipt['launcher_source_sha256'])
        controls_bytes=None;watchdog_bytes=None
        for path,want in PINS.items():
            raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest()
            require(got==want,'Changed pinned input '+str(path))
            receipt['source_pins'].append(dict(path=str(path),sha256=got,bytes=len(raw)))
            if path==CONTROLS:controls_bytes=raw
            if path==GUARD:watchdog_bytes=raw
        copy=out/'executed-controls.py'
        watchdog_copy=out/'executed-watchdog.py'
        copy_exact(copy,controls_bytes,PINS[CONTROLS])
        copy_exact(watchdog_copy,watchdog_bytes,PINS[GUARD])
        require(utc()<deadline,'Grant expired during source checks')
        command=[sys.executable,'-I','-B',str(watchdog_copy),'--out',str(out/'envelope.json'),'--cpu','11',
                 '--timeout','10','--max-job-mib','128','--no-window','--max-cpu','60','--min-free-gib','16',
                 '--',sys.executable,'-I','-B',str(copy),'--out',str(out/'controls'),'--cpu','11']
        receipt['command']=command
        with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
            process=subprocess.Popen(command,cwd=R,stdout=stdout,stderr=stderr,creationflags=0x08004000)
            receipt.update(wrapper_started=True,wrapper_pid=process.pid,wrapper_creation_unix=None)
            try:receipt['wrapper_creation_unix']=psutil.Process(process.pid).create_time()
            except psutil.NoSuchProcess:receipt['wrapper_creation_note']='Process exited before creation lookup'
            try:receipt['wrapper_exit']=process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                receipt['outer_timeout']=True;stop_owned_wrapper();receipt['wrapper_exit']=process.poll()
        receipt['wrapper_retained_handle_exited']=process.poll() is not None
        wrapper_pid=process.pid
        # Retain the exit result first, then release our handle. Windows can
        # retain the exited process identity while this Popen handle is open.
        # This is not a confirmed sole cause of the earlier false absence result.
        if receipt['wrapper_retained_handle_exited']:
            process=None
            gc.collect()
            receipt['wrapper_own_handle_released_before_lookup']=True
        identity=receipt['wrapper_creation_unix']
        if cleanup_deadline is None:cleanup_deadline=time.monotonic()+3
        def known_wrapper_absent():
            try:return (not psutil.pid_exists(wrapper_pid) or
                identity is not None and psutil.Process(wrapper_pid).create_time()!=identity)
            except psutil.NoSuchProcess:return True
        receipt['wrapper_identity_absent']=known_wrapper_absent()
        while not receipt['wrapper_identity_absent'] and time.monotonic()<cleanup_deadline:
            time.sleep(min(.025,max(0,cleanup_deadline-time.monotonic())))
            receipt['wrapper_identity_absent']=known_wrapper_absent()
        for name,path in [('envelope',out/'envelope.json'),('controls',out/'controls/result.json')]:
            if path.exists():
                raw=path.read_bytes();receipt[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),data=strict_receipt(raw))
        receipt['logs']={name:dict(sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(),
                                  bytes=(out/name).stat().st_size) for name in ('stdout.log','stderr.log')}
        envelope=receipt.get('envelope',{}).get('data',{});controls=receipt.get('controls',{}).get('data',{})
        expected_control_pins={str(path):pin for path,pin in PINS.items() if path not in (GUARD,CONTROLS)}
        receipt['passed']=(receipt['wrapper_exit']==0 and receipt.get('wrapper_identity_absent') is True
            and envelope.get('tree_absent') is True and envelope.get('child_exit_code')==0
            and envelope.get('job_limits_readback',{}).get('job_memory_limit')==128*2**20
            and envelope.get('child_readback_before_resume',{}).get('cpu_affinity')==[11]
            and envelope.get('child_readback_before_resume',{}).get('priority')==16384
            and controls.get('all_ok') is True and controls.get('case_count')==74
            and controls.get('schema')=='support-adapter-controls-c457b58e-r1'
            and controls.get('controls_sha256')==PINS[CONTROLS]
            and controls.get('pins')==expected_control_pins
            and type(controls.get('cpu')) is int and controls['cpu']==11 and controls.get('allowed_affinity')==[11]
            and controls.get('expected_cases')==74 and len(controls.get('cases',[]))==74
            and all(case.get('ok') is True for case in controls['cases']) and 'fatal' not in controls)
        exit_code=0 if receipt['passed'] else (3 if envelope.get('declined') is True else 1)
    except Exception as error:
        receipt['error']=type(error).__name__+': '+str(error)
        if process is not None and process.poll() is None:
            try:stop_owned_wrapper()
            except Exception as cleanup_error:
                receipt['wrapper_cleanup_unproven']=True
                receipt['cleanup_error']=type(cleanup_error).__name__+': '+str(cleanup_error)
    finally:
        receipt['ended_utc']=utc().isoformat();receipt['outer_elapsed_s']=time.monotonic()-started
        if not write(out/'launcher.json',receipt):exit_code=1
    print(json.dumps({k:receipt.get(k) for k in ('passed','wrapper_pid','wrapper_exit','outer_elapsed_s','error')}))
    return exit_code
if __name__=='__main__':sys.exit(main())
