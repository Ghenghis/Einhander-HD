from pathlib import Path
import hashlib,json,re,ast,subprocess,psutil
p=Path(__file__).resolve().parent;e=p.parents[2]/'remaster-audit/dev-center-evidence/stage1-completion-20261112';out=e/'sampling-build-v62-rgb-edges-r1'
d=json.loads((out/'build.json').read_text());c=next(x for x in d['commands'] if x['label']=='compile-gpu_gl_renderer.c');args=[];i=0
while i<len(c['arguments']):
 a=c['arguments'][i]
 if a in ['-c','-o','-MF','-MT']:i+=2;continue
 if a=='-MD':i+=1;continue
 args.append(a);i+=1
args+=['-E','-P',str(out/'src/gpu_gl_renderer.c')]
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
run=subprocess.run(args,cwd=c['cwd'],capture_output=True,text=True,timeout=30,creationflags=0x4000);assert run.returncode==0,run.stderr
match=re.search(r'static const char \*HD_FS\s*=\s*((?:\s*"(?:[^"\\]|\\.)*")+)(?:\s*;)',run.stdout);assert match
shader=''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"',match.group(1)))
(out/'HD_FS.frag').write_text(shader)
ref=(p/'rgb-edge-gpu-r4/HD_FS.frag').read_text()
ref=re.sub(r'^uniform int u_hd_class_levels;[^\n]*\n','',ref,flags=re.M)
begin=ref.index('  /* PRIVATE opt-in class-aware levels:');end=ref.index('  bool native_edge=',begin);ref=ref[:begin]+ref[end:]
begin=ref.index('  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion!=0');end=ref.index('  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion==0',begin);ref=ref[:begin]+ref[end:]
def tokens(s):
 s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
 return re.findall(r'[A-Za-z_]\w*|\d+(?:\.\d*)?|[^\s]',s)
same=tokens(shader)==tokens(ref)
receipt={'preprocess_exit':run.returncode,'game_shader_sha256':hashlib.sha256(shader.encode()).hexdigest(),'gpu_reference_sha256':hashlib.sha256((p/'rgb-edge-gpu-r4/HD_FS.frag').read_bytes()).hexdigest(),'removed_only_class_mip_branches_from_gpu_reference':True,'rgb_only_tokens_equal':same,'game_shader_tokens':len(tokens(shader)),'reference_tokens':len(tokens(ref)),'scope':'Compiled private game shader matches GPU-tested ordinary level0 RGB branch after removing unrelated class-mip paths. Does not qualify full gameplay.'}
(out/'shader-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));assert same
