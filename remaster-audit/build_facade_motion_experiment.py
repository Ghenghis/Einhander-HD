"""Build a private facade sampler experiment and hidden real-GL regressions.

Uses verified existing linked objects. Never updates a runtime descriptor,
installed executable, candidate pack, settings file, or a running process.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from run_hd_skin_material_test import extract_shader

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'remaster-audit'
SOURCE=ROOT/'windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c'
BASE=Path('C:/github/REMASTER_STAGING/full-remaster/exact-region-build-20261112-v4')
OUTPUT_ROOT=AUDIT/'facade-motion-experiment'
ORIGINAL=OUTPUT_ROOT/'baseline-gpu_gl_renderer.c'
COMPILER=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
BUILD=ROOT/'windows-x64/build-ss8c'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def windows_args(command):
    count=ctypes.c_int();parse=ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)];parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    values=parse(command,ctypes.byref(count))
    try:return [values[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(values)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.parent!=OUTPUT_ROOT.resolve() or out.exists():raise ValueError('Use a fresh run directly under facade-motion-experiment')
    baseline=json.loads((BASE/'build.json').read_bytes())
    if sha(ORIGINAL)!=baseline['source_hashes'][str(SOURCE)]:raise ValueError('Baseline renderer source differs')
    for row in baseline['objects']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Verified baseline object changed')
    pack=ROOT/'windows-x64/psxrecomp/runtime/src/hd_texture_pack.cpp'
    if sha(pack)!=baseline['source_hashes'][str(pack)]:raise ValueError('Pack source changed since verified baseline')
    owned_sources=[SOURCE,AUDIT/'test_facade_motion_gl.c',AUDIT/'test_facade_motion_gl.cpp',Path(__file__)]
    source_hashes={str(path):sha(path) for path in owned_sources}
    material=ROOT/'windows-x64/tools/material-runtime.json';material_before=sha(material)
    out.mkdir();commands=[]
    def run(command,label,timeout=180,env=None):
        result=subprocess.run(command,cwd=BUILD,env=env,capture_output=True,text=True,timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        commands.append(dict(label=label,arguments=command,exit=result.returncode))
        print(label,'exit',result.returncode,flush=True)
        write(out/'commands.json',commands)
        if result.returncode:
            print((result.stdout+result.stderr)[-10000:]);raise SystemExit(result.returncode)
        return result
    renderer_command=next(row['arguments'] for row in baseline['commands'] if row['label']=='compile-experimental-renderer')
    def renderer_object(destination,wrapper=None):
        command=renderer_command.copy()
        command[command.index('-o')+1]=str(destination)
        command[command.index('-MF')+1]=str(destination)+'.d'
        command[-1]=str(wrapper or SOURCE)
        command.insert(-2,'-I'+str(out))
        return command
    ninja=(BUILD/'build.ninja').read_text().splitlines()
    def main_flags():
        index=next(i for i,line in enumerate(ninja) if line.startswith('build CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj:'))
        fields={line.strip().split(' = ',1)[0]:line.split(' = ',1)[1] for line in ninja[index+1:index+15] if ' = ' in line}
        return [value.replace('D:/Games/Einhander/windows-x64/',(ROOT/'windows-x64').as_posix()+'/')
                for value in windows_args('unused '+fields['DEFINES']+' '+fields['FLAGS']+' '+fields['INCLUDES'])[1:]]
    response=(BASE/'exact-region-link.rsp').read_text().splitlines()
    def link(renderer,destination,label,main=None):
        values=response.copy()
        for suffix,replacement in [('/gpu_gl_renderer.c.obj',renderer)]+([('/main.cpp.obj',main)] if main else []):
            matches=[i for i,value in enumerate(values) if value.strip('"').replace('\\','/').endswith(suffix)]
            if len(matches)!=1:raise ValueError('Ambiguous baseline link object '+suffix)
            values[matches[0]]='"'+replacement.as_posix()+'"'
        rsp=out/(label+'.rsp');rsp.write_text('\n'.join(values)+'\n')
        run([str(COMPILER),'-O3','-static','-Wl,--stack,67108864','@'+str(rsp),'-o',str(destination)],label)
        return rsp
    fixture=out/'facade-pack';fixture.mkdir()
    proof=AUDIT/'world-sign-mapping/facade-pilot-source-v2/source-proof'
    key='52F33418-5E9B9AC3'
    mapping=json.loads((proof.parent/'manifest.json').read_bytes())
    expected={Path(row['path']).name:row['sha256'] for row in mapping['source_proof']}
    for suffix in ('words.bin','clut.bin','valid.bin'):
        source=proof/(key+'.'+suffix)
        if sha(source)!=expected[source.name]:raise ValueError('Facade source proof changed')
        (fixture/source.name).write_bytes(source.read_bytes())
    y,x=np.indices((1024,1024));value=np.where((x^y)&1,192,64).astype(np.uint8)
    alpha=np.where(x<341,0,np.where(x<683,127,255)).astype(np.uint8)
    Image.fromarray(np.stack([value,value,value,alpha],axis=-1)).save(fixture/(key+'.png'))
    (fixture/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+key+'\t768\t0\t16\t64\t0\t0\t480\n')
    (out/'facade_baseline_shader.h').write_text('static const char *facade_baseline_hd_fs='+json.dumps(extract_shader(ORIGINAL))+';\n')
    wrapper=out/'renderer-facade-test.c'
    wrapper.write_text('#define HD_RENDERER_SOURCE "'+SOURCE.as_posix()+'"\n#include "'+(AUDIT/'test_facade_motion_gl.c').as_posix()+'"\n')
    test_renderer=out/'facade-test-renderer.obj'
    run(renderer_object(test_renderer,wrapper),'compile-facade-renderer')
    main=out/'facade-main.obj';run([str(COMPILER),*main_flags(),'-c',str(AUDIT/'test_facade_motion_gl.cpp'),'-o',str(main)],'compile-facade-main')
    executable=out/'test-facade-motion.exe';link(test_renderer,executable,'link-facade-test',main)
    env=os.environ.copy()
    for name in ('PSX_LOAD_SLOT','PSXRECOMP_HD_DUMP','PSXRECOMP_HD_TEXTURE_ROOT','PSXRECOMP_SKIN_PROFILE','PSXRECOMP_SKIN_ENEMY_PROFILE','PSXRECOMP_HD_FACADE_MOTION','PSXRECOMP_HD_FACADE_ANISOTROPY'):env.pop(name,None)
    env.update(PSXRECOMP_HD_PAGE_FALLBACK='1',PSXRECOMP_HD_CPU_AUTHORITY='0')
    off=run([str(executable),str(fixture),'0'],'real-gl-default-off',45,env)
    opt_in=dict(env,PSXRECOMP_HD_FACADE_MOTION='1',PSXRECOMP_HD_FACADE_ANISOTROPY='64')
    enabled=run([str(executable),str(fixture),'1'],'real-gl-facade-motion',45,opt_in)
    regression_results={}
    for stem,label,main_object,arguments in [
        ('test_exact_regions_gl','prior-exact-region',BASE/'region-main.obj',[str(BASE/'fixtures/valid')]),
        ('test_gl_hires_capture','prior-hires-capture',BASE/'capture-main.obj',[])]:
        wrapper=out/(label+'.c');wrapper.write_text('#define HD_RENDERER_SOURCE "'+SOURCE.as_posix()+'"\n#include "'+(AUDIT/(stem+'.c')).as_posix()+'"\n')
        renderer=out/(label+'.obj');run(renderer_object(renderer,wrapper),'compile-'+label)
        test_exe=out/(label+'.exe');link(renderer,test_exe,'link-'+label,main_object)
        regression_results[label]=run([str(test_exe),*arguments],label,45,env).stdout
    (out/'hd_alpha_shaders.h').write_text('const char *legacy_hd_fs=R"SHADER('+extract_shader(Path('C:/github/REMASTER_STAGING/three_asset_proof/evidence/gpu_gl_renderer.before.c'))+')SHADER";\nconst char *current_hd_fs=R"SHADER('+extract_shader(SOURCE)+')SHADER";\n')
    alpha_exe=out/'test-hd-alpha.exe'
    run([str(COMPILER),'-O2','-static','-I'+str(out),str(AUDIT/'test_hd_alpha_gpu.cpp'),'-lopengl32','-lgdi32','-luser32','-o',str(alpha_exe)],'compile-prior-alpha')
    regression_results['prior-alpha']=run([str(alpha_exe)],'prior-alpha',45,env).stdout
    renderer=out/'gpu_gl_renderer.c.obj';run(renderer_object(renderer),'compile-experimental-renderer')
    runtime=out/'Einhander_Recompiled.exe';rsp=link(renderer,runtime,'link-experimental-runtime')
    if any(sha(path)!=digest for path,digest in source_hashes.items()):raise ValueError('Source changed during build')
    if sha(material)!=material_before:raise ValueError('Saved runtime descriptor changed')
    report=dict(at_utc=datetime.now(timezone.utc).isoformat(),executable=str(runtime),sha256=sha(runtime),
        source_hashes=source_hashes,baseline_source=dict(path=str(ORIGINAL),sha256=sha(ORIGINAL)),
        baseline_build=dict(path=str(BASE/'build.json'),sha256=sha(BASE/'build.json')),
        objects=[dict(path=str(renderer),sha256=sha(renderer))]+[row for row in baseline['objects'] if row['path'].endswith('hd_texture_pack.cpp.obj') or 'SCPH1001' in row['path']],
        bios_entries=baseline['bios_entries'],link_response=str(rsp),link_response_sha256=sha(rsp),link_exit=0,
        tests=dict(default_off=off.stdout,facade_motion=enabled.stdout,**regression_results),commands=commands,
        global_runtime_installed=False,game_launched=False,saved_material_receipt_unchanged=True,
        opt_in_environment={'PSXRECOMP_HD_FACADE_MOTION':'1','PSXRECOMP_HD_FACADE_ANISOTROPY':'8'},
        scope='Hidden synthetic real-GL sampling tests; authored facade/live motion acceptance remains pending')
    write(out/'build.json',report)
    print(json.dumps(dict(output=str(out),executable=str(runtime),sha256=report['sha256'],global_runtime_installed=False)))

if __name__=='__main__':main()
