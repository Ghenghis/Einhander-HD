"""Extract actual runtime shader strings, compile a hidden real-GPU check."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from run_hd_skin_material_test import extract_shader

ROOT=Path('C:/github/Einhander/remaster-audit')
OUT=Path('C:/github/REMASTER_STAGING/three_asset_proof/shader-test')
OUT.mkdir(exist_ok=True)
paths=[Path('C:/github/REMASTER_STAGING/three_asset_proof/evidence/gpu_gl_renderer.before.c'),
       Path('C:/github/Einhander/windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c')]
parts=[]
for label,path in zip(['legacy','current'],paths):
    shader=extract_shader(path)
    (OUT/(label+'.frag')).write_text(shader)
    parts.append(f'const char *{label}_hd_fs=R"SHADER({shader})SHADER";\n')
(OUT/'hd_alpha_shaders.h').write_text(''.join(parts))
compiler='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
args=[compiler,'-O2','-static','-I'+str(OUT),str(ROOT/'test_hd_alpha_gpu.cpp'),'-lopengl32','-lgdi32','-luser32','-o',str(OUT/'test_hd_alpha_gpu.exe')]
compiled=subprocess.run(args,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:
    print(compiled.stdout+compiled.stderr);raise SystemExit(compiled.returncode)
result=subprocess.run([str(OUT/'test_hd_alpha_gpu.exe')],capture_output=True,text=True,timeout=30)
(OUT/'result.log').write_text(result.stdout+result.stderr)
print(result.stdout+result.stderr)
if not result.returncode:
    report=json.loads(result.stdout)
    report.update(source=str(paths[1]),source_sha256=hashlib.sha256(paths[1].read_bytes()).hexdigest(),compile_exit=compiled.returncode,test_exit=result.returncode)
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(result.returncode)
