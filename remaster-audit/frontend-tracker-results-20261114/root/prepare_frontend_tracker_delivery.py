"""Publish scoped frontend code, exact-pack CPU regressions and newer art evidence."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
name='frontend-tracker-results-20261114';p=w/'remaster-audit'/name;p.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='55eafaa20e36b23bd1a9f9459f7d4639da22ae62'
sources=[];omitted=[];sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
extensions={'.py','.mjs','.ps1','.md','.json','.jsonl','.txt','.log','.patch','.h','.cpp','.c','.inc','.tsv'}
def cp(src,dest):
    src=Path(src);dest=p/dest;assert not dest.exists();data=src.read_bytes();assert b'\0' not in data,src
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
def tree(src,dest):
    src=Path(src);assert src.is_dir(),src
    for f in sorted(src.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:continue
        if f.suffix in extensions and f.stat().st_size<12*1024**2:cp(f,Path(dest)/f.relative_to(src))
        else:omitted.append(dict(source=str(f),bytes=f.stat().st_size,reason='Generated private binary/image/native payload retained on C:.'))
for folder in ['development-frontend-cpu-r1','development-frontend-cpu-r2','v67-pack-regressions-r1','region-o-canonical-copy-r1']:tree(n/folder,'root/'+folder)
monitors=sorted(n.glob('monitor-renewal-20261114T1547*'));assert len(monitors)==1;tree(monitors[0],'root/'+monitors[0].name)
for f in ['verify_development_frontend.py','prepare_frontend_followup.py','verify_frontend_followup.py','verify_v67_pack_regressions.py','preserve_region_o_candidate.py','decode-worker-delivery.json','decode-worker-pr-verification.json','prepare_frontend_tracker_delivery.py']:cp(n/f,'root/'+f)
changed=['windows-x64/tools/'+f for f in ['launch_hd.py','Start-Development.ps1','test_launch_hd.py']]
for rel in changed:cp(r/rel,'source/'+rel)
for rel in ['windows-x64/tools/test_material_profiles.py','windows-x64/tools/material_profiles.py','windows-x64/tools/launch_material.py']:cp(r/rel,'source/'+rel)
art=r/'remaster-audit/claude-backlog/95a3-o-city/frozen/95A3BCF8-O-city-v1';tree(art,'private-region-o')
stage=r/'remaster-audit/parallel-stages-20261114'
folders=[('s23','proposals/s3-scale2x-20261114T154534Z'),('s23','runs/j5-20261114T154534Z'),('s23','proposals/s2-trains-scale2x-20261114T160110Z'),('s23','runs/j5t-20261114T160110Z'),('s45','menu-hud/epx-retrace/20261114T154219Z'),('s45','menu-hud/gauge-B24C6DA2-v1/20261114T154853Z'),('s45','menu-hud/primary-audit/20261114T155808Z'),('s45','menu-hud/primary-audit/20261114T160358Z'),('s67','repairs/stage6-fx-classrepair-r2a-nativefill'),('s67','repairs/stage6-vram448-0-A5969BC9-dedither-r2'),('s67','repairs/stage7-space-backdrop-30BB2999-bursts-r1')]
for lane,folder in folders:tree(stage/lane/folder,'stage-work/'+lane+'/'+folder)
for lane,folder in [('s45','menu-hud/receipts'),('s45','menu-hud/tools'),('s23','tools')]:tree(stage/lane/folder,'dated-tools/'+lane+'/'+folder)
roster=json.loads((r/'coordination/CLAUDE-SESSIONS-20261114.json').read_text());cp(r/'coordination/CLAUDE-SESSIONS-20261114.json','dated-coordination/roster.json')
checkpoint=r/roster['sessions'][0]['checkpoint'];cp(checkpoint,'dated-coordination/primary-allowed-checkpoint.json')
cp(r/'.hermes3d_orchestrator/continuity/activity-22093f9cf1313bb6.json','dated-coordination/primary-activity.json')
base=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary'
for f in ['tools/run_rc2.py','tools/selftest_run_rc2.py','reviews/SAVED-MATERIAL-ROUTE-REVIEW-20261114.md']:cp(base/f,'native-primary/'+f)
front=json.loads((n/'development-frontend-cpu-r2/result.json').read_text());reg=json.loads((n/'v67-pack-regressions-r1/result.json').read_text());assert front['passed'] and reg['passed']
(p/'README.md').write_text('''# Saved-material frontend parity, exact-pack regressions and later art results

CPU-only checkpoint from C:. No game, browser, bridge or GPU was launched by these checks. Earlier immutable packets remain unchanged. Modern SDK GPU qualification, v67 live appearance/timing/audio and all seven-stage/release acceptance are still pending.

## Concrete launcher fix and actual checks

Normal Play-HD already used the explicitly saved receipt-validated material selection; Start-Development bypassed it. launch_hd now supports --frontend with identical validated saved runtime/material/detail inputs, and explicit stock when requested. Ordinary Play-HD keeps direct-game behavior. Start-Development validates the plan before starting a bridge/browser, then launches the prepared executable with its environment. A malformed preset fails visibly, with explicit -Stock/-WebOnly recovery choices. No preset or runtime was silently changed.

Native Claude review caught a custom-port regression: the material environment's default8094 URL could overwrite -Port. The effective launch plan now carries the requested workspace URL before environment application. -Stock forwards --stock; the selected material profiles are printed. The argument helper rejects embedded quotes/trailing backslashes and preserves spaced file paths under real Windows CommandLineToArgvW semantics.

Nine Python unit cases pass, including saved/detail/frontend parity, stock/invalid-pointer behavior and check-without-process creation. Actual saved direct/frontend CLI plans validate with identical environments; PowerShell parses and Start-Development -Check succeeds. The follow-up retains those unchanged Python controls and passes actual -Check -Port9000 for saved AuroraTeal/CrimsonRed and explicit stock, plus Windows argv round-trip/negative controls. Saved pointer bytes stay unchanged. The first passing source/review and subsequent source are both preserved. This is code and CPU launch-plan verification, not a live frontend/skin/game/audio pass.

## Exact private-game pack regressions

Two existing native fixture executables compile against the exact v67r3 game pack object71eedf1f4bf32578e17f6e52714bbe23053594ccbee393ac6b65408b4e994fcc. Sixteen fixture processes pass across baseline/region/incremental/both settings and decode identity off/on. They cover scan/hash/source tracking, partial invalidation/residency holes, wrapping, save-state serialization/restoration and bounded async decode. One fixture reports37 checks per mode; the other reports its aggregate semantic PASS without a numeric check total. The16 processes are not16 gameplay runs. CPU15/below-normal,6.037s, actual outer exit0, all observed child identities absent; private temporary tree ends empty. No user cards/game state or GPU changed. This closes the previously prepared-only CPU regression gate; real first-use frame tails/audio remain open.

## Region-O candidate preserved, integration still pending

The allowed-worktree freeze passes its actual wrapper controls and15.528s/exit0/tree-empty author run. Root verifies9 frozen pins/READY and copies all11 files with fsync/readback into canonical C: storage, leaving the worktree/source/original art intact. The2048 option changes only the far-building region O against its older w3 baseline, preserves native alpha and per-cell mean to max0.3125RGB error; root previously reviewed both palette sheets privately. The4096 version changes other regions too and has4x pixels/upload cost. It is retained as an alternative, not a drop-in for the current parent. Integration must copy ONLY O(u176..239,v112..175) into the latest private pack to preserve newer approved outside art/RISE, then regenerate affected identity sidecars. Neither option is installed or live/motion accepted. Nine verified files are not nine finished background areas.

## Later-stage author findings and limits

S23 S3 Scale2x proposal:39 keys/78 strict-pass and R5-clean files,136.19s/exit0. Class repair alters29,127 pixels. Structure/slats are crisper, but stone noise develops diagonal worm artefacts; native-noise hybrid is a separate proposal. Cells are still inferred32-grid, without S3 draw UV confirmation. S2 train proposal:20 keys/40 strict/R5-pass files,52.78s/exit0,58/58 same-class phase pairs consistent. Geometry is crisper but the prior weathered material is absent and camouflage has the same worms; it is not an overall visual improvement or installed replacement. Both are source/structure references pending actual look/source/live acceptance.

HUD EPX retrace is rejected: independent centre tests pass, but6/7 representative keys at both sizes fail island rules and readability worsens into blobs. Fourteen earlier cell-snap copies remain class-valid with visible curve bumps, not look-accepted. The new hit-gauge candidate covers11 keys/66 size/variant files, all primary/s2/centre pass; legacy11/11 files fail islands. The new chevrons are lumpy, so class success is not a fidelity acceptance. Cutout RGB fill belongs to composition and remains required.

Menu audit is intentionally scoped: first batch checks45 pack entries; second batch runtime-2048 checks83 files from9/11 folders, with7 primary passes.59 are centre-exact but fail connectivity/islands; others also fail centres. The second batch does not run s/2, and most1024/remaining pack files and two2048 folders are unprocessed. Frozen menus were never evidence all game interactions worked. Further repair/retrace and native state/source/live gates remain open.

S6 native-fill final pair passes2/2 strict with9,231 alpha corrections; together24 formerly failing files now have class-valid candidate copies, not accepted art. Dedither proposal28 files preserves alpha/classes but adds2,252 fringe flags diagnostically and needs look/live review. S7 burst proposal is included as an unaccepted proposal. All originals/failed attempts are retained. Exact per-file results, source pins and author limitations are in the source/report subset; mutable tool snapshots may be newer than executed copies.

## Continuity and unfinished project

The real native primary uses its registered allowed-worktree checkpoint; the canonical predecessor/retired original remain preserved. Actual hook activity is recorded, not synthesized Stop success. Bounded metadata monitor PID37556 ends16:17:23.189UTC and proves monitoring only. Source/worker/resource ownership remains explicit; no time-expiry GPU takeover or global driver/power change occurred.

Full actor/gun/boss UV/material mapping, native/in-game skin selectors, smooth modern HUD and all menu behaviors, distant signs/buildings/full palette coverage, successful modern Remix image/lifecycle and engine geometry/camera/material submission, ray tracing/DLSS in-game, audio remaster/listening, smooth full-stage gameplay, all seven stages and release/rollback remain incomplete. No completion percentage/date, stutter/audio fix,4K fidelity pass or installed experimental release is claimed. Private generated PNGs/binaries/native arrays/ROM/BIOS/cards stay on C: and are omitted; this is a source/report subset, not a portable clean full-source release.
''',encoding='utf-8',newline='\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=stamp(),sources=sources),indent=2)+'\n',encoding='utf-8')
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted),indent=2)+'\n',encoding='utf-8')
doc='docs/DEVELOPMENT-MATERIAL-RESULTS-20261114.md'
text='''# Development material routing — actual CPU results

Start-Development now uses the same receipt-validated saved material plan as Play-HD, with an explicit --frontend mode. The plan is validated before browser/bridge startup; -Stock and -WebOnly give explicit recovery options, and -Port is preserved in launcher links. No saved selection is rewritten. [Source, actual checks, review fixes and limits](../remaster-audit/frontend-tracker-results-20261114/README.md).

Nine Python cases, actual saved/direct/frontend validation, PowerShell syntax, custom-port saved/stock checks and Windows argument round-trip pass. No browser, bridge, game or GPU started. Live skin/frontend behavior remains unaccepted; full ship/weapon/boss mapping and in-game selectors remain unfinished.

The exact private v67 pack also passes16 native tracker/save-state/decode fixture processes. Region-O artwork is copied/verified in canonical C: storage, but requires ROI-only composition and fresh sidecars; it is not installed or live-accepted. Later-stage/HUD proposals preserve real numerical passes and visual/source failures, as detailed in the report.
'''
(r/doc).write_text(text,encoding='utf-8',newline='\n');shutil.copy2(r/doc,w/doc)
docs=['docs/'+f for f in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
current='''## Current frontend/tracker checkpoint —16:06UTC

Development launch now uses validated saved materials, explicit stock recovery and correct custom-port links. Nine unit cases and actual CPU validation/PowerShell/Windows-argv controls pass; saved pointer unchanged. The exact v67 pack passes16 tracker/save-state/decode fixture processes in6.037s. Region-O9pins/all11files are preserved in canonical C: storage; ROI-only integration/sidecar refresh and live look remain pending. [Actual code, checks and newer art/menu failures](../docs/DEVELOPMENT-MATERIAL-RESULTS-20261114.md).

No game/GPU/audio/browser/bridge test ran. Modern GPU qualification is the next controlled gate after explicit shared grant and current resource checks; elapsed time alone grants nothing. Full remaster/stage acceptance remains open. Metadata monitor PID37556 is bounded to16:17:23.189UTC; older checkpoints below are historical.

'''
for rel in docs:
    f=r/rel;title,tail=f.read_text(encoding='utf-8').split('\n',1);f.write_text(title+'\n\n'+current+tail.lstrip(),encoding='utf-8',newline='\n');shutil.copy2(f,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statefile.read_text(encoding='utf-8'));state['updated_at_utc']=stamp()
state['latest_verified_component']=dict(id='Development saved-material parity and actual-pack tracker regressions',evidence='remaster-audit/'+name+'/README.md',frontend_cpu_verified=True,tracker_fixture_processes=16,gpu_run=False,game_run=False,audio_run=False,live_acceptance=False)
state['actual_monitor']=dict(pid=37556,bound_end_utc='2026-11-14T16:17:23.189Z',watcher_only=True,proves_model_activity=False);statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');shutil.copy2(statefile,w/statefile.relative_to(r))
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dst=r/'remaster-audit'/name/f.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
subprocess.run(['git','add','-f','--','.gitattributes','remaster-audit/'+name,doc,*docs,*changed,statefile.relative_to(r).as_posix()],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=stamp(),packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),staged=True,pushed=False,gpu_run=False)
(n/'frontend-tracker-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
