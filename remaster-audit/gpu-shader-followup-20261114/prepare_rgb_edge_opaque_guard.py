from pathlib import Path
import hashlib,json,subprocess,time,shutil,psutil
p=Path(__file__).resolve().parent;source=p/'rgb-edge-gpu-r2';out=p/'rgb-edge-gpu-r3';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for name in ['HD_FS.frag','TEX_VS.vert','hd_class_mips.inc','gl_selftest_classmips.c']:shutil.copy2(source/name,out/name)
f=out/'HD_FS.frag';s=f.read_text();a='''      vec4 edge1=hd_visible_rgb(rgb_pos,1);''';assert s.count(a)==1
s=s.replace(a,'''      // Preserve original hardware filtering exactly when no cutout tap contributes.
      if(edge0.a < 0.999999) {
      vec4 edge1=hd_visible_rgb(rgb_pos,1);''',1)
a='      c.rgb=mix(rgb0,rgb1,lod);';assert s.count(a)==1;s=s.replace(a,a+'\n      }',1);f.write_text(s)
f=out/'gl_selftest_classmips.c';s=f.read_text();a='    // All-opaque level0 control, mixed STP classes, varying colors.'
extra='''    // Mixed STP/cutout control, including both semi-transparent subpasses.
    for(int y=0;y<HH;y++)for(int x=0;x<HW;x++)if(g_l0[y][x][3])g_l0[y][x][3]=((x/S+y/S)&1)?255:127;
    for(int y=0;y<NH;y++)for(int x=0;x<NW;x++)if(g_ncls[y][x])g_ncls[y][x]=((x+y)&1)?255:127;
    GLuint tMixed=make_tex(2);int mixed_same=1;
    for(int pass=0;pass<3;pass++)for(int k=0;k<10;k++)for(int ph=0;ph<PHASES;ph++) {
      pUniform1i(pGetUniformLocation(g_prog,"u_semipass"),pass);
      g_rgb_edges=0;render(tMixed,1,3,ms[k],ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tMixed,1,3,ms[k],ph);
      for(int y=0;y<VH;y++)for(int x=0;x<VW;x++)
        if(drawn(before[y][x])!=drawn(g_px[y][x]) || before[y][x][3]!=g_px[y][x][3])mixed_same=0;
    }
    pUniform1i(pGetUniformLocation(g_prog,"u_semipass"),0);
    fprintf(out," \\"mixed_stp_cutout_subpasses_unchanged\\":%s,\\n",mixed_same?"true":"false");
'''
assert s.count(a)==1;s=s.replace(a,extra+a,1)
a='''    for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tO,1,3,1,ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tO,1,3,1,ph);'''
b='''    for(int k=0;k<10;k++)for(int ph=0;ph<PHASES;ph++) {
      g_rgb_edges=0;render(tO,1,3,ms[k],ph);memcpy(before,g_px,sizeof before);
      g_rgb_edges=1;render(tO,1,3,ms[k],ph);'''
assert s.count(a)==1;s=s.replace(a,b,1);f.write_text(s)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
cmd=json.loads((source/'build.json').read_text())['command'];cmd=[x.replace(str(source),str(out)) for x in cmd]
start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=45,creationflags=0x4000);(out/'compile.log').write_text(c.stdout+c.stderr)
d={'compile_exit':c.returncode,'seconds':time.monotonic()-start,'command':cmd,'sources':{f.name:sha(f) for f in out.iterdir() if f.suffix in ['.c','.inc','.vert','.frag']},'gpu_executed':False,'source_build':str(source/'build.json')}
if c.returncode==0:d['exe_sha256']=sha(out/'gl_selftest_classmips.exe')
(out/'build.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d));raise SystemExit(c.returncode)
