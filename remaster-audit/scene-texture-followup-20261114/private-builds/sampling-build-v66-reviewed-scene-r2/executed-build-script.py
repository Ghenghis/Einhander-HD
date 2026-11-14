"""Link frozen v4 into an isolated v61-derived executable, CPU only."""
from pathlib import Path
import datetime, hashlib, json, os, psutil, shutil, subprocess, time
r=Path('C:/github/Einhander'); n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v61-view-metrics-r2'
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v4'
rd=f/'host-run/20261114T114326Z'
out=e/'sampling-build-v66-reviewed-scene-r2'; out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
parent=json.loads((base/'build.json').read_text())
assert sha(parent['executable'])==parent['executable_sha256']=='c6e573f317e5faaa624612320c5468ed8e0158092b4e53e3a0357e607e325686'
assert sha(f/'READY.json')=='93a97669e6d9cf5fbd75536d5261efbe5855f1299bb91683badea4f7a395299e'
for ref in parent['link_inputs']: assert Path(ref['path']).drive.upper()=='C:' and sha(ref['path'])==ref['sha256']
for name,h in parent['headers'].items(): assert sha(base/name)==h
for name,h in parent['sources'].items(): assert sha(base/name)==h
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED'; hold=marker.read_bytes()
src=out/'src'; src.mkdir(); inc=out/'include'; shutil.copytree(base/'include',inc)
shutil.copy2(rd/'patched/gpu_gl_renderer.c',src/'gpu_gl_renderer.c')
shutil.copy2(rd/'patched/hd_class_mips.inc',src/'hd_class_mips.inc')
assert sha(src/'gpu_gl_renderer.c')=='b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16'
# The v63 renderer remains byte-identical to Claude's frozen v4.
for name in ['scene_capture.h','scene_capture.cpp','scene_json.cpp','scene_runtime.h','scene_runtime.cpp']:
    shutil.copy2(n/'scene-export'/name,src/name)
gpu=(base/'src/gpu.c').read_text()
a='#include "pgxp.h"'; assert gpu.count(a)==1
gpu=gpu.replace(a,a+'\n#include "scene_runtime.h"',1)
a='    gp0_ring_record(gp0_cmd_buf, gp0_words_needed);'; assert gpu.count(a)==1
observer='''
    /* PRIVATE opt-in observer. Submitted GP0 stream, before culling/rasterization.
     * No guest writes, GPU calls or logging; frame/packet snapshots only. */
    if (scene_runtime_enabled()) {
        const SceneDrawState st={texture_window_value,draw_offset_x,draw_offset_y,
          (uint16_t)draw_area_left,(uint16_t)draw_area_top,(uint16_t)draw_area_right,(uint16_t)draw_area_bottom,
          (uint8_t)set_mask_bit,(uint8_t)check_mask_bit};
        scene_runtime_command((uint32_t)s_frame_count,gp0_cmd_buf,gp0_words_needed,gp0_cmd_source_addr,&st);
    }
'''
gpu=gpu.replace(a,a+observer,1)
a='static uint32_t gp0_cmd_buf[16];';assert gpu.count(a)==1
gpu=gpu.replace(a,'static uint32_t s_scene_word_sources[16];\n'+a,1)
a='gp0_words_needed,gp0_cmd_source_addr,&st);';assert gpu.count(a)==1
gpu=gpu.replace(a,'gp0_words_needed,s_scene_word_sources,&st);',1)
a='        gp0_cmd_buf[gp0_words_collected++] = val;';assert gpu.count(a)==1
gpu=gpu.replace(a,'        if(scene_runtime_enabled())s_scene_word_sources[gp0_words_collected]=gp0_next_source_addr;\n'+a,1)
a='    gp0_cmd_buf[0] = val;';assert gpu.count(a)==1
gpu=gpu.replace(a,'    if(scene_runtime_enabled())s_scene_word_sources[0]=gp0_next_source_addr;\n'+a,1)
# Observer state is host diagnostics, never added to the guest snapshot format.
# Reset/load makes all existing partial source slots unknown and drops snapshots.
for a in ['static void gpu_reset_state(int clear_vram) {','static int gpu_snap_parse(PstR *r) {']:
    assert gpu.count(a)==1
    gpu=gpu.replace(a,a+'\n    memset(s_scene_word_sources,0xff,sizeof s_scene_word_sources);\n    scene_runtime_invalidate();',1)
