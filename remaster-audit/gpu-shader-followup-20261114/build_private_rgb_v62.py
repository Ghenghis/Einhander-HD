from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,time,os,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v61-view-metrics-r2';out=e/'sampling-build-v62-rgb-edges-r1';out.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest();stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
parent=json.loads((base/'build.json').read_text());assert parent['executable_sha256']=='c6e573f317e5faaa624612320c5468ed8e0158092b4e53e3a0357e607e325686'
assert sha(parent['executable'])==parent['executable_sha256']
for ref in parent['link_inputs']:assert Path(ref['path']).drive.upper()=='C:' and sha(ref['path'])==ref['sha256'],ref['path']
for name,h in parent['headers'].items():assert sha(base/name)==h,name
for name,h in parent['sources'].items():assert sha(base/name)==h,name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
src=out/'src';src.mkdir();inc=out/'include';shutil.copytree(base/'include',inc)
renderer=(base/'src/gpu_gl_renderer.c').read_text();original=renderer
assert sha(base/'src/gpu_gl_renderer.c')=='90c6a4e15d8e956ca7be28f1cd5219add1e1c2ee37f31fbd361711db0510e3a1'
fragment=(n/'rgb-edge-gpu-r4/HD_FS.frag').read_text();assert sha(n/'rgb-edge-gpu-r4/HD_FS.frag')=='5b3929b51b6cf71dd84c8dfb11ec176dee4b59c50a3c692309841511d25ff34b'
helper=fragment[fragment.index('// PRIVATE RGB-only experiment.'):fragment.index('void main(){')]
begin='  if(u_hd_rgb_edges!=0 && u_filter!=0 && u_hd_facade_motion==0 && !native_edge) {'
branch=fragment[fragment.index(begin):fragment.index('  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}')]
cstrings=lambda s:''.join('    '+json.dumps(line+'\n')+'\n' for line in s.splitlines())
start=renderer.index('static const char *HD_FS =');end=renderer.index('    "}\\n";',start)+len('    "}\\n";');block=renderer[start:end];oldblock=block
a='    "void main(){\\n"\n';assert block.count(a)==1;block=block.replace(a,cstrings(helper)+a,1)
a='    "  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}\\n"\n';assert block.count(a)==1;block=block.replace(a,cstrings(branch)+a,1)
assert block.replace(cstrings(helper),'',1).replace(cstrings(branch),'',1)==oldblock
renderer=renderer[:start]+block+renderer[end:]
global_code='''static GLint s_hd_uRgbEdges = -1;
static int s_hd_rgb_edges_enabled;
static uint64_t s_hd_rgb_edges_draw_calls;
int gl_renderer_rgb_edges_counters(uint64_t *out,int cap);
int gl_renderer_rgb_edges_counters(uint64_t *out,int cap) {
    if(!out || cap<2)return 0;
    out[0]=(uint64_t)s_hd_rgb_edges_enabled;out[1]=s_hd_rgb_edges_draw_calls;return 2;
}
'''
a='static GLint s_hd_uFacadeMotion = -1;\n';assert renderer.count(a)==1;renderer=renderer.replace(a,a+global_code,1)
a='        s_hd_uFacadeMotion = p_glGetUniformLocation(s_hd_prog,"u_hd_facade_motion");\n';assert renderer.count(a)==1
renderer=renderer.replace(a,a+'        s_hd_uRgbEdges = p_glGetUniformLocation(s_hd_prog,"u_hd_rgb_edges");\n',1)
a='        p_glUniform1i(s_hd_uFacadeMotion,0);\n';assert renderer.count(a)==1
renderer=renderer.replace(a,a+'''        { const char *value=getenv("PSXRECOMP_HD_RGB_EDGES");
          s_hd_rgb_edges_enabled=value && strcmp(value,"1")==0;
          p_glUniform1i(s_hd_uRgbEdges,s_hd_rgb_edges_enabled);
          fprintf(stderr,"[hd_rgb_edges] enabled=%d; filtered level0 RGB only; class/STP unchanged\\n",s_hd_rgb_edges_enabled); }
''',1)
a='        p_glUniform1i(s_hd_uHd, 0);\n';assert renderer.count(a)==1;renderer=renderer.replace(a,'        if(s_hd_rgb_edges_enabled && s_tex_filter)++s_hd_rgb_edges_draw_calls;\n'+a,1)
(src/'gpu_gl_renderer.c').write_text(renderer)
debug=(base/'src/debug_server.c').read_text();original_debug=debug
handler='''/* PRIVATE read-only RGB-edge mode/draw-assignment diagnostic. */
extern int gl_renderer_rgb_edges_counters(uint64_t *out,int cap);
static void handle_hd_rgb_edges(int id,const char *json) {
    (void)json;uint64_t values[2]={0,0};int count=gl_renderer_rgb_edges_counters(values,2);
    send_fmt("{\\"id\\":%d,\\"ok\\":%s,\\"enabled\\":%llu,\\"filtered_hd_draw_calls\\":%llu}",id,count==2?"true":"false",(unsigned long long)values[0],(unsigned long long)values[1]);
}

'''
a='/* pgxp_view —';assert debug.count(a)==1;debug=debug.replace(a,handler+a,1)
a='    { "pgxp_view",         handle_pgxp_view },';assert debug.count(a)==1
table='\n    { "hd_rgb_edges",      handle_hd_rgb_edges },';debug=debug.replace(a,a+table,1)
assert debug.replace(handler,'',1).replace(table,'',1)==original_debug
(src/'debug_server.c').write_text(debug)
receipt={'started_utc':stamp(),'scope':'Private complete executable link: rebuild renderer/debug TUs only from frozen v61; retain pinned guest/core/platform objects. No canonical change, game launch, foreign cache or production installation.', 'parent_exe_sha256':parent['executable_sha256'],'commands':[],'source_hashes':{f.relative_to(out).as_posix():sha(f) for f in src.iterdir()},'headers':parent['headers'],'cpu_affinity':me.cpu_affinity(),'below_normal':True,'default_off_env':'PSXRECOMP_HD_RGB_EDGES=1','build_complete':False,'game_launched':False,'gpu_work':False,'shader_experiment_sha256':sha(n/'rgb-edge-gpu-r4/HD_FS.frag')}
def run(label,args,cwd):
 log=out/(label+'.log');start=time.monotonic()
 with log.open('w') as f:
  process=subprocess.Popen(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,creationflags=0x4000)
  try:rc=process.wait(timeout=90)
  except subprocess.TimeoutExpired:process.terminate();rc=process.wait(timeout=5)
 receipt['commands'].append({'label':label,'arguments':args,'cwd':str(cwd),'exit':rc,'seconds':time.monotonic()-start,'log_sha256':sha(log)})
 print(json.dumps({'phase':label,'exit':rc,'seconds':receipt['commands'][-1]['seconds']}),flush=True);assert rc==0,label
