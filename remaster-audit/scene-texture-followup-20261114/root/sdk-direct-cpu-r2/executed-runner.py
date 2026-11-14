"""Compile diagnostic; execute only its early-return CPU layout branch."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess
n=Path(__file__).resolve().parent;r=n.parents[2];out=n/'sdk-direct-cpu-r2';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes();assert json.loads(hold)['owner']=='user-external-project'
sdk=n.parent/'project-completion-20261114/remix-sdk-reference/remix_c.h'
assert sha(sdk)=='a3f40860e643127dfd3bee1afee04a8715704d322a8b16d5bd542852f863501d'
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe';exe=out/'sdk-direct-control.exe'
commands=[];passed=True
for label,args in [('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra',str(n/'sdk_direct_control.cpp'),'-o',str(exe),'-luser32','-lgdi32']),('cpu-schema',[str(exe),'--cpu-schema'])]:
    x=subprocess.run(args,cwd=out,capture_output=True,text=True,timeout=45,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr);commands.append(dict(label=label,args=args,exit=x.returncode,output=x.stdout+x.stderr))
    if x.returncode:passed=False;break
    if label=='cpu-schema':
        schema=json.loads(x.stdout);assert schema['cpu_only'] and schema['vertex_bytes']==64 and schema['sdk_version']=='0.6.11'
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=passed,commands=commands,
             gpu_executed=False,renderer_dll_loaded=False,game_launched=False,user_gpu_hold_unchanged=True,
             source_sha256=sha(n/'sdk_direct_control.cpp'),header_sha256=sha(sdk),cpu_affinity=me.cpu_affinity(),below_normal=True,
             scope='Compile and early-return CPU layout branch only. Native device/readback/lifecycle control remains NOT RUN.')
if exe.exists():receipt['executable_sha256']=sha(exe)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(n/'sdk_direct_control.cpp',out/'executed-source.cpp');shutil.copy2(__file__,out/'executed-runner.py')
print(json.dumps(receipt));raise SystemExit(0 if passed else 1)
