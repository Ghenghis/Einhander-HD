"""Read and verify the completed T2r4 fixture receipts; never rerun fixtures or compilers."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil

R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
P=R/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport'
A=P/'t2r4-run1/20261114T222908Z'; E=P/'t2r4-run1-envelope.json'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
def need(ok,why):
    if not ok: raise RuntimeError(why)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
need(sha(E)=='c34c9d228100cde13b07772db1eeda5945ecc216b44a4231b6df7e78a4e39b82','envelope changed')
need(sha(A/'result.json')=='e847019d72d6ba8cde20111a49581f46d41e0b2a921a844a8a5dda4ef806d540','result changed')
e=json.loads(E.read_bytes()); m=json.loads((A/'result.json').read_bytes())
need(m['passed'] is True and not m['gl_used'] and not m['sdk_used'],'fixture failed or unexpected scope')
steps={s['label']:s for s in m['steps']}
need(set(steps)=={'extract','compile-unit','run-unit','compile-integ','run-integ'},'unexpected step set')
need(all(s['passed'] for s in steps.values()),'step failed')
need(len(steps['extract']['blocks'])==12 and all(b['sha256']==b['pinned'] and b['passed'] for b in steps['extract']['blocks'].values()),'native block pins')
need(steps['extract']['divide_block']=={'sha256':'cfa7686a59c223f358d2507674af7289dc462213e0b676165b87b60974a896ef','v61_equals_canonical':True},'divide extraction')
pins=[]
for name,row in m['inputs'].items():
    p=Path(row['path']).resolve(); need(p.is_relative_to(R),'outside project input')
    got=sha(p); need(got==row['sha256'],'input changed '+name)
    pins.append(dict(name=name,path=str(p.relative_to(R)),sha256=got))
for name,want in m['executed_copies'].items(): need(sha(A/name)==want,'executed copy changed '+name)
raw=Path(m['inputs']['pgxp.h']['path']).read_bytes()
old=b'*x16/*y16'; new=b'*x16 and *y16'
need(raw.count(old)==1 and raw.find(old)==3986,'header token changed')
need((A/'pgxp.h').read_bytes()==raw[:3986]+new+raw[3986+len(old):],'derived header not exact comment-only change')
need(sha(A/'scene_ledger_native_unpack.inc')=='a9b1eaa343f4d6853f31a78d12faa817ac4564df3a7922db31891430eb534b00','native unpack changed')
fixtures={}
for key,count in [('unit',55),('integ',21)]:
    f=json.loads((A/f'fixture-{key}.json').read_bytes())
    need(f['checks']==count and f['failures']==0 and f['passed'] is True and f['gl_used'] is False and f['sdk_used'] is False,'fixture contract '+key)
    need(f==steps['run-'+key]['fixture'],'fixture does not bind result '+key)
    need(sha(A/f'test-t2r4-{key}.exe')==m['exe_sha256'][key],'exe changed '+key)
    for k in ('compile-'+key,'run-'+key): need(steps[k]['exit']==0 and steps[k]['timed_out'] is False,'child failed '+k)
    fixtures[key]=dict(checks=count,failures=0,fixture_sha256=sha(A/f'fixture-{key}.json'),exe_sha256=m['exe_sha256'][key])
need(sha(P/'t2r4-run1-runner/executed-watchdog.py')=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','copied watchdog changed')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'envelope failed')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'resource gate')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384},'pre-resume child settings')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==32768,'Job limits')
need(e['job']['active']==0 and e['tree_absent'] and not e['descendants_left'],'cleanup receipt')
ids=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
ids += [(k,s['pid'],s['creation_unix']) for k,s in steps.items() if k!='extract']
known=[]
for label,pid,created in ids:
    need(created is not None,'missing recorded creation time')
    try: absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess: absent=True
    need(absent,'known identity remains '+label)
    known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'t2r4-actual-readback-r1'; out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,
    result_sha256=sha(A/'result.json'),envelope_sha256=sha(E),source_inputs=pins,
    executed_copies=m['executed_copies'],fixtures=fixtures,known_identities=known,
    elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],
    sampler_complete=False,unobserved_pid_identities_not_inferred=True,
    large_toolchain_rehashed_by_root=False,native_extraction_repeated=False,fixtures_replayed=False,
    game_run=False,gpu_run=False,scope='Synthetic CPU policy and epoch refusal plumbing only; no live glue/material/camera/compositor/suppression qualification')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(metadata_readback_pass=True,checks=76,source_inputs=len(pins),copied_inputs=len(m['executed_copies']),
    known_identities_absent=len(known),elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],out=str(out))))
