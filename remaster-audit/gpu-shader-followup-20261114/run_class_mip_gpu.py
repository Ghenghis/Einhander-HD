from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,sys,time,psutil
p=Path(__file__).resolve().parent;r=p.parents[2]
source=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/selftest/20261114T110630Z'
out=p/'class-mip-gpu-r1';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
build=json.loads((source/'build.json').read_text());assert build['compile_rc']==0
for name,h in build['files'].items():assert sha(source/name)==h,name
for name in [*build['files'],'build.json','README-ROOT.md','compile.log']:
 if (source/name).exists():shutil.copy2(source/name,out/name)
assert sha(out/'HD_FS.frag')==build['files']['HD_FS.frag']
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-2:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';assert not marker.exists();assert not (marker.parent/'GPU-LOCK').exists()
owned=(json.dumps({'owner':'codex-einhander-recovery','scope':'User-authorized RTX3090Ti, private64x64GLshaderfixture, no game, no3060','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})+'\n').encode()
with marker.open('xb') as f:f.write(owned)
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'author_build_sha256':sha(source/'build.json'),'all_build_files_verified':True,'original_build_files':build['files'],'gpu_fixture_only':True,'gameplay':False,'renderer_version':'v1 shader, v1 uploader superseded after review; this test does not exercise slot uploader/sidecar admission','passed':False}
process=None
try:
 sys.path.insert(0,str(r/'remaster-audit'));from gpu_capture_guard import require_quiet_gpu
 result['preflight']=require_quiet_gpu()
 args=[str(out/'gl_selftest_classmips.exe'),str(out/'TEX_VS.vert'),str(out/'HD_FS.frag'),str(out/'selftest-result.json')]
 start=time.monotonic()
 with (out/'stdout.log').open('w') as a,(out/'stderr.log').open('w') as b:
  process=subprocess.Popen(args,cwd=out,stdout=a,stderr=b,creationflags=0x4000)
  result['pid']=process.pid;result['arguments']=args
  try:result['exit']=process.wait(timeout=20)
  except subprocess.TimeoutExpired:process.terminate();result.update(exit=process.wait(timeout=5),watchdog_terminated=True)
 result['seconds']=round(time.monotonic()-start,3)
 if (out/'selftest-result.json').exists():
  data=json.loads((out/'selftest-result.json').read_text());result['test_result']=data
  result['passed']=result['exit']==0 and data.get('pass') is True
except Exception as ex:result['error']=repr(ex)
finally:
 if process and process.poll() is None:process.terminate();process.wait(timeout=5)
 result['process_gone']=process is None or process.poll() is not None
 if marker.exists() and marker.read_bytes()==owned and result['process_gone']:
  (out/'released-reservation.json').write_bytes(owned);marker.unlink();result['reservation_released']=True
 (out/'root-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
