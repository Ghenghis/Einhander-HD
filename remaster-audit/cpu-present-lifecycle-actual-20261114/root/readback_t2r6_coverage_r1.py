"""Check completed T2r6/coverage receipts, copies and known identities; no replay or bulk scan."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
P=R/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport'
S=R/'remaster-audit/parallel-stages-20261114/s23'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; identities=[]; runs={}
def need(ok,why):
    if not ok: raise RuntimeError(why)
def pin(p,want=None):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); need(want is None or h==want,'pin '+str(p)); pins[str(p)]=h; return h
def read(p,want=None): pin(p,want); return json.loads(p.read_bytes())
def absent(label,pid,ct):
    try: gone=psutil.Process(pid).create_time()!=ct
    except psutil.NoSuchProcess: gone=True
    need(gone,'identity remains '+label); identities.append(dict(label=label,pid=pid,creation_unix=ct,identity_absent=True))
def envelope(label,p,cpu,want):
    e=read(p,want); need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],label+' exit')
    need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[cpu],'priority':16384},label+' scheduling')
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,label+' resource precheck')
    need(e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left'],label+' tree')
    for role in ['wrapper','child']: absent(label+'/'+role,e[role+'_pid'],e[role+'_create_time'])
    runs[label]=dict(envelope_sha256=pins[str(p)],elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
    return e
envelope('t2r6',P/'t2r6-run1-envelope.json',12,'423ade12a8c081de636effd650ed39559c1e0a4891338a2251db3f348acb1f03')
d=P/'t2r6-run1/20261114T231146Z'; a=read(d/'result.json','d5f7a5fd752316e4820e8f7eea29b10abb98501a850410b182ef7abfc61be90f')
need(a['passed'] and a['exception'] is None and all(s['passed'] for s in a['steps']),'T2 driver result')
for row in a['inputs'].values(): pin(Path(row['path']),row['sha256'])
for name,h in a['executed_copies'].items(): pin(d/name,h)
pin(P/'t2/r6/build_t2_fixture.r6.py',a['builder_sha256'])
pin(P/'t2r6-run1-runner/executed-watchdog.py','fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36')
f=read(d/'fixture-unit.json'); need(f==dict(fixture='t2',revision='r6',checks=50,failures=0,passed=True,gl_used=False,sdk_used=False),'actual 50 checks')
pin(d/'test-t2r6-unit.exe',a['exe_sha256']['unit']); need((d/'compile-unit.log').read_bytes()==b'','strict compiler warning log')
pin(d/'compile-unit.log'); pin(d/'run-unit.log')
for s in a['steps']:
    if s.get('pid') is not None: absent('t2r6/'+s['label'],s['pid'],s['creation_unix'])
runs['t2r6'].update(checks=50,failures=0,executed_copies=len(a['executed_copies']),source_inputs=len(a['inputs']),compiler_libraries_rehashed_by_root=False,synthetic_only=True)
envelope('coverage',S/'runs/covr3-2311-envelope.json',13,'6ec6c1bfe3214e6764674d472fe94c96ddaaf38e219fad8639e3e64099808fff')
pin(S/'tools/fullstage_coverage_r3.py','4c40c85b43d5b8228fa2bc1b1858c097afb3a486742d2611dc49404a599b3f90')
pin(S/'runs/covr3-2311-runner/executed-watchdog.py','fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36')
c=read(S/'runs/fullstage-r3-2311/fullstage-coverage.json','ef8ff7519743d6f829fda8f7fb785644bbe93422556921534fd7bb7403b73c46')
old=read(S/'runs/fullstage-20261114T182734Z/fullstage-coverage.json')
pin(S/'runs/fullstage-r3-2311/FULLSTAGE-COVERAGE.md','27575fafbcfb509fb287fd0bef3d5ca77f824134b41d6184a31f8cf339a349bd')
need(c['inputs']==old['inputs'],'recorded stage input hashes changed')
stats={}
for stage,expected in [('stage2',2321),('stage3',2289)]:
    rows=c['stages'][stage]['rows']; before=old['stages'][stage]['rows']; need(len(rows)==expected and set(rows)==set(before),'key universe')
    need(all(v['source']==before[k]['source'] and v['authored']==before[k]['authored'] for k,v in rows.items()),'raw source/authored fields')
    need(all(v['admission']=='not established' for v in rows.values()),'row admission')
    need(all(v['live_visual']==v['stage_e2e']=='none' for v in c['stages'][stage]['families'].values()),'live qualification')
    cand=[k for k,v in rows.items() if v['provenance']=='stage1 candidate ledger']; need(len(cand)==1 and all(rows[k]['integration'].startswith('unknown') for k in cand),'candidate provenance')
    stats[stage]=dict(keys=len(rows),overrides=len(c['overrides_applied'][stage]),candidate_provenance_only=len(cand),drawn_without_authored=sum(v['source'] in ('live_drawn','complete_live_source') and not v['authored'] for v in rows.values()))
trans=[v for k,v in c['stages']['stage2']['rows'].items() if k.startswith('442981F7-')]
need(len(trans)==4 and all(not v['authored'] and v['provenance']=='none' and v['integration']=='none' and 'unverified' in v['family'] for v in trans),'transient gaps preserved')
runs['coverage'].update(stages=stats,transient_gaps_preserved=4,all_manifest_inputs_rehashed_by_root=False,scope='ownership/provenance accounting only; no new assets or live acceptance')
out=N/'t2r6-coverage-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=identities,compiler_or_fixture_replayed=False,game_launched=False,gpu_used=False,art_admitted=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(metadata_readback_pass=True,runs=runs,pins_verified=len(pins),known_identities_absent=len(identities))))
