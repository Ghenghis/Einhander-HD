from pathlib import Path
import copy,datetime,hashlib,json,psutil,shutil
from audit_scene_snapshot import audit
n=Path(__file__).resolve().parent;out=n/'snapshot-audit-r2';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
record=json.loads((n/'host-r8/record.json').read_text())
info=dict(mode=4,capacity=1024,count=1,complete_interval=True,malformed=0,overflow=0,textured_seen=1,frame=record['frame'],geometry_qualified=1,generation=record['generation'],geometry_types_complete=True)
base=dict(schema='gp0-scene-v3',info=info,records=[record])
positive=audit(base);assert positive['passed'] and positive['ideal_projection_error_max_px']==0,positive
cases=[]
def mutate(name,path,value):
    b=copy.deepcopy(base);cursor=b
    for key in path[:-1]:cursor=cursor[key]
    cursor[path[-1]]=value
    result=audit(b);assert not result['passed'],name
    cases.append(dict(name=name,errors=result['errors']))
mutate('unknown schema',['schema'],'gp0-scene-v1')
mutate('partial capture',['info','complete_interval'],False)
mutate('overflow',['info','overflow'],1)
mutate('counter',['info','count'],2)
mutate('bad topology',['records',0,'indices'],[0,2,1,2,1,3])
mutate('source mismatch',['records',0,'word_sources',1],0x8000)
mutate('packet mismatch',['records',0,'vertices',0,'packed'],0)
mutate('UV mismatch',['records',0,'vertices',0,'uv'],[123,234])
mutate('RGB mismatch',['records',0,'vertices',0,'rgb'],1)
mutate('CLUT mismatch',['records',0,'material','clut'],0)
mutate('future provenance',['records',0,'vertices',0,'source_frame'],102)
mutate('old provenance',['records',0,'vertices',0,'source_frame'],99)
mutate('negative frame',['records',0,'vertices',0,'source_frame'],-4294967195)
mutate('uncommitted',['records',0,'vertices',0,'flags'],1)
mutate('divergence',['records',0,'vertices',0,'flags'],(1<<9)|(1<<4))
mutate('lane',['records',0,'vertices',0,'lane'],2)
mutate('hash',['records',0,'vertices',0,'xform_hash'],0)
mutate('MAC',['records',0,'vertices',0,'mac',0],1)
mutate('missing fields',['records',0,'vertices',0],{})
mutate('qualified contradiction',['records',0,'geometry_qualified'],False)
mutate('cross-generation record',['records',0,'generation'],record['generation']+1)
mutate('incomplete record',['records',0,'complete_interval'],False)
mutate('SF0',['records',0,'vertices',0,'flags'],1<<9)
mutate('native XY',['records',0,'vertices',0,'native_xy'],[1,2])
mutate('oversize mask',['records',0,'oversize_mask'],3)
mutate('eligibility mask',['records',0,'eligible_triangle_mask'],0)
mutate('omitted geometry hidden',['info','textured_sprites'],1)
mutate('lookup status',['records',0,'vertices',0,'lookup_miss_reason'],5)
# Validate frame-counter wrap without accepting future provenance.
wrapped=copy.deepcopy(base);wrapped['info']['frame']=0;wrapped['records'][0]['frame']=0
for v in wrapped['records'][0]['vertices']:v['source_frame']=0xffffffff;v['lag']=1
assert audit(wrapped)['passed']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p in [n/'audit_scene_snapshot.py',Path(__file__),n/'host-r8/record.json']:shutil.copy2(p,out/p.name)
(out/'fixture-snapshot.json').write_text(json.dumps(base,indent=2)+'\n')
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,positive=positive,
             negative_cases=cases,negative_cases_caught=len(cases),wrap_positive=True,gpu_executed=False,
             source_sha256=sha(n/'audit_scene_snapshot.py'),input_record_sha256=sha(n/'host-r8/record.json'),
             cpu_affinity=me.cpu_affinity(),below_normal=True,scope='Independent Python packet/MAC/hash consistency; fixture JSON emitted by C++ collector. Not live capture or renderer qualification.')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(passed=True,negative_cases_caught=len(cases),projection_error_max_px=positive['ideal_projection_error_max_px'],gpu=False)))
