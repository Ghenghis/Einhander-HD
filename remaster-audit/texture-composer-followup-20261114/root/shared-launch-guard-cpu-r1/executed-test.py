"""CPU-only protocol checks; never acquire or mutate the user's actual GPU grant."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('shared_guard',r/'tools/coordination/shared_gpu_guard.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
out=n/'shared-launch-guard-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
now=datetime.datetime(2026,11,14,14,50,tzinfo=datetime.timezone.utc);token='fixture-fence-only'
base=dict(schema='shared-gpu-v1',gpu_uuid=guard.GPU,revision=1,denied=[],grant=dict(owner=guard.OWNER,token=token,new_starts_allowed=True,expires_utc='2026-11-14T15:00:00Z'))
cases=[]
def check(name,state,fence,expected,new_starts=True):
    result=guard.permission(state,fence,now,new_starts);assert result['allowed']==expected,(name,result)
    cases.append(dict(case=name,expected=expected,passed=True,result=result))
check('valid_current_fence',base,token,True)
for name,edit in [('foreign_project',lambda s:s['grant'].update(owner='claude-pizza-tycoon-hd')),('expired',lambda s:s['grant'].update(expires_utc='2026-11-14T14:00:00Z')),('denied',lambda s:s.update(denied=[guard.OWNER])),('new_starts_disabled',lambda s:s['grant'].update(new_starts_allowed=False)),('wrong_device',lambda s:s.update(gpu_uuid='other-gpu')),('bad_deadline',lambda s:s['grant'].update(expires_utc='not-a-time')),('bad_deny_list',lambda s:s.update(denied=None))]:
    state=copy.deepcopy(base);edit(state);check(name,state,token,False)
check('missing_fence',base,None,False);check('stale_fence',base,'old-fixture',False);check('missing_state',None,token,False)
expired=copy.deepcopy(base);expired['grant'].update(expires_utc='2026-11-14T14:00:00Z',new_starts_allowed=False);check('running_job_retains_ownership_after_expiry',expired,token,True,False)
actual=guard.current_permission(None);assert not actual['allowed'] and actual['owner']=='claude-pizza-tycoon-hd'
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,cpu_cases=len(cases),cases=cases,current_actual_owner_without_token=actual,actual_state_mutated=False,gpu_run=False,source_sha256=hashlib.sha256((r/'tools/coordination/shared_gpu_guard.py').read_bytes()).hexdigest(),below_normal=True,cpu_affinity=me.cpu_affinity())
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'executed-test.py');shutil.copy2(r/'tools/coordination/shared_gpu_guard.py',out/'executed-source.py');print(json.dumps(report))
