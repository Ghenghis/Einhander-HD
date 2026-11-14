"""Build/link the complete private executable with provenance v2; NEVER run it.

One compiler at a time, below normal, one logical CPU, all source/data on C:.
Retain the proven v58 main/renderer source and inject the new TCP handler into its
frozen diagnostic server. Rebuild full GPU/GTE/PGXP TUs plus the new census TU.
Existing guest/platform objects remain pinned; no foreign code cache is staged.
"""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,time,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v58-frame-phases';v2=r/'remaster-audit/runtime-review/remix-provenance/impl-v2'
out=e/'sampling-build-v60-view-provenance-r2';assert not out.exists();out.mkdir()
shutil.copy2(Path(__file__),out/'executed-build-script.py')
hold_path=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=hold_path.read_bytes();assert json.loads(hold)['owner']=='user-external-project'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);cores=me.cpu_affinity();me.cpu_affinity([cores[-1]])
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
d=json.loads((base/'build.json').read_text());ready=json.loads((v2/'READY.json').read_text());patch=json.loads((v2/'patch-receipt.json').read_text())
receipt={'started_utc':stamp(),'scope':'Complete private executable compile/link from pinned parent inputs plus provenance-v2 full translation units. Not a clean full-source rebuild or executed game.',
 'production_installed':False,'gpu_work':False,'game_launched':False,'guest_code_cache_staged':False,
 'below_normal':True,'logical_cpu_affinity':me.cpu_affinity(),'sequential':True,'commands':[],'builder_sha256':sha(Path(__file__)),
 'parent_runtime_sha256':d['executable_sha256'],'v2_ready_sha256':sha(v2/'READY.json'),'build_complete':False}
