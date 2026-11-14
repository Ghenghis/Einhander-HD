"""Verify new successful write/cleanup controls and preserve both raw-control failures."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
S=R/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/adapter-binding'
L=R/'remaster-audit/parallel-stages-20261114/s67'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; ids=[]; runs={}
def need(ok,why):
    if not ok: raise RuntimeError(why)
def pin(p,want=None):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); need(want is None or h==want,'pin '+str(p)); pins[str(p)]=h; return h
def read(p,want=None): pin(p,want); return json.loads(p.read_bytes())
def env(label,p,cpu,rc,want):
    e=read(p,want); need(e['rc']==e['wrapper_exit']==e['child_exit_code']==rc and not e['timeout_killed'],label+' exit')
    need(e['child_readback_before_resume']=={'cpu_affinity':[cpu],'priority':16384} and e['job_assigned_before_resume'],label+' scheduling')
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,label+' resources')
    need(e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left'],label+' tree')
    for role in ['wrapper','child']:
        pid=e[role+'_pid']; ct=e[role+'_create_time']
        try: gone=psutil.Process(pid).create_time()!=ct
        except psutil.NoSuchProcess: gone=True
        need(gone,'identity remains'); ids.append(dict(run=label,role=role,pid=pid,creation_unix=ct,identity_absent=True))
    runs[label]=dict(envelope_sha256=pins[str(p)],exit=rc,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
env('79902-write',U/'receipts/C1r4-write-79902A90-20261114T232145Z-envelope.json',13,0,'0ad0663b0738d775d1e85be35d39f152846b2be4533ac92ef184f8ede9ffda1f')
d=U/'c1-stroke-void/runs/20261114T232147Z'; a=read(d/'result.json','60f03bc1a8a9ddd2a179f83ae099d09f5dd795ac783dcdf03a8e23bebcbd3fa1')
need(a['verdict']=='PASS' and not a['blockers'] and len(a['controls'])==14 and all(a['controls'].values()) and len(a['gates'])==5 and all(a['gates'].values()),'final write gates')
need(a['voids']==a['changed_pixels']==422 and a['voids_per_roi']=={'A':88,'B':240,'C':94} and a['centre_voids']==0 and a['centre_class_ok_before']==65536,'final write counts')
for row in a['review_1x'].values(): pin(d/row['path'],row['sha256'])
pin(d/a['output_png']['path'],'1067cc536c8028c619089b4abff41f228c9d845696eed26f99af9af693355a03')
runs['79902-write'].update(changed_pixels=422,candidate_sha256=a['output_png']['sha256'],prior_refusal_preserved=True,fresh_grant_used=True,repeated_dry_run=False)
env('cleanup17',S/'runs/controls-cleanup-2316-envelope.json',12,0,'5116ecc2c9b5351c9353ecd72e98c64f9129b6cebff8b0f895bcc9855f4ed680')
b=read(S/'runs/controls-cleanup-2316/result.json','9944c3a4a188b835483e45f78540e90eec7dd71f7e854a21906456291359fa49')
need(b['all_ok'] and b['case_count']==b['expected_cases']==len(b['cases'])==17 and all(c['ok'] for c in b['cases']) and 'fatal' not in b,'17 controls')
pin(S/'controls_cleanup_r1.py',b['controls_sha256'])
for p,h in b['pins'].items(): pin(Path(p),h)
runs['cleanup17'].update(checks=17,failures=0,controls_elapsed_s=b['elapsed_s'],pure_doubles_only=True,live_tree_qualification=False)
for name,prefix,want in [('raw-r2','raw37c-controls-r2-2315','57e2bfb56578db2443b76a78e275dc43668777372a1848e2c7307a605f09d91b'),('raw-r3','raw37c-controls-r3-2318','6406175e4c4ff296956d7e56d6b9d182661c564a9b11a47252c97766dc4ff3a4')]:
    env(name,L/'runs'/(prefix+'-envelope.json'),14,1,want)
    runs[name].update(passed=False,check_counts_unknown=True,staging_run=False)
for suffix in ['stdout','stderr']:
    p=L/'runs'/('raw37c-controls-r2-2315.'+suffix); need(p.read_bytes()==b'','preserved empty capture'); pin(p)
log=L/'runs/raw37c-controls-r3-2318.log'; pin(log,'28ae6aa2fce663d76049426c4ff3f2607d4126b72e65f802617be286f7c545f2')
need('private settings changed' in log.read_text() and 'reverify_ok' in log.read_text(),'logged cause')
runs['raw-r2']['cause']='UNKNOWN: original stdio empty; later same-body evidence is an inference only'
runs['raw-r3']['cause']='fixture Windows CRLF bytes versus expected LF hash; production check correctly refused'
out=N/'final-lettering-cleanup-failures-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=ids,c1_total_candidates=3,c1_total_changed_pixels=856,c1_previous_r3_pixels_included=240,tests_replayed=False,game_launched=False,gpu_used=False,installed=False,art_admitted=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in rec.items() if k not in ('pins','known_identities')}|dict(pins_verified=len(pins),known_identities_absent=len(ids))))
