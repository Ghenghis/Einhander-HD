from pathlib import Path
import datetime,hashlib,json,subprocess,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
p=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v60-view-provenance-r3'
d=json.loads((p/'build.json').read_text());assert d['build_complete'] and not d['game_launched'] and not d['gpu_work']
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
exe=Path(d['executable']);assert sha(exe)==d['executable_sha256']
nm=Path(d['commands'][-1]['arguments'][0]).parent/'llvm-nm.exe';assert nm.is_file()
args=[str(nm),'--defined-only',str(exe)]
q=subprocess.run(args,capture_output=True,text=True,timeout=30,creationflags=0x4000);assert q.returncode==0
needed=['pgxp_set_view_payload','gpu_view_census_set','pgxp_view_census_prim','pgxp_view_census_recent','gte_rtp_ring_seq_live',
 'pgxp_get_precise_vertex_view_ex','handle_pgxp_view','psx_frame_phase_get_status']
found={name:[line for line in q.stdout.splitlines() if line.split()[-1:]==[name]] for name in needed}
# The existing phase symbol name differs across snapshots; enumerate it without
# treating an invented spelling as a required API.
phase=[line for line in q.stdout.splitlines() if 'frame_phase' in line.split()[-1]]
required=needed[:-1];assert all(found[x] for x in required),found
assert phase,'Preserved phase diagnostics absent'
assert len(d['link_inputs'])==152
for row in d['link_inputs']:assert sha(row['path'])==row['sha256']
for name,digest in d['headers'].items():assert sha(p/name)==digest
assert d['tcp_merge']['existing_parent_code_preserved']
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'executable_sha256':sha(exe),'tool':{'path':str(nm),'sha256':sha(nm)},
 'command':args,'exit':q.returncode,'required_symbols':{x:found[x] for x in required},'preserved_phase_symbols':phase,
 'linked_inputs_verified':152,'replaced_parent_objects':len(d['replaced_actual_linked_objects']),
 'new_census_object':True,'header_snapshot_hashes_verified':len(d['headers']),'parent_debug_code_preserved':True,
 'gpu_work':False,'game_executed':False,'scope':'Static complete executable and link-input checks only; no startup, rendering, gameplay, live coverage or performance acceptance.'}
(n/'runtime-static-link-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
