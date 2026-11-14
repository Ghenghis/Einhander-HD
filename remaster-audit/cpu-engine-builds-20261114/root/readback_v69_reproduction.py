"""Read actual reproduction and peer closure review; no repeat compile or full header hash sweep."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil,shutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
A=R/'remaster-audit/parallel-stages-20261114/s67/runs/v69-repro-2200';E=A.parent/'v69-repro-2200-envelope.json'
REVIEW=R/'coordination/pizza-review-20261114/v69-build-source-qualification-2205.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
need(sha(E)=='6fb75a3c7e1a911cecc93af711721a98a36f01c3b277e4080223749de1be1789','envelope changed')
need(sha(A/'manifest.json')=='af6fa0329b243e7d9e490431069ac8c0c6edba5107206da94dfe134db1e84b0c','manifest changed')
m=json.loads((A/'manifest.json').read_bytes());e=json.loads(E.read_bytes());review=json.loads(REVIEW.read_bytes())
need(m['verdict']=='PASS' and m['phase']=='repro' and not m['errors'] and not m['reasons'],'reproduction failed')
need(m['driver_sha256']==review['driver_sha256']=='45a73ed13b58cbbff8f3164260c7d0f735736206c4a7223bd27f45ad72161003','driver binding')
need(review['repro_manifest_sha256']==sha(A/'manifest.json'),'peer report manifest binding')
need(review['repro_source_closure']['unique_current_rehashed']==1201 and not review['repro_source_closure']['mismatches'],'peer dependency review')
need(review['retained_link_inputs_current']=={'count':153,'mismatch':[]},'retained link review')
need(all(c['actual']==c['expected'] for c in review['compiler_current_checks'].values()),'peer compiler review')
objects=[]
for label,pin,count in [('main','911b117aebb45d0414d54057bdde273aac43219dfafeecb08bacaf496d337dd3',1142),
    ('debug','1947bca3cd81af078289a46a4e6d7017f1296edb4c93e650b30ec8f186ddf8b6',403)]:
    ent=m['repro'][label];need(ent['reproduces_v68_object'] and ent['obj_sha256']==pin and sha(Path(ent['obj']))==pin,'baseline object')
    need(sha(Path(ent['depfile']))==ent['depfile_sha256'] and ent['closure_count']==len(ent['closure'])==count,'dependency receipt')
    objects.append(dict(label=label,sha256=pin,closure_count=count,depfile_sha256=ent['depfile_sha256']))
need(len(m['children'])==2 and all(c['rc']==0 and not c['timed_out'] for c in m['children']),'actual compile steps')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'Job exit')
need(e['job']['active']==0 and e['tree_absent'] and e['child_absent'] and not e['descendants_left'],'original cleanup')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384},'before-resume readback')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==32768,'Job readback')
identities=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
identities += [(c['step'],c['pid'],c['creation_unix']) for c in m['children']]
known=[]
for label,pid,created in identities:
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known owned identity remains');known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'v69-reproduction-readback-r1';out.mkdir(exist_ok=False);shutil.copy2(REVIEW,out/'peer-source-qualification.json')
result=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),readback_pass=True,actual_reproduction_pass=True,
    manifest_sha256=sha(A/'manifest.json'),envelope_sha256=sha(E),peer_review_sha256=sha(REVIEW),
    peer_rehashed_dependencies=1201,peer_rehashed_retained_link_inputs=153,objects=objects,known_identities=known,
    provenance_deviation=review['provenance_deviation'],full_dependency_rehash_repeated_by_root=False,
    build_phase_started_by_root=False,compiler_or_fixture_replayed=False,game_run=False,gpu_run=False,
    real_device_or_listening_tested=False,installed=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('objects','known_identities')}))
