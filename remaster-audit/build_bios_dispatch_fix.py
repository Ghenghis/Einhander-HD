"""Compile newly discovered BIOS entries without rebuilding unchanged routines."""
import ctypes
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

PROJECT = Path('C:/github/Einhander/windows-x64')
BUILD = PROJECT/'build-ss8c'
OUT = Path('C:/github/REMASTER_STAGING/save-fix/bios-seed')
GENERATED = OUT/'generated'
original = PROJECT/'psxrecomp/generated/SCPH1001_full.c'
updated = GENERATED/'SCPH1001_full.c'
baseline = OUT/'before/SCPH1001_full.c'
if not baseline.exists():
    baseline.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(original,baseline)
old_text, new_text = baseline.read_text(), updated.read_text()
pattern = re.compile(r'^void (\w+)\(CPUState\* cpu\)\s*\{', re.M)


def functions(source):
    matches = list(pattern.finditer(source))
    return {m.group(1): source[m.start():matches[i+1].start() if i+1<len(matches) else len(source)].strip()
            for i,m in enumerate(matches)}


old, new = functions(old_text), functions(new_text)
added = sorted(set(new)-set(old))
assert added, 'Regeneration must add a BIOS entry'
assert set(old) <= set(new), 'Existing BIOS entry removed'
changed = [name for name in old if old[name] != new[name]]
assert not changed, 'Existing BIOS routines changed: '+str(changed[:10])
assert 'SCPH1001_func_1FC09800' in added
shard = OUT/'SCPH1001_save_support.c'
shard.write_text(new_text[:next(pattern.finditer(new_text)).start()]+'\n\n'.join(new[n] for n in added)+'\n')


def windows_args(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    values = parse(command, ctypes.byref(count))
    try:return [values[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(values)


def run(arguments, name):
    result = subprocess.run(arguments,cwd=BUILD,capture_output=True,text=True,timeout=180)
    (OUT/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    print(name,'exit',result.returncode,flush=True)
    if result.returncode:
        print((result.stdout+result.stderr)[-4000:]);raise SystemExit(result.returncode)


commands = Path('C:/github/REMASTER_STAGING/stage01_city/evidence/runtime-build-commands.txt').read_text().splitlines()
args = windows_args(next(s for s in commands if s.endswith('/SCPH1001_full.c')))
if Path(args[0]).name.lower()=='ccache.exe':args=args[1:]
args = [a.replace('D:/Games/Einhander/windows-x64/',PROJECT.as_posix()+'/') for a in args]
objects = []
for source in (shard,GENERATED/'SCPH1001_dispatch.c'):
    output = OUT/(source.name+'.obj')
    invocation = list(args)
    invocation[-1] = str(source)
    invocation[invocation.index('-o')+1] = str(output)
    invocation[invocation.index('-MF')+1] = str(output)+'.d'
    run(invocation,'compile-'+source.stem)
    objects.append(output)
response = Path('C:/github/REMASTER_STAGING/full-remaster/devtools-build/devtools-link.rsp').read_text().splitlines()
old_dispatch = '"CMakeFiles/psx-runtime.dir/psxrecomp/generated/SCPH1001_dispatch.c.obj"'
assert response.count(old_dispatch)==1
response[response.index(old_dispatch)] = '"'+objects[1].as_posix()+'"'
old_object = BUILD/'CMakeFiles/psx-runtime.dir/psxrecomp/generated/SCPH1001_full.c.obj'
assert all(n.encode() not in old_object.read_bytes() for n in added), 'Old object already defines a supplement'
response.append('"'+objects[0].as_posix()+'"')
link = OUT/'bios-save-link.rsp';link.write_text('\n'.join(response))
compiler = Path(args[0]).with_name('clang++.exe')
executable = OUT/'Einhander_Recompiled.exe'
run([str(compiler),'-O3','-DNDEBUG','-Wl,--stack,67108864','-mwindows','-static',
     '-static-libgcc','-static-libstdc++','@'+str(link),'-o',str(executable)],'link-bios-save')
report = {'executable':str(executable),'sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
          'new_functions':added,'existing_functions_unchanged':len(old),
          'status':'built; native card-creation verification pending'}
(OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
