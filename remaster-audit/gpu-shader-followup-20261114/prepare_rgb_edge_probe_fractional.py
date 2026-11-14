from pathlib import Path
import hashlib,json,shutil,subprocess,time,psutil
p=Path(__file__).resolve().parent;src=p/'class-mip-gpu-r1';out=p/'rgb-edge-gpu-r2';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for name in ['gl_selftest_classmips.c','hd_class_mips.inc','HD_FS.frag','TEX_VS.vert']:shutil.copy2(src/name,out/name)
shader=(out/'HD_FS.frag').read_text()
helper='''// PRIVATE RGB-only experiment. Alpha is still the separately selected PSX class.
uniform int u_hd_rgb_edges;
vec4 hd_visible_rgb(vec2 pos, int level) {
  ivec2 size = textureSize(u_hd,level);
  vec2 p = pos * vec2(size) - vec2(0.5);
  ivec2 b = ivec2(floor(p)); vec2 f = fract(p);
  vec4 a=texelFetch(u_hd,clamp(b,ivec2(0),size-ivec2(1)),level);
  vec4 c=texelFetch(u_hd,clamp(b+ivec2(1,0),ivec2(0),size-ivec2(1)),level);
  vec4 d=texelFetch(u_hd,clamp(b+ivec2(0,1),ivec2(0),size-ivec2(1)),level);
  vec4 e=texelFetch(u_hd,clamp(b+ivec2(1,1),ivec2(0),size-ivec2(1)),level);
  vec4 w=vec4((1.0-f.x)*(1.0-f.y),f.x*(1.0-f.y),(1.0-f.x)*f.y,f.x*f.y);
  w*=vec4(a.a>0.0?1.0:0.0,c.a>0.0?1.0:0.0,d.a>0.0?1.0:0.0,e.a>0.0?1.0:0.0);
  float n=dot(w,vec4(1.0));
  return vec4((a.rgb*w.x+c.rgb*w.y+d.rgb*w.z+e.rgb*w.w)/max(n,1e-8),n);
}
'''
anchor='void main(){';assert shader.count(anchor)==1;shader=shader.replace(anchor,helper+anchor,1)
anchor='  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}'
addition='''  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion!=0 && u_hd_class_levels>0 && !native_edge) {
    vec2 gx=facade_dx*vec2(hd_size), gy=facade_dy*vec2(hd_size);
    float lod=clamp(log2(max(max(length(gx),length(gy)),1e-8)),0.0,float(u_hd_class_levels));
    if(lod<1.0) {
      vec4 edge0=hd_visible_rgb(rgb_pos,0);
      vec4 edge1=hd_visible_rgb(rgb_pos,1);
      // Generated class levels carry filled RGB even in cutouts. Do not mix black
      // into a conservative visible class when the level0 footprint is empty.
      vec3 rgb1=edge1.a>1e-8?edge1.rgb:textureLod(u_hd,rgb_pos,1.0).rgb;
      vec3 rgb0=edge0.a>1e-8?edge0.rgb:rgb1;
      c.rgb=mix(rgb0,rgb1,lod);
    }
  }
'''
assert shader.count(anchor)==1;shader=shader.replace(anchor,addition+anchor,1);(out/'HD_FS.frag').write_text(shader)
harness=(out/'gl_selftest_classmips.c').read_text()
anchor='static GLuint g_prog, g_vbo, g_fbo, g_rt;';assert harness.count(anchor)==1;harness=harness.replace(anchor,anchor+'\nstatic int g_rgb_edges=1;')
anchor='    pUniform1i(pGetUniformLocation(g_prog, "u_hd_class_levels"), class_levels);';assert harness.count(anchor)==1
harness=harness.replace(anchor,anchor+'\n    pUniform1i(pGetUniformLocation(g_prog, "u_hd_rgb_edges"), g_rgb_edges);')
anchor='    const GLenum err = glGetError();'
extra='''    // Compare only support/STP alpha: RGB intentionally changes at cutout edges.
    int support_same=1; static uint8_t before[VH][VW][4];
    for(int k=0;k<5;k++) for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tC,1,3,ms[k],ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tC,1,3,ms[k],ph);
      for(int y=0;y<VH;y++)for(int x=0;x<VW;x++)
        if(drawn(before[y][x])!=drawn(g_px[y][x]) || before[y][x][3]!=g_px[y][x][3])support_same=0;
    }
    // All-opaque level0 control, mixed STP classes, varying colors. Same texture,
    // same selected class; only the RGB-only uniform changes.
    for(int y=0;y<HH;y++)for(int x=0;x<HW;x++) {
      g_l0[y][x][0]=(uint8_t)(x*3);g_l0[y][x][1]=(uint8_t)(y*3);
      g_l0[y][x][2]=(uint8_t)((x+y)*2);g_l0[y][x][3]=((x/S+y/S)&1)?255:127;
    }
    for(int y=0;y<NH;y++)for(int x=0;x<NW;x++)g_ncls[y][x]=((x+y)&1)?255:127;
    GLuint tO=make_tex(2);int opaque_max_delta=0,opaque_alpha_same=1;
    for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tO,1,3,1,ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tO,1,3,1,ph);
      for(int y=0;y<VH;y++)for(int x=0;x<VW;x++) {
        for(int c=0;c<3;c++){int delta=abs((int)before[y][x][c]-(int)g_px[y][x][c]);if(delta>opaque_max_delta)opaque_max_delta=delta;}
        if(before[y][x][3]!=g_px[y][x][3])opaque_alpha_same=0;
      }
    }
    fprintf(out," \\"rgb_edge_experiment\\": {\\"support_and_stp_unchanged\\":%s,\\"opaque_lod0_max_delta\\":%d,\\"opaque_stp_unchanged\\":%s},\\n",support_same?"true":"false",opaque_max_delta,opaque_alpha_same?"true":"false");
'''
# Keep original fixture and original acceptance checks intact. Additional controls
# are recorded separately; the original m12 failure is not relabeled.
extra=extra.replace('\\"','\\"')
assert harness.count(anchor)==1;harness=harness.replace(anchor,extra+anchor,1)
# Expand actual GPU sampling to magnification and fractional LOD transitions.
harness=harness.replace('const double ms[5] = {1, 2, 4, 8, 12};','const double ms[10] = {.5, 1, 1.125, 1.25, 1.5, 1.75, 2, 4, 8, 12};')
harness=harness.replace('Stat sa[5], sb[5], sc[5];','Stat sa[10], sb[10], sc[10];')
harness=harness.replace('i < 5','i < 10').replace('k<5','k<10').replace('i < 4','i < 10')
harness=harness.replace('sc[3].vis_min > 0 && sc[4].vis_min > 0','sc[8].vis_min > 0 && sc[9].vis_min > 0')
old='''    const int c3 = sc[0].dark_luma >= 0.9 * g_auth_min_luma && sc[1].dark_luma >= 0.9 * g_auth_min_luma &&
                   sc[2].dark_luma >= 0.9 * g_auth_min_luma && sc[3].dark_luma >= 0.9 * g_auth_min_luma &&
                   sc[4].dark_luma >= 0.9 * g_auth_min_luma;'''
