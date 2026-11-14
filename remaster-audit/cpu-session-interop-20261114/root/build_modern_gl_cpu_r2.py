"""Isolate syntax/object/link after the preserved driver timeout. Never executes the GPU branch."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess,time
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander');out=n/'sdk-modern-gl-cpu-r2';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes();assert json.loads(hold)['owner']=='user-external-project' and json.loads(hold)['expires_utc'] is None
r1=n/'sdk-modern-gl-cpu-r1';late=r1/'sdk-modern-gl.exe';(r1/'failure.json').write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='combined compile/link driver',status='FAIL: subprocess.TimeoutExpired after30s',compiler_exit_observed=False,cpu_contracts='NOT RUN',gpu_executed=False,renderer_dll_loaded=False,late_executable_exists=late.exists(),late_executable_sha256=sha(late) if late.exists() else None,late_executable_accepted=False,child_inventory='Scoped follow-up found no remaining compiler/linker with owned source/output command line; the PowerShell inventory command matched itself only.'),indent=2)+'\n')
shutil.copy2(__file__,out/'executed-runner.py');shutil.copy2(n/'sdk_modern_gl_probe.cpp',out/'executed-source.cpp')
assert sha(n/'sdk-release-header/remix_c.h')=='e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c'
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe';obj=out/'probe.obj';exe=out/'sdk-modern-gl.exe';src=n/'sdk_modern_gl_probe.cpp';rows=[];passed=True
flags=[cc,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers']
commands=[('syntax',flags+['-fsyntax-only','-v',str(src)],0,45),('compile-object',flags+['-O0','-c',str(src),'-o',str(obj)],0,60),('link',[cc,str(obj),'-o',str(exe),'-luser32','-lgdi32','-lopengl32'],0,45),('cpu-contract',[str(exe),'--cpu-contract'],0,10),('cpu-reservation-guard',[str(exe),'--guard-contract'],77,10)]
for label,args,expected,limit in commands:
    started=time.monotonic();timed=False;terminated=[]
    with (out/(label+'.log')).open('w') as stream:
        child=subprocess.Popen(args,cwd=out,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x4000)
        try:code=child.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timed=True
            try:
                proc=psutil.Process(child.pid)
                for sub in proc.children(recursive=True):
                    try:terminated.append(sub.pid);sub.kill()
                    except psutil.NoSuchProcess:pass
                proc.kill()
            except psutil.NoSuchProcess:pass
            code=child.wait(timeout=5)
    output=(out/(label+'.log')).read_text();row=dict(label=label,args=args,pid=child.pid,exit=code,expected_exit=expected,timed_out=timed,terminated_owned_descendants=terminated,seconds=round(time.monotonic()-started,3),output=output);rows.append(row)
    print(json.dumps(dict(label=label,exit=code,timed_out=timed,seconds=row['seconds'],output_tail=output[-2000:])),flush=True)
    if timed or code!=expected:passed=False;break
    if label=='cpu-contract':a=json.loads(output);assert a['cpu_contract_checks']==10 and a['passed'] and not a['dll_loaded'] and not a['gl_context']
    if label=='cpu-reservation-guard':a=json.loads(output);assert a['reservation_exists'] and not a['gpu_started'] and not a['dll_loaded']
assert marker.read_bytes()==hold
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=passed,commands=rows,source_sha256=sha(src),header_sha256=sha(n/'sdk-release-header/remix_c.h'),compiler_sha256=sha(cc),executable_sha256=sha(exe) if exe.exists() else None,object_sha256=sha(obj) if obj.exists() else None,user_hold_sha256=hashlib.sha256(hold).hexdigest(),user_hold_unchanged=True,gpu_executed=False,renderer_dll_loaded=False,gl_context_created=False,window_created=False,game_loaded=False,cpu_affinity=me.cpu_affinity(),below_normal=True,optimization='O0 diagnostic',scope='Only CPU contracts execute; Startup/Submit/Present, external-memory/timeline semaphores and final image/lifecycle remain NOT RUN.')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='commands'}));raise SystemExit(0 if passed else 1)
