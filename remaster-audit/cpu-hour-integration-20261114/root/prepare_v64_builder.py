"""Derive an auditable private builder from the already executed v63 recipe."""
from pathlib import Path
n=Path(__file__).resolve().parent
s=(n/'build_private_class_v63.py').read_text()
s=s.replace('sampling-build-v63-classmip-r1','sampling-build-v64-scene-capture-r2')
start=s.index("debug=(base/'src/debug_server.c').read_text()")
end=s.index('receipt=dict(',start)
block=r'''# The v63 renderer remains byte-identical to Claude's frozen v4.
for name in ['scene_capture.h','scene_capture.cpp','scene_json.cpp','scene_runtime.h','scene_runtime.cpp']:
    shutil.copy2(n/'scene-export'/name,src/name)
gpu=(base/'src/gpu.c').read_text()
a='#include "pgxp.h"'; assert gpu.count(a)==1
gpu=gpu.replace(a,a+'\n#include "scene_runtime.h"',1)
a='    gp0_ring_record(gp0_cmd_buf, gp0_words_needed);'; assert gpu.count(a)==1
observer='''+"'''"+r'''
    /* PRIVATE opt-in observer. Submitted GP0 stream, before culling/rasterization.
     * No guest writes, GPU calls or logging; frame/packet snapshots only. */
    if (scene_runtime_enabled()) {
        const SceneDrawState st={texture_window_value,draw_offset_x,draw_offset_y,
          (uint16_t)draw_area_left,(uint16_t)draw_area_top,(uint16_t)draw_area_right,(uint16_t)draw_area_bottom,
          (uint8_t)set_mask_bit,(uint8_t)check_mask_bit};
        scene_runtime_command((uint32_t)s_frame_count,gp0_cmd_buf,gp0_words_needed,gp0_cmd_source_addr,&st);
    }
'''+"'''"+r'''
gpu=gpu.replace(a,a+observer,1); (src/'gpu.c').write_text(gpu)
v63=e/'sampling-build-v63-classmip-r1'
assert sha(v63/'Einhander_Recompiled.exe')=='9b47f310e5de31762bdd815a59c73f21170be6456146b701d3baa908cbb65c3e'
debug=(v63/'src/debug_server.c').read_text()
a='#include "pgxp.h"'; assert debug.count(a)==1
debug=debug.replace(a,a+'\n#include "scene_runtime.h"',1)
handler=r'''+"'''"+r'''/* PRIVATE default-OFF scene observer control. Executes at emulation safe point. */
static void handle_scene_capture(int id,const char *json) {
    int rc=SCENE_OK;
    if(json_get_int(json,"cancel",0)==1)rc=scene_runtime_cancel();
    if(json_get_int(json,"arm",0)==1)rc=scene_runtime_arm((uint32_t)s_frame_count);
    int index=json_get_int(json,"index",-1);
    SceneCaptureInfo i={0};int ir=scene_runtime_info(&i);
    if(rc!=SCENE_OK||ir!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc!=SCENE_OK?rc:ir);return;}
    if(index>=0) {
        char record[8192];rc=scene_runtime_json((uint32_t)index,record,sizeof record);
        if(rc!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc);return;}
        send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v1\",\"record\":%s}",id,record);return;
    }
    send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v1\",\"mode\":%u,\"frame\":%u,\"count\":%u,\"capacity\":%u,\"textured_seen\":%u,\"malformed\":%u,\"overflow\":%u,\"geometry_qualified\":%u,\"missing_vertices\":%u,\"other_commands\":%u,\"complete_interval\":%s}",id,i.mode,i.frame,i.count,i.capacity,i.textured_seen,i.malformed,i.overflow,i.qualified,i.missing_vertices,i.other_commands,i.complete?"true":"false");
}

'''+"'''"+r'''
a='/* pgxp_view —'; assert debug.count(a)==1; debug=debug.replace(a,handler+a,1)
a='    { "pgxp_view",         handle_pgxp_view },'; assert debug.count(a)==1
debug=debug.replace(a,a+'\n    { "scene_capture",     handle_scene_capture },',1)
a='        s_frame_count++;';assert debug.count(a)==1
debug=debug.replace(a,a+'\n        scene_runtime_tick((uint32_t)s_frame_count);',1)
a='    s_frame_count++;';assert debug.count(a)==2 # nested and normal increments
# Replace the unindented exact full line only.
debug=debug.replace('\n'+a+'\n','\n'+a+'\n    scene_runtime_tick((uint32_t)s_frame_count);\n',1)
(src/'debug_server.c').write_text(debug)
'''
s=s[:start]+block+s[end:]
s=s.replace("assert len(replaced)==2","assert len(replaced)==3")
s=s.replace("assert count==2","assert count==3\n    for name,obj in extra.items():\n        lines.append('\"'+obj.as_posix()+'\"'); inputs.append(dict(path=str(obj),sha256=sha(obj)))")
a='    inputs=[]; replaced={}'
assert s.count(a)==1
extra='''    extra={}
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
'''
s=s.replace(a,extra+a,1)
s=s.replace("Private executable: frozen v4 renderer plus read-only counter RPC; retain pinned v61 guest/core/platform link inputs. Not a clean full-source build or production installation.","Private executable: frozen v4 renderer, read-only counter RPC and bounded actual GP0 scene capture. Three core TUs rebuilt, three observer TUs added; retained pinned guest/core/platform objects. Not a clean full-source build or production installation.")
s=s.replace("default_off_env=['PSXRECOMP_HD_CLASS_MIPS=1','PSXRECOMP_HD_RGB_EDGES=1']","default_off_env=['PSXRECOMP_HD_CLASS_MIPS=1','PSXRECOMP_HD_RGB_EDGES=1','PSXRECOMP_SCENE_CAPTURE=1']")
compile(s,'build_private_scene_v64.py','exec')
(n/'build_private_scene_v64.py').write_text(s)
print('Created v64 builder; not executed')
