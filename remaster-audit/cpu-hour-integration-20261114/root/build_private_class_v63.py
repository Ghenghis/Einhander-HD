"""Link frozen v4 into an isolated v61-derived executable, CPU only."""
from pathlib import Path
import datetime, hashlib, json, os, psutil, shutil, subprocess, time
r=Path('C:/github/Einhander'); n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v61-view-metrics-r2'
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v4'
rd=f/'host-run/20261114T114326Z'
out=e/'sampling-build-v63-classmip-r1'; out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
parent=json.loads((base/'build.json').read_text())
assert sha(parent['executable'])==parent['executable_sha256']=='c6e573f317e5faaa624612320c5468ed8e0158092b4e53e3a0357e607e325686'
assert sha(f/'READY.json')=='93a97669e6d9cf5fbd75536d5261efbe5855f1299bb91683badea4f7a395299e'
for ref in parent['link_inputs']: assert Path(ref['path']).drive.upper()=='C:' and sha(ref['path'])==ref['sha256']
for name,h in parent['headers'].items(): assert sha(base/name)==h
for name,h in parent['sources'].items(): assert sha(base/name)==h
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity(me.cpu_affinity()[-1:])
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED'; hold=marker.read_bytes()
src=out/'src'; src.mkdir(); inc=out/'include'; shutil.copytree(base/'include',inc)
shutil.copy2(rd/'patched/gpu_gl_renderer.c',src/'gpu_gl_renderer.c')
shutil.copy2(rd/'patched/hd_class_mips.inc',src/'hd_class_mips.inc')
assert sha(src/'gpu_gl_renderer.c')=='b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16'
debug=(base/'src/debug_server.c').read_text()
handler='''/* PRIVATE read-only scoped class-mip/RGB admission counters. No state writes. */
extern int gl_renderer_class_mips_counters(uint64_t *out, int cap);
static void handle_hd_class_mips(int id,const char *json) {
    (void)json; uint64_t v[64]={0}; char values[1800]; size_t pos=0;
    int count=gl_renderer_class_mips_counters(v,64);
    for(int i=0;i<count;i++) {
        int wrote=snprintf(values+pos,sizeof(values)-pos,"%s%llu",i?",":"",(unsigned long long)v[i]);
        if(wrote<0 || (size_t)wrote>=sizeof(values)-pos) { send_fmt("{\\"id\\":%d,\\"ok\\":false}",id); return; }
        pos+=(size_t)wrote;
    }
    values[pos]=0;
    send_fmt("{\\"id\\":%d,\\"ok\\":true,\\"schema\\":\\"hdcm-v4-counters\\",\\"values\\":[%s]}",id,values);
}

'''
a='/* pgxp_view —'; assert debug.count(a)==1; debug=debug.replace(a,handler+a,1)
a='    { "pgxp_view",         handle_pgxp_view },'; assert debug.count(a)==1
debug=debug.replace(a,a+'\n    { "hd_class_mips",      handle_hd_class_mips },',1)
(src/'debug_server.c').write_text(debug)
receipt=dict(started_utc=stamp(),scope='Private executable: frozen v4 renderer plus read-only counter RPC; retain pinned v61 guest/core/platform link inputs. Not a clean full-source build or production installation.',commands=[],
             parent_exe_sha256=parent['executable_sha256'],source_hashes={p.relative_to(out).as_posix():sha(p) for p in src.iterdir()},headers=parent['headers'],
             cpu_affinity=me.cpu_affinity(),below_normal=True,build_complete=False,game_launched=False,gpu_work=False,
             supersedes='v62 RGB-only is unlaunched and retired: broad scope, added fprintf, overcounting; v4 scoped semantics authoritative',
             default_off_env=['PSXRECOMP_HD_CLASS_MIPS=1','PSXRECOMP_HD_RGB_EDGES=1'],both_require='PSXRECOMP_HD_CLASS_MIPS_DIR with identity-bound sidecars')
def run(label,args,cwd):
    log=out/(label+'.log'); t=time.monotonic()
    with log.open('w') as dest:
        p=subprocess.Popen(args,cwd=cwd,stdout=dest,stderr=subprocess.STDOUT,creationflags=0x4000)
        try: rc=p.wait(timeout=90)
        except subprocess.TimeoutExpired: p.terminate(); rc=p.wait(timeout=5)
    receipt['commands'].append(dict(label=label,arguments=args,cwd=str(cwd),exit=rc,seconds=time.monotonic()-t,log_sha256=sha(log)))
    print(json.dumps(dict(label=label,exit=rc,seconds=time.monotonic()-t)),flush=True)
    assert rc==0,label
try:
    objects={}
    for source in sorted(src.glob('*.c')):
        old=next(c for c in parent['commands'] if c['label']=='compile-'+source.name)
        args=[]; i=0
        while i<len(old['arguments']):
            a=old['arguments'][i]
            if a in ['-o','-c','-MT','-MF']: i+=2; continue
            if a=='-MD' or a=='-I'+str(base/'include'): i+=1; continue
            args.append(a); i+=1
        obj=out/(source.name+'.obj'); args.insert(1,'-I'+str(inc))
        args+=['-MD','-MF',str(obj)+'.d','-c',str(source),'-o',str(obj)]
        run('compile-'+source.name,args,r); objects[source.name+'.obj']=obj
    inputs=[]; replaced={}
    for ref in parent['link_inputs']:
        name=Path(ref['path']).name
        if name in objects:
            assert name not in replaced
            replaced[name]=(ref,objects[name]); inputs.append(dict(path=str(objects[name]),sha256=sha(objects[name])))
        else: inputs.append(ref)
    assert len(replaced)==2
    link=parent['commands'][-1]; cwd=Path(link['cwd']); lines=[]; count=0
    for line in (base/'Einhander_Recompiled.rsp').read_text().splitlines():
        token=line.strip().strip('"'); p=Path(token); full=(p if p.is_absolute() else cwd/p).resolve()
        pair=next((v for v in replaced.values() if os.path.normcase(str(Path(v[0]['path']).resolve()))==os.path.normcase(str(full))),None)
        if pair: lines.append('"'+pair[1].as_posix()+'"'); count+=1
        else: lines.append(line)
    assert count==2
    rsp=out/'Einhander_Recompiled.rsp'; rsp.write_text('\n'.join(lines)+'\n')
    args=list(link['arguments']); args[next(i for i,a in enumerate(args) if a.startswith('@'))]='@'+str(rsp)
    exe=out/'Einhander_Recompiled.exe'; args[args.index('-o')+1]=str(exe)
    run('link',args,cwd)
    for ref in parent['link_inputs']: assert sha(ref['path'])==ref['sha256']
    assert marker.read_bytes()==hold
    receipt.update(build_complete=True,executable=str(exe),executable_sha256=sha(exe),link_inputs=inputs,response_sha256=sha(rsp),user_gpu_hold_unchanged=True)
except Exception as ex: receipt['error']=repr(ex); raise
finally:
    receipt['ended_utc']=stamp(); (out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    shutil.copy2(__file__,out/'executed-build-script.py')
print(json.dumps(dict(build_complete=receipt['build_complete'],executable_sha256=receipt.get('executable_sha256'))))