assert harness.count(old)==1
harness=harness.replace(old,'    int c3=1;for(int i=0;i<10;i++)c3 &= sc[i].dark_luma >= 0.9 * g_auth_min_luma;')
harness=harness.replace('i < 4 ? "," : ""','i < 9 ? "," : ""')
# The loop-count replacement changed the separator comparison too.
harness=harness.replace('i < 10 ? "," : ""','i < 9 ? "," : ""')
harness=harness.replace('%.0f, \\"A_level0','%.3f, \\"A_level0')
(out/'gl_selftest_classmips.c').write_text(harness)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
compiler='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe';deps=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/deps')
build=json.loads((src/'build.json').read_text());cmd=build['command'];original_source=next(x for x in cmd if x.endswith('gl_selftest_classmips.c'));cmd=[x.replace(str(Path(original_source).parent),str(out)) if str(Path(original_source).parent) in x else x for x in cmd]
# Include flag path is a separate argument in the original command.
cmd[cmd.index('-I')+1]=str(out);cmd[cmd.index('-o')+1]=str(out/'gl_selftest_classmips.exe')
start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=45,creationflags=0x4000)
(out/'compile.log').write_text(c.stdout+c.stderr)
result={'compile_exit':c.returncode,'seconds':time.monotonic()-start,'command':cmd,'sources':{f.name:sha(f) for f in out.iterdir() if f.is_file() and f.suffix in ['.c','.inc','.frag','.vert']},'gpu_executed':False,'source_build':str(src/'build.json')}
if c.returncode==0:result['exe_sha256']=sha(out/'gl_selftest_classmips.exe')
(out/'build.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(c.returncode)
