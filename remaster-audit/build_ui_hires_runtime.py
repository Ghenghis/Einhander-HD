"""Build the devtools changes with the existing local compiler and objects."""
import ctypes
import hashlib
import json
import runpy
import re
import sys
import subprocess
from pathlib import Path

PROJECT = Path('C:/github/Einhander/windows-x64')
BUILD = PROJECT/'build-ss8c'
OUT = Path('C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112')
OUT.mkdir(parents=True, exist_ok=False)


def shader_macro(path, name):
    lines = path.read_text(encoding='utf-8').splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('#define '+name+' '))
    fragments = []
    for line in lines[start+1:]:
        fragments.extend(json.loads(token) for token in re.findall(r'"(?:\\.|[^"\\])*"', line))
        if not line.rstrip().endswith('\\'):
            break
    return ''.join(fragments)


material_header = PROJECT/'psxrecomp/runtime/src/hd_skin_material.h'
detail_header = PROJECT/'psxrecomp/runtime/src/hd_skin_detail.h'
if False:  # Candidate build must not rewrite shared shader kernels
    (PROJECT/'tools/material-shader-kernels.json').write_text(json.dumps({
        'palette': shader_macro(material_header, 'HD_SKIN_MATERIAL_GLSL'),
        'detail': shader_macro(detail_header, 'HD_SKIN_DETAIL_GLSL'),
        'palette_sha256': hashlib.sha256(material_header.read_bytes()).hexdigest(),
        'detail_sha256': hashlib.sha256(detail_header.read_bytes()).hexdigest(),
        'scope': 'Exact renderer GLSL shared by the WebGL atlas review'
    }, indent=2)+'\n', encoding='utf-8')

if '--kernels-only' in sys.argv:
    print('Shared material shader kernels exported.')
    raise SystemExit(0)


def windows_args(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    values = parse(command, ctypes.byref(count))
    try:
        return [values[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(values)


def run(arguments, name):
    result = subprocess.run(arguments, cwd=BUILD, capture_output=True, text=True, timeout=180)
    (OUT/(name+'.log')).write_text(result.stdout+result.stderr, encoding='utf-8')
    print(name, 'exit', result.returncode, flush=True)
    if result.returncode:
        print((result.stdout+result.stderr)[-6000:])
        raise SystemExit(result.returncode)


commands = Path('C:/github/REMASTER_STAGING/stage01_city/evidence/runtime-build-commands.txt').read_text().splitlines()
original = next(s for s in commands if s.endswith('/launcher_imgui.cpp'))
arguments = windows_args(original)
if Path(arguments[0]).name.lower() == 'ccache.exe':
    arguments = arguments[1:]
arguments = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix()+'/') for s in arguments]
compiler = arguments[0]
objects = {}
for name in ('launcher_imgui', 'launcher_devtools'):
    args = [s.replace('launcher_imgui.cpp', name+'.cpp') for s in arguments]
    output = OUT/(name+'.cpp.obj')
    args[args.index('-o')+1] = str(output)
    args[args.index('-MF')+1] = str(output)+'.d'
    run(args, 'compile-'+name)
    objects[name] = output

# The model owns the console profile (including which settings panels exist).
model_command = next(s for s in commands if s.endswith('/launcher_model.c'))
model_args = windows_args(model_command)
if Path(model_args[0]).name.lower() == 'ccache.exe':
    model_args = model_args[1:]
model_args = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix()+'/') for s in model_args]
model_output = OUT/'launcher_model.c.obj'
model_args[model_args.index('-o')+1] = str(model_output)
model_args[model_args.index('-MF')+1] = str(model_output)+'.d'
run(model_args, 'compile-launcher_model')

# Rebuild the current renderer as well; cached objects cannot substantiate a
# material-shader change. Preserve the known-good runtime compile definitions.
renderer_command = Path('C:/github/REMASTER_STAGING/stage01_city/evidence/renderer-build-command.txt').read_text(encoding='utf-8')
renderer_args = windows_args(renderer_command)
if Path(renderer_args[0]).name.lower() == 'ccache.exe':
    renderer_args = renderer_args[1:]
