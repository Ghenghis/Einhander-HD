"""Fresh pinned host executions only. No game, GPU or new compilation."""
from pathlib import Path
import hashlib,json,subprocess,datetime,psutil
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander');p=r/'remaster-audit/runtime-review/remix-provenance/impl-v2'
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
ready=json.loads((p/'READY.json').read_text());patch=json.loads((p/'patch-receipt.json').read_text());report=json.loads((p/'host-test-v2.json').read_text())
holdpath=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=holdpath.read_bytes();assert json.loads(hold)['owner']=='user-external-project'
for name,digest in ready['files'].items():assert sha(p/name)==digest,name
for name,ref in patch['bases'].items():assert sha(Path(ref['path']))==ref['sha256'],name
assert sha(Path(patch['v1_generator']['path']))==patch['v1_generator']['sha256']
runs=[]
for run in report['runs']:
 exe=p/'work'/(run['name']+'.exe');assert sha(exe)==run['exe_sha256']
 t=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30,creationflags=0x4000)
 runs.append({'name':run['name'],'exe_sha256':sha(exe),'exit':t.returncode,
 'stdout_tail':t.stdout.splitlines()[-2:],'failures':[x for x in t.stderr.splitlines() if x.startswith('FAIL')]})
 assert t.returncode==0 and not runs[-1]['failures'],runs[-1]
assert holdpath.read_bytes()==hold
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ready_sha256':sha(p/'READY.json'),
 'source_and_binary_pins_verified':True,'canonical_bases_unchanged':True,'runs':runs,'all_four_pass':len(runs)==4,
 'author_mutation_controls':{'caught':report['mutants_caught'],'total':report['mutants_total'],'repeated_by_root':False},
 'gpu_work':False,'new_game_build':False,'live_coverage':False,'user_gpu_hold_unchanged':True,
 'remaining_integration':'Private full-runtime build with correct header/link inputs; live PGXP hook-flavour coverage after user returnsGPU. Camera/object separation, scene submission/PBR/RT/DLSS remain unfinished.'}
(n/'provenance-v2-independent-replay.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
