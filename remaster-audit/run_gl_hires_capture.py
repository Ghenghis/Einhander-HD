"""Build a hidden real-GL capture regression; never start or address a game."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'windows-x64'
BUILD=PROJECT/'build-ss8c'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
OUT=args.output.resolve()
if OUT.exists():raise ValueError('Use a new output directory to preserve earlier results')
OUT.mkdir(parents=True)

def windows_args(command):
    count=ctypes.c_int()
    parse=ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    values=parse(command,ctypes.byref(count))
    try:return [values[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(values)

def run(arguments,label,timeout=120,env=None):
    result=subprocess.run(arguments,cwd=BUILD,env=env,capture_output=True,text=True,timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    print(label,'exit',result.returncode,flush=True)
    if result.returncode:print((result.stdout+result.stderr)[-6000:],flush=True)
    return result

def must_run(arguments,label,**kwargs):
    result=run(arguments,label,**kwargs)
    if result.returncode:raise SystemExit(result.returncode)
    return result

lines=(BUILD/'build.ninja').read_text().splitlines()
index=next(i for i,line in enumerate(lines) if line.startswith('build CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj:'))
fields={line.strip().split(' = ',1)[0]:line.split(' = ',1)[1] for line in lines[index+1:index+15] if ' = ' in line}
compiler=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
flags=windows_args('unused '+fields['DEFINES']+' '+fields['FLAGS']+' '+fields['INCLUDES'])[1:]
flags=[s.replace('D:/Games/Einhander/windows-x64/',PROJECT.as_posix()+'/') for s in flags]
main_obj=OUT/'hires-main.obj'
main_source=Path(__file__).with_name('test_gl_hires_capture.cpp')
must_run([str(compiler),*flags,'-c',str(main_source),'-o',str(main_obj)],'compile-main')

renderer_source=PROJECT/'psxrecomp/runtime/src/gpu_gl_renderer.c'
renderer_args=windows_args(Path('C:/github/REMASTER_STAGING/stage01_city/evidence/renderer-build-command.txt').read_text())
if Path(renderer_args[0]).name.lower()=='ccache.exe':renderer_args=renderer_args[1:]
renderer_args=[s.replace('D:/Games/Einhander/windows-x64/',PROJECT.as_posix()+'/') for s in renderer_args]
renderer_obj=OUT/'gpu_gl_renderer.c.obj'
renderer_args[renderer_args.index('-o')+1]=str(renderer_obj)
renderer_args[renderer_args.index('-MF')+1]=str(renderer_obj)+'.d'
wrapper=OUT/'renderer-test.c'
wrapper.write_text('#define HD_RENDERER_SOURCE "'+renderer_source.as_posix()+'"\n#include "'+Path(__file__).with_name('test_gl_hires_capture.c').as_posix()+'"\n',encoding='utf-8')
renderer_args[-1]=str(wrapper)
renderer_args.insert(-2,'-I'+str(PROJECT/'psxrecomp/runtime/src'))
must_run(renderer_args,'compile-renderer')

response=Path('C:/github/REMASTER_STAGING/stage01_city/build/stage1-link.rsp').read_text()
old_main='"CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj"'
assert response.count(old_main)==1
response=response.replace(old_main,'"'+main_obj.as_posix()+'"')
old_renderer='"C:/github/REMASTER_STAGING/stage01_city/build/gpu_gl_renderer.c.obj"'
assert response.count(old_renderer)==1
response=response.replace(old_renderer,'"'+renderer_obj.as_posix()+'"')
rsp=OUT/'link.rsp';rsp.write_text(response,encoding='utf-8')
exe=OUT/'hires-capture.exe'
must_run([str(compiler),'-O3','-static','-Wl,--stack,67108864','@'+str(rsp),'-o',str(exe)],'link')
environment=os.environ.copy()
environment.update(PSXRECOMP_HD_CPU_AUTHORITY='0')
for key in ['PSX_LOAD_SLOT','PSX_HLE_SCHEDULER','PSXRECOMP_HD_TEXTURE_ROOT','PSXRECOMP_HD_DUMP']:
    environment.pop(key,None)
result=run([str(exe)],'real-gl-regression',timeout=40,env=environment)
print(result.stdout,flush=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(at_utc=datetime.now(timezone.utc).isoformat(),renderer_source=str(renderer_source),renderer_sha256=sha(renderer_source),
            harness_c_sha256=sha(Path(__file__).with_name('test_gl_hires_capture.c')),harness_cpp_sha256=sha(main_source),
            executable=str(exe),executable_sha256=sha(exe),exit_code=result.returncode,output=result.stdout,
            scope='Hidden isolated GL fixture; no game process or bridge inputs')
(OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
raise SystemExit(result.returncode)
