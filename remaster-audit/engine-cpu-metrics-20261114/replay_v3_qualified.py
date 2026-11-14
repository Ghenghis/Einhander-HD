from pathlib import Path
import hashlib,json,subprocess,datetime,psutil,importlib.util
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;p=n/'v3-qualified-run4';origin=r/'remaster-audit/runtime-review/remix-provenance/impl-v3'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([me.cpu_affinity()[-1]])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
ready=json.loads((p/'READY.json').read_bytes());report=json.loads((p/'host-test-v3.json').read_bytes());assert report['verdict']=='pass'
for name,digest in ready['files'].items():assert sha(p/name)==digest,name
for folder in ['impl-v2','impl-v3']:
 patch=json.loads((origin.parent/folder/'patch-receipt.json').read_bytes())
 for name,ref in patch['bases'].items():assert sha(ref['path'])==ref['sha256'],name
spec=importlib.util.spec_from_file_location('v3_recipe',p/'run_host_test_v3.py');recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
holdpath=r/'remaster-audit/comfy-authoring/GPU-RESERVED';before=holdpath.read_bytes();assert json.loads(before)['owner']=='user-external-project'
runs=[]
for run in report['runs']:
 exe=origin/'work'/(run['name']+'.exe');assert sha(exe)==run['exe_sha256'];q=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30,creationflags=0x4000)
 errors=[]
 if run['name']=='view_v3_test':errors,_=recipe.check_tcp(q.stdout)
 row={'name':run['name'],'sha256':sha(exe),'exit':q.returncode,'stdout_tail':q.stdout.splitlines()[-2:],'failures':[x for x in q.stderr.splitlines() if x.startswith('FAIL')],'tcp_errors':errors}
 runs.append(row);assert q.returncode==0 and not row['failures'] and not errors,row
assert holdpath.read_bytes()==before
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ready_sha256':sha(p/'READY.json'),'source_and_binary_pins_verified':True,'v2_and_canonical_bases_unchanged':True,'runs':runs,'all_four_pass':len(runs)==4,'author_mutants':{'caught':report['mutants_caught'],'total':report['mutants_total'],'root_repeated':False},'one_logical_cpu':me.cpu_affinity(),'below_normal':True,'gpu_work':False,'game_executed':False,'user_gpu_hold_unchanged':True}
(n/'provenance-v3-independent-replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