env=os.environ.copy()
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:env[key]='1'
try:
 for name,digest in ready['files'].items():assert sha(v2/name)==digest,name
 for name,ref in patch['bases'].items():assert sha(ref['path'])==ref['sha256'],name
 for name,digest in d['sources'].items():assert sha(base/name)==digest,name
 for ref in d['link_inputs']:
  assert Path(ref['path']).drive.upper()=='C:' and sha(ref['path'])==ref['sha256'],ref['path']
 assert sha(d['executable'])==d['executable_sha256']
 inc=out/'include';shutil.copytree(r/'windows-x64/psxrecomp/runtime/include',inc)
 for src in (r/'windows-x64/psxrecomp/runtime/src').iterdir():
  if src.is_file() and src.suffix in ['.h','.inc','.inl']:shutil.copy2(src,inc/src.name)
 # Match the established diagnostic layout, and rebuild its renderer TU too.
 # This is the same header search origin as the pinned v58 compile commands.
 diagnostic_header=Path('C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime/include/gpu_gl_renderer.h')
 shutil.copy2(diagnostic_header,inc/diagnostic_header.name)
 receipt['diagnostic_header_origin']={'path':str(diagnostic_header),'sha256':sha(diagnostic_header),'renderer_rebuilt_with_same_private_header':True}
 for src in base.glob('*.h'):shutil.copy2(src,inc/src.name)
 for src in (v2/'include').glob('*.h'):shutil.copy2(src,inc/src.name)
 srcdir=out/'src';srcdir.mkdir()
 for name in ['gpu.c','gte.cpp','pgxp.cpp','pgxp_view_census.cpp']:shutil.copy2(v2/'src'/name,srcdir/name)
 shutil.copy2(base/'gpu_gl_renderer.c',srcdir/'gpu_gl_renderer.c')
 original=(base/'debug_server.c').read_text();latest=(v2/'src/debug_server.c').read_text()
 begin='/* pgxp_view —';end='/* pgxp — live-tune'
 assert latest.count(begin)==1 and latest.count(end)==1 and original.count(end)==1
 addition=latest[latest.index(begin):latest.index(end)]
 combined=original.replace(end,addition+end,1)
 table='{ "pgxp",              handle_pgxp },';assert combined.count(table)==1
 combined=combined.replace(table,table+'\n    { "pgxp_view",         handle_pgxp_view },',1)
 debug=srcdir/'debug_server.c';debug.write_text(combined,encoding='utf-8')
 receipt['tcp_merge']={'parent_sha256':sha(base/'debug_server.c'),'canonical_v2_sha256':sha(v2/'src/debug_server.c'),
  'injected_handler_sha256':hashlib.sha256(addition.encode()).hexdigest(),'private_combined_sha256':sha(debug),
  'existing_parent_code_preserved':combined.replace(addition,'',1).replace('\n    { "pgxp_view",         handle_pgxp_view },','',1)==original}
 assert receipt['tcp_merge']['existing_parent_code_preserved']
 receipt['sources']={p.relative_to(out).as_posix():sha(p) for p in sorted(srcdir.glob('*'))}
 receipt['headers']={p.relative_to(out).as_posix():sha(p) for p in sorted(inc.glob('*')) if p.is_file()}
 def compile_args(source,obj):
  cpp=source.suffix=='.cpp';template=d['commands'][2 if cpp else 0]['arguments'];args=[template[0],'-I'+str(inc)]
  i=1
  while i<len(template):
   a=template[i]
   if a in ['-MT','-MF','-o','-c']:i+=2;continue
   if a=='-MD':i+=1;continue
   if a.startswith('-I') and ('upload-index-hitch' in a or str(base).lower() in a.lower()):i+=1;continue
   args.append(a);i+=1
  args+=['-MD','-MF',str(obj)+'.d','-c',str(source),'-o',str(obj)]
  return args
 def run(label,args,cwd):
  before=time.monotonic();log=out/(label+'.log');record={'label':label,'arguments':args,'cwd':str(cwd)}
  with log.open('w',encoding='utf-8') as stream:
   proc=subprocess.Popen(args,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x4000)
   child=psutil.Process(proc.pid);child.cpu_affinity(me.cpu_affinity());child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
   try:record['exit']=proc.wait(timeout=90)
   except subprocess.TimeoutExpired:proc.terminate();record['exit']=proc.wait(timeout=5);record['timeout']=True
  record.update(seconds=round(time.monotonic()-before,3),log_sha256=sha(log));receipt['commands'].append(record)
  print(json.dumps({'phase':label,'exit':record['exit'],'seconds':record['seconds']}),flush=True)
  assert record['exit']==0,label+' failed; see '+str(log)
 objects={}
 for source in sorted(srcdir.glob('*')):
  obj=out/(source.name+'.obj');run('compile-'+source.name,compile_args(source,obj),r);objects[source.name]=obj
 replaced={};new_inputs=[]
 wanted={'gpu.c.obj':'gpu.c','debug_server.c.obj':'debug_server.c','gte.cpp.obj':'gte.cpp','pgxp.cpp.obj':'pgxp.cpp','gpu_gl_renderer.c.obj':'gpu_gl_renderer.c'}
 for ref in d['link_inputs']:
  old=Path(ref['path']);name=wanted.get(old.name)
  if name:
   assert name not in replaced;replaced[name]={'old':ref,'new':{'path':str(objects[name]),'sha256':sha(objects[name])}};new_inputs.append(replaced[name]['new'])
  else:new_inputs.append(ref)
 assert set(replaced)==set(wanted.values())
 new_inputs.append({'path':str(objects['pgxp_view_census.cpp']),'sha256':sha(objects['pgxp_view_census.cpp'])})
 link_base=d['commands'][-1];cwd=Path(link_base['cwd']);raw=(base/'Einhander_Recompiled.rsp').read_text();lines=[];rewritten=set()
 for line in raw.splitlines():
  token=line.strip();unquoted=token[1:-1] if token.startswith('"') and token.endswith('"') else token
  path=Path(unquoted);resolved=(path if path.is_absolute() else cwd/path).resolve()
  key=os.path.normcase(str(resolved))
  found=next(((name,entry) for name,entry in replaced.items() if os.path.normcase(str(Path(entry['old']['path']).resolve()))==key),None)
  if found:
   name,entry=found;lines.append('"'+Path(entry['new']['path']).as_posix()+'"');rewritten.add(name)
  else:lines.append(line)
 assert rewritten==set(replaced)
 lines.insert(0,'"'+objects['pgxp_view_census.cpp'].as_posix()+'"')
 response=out/'Einhander_Recompiled.rsp';response.write_text('\n'.join(lines)+'\n')
 linkargs=list(link_base['arguments']);rspindex=next(i for i,x in enumerate(linkargs) if x.startswith('@'));linkargs[rspindex]='@'+str(response)
 exe=out/'Einhander_Recompiled.exe';linkargs[linkargs.index('-o')+1]=str(exe)
 run('link-Einhander_Recompiled',linkargs,cwd)
 for ref in d['link_inputs']:assert sha(ref['path'])==ref['sha256'],'Parent input changed'
 for name,digest in ready['files'].items():assert sha(v2/name)==digest,'v2 changed during build'
 for name,ref in patch['bases'].items():assert sha(ref['path'])==ref['sha256'],'Canonical changed during build'
 assert hold_path.read_bytes()==hold
 receipt.update(link_inputs=new_inputs,replaced_actual_linked_objects=replaced,response_sha256=sha(response),
  executable=str(exe),executable_sha256=sha(exe),build_complete=True,user_gpu_hold_unchanged=True,
  compiler_sha256={x['arguments'][0]:sha(x['arguments'][0]) for x in receipt['commands']},
  limitations=['Compile/link only; no startup or live PGXP coverage.','Existing guest/platform objects retained with pinned hashes; no generated code edited.',
   'Private GPU core rebuilt from reviewed canonical-based v2 source; runtime behavior needs future GPU validation.',
   'No Remix renderer Startup, scene submission, ray tracing or DLSS yet.'])
except Exception as ex:
 receipt['error']=repr(ex);raise
finally:
 receipt['ended_utc']=stamp();(out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (n/'private-runtime-build-result.json').write_text(json.dumps({k:v for k,v in receipt.items() if k not in ['headers','commands','sources','link_inputs','replaced_actual_linked_objects']},indent=2)+'\n')
print(json.dumps({'build_complete':receipt['build_complete'],'executable_sha256':receipt.get('executable_sha256'),'game_launched':False,'gpu_work':False,'objects':len(receipt.get('link_inputs',[]))}),flush=True)
