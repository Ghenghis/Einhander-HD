from pathlib import Path
import hashlib,json,shutil,subprocess,time,psutil
p=Path(__file__).resolve().parent;source=p/'rgb-edge-gpu-r3';out=p/'rgb-edge-gpu-r4';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for name in ['HD_FS.frag','TEX_VS.vert','hd_class_mips.inc','gl_selftest_classmips.c']:shutil.copy2(source/name,out/name)
f=out/'HD_FS.frag';s=f.read_text();anchor='  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}'
add='''  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion==0 && !native_edge) {
    vec4 edge0=hd_visible_rgb(rgb_pos,0);
    if(edge0.a>1e-8 && edge0.a<0.999999)c.rgb=edge0.rgb;
  }
'''
assert s.count(anchor)==1;s=s.replace(anchor,add+anchor,1);f.write_text(s)
f=out/'gl_selftest_classmips.c';s=f.read_text();a='pUniform1i(pGetUniformLocation(g_prog, "u_hd_facade_motion"), 1);';assert s.count(a)==1;s=s.replace(a,a.replace(', 1);',', 0);'),1)
a='pUniform1i(pGetUniformLocation(g_prog, "u_hd_rgb_edges"), g_rgb_edges);';assert s.count(a)==1;s=s.replace(a,a.replace('g_rgb_edges);','g_rgb_edges && class_levels>0);'),1);f.write_text(s)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
cmd=json.loads((source/'build.json').read_text())['command'];cmd=[x.replace(str(source),str(out)) for x in cmd]
start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=45,creationflags=0x4000);(out/'compile.log').write_text(c.stdout+c.stderr)
d={'compile_exit':c.returncode,'seconds':time.monotonic()-start,'command':cmd,'sources':{f.name:sha(f) for f in out.iterdir() if f.suffix in ['.c','.inc','.vert','.frag']},'gpu_executed':False,'source_build':str(source/'build.json')}
if c.returncode==0:d['exe_sha256']=sha(out/'gl_selftest_classmips.exe')
(out/'build.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'compile_exit':c.returncode,'exe_sha256':d.get('exe_sha256')}));raise SystemExit(c.returncode)
