from pathlib import Path
import hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;origin=r/'remaster-audit/runtime-review/remix-provenance/impl-v3'
out=n/'v3-qualified-run4';assert not out.exists();out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ready=json.loads((origin/'READY.json').read_bytes());refs=[]
for name,digest in ready['files'].items():
 p=origin/name
 if name=='run_host_test_v3.py' and sha(p)!=digest:p=origin/'runs/20261114-run4-preserved/run_host_test_v3.py'
 assert sha(p)==digest,name
 target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);assert sha(target)==digest
 refs.append({'qualified_path':name,'actual_source_path':str(p),'sha256':digest})
for name in ['READY.json','verification-manifest.json','FAILED-RUNS.md']:shutil.copy2(origin/name,out/name)
(out/'qualified-origins.json').write_text(json.dumps({'scope':'Exact READY-pinned run4 input/output bytes; current runner changed only to add future run archival and is not substituted for the executed run4 recipe. Every expected hash is required.','files':refs},indent=2)+'\n')
for name,digest in ready['files'].items():assert sha(out/name)==digest
print(json.dumps({'snapshot':str(out),'ready_sha256':sha(out/'READY.json'),'pinned_files':len(refs),'all_hashes_match':True}))
replay=(n/'replay_v3.py').read_text().replace("p=r/'remaster-audit/runtime-review/remix-provenance/impl-v3'","p=n/'v3-qualified-run4';origin=r/'remaster-audit/runtime-review/remix-provenance/impl-v3'")
replay=replay.replace("p.parent/folder/'patch-receipt.json'","origin.parent/folder/'patch-receipt.json'").replace("exe=p/'work'/","exe=origin/'work'/")
(n/'replay_v3_qualified.py').write_text(replay,encoding='utf-8')
builder=(n/'build_private_runtime_v61.py').read_text().replace("v3=r/'remaster-audit/runtime-review/remix-provenance/impl-v3'","v3=n/'v3-qualified-run4'").replace('sampling-build-v61-view-metrics','sampling-build-v61-view-metrics-r2').replace('private-runtime-v61-build-result.json','private-runtime-v61-r2-build-result.json')
(n/'build_private_runtime_v61_r2.py').write_text(builder,encoding='utf-8')
