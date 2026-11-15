from pathlib import Path
import datetime,hashlib,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in')
p=w/'remaster-audit/scene-texture-followup-20261114'
target=r/'remaster-audit/stage1-completion-20261112/execution-state.json'
old=target.read_bytes();(p/'root/prior-execution-state.json').write_bytes(old)
state=json.loads(old);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
owned=[]
for proc in psutil.process_iter(['pid','name','exe']):
    try:
        exe=(proc.info['exe'] or '').replace('\\','/').lower()
        if exe.startswith(str(r/'remaster-audit').replace('\\','/').lower()+'/') and (proc.info['name'] or '').lower().endswith('.exe') and any(s in exe for s in ['einhander_recompiled','sdk-','gl_selftest']):owned.append(proc.info)
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not owned,owned
state['historical_active_work_before_20261114_1311']=state.pop('active_work')
state['updated_at_utc']=now
state['latest_verified_component']={'id':'v66 reviewed scene capture and matching modern SDK CPU table initialization','github_commit':'26d3fd208f48544ec69d7abcdf11115e6c061f5d','github_commit_scope':'Previous published checkpoint; current follow-up commit not yet created. See actual branch HEAD/PR delivery receipt.','status':'v66 compiled/linked and CPU-tested, not live-run; SDK0.16.1 function table initializes, no Startup/Submit/Present; v5 restart integrity recovery ongoing','evidence':'remaster-audit/scene-texture-followup-20261114/README.md'}
state['active_work']={'id':'EIN-CODEX-CONTINUITY-20261114','state':'CPU-only restart integrity recovery with actual native Claude, scene/SDK implementation and actual-results publication','worktree':'C:/github/Einhander','publication_worktree':str(w).replace('\\','/'),'owner':'codex-einhander','claude_owner':'claude-einhander','current_owned_game':None,'owned_probe_inventory':owned,'inventory_utc':now,'gpu_work_active':False,'stutter_fixed':False,'audio_fixed':False,'production_installed':False,'runtime':'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3/build.json','sha256':'51ec32e3fdf4fc7567e807bce7106576a51e0c39ae73e65cb0599c33bd6a5a98','runtime_executed':False,'clean_full_source_rebuild':False,'scene_capture_schema':'gp0-scene-v3','host_checks':{'enabled':2932,'disabled':6,'failures':0,'rpc_cases':14,'foreign_thread_control':True,'independent_negative_mutations':28},'sdk_modern_table_only_passed':True,'sdk_modern_startup_submit_present_executed':False,'ray_tracing_in_game':False,'dlss_in_game':False,'user_3090_hold':{'started_utc':'2026-11-14T11:44:30Z','expires_utc':'2026-11-14T12:44:30Z','elapsed':True,'reuse_after_hour_authorized':True,'rtx3060_permitted':True},'restart_recovery':{'boot_utc':'2026-11-14T12:49:22.109931+00:00','root_checked_text_files':5066,'root_all_zero_text_files':90,'root_affected_freeze':'renderer-v61-classmip-v5','failed_freeze_preserved':True,'prior_published_pins_verified':990,'prior_pin_errors':0,'new_freeze_accepted':False,'cause_established':False},'next_steps':['Verify fresh Claude v5-r2 freeze and independent CPU replay','Publish owned source/reports and verify staged documentation, hashes and remote HEAD','Implement matching modern SDK Submit/Present interop lifecycle on CPU before GPU qualification','Qualify v66 real scene capture with bounded private route and correct phase bounds','Complete RISE/far-background art and full skin/HUD/menu/audio/seven-stage acceptance']}
state['github_head']='26d3fd208f48544ec69d7abcdf11115e6c061f5d'
state['package']='remaster-audit/scene-texture-followup-20261114'
state['resources_reserved']=False
state['documentation_publication_previous']=state.pop('documentation_publication')
state['documentation_publication']={'status':'Prepared, not yet committed or pushed','previous_commit':'26d3fd208f48544ec69d7abcdf11115e6c061f5d','branch':'codex/display-history-opt-in','pr':'https://github.com/Ghenghis/Einhander-HD/pull/1','canonical_handoff':'coordination/Codex-HANDOFF.md','package':state['package'],'full_e2e_complete':False}
state['runtime_continuation_owner']='codex-einhander'
for key in ['full_remaster_complete','stage1_complete','e2e_complete']:assert state[key] is False
target.write_text(json.dumps(state,indent=2)+'\n')
dst=w/target.relative_to(r);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,dst)
status=r/'docs/STAGE1-COMPLETION-STATUS.md';text=status.read_text();first,rest=text.split('\n',1)
intro='''
November14 current checkpoint: **Stage1 and the full remaster remain incomplete**. [Actual reviewed scene/SDK/restart evidence](../remaster-audit/scene-texture-followup-20261114/README.md) supersedes historical next actions below. V66r3 compiles/links and passes2932 enabled/6 disabled CPU checks,14 exact-handler RPC cases plus foreign-thread control and28 independent negative snapshot mutations. It has not run in-game. Modern matching SDK0.16.1 initializes its function table only; Startup/Submit/Present are not executed. The old-runtime GPU image/lifecycle control still fails. Ray tracing/DLSS in-game are unfinished.

The user's3090Ti hour ended12:44:30UTC and reuse afterward is authorized; no owned game/probe is running. Windows restarted12:49:22UTC. Root found90 zero-filled text files confined to unpublished frozenv5; all990 published pins verify intact. Native Claude is actively recovering from intact originals into a new freeze; no recovered v5 acceptance yet. Distant signs/buildings, full texture coverage, detailed skins/selectors, HUD/menus, audio and seven-stage E2E remain open. Prior v61 live smoothness/audio acceptance remains failed; no new gameplay/audio test ran. [Codex handoff and current queue](../coordination/Codex-HANDOFF.md).
'''
status.write_text(first+'\n'+intro+'\n'+rest.lstrip());shutil.copy2(status,w/'docs'/status.name)
receipt=dict(at_utc=now,previous_execution_state_sha256=hashlib.sha256(old).hexdigest(),new_execution_state_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),owned_runtime_processes=owned,prior_active_work_preserved=True,gpu_executed=False)
(p/'root/current-state-refresh.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,p/'root'/Path(__file__).name)
print(json.dumps(receipt))
