"""Existing tracker/save-state/decode tests against the exact new game pack object."""
from pathlib import Path
import datetime,gc,hashlib,json,os,psutil,shutil,subprocess,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
game=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v67-decode-identity-r3'
build=json.loads((game/'build.json').read_text(encoding='utf-8'));assert build['build_complete']
out=n/'v67-pack-regressions-r1'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3)
if cpu>=60 or free<16:
    declined=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cpu_percent=cpu,free_gib=free,declined_before_children=True)
    (n/('pack-regression-declined-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S')+'.json')).write_text(json.dumps(declined,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(declined));raise SystemExit(3)
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
layout=out/'test-sources'
for d in ['tests','src','third_party','include']:(layout/d).mkdir(parents=True,exist_ok=True)
testnames=['hd_texture_pack_test.cpp','test_hd_texture_pack.cpp']
sources={}
for name in testnames:
    p=r/'windows-x64/psxrecomp/runtime/tests'/name;shutil.copy2(p,layout/'tests'/name);sources[str(p)]=sha(p)
for source,destination in [(r/'windows-x64/psxrecomp/runtime/src/png_write.h',layout/'src/png_write.h'),(game/'third_party/stb_image.h',layout/'third_party/stb_image.h'),(game/'include/hd_texture_pack.h',layout/'include/hd_texture_pack.h')]:
    shutil.copy2(source,destination);sources[str(source)]=sha(source)
pack=game/'hd_texture_pack.cpp.obj'
assert next(x['sha256'] for x in build['link_inputs'] if x['path']==str(pack))==sha(pack)
temp=out/'fixture-temp';temp.mkdir();assert temp.resolve().is_relative_to(out.resolve())
env0={k:v for k,v in os.environ.items() if not k.startswith('PSXRECOMP_HD_')}
env0.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',TEMP=str(temp),TMP=str(temp))
start=time.monotonic();deadline=start+180;rows=[]
receipt=dict(started_utc=stamp(),pid=me.pid,creation_unix=me.create_time(),affinity=me.cpu_affinity(),below_normal=True,precheck_cpu=cpu,free_gib=free,source_pins=sources,actual_game_pack_object_sha256=sha(pack),commands=rows,passed=False,gpu_run=False,game_run=False,scope='Existing small native fixture tests. Synthetic source tracking, invalidation, wrap, save-state serialization and bounded async decode; no user card/game state. Does not prove real gameplay latency.')
def save():(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
def run(label,args,env):
    remaining=deadline-time.monotonic();assert remaining>0
    log=out/(label+'.log');before=time.monotonic()
    with log.open('wb') as f:
        child=subprocess.Popen(args,cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=0x08004000)
        pid=child.pid;identity=psutil.Process(pid).create_time()
        try:rc=child.wait(timeout=min(40,remaining))
        except subprocess.TimeoutExpired:child.terminate();rc=child.wait(timeout=5);raise RuntimeError('Fixture command exceeded cap: '+label)
    del child;gc.collect()
    absent=False;until=time.monotonic()+2
    while time.monotonic()<until:
        try:
            p=psutil.Process(pid)
            if p.create_time()!=identity or not p.is_running():absent=True;break
        except psutil.NoSuchProcess:absent=True;break
        time.sleep(.025)
    row=dict(label=label,args=args,pid=pid,creation_unix=identity,exit=rc,seconds=time.monotonic()-before,original_child_absent=absent,log_sha256=sha(log))
    rows.append(row);save();assert rc==0 and absent,(label,rc)
    return log.read_text(encoding='utf-8',errors='replace')
save()
try:
    cxx='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe'
    for name in testnames:
        exe=out/(name+'.exe')
        run('compile-'+name,[cxx,'-std=c++17','-O1','-I'+str(layout/'include'),str(layout/'tests'/name),str(pack),'-o',str(exe)],env0)
        for identity in [False,True]:
            for mode,flags in [('baseline',{}),('region',{'PSXRECOMP_HD_REGION_INDEX':'1'}),('incremental',{'PSXRECOMP_HD_UPLOAD_INDEX_INCREMENTAL':'1'}),('both',{'PSXRECOMP_HD_REGION_INDEX':'1','PSXRECOMP_HD_UPLOAD_INDEX_INCREMENTAL':'1'})]:
                env=dict(env0,**flags)
                if identity:env['PSXRECOMP_HD_DECODE_IDENTITY']='1'
                text=run(name+'-'+mode+('-id1' if identity else '-id0'),[str(exe)],env)
                assert ('0 failures' in text if name=='hd_texture_pack_test.cpp' else 'PASS: external HD texture pack scan/hash/tracker semantics' in text)
    for source,h in sources.items():assert sha(source)==h
    assert sha(pack)==receipt['actual_game_pack_object_sha256']
    receipt.update(passed=True,fixture_processes=16,compile_processes=2,ended_utc=stamp(),elapsed_seconds=time.monotonic()-start,remaining_temp_entries=[p.name for p in temp.iterdir()])
except Exception as error:receipt.update(error=repr(error),ended_utc=stamp());raise
finally:save();shutil.copy2(__file__,out/'executed-runner.py')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['commands','source_pins']}))
