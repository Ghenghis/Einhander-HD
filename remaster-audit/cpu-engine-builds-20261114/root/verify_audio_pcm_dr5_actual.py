"""Independent hashes of the actual seven PCM cases; never replay the fixture."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
A=R/'remaster-audit/parallel-stages-20261114/s67/runs/audio-gap-Dr5-2147'
E=A.parent/'audio-gap-Dr5-2147-envelope.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
need(sha(E)=='b6311948bce3a5f07790097f2bdad2559c362c8979403c02ca48a9d05dac15a3','envelope changed')
need(sha(A/'manifest.json')=='f0ec68c98f3dd5622c7f36601fb78cbefeb6511eff3557d5080230c036488433','manifest changed')
e=json.loads(E.read_bytes());m=json.loads((A/'manifest.json').read_bytes())
need(m['grant_id']=='msg_b2b1e01caf214831','actual direct grant changed')
need(m['verdict']=='PASS' and not m['reasons'] and not m['errors'],'fixture failure')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'job failure')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'gate failed')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384},'child resource readback')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==32768
     and e['job_limits_readback']['priority_class']==16384 and e['job_limits_readback']['limit_flags']==8752,'Job limits')
need(e['job']['active']==0 and e['tree_absent'] and e['child_absent'] and not e['descendants_left'],'cleanup receipt')
need(len(m['children'])==4 and all(c['rc']==0 and not c['timed_out'] for c in m['children']),'compile/run failed')
need([c['step'] for c in m['children']]==['compile:base','run:base','compile:patched','run:patched'],'step order')
pins=[]
for key in ('fixture','base_header','patched_header'):
    ent=m['inputs'][key]
    for field in ('original','copy'):
        path=Path(ent[field]);need(path.resolve().is_relative_to(R.resolve()),'outside project')
        need(sha(path)==ent['expected']==ent['read_sha256']==ent['copy_sha256'],'source changed '+key)
        pins.append(dict(kind=key,path=path.relative_to(R).as_posix(),sha256=sha(path)))
cases=['unprimed_starvation','one_gap','recovery','multiple_gaps','gap_split_across_callbacks','mute_then_unmute_reset','reset_by_init']
need(list(m['cases'])==cases,'seven-case list changed');comparison=[]
for name in cases:
    case=m['cases'][name];need(case['pcm_equal'] and case['old_counter_marks_equal'],'original comparison failed')
    hashes=[]
    for side in ('base','patched'):
        path=A/(side+'_run')/(name+'.pcm');ent=case[side]
        need(sha(path)==ent['pcm_sha256'] and path.stat().st_size==ent['pcm_bytes'],'actual PCM changed')
        hashes.append(sha(path))
    need(hashes[0]==hashes[1] and case['base']['line']['marks']==case['patched']['line']['marks'],'independent equality failed')
    comparison.append(dict(case=name,pcm_sha256=hashes[0],bytes=case['base']['pcm_bytes'],old_counter_marks=case['base']['line']['marks']))
identities=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
identities += [(c['step'],c['pid'],c['creation_unix']) for c in m['children']]
known=[]
for label,pid,created in identities:
    need(created is not None,'creation time unavailable')
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known owned identity remains: '+label)
    known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'audio-pcm-dr5-independent-readback-r1';out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=True,metadata_and_pcm_hashes_only=True,
    envelope_sha256=sha(E),manifest_sha256=sha(A/'manifest.json'),inputs=pins,known_identities=known,
    cases=comparison,actual_grant=m['grant_id'],relayed_same_slot_grant='msg_35c1f60f7fa0733c',attempt_count=1,
    fixture_replayed=False,toolchain_files_rehashed_by_readback=False,real_sdl=False,listening=False,
    game_run=False,gpu_run=False,performance_gain_proved=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('inputs','known_identities','cases')}))
