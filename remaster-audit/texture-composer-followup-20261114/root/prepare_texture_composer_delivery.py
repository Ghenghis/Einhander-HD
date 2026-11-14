"""Freeze a new owned source/report packet; never rewrite preceding packets."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in')
name='texture-composer-followup-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=me.cpu_affinity();me.cpu_affinity([11 if 11 in allowed else allowed[0]])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='ee7824a4e4e869972045b914225cfdf1efab8fcc'
p.mkdir(exist_ok=False)
sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest()
ext={'.py','.c','.cpp','.h','.inc','.json','.jsonl','.md','.txt','.log','.mjs','.java','.csv','.tsv','.glsl','.frag','.vert','.rsp','.ps1','.bat','.cmd','.i'}
sources=[];omitted=[]
def cp(src,dst):
    data=src.read_bytes();assert b'\0' not in data,src
    if src.suffix=='.json':json.loads(data)
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    sources.append(dict(source=str(src),published=dst.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dst)))
def tree(src,dst):
    assert src.is_dir(),src
    for file in sorted(src.rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts:continue
        if file.suffix.lower() not in ext or file.stat().st_size>12*1024*1024:
            omitted.append(dict(source=str(file),bytes=file.stat().st_size,reason='Generated private binary, image/native-array or large payload. Retained locally and pinned by author/build receipts.'))
        else:cp(file,dst/file.relative_to(src))
folders=['sdk-modern-gl-cpu-r4','modern-r4-controls-cpu-r1','modern-parent-cleanup-cpu-r1','modern-parent-cleanup-cpu-r2','modern-parent-cleanup-cpu-r3','shared-launch-guard-cpu-r1','packet-preparation-r0-failure','composer-cutout-fill-cpu-r1','real-composer-fill-cpu-r1','rise-native-alpha-r1','v6-freeze-integrity-r1','user-release-20261114T1403','user-gpu-handback-20261114T1438','monitor-renewal-20261114T140109Z','monitor-renewal-20261114T142521Z','monitor-renewal-20261114T145329Z','modern-gl-parent-20261114T140220467359Z','modern-gl-parent-20261114T141350512672Z']
for folder in folders:tree(n/folder,p/'root'/folder)
for extra in sorted(n.glob('modern-gl-parent-*')):
    if extra.name not in folders:tree(extra,p/'root'/extra.name)
files=['sdk_modern_gl_probe.cpp','run_modern_gl_probe.py','build_modern_gl_cpu_r2.py','build_modern_gl_cpu_r4.py','audit_modern_gl_image.py','test_modern_gl_image.py','test_modern_parent_cleanup.py','capture_modern_r4_controls.py','test_composer_cutout_fill.py','verify_real_cutout_fill.py','prepare_rise_native_alpha.py','compose_rise_f32.py','compose_rise_native_alpha_r1.py','rise-native-alpha-plan.json','rise-native-alpha-compose.log','rise-native-alpha-native-admission.log','rise-native-alpha-composition-result.json','verify_v6_freeze_files.py','renew_session_monitor.py','record_user_gpu_release.py','hand_back_gpu_to_user.py','checkpoint_release_and_monitor.py','cpu-session-delivery.json','cpu-session-pr-verification.json','pr-resource-correction-result.json','prepare_texture_composer_delivery.py']
for file in files:cp(n/file,p/'root'/file)
cp(n/'sdk-release-header/remix_c.h',p/'root/sdk-release-header/remix_c.h')
candidate=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-rise-f32-r1'
cp(candidate/'candidate.json',p/'private-rise-composition/candidate.json');cp(candidate/'executed-compose.py',p/'private-rise-composition/executed-compose.py')
rise=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector'
for folder in ['authored/20261114T135842Z','expand33/20261114T135902Z']:tree(rise/folder,p/'rise-f32'/folder)
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v6'
assert sha(f/'READY.json')=='33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0'
assert json.loads((n/'v6-freeze-integrity-r1/result.json').read_text())['passed']
tree(f,p/'claude-v6-source-report-subset')
stage=r/'remaster-audit/parallel-stages-20261114'
for lane,folders,files in [
 ('s23',['proposals/s3-dither-hybrid-a-20261114T140153Z','proposals/s3-dither-hybrid-b-20261114T140153Z','proposals/s3-dither-hybrid-a-20261114T143143Z','proposals/s3-dither-hybrid-b-20261114T143143Z','runs/j2-20261114T140153Z','runs/j2full-20261114T143143Z','runs/admission-20261114T142941Z','tools'],['S2-S3-GATES.md']),
 ('s45',['strict-audit','probe-audit','repairs','checklist/20261114T143022Z','tools'],['README.md','BACKLOG-S45.md','REPAIR-PROPOSALS.md','DUERER-8BPP-PLAN.md','PANORAMA-05E1881C-OWNERSHIP.md']),
 ('s67',['repairs','reports','tooling/timeout-profile','tools','requests'],[])]:
    for folder in folders:tree(stage/lane/folder,p/'stage-work'/lane/folder)
    for file in files:cp(stage/lane/file,p/'stage-work'/lane/file)
for file in ['texture-cpu-slot.json','texture-dual-slot.json','texture-job-queue.json']:
    src=r/'remaster-audit/runtime-review/session-continuation-20261114'/file
    if src.exists():cp(src,p/'dated-coordination'/file)
cp(r/'remaster-audit/build_stage1_frozen_candidate.py',p/'root/build_stage1_frozen_candidate.py')
cp(r/'tools/coordination/shared_gpu_guard.py',p/'root/shared_gpu_guard.py')
cp(n/'test_shared_gpu_launch_guard.py',p/'root/test_shared_gpu_launch_guard.py')
hold=r/'remaster-audit/comfy-authoring/GPU-RESERVED';assert sha(hold)=='91c25dccc9956aa77ac2a24935b2bb6f11e82371700d114cf841fbfa04626796';cp(hold,p/'dated-coordination/user-gpu-hold.json')
monitor=json.loads((n/'monitor-renewal-20261114T145329Z/result.json').read_text())
rosterfile=r/'coordination/CLAUDE-SESSIONS-20261114.json';roster=json.loads(rosterfile.read_text());roster['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();roster['gpu_policy']='3090 Ti handed back to Pizza Tycoon after user availability request at14:38:45 UTC. Root never launched modern GPU probe. Current user-project reservation has no expiry and blocks new Einhander GPU jobs until release; CPU work continues.';roster['monitoring_handoff'].update(watcher_pid=monitor['pid'],current_bound_end_utc=monitor['bound_end_utc'],renewal_receipt='remaster-audit/runtime-review/gpu-texture-remix-20261114/monitor-renewal-20261114T142521Z/result.json');roster['sessions'][0]['live_hook_status']='Canonical project hook is not taking effect in original parent-root native session; coordinator is correcting exact session root/replacement, no global hook change. Actual manual source/results work verified.';rosterfile.write_text(json.dumps(roster,indent=2)+'\n');cp(rosterfile,p/'dated-coordination/CLAUDE-SESSIONS-20261114.json')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources,scope='Dated read-only snapshots. Mutable author tools may be newer than frozen run copies; use executed source/receipts for the actual run. Snapshots of queues do not prove future liveness.'),indent=2)+'\n')
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted,scope='Source/report subset. No SDK DLL/JAR, private executable/object, generated PNG, native words/CLUT/array, game/ROM/BIOS/cards are redistributed. Full private RISE pack and sidecars remain on C:; their exact ledgers are included. This is not a clean full-source release.'),indent=2)+'\n')
(p/'README.md').write_text('''# Texture composition, decode-worker evidence and reviewed Remix probe — November 14, 2026

This packet records actual CPU/source work and preserved failures from C:. The RTX 3090 Ti was released by the user and later handed back to Pizza Tycoon at14:38:45 UTC after another availability request. **The modern GPU test never started.** No new game, GPU image/lifecycle or audio result is claimed. No power/driver setting or installed game/toolkit was changed. The current user-project hold has no expiry. Work continues on CPU; two bounded texture lanes are permitted only with separate CPU13/15, below-normal priority, resource gates and no overlap with an exclusive engine build/live test.

## Actual composition implementation and results

The canonical `build_stage1_frozen_candidate.py` gains an explicit opt-in `cutout_rgb_fill` plan policy. It requires pinned CPU library/source/header/build-receipt references, fills invisible RGB only after the final image/alpha transforms, rejects alpha or visible-RGB changes, recomputes output PNG hashes and records per-key invisible changes. With no policy it loads no fill library. New candidate writes use exclusive temporary files, flush/fsync and atomic replacement to break immutable-parent hardlinks. Ten CPU controls pass, including bad-pin, noncategorical alpha and mutating-function rejection. This is not automatic native source admission or class-ownership repair.

On an actual Stage 5 audit probe `9F3D98EF-A345AE9E` at2048², the independent border calculation matches the author's100,550 R5 flags; composition fill reduces them to0. Alpha and every visible RGB byte stay identical. All3,153,247 cutout RGB pixels change because the fill reaches deeper invisible texels; this exceeds the border-only R5 count by design. The source remains an unconfirmed audit probe, not admitted artwork. No simulated/live filtering equivalence or screen-space quality pass is substituted for these checks.

The corrected float32 RISE expansion has33 variants and reproduces the approved reference PNG byte-for-byte. Root's extra composition precheck correctly rejected a stronger, mistaken assumption: its vector-refined silhouette is not pixel-identical to native-nearest alpha. The failure/recipe is preserved. A separate exact-native-alpha option changes5,242 alpha pixels per palette versus that vector version (2,081 newly visible,3,161 newly hidden), retains common-visible RGB and uses the former cutout fill in newly visible pixels. It adds no new detail there. Both variants remain available; the native-alpha option has root and Claude private-composition review, not in-game acceptance.

The NEW private `world-integrated-rise-f32-r1` pack composes33 exact-native-alpha entries and retains all1,666 other parent image hashes. All33 composed RGBA images match that option; all1699 entries pass the existing native-admission executable. Candidate SHA256 `aa9d5798cef3176f20f72670b1c861cfb22eab446837c9a32c8a60294aaa7c27`. Native admission does not prove every older entry passes the newer whole-cell rules. Source/parent bytes are unchanged. No candidate was installed or launched, and visual/motion/palette-cycle acceptance remains open.

## v6: real decode-worker implementation, host evidence, private link still pending

Claude's NEW frozen v6 moves RGB-sidecar identity hashing from first draw to the below-normal decode worker before immutable publication. A lease-bound O(1) accessor rejects unavailable/mismatched identity and has no synchronous fallback hash. It uses the reviewed v48 source closure preserving the v61 incremental-upload ABI; canonical source that dropped the ABI remains rejected. Flags stay default off and exact-value gated; class-sidecar validation remains separate. Shader/GL source is unchanged from v5-r2.

Root independently verifies all1,111 frozen file pins (155,324,734 bytes), READY `33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0`, no NUL-filled or unlisted file. Author's actual report records7,534 fixtures,56 implementation mutants,16 GL-stub cases,24 glue mutants,92 pack-mode checks and6 pack mutants passing, patched/control compilation and GLSL validation successful. Pack identity/lifetime is exercised with real worker threads and immutable leases. **The outer run_host process exit code was not captured**; its final pass report and child-step codes are evidence, not a substitute numeric exit. Selftest-build/freeze wrapper exits0 are captured. Root has not yet replayed the new host suite or linked the rebuilt pack TU into a game executable. GL selftest is built, NOT run; its extra unused-function warning is disclosed. The freeze overlapped the short r4 compile by up to9s, so compile timings are not isolated performance measurements.

## Modern Remix/OpenGL r4: reviewed and compiled, GPU NOT RUN

Root implemented the independent review: GL objects/context/window retire before main-thread native Shutdown; DLL unload is last; a child deadline attributes a stuck Shutdown. Successful Submit is paired with Present even on failed interop handling, with no wait on an unqualified client value. GUI composition is disabled for the diagnostic. Per-frame image imports and timeline checks remain explicit. Three known translated triangle phases require three distinct images; the independent oracle rejects a frozen frame as well as uniform/fallback output. Source SHA256 `3f77474fea5208bafae6a7cd82132f0188584a030112c7db68915e04f382a2dc`; private EXE `3911f74c0e380f9358d32f529ee1de440b709bdf8fec93b1ef4ea12a91643d1d`.

Actual r4 syntax/object/link commands exit0;14 CPU contracts pass and the child correctly refuses graphics without its owned nonce lease. Twelve captured image-oracle controls and seven cleanup controls pass, including delayed/failed termination and a foreign-marker race. The parent honours GPU/CPU-quiet reservations, keeps leases if termination cannot be established, pins the exact binary/runtime/oracle and requests termination at45s; total observation/cleanup can take about70s. The resource gate distinguishes idle from explicitly bounded low-power desktop activity and does not call the latter idle. The first12-control stdout was truncated and affinity unqualified; a separate captured repeat records CPU11/below-normal and full raw output. Earlier compiler/legacy-runtime failures remain immutable in preceding packets.

The planned GPU window was returned unused when the user requested the card. Startup/Submit/Present interoperability, real moving images and clean lifecycle are still NOT RUN on this modern build. Engine scene/material/camera integration, ray tracing/DLSS in-game and newer feature sets are not accepted. CPU test success cannot establish those outcomes.

## Later-stage results and remaining defects

S2/S3: two FULL14-key repair variants now produce56 files total; strict/R5 checks pass and outside replaced cells alpha/visible RGB are byte-identical. They restore native grain where v1 made blobs, adding no HD detail. The granite is improved by variant a; b barely changes it. Wall shimmer simulation returns near native (about2.9× v1 without mips). These remain unconfirmed proposals: every S3 selected key still lacks draw evidence. The keyed142-row admission checklist has110 blocked,28 pending live confirmation and4 not authored; it is not a unique-sign or whole-game denominator. Prior partial/bad-crop attempts remain preserved.

S4/S5: corrected bounds now distinguish s/2 displacement from connectivity-only primary. Selected review exports: S4 primary26/26 and strict26/26; S5 primary24/24, strict22/24. Their opaque review palettes had hidden transparency defects. Real cutout probes: S4 partial24/24 pass both class policies but all have R5 fringe; one planned probe was skipped. S5 complete24 files: primary20/24, strict16/24, all have fringe. Smoke and shock/debris FX reveal class failures. New eight-file class-snap proposals clear all measured class counters with common-visible RGB retained, but change visibility and need colour/look review. The failed Windows launcher and immediate-versus-later child-absence discrepancy are preserved. Native 8bpp Duerer/boss-arena source, CLUTs and actual draws remain unresolved; static pair frequency is not live proof.

S6/S7: original selected strict counts stay178/202 and52/52. Original counters labelled connectivity used the wrong bound; new corrections preserve those files, prove the primary pass/fail deduction from R4/source and measure exact counts during repair. S6 r1 repair failed on a Windows filename and is retained; r1b produces22 files, r1c the final2. All24 new copies pass strict and connectivity checks. Their83,007 alpha changes include new visibility and STP toggles; common-visible RGB is unchanged, not all visible colour. Newly exposed teal fill is wrong for some native-dark smoke texels and remains a look blocker. Stage1-shared explosion originals are untouched. S7's inferred planet pairing still lacks source/draw confirmation.

The isolated Stage6 timeout-profile proposal was corrected through r4 after independent reviews caught wrong-stage, time-window, unsupported-residency and relabelled-snapshot holes. Worker55-case evidence and actual native-event/wrong-frame controls are included, but root has not independently replayed/promoted it. A timeout can never count as a Stage6 clear. The first r3 harness traceback was overwritten before preservation; the author discloses that limitation. No real AQ-13 capture exists.

## Continuity and full-project limits

Four real native workers have produced concrete stage/source results. The original parent-root session's canonical continuity hook was not taking effect; correction of that exact session/config or orderly replacement is in progress, without a global hook or fabricated user pause. Other workers' own hooks/mail turns are observed. The actual metadata monitor PID1652 is bounded to14:55:21UTC; it does not prove future uninterrupted model activity. Dated queues/roster snapshots are not live scheduler guarantees.

The whole remaster remains incomplete: all world/background/sign coverage; final player/enemy/boss/weapon skins/selectors; modern HUD/menus; remastered audio; efficient and qualified engine/Remix integration; seven-stage gameplay/audio/visual and release acceptance. No new stage clear, stutter/audio resolution,4K fidelity pass, installed release, completion percentage or finish date is claimed. Consult SOURCE-MAP and LOCAL-PAYLOADS for exact original C: paths and omitted private assets. Previous evidence packets are unchanged.
''')
current='''The 3090 Ti was handed back to Pizza Tycoon at14:38:45UTC; the modern GPU test never started and a new user-project hold blocks launches until release. CPU work continues. New private RISE composition replaces33 variants, preserves1,666 other images and passes native admission for1,699 entries, without installation/live acceptance. Opt-in composition fill passes10 controls and removes100,550 measured border flags on a real audit probe while preserving alpha/visible RGB.

Root verifies1,111 v6 freeze pins; author host report passes7,534 fixtures plus mutation/glue/pack checks, but its outer process exit was not captured and root replay/private game link remain pending. Modern GL r4 compiles and passes14 CPU contracts,12 image controls and7 cleanup controls; actual modern GPU images/lifecycle and in-game RT/DLSS remain NOT RUN. Later-stage repaired copies still require source/colour/live review; current policy corrections and failures are retained. [Actual source, checks, failures and limits](../remaster-audit/texture-composer-followup-20261114/README.md).

'''
docs=['docs/'+x for x in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]
for rel in docs+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']:
    file=r/rel;title,tail=file.read_text().split('\n',1);file.write_text(title+'\n\n## Latest texture/engine CPU checkpoint\n\n'+current+tail.lstrip());shutil.copy2(file,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statefile.read_text());state['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();state['latest_verified_component']=dict(id='Private RISE native-alpha composition and CPU decode/interop evidence',evidence='remaster-audit/'+name+'/README.md',status='CPU composition/admission verified; v6 file pins verified and author report qualified; no new GPU/game acceptance');state['latest_resource_policy']=dict(gpu_user_project_hold=True,modern_gpu_test_started=False,requires_explicit_user_release=True,hold_sha256=sha(hold),handoff_receipt='remaster-audit/runtime-review/gpu-texture-remix-20261114/user-gpu-handback-20261114T1438/result.json');state['actual_monitor']=dict(pid=1652,bound_end_utc='2026-11-14T14:55:21.254Z',watcher_only=True,proves_model_activity=False);statefile.write_text(json.dumps(state,indent=2)+'\n');shutil.copy2(statefile,w/statefile.relative_to(r))
shutil.copy2(r/'remaster-audit/build_stage1_frozen_candidate.py',w/'remaster-audit/build_stage1_frozen_candidate.py')
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(file)+'  '+file.relative_to(p).as_posix()+'\n' for file in sorted(p.rglob('*')) if file.is_file() and file.name!='SHA256SUMS.txt'))
for file in p.rglob('*'):
    if file.is_file():dst=r/'remaster-audit'/name/file.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dst)
paths=['.gitattributes','remaster-audit/'+name,'remaster-audit/build_stage1_frozen_candidate.py',*docs,'coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md',statefile.relative_to(r).as_posix()]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True,timeout=20);subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),bytes=sum(f.stat().st_size for f in p.rglob('*') if f.is_file()),staged=True,committed=False,pushed=False,new_gpu_test_started=False)
(n/'texture-composer-stage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
