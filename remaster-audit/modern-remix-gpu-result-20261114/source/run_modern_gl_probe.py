"""Private bounded GPU qualification; the default path only reports a user hold.

The GPU mode requires an actual explicit human release plus the named switch.
It never expires, replaces or removes another owner's reservation.
"""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, os, psutil, shutil, subprocess, threading, time, uuid
from audit_modern_gl_image import audit_file

ROOT=Path('C:/github/Einhander'); BASE=Path(__file__).resolve().parent
MARKER=ROOT/'remaster-audit/comfy-authoring/GPU-RESERVED'; LOCK=MARKER.parent/'GPU-LOCK'
CPU_QUIET=MARKER.parent/'CPU-QUIET'
TARGET='GPU-ff51fa52-74c8-c785-e000-53fe58844033'
DEVICE='NVIDIA GeForce RTX 3090 Ti'
_guard_spec=importlib.util.spec_from_file_location('ein_shared_gpu_guard',ROOT/'tools/coordination/shared_gpu_guard.py')
SHARED=importlib.util.module_from_spec(_guard_spec);_guard_spec.loader.exec_module(SHARED)
EXE=BASE/'sdk-modern-gl-cpu-r4/sdk-modern-gl.exe'
DLL=BASE/'sdk-v016-release/win64/d3d9.dll'
EXE_SHA='3911f74c0e380f9358d32f529ee1de440b709bdf8fec93b1ef4ea12a91643d1d'
DLL_SHA='a8365272734cf5541e3600aeacb445c0fd102187dc3a167495a56809ce5891d9'
AUDIT_SHA='a8c80d0ab4acc7674d57c1791809929cb37dc9bdb2d0c4f8539bc3cdb4e2bc1f'
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def read_optional(file):
    try:return file.read_bytes()
    except FileNotFoundError:return None
def create_exclusive(file,data):
    with file.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
def retire_owned(file,lease,result):
    if read_optional(file)!=lease:return False
    retired=file.with_name(file.name+'.codex-release.'+uuid.uuid4().hex)
    try:os.rename(file,retired)
    except OSError as error:result.setdefault('release_errors',[]).append(repr(error));return False
    if retired.read_bytes()==lease:retired.unlink();return True
    # A foreign writer raced the ownership check. Preserve its bytes, and restore
    # the canonical name exclusively if still absent; never overwrite another lease.
    try:os.link(retired,file);retired.unlink()
    except OSError:result.setdefault('preserved_foreign_lease_files',[]).append(str(retired))
    return False
def finish_owned(child,result,lease,marker_owned,lock_owned,marker=MARKER,lock=LOCK):
    errors=[]
    if child is not None and child.poll() is None:
        try:child.terminate()
        except OSError as error:errors.append(repr(error))
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:result['owned_child_termination_timeout']=True
    gone=child is None or child.poll() is not None;result['owned_process_gone']=gone
    for file,owned,key in ((marker,marker_owned,'owned_marker_released'),(lock,lock_owned,'owned_lock_released')):
        result[key]=False
        if owned and gone:result[key]=retire_owned(file,lease,result)
    if not gone or marker_owned and not result['owned_marker_released'] or lock_owned and not result['owned_lock_released']:result['passed']=False
    return errors
def query(*args):
    x=subprocess.run(['nvidia-smi',*args],capture_output=True,text=True,timeout=4,creationflags=0x08000000)
    if x.returncode:raise RuntimeError('nvidia-smi failed: '+x.stderr[-1000:])
    return x.stdout
