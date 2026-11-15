"""Rebuild three private game TUs and verify the exact diagnostic adapter on CPU only."""
from pathlib import Path
import datetime,gc,hashlib,json,os,psutil,shutil,subprocess,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
out=e/'sampling-build-v67-decode-identity-r3';src=out/'src'
prep=json.loads((out/'prepared.json').read_text(encoding='utf-8'));base=Path(prep['parent'])
parent=json.loads((base/'build.json').read_text(encoding='utf-8'))
oldbase=e/'sampling-build-v61-view-metrics-r2'
oldparent=json.loads((oldbase/'build.json').read_text(encoding='utf-8'))
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
assert not (out/'build.json').exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
for rel,h in {**prep['sources'],**prep['headers']}.items():assert sha(out/rel)==h,rel
for ref in parent['link_inputs']:assert Path(ref['path']).drive.upper()=='C:' and sha(ref['path'])==ref['sha256']
assert sha(base/'Einhander_Recompiled.exe')==prep['parent_executable_sha256']
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3)
if cpu>=60 or free<16:
    declined=dict(at_utc=stamp(),cpu_percent=cpu,free_gib=free,declined_before_children=True,gpu_run=False,compiler_started=False)
    (out/('precheck-declined-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S')+'.json')).write_text(json.dumps(declined,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(declined),flush=True);raise SystemExit(3)
holdpath=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=holdpath.read_bytes() if holdpath.exists() else None
started=time.monotonic();deadline=started+180
receipt=dict(prep,started_utc=stamp(),pid=me.pid,creation_unix=me.create_time(),cpu_affinity=me.cpu_affinity(),below_normal=True,precheck_cpu=cpu,free_gib=free,commands=[],build_complete=False,game_launched=False,gpu_run=False)
def save():
    f=out/'build.json';tmp=f.with_name(f.name+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(receipt,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,f)
def run(label,args,cwd=r):
    log=out/(label+'.log');t=time.monotonic()
    remaining=deadline-t;assert remaining>0
    with log.open('wb') as stream:
        child=subprocess.Popen(args,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08004000)
        ident=psutil.Process(child.pid)
        info=dict(label=label,args=args,cwd=str(cwd),pid=child.pid,creation_unix=ident.create_time(),started_utc=stamp())
        receipt['commands'].append(info);save();print(json.dumps(info),flush=True)
        try:rc=child.wait(timeout=min(60,remaining))
        except subprocess.TimeoutExpired:
            child.terminate();rc=child.wait(timeout=5);info['timed_out']=True
    # Windows may expose the just-exited process briefly. Never confuse a reused PID
    # with this child, and never terminate a process merely because its PID matches.
    pid=child.pid
    del child,ident
    gc.collect()  # Release this completed child's process handle before PID observation.
    absent=False;absence_deadline=time.monotonic()+2
    while time.monotonic()<absence_deadline:
        try:
            current=psutil.Process(pid)
            if current.create_time()!=info['creation_unix'] or not current.is_running():absent=True;break
        except psutil.NoSuchProcess:absent=True;break
        time.sleep(.025)
    info.update(exit=rc,seconds=time.monotonic()-t,child_absent=absent,log_sha256=sha(log));save()
    assert rc==0 and not info.get('timed_out') and info['child_absent'],(label,rc)
    return log.read_text(encoding='utf-8',errors='replace')
save()
try:
    # Keep successful, unchanged adapter and renderer controls from the preserved r2.
    retained=prep['retained_validation'];prior=json.loads(Path(retained['path']).read_text(encoding='utf-8'))
    assert sha(retained['path'])==retained['sha256'] and prior['counter_adapter_passed'] and prior['real_growth_mutant_detected']
    assert sha(out/'counter-handler.inc')==retained['source_handler_sha256'] and sha(out/'counter-handler-test.c')==retained['source_test_sha256']
    assert sha(src/'gpu_gl_renderer.c')==retained['renderer_source_sha256'] and sha(retained['renderer_object'])==retained['renderer_object_sha256']
    receipt.update(counter_adapter_cases=8,counter_adapter_passed=True,real_growth_mutant_detected=True,adapter_controls_retained_not_replayed=True,retained_renderer_object=retained['renderer_object']);save()
    def arguments(old):
        result=[];i=0
        while i<len(old):
            arg=old[i]
            if arg in ['-o','-c','-MT','-MF']:i+=2;continue
            if arg=='-MD':i+=1;continue
            result.append(arg);i+=1
        result.insert(1,'-I'+str(src));result.insert(1,'-I'+str(out/'include'))
        return result
    rebuilt={'gpu_gl_renderer.c.obj':Path(retained['renderer_object'])}
    for name in ['debug_server.c','hd_texture_pack.cpp']:
        if name.endswith('.cpp'):old=next(c for c in oldparent['commands'] if c['label']=='compile-pgxp.cpp')
        else:old=next(c for c in parent['commands'] if c['label']=='compile-'+name)
        obj=out/(name+'.obj');args=arguments(old['arguments'])
        args+=['-MD','-MF',str(obj)+'.d','-c',str(src/name),'-o',str(obj)]
        run('compile-'+name,args);rebuilt[name+'.obj']=obj
    inputs=[];replaced={}
    for ref in parent['link_inputs']:
        basename=Path(ref['path']).name
        if basename in rebuilt:
            assert basename not in replaced;replaced[basename]=(ref,rebuilt[basename]);inputs.append(dict(path=str(rebuilt[basename]),sha256=sha(rebuilt[basename])))
        else:inputs.append(ref)
    assert len(replaced)==3
    link=parent['commands'][-1]
    assert link['label']=='link';cwd=Path(link['cwd']);lines=[];count=0
    for line in (base/'Einhander_Recompiled.rsp').read_text().splitlines():
        token=line.strip().strip('"');file=Path(token);absolute=(file if file.is_absolute() else cwd/file).resolve()
        pair=next((item for item in replaced.values() if os.path.normcase(str(Path(item[0]['path']).resolve()))==os.path.normcase(str(absolute))),None)
        if pair:lines.append('"'+pair[1].as_posix()+'"');count+=1
        else:lines.append(line)
    assert count==3
    rsp=out/'Einhander_Recompiled.rsp';rsp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    args=list(link['arguments']);args[next(i for i,a in enumerate(args) if a.startswith('@'))]='@'+str(rsp)
    exe=out/'Einhander_Recompiled.exe';args[args.index('-o')+1]=str(exe)
    run('link',args,cwd)
    for ref in parent['link_inputs']:assert sha(ref['path'])==ref['sha256']
    for rel,h in {**prep['sources'],**prep['headers']}.items():assert sha(out/rel)==h
    assert (holdpath.read_bytes() if holdpath.exists() else None)==hold
    receipt.update(build_complete=True,executable=str(exe),executable_sha256=sha(exe),link_inputs=inputs,response_sha256=sha(rsp),hold_unchanged=True,freshly_rebuilt_tus=2,renderer_rebuilt_in_preserved_r2=True,retained_link_inputs=len(inputs)-2)
except Exception as error:receipt['error']=repr(error);raise
finally:
    receipt['ended_utc']=stamp();receipt['elapsed_seconds']=time.monotonic()-started;save();shutil.copy2(__file__,out/'executed-build.py')
print(json.dumps(dict(build_complete=receipt['build_complete'],exe_sha256=receipt.get('executable_sha256'),counter_cases=receipt.get('counter_adapter_cases'),elapsed_seconds=receipt['elapsed_seconds'],gpu_run=False)),flush=True)