renderer_args = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix()+'/') for s in renderer_args]
renderer_output = OUT/'gpu_gl_renderer.c.obj'
renderer_args[renderer_args.index('-o')+1] = str(renderer_output)
renderer_args[renderer_args.index('-MF')+1] = str(renderer_output)+'.d'
run(renderer_args, 'compile-material-renderer')

# Debug commands must be linked from the current source, not the old cached
# server object. This includes live material control and research recording.
debug_command = next(s for s in commands if s.endswith('/debug_server.c'))
debug_args = windows_args(debug_command)
if Path(debug_args[0]).name.lower() == 'ccache.exe':
    debug_args = debug_args[1:]
debug_args = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix()+'/') for s in debug_args]
debug_output = OUT/'debug_server.c.obj'
debug_args[debug_args.index('-o')+1] = str(debug_output)
debug_args[debug_args.index('-MF')+1] = str(debug_output)+'.d'
run(debug_args, 'compile-debug-server')

# The previous verified runtime link response includes the fixed GPU objects.
response = Path('C:/github/REMASTER_STAGING/stage01_city/build/stage1-link.rsp').read_text().splitlines()
old = '"CMakeFiles/psx-runtime.dir/recomp-ui/src/common/backends/imgui/launcher_imgui.cpp.obj"'
assert response.count(old) == 1
response[response.index(old)] = '"'+objects['launcher_imgui'].as_posix()+'"'
old_model = '"CMakeFiles/psx-runtime.dir/recomp-ui/src/common/launcher_model.c.obj"'
assert response.count(old_model) == 1
response[response.index(old_model)] = '"'+model_output.as_posix()+'"'
renderer_entries = [i for i, entry in enumerate(response) if entry.strip('"').replace('\\', '/').endswith('/gpu_gl_renderer.c.obj')]
assert len(renderer_entries) == 1, 'Expected exactly one renderer object in the verified link response'
response[renderer_entries[0]] = '"'+renderer_output.as_posix()+'"'
debug_entries = [i for i, entry in enumerate(response) if entry.strip('"').replace('\\', '/').endswith('/debug_server.c.obj')]
assert len(debug_entries) == 1, 'Expected exactly one debug-server object in the verified link response'
response[debug_entries[0]] = '"'+debug_output.as_posix()+'"'
response.append('"'+objects['launcher_devtools'].as_posix()+'"')
link = OUT/'devtools-link.rsp'
link.write_text('\n'.join(response), encoding='utf-8')
executable = OUT/'Einhander_Recompiled.exe'
run([compiler, '-O3', '-DNDEBUG', '-Wl,--stack,67108864', '-mwindows', '-static',
     '-static-libgcc', '-static-libstdc++', '@'+str(link), '-o', str(executable)], 'link-devtools')
(OUT/'build.json').write_text(json.dumps({'executable': str(executable),
    'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
    'status': 'built; runtime verification pending'}, indent=2)+'\n')
if False:  # Candidate build must not rewrite saved material-runtime receipt
    material_catalog = runpy.run_path(str(PROJECT/'tools/material_profiles.py'))
    (PROJECT/'tools/material-runtime.json').write_text(json.dumps({
        'schema_version': 1, 'contract': material_catalog['CONTRACT'], 'material_shader': True,
        'dual_profiles': True,
        'detail_maps': detail_header.is_file(),
        'profiles': [row['id'] for row in material_catalog['PROFILES']],
        'player_keys': list(material_catalog['PLAYER_KEYS']),
        'enemy_keys': list(material_catalog['ENEMY_KEYS']),
        'executable': str(executable),
        'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        'verification': 'compiled and linked; gameplay appearance remains unverified'
    }, indent=2)+'\n', encoding='utf-8')
print(executable, flush=True)
