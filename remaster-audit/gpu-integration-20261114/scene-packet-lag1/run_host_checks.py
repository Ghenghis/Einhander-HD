from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,time,psutil
p=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
hold=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold_bytes=hold.read_bytes() if hold.exists() else None
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([me.cpu_affinity()[-1]])
vendor=p/'vendor';vendor.mkdir(exist_ok=True)
sdk=r/'remaster-audit/runtime-review/project-completion-20261114/remix-sdk-reference/remix_c.h'
pgxp=r/'remaster-audit/runtime-review/remix-provenance/impl-v2/include/pgxp.h'
assert sha(sdk)=='a3f40860e643127dfd3bee1afee04a8715704d322a8b16d5bd542852f863501d'
assert sha(pgxp)=='a9b658729d4f60f5d7b2a58e68c449a3c303b7e4f8d789db81e908b53c84108e'
for source in [sdk,pgxp]:shutil.copy2(source,vendor/source.name)
compiler=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
exe=p/'mesh_packet_test.exe';args=[str(compiler),'-std=c++17','-O1','-Wall','-Wextra','-I'+str(vendor),str(p/'remix_mesh_packet.cpp'),str(p/'test_remix_mesh_packet.cpp'),'-o',str(exe)]
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_work':False,'game_executed':False,'sdk_calls':False,
 'logical_cpu_affinity':me.cpu_affinity(),'priority_class':int(me.nice()),'compiler_sha256':sha(compiler),'commands':[],
 'source_hashes':{x.name:sha(x) for x in p.glob('*') if x.is_file() and x.suffix in ['.h','.cpp','.py']},'header_pins':{x.name:sha(x) for x in vendor.glob('*.h')}}
def run(label,command):
 log=p/(label+'.log');start=time.monotonic();peak=0
 with log.open('w',encoding='utf-8') as stream:
  process=subprocess.Popen(command,cwd=p,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x4000)
  child=psutil.Process(process.pid)
  while process.poll() is None:
   try:peak=max(peak,child.memory_info().rss)
   except psutil.NoSuchProcess:pass
   if time.monotonic()-start>60:process.terminate();break
   time.sleep(.025)
  code=process.wait(timeout=5)
 row={'label':label,'arguments':command,'exit':code,'seconds':round(time.monotonic()-start,3),'peak_sampled_rss_bytes':peak,'stdout':log.read_text()[-5000:]}
 receipt['commands'].append(row);print(json.dumps(row),flush=True);return code
rc=run('compile',args)
if rc==0:
 receipt['executable_sha256']=sha(exe);rc=run('host-test',[str(exe)])
assert (hold.read_bytes() if hold.exists() else None)==hold_bytes
receipt.update(ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=rc==0,user_gpu_hold_unchanged=True,
 scope='CPU resource-packet construction against official SDK layout using explicit host fixtures. No game integration, real material allocation, camera/world reconstruction, SDK renderer call, rendering or GPU test.')
(p/'host-results.json').write_text(json.dumps(receipt,indent=2)+'\n')
raise SystemExit(rc)
