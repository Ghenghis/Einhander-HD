"""Read successful CPU staging and the later setup abort before game creation; no replay."""
from pathlib import Path
import datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent; S=R/'remaster-audit/parallel-stages-20261114/s67'
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
pins={}; ids=[]; runs={}
def pin(p,want=None):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); assert want is None or h==want,(str(p),h,want); pins[str(p)]=h; return h
def read(p,want=None): pin(p,want); return json.loads(p.read_bytes())
def envelope(label,p,cpu,rc,normal=False,want=None):
    e=read(p,want); assert e['rc']==e['wrapper_exit']==e['child_exit_code']==rc and not e['timeout_killed']
    aff=list(range(16)) if normal else [cpu]; pri=32 if normal else 16384
    assert e['child_readback_before_resume']==dict(cpu_affinity=aff,priority=pri) and e['job_assigned_before_resume']
    assert e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16
    assert e['job']['active']==0 and e['job_empty'] and e['tree_absent'] and not e['descendants_left']
    for role in ['wrapper','child']:
        pid=e[role+'_pid']; ct=e[role+'_create_time']
        try: gone=psutil.Process(pid).create_time()!=ct
        except psutil.NoSuchProcess: gone=True
        assert gone; ids.append(dict(run=label,role=role,pid=pid,creation_unix=ct,identity_absent=True))
    runs[label]=dict(envelope_sha256=pins[str(p)],exit=rc,elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'])
envelope('cpu-stage',S/'runs/raw37c-stage-r6-2331-envelope.json',14,0,want='f6541cc6af56cfe8ef18581db90c67018b11a2b451cabec2f9df6e89bf9f4b4c')
p=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112/raw37c-r6-20261114T2331Z/hd-on_rewind-off/raw37c-staging.json'
s=read(p,'2710782ef5627a16f9c1528ac1f662d80bd03a1cb5985365c5ef1db04f809c79')
assert s['schema']=='s67-raw37c-staging-r6' and s['executable_sha256']=='37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc'
assert len(s['pack']['png_pins'])==1701 and len(s['pack']['unpinned_nonpng'])==688 and s['pack']['pinned_from_candidate_files']==1699 and len(s['pack']['pinned_from_candidate_emissive_files'])==2
assert s['own_cache']['empty_at_stage'] and s['cards']['card1']['exists'] and not s['cards']['card2']['exists'] and s['cards']['enable2'] is False
deps={k:v for k,v in s['pacing_dependencies'].items() if not k.startswith('_')}; assert len(deps)==15
assert sum(v.get('load_time') is True for v in deps.values())==11 and sum(v.get('lazy') is True for v in deps.values())==4
for v in deps.values(): pin(Path(v['path']),v['sha256'])
exe=Path(s['spec']['arguments'][0]); pin(exe,s['executable_sha256'])
current_small={k:pin(Path(v['path'])) for k,v in s['launch_binding']['small'].items()}
current_settings=pin(Path(s['settings']['path']))
assert len(s['launch_binding']['bins'])==1 and s['launch_binding']['bins'][0]['bytes']==653493792
runs['cpu-stage'].update(staging_sha256=pins[str(p)],png_names_pinned=1701,nonpng_hashes_recorded_unpinned=688,local_import_pins_verified=15,own_cache_empty_recorded_at_stage=True,binary_rom_rehashed_by_root=False,pack_rehashed_by_root=False,current_small_inputs_match_stage=all(current_small[k]==v['sha256'] for k,v in s['launch_binding']['small'].items()),current_settings_matches_stage=current_settings==s['settings']['sha256'])
q=R/'coordination/pizza-review-20261114/raw37c-live-20261114T233236Z'
envelope('run-setup-abort',q/'envelope.json',11,1,normal=True)
a=read(q/'evidence/raw37c-evidence.json'); assert a['verdict']=='ABORTED' and 'gl_adapter_identity_guard' in a['abort']
assert 'S0' not in a['steps'] and 'cleanup_holder' not in a and 'fence' not in a
assert a['logs']=={'game.stdout.log':None,'game.stderr.log':None}
pin(q/'driver.log')
runs['run-setup-abort'].update(raw_evidence_sha256=pins[str(q/'evidence/raw37c-evidence.json')],game_popen_created=False,holder_created=False,game_registered=False,game_rendered=False,cause=a['abort'],gpu_release_claim='coordinator reported explicit empty-grant release; root did not read private broker/token files')
out=N/'raw-stage-setup-actual-readback-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_pass=True,runs=runs,pins=pins,known_identities=ids,tests_replayed=False,pack_or_rom_bulk_sweep_repeated=False,root_game_launched=False,gameplay_audio_acceptance=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in rec.items() if k not in ('pins','known_identities')}|dict(pins_verified=len(pins),known_identities_absent=len(ids))))
