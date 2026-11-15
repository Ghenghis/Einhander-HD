from pathlib import Path
import hashlib,json,subprocess,time,psutil,shutil
p=Path(__file__).resolve().parent;root=p.parents[2]
src=root/'remaster-audit/claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1/proto-v2b'
out=p/'class-mip-replay';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
for f in src.glob('*'):
 if f.suffix in ['.c','.h']:shutil.copy2(f,out/f.name)
compiler=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe')
args=[str(compiler),'-std=c11','-O1','-Wall','-Wextra',str(out/'test_class_mip.c'),str(out/'class_mip.c'),'-o',str(out/'test.exe')]
start=time.monotonic();build=subprocess.run(args,capture_output=True,text=True,timeout=45,creationflags=0x4000)
(out/'compile.log').write_text(build.stdout+build.stderr)
result={'commands':[args],'source_hashes':{x.name:sha(x) for x in out.glob('*') if x.suffix in ['.h','.c']},'build_exit':build.returncode,'cpu_affinity':me.cpu_affinity(),'gpu':False,'mutants_replayed':False}
if build.returncode==0:
 args=[str(out/'test.exe')];run=subprocess.run(args,capture_output=True,text=True,timeout=15,creationflags=0x4000)
 (out/'test.log').write_text(run.stdout+run.stderr);result.update(test_exit=run.returncode,summary=run.stdout.strip().splitlines()[-1],executable_sha256=sha(out/'test.exe'));result['commands'].append(args)
result.update(seconds=time.monotonic()-start,passed=build.returncode==0 and result.get('test_exit')==0)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
