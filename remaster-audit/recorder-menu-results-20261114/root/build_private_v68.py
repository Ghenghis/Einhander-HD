"""One bounded CPU renderer compile/link; never run the output executable."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import psutil
import subprocess
import time

r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
out=e/'sampling-build-v68-recorder-reserve-r1';base=e/'sampling-build-v67-decode-identity-r3'
old=e/'sampling-build-v67-decode-identity-r2'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
stamp=lambda:dt.datetime.now(dt.timezone.utc).isoformat()
prep=json.loads((out/'prepared.json').read_bytes());parent=json.loads((base/'build.json').read_bytes())
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
if (out/'build.json').exists():raise RuntimeError('Build already attempted; preserve it')
assert sha(base/'build.json')==prep['parent_build_sha256']
for f,h in prep['sources'].items():assert sha(out/f)==h,f
for ref in parent['link_inputs']:assert sha(ref['path'])==ref['sha256'],ref['path']
cpu=psutil.cpu_percent(interval=1);free=psutil.virtual_memory().available/2**30
if cpu>=60 or free<16:
    declined=dict(at_utc=stamp(),cpu_percent=cpu,free_gib=free,declined_before_children=True,gpu_run=False)
    (out/('declined-'+dt.datetime.now(dt.timezone.utc).strftime('%H%M%S')+'.json')).write_text(json.dumps(declined,indent=2)+'\n')
    print(json.dumps(declined));raise SystemExit(3)
started=time.monotonic();deadline=started+90
d=dict(started_utc=stamp(),prepared_sha256=sha(out/'prepared.json'),precheck_cpu=cpu,free_gib=free,
       pid=me.pid,creation_unix=me.create_time(),cpu_affinity=me.cpu_affinity(),below_normal=True,
       commands=[],build_complete=False,game_launched=False,gpu_run=False,installed=False)
def save():
    p=out/'build.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');os.replace(t,p)
def run(label,args,cwd=r):
    before=time.monotonic();remaining=deadline-before
    if remaining<=0:raise TimeoutError('Whole build deadline')
    with (out/(label+'.log')).open('xb') as stream:
        child=subprocess.Popen(args,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08004000)
        identity=psutil.Process(child.pid)
        row=dict(label=label,args=args,cwd=str(cwd),pid=child.pid,creation_unix=identity.create_time(),started_utc=stamp())
        d['commands'].append(row);save()
        try:rc=child.wait(timeout=min(60,remaining))
        except subprocess.TimeoutExpired:
            child.kill();rc=child.wait(timeout=5);row['timeout_killed']=True
    row.update(exit=rc,seconds=time.monotonic()-before,ended_utc=stamp(),owned_handle_exited=child.poll() is not None)
    save()
    if rc:raise RuntimeError(label+' exit '+str(rc))
try:
    old_build=json.loads((old/'build.json').read_bytes())
    command=next(c for c in old_build['commands'] if c['label']=='compile-gpu_gl_renderer.c')
    args=[];i=0
    while i<len(command['args']):
        item=command['args'][i]
        if item in ['-o','-c','-MT','-MF']:i+=2;continue
        if item=='-MD':i+=1;continue
        for folder in ['src','include']:
            if item=='-I'+str(old/folder):item='-I'+str(out/folder)
        args.append(item);i+=1
    obj=out/'gpu_gl_renderer.c.obj'
    args+=['-MD','-MF',str(obj)+'.d','-c',str(out/'src/gpu_gl_renderer.c'),'-o',str(obj)]
    run('compile-gpu_gl_renderer.c',args)
    replacement=next(ref for ref in parent['link_inputs'] if Path(ref['path']).name=='gpu_gl_renderer.c.obj')
    link=next(c for c in parent['commands'] if c['label']=='link');cwd=Path(link['cwd'])
    lines=[];count=0
    for line in (base/'Einhander_Recompiled.rsp').read_text().splitlines():
        p=Path(line.strip().strip('"'));absolute=(p if p.is_absolute() else cwd/p).resolve()
        if os.path.normcase(str(absolute))==os.path.normcase(str(Path(replacement['path']).resolve())):
            lines.append('"'+obj.as_posix()+'"');count+=1
        else:lines.append(line)
    assert count==1
    rsp=out/'Einhander_Recompiled.rsp';rsp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    args=list(link['args']);args[next(i for i,a in enumerate(args) if a.startswith('@'))]='@'+str(rsp)
    exe=out/'Einhander_Recompiled.exe';args[args.index('-o')+1]=str(exe)
    run('link',args,cwd)
    for f,h in prep['sources'].items():assert sha(out/f)==h,f
    for ref in parent['link_inputs']:assert sha(ref['path'])==ref['sha256'],ref['path']
    d.update(build_complete=True,executable=str(exe),executable_sha256=sha(exe),
        freshly_rebuilt_tus=1,retained_link_inputs=len(parent['link_inputs'])-1,
        link_inputs=[dict(path=str(obj),sha256=sha(obj)) if ref is replacement else ref for ref in parent['link_inputs']],
        complete_source_rebuild=False,live_qualified=False)
except Exception as error:d['error']=repr(error);raise
finally:
    d['ended_utc']=stamp();d['elapsed_seconds']=time.monotonic()-started;save()
print(json.dumps({k:v for k,v in d.items() if k not in ('commands','link_inputs')}))
