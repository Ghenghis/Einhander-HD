import json,subprocess,hashlib,shutil
from pathlib import Path
R=Path('C:/github/Einhander'); E=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112'; O=E/'sampling-build-v58-frame-phases'; P=E/'sampling-build-v57-native-upload'; B=R/'windows-x64/build-ss8c'; W=Path('C:/github/Einhander-wt/upload-index-hitch'); L=R/'remaster-audit/runtime-review/frame-phase-ring'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(p): return str(p).replace(chr(92),'/')
parent=json.loads((P/'build.json').read_bytes()); assert sha(parent['executable'])==parent['executable_sha256']=='efde4724c391bed59393e16573e5831999848fb261e9dad5ca88061f3d75656d'
for row in parent['link_inputs']: assert sha(row['path'])==row['sha256'],row['path']
receipt=json.loads((L/'patch-receipt.json').read_bytes())
source_names=[n for n in receipt if n.endswith(('.cpp','.c','.h')) and (L/'new'/n).is_file()]
assert all(n in source_names for n in ['main.cpp','gpu_gl_renderer.c','debug_server.c'])
for name in source_names:
 src=L/'new'/name; assert sha(src)==receipt[name]['new_sha256']; shutil.copy2(src,O/name); assert sha(O/name)==receipt[name]['new_sha256']
for name in ['hd_upload_ledger.h','native_upload_ledger.h']:
 if name not in source_names: shutil.copy2(P/name,O/name)
 assert sha(O/name)==sha(P/name)
r={'scope':'v57 exact parent inputs with opt-in CPU-only per-frame phase timestamps; no timing or render behavior change','production_installed':False,'parent_runtime_sha256':parent['executable_sha256'],'patch_receipt':receipt,'sources':{n:sha(O/n) for n in source_names+['native_upload_ledger.h','hd_upload_ledger.h']},'commands':[]}
def save(): (O/'build.json').write_text(json.dumps(r,indent=2)+'\n')
def run(a,label,cwd):
 with (O/(label+'.log')).open('w') as log: p=subprocess.run(a,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 r['commands'].append(dict(label=label,arguments=a,cwd=str(cwd),exit=p.returncode)); save(); print(label,p.returncode,flush=True)
 if p.returncode: raise RuntimeError((O/(label+'.log')).read_text()[-4000:])
recipes=json.loads((E/'sampling-build-v47-attrib/build.json').read_bytes())['commands']
for name in ['gpu_gl_renderer.c','debug_server.c','main.cpp']:
 a=next(c['arguments'] for c in recipes if c['label']==('compile-runtime-main' if name=='main.cpp' else 'compile-'+name)).copy(); a=[norm(x).replace('D:/Games/Einhander',norm(R)) for x in a if 'psx_libchdr-src/include' not in norm(x)]
 a[a.index('-c')+1]=str(O/name); a[a.index('-o')+1]=str(O/(name+'.obj'))
 for flag,suffix in [('-MF','.obj.d'),('-MT','.obj')]:
  if flag in a: a[a.index(flag)+1]=str(O/(name+suffix))
 a[1:1]=['-I'+str(O),'-I'+str(W/'windows-x64/psxrecomp/runtime/include'),'-I'+str(W/'windows-x64/psxrecomp/runtime/src')]; run(a,'compile-'+name,R)
new=[]; inputs=[]; replaced=[]
for line in (P/'Einhander_Recompiled.rsp').read_text().splitlines():
 old=norm(line.strip().strip(chr(34))); q=old
 if old==norm(P/'gpu_gl_renderer.c.obj'): q=norm(O/'gpu_gl_renderer.c.obj')
 if old==norm(P/'debug_server.c.obj'): q=norm(O/'debug_server.c.obj')
 if old==norm(E/'sampling-build-v48-upload-index'/'runtime-main.cpp.obj'): q=norm(O/'main.cpp.obj')
 if q!=old: replaced.append(dict(old=old,old_sha256=sha(old),new=q,new_sha256=sha(q)))
 if q.endswith(('.obj','.o','.a','.lib')):
  f=Path(q); f=f if f.is_absolute() else B/f; assert f.is_file(); inputs.append(dict(path=str(f),sha256=sha(f)))
 new.append(chr(34)+q+chr(34))
assert len(replaced)==3 and len(inputs)==len(parent['link_inputs'])==151
rsp=O/'Einhander_Recompiled.rsp'; rsp.write_text('\n'.join(new)+'\n'); r.update(link_inputs=inputs,replaced_actual_linked_objects=replaced,response_sha256=sha(rsp)); save()
cc=next(c['arguments'][0] for c in reversed(parent['commands']) if c['label'].startswith('link-Einhander_Recompiled') and c['exit']==0); exe=O/'Einhander_Recompiled.exe'; run([cc,'-O3','-static','-Wl,--stack,67108864','@'+str(rsp),'-o',str(exe)],'link-Einhander_Recompiled',B)
r.update(executable=str(exe),executable_sha256=sha(exe),build_complete=True); save(); print(json.dumps(dict(executable_sha256=r['executable_sha256'],inputs=len(inputs))),flush=True)