a='        const SceneDrawState st={texture_window_value,draw_offset_x,draw_offset_y,';assert gpu.count(a)==1
gpu=gpu.replace(a,'        int32_t host_left,host_right;draw_area_host_x_bounds(&host_left,&host_right);\n'+a,1)
a='(uint8_t)set_mask_bit,(uint8_t)check_mask_bit};';assert gpu.count(a)==1
gpu=gpu.replace(a,'(uint8_t)set_mask_bit,(uint8_t)check_mask_bit,host_left,host_right,\n          (uint8_t)(!ws_active()&&!ws_native_wide_active()&&!gte_geometry_correction_enabled())};',1)
a='        gp0_ring_record(hdr_only, 1);';assert gpu.count(a)==1
gpu=gpu.replace(a,a+'\n        if(scene_runtime_enabled())scene_runtime_command((uint32_t)s_frame_count,hdr_only,1,NULL,NULL);',1)
(src/'gpu.c').write_text(gpu)

v63=e/'sampling-build-v63-classmip-r1'
assert sha(v63/'Einhander_Recompiled.exe')=='9b47f310e5de31762bdd815a59c73f21170be6456146b701d3baa908cbb65c3e'
debug=(v63/'src/debug_server.c').read_text()
a='#include "pgxp.h"'; assert debug.count(a)==1
debug=debug.replace(a,a+'\n#include "scene_runtime.h"',1)
handler=r'''/* PRIVATE default-OFF scene observer control. Executes at emulation safe point. */
static void handle_scene_capture(int id,const char *json) {
    int rc=SCENE_OK;
    if(json_get_int(json,"cancel",0)==1)rc=scene_runtime_cancel();
    if(json_get_int(json,"arm",0)==1)rc=scene_runtime_arm((uint32_t)s_frame_count);
    int index=json_get_int(json,"index",-1);
    SceneCaptureInfo i={0};int ir=scene_runtime_info(&i);
    if(rc!=SCENE_OK||ir!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc!=SCENE_OK?rc:ir);return;}
    if(index>=0) {
        int generation=json_get_int(json,"generation",-1);
        if(generation<0){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,SCENE_BAD_ARGUMENT);return;}
        char record[8192];rc=scene_runtime_json((uint32_t)index,(uint32_t)generation,record,sizeof record);
        if(rc!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc);return;}
        send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v3\",\"record\":%s}",id,record);return;
    }
    send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v3\",\"mode\":%u,\"frame\":%u,\"generation\":%u,\"count\":%u,\"capacity\":%u,\"textured_seen\":%u,\"malformed\":%u,\"overflow\":%u,\"geometry_qualified\":%u,\"missing_vertices\":%u,\"other_commands\":%u,\"complete_interval\":%s,\"untextured_polygons\":%u,\"textured_sprites\":%u,\"untextured_rects\":%u,\"lines\":%u,\"vram_fills\":%u,\"lag0_vertices\":%u,\"lag1_vertices\":%u,\"mixed_lag_primitives\":%u,\"ws_rejected_vertices\":%u,\"owner_errors\":%u,\"geometry_types_complete\":%s}",id,i.mode,i.frame,i.generation,i.count,i.capacity,i.textured_seen,i.malformed,i.overflow,i.qualified,i.missing_vertices,i.other_commands,i.complete?"true":"false",i.untextured_polygons,i.textured_sprites,i.untextured_rects,i.lines,i.vram_fills,i.lag0_vertices,i.lag1_vertices,i.mixed_lag_primitives,i.ws_rejected_vertices,i.owner_errors,i.geometry_types_complete?"true":"false");
}

'''
a='/* pgxp_view —'; assert debug.count(a)==1; debug=debug.replace(a,handler+a,1)
a='    { "pgxp_view",         handle_pgxp_view },'; assert debug.count(a)==1
debug=debug.replace(a,a+'\n    { "scene_capture",     handle_scene_capture },',1)
a='        s_frame_count++;';assert debug.count(a)==1
debug=debug.replace(a,a+'\n        scene_runtime_tick((uint32_t)s_frame_count);',1)
a='    s_frame_count++;';assert debug.count(a)==2 # nested and normal increments
# Replace the unindented exact full line only.
debug=debug.replace('\n'+a+'\n','\n'+a+'\n    scene_runtime_tick((uint32_t)s_frame_count);\n',1)
(src/'debug_server.c').write_text(debug)
receipt=dict(started_utc=stamp(),scope='Private executable: frozen v4 renderer, read-only counter RPC and bounded actual GP0 scene capture with exact per-word sources, generation/complete gates, culling metadata, omitted-family counts, SF check, explicit owner path and reset/load invalidation. Three core TUs rebuilt, three observer TUs added; retained pinned guest/core/platform objects. Not a clean full-source build or production installation.',commands=[],
             parent_exe_sha256=parent['executable_sha256'],source_hashes={p.relative_to(out).as_posix():sha(p) for p in src.iterdir()},headers=parent['headers'],
             cpu_affinity=me.cpu_affinity(),below_normal=True,build_complete=False,game_launched=False,gpu_work=False,
             supersedes='v62 RGB-only is unlaunched and retired: broad scope, added fprintf, overcounting; v4 scoped semantics authoritative',
             default_off_env=['PSXRECOMP_HD_CLASS_MIPS=1','PSXRECOMP_HD_RGB_EDGES=1','PSXRECOMP_SCENE_CAPTURE=1'],both_require='PSXRECOMP_HD_CLASS_MIPS_DIR with identity-bound sidecars')
