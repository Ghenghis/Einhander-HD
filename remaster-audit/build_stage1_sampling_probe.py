"""Build a private sampling probe from pinned objects, then test it separately.

Compilation does not use the GPU. --test runs hidden real-GL fixtures and must
be scheduled while the shared GPU is quiet. Neither mode installs a runtime.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

import build_facade_motion_experiment as prior
from run_hd_skin_material_test import extract_shader

ROOT=prior.ROOT
AUDIT=prior.AUDIT
OUTPUT=AUDIT/'dev-center-evidence/stage1-completion-20261112'
SOURCE=prior.SOURCE

def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--audio-max-correction',type=float,choices=[.005,.01],default=None,
        help='Explicit private same-source audio control; default uses the production header')
    args=parser.parse_args();out=args.output.resolve()
    if out.parent!=OUTPUT.resolve():raise ValueError('Output must be directly inside private completion evidence')
    commands=[]
    def run(command,label,env=None):
        result=subprocess.run(command,cwd=prior.BUILD,env=env,capture_output=True,text=True,
            timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        commands.append(dict(label=label,arguments=command,exit=result.returncode))
        write(out/('test-commands.json' if args.test else 'commands.json'),commands)
        print(label,'exit',result.returncode,flush=True)
        if result.returncode:
            print((result.stdout+result.stderr)[-12000:]);raise SystemExit(result.returncode)
        return result
    if args.test:
        from gpu_capture_guard import require_quiet_gpu
        quiet=require_quiet_gpu()
        report=json.loads((out/'build.json').read_bytes())
        if (out/'tests.json').exists():raise ValueError('Tests already recorded; use a fresh build')
        for name in ('executable','test_executable'):
            if prior.sha(report[name])!=report[name+'_sha256']:raise ValueError('Executable changed')
        env=os.environ.copy()
        for key in list(env):
            if key.startswith(('PSXRECOMP_HD_','PSXRECOMP_SKIN_','PSXRECOMP_PLAYER_DRAW_')) or key=='PSX_LOAD_SLOT':env.pop(key)
        env.update(PSXRECOMP_HD_PAGE_FALLBACK='1',PSXRECOMP_HD_CPU_AUTHORITY='0',
            PSXRECOMP_HD_FACADE_MOTION='0')
        results={}
        results['native-regions']=run([str(out/'test-regions.exe'),str(out/'region-fixtures'),str(out/'capacity-fixtures')],'native-region-regressions',env).stdout
        results['watchdog-time']=run([str(out/'test-watchdog-time.exe')],'watchdog-time-regressions',env).stdout
        results['freeze-stack']=run([str(out/'test-freeze-stack.exe')],'freeze-stack-regressions',env).stdout
        results['hero-draw']=run([str(out/'test-hero-draw.exe')],'hero-draw-regressions',env).stdout
        results['threat-draw']=run([str(out/'test-threat-draw.exe')],'threat-draw-regressions',env).stdout
        results['interp-pc-sampler']=run([str(out/'test-interp-pc-sampler.exe')],'interp-pc-sampler-regressions',env).stdout
        results['timestamp-batch']=run([str(out/'test-timestamp-batch.exe')],'timestamp-batch-regressions',env).stdout
        results['rewind-cadence']=run([str(out/'test-rewind-cadence.exe'),str(ROOT/'windows-x64/psxrecomp/runtime/tests/fixtures/rewind')],'rewind-cadence-regressions',env).stdout
        results['source-cache-filter']=run([str(out/'test-source-cache-filter.exe')],'source-cache-filter-regressions',env).stdout
        results['decode-queue']=run([str(out/'test-decode-queue.exe')],'decode-queue-regressions',env).stdout
        for enabled in (0,1):
            label='real-gl-world-'+str(enabled)
            result=run([report['test_executable'],str(out/'facade-pack'),str(enabled)],label,
                dict(env,PSXRECOMP_HD_WORLD_SAMPLING=str(enabled),PSXRECOMP_HD_WORLD_ANISOTROPY='8'))
            results[label]=result.stdout
        label='real-gl-world-0-filter-cache-1'
        results[label]=run([report['test_executable'],str(out/'facade-pack'),'0'],label,
            dict(env,PSXRECOMP_HD_WORLD_SAMPLING='0',PSXRECOMP_HD_FILTER_STATE_CACHE='1')).stdout
        label='real-gl-world-0-keep-bracket-1'
        results[label]=run([report['test_executable'],str(out/'facade-pack'),'0'],label,
            dict(env,PSXRECOMP_HD_WORLD_SAMPLING='0',PSXRECOMP_HD_KEEP_BRACKET='1')).stdout
        write(out/'tests.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),gpu_preflight=quiet,results=results,
            build_sha256=prior.sha(out/'build.json'),commands=commands))
        return
    if out.exists():raise ValueError('Use a fresh immutable build directory')
    baseline=json.loads((prior.BASE/'build.json').read_bytes())
    for row in baseline['objects']:
        if prior.sha(row['path'])!=row['sha256']:raise ValueError('Pinned object changed')
    pack=ROOT/'windows-x64/psxrecomp/runtime/src/hd_texture_pack.cpp'
    saved=OUTPUT/'source-baseline/gpu_gl_renderer.c'
    if prior.sha(saved)!='bea6700fbc17ea0063af0830ff320381c11119251fa7a9a398976834bdb63b01':
        raise ValueError('Pre-experiment source changed')
    watchdog=SOURCE.with_name('starvation_ring.c')
    freeze=SOURCE.with_name('freeze_heartbeat.c')
    debug=SOURCE.with_name('debug_server.c')
    sources=[SOURCE,pack,watchdog,freeze,debug,freeze.with_name('freeze_stack_capture.h'),watchdog.with_name('starvation_watchdog_time.h'),SOURCE.with_name('hd_research_renderer.h'),SOURCE.with_name('hero_draw_tracker.h'),ROOT/'windows-x64/psxrecomp/runtime/include/gpu_gl_renderer.h',Path(__file__),AUDIT/'test_stage1_sampling_gl.c',AUDIT/'test_facade_motion_gl.c',AUDIT/'test_facade_motion_gl.cpp',AUDIT/'test_exact_regions.cpp',AUDIT/'test_starvation_watchdog_time.c',AUDIT/'test_freeze_stack_capture.c',AUDIT/'test_hero_draw_tracker.c']
    sources.append(AUDIT/'test_hd_opaque_batch_gl.h')
    sources.append(AUDIT/'test_hd_emissive_gl.h')
    sources.extend([SOURCE.with_name('threat_draw_tracker.h'),AUDIT/'test_threat_draw_tracker.c',
        SOURCE.with_name('dirty_ram_interp.c'),SOURCE.with_name('psx_cycles.c'),SOURCE.with_name('overlay_loader.c'),
        ROOT/'windows-x64/psxrecomp/runtime/include/interp_pc_sampler.h',AUDIT/'test_interp_pc_sampler.c',
        ROOT/'windows-x64/psxrecomp/runtime/tests/test_psx_timestamp_batch.c',ROOT/'windows-x64/psxrecomp/runtime/tests/test_psx_cycle_event_boundaries.c'])
    sources.extend([SOURCE.with_name('main.cpp'),SOURCE.with_name('recomp_audio_drc.h')])
    sources.extend([SOURCE.with_name('psx_rewind.c'),ROOT/'windows-x64/psxrecomp/runtime/include/psx_rewind.h',
        ROOT/'windows-x64/psxrecomp/runtime/tests/test_rewind_cadence.c'])
    sources.extend((ROOT/'windows-x64/psxrecomp/runtime/tests/fixtures/rewind').glob('*.trace'))
    sources.extend([AUDIT/'gpu_capture_guard.py',AUDIT/'test_gpu_capture_guard.py'])
    sources.extend([SOURCE.with_name('hd_source_cache_filter.h'),AUDIT/'test_hd_source_cache_filter.c'])
    sources.extend([SOURCE.with_name('hd_decode_queue.h'),AUDIT/'test_hd_decode_queue.cpp',ROOT/'windows-x64/psxrecomp/runtime/include/hd_texture_pack.h'])
    hashes={str(p):prior.sha(p) for p in sources}
    out.mkdir()
    shutil.copytree(AUDIT/'facade-motion-experiment/build-v3/facade-pack',out/'facade-pack')
    green=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
    green_key='95A3BCF8-723E222C'
    for suffix in ('words.bin','clut.bin'):
        shutil.copy2(green/(green_key+'.'+suffix),out/'facade-pack'/(green_key+'.'+suffix))
        shutil.copy2(green/('724E77DA-21FDE894.'+suffix),out/'facade-pack'/('724E77DA-21FDE894.'+suffix))
        for batch,key in [('mk3-native-sources-v1','8FE8B060-21FDE894'),('astraea-native-sources-v2','6ACFACE4-EF213D7F')]:
            source=OUTPUT/batch/'hd-on_rewind-off/source-pages'/(key+'.'+suffix)
            shutil.copy2(source,out/'facade-pack'/(key+'.'+suffix))
        key='1263A036-6E78D825'
        shutil.copy2(OUTPUT/'actor-native-proofs-v1'/(key+'.'+suffix),out/'facade-pack'/(key+'.'+suffix))
    from PIL import Image
    mask_root=out/'emissive-pack';mask_root.mkdir()
    for index,colour in enumerate([0x1111,0x2222,0x3333]):
        raw=struct.pack('<H',colour)*1024;key=f'{zlib.crc32(raw):08X}-00000000'
        image=Image.new('RGBA',(64,64),(100,150,200,127))
        for y in range(8):
            for x in range(64):image.putpixel((x,y),(100,150,200,0))
        for y in range(56,64):
            for x in range(64):image.putpixel((x,y),(100,150,200,255))
        image.save(mask_root/(key+'.png'))
        if index==0:
            mask=Image.new('L',(64,64),0)
            for y in range(64):
                for x in range(20,64):mask.putpixel((x,y),128 if x<40 else 255)
        elif index==1:mask=Image.new('L',(8,8),255)
        else:mask=Image.new('RGB',(64,64),(255,255,255))
        mask.save(mask_root/(key+'-emissive.png'))
    Image.new('RGBA',(1024,1024),(64,96,128,127)).save(out/'facade-pack'/(green_key+'.png'))
    Image.new('RGBA',(64,64),(0,0,0,0)).save(out/'facade-pack'/'724E77DA-21FDE894.png')
    (out/'facade_baseline_shader.h').write_text('static const char *facade_baseline_hd_fs='+json.dumps(extract_shader(saved))+';\n')
    shutil.copytree(prior.BASE/'fixtures',out/'region-fixtures')
    cross=out/'region-fixtures/cross-depth'
    shutil.copytree(out/'region-fixtures/valid',cross)
    raw=struct.pack('<128H',*([0x001f]*128));clut=struct.pack('<16H',*range(16))
    key=f'{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}'
    for suffix,data in [('words.bin',raw),('valid.bin',bytes([1])*128),('clut.bin',clut)]:
        (cross/(key+'.'+suffix)).write_bytes(data)
    Image.new('RGBA',(64,8),(8,16,24,255)).save(cross/(key+'.png'))
    with (cross/'ExactRegions.tsv').open('a') as stream:
        stream.write(f'{key}\t448\t256\t16\t8\t0\t800\t500\n')
    for count,label in [(256,'valid256'),(257,'invalid257')]:
        directory=out/'capacity-fixtures'/label;directory.mkdir(parents=True)
        rows=[];raw=struct.pack('<H',0x1111);th=zlib.crc32(raw)
        for phase in range(count):
            clut=struct.pack('<16H',0,phase+1,*([0]*14));key=f'{th:08X}-{zlib.crc32(clut):08X}'
            for suffix,data in [('words.bin',raw),('valid.bin',b'\1'),('clut.bin',clut)]:
                (directory/(key+'.'+suffix)).write_bytes(data)
            Image.new('RGBA',(4,1),(8,16,24,127)).save(directory/(key+'.png'))
            rows.append(f'{key}\t800\t0\t1\t1\t0\t800\t500')
        (directory/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+'\n'.join(rows)+'\n')
    run([str(prior.COMPILER),'-std=c++17','-O2','-static','-DHD_TEXTURE_PACK_DISABLE_PNG_DECODE',
        '-I'+str(ROOT/'windows-x64/psxrecomp/runtime/include'),str(AUDIT/'test_exact_regions.cpp'),str(pack),
        '-o',str(out/'test-regions.exe')],'compile-region-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        str(AUDIT/'test_starvation_watchdog_time.c'),'-o',str(out/'test-watchdog-time.exe')],'compile-watchdog-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        str(AUDIT/'test_freeze_stack_capture.c'),'-o',str(out/'test-freeze-stack.exe')],'compile-freeze-stack-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-I'+str(SOURCE.parent),'-I'+str(ROOT/'windows-x64/psxrecomp/runtime/include'),
        str(AUDIT/'test_hero_draw_tracker.c'),'-o',str(out/'test-hero-draw.exe')],'compile-hero-draw-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-I'+str(SOURCE.parent),str(AUDIT/'test_threat_draw_tracker.c'),'-o',str(out/'test-threat-draw.exe')],'compile-threat-draw-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-I'+str(ROOT/'windows-x64/psxrecomp/runtime/include'),str(AUDIT/'test_interp_pc_sampler.c'),
        '-o',str(out/'test-interp-pc-sampler.exe')],'compile-interp-pc-sampler-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-I'+str(ROOT/'windows-x64/psxrecomp/runtime/include'),
        str(ROOT/'windows-x64/psxrecomp/runtime/tests/test_psx_timestamp_batch.c'),str(SOURCE.with_name('psx_cycles.c')),
        '-o',str(out/'test-timestamp-batch.exe')],'compile-timestamp-batch-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-DPSX_HAS_RBENGINE_SNAP=1','-DWITH_REWIND_STATS=1',
        '-I'+str(ROOT/'windows-x64/psxrecomp/runtime/include'),
        '-I'+str(ROOT/'windows-x64/psxrecomp/lib/retcomm-rbengine/include'),
        str(ROOT/'windows-x64/psxrecomp/runtime/tests/test_rewind_cadence.c'),str(SOURCE.with_name('mdec.c')),
        str(ROOT/'windows-x64/psxrecomp/lib/retcomm-rbengine/src/snap/rbe_snap_ring.c'),
        '-o',str(out/'test-rewind-cadence.exe')],'compile-rewind-cadence-regressions')
    run([str(prior.COMPILER.with_name('clang.exe')),'-std=c11','-O2','-static',
        '-I'+str(SOURCE.parent),str(AUDIT/'test_hd_source_cache_filter.c'),
        '-o',str(out/'test-source-cache-filter.exe')],'compile-source-cache-filter-regressions')
    run([str(prior.COMPILER),'-std=c++17','-O2','-static',str(AUDIT/'test_hd_decode_queue.cpp'),
        '-o',str(out/'test-decode-queue.exe')],'compile-decode-queue-regressions')
    pack_object=out/'hd_texture_pack.cpp.obj'
    pack_command=next(row['arguments'] for row in baseline['commands'] if row['label']=='compile-pack').copy()
    pack_command[pack_command.index('-o')+1]=str(pack_object)
    if '-MF' in pack_command:pack_command[pack_command.index('-MF')+1]=str(pack_object)+'.d'
    run(pack_command,'compile-current-pack')
    template=next(row['arguments'] for row in baseline['commands'] if row['label']=='compile-experimental-renderer')
    def compile_renderer(destination,source=SOURCE):
        command=template.copy()
        command[command.index('-o')+1]=str(destination)
        command[command.index('-MF')+1]=str(destination)+'.d'
        command[-1]=str(source)
        command.insert(-2,'-I'+str(out))
        run(command,'compile-'+destination.stem)
    watchdog_object=out/'starvation_ring.c.obj';compile_renderer(watchdog_object,watchdog)
    freeze_object=out/'freeze_heartbeat.c.obj';compile_renderer(freeze_object,freeze)
    debug_object=out/'debug_server.c.obj';compile_renderer(debug_object,debug)
    interp_object=out/'dirty_ram_interp.c.obj';compile_renderer(interp_object,SOURCE.with_name('dirty_ram_interp.c'))
    cycles_object=out/'psx_cycles.c.obj';compile_renderer(cycles_object,SOURCE.with_name('psx_cycles.c'))
    loader_object=out/'overlay_loader.c.obj';compile_renderer(loader_object,SOURCE.with_name('overlay_loader.c'))
    rewind_object=out/'psx_rewind.c.obj';compile_renderer(rewind_object,SOURCE.with_name('psx_rewind.c'))
    response=(prior.BASE/'exact-region-link.rsp').read_text().splitlines()
    def link(renderer,destination,main=None):
        values=response.copy()
        for suffix,replacement in [('/gpu_gl_renderer.c.obj',renderer),('/hd_texture_pack.cpp.obj',pack_object),('/starvation_ring.c.obj',watchdog_object),('/freeze_heartbeat.c.obj',freeze_object),('/debug_server.c.obj',debug_object),('/dirty_ram_interp.c.obj',interp_object),('/psx_cycles.c.obj',cycles_object),('/overlay_loader.c.obj',loader_object),('/psx_rewind.c.obj',rewind_object)]+([('/main.cpp.obj',main)] if main else []):
            matches=[i for i,value in enumerate(values) if value.strip('"').replace('\\','/').endswith(suffix)]
            if len(matches)!=1:raise ValueError('Ambiguous pinned link object '+suffix)
            values[matches[0]]='"'+replacement.as_posix()+'"'
        rsp=out/(destination.stem+'.rsp');rsp.write_text('\n'.join(values)+'\n')
        run([str(prior.COMPILER),'-O3','-static','-Wl,--stack,67108864','@'+str(rsp),'-o',str(destination)],'link-'+destination.stem)
        return rsp
    wrapper=out/'sampling-test.c'
    wrapper.write_text('#define HD_RENDERER_SOURCE "'+SOURCE.as_posix()+'"\n#include "'+(AUDIT/'test_stage1_sampling_gl.c').as_posix()+'"\n')
    test_object=out/'sampling-test.obj';compile_renderer(test_object,wrapper)
    ninja=(prior.BUILD/'build.ninja').read_text().splitlines()
    index=next(i for i,line in enumerate(ninja) if line.startswith('build CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj:'))
    fields={line.strip().split(' = ',1)[0]:line.split(' = ',1)[1] for line in ninja[index+1:index+15] if ' = ' in line}
    flags=[v.replace('D:/Games/Einhander/windows-x64/',(ROOT/'windows-x64').as_posix()+'/')
        for v in prior.windows_args('unused '+fields['DEFINES']+' '+fields['FLAGS']+' '+fields['INCLUDES'])[1:]]
    main_object=out/'sampling-main.obj'
    run([str(prior.COMPILER),*flags,'-c',str(AUDIT/'test_facade_motion_gl.cpp'),'-o',str(main_object)],'compile-test-main')
    test_exe=out/'test-stage1-sampling.exe';link(test_object,test_exe,main_object)
    renderer=out/'gpu_gl_renderer.c.obj';compile_renderer(renderer)
    runtime_main=out/'runtime-main.cpp.obj'
    audio_flags=[] if args.audio_max_correction is None else ['-DRECOMP_AUDIO_DRC_MAX_CORRECTION='+str(args.audio_max_correction)]
    run([str(prior.COMPILER),*flags,*audio_flags,'-c',str(SOURCE.with_name('main.cpp')),'-o',str(runtime_main)],'compile-runtime-main')
    runtime=out/'Einhander_Recompiled.exe';rsp=link(renderer,runtime,runtime_main)
    if any(prior.sha(p)!=digest for p,digest in hashes.items()):raise ValueError('Source changed while compiling')
    write(out/'build.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),
        executable=str(runtime),executable_sha256=prior.sha(runtime),test_executable=str(test_exe),
        test_executable_sha256=prior.sha(test_exe),source_hashes=hashes,
        fixture_hashes={p.relative_to(out).as_posix():prior.sha(p) for p in (out/'facade-pack').rglob('*') if p.is_file()},
        baseline_build=dict(path=str(prior.BASE/'build.json'),sha256=prior.sha(prior.BASE/'build.json')),
        link_response=str(rsp),link_response_sha256=prior.sha(rsp),commands=commands,
        runtime_main_object_sha256=prior.sha(runtime_main),audio_max_correction_override=args.audio_max_correction,
        global_runtime_installed=False,game_launched=False))
    print(json.dumps(dict(output=str(out),runtime_sha256=prior.sha(runtime))))

if __name__=='__main__':main()
