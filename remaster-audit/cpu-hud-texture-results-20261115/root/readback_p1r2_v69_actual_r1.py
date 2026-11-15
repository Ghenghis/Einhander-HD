"""Read back completed private CPU build; do not launch, rebuild or sweep libraries."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
n=Path(__file__).resolve().parent
u=Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui')
b=u/'builds/p1r2-v69-0040'
pins={u/'receipts/P1r2-v69-0040-envelope.json':'9fba33e8c58b31282921b7e6d27c6f888eca7170db793f98885d014fc124fa97',b/'manifest.json':'7af19709de4db34b785f7e92e0c36c0a5d4b474a77dd20087f115667501802e1',u/'proposals/p1-player-color/build/build_p1r2_v69_r4.py':'a8a8f8628de324d640dcdd9e9ae11a18a413f2b66ccc68e894ca32dcbbe50a2f',b/'src/main.cpp':'fe85c7e4caf7be4f76ce3a8528ba08868e9468113940ea44e716aa68a2ae6dd3',b/'Einhander_Recompiled.exe':'34e5d8f50ee013749bdd53eb139796ca15adea684d1a93bb8335b6127bcd3be2',u/'receipts/P1r2-v69-0040-runner/executed-watchdog.py':'fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36'}
rows=[]
for path,want in pins.items():
 raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(str(path),got)
 rows.append(dict(path=str(path),sha256=got,bytes=len(raw)))
d=json.loads((b/'manifest.json').read_bytes());e=json.loads((u/'receipts/P1r2-v69-0040-envelope.json').read_bytes())
assert d['verdict']=='PASS' and not d['reasons']
s=d['steps'];assert len(s)==12 and all(x['ok'] is True for x in s.values())
assert s['deps:main']['v69_closure_entries']==s['deps:main']['new_entries']==1142
assert not any(s['deps:main'][k] for k in ['only_in_new','only_in_expected','changed_or_missing_shared'])
assert len(s['deps:keymap']['deps'])==118 and all(x['path'].lower().startswith('c:') for x in s['deps:keymap']['deps'])
assert len(s['rsp']['replaced'])==2 and s['retained_inputs']['file_inputs']==155
assert s['outputs']['v69_exe_untouched'] is True
assert e['cpu']==13 and e['affinity']==[13] and e['priority']==16384 and e['timeout_s']==120 and e['max_job_mib']==1024
assert e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16
assert e['rc']==e['child_exit_code']==e['wrapper_exit']==0 and not e['timeout_killed']
assert e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and e['child_absent']
identities=[]
for kind in ('wrapper','child'):
 pid,ctime=e[kind+'_pid'],e[kind+'_create_time']
 try:gone=psutil.Process(pid).create_time()!=ctime
 except psutil.NoSuchProcess:gone=True
 assert gone,(kind,pid)
 identities.append(dict(kind=kind,pid=pid,creation_unix=ctime,identity_absent=True))
out=n/'p1r2-v69-actual-readback-r1';out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),pins=rows,known_identities=identities,manifest_steps_passed=12,main_closure_entries=1142,keymap_c_only_closure_entries=118,retained_file_inputs=155,replaced_objects=2,whole_job_seconds=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],job_empty=True,baseline_untouched_reported_by_builder=True,root_rebuilt=False,root_launched=False,root_game_gpu_used=False,installed=False,
 limits=['Private player/enemy COLOUR profile selector only, not realistic actor skins or PBR.','Compile/link/recorded dependency equality is not live menu behaviour.','No fresh rehash of 1142 toolchain dependencies or 153 retained objects in this readback.','Historical D: keymap dependency closure remains UNKNOWN; no D: access.','Live L5-L7 and E1-E6 not run; zero-strength UX, persistence, per-actor roles and asset admission remain open.','No new gameplay, audio, G4/compositor, RT/DLSS or installed release acceptance.'])
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(out=str(out),pins=len(rows),manifest_steps_passed=12,seconds=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],job_empty=True)))
