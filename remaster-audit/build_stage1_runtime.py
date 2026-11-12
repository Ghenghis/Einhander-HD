"""Compile changed renderer and relink existing local objects into a new test EXE.

No CMake cache rewrites, source relocation, downloads, or installed EXE replacement.
"""
import ctypes
import json
import subprocess
from pathlib import Path

PROJECT=Path('C:/github/Einhander/windows-x64')
BUILD=PROJECT/'build-ss8c'
ROOT=Path('C:/github/REMASTER_STAGING/stage01_city')
OUT=ROOT/'build'
OUT.mkdir(exist_ok=True)
EVIDENCE=ROOT/'evidence'

def windows_args(command):
    count=ctypes.c_int()
    parse=ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    values=parse(command,ctypes.byref(count))
    try:return [values[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(values)

def run(args,name):
    result=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=120)
    (EVIDENCE/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    print(name,'exit',result.returncode,flush=True)
    if result.returncode:
        print((result.stdout+result.stderr)[-6000:])
        raise SystemExit(result.returncode)

command=(EVIDENCE/'renderer-build-command.txt').read_text(encoding='utf-8')
args=windows_args(command)
# Drop ccache while preserving the exact cached compile flags/definitions.
if Path(args[0]).name.lower()=='ccache.exe':args=args[1:]
args=[a.replace('D:/Games/Einhander/windows-x64/','C:/github/Einhander/windows-x64/') for a in args]
renderer=OUT/'gpu_gl_renderer.c.obj'
args[args.index('-o')+1]=str(renderer)
args[args.index('-MF')+1]=str(OUT/'gpu_gl_renderer.c.obj.d')
run(args,'compile-stage1-renderer')
gpu=OUT/'gpu.c.obj'
gpu_args=[a.replace('gpu_gl_renderer.c','gpu.c') for a in args]
gpu_args[gpu_args.index('-o')+1]=str(gpu)
gpu_args[gpu_args.index('-MF')+1]=str(OUT/'gpu.c.obj.d')
run(gpu_args,'compile-stage1-gpu')

lines=(BUILD/'build.ninja').read_text().splitlines()
index=next(i for i,s in enumerate(lines) if s.startswith('build Einhander_Recompiled.exe:'))
line=lines[index]
inputs=line.split('CXX_EXECUTABLE_LINKER__psx-runtime_Release ',1)[1].split(' | ',1)[0].split(' || ',1)[0].split()
objects=[s.replace('$:',':').replace('$ ',' ') for s in inputs]
old='CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/gpu_gl_renderer.c.obj'
assert old in objects
objects=[str(renderer) if s==old else s for s in objects]
old_gpu='CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/gpu.c.obj'
assert old_gpu in objects
objects=[str(gpu) if s==old_gpu else s for s in objects]
missing=[s for s in objects if not (Path(s).is_absolute() and Path(s).exists()) and not (BUILD/s).exists()]
if missing:raise RuntimeError('Missing cached objects: '+str(missing[:12]))
libraries=next(s.split(' = ',1)[1] for s in lines[index+1:index+15] if s.startswith('  LINK_LIBRARIES ='))
libraries=windows_args('unused '+libraries)[1:]
response=OUT/'stage1-link.rsp'
response.write_text('\n'.join('"'+s.replace('\\','/')+'"' for s in objects+libraries),encoding='utf-8')
compiler='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
executable=OUT/'Einhander_Stage1.exe'
run([compiler,'-O3','-DNDEBUG','-Wl,--stack,67108864','-mwindows','-static','-static-libgcc','-static-libstdc++',
     '@'+str(response),'-o',str(executable)],'link-stage1-runtime')
print(json.dumps({'executable':str(executable),'bytes':executable.stat().st_size,'scope':'New isolated runtime; installed executable unchanged'},indent=2),flush=True)
