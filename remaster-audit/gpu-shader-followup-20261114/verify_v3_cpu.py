from pathlib import Path
import hashlib,json,subprocess,shutil,os,datetime,psutil
p=Path(__file__).resolve().parent;r=p.parents[2];f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v3';out=p/'v3-cpu-verification-r2';out.mkdir(exist_ok=False)
sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest()
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes();assert json.loads(hold)['owner']=='user-external-project'
assert sha(f/'READY.json')=='90cb506ddae3952509baabd2f1f6a7218f0c17ab2589029b98c1e139d9efa625'
assert sha(f/'SHA256SUMS.txt')=='a43774a12dc6c9f195976515a31b754f7e67302507f7b1cd1a7470a605a70995'
count=0
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
 h,name=line.split('  ',1);file=(f/name).resolve();assert file.is_relative_to(f.resolve());assert sha(file)==h,name;count+=1
rd=f/'host-run/20261114T113027Z';result=json.loads((rd/'result.json').read_text());first=next(x for x in result['steps']['4-sidecars']['sidecars'] if x['in_index'])
for source in [f/'src/test_hd_class_mips.c',f/'src/hd_class_mips.inc',rd/'glue/glue_harness.c',rd/'glue/glue.c',rd/'inputs/class_mip.c',rd/'inputs/class_mip.h']:shutil.copy2(source,out/source.name)
compiler='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe';rows=[]
def run(label,args,env=None):
 res=subprocess.run(args,cwd=out,capture_output=True,text=True,env=env,timeout=45,creationflags=0x4000)
 (out/(label+'.log')).write_text(res.stdout+res.stderr);rows.append({'label':label,'arguments':args,'exit':res.returncode,'stdout_tail':res.stdout.splitlines()[-6:]});assert res.returncode==0,label
run('compile-fixture',[compiler,'-std=c11','-O1','-Wall','-Wextra','-Wno-unused-function','-I'+str(out),str(out/'test_hd_class_mips.c'),str(out/'class_mip.c'),'-o',str(out/'fixture.exe')])
run('fixture',[str(out/'fixture.exe')])
run('compile-glue-stubs',[compiler,'-std=c11','-O1','-Wall','-Wextra','-Wno-unused-function','-I'+str(out),str(out/'glue_harness.c'),'-o',str(out/'glue.exe')])
nw,nh=first['native'];scale=first['scale'];rgba=rd/'glue/rgba.bin';assert rgba.stat().st_size==nw*scale*nh*scale*4
args=[str(out/'glue.exe'),'',str(rgba),str(nw*scale),str(nh*scale),*first['key'].split('-'),str(nw),str(nh),'2',str(nw),str(first['levels']),'8']
env={k:v for k,v in os.environ.items() if not k.startswith('PSXRECOMP_HD_CLASS_MIPS')}
args[1]='off';run('glue-off',list(args),env)
env.update(PSXRECOMP_HD_CLASS_MIPS='1',PSXRECOMP_HD_CLASS_MIPS_DIR=str(rd/'sidecars'))
args[1]='on';run('glue-on',list(args),env)
assert marker.read_bytes()==hold
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frozen_files_verified':count,'ready_sha256':sha(f/'READY.json'),'sums_sha256':sha(f/'SHA256SUMS.txt'),'root_recompiled_and_replayed':True,'commands':rows,'sources':{x.name:sha(x) for x in out.iterdir() if x.suffix in ['.c','.inc']},'compiler_sha256':sha(compiler),'gpu_executed':False,'gl_stubs_only':True,'user_gpu_hold_unchanged':True,'passed':True,'mutants_replayed':False}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'verified_files':count,'host_runs':rows,'gpu':False}))
