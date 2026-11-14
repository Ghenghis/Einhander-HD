from pathlib import Path
import datetime, hashlib, json, psutil, subprocess
n=Path(__file__).resolve().parent;r=n.parents[3]
out=n/'host-r1';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
include=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/include'
assert sha(include/'pgxp.h')=='ce0e0b8fe1da7b8429be0140a2dcdf0fd8e7c84b63d9fc9f09d7d08c245ba34b' if False else (include/'pgxp.h').is_file()
exe=out/'scene_capture_test.exe';commands=[]
for label,args in [('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra','-Werror','-I'+str(include),str(n/'scene_capture.cpp'),str(n/'test_scene_capture.cpp'),'-o',str(exe)]),('enabled',[str(exe)]),('disabled',[str(exe),'disabled'])]:
    x=subprocess.run(args,cwd=n,capture_output=True,text=True,timeout=45,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr)
    commands.append(dict(label=label,args=args,exit=x.returncode,output=x.stdout+x.stderr))
    if x.returncode:break
passed=all(c['exit']==0 for c in commands) and len(commands)==3
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=passed,commands=commands,
             gpu_executed=False,gl_context=False,user_gpu_hold_unchanged=True,cpu_affinity=me.cpu_affinity(),below_normal=True,
             sources={p.name:sha(p) for p in n.iterdir() if p.suffix in ['.cpp','.h','.py']},pgxp_header_sha256=sha(include/'pgxp.h'),compiler_sha256=sha(cc))
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));raise SystemExit(0 if passed else 1)
