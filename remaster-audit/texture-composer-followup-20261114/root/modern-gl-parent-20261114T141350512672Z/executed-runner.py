"""Private bounded GPU qualification; the default path only reports a user hold.

The GPU mode requires an actual explicit human release plus the named switch.
It never expires, replaces or removes another owner's reservation.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, psutil, shutil, subprocess, threading, time, uuid
from audit_modern_gl_image import audit_file

ROOT=Path('C:/github/Einhander'); BASE=Path(__file__).resolve().parent
MARKER=ROOT/'remaster-audit/comfy-authoring/GPU-RESERVED'; LOCK=MARKER.parent/'GPU-LOCK'
TARGET='GPU-ff51fa52-74c8-c785-e000-53fe58844033'
DEVICE='NVIDIA GeForce RTX 3090 Ti'
EXE=BASE/'sdk-modern-gl-cpu-r3/sdk-modern-gl.exe'
DLL=BASE/'sdk-v016-release/win64/d3d9.dll'
EXE_SHA='102bfad90943d47148c61d340d570329f104ac77220cce5632f74a04389e6a88'
DLL_SHA='a8365272734cf5541e3600aeacb445c0fd102187dc3a167495a56809ce5891d9'
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def read_optional(file):
    try:return file.read_bytes()
    except FileNotFoundError:return None
def create_exclusive(file,data):
    with file.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
def query(*args):
    x=subprocess.run(['nvidia-smi',*args],capture_output=True,text=True,timeout=4,creationflags=0x08000000)
    if x.returncode:raise RuntimeError('nvidia-smi failed: '+x.stderr[-1000:])
    return x.stdout
def preflight():
    rows=query('--id='+TARGET,'--query-gpu=uuid,name,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits').strip().split(', ')
    if len(rows)!=5 or rows[0]!=TARGET or rows[1]!=DEVICE or int(rows[3])-int(rows[2])<6144 or int(rows[4])>5:
        raise RuntimeError('Target adapter is not quiet with at least 6 GiB free: '+repr(rows))
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-after-explicit-user-release',action='store_true')
    parser.add_argument('--verify-current-user-hold',action='store_true',help='CPU-only refusal test; no adapter query or child launch')
    args=parser.parse_args()
    if args.run_after_explicit_user_release and args.verify_current_user_hold:parser.error('Modes are exclusive')
    out=BASE/('modern-gl-parent-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir(exist_ok=False)
    shutil.copy2(__file__,out/'executed-runner.py')
    me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
    before=read_optional(MARKER); lock_before=read_optional(LOCK)
    result=dict(started_utc=stamp(),gpu_executed=False,game_executed=False,window_created=False,renderer_dll_loaded=False,passed=False,mode='GPU requested after explicit release' if args.run_after_explicit_user_release else 'CPU reservation check',cpu_affinity=me.cpu_affinity(),below_normal=True)
    if before is not None or lock_before is not None or not args.run_after_explicit_user_release:
        result.update(status='NOT RUN: reservation exists or explicit GPU mode absent',reservation_exists=before is not None,lock_exists=lock_before is not None,user_marker_sha256=hashlib.sha256(before).hexdigest() if before is not None else None,reservation_unchanged=read_optional(MARKER)==before,lock_unchanged=read_optional(LOCK)==lock_before,child_started=False,adapter_queried=False)
        if args.verify_current_user_hold:
            result['passed']=before is not None and json.loads(before)['owner']=='user-external-project' and result['reservation_unchanged'] and result['lock_unchanged']
            result['scope']='Actual CPU-only parent refusal under current user hold; no GPU qualification.'
        result['ended_utc']=stamp();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['passed'] else 77
    child=None;lease=None;lock_owned=False;marker_owned=False;samples=[];timer=None;watchdog=threading.Event()
    try:
        assert sha(EXE)==EXE_SHA and sha(DLL)==DLL_SHA,'Private build/runtime pin mismatch'
        result['target_preflight']=preflight()
        # Insertion order and compact serialization are the child's documented lease format.
        nonce=uuid.uuid4().hex
        lease=(json.dumps(dict(owner='codex-einhander',purpose='private-modern-sdk-gl-probe',lease_nonce=nonce,parent_pid=os.getpid(),gpu_uuid=TARGET,at_utc=stamp(),watchdog_seconds=45),separators=(',',':'))+'\n').encode()
        create_exclusive(LOCK,lease);lock_owned=True
        create_exclusive(MARKER,lease);marker_owned=True
        result['reserved_preflight']=preflight()
        (out/'owned-lease.json').write_bytes(lease)
        (out/'dxvk.conf').write_text('dxvk.numCompilerThreads = 1\n')
        env=os.environ.copy();env.update(EINHANDER_PRIVATE_GPU_NONCE=nonce,DXVK_FILTER_DEVICE_NAME=DEVICE,DXVK_LOG_PATH=str(out),DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_STATE_CACHE_PATH=str(out),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        command=[str(EXE),'--run-after-explicit-user-release',str(out/'readback')]
        start=time.monotonic(); last_query=-5
        with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
            child=subprocess.Popen(command,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
            result.update(pid=child.pid,command=command,gpu_attempted=True,window_created='Unknown until child graphics-context event',renderer_dll_loaded='Unknown until child initialization result',executable_sha256=sha(EXE),dll_sha256=sha(DLL))
            def stop_owned_child():
                if child.poll() is None:
                    watchdog.set();child.terminate()
            timer=threading.Timer(45,stop_owned_child);timer.daemon=True;timer.start()
            while child.poll() is None:
                elapsed=time.monotonic()-start
                if elapsed>=45:stop_owned_child();break
                if read_optional(MARKER)!=lease or read_optional(LOCK)!=lease:
                    result['reservation_changed_abort']=True;child.terminate();break
                if elapsed-last_query>=2:
                    last_query=elapsed
                    lines=query('--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader').splitlines()
                    mine=[line for line in lines if len(line.split(','))>=2 and line.split(',')[1].strip()==str(child.pid)]
                    samples.append(dict(seconds=round(elapsed,3),owned_pid_rows=mine))
                    if any(not line.startswith(TARGET+',') for line in mine):result['wrong_adapter_abort']=True;child.terminate();break
                time.sleep(.05)
            result.update(exit=child.wait(timeout=5),seconds=round(time.monotonic()-start,3),gpu_process_samples=samples,watchdog_terminated=watchdog.is_set())
        events=[]
        for line in (out/'stdout.jsonl').read_text().splitlines():
            try:events.append(json.loads(line))
            except json.JSONDecodeError:pass
        result['selected_adapter_verified']=any(DEVICE in x.get('gl_renderer','') for x in events)
        result['gpu_executed']=any('gl_renderer' in x for x in events)
        result['window_created']=True if result['gpu_executed'] else 'Not observed; inspect child exit/log'
        result['renderer_dll_initialization_passed']=any(x.get('call')=='InitializeLibrary' and x.get('rc')==0 for x in events)
        result['renderer_dll_loaded']=True if result['renderer_dll_initialization_passed'] else 'Not established by initialization result'
        result['owned_pid_seen_on_target']=any(line.startswith(TARGET+',') for sample in samples for line in sample['owned_pid_rows'])
        result['readback_control_passed']=any(x.get('owned_readback_magenta_pixels')==320*180 for x in events)
        result['lifecycle_passed']=result['exit']==0 and any(x.get('call')=='Shutdown' and x.get('rc')==0 for x in events)
        result['image_oracles']=[dict(frame=frame,**audit_file(out/('readback.'+str(frame)+'.ppm'))) for frame in (7,23,31)]
        result['passed']=all(result[key] for key in ('selected_adapter_verified','owned_pid_seen_on_target','readback_control_passed','lifecycle_passed')) and all(x['passed'] for x in result['image_oracles'])
    except Exception as error:
        result['error']=repr(error);result['passed']=False
    finally:
        if timer is not None:timer.cancel()
        if child is not None and child.poll() is None:child.terminate();child.wait(timeout=5)
        gone=child is None or child.poll() is not None;result['owned_process_gone']=gone
        for file,owned,key in ((MARKER,marker_owned,'owned_marker_released'),(LOCK,lock_owned,'owned_lock_released')):
            result[key]=False
            if owned and gone and read_optional(file)==lease:file.unlink();result[key]=True
        if not gone or marker_owned and not result['owned_marker_released'] or lock_owned and not result['owned_lock_released']:result['passed']=False
        result['ended_utc']=stamp();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='gpu_process_samples'}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
