"""Freeze a new CPU verification/build checkpoint; previous published packets stay immutable."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in')
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
name='decode-worker-results-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='588ab2a7f5991c0709b9fb393ca1125f017ccdde'
p.mkdir(exist_ok=False);sources=[];omitted=[]
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
extensions={'.py','.c','.cpp','.h','.inc','.json','.jsonl','.md','.txt','.log','.mjs','.tsv','.csv','.rsp','.d'}
def cp(src,dest):
    src=Path(src);dest=p/dest;data=src.read_bytes();assert b'\0' not in data,src
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
def tree(src,dest):
    src=Path(src);assert src.is_dir(),src
    for f in sorted(src.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:continue
        if f.suffix.lower() in extensions and f.stat().st_size<12*1024**2:cp(f,Path(dest)/f.relative_to(src))
        else:omitted.append(dict(source=str(f),bytes=f.stat().st_size,reason='Private generated binary/image/native payload retained locally; not redistributed.'))
replay=json.loads((n/'v6-cpu-verification-r1/result.json').read_text(encoding='utf-8'))
b=e/'sampling-build-v67-decode-identity-r3';build=json.loads((b/'build.json').read_text(encoding='utf-8'))
assert replay['passed'] and build['build_complete'] and sha(build['executable'])=='8bc3ac3daedcbb08790905c228d1dc7b052bd5ed52d3bb739c02009ec86bb772'
for folder in ['v6-cpu-verification-r1','v6-cpu-outer-r1','primary-replacement-registration-r1','primary-replacement-registration-r2']:tree(n/folder,'root/'+folder)
for f in ['prepare_v6_replay.py','verify_v6_cpu.py','run_v6_cpu_bounded.py','register_primary_replacement.py','prepare_v67_source.py','prepare_v67_r2.py','fix_v67_growth_contract.py','prepare_v67_r3.py','build_private_v67.py','build_private_v67_r3.py','check_v67_r1_exit.py','v67-r1-exit-followup.json','verify_v67_pack_regressions.py','texture-composer-delivery.json','texture-composer-pr-verification.json','prepare_decode_worker_delivery.py']:cp(n/f,'root/'+f)
monitors=sorted(n.glob('monitor-renewal-20261114T1519*'));assert len(monitors)==1
tree(monitors[0],'root/'+monitors[0].name);monitor=json.loads((monitors[0]/'result.json').read_text())
for version in ['r1','r2','r3']:tree(e/('sampling-build-v67-decode-identity-'+version),'private-build/'+version)
report=Path('C:/Users/Admin/AppData/Roaming/Claude/side-session-notes/local_4ea66aaa-8822-4352-9314-bc95cc950d9e/V66-V67-COUNTER-REVIEW-20261114.md')
assert sha(report)=='8f3b988380889834e1c9d9b351ba72524ff77e845a8ceeef7e2af48035c5984b';cp(report,'native-review/'+report.name)
stage=r/'remaster-audit/parallel-stages-20261114'
selected=[('s23','runs/j3-20261114T150256Z'),('s23','runs/j6-20261114T152828Z'),('s23','proposals/s2-phase-selftest-20261114T152828Z'),('s45','menu-hud/fade-recovery/20261114T150008Z'),('s45','menu-hud/fade-recovery/20261114T150530Z-provenance'),('s45','menu-hud/fade-aliases-v1/20261114T150907Z'),('s45','menu-hud/crosscheck-w6/20261114T151137Z'),('s45','menu-hud/w6-primary-probe/20261114T151757Z'),('s45','menu-hud/state-register/20261114T152157Z'),('s45','menu-hud/gates/20261114T153536Z'),('s45','menu-hud/classsnap/20261114T152840Z'),('s67','repairs/stage6-fx-classrepair-r2b-nativefill')]
for lane,folder in selected:tree(stage/lane/folder,'stage-work/'+lane+'/'+folder)
for lane,folder in [('s45','menu-hud/tools')]:tree(stage/lane/folder,'dated-tools/'+lane+'/'+folder)
observed=dict(recorded_utc=stamp(),basis='Actual shell tool result and preserved child/run receipts; no synthetic scheduler receipt.',v67_r1_tool_exit=1,v67_r2_precheck_tool_exit=1,v67_r2_precheck_cpu=75.6,v67_r2_precheck_free_gib=78.58602142333984,v67_r2_precheck_child_started=False,v67_r2_compile_tool_exit=1,v67_r3_tool_exit=0,v67_r3_tool_chunk='0bfe54',v67_r3_build_sha256=sha(b/'build.json'),game_run=False,gpu_run=False,audio_run=False)
(p/'OBSERVED-OUTER-RESULTS.json').write_text(json.dumps(observed,indent=2)+'\n',encoding='utf-8')
rosterfile=r/'coordination/CLAUDE-SESSIONS-20261114.json';roster=json.loads(rosterfile.read_text(encoding='utf-8'));roster['updated_utc']=stamp()
activity=r/'.hermes3d_orchestrator/continuity/activity-22093f9cf1313bb6.json';a=json.loads(activity.read_text());assert a['owner']=='claude-einhander' and a['session_id']=='1c56db97-2f5d-4f18-aece-e2a77dbf7a70'
roster['sessions'][0].update(state='actual_replacement_hook_inbox_checkpoint_verified',live_hook_verified_utc=a['model_hook_observed_at_utc'],live_hook_status='Actual canonical hook writes name exact owner/CLI; own-inbox and fresh checkpoint reported and independently read. Canonical writes blocked by native worktree guard are not routed through shell; root applies reviewed canonical outputs within its own scope.')
roster['sessions'][2]['scope']+='; menu/HUD implementation and state/source gates'
roster['monitoring_handoff'].update(watcher_pid=monitor['pid'],current_bound_end_utc=monitor['bound_end_utc'],renewal_receipt=str((monitors[0]/'result.json').relative_to(r)).replace('\\','/'))
rosterfile.write_text(json.dumps(roster,indent=2)+'\n',encoding='utf-8');cp(rosterfile,'dated-coordination/CLAUDE-SESSIONS-20261114.json');cp(activity,'dated-coordination/primary-activity.json')
cp(r/'.hermes3d_orchestrator/continuity/claude-einhander.json','dated-coordination/primary-checkpoint.json')
cp(r/'remaster-audit/claude-backlog/ORIGINAL-HANDOFF-20261114T1450Z.md','dated-coordination/retired-primary-handoff.md')
(p/'README.md').write_text('''# Decode-worker verification and private game integration — November14

This is a new CPU-only source/report checkpoint from C:. No graphics process, game/audio test or experimental installation ran. Modern Remix/OpenGL image/synchronization/lifecycle and ray tracing/DLSS in-game remain NOT RUN. Older packets are immutable.

Root independently verifies1,111 v6 frozen pins, recompiles/replays7,534 fixture checks and16 recording-GL cases/425 checks, and recompiles the actual worker pack plus STB source for92 identity/lifetime/exact-env checks. All pass. The bounded outer wrapper captures exit0,13.865s,CPU15/below-normal, child absent; its hold bytes stay unchanged. Root did not replay the author's mutation suite or real-page benchmarks. These are CPU correctness checks, not game latency or visual acceptance.

The private v67r3 game now compiles/links: EXE8bc3ac3daedcbb08790905c228d1dc7b052bd5ed52d3bb739c02009ec86bb772,155 pinned link inputs. R3 freshly compiles debug and pack, retaining the already-rebuilt/pinned r2 renderer and other existing core/guest/platform objects; this is not a clean full-source build. The v6 worker computes RGB-sidecar identities before Ready publication and provides immutable lease-bound O(1) access, with no synchronous fallback hash. Experiments remain default off. Scene-v3 collection stays in place; complete geometry/world/camera/material transport is unfinished. The executable is not launched or installed.

The read-only diagnostics adapter now exports all98 values (14 head + four21-reason tables) under a v6 schema. It requests99 slots and requires98 so a cap-honouring expanded accessor is rejected. Eight CPU adapter cases pass, including zero/all-UINT64_MAX data, final identity reason, invalid counts and a real99-value accessor. The old-cap mutation silently accepts growth and is caught by that control. Head13 counts identity attempts, not accepted entries. Native Claude independently reviewed the source and found this growth issue. Historical v66 was correct for its own v4 renderer/48 values; only combining its old handler with v6 would truncate.

Failures are preserved: r1's adapter compiler exited0 but immediate PID observation asserted before any test/game compilation; follow-up verified the exact parent/child absent. R2 fixes handle release and bounded identity observation. One r2 resource precheck declined75.6%CPU before children; it is not a compiler failure. Later r2 adapter8/growth controls and renderer compile pass, but full debug compilation catches the omitted local scene_runtime.h closure. New r3 adds both pinned v66 scene headers, retains passing controls, and debug/pack/link exit0 in6.837s. Tool outer exits and their distinction from child results are recorded. No unrelated PID was terminated, and earlier failures were not overwritten.

Existing tracker/save-state/async-decode regression recipes are prepared against the exact new game pack object but NOT RUN here. They cover source tracking, invalidation, wrapping and save-state serialization across index/identity settings using synthetic temporary fixtures. Live first-use stalls, audio, class-mip/RGB appearance and full-stage route tests remain pending.

Actual native-primary replacement is registered: desktop43668750/CLI1c56db97, with observed canonical own-owner hook activity, own inbox and fresh checkpoint. Original11357b05 is retired from new assignments with transcript/checkpoint preserved, not user_stop. Actual cwd is a C: project worktree with canonical config root; native worktree guards prohibit canonical writes and are respected. Root may apply reviewed proposals with its own permissions. The bounded metadata monitor PID36052 ends15:49:33.939UTC and proves monitoring only, not future model availability.

Later-stage author results: S23 J3 finds six light-strip phase-pair outline mismatches; J6 reproduces8 known keys/16 outputs byte-for-byte and strict-pass in50.93s/exit0. Phase-union repair remains unexecuted at this snapshot. S45 derives152 HUD fade candidates; all304 original-method exports fail whole-cell classes, as do sampled older centre-only fixes. They remain blocked. Fourteen representative cell-snap copies pass strict policies with common-visible RGB unchanged, but alter alpha/STP toward native classes and retain visible stair bumps; nearest fill can bleed colours and has fringe. No HUD look/live acceptance. An independent reconstruction supplies the remaining five fade keys, so157 keys have derived candidates, not byte-captured source confirmation. S67's8-file native smoke fill passes class checks and removes wrong teal fill in simulation; no live acceptance.

The menu register distinguishes frozen-candidate coverage from real delivery: boot3/3,title50/50,title-menu1/1,selection19/19,config/file/name/rankings38/38,pause/continue8/8,game-over1/1,results51/51,in-play116/142,HUD fades24/157 in prior sets plus the newer failing candidates. Instructions/DEMO0/3 lack archived words. B24C6DA2's11 hit-gauge keys have stock source but no current frozen candidate. These are per-state selection counts, not a whole-game completion percentage; no keys' existence proves a menu interaction works. Only earlier Total/Field Evaluation was observed; return-to-title and normal save/load/continue/game-over remain open. The joined per-state gates preserve exact source/capture requests rather than declaring completion.

Root also viewed both region-O far-building previews: new panes are clearer, but bright separated windows need screen-size/motion review. The2048 option avoids the4096 page's4x upload cost; neither is frozen/installed/live-accepted by this checkpoint. Full backgrounds/signs, realistic player/enemy/boss/gun skins and selectors, modern menu/HUD interactions, remastered audio/listening, successful full Remix/engine rendering and stages1–7/release acceptance remain unfinished. No smoothness/audio fix,4K fidelity pass, completion percentage or finish date is claimed. SOURCE-MAP binds dated read-only snapshots; mutable tool copies may be newer than executed copies. LOCAL-PAYLOADS lists omitted private images, native inputs and binaries.
''',encoding='utf-8',newline='\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=stamp(),sources=sources),indent=2)+'\n',encoding='utf-8')
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted,scope='No ROM/BIOS/cards, SDK DLL/JAR, private exe/object or generated artwork/native payload redistributed. Source/report subset only; full private data retained on C:.'),indent=2)+'\n',encoding='utf-8')
doc='''# Decode-worker and private v67 results — November14

Root's CPU replay passes7,534 fixture checks,16 recording-GL cases/425 checks and92 worker identity checks. The bounded outer process exits0 in13.865s on one below-normal CPU. Private v67r3 compiles/links with full98-value v6 diagnostics and a real growth guard; eight adapter controls pass. It retains pinned parent objects and is not a clean full-source release. [Exact source, raw checks, failures and limits](../remaster-audit/decode-worker-results-20261114/README.md).

The game has not launched or been installed. Existing tracker/save-state regression recipes are prepared, not run. Modern Remix images/lifecycle, in-game ray tracing/DLSS, mini-boss smoothness/audio, skin selectors, complete HUD/menu interactions and all seven stages still need acceptance.

The actual native primary replacement now has verified own-owner hook/inbox activity. Original history is preserved. Its native worktree guard is respected; denied canonical writes are not routed through shell. The metadata monitor is bounded and does not prove uninterrupted future work.
'''
newdoc='docs/DECODE-WORKER-RESULTS-20261114.md';(r/newdoc).write_text(doc,encoding='utf-8',newline='\n');shutil.copy2(r/newdoc,w/newdoc)
docs=['docs/'+x for x in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
current='''## Current verified CPU checkpoint —15:37UTC

Root independently replays v6:7,534 fixtures,16 recording-GL cases/425 checks and92 worker identity checks pass; bounded outer exit0/13.865s. Private v67r3 now compiles/links (EXE8bc3ac3d...), with8 adapter controls and a real growth mutation caught. It freshly builds debug/pack, retains the rebuilt r2 renderer and other pinned objects; not a clean full-source build. No game/GPU/audio run or installation. Tracker/save-state regressions and all live acceptance remain open. [Actual results and preserved failures](../docs/DECODE-WORKER-RESULTS-20261114.md).

The canonical native primary replacement has actual own hook/inbox/checkpoint proof; original history is retained and its worktree guard respected. Metadata monitor PID36052 is bounded to15:49:33.939UTC. CPU-only work continues; no GPU grant is inferred from elapsed time. Older checkpoint paragraphs below are historical. HUD derived candidates still require source/look/live acceptance; full skins/menu/audio and seven-stage completion are not claimed.

'''
for rel in docs:
    file=r/rel;text=file.read_text(encoding='utf-8');title,tail=text.split('\n',1)
    with file.open('w',encoding='utf-8',newline='\n') as f:f.write(title+'\n\n'+current+tail.lstrip())
    shutil.copy2(file,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statefile.read_text(encoding='utf-8'))
state['updated_at_utc']=stamp();state['latest_verified_component']=dict(id='v6 independent CPU replay and private v67r3 link',evidence='remaster-audit/'+name+'/README.md',fixture_checks=7534,glue_cases=16,glue_checks=425,pack_checks=92,counter_adapter_cases=8,private_exe_sha256=build['executable_sha256'],game_launched=False,gpu_run=False,audio_run=False,status='CPU verified/private link only; tracker regression and live acceptance pending')
state['actual_monitor']=dict(pid=monitor['pid'],bound_end_utc=monitor['bound_end_utc'],watcher_only=True,proves_model_activity=False)
statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');shutil.copy2(statefile,w/statefile.relative_to(r))
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dest=r/'remaster-audit'/name/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
paths=['.gitattributes','remaster-audit/'+name,newdoc,*docs,statefile.relative_to(r).as_posix()]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=stamp(),packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),staged=True,committed=False,pushed=False,gpu_run=False)
(n/'decode-worker-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