def run(label,args,cwd):
    log=out/(label+'.log'); t=time.monotonic()
    with log.open('w') as dest:
        p=subprocess.Popen(args,cwd=cwd,stdout=dest,stderr=subprocess.STDOUT,creationflags=0x4000)
        try: rc=p.wait(timeout=90)
        except subprocess.TimeoutExpired: p.terminate(); rc=p.wait(timeout=5)
    receipt['commands'].append(dict(label=label,arguments=args,cwd=str(cwd),exit=rc,seconds=time.monotonic()-t,log_sha256=sha(log)))
    print(json.dumps(dict(label=label,exit=rc,seconds=time.monotonic()-t)),flush=True)
    assert rc==0,label
try:
    objects={}
    for source in sorted(src.glob('*.c')):
        old=next(c for c in parent['commands'] if c['label']=='compile-'+source.name)
        args=[]; i=0
        while i<len(old['arguments']):
            a=old['arguments'][i]
            if a in ['-o','-c','-MT','-MF']: i+=2; continue
            if a=='-MD' or a=='-I'+str(base/'include'): i+=1; continue
            args.append(a); i+=1
        obj=out/(source.name+'.obj'); args.insert(1,'-I'+str(inc))
        args+=['-MD','-MF',str(obj)+'.d','-c',str(source),'-o',str(obj)]
        run('compile-'+source.name,args,r); objects[source.name+'.obj']=obj
    extra={}
    old=next(c for c in parent['commands'] if c['label']=='compile-pgxp.cpp')
    for source in sorted(src.glob('*.cpp')):
        args=[];i=0
        while i<len(old['arguments']):
            a=old['arguments'][i]
            if a in ['-o','-c','-MT','-MF']:i+=2;continue
            if a=='-MD' or a=='-I'+str(base/'include'):i+=1;continue
            args.append(a);i+=1
        args.insert(1,'-I'+str(inc));obj=out/(source.name+'.obj')
        args+=['-MD','-MF',str(obj)+'.d','-c',str(source),'-o',str(obj)]
        run('compile-'+source.name,args,r);extra[source.name]=obj
    inputs=[]; replaced={}
    for ref in parent['link_inputs']:
        name=Path(ref['path']).name
        if name in objects:
            assert name not in replaced
            replaced[name]=(ref,objects[name]); inputs.append(dict(path=str(objects[name]),sha256=sha(objects[name])))
        else: inputs.append(ref)
    assert len(replaced)==3
    link=parent['commands'][-1]; cwd=Path(link['cwd']); lines=[]; count=0
    for line in (base/'Einhander_Recompiled.rsp').read_text().splitlines():
        token=line.strip().strip('"'); p=Path(token); full=(p if p.is_absolute() else cwd/p).resolve()
        pair=next((v for v in replaced.values() if os.path.normcase(str(Path(v[0]['path']).resolve()))==os.path.normcase(str(full))),None)
        if pair: lines.append('"'+pair[1].as_posix()+'"'); count+=1
        else: lines.append(line)
    assert count==3
    for name,obj in extra.items():
        lines.append('"'+obj.as_posix()+'"'); inputs.append(dict(path=str(obj),sha256=sha(obj)))
    rsp=out/'Einhander_Recompiled.rsp'; rsp.write_text('\n'.join(lines)+'\n')
    args=list(link['arguments']); args[next(i for i,a in enumerate(args) if a.startswith('@'))]='@'+str(rsp)
    exe=out/'Einhander_Recompiled.exe'; args[args.index('-o')+1]=str(exe)
    run('link',args,cwd)
    for ref in parent['link_inputs']: assert sha(ref['path'])==ref['sha256']
    assert marker.read_bytes()==hold
    receipt.update(build_complete=True,executable=str(exe),executable_sha256=sha(exe),link_inputs=inputs,response_sha256=sha(rsp),user_gpu_hold_unchanged=True)
except Exception as ex: receipt['error']=repr(ex); raise
finally:
    receipt['ended_utc']=stamp(); (out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    shutil.copy2(__file__,out/'executed-build-script.py')
print(json.dumps(dict(build_complete=receipt['build_complete'],executable_sha256=receipt.get('executable_sha256'))))
