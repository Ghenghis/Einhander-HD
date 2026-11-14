from pathlib import Path
import datetime, hashlib, json, psutil, shutil, subprocess
n=Path(__file__).resolve().parent;r=n.parents[3]
out=n/'host-r7';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
include=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/include'
assert sha(include/'pgxp.h')=='1f50599f51a53fdc989d1d0bb9c7aea46f0f6cc53b303048367c0f05b18c4c47'
exe=out/'scene_capture_test.exe';commands=[]
for p in n.iterdir():
    if p.suffix in ['.cpp','.h','.py']:shutil.copy2(p,out/p.name)
for label,args in [('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra','-Werror','-Wno-comment','-I'+str(include),str(n/'scene_capture.cpp'),str(n/'scene_json.cpp'),str(n/'test_scene_capture.cpp'),'-o',str(exe)]),('enabled',[str(exe)]),('disabled',[str(exe),'disabled'])]:
    x=subprocess.run(args,cwd=n,capture_output=True,text=True,timeout=45,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr)
    commands.append(dict(label=label,args=args,exit=x.returncode,output='\n'.join(l for l in (x.stdout+x.stderr).splitlines() if not l.startswith('RECORD '))))
    if label=='enabled' and x.returncode==0:
        packet=json.loads(next(l[7:] for l in x.stdout.splitlines() if l.startswith('RECORD ')))
        assert packet['word_sources']==[0x1000+j*4 for j in range(12)]
        assert packet['indices']==[0,1,2,2,1,3] and packet['geometry_qualified']
        assert packet['material']==dict(clut=0x3210,tpage=0x1e5,depth=3,blend=3,raw=0,semi=0,window=0xabcde,set_mask=1,check_mask=1)
        assert len(packet['vertices'])==4 and all(v['source_frame']==101 and len(v['combined_rt'])==9 and len(v['rtp_seq_hex'])==16 for v in packet['vertices'])
        (out/'record.json').write_text(json.dumps(packet,indent=2)+'\n')
    if x.returncode:break
passed=all(c['exit']==0 for c in commands) and len(commands)==3
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=passed,commands=commands,
             gpu_executed=False,gl_context=False,user_gpu_hold_unchanged=True,cpu_affinity=me.cpu_affinity(),below_normal=True,
             sources={p.name:sha(p) for p in n.iterdir() if p.suffix in ['.cpp','.h','.py']},pgxp_header_sha256=sha(include/'pgxp.h'),compiler_sha256=sha(cc))
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));raise SystemExit(0 if passed else 1)
