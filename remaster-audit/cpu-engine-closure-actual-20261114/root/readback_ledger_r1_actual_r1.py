"""Verify actual ledger CPU artifacts and known identities without replay or library sweep."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
o=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport'
b=o/'ledger-r1-run1/20261115T000222Z';rp=b/'result.json';ep=o/'ledger-r1-run1-envelope.json'
pins={rp:'56f442e63deb128113889eb6dc8a1f092f88b3478bf75a0d0247a59321e3f2d1',ep:'a775833906528d2daff6fead16ca35c83bf0348e2fb35f401f1b75a5aa6d141c',o/'ledger-r1-run1-runner/executed-watchdog.py':'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36'}
rows=[]
def check(path,want):
    raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(str(path),got)
    rows.append({'path':str(path),'sha256':got,'bytes':len(raw)})
for path,want in pins.items():check(path,want)
d=json.loads(rp.read_bytes());e=json.loads(ep.read_bytes())
assert d['passed'] and not d['gl_used'] and not d['sdk_used'] and d['cpu']==12
assert e['child_exit_code']==0 and e['wrapper_exit']==0 and e['job_empty'] and e['tree_absent'] and e['job']['active']==0
assert e['cpu']==12 and e['priority']==16384 and e['timeout_s']==120 and e['max_job_mib']==1024
for name,v in d['inputs'].items():check(Path(v['path']),v['sha256'])
for rel,v in d['executed_copies'].items():check(b/rel,v if isinstance(v,str) else v['sha256'])
for name,want in d['exe_sha256'].items():check(b/f'test-scene-ledger-{name}.exe',want)
check(o/'capture/ledger-r1/build_scene_ledger_fixture.r1.py',d['builder_sha256'])
identities=[]
def absent(kind,pid,ct):
    if pid is None or ct is None:raise ValueError('Missing known identity '+kind)
    try:gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess:gone=True
    assert gone,(kind,pid)
    identities.append({'kind':kind,'pid':pid,'creation_unix':ct,'identity_absent':True})
for kind in ('wrapper','child'):absent(kind,e[kind+'_pid'],e[kind+'_create_time'])
for step in d['steps']:
    assert step['passed'],step['label']
    if step['label']=='extract':continue
    assert step['exit']==0 and step['timed_out'] is False
    absent(step['label'],step['pid'],step['creation_unix'])
    log=b/(step['label']+'.log');rows.append({'path':str(log),'sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'bytes':log.stat().st_size})
    if step['label'].startswith('compile-'):assert log.stat().st_size==0
for name,count,revision in [('r0reg',99,'r0'),('r1',32,'r1')]:
    path=b/f'fixture-{name}.json';f=json.loads(path.read_bytes());assert f['checks']==count and f['failures']==0 and f['passed'] is True and f['revision']==revision and f['gl_used'] is False and f['sdk_used'] is False
    rows.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
out=n/'ledger-r1-actual-readback-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'known_identities':identities,'actual_checks':{'unchanged_r0_regression':99,'new_display_hazard':32,'failures':0},'whole_job_seconds':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes'],'empty_strict_compile_logs':True,'job_empty':True,'tests_replayed':False,'compiler_libraries_rehashed':False,'gpu_game_used':False,'scope':'Synthetic GP0 CPU tests; not glueR3, real frames, G4, compositor, GPU/game/RT/DLSS/installed acceptance.'}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'checks':131,'pins':len(rows),'identities':len(identities),'seconds':e['elapsed_s'],'peak_job_memory_bytes':e['peak_job_memory_bytes']}))
