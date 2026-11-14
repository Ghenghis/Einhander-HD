"""Read actual Dr2 artifacts and known process identities. No test rerun or GPU."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil

R = Path('C:/github/Einhander')
N = Path(__file__).resolve().parent
A = R/'remaster-audit/parallel-stages-20261114/s67/runs/audio-telemetry-combined-r2-806b'
E = A.parent/'audio-Dr2-806b-envelope.json'
me = psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
def need(ok, why):
    if not ok: raise RuntimeError(why)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
need(sha(E) == '8b7c7348d4a9c634fe9ea66c4b6f6bf7b1702272cd0d1796d394b0cb158db302', 'envelope changed')
need(sha(A/'manifest.json') == 'f92094c4229e3eccafcb1906452f6caac506577ba88a093559a386a83fdba63a', 'manifest changed')
e = json.loads(E.read_bytes()); m = json.loads((A/'manifest.json').read_bytes())
need(m['verdict'] == 'PASS' and not m['errors'] and not m['reasons'], 'fixture did not pass')
need(m['grant_id'] == 'msg_806b9f6d1aa666e0', 'wrong one-use grant')
need(len(m['children']) == 4 and all(c['rc'] == 0 and not c['timed_out'] for c in m['children']), 'compile/run failed')
need([c['step'] for c in m['children']] == ['compile:getters','run:getters','compile:pump','run:pump'], 'step order')
need(e['rc'] == e['wrapper_exit'] == e['child_exit_code'] == 0 and not e['timeout_killed'], 'envelope failed')
need(e['precheck']['system_cpu_pct'] < 60 and e['precheck']['free_gib'] >= 16, 'precheck gate')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume'] == {'cpu_affinity':[15], 'priority':16384}, 'child resource readback')
need(e['job_limits_readback']['job_memory_limit'] == 1073741824 and e['job_limits_readback']['affinity_mask'] == 32768
     and e['job_limits_readback']['priority_class'] == 16384 and e['job_limits_readback']['limit_flags'] == 8752, 'Job limits')
need(e['job']['active'] == 0 and e['tree_absent'] and e['child_absent'] and not e['descendants_left'], 'original cleanup')
pins = []
for key in ('getters_harness','pump_harness','getters_inc','pump_inc','header','main_cpp'):
    entry = m['inputs'][key]
    for field in ('original','copy'):
        path = Path(entry[field]); need(path.resolve().is_relative_to(R.resolve()), 'outside project')
        need(sha(path) == entry['expected'] == entry['copy_sha256'], 'input changed: '+key)
        pins.append(dict(kind=key, path=str(path.relative_to(R)), sha256=sha(path)))
for key in ('getters_exe','pump_exe'):
    entry = m['inputs'][key]; need(sha(Path(entry['path'])) == entry['sha256'], 'local executable changed')
need(m['inputs']['getters_reextract_equal'] and m['inputs']['pump_reextract_equal'], 'original re-extraction')
g=m['results']['getters']; p=m['results']['pump']
need(g['result']=='PASS' and g['reads']==200000 and g['negative_controls_fired']==3
     and g['viol_mod37']==g['viol_coherence']==g['viol_gaps']==0 and g['distinct']>=100
     and g['pulls_during_C']>=1000, 'getter oracle')
need(p == {'events':4, 'result':'PASS'}, 'pump oracle')
identities=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
identities += [(c['step'],c['pid'],c['creation_unix']) for c in m['children']]
known=[]
for label,pid,created in identities:
    try: absent = psutil.Process(pid).create_time() != created
    except psutil.NoSuchProcess: absent = True
    need(absent, 'known owned identity remains: '+label)
    known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'audio-dr2-independent-readback-r1'; out.mkdir(exist_ok=False)
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=True,metadata_only=True,
    envelope_sha256=sha(E),manifest_sha256=sha(A/'manifest.json'),inputs=pins,known_identities=known,
    result=g,pump=p,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],
    source_reextraction_repeated=False,fixture_replayed=False,real_sdl=False,pcm_identity_tested=False,
    game_run=False,gpu_run=False,audible_gain_proved=False,performance_gain_proved=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('inputs','known_identities','result','pump')}))
