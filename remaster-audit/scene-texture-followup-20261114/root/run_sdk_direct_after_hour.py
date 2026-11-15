"""One bounded 3060 diagnostic. Never replaces/uses the user's 3090 lease."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess,time
n=Path(__file__).resolve().parent;r=n.parents[2];out=n/'sdk-direct-after-hour-r1';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
target='GPU-ff51fa52-74c8-c785-e000-53fe58844033';reserved='GPU-eb6787b1-90ea-26b2-4a62-d44b1452d8aa'
device_name='NVIDIA GeForce RTX 3090 Ti';me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-2:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
assert json.loads(hold)['owner']=='user-external-project' and json.loads(hold)['rtx3060_allowed_if_needed']
deadline=datetime.datetime.fromisoformat(json.loads(hold)['expires_utc'].replace('Z','+00:00'))
assert datetime.datetime.now(datetime.timezone.utc)>=deadline,'User 3090 hour has not ended'
assert not (marker.parent/'GPU-LOCK').exists()
lease=marker.parent/'GPU-LOCK';owned=None;process=None
exe=n/'sdk-direct-cpu-r2/sdk-direct-control.exe';assert sha(exe)=='9d588f52417829501f9b2666ee36880cd6e76d741c0fdfe14f02b65c80680e55'
dll=Path('C:/Program Files/NVIDIA Corporation/RTX Remix/deps/remix_runtime/runtime/.trex/d3d9.dll')
assert sha(dll)=='ca71edf1d7d03d792a3e8d1d6b00c75d122220e4b4f323ef93e6f71bb9392dc1'
def query(args):
    x=subprocess.run(['nvidia-smi',*args],capture_output=True,text=True,timeout=5,creationflags=0x08000000)
    assert x.returncode==0,x.stderr
    return x.stdout
result=dict(started_utc=stamp(),gpu_target_uuid=target,gpu_target_name=device_name,other_gpu_uuid=reserved,
            user_3090_lease_writes=True,resolution=[320,180],frame_limit=120,fps_cap=10,watchdog_seconds=45,
            executable_sha256=sha(exe),dll_sha256=sha(dll),cpu_affinity=me.cpu_affinity(),below_normal=True,
            purpose='Owned D3D9 readback and direct registered-device Present control; no game, GL or global driver changes.',passed=False)
try:
    gpu=query(['--id='+target,'--query-gpu=uuid,name,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits']).strip().split(', ')
    assert gpu[0]==target and gpu[1]==device_name and int(gpu[3])-int(gpu[2])>=6144 and int(gpu[4])<=5,gpu
    result['target_preflight']=gpu
    rows=query(['--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).splitlines()
    # User desktop contexts may remain. Low utilization + >=6GiB free is the
    # gate; no other process is stopped or reconfigured.
    result['target_existing_context_count']=sum(x.startswith(target+',') for x in rows)
    owned=(json.dumps(dict(owner='codex-einhander-recovery',gpu_uuid=target,at_utc=stamp(),scope='Single bounded 3090 SDK control after user-authorized hour; below-normal,320x180,45s watchdog'),indent=2)+'\n').encode()
    with lease.open('xb') as f:f.write(owned)
    (out/'expired-user-3090-lease.json').write_bytes(hold)
    assert marker.read_bytes()==hold
    marker.write_bytes(owned)
    (out/'owned-3090-lease.json').write_bytes(owned)
    (out/'dxvk.conf').write_text('dxvk.numCompilerThreads = 1\n')
    env=os.environ.copy();env.update(DXVK_FILTER_DEVICE_NAME=device_name,DXVK_LOG_PATH=str(out),DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_STATE_CACHE_PATH=str(out))
    result['environment_overrides']={k:env[k] for k in ['DXVK_FILTER_DEVICE_NAME','DXVK_LOG_PATH','DXVK_CONFIG_FILE','DXVK_STATE_CACHE_PATH']}
    args=[str(exe),str(out/'readback'),device_name];result['command']=args
    samples=[];start=time.monotonic()
    with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
        process=subprocess.Popen(args,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=0x4000);result['pid']=process.pid
        while process.poll() is None:
            elapsed=time.monotonic()-start
            if elapsed>45:result['watchdog_terminated']=True;process.terminate();break
            if not samples or elapsed-samples[-1]['seconds']>=2:
                rows=query(['--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader']).splitlines()
                mine=[x for x in rows if f', {process.pid},' in x]
                samples.append(dict(seconds=round(elapsed,3),owned_pid_rows=mine))
            time.sleep(.1)
        result.update(exit=process.wait(timeout=10),seconds=round(time.monotonic()-start,3),gpu_process_samples=samples)
    events=[]
    for line in (out/'stdout.jsonl').read_text().splitlines():
        try:events.append(json.loads(line))
        except json.JSONDecodeError:pass
    result['selected_adapter_verified']=any(x.get('description')==device_name for x in events)
    result['owned_pid_seen_on_target']=any(x.startswith(target+',') for s in samples for x in s['owned_pid_rows'])
    result['owned_pid_seen_on_other_gpu']=any(x.startswith(reserved+',') for s in samples for x in s['owned_pid_rows'])
    result['readback_samples']=[x for x in events if 'readback_frame' in x]
    result['readback_control_passed']=any(x['readback_frame']==-1 and x['magenta_pixels']>57000 for x in result['readback_samples'])
    result['scene_image_passed']=any(x['readback_frame']>=0 and x['green_pixels']>200 for x in result['readback_samples'])
    result['lifecycle_passed']=result['exit']==0 and any(x.get('call')=='Shutdown' and x.get('code')==0 for x in events)
    result['passed']=all(result[x] for x in ['selected_adapter_verified','owned_pid_seen_on_target','readback_control_passed','scene_image_passed','lifecycle_passed'])
except Exception as ex:
    result['error']=repr(ex)
    if process is None:result['gpu_test_status']='NOT_RUN_RESOURCE_PREFLIGHT'
finally:
    if process is not None and process.poll() is None:process.terminate();process.wait(timeout=10)
    result['process_gone']=process is None or process.poll() is not None
    if owned is not None and lease.exists() and lease.read_bytes()==owned and result['process_gone']:
        lease.unlink();result['owned_gpu_lock_released']=True
    if owned is not None and marker.exists() and marker.read_bytes()==owned and result['process_gone']:
        marker.unlink();result['owned_3090_lease_released']=True
    result['expired_user_lease_archived']=owned is not None and (out/'expired-user-3090-lease.json').exists()
    result['user_hour_respected']=datetime.datetime.now(datetime.timezone.utc)>=deadline
    result['ended_utc']=stamp();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copy2(__file__,out/'executed-runner.py');shutil.copy2(n/'sdk_direct_control.cpp',out/'executed-source.cpp')
    print(json.dumps({k:v for k,v in result.items() if k not in ['environment_overrides','command','gpu_process_samples']},indent=2))
raise SystemExit(0 if result['passed'] else 1)
