"""SOURCE ONLY: focused Windows lifetime diagnostic; no game/GPU/network.

Future fresh grant only, under qualified fa5 one-CPU/BelowNormal/10s/128MiB Job.
Two tiny owned Python children, sequential: ordinary exit and TerminateProcess.
It records signaled handles/exit codes separately from PID visibility. Visibility
while a handle is retained is an observation, not a pass criterion or a causal proof.
No 74-control rerun. An outer kill can prevent this probe's final receipt.
"""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
import gc
import hashlib
import json
import os
import psutil
import subprocess
import sys
import time

def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def need(ok,why):
    if not ok:raise RuntimeError(why)
def metadata(pid,created):
    row=dict(at_utc=utc(),pid=pid,expected_creation_unix=created,same_identity=None)
    try:
        proc=psutil.Process(pid)
        row.update(creation_unix=proc.create_time(),is_running=proc.is_running())
        row['same_identity']=row['creation_unix']==created
    except psutil.NoSuchProcess:row['same_identity']=False
    except psutil.Error as error:row['error']=type(error).__name__
    return row

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True);parser.add_argument('--cpu',type=int,required=True)
    parser.add_argument('--grant-id',required=True)
    args=parser.parse_args()
    need(os.name=='nt' and sys.flags.isolated and not sys.flags.optimize,'Windows, -I and no -O required')
    need(Path(sys.executable).resolve()==Path(sys._base_executable).resolve(),'Base Python required; no venv redirector')
    own_source=Path(__file__).read_bytes()
    me=psutil.Process();need(args.cpu in me.cpu_affinity(),'CPU outside granted affinity')
    me.cpu_affinity([args.cpu]);me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    out=Path(args.out).resolve();out.mkdir(exist_ok=False)
    child_source=b'import sys\nsys.stdin.buffer.read(1)\n'
    child_file=out/'owned-lifetime-child.py'
    with child_file.open('xb') as stream:stream.write(child_source)
    with (out/'executed-probe.py').open('xb') as stream:stream.write(own_source)
    need(child_file.read_bytes()==child_source and (out/'executed-probe.py').read_bytes()==own_source,'Copied source changed')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype=wintypes.BOOL
    result=dict(at_utc=utc(),grant_id=args.grant_id,cpu=args.cpu,source_sha256=hashlib.sha256(own_source).hexdigest(),
        child_source_sha256=hashlib.sha256(child_source).hexdigest(),cases=[],passed=False,
        gpu_run=False,game_run=False,network_used=False,collector_controls_rerun=False,
        envelope_required='fa5/oneCPU/BelowNormal/10s/128MiB; validated by separate outer receipt')
    process=None
    try:
        for mode in ('normal_exit','terminate_owned'):
            case=dict(mode=mode,held=[],released=[],passed=False);result['cases'].append(case)
            process=subprocess.Popen([sys.executable,'-I','-B',str(child_file)],stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08004000)
            pid=process.pid;created=psutil.Process(pid).create_time()
            case.update(pid=pid,creation_unix=created,before=metadata(pid,created))
            if mode=='normal_exit':process.stdin.close()
            else:process.terminate();process.stdin.close()
            case['retained_popen_exit']=process.wait(timeout=2)
            # Keep only the integer handle value, never another owning Handle reference.
            raw_handle=int(process._handle)
            code=wintypes.DWORD()
            case['wait_status']=int(kernel.WaitForSingleObject(raw_handle,0))
            case['exit_query_ok']=bool(kernel.GetExitCodeProcess(raw_handle,ctypes.byref(code)))
            case['win32_exit_code']=int(code.value)
            for delay in (0,.025,.1):
                if delay:time.sleep(delay)
                case['held'].append(metadata(pid,created))
            process=None;gc.collect()
            case['own_popen_released']=True
            start=time.monotonic()
            for offset in (0,.025,.1,.25,.5,.75):
                left=offset-(time.monotonic()-start)
                if left>0:time.sleep(left)
                case['released'].append(metadata(pid,created))
                if case['released'][-1]['same_identity'] is False:break
            case['held_identity_visibility_reproduced']=any(row['same_identity'] is True for row in case['held'])
            case['passed']=(case['before']['same_identity'] is True and case['wait_status']==0
                and case['exit_query_ok'] is True and case['win32_exit_code']!=259
                and case['win32_exit_code']==(case['retained_popen_exit']&0xFFFFFFFF)
                and ((mode=='normal_exit' and case['retained_popen_exit']==0)
                     or (mode=='terminate_owned' and case['retained_popen_exit']!=0))
                and case['released'][-1]['same_identity'] is False)
        result['passed']=len(result['cases'])==2 and all(case['passed'] for case in result['cases'])
    except Exception as error:result['error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None and process.poll() is None:
            try:process.kill();process.wait(timeout=2)
            except Exception as error:result['cleanup_error']=type(error).__name__+': '+str(error)
        result['ended_utc']=utc()
        payload=json.dumps(result,indent=2,allow_nan=False)+'\n'
        with (out/'result.json').open('x',encoding='utf-8') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(passed=result['passed'],cases=len(result['cases']),error=result.get('error'))))
    return 0 if result['passed'] else 1
if __name__=='__main__':sys.exit(main())
