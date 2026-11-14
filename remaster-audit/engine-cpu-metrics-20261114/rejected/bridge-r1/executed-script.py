from pathlib import Path
import datetime,hashlib,importlib.util,json,os,shutil,subprocess,time,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
source=r/'remaster-audit/runtime-review/remix-provenance/impl-v2';ready=json.loads((source/'READY.json').read_bytes())
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for rel,digest in ready['files'].items():assert sha(source/rel)==digest
hold=r/'remaster-audit/comfy-authoring/GPU-RESERVED';before=hold.read_bytes();assert json.loads(before)['owner']=='user-external-project'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([me.cpu_affinity()[-1]])
out=n/'real-producer-bridge';assert not out.exists();out.mkdir()
spec=importlib.util.spec_from_file_location('v2_host_recipe',source/'run_host_test_v2.py');recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
recipe.extract(source,out/'extracts')
for name in ['remix_mesh_packet.h','remix_mesh_packet.cpp']:shutil.copy2(n/'scene-packet-v2'/name,out/name)
shutil.copytree(n/'scene-packet-v2/vendor',out/'vendor')
test=(source/'tests/test_pgxp_view_v2.cpp').read_text()
assert test.count('int main() {')==1 and test.count('    t_tcp();')==1
test='#include "remix_mesh_packet.h"\n'+test.replace('int main() {',(n/'real_producer_bridge.inc').read_text()+'\nint main() {').replace('    t_tcp();','    t_tcp();\n    t_real_producer_bridge();')
(out/'test_real_producer.cpp').write_text(test,encoding='utf-8')
tc=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin');runtime=r/'windows-x64/psxrecomp/runtime'
inc=[str(source/'include'),str(runtime/'include'),str(out),str(out/'vendor'),str(out/'extracts')]
base=['-O1','-Wall','-Wextra']+['-I'+x for x in inc]
commands=[['clang.exe','-std=gnu11',*base,'-c',str(source/'tests/gpu_census_harness.c'),'-o',str(out/'harness.obj')],
 ['clang++.exe','-std=c++17',*base,str(out/'test_real_producer.cpp'),str(out/'remix_mesh_packet.cpp'),*[str(source/'src'/x) for x in ['gte.cpp','pgxp.cpp','pgxp_view_census.cpp']],str(out/'harness.obj'),'-o',str(out/'real_producer_test.exe')]]
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gpu_work':False,'sdk_calls':False,'game_executed':False,'one_logical_cpu':me.cpu_affinity(),'below_normal':True,'v2_ready_sha256':sha(source/'READY.json'),'commands':[],'source_hashes':{str(p):sha(p) for p in [n/'real_producer_bridge.inc',n/'run_real_producer_bridge.py',source/'run_host_test_v2.py',source/'tests/test_pgxp_view_v2.cpp',source/'tests/gpu_census_harness.c',source/'include/pgxp.h',source/'include/gpu.h',*[source/'src'/x for x in ['gte.cpp','pgxp.cpp','pgxp_view_census.cpp']]]}}
env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
def run(label,args):
 start=time.monotonic();q=subprocess.run(args,cwd=out,capture_output=True,text=True,encoding='utf-8',env=env,timeout=60,creationflags=0x4000)
 (out/(label+'.log')).write_text(q.stdout+q.stderr,encoding='utf-8');receipt['commands'].append({'label':label,'args':args,'exit':q.returncode,'seconds':round(time.monotonic()-start,3),'log':label+'.log'});print(json.dumps(receipt['commands'][-1]),flush=True);return q
ok=True
for i,c in enumerate(commands):
 c[0]=str(tc/c[0]);q=run('compile'+str(i),c)
 if q.returncode:ok=False;break
if ok:
 exe=out/'real_producer_test.exe';receipt['executable_sha256']=sha(exe);q=run('host-test',[str(exe)]);ok=q.returncode==0
 receipt['stdout_tail']=q.stdout.splitlines()[-1:];errors,replies=recipe.check_tcp(q.stdout);receipt['tcp_errors']=errors;ok=ok and not errors
 (out/'tcp-replies.json').write_text(json.dumps(replies,indent=2)+'\n')
assert hold.read_bytes()==before
for rel,digest in ready['files'].items():assert sha(source/rel)==digest
receipt.update(passed=ok,user_gpu_hold_unchanged=True,scope='Actual CPU GTE RTPT and SWC2 PGXP transport to SDK-layout resource staging, with synthetic guest input/dummy material and extracted GPU/debug stand-ins. No game, actual frame submission, SDK renderer, camera/world reconstruction, rendering, performance or visual acceptance.')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':ok,'stdout_tail':receipt.get('stdout_tail'),'tcp_errors':receipt.get('tcp_errors')}));raise SystemExit(0 if ok else 1)
