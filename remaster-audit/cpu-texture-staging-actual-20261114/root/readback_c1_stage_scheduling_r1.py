"""Read completed receipts and small artifacts only; no image transforms, cache sweep or rerun."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil, struct
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
S=R/'remaster-audit/parallel-stages-20261114/s23'
Q=R/'coordination/pizza-review-20261114/normal-game-envelope-r1'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; identities=[]; runs={}
def need(ok, why):
    if not ok: raise RuntimeError(why)
def pin(p, want=None):
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    need(want is None or h==want, 'pin: '+str(p)); pins[str(p)]=h; return h
def read(p,want=None):
    pin(p,want); return json.loads(p.read_bytes())
def envelope(label,p,cpu,normal=False):
    e=read(p)
    need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],label+' exit')
    need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,label+' resources')
    affinity=list(range(16)) if normal else [cpu]; priority=32 if normal else 16384
    need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':affinity,'priority':priority}, label+' scheduling')
    need(e['job_limits_readback']['priority_class']==priority and e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left'],label+' Job')
    for role in ['wrapper','child']:
        pid=e[role+'_pid']; ct=e[role+'_create_time']
        try: absent=psutil.Process(pid).create_time()!=ct
        except psutil.NoSuchProcess: absent=True
        need(absent,label+' identity remains')
        identities.append(dict(run=label,role=role,pid=pid,creation_unix=ct,identity_absent=True))
    runs[label]=dict(envelope_sha256=pins[str(p)],elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
    return e
pin(U/'c1-stroke-void/ui_c1_stroke_void_r3.py','02071250968200ed79ca5323e643e30191c5287d5c642368555a8540e2eca551')
for label,stamp,mode,expected in [
    ('c1-dry','20261114T230007Z','dry-run','03b61ae370db23c0dee82be53fa79214a1e2d249e52deaf44716d1d73204af7a'),
    ('c1-write','20261114T230036Z','write','a3a745880c26c9725ed03af9f84118e156135a63f1a1a2e13f1de7dc5074c592')]:
    ep='C1r3-dry-20261114T230005Z-envelope.json' if mode=='dry-run' else 'C1r3-write-20261114T230033Z-envelope.json'
    envelope(label,U/'receipts'/ep,13)
    d=U/'c1-stroke-void/runs'/stamp; a=read(d/'result.json',expected)
    need(a['mode']==mode and a['verdict']=='PASS' and not a['blockers'] and len(a['controls'])==14 and all(a['controls'].values()),label+' result')
    need(len(a['gates'])==5 and all(a['gates'].values()) and a['voids']==a['changed_pixels']==240 and a['centre_voids']==0 and a['centre_class_ok_before']==65536,label+' gates')
    pin(d/a['review_1x']['path'],a['review_1x']['sha256'])
    if mode=='write':
        png=d/a['output_png']['path']; pin(png,a['output_png']['sha256'])
        with png.open('rb') as f: header=f.read(24)
        need(header[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24])==(2048,2048),'PNG header')
    runs[label].update(result_sha256=expected,controls=14,gates=5,changed_pixels=240,art_admitted=False,installed=False)
pin(S/'tools/pilot_stage_onekey_r2.py','c03a7d83f00749a686b7ab2adf250f6be5fb9db87f73e5fd922c56349ea435f5')
envelope('cache-qualify',S/'runs/qual-2255-envelope.json',12)
envelope('pilot-stage',S/'runs/stage-2255-envelope.json',12)
a=read(S/'runs/j10-cache-qualify-2255/QUALIFY.json','47ab696965f72eaa37450ff1574fea37d6529d78b4ace000f62139738345d44e')
b=read(S/'pilot/j10-onekey-2255/PILOT-STAGE.json','9dcd225db562892944abdff6f8064077d26921f2f9be75ef25a98f75d0021a8e')
need(a['ok'] and b['ok'] and a['manifest']['files']==b['cache']['files']==4405 and a['manifest']['bytes']==b['cache']['bytes']==239111587,'cache counts')
pin(Path(a['manifest']['path']),'bbcb9abeecb227d5e29705584f6955a06b06386c414c2298933d917b917e9b9f')
need(b['cache']['mode']=='copy' and len(b['settings']['mutated'])==4 and b['hdroot_check']['only_key_png'],'staging facts')
pin(S/'pilot/j10-onekey-2255/runtime/settings.toml',b['settings']['sha256'])
pin(S/'pilot/j10-onekey-2255/hdroot/28127931-7C2D834A.png',b['png'])
runs['pilot-stage'].update(files=4405,bytes=239111587,art_admitted=False,game_launched=False,cache_abi_qualified=False,bulk_cache_rehashed_by_root=False)
pin(Q/'run_normal_game_envelope_r1.py','c1fc81d49392cdf350468db1f781818eb547e79f0ee33f0cab6cd10811191448')
e=envelope('normal-child',Q/'readback-2255-envelope.json',11,True)
c=read(Q/'readback-2255.json','10de2668caef8c99e1ee9ae987a0d5ae2d70860ba293ebe2e0188386a7899c26')
need(c['cpu_affinity']==list(range(16)) and c['priority']==32 and e['affinity']==[11] and e['priority']==16384,'actual scheduling')
out=N/'c1-stage-scheduling-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=identities,
         image_processing_run=False,fixtures_replayed=False,game_launched=False,gpu_used=False,art_admitted=False,
         scope='Recorded receipts, small artifacts and known identities checked; no full input/cache sweep or live acceptance.')
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(metadata_readback_pass=True,runs=runs,verified_pins=len(pins),known_identities_absent=len(identities))))
