"""Read five completed C1r4 results and the separate prelaunch refusal; do not retry."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
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
pin(U/'c1-stroke-void/ui_c1_stroke_void_r4.py','4b21da8314d688fb36c1d2cc982bb824fef91b663b8cd1a66ada3c36e86c30a0')
rows=[('4315989E','dry-run','231259','231302',12),('4315989E','write','231343','231345',12),('02491337','dry-run','231400','231402',422),('02491337','write','231411','231414',422),('79902A90','dry-run','231428','231431',422)]
for key,mode,start,stamp,count in rows:
    label=key+'/'+mode; ep=U/'receipts'/f'C1r4-{mode}-{key}-20261114T{start}Z-envelope.json'; e=read(ep)
    need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],label+' exit')
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,label+' resource')
    need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[13],'priority':16384},label+' scheduling')
    need(e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left'],label+' tree')
    for role in ['wrapper','child']: absent(label+'/'+role,e[role+'_pid'],e[role+'_create_time'])
    d=U/'c1-stroke-void/runs'/f'20261114T{stamp}Z'; a=read(d/'result.json')
    need(a['key']==f'1AD90FC9-{key}.png' and a['mode']==mode and a['verdict']=='PASS' and not a['blockers'],label+' verdict')
    need(len(a['controls'])==14 and all(a['controls'].values()) and len(a['gates'])==5 and all(a['gates'].values()),label+' controls')
    need(a['voids']==a['changed_pixels']==count and a['voids_per_roi']==a['r6_voids_per_roi'] and a['centre_voids']==0 and a['centre_class_ok_before']==65536,label+' counts')
    for row in a['review_1x'].values(): pin(d/row['path'],row['sha256'])
    if mode=='write': pin(d/a['output_png']['path'],a['output_png']['sha256'])
    else: need('output_png' not in a,'dry wrote candidate')
    runs[label]=dict(envelope_sha256=pins[str(ep)],result_sha256=pins[str(d/'result.json')],elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],changed_pixels=count,candidate=a.get('output_png'),art_admitted=False)
ep=U/'receipts/C1r4-write-79902A90-20261114T231440Z-envelope.json'; e=read(ep,'278f227f6e55dd48b56b9188699c122cca4cbf8bae29f11eecbd695166952b86')
need(e['declined'] and e['child_pid'] is None and e['wrapper_exit']==3 and e['rc'] is None,'prelaunch decline')
need(e['precheck']['system_cpu_pct']==71.4 and e['precheck']['system_cpu_pct']>e['precheck']['max_cpu'],'CPU refusal reason')
absent('79902A90/write-declined/wrapper',e['wrapper_pid'],e['wrapper_create_time'])
runs['79902A90/write-declined']=dict(envelope_sha256=pins[str(ep)],cpu_pct=71.4,child_started=False,write_completed=False,retried=False)
out=N/'c1r4-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=identities,successful_children=5,declined_before_child=1,new_private_candidates=2,new_candidate_pixels_total=434,previous_r3_pixels_included_in_total=240,remaining_write_pixels=422,tests_replayed=False,image_processing_run=False,game_launched=False,gpu_used=False,installed=False,art_admitted=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in rec.items() if k not in ('pins','known_identities')}|dict(pins_verified=len(pins),known_identities_absent=len(identities))))
