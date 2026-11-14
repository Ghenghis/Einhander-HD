from pathlib import Path
n=Path(__file__).resolve().parent
# The previously executed v64 recipe is immutable in its build folder.
r=Path('C:/github/Einhander')
p=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v64-scene-capture-r2/executed-build-script.py'
s=p.read_text().replace('sampling-build-v64-scene-capture-r2','sampling-build-v65-word-sources-r1')
a="gpu=gpu.replace(a,a+observer,1); (src/'gpu.c').write_text(gpu)"
new=r'''gpu=gpu.replace(a,a+observer,1)
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
(src/'gpu.c').write_text(gpu)
'''
assert s.count("gpu=gpu.replace(a,a+observer,1); (src/'gpu.c').write_text(gpu)")==1
s=s.replace("gpu=gpu.replace(a,a+observer,1); (src/'gpu.c').write_text(gpu)",new,1)
s=s.replace('gp0-scene-v1','gp0-scene-v2')
s=s.replace('bounded actual GP0 scene capture.','bounded actual GP0 scene capture with exact per-word sources and reset/load invalidation.')
compile(s,'build_private_scene_v65.py','exec')
(n/'build_private_scene_v65.py').write_text(s)
print('Prepared exact per-word source v65 build recipe; not executed')
