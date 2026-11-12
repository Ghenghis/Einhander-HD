"""Build/test an isolated exact-region runtime; no game process or installation."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zlib
from PIL import Image
from run_hd_skin_material_test import extract_shader

ROOT=Path(__file__).resolve().parent.parent
PROJECT=ROOT/'windows-x64'
BUILD=PROJECT/'build-ss8c'
BASE=Path('C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112-v3')
TOOLS=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def windows_args(command):
    count=ctypes.c_int();parse=ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)];parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    values=parse(command,ctypes.byref(count))
    try:return [values[i] for i in range(count.value)]
    finally:ctypes.windll.kernel32.LocalFree(values)

def fixture_pack(path,values=(0x001f,0x03e0)):
    path.mkdir();rows=[]
    for value in values:
        raw=struct.pack('<H',value)*(64*256);key=f'{zlib.crc32(raw):08X}-00000000'
        Image.new('RGBA',(1024,4096),(32,192,64,127)).save(path/(key+'.png'))
        (path/(key+'.words.bin')).write_bytes(raw);(path/(key+'.valid.bin')).write_bytes(b'\1'*(64*256));(path/(key+'.clut.bin')).write_bytes(b'')
        rows.append(f'{key} 448 256 64 256 2 0 0')
    raw=struct.pack('<H',0x1111)*(16*8);palette=struct.pack('<16H',*[i*32+1 for i in range(16)])
    key=f'{zlib.crc32(raw):08X}-{zlib.crc32(palette):08X}'
    Image.new('RGBA',(1024,128),(32,192,64,127)).save(path/(key+'.png'))
    (path/(key+'.words.bin')).write_bytes(raw);(path/(key+'.valid.bin')).write_bytes(b'\1'*(16*8));(path/(key+'.clut.bin')).write_bytes(palette)
    rows.append(f'{key} 800 0 16 8 0 800 500')
    (path/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+'\n'.join(rows)+'\n');return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    material=PROJECT/'tools/material-runtime.json';before=sha(material)
    sources=[PROJECT/'psxrecomp/runtime/src/gpu_gl_renderer.c',PROJECT/'psxrecomp/runtime/src/hd_texture_pack.cpp',PROJECT/'psxrecomp/runtime/include/hd_texture_pack.h',PROJECT/'psxrecomp/runtime/src/hd_research_renderer.h',PROJECT/'psxrecomp/runtime/src/hd_native_page.h']
    source_hashes={str(p):sha(p) for p in sources}
    for name in ('test_exact_regions.cpp','test_exact_regions_gl.c','test_exact_regions_gl.cpp','test_gl_hires_capture.c','test_gl_hires_capture.cpp','test_hd_alpha_gpu.cpp'):
        source_hashes[str(ROOT/'remaster-audit'/name)]=sha(ROOT/'remaster-audit'/name)
    commands=[]
    def run(command,label,timeout=180,env=None):
        result=subprocess.run(command,cwd=BUILD,env=env,capture_output=True,text=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        commands.append({'label':label,'arguments':command,'exit':result.returncode});print(label,'exit',result.returncode,flush=True)
        if result.returncode:print((result.stdout+result.stderr)[-10000:]);raise SystemExit(result.returncode)
        return result
    fixtures=out/'fixtures';fixtures.mkdir();rows=fixture_pack(fixtures/'valid')
    for bad in ('invalid','crc','duplicate','overlap','missing','depth','palette'):
        path=fixtures/bad;shutil.copytree(fixtures/'valid',path);key=rows[0].split()[0]
        if bad=='invalid':(path/(key+'.valid.bin')).write_bytes(b'\0'+b'\1'*(64*256-1))
        elif bad=='crc':(path/(key+'.words.bin')).write_bytes(b'\0\0'+(path/(key+'.words.bin')).read_bytes()[2:])
        elif bad=='duplicate':(path/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+rows[0]+'\n'+rows[0]+'\n')
        elif bad=='overlap':(path/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+rows[0]+'\n'+rows[1].replace('448 256','449 256')+'\n')
        elif bad=='missing':(path/(key+'.png')).unlink()
        elif bad=='depth':(path/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+rows[0].replace('256 2 0 0','256 3 0 0')+'\n')
        elif bad=='palette':(path/(key+'.clut.bin')).write_bytes(b'\1\0')
    compiler=TOOLS/'clang++.exe'
    unit=out/'test-exact-regions.exe'
    run([str(compiler),'-std=c++17','-O2','-static','-DHD_TEXTURE_PACK_DISABLE_PNG_DECODE','-I'+str(PROJECT/'psxrecomp/runtime/include'),str(ROOT/'remaster-audit/test_exact_regions.cpp'),str(sources[1]),'-o',str(unit)],'compile-unit')
    unit_result=run([str(unit),str(fixtures)],'native-region-tests',40)
    ninja=(BUILD/'build.ninja').read_text().splitlines()
    def flags(target):
        index=next(i for i,line in enumerate(ninja) if line.startswith('build CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/'+target+'.obj:'))
        fields={line.strip().split(' = ',1)[0]:line.split(' = ',1)[1] for line in ninja[index+1:index+15] if ' = ' in line}
        values=windows_args('unused '+fields['DEFINES']+' '+fields['FLAGS']+' '+fields['INCLUDES'])[1:]
        return [v.replace('D:/Games/Einhander/windows-x64/',PROJECT.as_posix()+'/') for v in values]
    pack_obj=out/'hd_texture_pack.cpp.obj';run([str(compiler),*flags('hd_texture_pack.cpp'),'-c',str(sources[1]),'-o',str(pack_obj)],'compile-pack')
    main_obj=out/'region-main.obj';run([str(compiler),*flags('main.cpp'),'-c',str(ROOT/'remaster-audit/test_exact_regions_gl.cpp'),'-o',str(main_obj)],'compile-gl-main')
    renderer_args=windows_args(Path('C:/github/REMASTER_STAGING/stage01_city/evidence/renderer-build-command.txt').read_text())
    if Path(renderer_args[0]).name.lower()=='ccache.exe':renderer_args=renderer_args[1:]
    renderer_args=[v.replace('D:/Games/Einhander/windows-x64/',PROJECT.as_posix()+'/') for v in renderer_args]
    def renderer_object(destination,wrapper=None):
        command=renderer_args.copy();command[command.index('-o')+1]=str(destination);command[command.index('-MF')+1]=str(destination)+'.d'
        command[-1]=str(wrapper or sources[0]);command.insert(-2,'-I'+str(PROJECT/'psxrecomp/runtime/src'))
        return command
    wrapper=out/'renderer-region-test.c';wrapper.write_text('#define HD_RENDERER_SOURCE "'+sources[0].as_posix()+'"\n#include "'+(ROOT/'remaster-audit/test_exact_regions_gl.c').as_posix()+'"\n')
    gl_renderer=out/'region-test-renderer.obj';run(renderer_object(gl_renderer,wrapper),'compile-gl-renderer')
    baseline=json.loads((BASE/'build.json').read_text());assert baseline['bios_entries']==['SCPH1001_func_1FC09800','SCPH1001_func_1FC0980C']
    for row in baseline['objects']:assert sha(row['path'])==row['sha256']
    response=(BASE/'hires-title-bios-link.rsp').read_text().splitlines()
    def response_for(renderer,main=None):
        values=response.copy()
        for suffix,replacement in [('/gpu_gl_renderer.c.obj',renderer),('/hd_texture_pack.cpp.obj',pack_obj)]+([('/main.cpp.obj',main)] if main else []):
            matches=[i for i,v in enumerate(values) if v.strip('"').replace('\\','/').endswith(suffix)]
            assert len(matches)==1,(suffix,matches);values[matches[0]]='"'+replacement.as_posix()+'"'
        return values
    gl_rsp=out/'region-gl-link.rsp';gl_rsp.write_text('\n'.join(response_for(gl_renderer,main_obj))+'\n')
    gl_exe=out/'test-exact-regions-gl.exe';run([str(compiler),'-O3','-static','-Wl,--stack,67108864','@'+str(gl_rsp),'-o',str(gl_exe)],'link-gl')
    env=os.environ.copy()
    for name in ('PSX_LOAD_SLOT','PSXRECOMP_HD_DUMP','PSXRECOMP_HD_TEXTURE_ROOT','PSXRECOMP_SKIN_PROFILE','PSXRECOMP_SKIN_ENEMY_PROFILE'):env.pop(name,None)
    env.update(PSXRECOMP_HD_PAGE_FALLBACK='1',PSXRECOMP_HD_CPU_AUTHORITY='0')
    gl_result=run([str(gl_exe),str(fixtures/'valid')],'real-gl-region-tests',40,env)
    capture_main=out/'capture-main.obj';run([str(compiler),*flags('main.cpp'),'-c',str(ROOT/'remaster-audit/test_gl_hires_capture.cpp'),'-o',str(capture_main)],'compile-prior-capture-main')
    capture_wrapper=out/'renderer-capture-test.c';capture_wrapper.write_text('#define HD_RENDERER_SOURCE "'+sources[0].as_posix()+'"\n#include "'+(ROOT/'remaster-audit/test_gl_hires_capture.c').as_posix()+'"\n')
    capture_renderer=out/'capture-test-renderer.obj';run(renderer_object(capture_renderer,capture_wrapper),'compile-prior-capture-renderer')
    capture_rsp=out/'prior-capture-link.rsp';capture_rsp.write_text('\n'.join(response_for(capture_renderer,capture_main))+'\n')
    capture_exe=out/'test-prior-hires-capture.exe';run([str(compiler),'-O3','-static','-Wl,--stack,67108864','@'+str(capture_rsp),'-o',str(capture_exe)],'link-prior-capture')
    capture_result=run([str(capture_exe)],'prior-hires-capture-regression',40,env)
    legacy=Path('C:/github/REMASTER_STAGING/three_asset_proof/evidence/gpu_gl_renderer.before.c')
    shader_header=out/'hd_alpha_shaders.h'
    shader_header.write_text('const char *legacy_hd_fs=R"SHADER('+extract_shader(legacy)+')SHADER";\nconst char *current_hd_fs=R"SHADER('+extract_shader(sources[0])+')SHADER";\n')
    alpha_exe=out/'test-hd-alpha.exe';run([str(compiler),'-O2','-static','-I'+str(out),str(ROOT/'remaster-audit/test_hd_alpha_gpu.cpp'),'-lopengl32','-lgdi32','-luser32','-o',str(alpha_exe)],'compile-prior-alpha')
    alpha_result=run([str(alpha_exe)],'prior-alpha-class-regression',40,env)
    renderer=out/'gpu_gl_renderer.c.obj';run(renderer_object(renderer),'compile-experimental-renderer')
    rsp=out/'exact-region-link.rsp';rsp.write_text('\n'.join(response_for(renderer))+'\n')
    executable=out/'Einhander_Recompiled.exe';run([str(compiler),'-O3','-DNDEBUG','-mwindows','-static','-static-libgcc','-static-libstdc++','-Wl,--stack,67108864','@'+str(rsp),'-o',str(executable)],'link-experimental-runtime')
    assert all(sha(p)==digest for p,digest in source_hashes.items()),'Source changed during build'
    assert sha(material)==before,'Saved runtime descriptor changed'
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'executable':str(executable),'sha256':sha(executable),'source_hashes':source_hashes,
            'objects':[{'path':str(p),'sha256':sha(p)} for p in (renderer,pack_obj)]+[r for r in baseline['objects'] if 'SCPH1001' in r['path']],
            'bios_entries':baseline['bios_entries'],'baseline_build_receipt':{'path':str(BASE/'build.json'),'sha256':sha(BASE/'build.json')},
            'native_tests':unit_result.stdout,'gl_tests':gl_result.stdout,'prior_capture_tests':capture_result.stdout,'prior_alpha_tests':alpha_result.stdout,'commands':commands,
            'link_response':str(rsp),'link_response_sha256':sha(rsp),'link_exit':0,'global_runtime_installed':False,
            'saved_material_receipt_unchanged':True,'gameplay_acceptance':'pending isolated candidate launch'}
    (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'executable':str(executable),'sha256':report['sha256'],'global_runtime_installed':False}))

if __name__=='__main__':main()