try:
 objects={}
 for source in sorted(src.iterdir()):
  old=next(c for c in parent['commands'] if c['label']=='compile-'+source.name);args=[];i=0
  while i<len(old['arguments']):
   a=old['arguments'][i]
   if a in ['-o','-c','-MT','-MF']:i+=2;continue
   if a=='-MD':i+=1;continue
   if a=='-I'+str(base/'include'):i+=1;continue
   args.append(a);i+=1
  obj=out/(source.name+'.obj');args.insert(1,'-I'+str(inc));args+=['-MD','-MF',str(obj)+'.d','-c',str(source),'-o',str(obj)]
  run('compile-'+source.name,args,r);objects[source.name+'.obj']=obj
 inputs=[];replaced={}
 for ref in parent['link_inputs']:
  name=Path(ref['path']).name
  if name in objects:
   assert name not in replaced;replaced[name]=(ref,objects[name]);inputs.append({'path':str(objects[name]),'sha256':sha(objects[name])})
  else:inputs.append(ref)
 assert len(replaced)==2
 link=parent['commands'][-1];cwd=Path(link['cwd']);lines=[];count=0
 for line in (base/'Einhander_Recompiled.rsp').read_text().splitlines():
  token=line.strip().strip('"');f=Path(token);full=(f if f.is_absolute() else cwd/f).resolve()
  pair=next((v for v in replaced.values() if os.path.normcase(str(Path(v[0]['path']).resolve()))==os.path.normcase(str(full))),None)
  if pair:lines.append('"'+pair[1].as_posix()+'"');count+=1
  else:lines.append(line)
 assert count==2
 rsp=out/'Einhander_Recompiled.rsp';rsp.write_text('\n'.join(lines)+'\n')
 args=list(link['arguments']);args[next(i for i,a in enumerate(args) if a.startswith('@'))]='@'+str(rsp)
 exe=out/'Einhander_Recompiled.exe';args[args.index('-o')+1]=str(exe);run('link',args,cwd)
 for ref in parent['link_inputs']:assert sha(ref['path'])==ref['sha256'],ref['path']
 for name,h in parent['sources'].items():assert sha(base/name)==h,name
 receipt.update(build_complete=True,executable=str(exe),executable_sha256=sha(exe),link_inputs=inputs,response_sha256=sha(rsp))
except Exception as ex:receipt['error']=repr(ex);raise
finally:
 receipt['ended_utc']=stamp();(out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-build-script.py')
print(json.dumps({'build_complete':receipt['build_complete'],'executable_sha256':receipt.get('executable_sha256')}))