def preflight():
    rows=query('--id='+TARGET,'--query-gpu=uuid,name,memory.used,memory.total,utilization.gpu,power.draw,display_active','--format=csv,noheader,nounits').strip().split(', ')
    valid=len(rows)==7 and rows[0]==TARGET and rows[1]==DEVICE
    light_desktop=valid and rows[6]=='Enabled' and int(rows[2])<=3072 and float(rows[5])<=100 and int(rows[4])<=60
    quiet=valid and int(rows[4])<=5
    if not valid or int(rows[3])-int(rows[2])<6144 or not (quiet or light_desktop):
        raise RuntimeError('Target resource gate: >=6 GiB free and idle or bounded light display activity required: '+repr(rows))
    return dict(raw=rows,mode='idle utilization' if quiet else 'light active display: <=3GiB used, <=100W, <=60% busy-time',scope='Resource headroom heuristic, not proof the GPU is idle or prediction of responsiveness.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-after-explicit-user-release',action='store_true')
    parser.add_argument('--verify-current-user-hold',action='store_true',help='CPU-only refusal test; no adapter query or child launch')
    args=parser.parse_args()
    if args.run_after_explicit_user_release and args.verify_current_user_hold:parser.error('Modes are exclusive')
    out=BASE/('modern-gl-parent-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir(exist_ok=False)
    shutil.copy2(__file__,out/'executed-runner.py')
    me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
    before=read_optional(MARKER); lock_before=read_optional(LOCK);quiet_before=read_optional(CPU_QUIET)
    shared_token=os.environ.get('EINHANDER_SHARED_GPU_TOKEN');shared=SHARED.current_permission(shared_token)
    result=dict(started_utc=stamp(),gpu_executed=False,game_executed=False,window_created=False,renderer_dll_loaded=False,passed=False,mode='GPU requested after explicit release' if args.run_after_explicit_user_release else 'CPU reservation check',cpu_affinity=me.cpu_affinity(),below_normal=True)
    result['shared_gpu_permission']=shared
    if before is not None or lock_before is not None or quiet_before is not None or not shared['allowed'] or not args.run_after_explicit_user_release:
        result.update(status='NOT RUN: reservation exists or explicit GPU mode absent',reservation_exists=before is not None,lock_exists=lock_before is not None,cpu_quiet_exists=quiet_before is not None,user_marker_sha256=hashlib.sha256(before).hexdigest() if before is not None else None,reservation_unchanged=read_optional(MARKER)==before,lock_unchanged=read_optional(LOCK)==lock_before,child_started=False,adapter_queried=False)
        if args.verify_current_user_hold:
            result['passed']=before is not None and json.loads(before)['owner']=='user-external-project' and result['reservation_unchanged'] and result['lock_unchanged']
            result['scope']='Actual CPU-only parent refusal under current user hold; no GPU qualification.'
        result['ended_utc']=stamp();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['passed'] else 77
    child=None;lease=None;lock_owned=False;marker_owned=False;samples=[];timer=None;watchdog=threading.Event();termination_errors=[]
    try:
        assert sha(EXE)==EXE_SHA and sha(DLL)==DLL_SHA,'Private build/runtime pin mismatch'
        assert sha(BASE/'audit_modern_gl_image.py')==AUDIT_SHA,'Independent image-oracle pin mismatch'
        shutil.copy2(BASE/'audit_modern_gl_image.py',out/'executed-image-oracle.py')
        # Insertion order and compact serialization are the child's documented lease format.
        nonce=uuid.uuid4().hex
        lease=(json.dumps(dict(owner='codex-einhander',purpose='private-modern-sdk-gl-probe',lease_nonce=nonce,parent_pid=os.getpid(),gpu_uuid=TARGET,at_utc=stamp(),watchdog_seconds=45),separators=(',',':'))+'\n').encode()
        create_exclusive(LOCK,lease);lock_owned=True
        create_exclusive(MARKER,lease);marker_owned=True
        result['reserved_preflight']=preflight()
        assert read_optional(CPU_QUIET) is None,'A CPU quiet reservation appeared'
        result['shared_broker_check']=SHARED.broker_action('check',shared_token,out)
        (out/'owned-lease.json').write_bytes(lease)
        (out/'dxvk.conf').write_text('dxvk.numCompilerThreads = 1\n')
        env=os.environ.copy();env.update(EINHANDER_PRIVATE_GPU_NONCE=nonce,DXVK_FILTER_DEVICE_NAME=DEVICE,DXVK_LOG_PATH=str(out),DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_STATE_CACHE_PATH=str(out),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        command=[str(EXE),'--run-after-explicit-user-release',str(out/'readback')]
        assert sha(EXE)==EXE_SHA and sha(DLL)==DLL_SHA,'Private pins changed before launch'
        created=datetime.datetime.fromtimestamp(me.create_time(),datetime.timezone.utc).isoformat()
        result['shared_managed_runner']=SHARED.broker_action('start',shared_token,out,pid=os.getpid(),created_utc=created,command='Einhander private modern GL probe managed parent; child '+str(EXE))
        result['shared_release_requirement']='Registered parent must exit before integration owner verifies cleanup and explicitly releases the grant; no automatic transfer.'
        start=time.monotonic(); last_query=-5
        with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
            child=subprocess.Popen(command,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
            result.update(pid=child.pid,command=command,gpu_attempted=True,window_created='Unknown until child graphics-context event',renderer_dll_loaded='Unknown until child initialization result',executable_sha256=sha(EXE),dll_sha256=sha(DLL))
            def stop_owned_child():
                if child.poll() is None:
                    watchdog.set()
                    try:child.terminate()
                    except OSError as error:termination_errors.append(repr(error))
            timer=threading.Timer(45,stop_owned_child);timer.daemon=True;timer.start()
            while child.poll() is None:
                elapsed=time.monotonic()-start
                if elapsed>=45:stop_owned_child();break
                if read_optional(MARKER)!=lease or read_optional(LOCK)!=lease or read_optional(CPU_QUIET) is not None or not SHARED.current_permission(shared_token,new_starts=False)['allowed']:
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
        result['image_oracles']=[dict(frame=frame,**audit_file(out/('readback.'+str(frame)+'.ppm'),offset)) for frame,offset in ((7,-2),(23,0),(31,2))]
        result['three_distinct_images']=len({x['sha256'] for x in result['image_oracles']})==3
        result['passed']=all(result[key] for key in ('selected_adapter_verified','owned_pid_seen_on_target','readback_control_passed','lifecycle_passed','three_distinct_images')) and all(x['passed'] for x in result['image_oracles'])
    except Exception as error:
        result['error']=repr(error);result['passed']=False
    finally:
        if timer is not None:timer.cancel()
        try:termination_errors.extend(finish_owned(child,result,lease,marker_owned,lock_owned))
        except Exception as error:
            result['cleanup_error']=repr(error);result['passed']=False;result.setdefault('owned_process_gone',None)
        result['watchdog_termination_requested']=watchdog.is_set();result['termination_errors']=termination_errors
        result['watchdog_scope']='Termination requested at 45 s after child launch by a separate parent timer. Driver-delayed termination is not guaranteed; leases remain if the child is still alive. Parent observation/cleanup can take about 70 s including two preflights, a metadata query and bounded waits.'
        if watchdog.is_set():result['timeout_interpretation']='Qualification incomplete under one-core cold-start confinement; timeout alone does not establish an SDK defect or cause.'
        result['ended_utc']=stamp();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='gpu_process_samples'}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
