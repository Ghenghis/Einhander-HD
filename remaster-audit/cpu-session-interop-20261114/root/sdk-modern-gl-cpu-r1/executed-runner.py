"""Compile the private real interop path; execute only early-return CPU contracts."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander');out=n/'sdk-modern-gl-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest();marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes();assert json.loads(hold)['owner']=='user-external-project' and json.loads(hold)['expires_utc'] is None
assert sha(n/'sdk-release-header/remix_c.h')=='e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c'
shutil.copy2(__file__,out/'executed-runner.py');shutil.copy2(n/'sdk_modern_gl_probe.cpp',out/'executed-source.cpp')
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe';exe=out/'sdk-modern-gl.exe';rows=[];passed=True
commands=[('compile',[cc,'-std=c++17','-O1','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers',str(n/'sdk_modern_gl_probe.cpp'),'-o',str(exe),'-luser32','-lgdi32','-lopengl32'],0),('cpu-contract',[str(exe),'--cpu-contract'],0),('cpu-reservation-guard',[str(exe),'--guard-contract'],77)]
for label,args,expected in commands:
    x=subprocess.run(args,cwd=out,capture_output=True,text=True,timeout=30,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr);rows.append(dict(label=label,args=args,exit=x.returncode,expected_exit=expected,output=x.stdout+x.stderr))
    if x.returncode!=expected:passed=False;break
    if label=='cpu-contract':obj=json.loads(x.stdout);assert obj['cpu_contract_checks']==10 and obj['passed'] and not obj['dll_loaded'] and not obj['gl_context']
    if label=='cpu-reservation-guard':obj=json.loads(x.stdout);assert obj['reservation_exists'] and not obj['gpu_started'] and not obj['dll_loaded']
assert marker.read_bytes()==hold
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=passed,commands=rows,source_sha256=sha(n/'sdk_modern_gl_probe.cpp'),header_sha256=sha(n/'sdk-release-header/remix_c.h'),compiler_sha256=sha(cc),executable_sha256=sha(exe) if exe.exists() else None,user_hold_sha256=hashlib.sha256(hold).hexdigest(),user_hold_unchanged=True,gpu_executed=False,renderer_dll_loaded=False,gl_context_created=False,window_created=False,game_loaded=False,cpu_affinity=me.cpu_affinity(),below_normal=True,scope='Actual compiled interop candidate; executed only CPU metadata and reservation contracts. Startup/Submit/Present, external-memory/semaphore imports and image/lifecycle qualification NOT RUN.')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if passed else 1)
