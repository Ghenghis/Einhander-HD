from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys, time
import psutil

p=Path(__file__).resolve().parent
r=Path('C:/github/Einhander')
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
out=p/'sdk-interop-r4';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-2:])
compiler=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
exe=out/'sdk-probe.exe';sdk=p.parent/'project-completion-20261114/remix-sdk-reference/remix_c.h'
dll=Path('C:/Program Files/NVIDIA Corporation/RTX Remix/deps/remix_runtime/runtime/.trex/d3d9.dll')
assert sha(sdk)=='a3f40860e643127dfd3bee1afee04a8715704d322a8b16d5bd542852f863501d'
assert sha(dll)=='ca71edf1d7d03d792a3e8d1d6b00c75d122220e4b4f323ef93e6f71bb9392dc1'
result={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(p/'sdk_probe.cpp'),'runner_sha256':sha(__file__),'dll_sha256':sha(dll),'header_sha256':sha(sdk),'priority':'below normal','cpu_affinity':me.cpu_affinity(),'resolution':[640,360],'frame_limit':24,'gameplay':False}
args=[str(compiler),'-std=c++17','-O1',str(p/'sdk_probe.cpp'),'-o',str(exe),'-luser32','-lgdi32','-lopengl32']
start=time.monotonic();build=subprocess.run(args,capture_output=True,text=True,timeout=60,creationflags=0x4000)
(out/'compile.log').write_text(build.stdout+build.stderr)
result['build']={'args':args,'exit':build.returncode,'seconds':time.monotonic()-start}
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';owned=None;process=None
try:
 assert build.returncode==0,build.stderr
 assert not marker.exists(),'Another GPU reservation exists'
 assert not (marker.parent/'GPU-LOCK').exists(),'Another GPU job exists'
 owned=(json.dumps({'owner':'codex-einhander-recovery','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'User-authorized RTX3090Ti private 24-frame SDK OpenGL interoperability probe. No3060; no game/settings mutation.'},indent=2)+'\n').encode()
 with marker.open('xb') as f:f.write(owned)
 sys.path.insert(0,str(r/'remaster-audit'))
 from gpu_capture_guard import require_quiet_gpu
 result['preflight']=require_quiet_gpu()
 (out/'dxvk.conf').write_text('dxvk.numCompilerThreads = 2\n')
 env=os.environ.copy();env.update(DXVK_FILTER_DEVICE_NAME='NVIDIA GeForce RTX 3090 Ti',DXVK_LOG_PATH=str(out),DXVK_CONFIG_FILE=str(out/'dxvk.conf'),DXVK_STATE_CACHE_PATH=str(out))
 result['process_environment_overrides']={k:env[k] for k in ['DXVK_FILTER_DEVICE_NAME','DXVK_LOG_PATH','DXVK_CONFIG_FILE','DXVK_STATE_CACHE_PATH']}
 args=[str(exe),str(out/'interop.ppm')];result['exe_sha256']=sha(exe)
 start=time.monotonic();snapshots=[]
 with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
  process=subprocess.Popen(args,cwd=out,env=env,stdout=stdout,stderr=stderr,creationflags=0x4000)
  result['pid']=process.pid;result['command']=args
  while process.poll() is None:
   elapsed=time.monotonic()-start
   if elapsed>60:
    result['watchdog_terminated']=True;process.terminate();break
   if not snapshots or elapsed-snapshots[-1]['seconds']>5:
    s=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name','--format=csv,noheader'],capture_output=True,text=True,timeout=4,creationflags=0x08000000)
    snapshots.append({'seconds':round(elapsed,3),'matching_process_rows':[x for x in s.stdout.splitlines() if f', {process.pid},' in x]})
   time.sleep(.1)
  result.update(exit=process.wait(timeout=10),seconds=round(time.monotonic()-start,3),gpu_process_samples=snapshots)
 result['passed']=result['exit']==0 and (out/'interop.ppm').exists()
 if (out/'interop.ppm').exists():
  from PIL import Image
  image=Image.open(out/'interop.ppm');image.save(out/'interop.png')
  pixels=list(image.getdata());green=sum(g>r*1.4 and g>b*1.4 and g>30 for r,g,b in pixels)
  result.update(image_sha256=sha(out/'interop.ppm'),rgb_extrema=image.getextrema(),green_pixels=green)
  result['passed']=result['passed'] and green>1000
except Exception as e:
 result.update(passed=False,error=str(e))
finally:
 if process is not None and process.poll() is None:
  process.terminate();process.wait(timeout=10)
 result['process_gone']=process is None or process.poll() is not None
 if owned is not None and marker.exists() and marker.read_bytes()==owned and result['process_gone']:
  (out/'released-reservation.json').write_bytes(owned);marker.unlink();result['reservation_released']=True
 result['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
sys.exit(0 if result['passed'] else 1)
