"""Publish immutable, redacted evidence of the actual modern GPU failure."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
name='modern-remix-gpu-result-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='bd0299d2708a1855ca03857e489a85f435264a91'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
p.mkdir(exist_ok=False);sources=[]
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def cp(src,rel):
    src=Path(src);dest=p/rel;data=src.read_bytes();assert b'\0' not in data,src
    assert src.suffix!='.private' and not dest.exists()
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
for f in ['sdk_modern_gl_probe.cpp','run_modern_gl_probe.py','audit_modern_gl_image.py','run_granted_modern_probe.py','refresh_modern_grant_and_run.py','release_modern_gpu_window.py','grant_modern_gpu_window.py','request_modern_gpu_window.py','prepare_modern_gpu_result_delivery.py']:
    cp(n/f,'source/'+f)
for folder in ['modern-gpu-ready-r1','modern-gpu-grant-r1','modern-gpu-grant-r2','modern-gpu-request-r1','modern-gpu-request-r2','modern-gpu-release-r1']:
    cp(n/folder/'result.json','root/'+folder+'/result.json')
for f in ['result.json','release-result.json','request_modern_gpu_window.py','grant_modern_gpu_window.py']:
    cp(n/'modern-gpu-window-refresh-r1'/f,'root/modern-gpu-window-refresh-r1/'+f)
for f in ['start.json','result.json','stderr.log','stdout.json']:
    cp(n/'modern-granted-execution-r1'/f,'root/modern-granted-execution-r1/'+f)
probe=n/'modern-gl-parent-20261114T163312127399Z'
for f in ['result.json','stdout.jsonl','stderr.log','remix-dxvk.log','executed-runner.py','executed-image-oracle.py','dxvk.conf']:
    cp(probe/f,'gpu-probe/'+f)
images=[dict(file=f.name,bytes=f.stat().st_size,sha256=sha(f),retained_local=True) for f in sorted(probe.glob('readback.*.ppm'))]
assert len(images)==3 and len({f['sha256'] for f in images})==1
(p/'IMAGE-PINS.json').write_text(json.dumps(dict(images=images,omitted='Private generated images remain local; hashes and independent oracle results are published.'),indent=2)+'\n',encoding='utf-8')
monitor=sorted(n.glob('monitor-renewal-*'))[-1]
cp(monitor/'result.json','dated-monitor/result.json')
cp(r/'coordination/CLAUDE-SESSIONS-20261114.json','dated-coordination/roster.json')
cp(r/'coordination/CLAUDE-SESSIONS-20261114.json','source/coordination/CLAUDE-SESSIONS-20261114.json')
run=json.loads((probe/'result.json').read_text());outer=json.loads((n/'modern-granted-execution-r1/result.json').read_text());release=json.loads((n/'modern-gpu-release-r1/result.json').read_text())
assert not run['passed'] and run['gpu_executed'] and not run['game_executed']
assert run['exit']==30 and outer['outer_exit']==1 and release['explicit_release']
assert outer['managed_parent_identity_absent'] and run['owned_process_gone']
assert run['owned_marker_released'] and run['owned_lock_released']
assert not run['three_distinct_images'] and not run['lifecycle_passed']
text='''# Modern Remix GPU probe — actual failure, November 14

The private API0.16.1/OpenGL probe ran on the RTX3090Ti at16:33:12–16:33:53UTC and FAILED. It created a small320x180 nonactivating window and submitted32 synthetic frames. This is a diagnostic test, not the game or a remaster release.

Startup, material/mesh/camera/draw, Submit, InteropInfo and Present returned0. The initial owned OpenGL readback contained57,600 magenta pixels, so the basic readback control passed. The actual target adapter was independently observed. These successes do not prove that submitted geometry rendered.

All three scene samples (frames7/23/31, offsets-2/0/+2) have exactly the same SHA2568b329bbf0b37386cd7f8094766a953d89287b83a5a7b3aef400ff2dc364727a2, zero green pixels and no expected projected triangle. They have zero fallback-magenta pixels, so this is not the old fallback-magenta result. Independent image oracles reject all three. No successful moving geometry, image synchronization, ray-traced gameplay or DLSS acceptance is established.

Mesh/material destruction returned0, but Shutdown entered and exceeded its15-second internal deadline. The child exited30 after40.159s; the managed wrapper exited1 after41.681s. The independent45-second parent termination watchdog was not used. The probe result records lifecycle_passed=false. SDK log capability notices are not evidence those features are integrated or usable in-game. The log also reports a late swapchain initialization and undisposed common device objects; their causal role requires source review rather than assumption.

Cleanup is verified: child34664 and managed parent38504 are absent, both nonce resource markers were released, and the shared broker was explicitly released at16:35:17UTC, revision10, event10767db9-5854-49c9-ba59-9dbb3cfc1502. No automatic expiry takeover, unrelated process kill or global driver/power change occurred. CPU texture jobs may resume under the coordinator's two-job limit. Root continues CPU-only diagnosis; a further GPU attempt requires a fresh reviewed plan and grant.

## Exact execution and preserved prestart failure

The first official grant, revision5, expired unused during context recovery. No graphics process or execution directory was created under it. Root explicitly released it (revision6), requested again and committed a fresh grant (revision8), immediately executing the reviewed parent. The grant's empty owned-heavy process inventory and CPU20%/74GiB gate are recorded. The wrapper independently sampled CPU15.6% before launch, used CPU15 and BelowNormal priority, and passed a fenced token locally without logging it.

Executed command: python -X utf8 run_modern_gl_probe.py --run-after-explicit-user-release, through the reviewed wrapper. Actual parent creation time1794673991.948414 and the child command, source/DLL/executable SHA256 pins, frame oracles and process/cleanup checks are in the raw reports. Parent source d545a7de7ef220e1c30eadb69eef3aa12f64db60861c40d56df485f4d36ea122; EXE3911f74c0e380f9358d32f529ee1de440b709bdf8fec93b1ef4ea12a91643d1d; private DLL a8365272734cf5541e3600aeacb445c0fd102187dc3a167495a56809ce5891d9.

## What remains

Investigate actual output/readback synchronization, geometry submission/camera conventions, initialization readiness and shutdown ownership using source and these failed logs. Do not relax the image oracle or count API return codes as visual success. World geometry/camera/material transport, actual in-game RT/DLSS, texture ROI composition/live acceptance, complete skins/HUD/menu interactions, audio/listening/performance and all seven stages remain unfinished. No game/audio test, installation or whole-project completion is claimed here.

Six actual native Claude sessions now have registered owner/checkpoint routing; the dated roster records the UI/support additions. Their source and art work continues independently. A bounded metadata monitor was renewed, but proves monitoring only. Earlier immutable packets and failed evidence remain unchanged.

The packet is a source/report subset. SDK DLL/JAR, executable, cache, sentry payloads, generated images, live grant tokens/private broker files, ROM/BIOS, native game data and user state are excluded and retained locally where applicable. Image hashes are published. SOURCE-MAP binds every copied source/report to its local provenance. SHA256SUMS binds packet bytes.
'''
(p/'README.md').write_text(text,encoding='utf-8',newline='\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources),indent=2)+'\n',encoding='utf-8')
doc='docs/MODERN-REMIX-GPU-RESULT-20261114.md'
doc_text='''# Modern Remix GPU qualification — actual result

The private320x180/32-frame modern Remix probe ran on the3090Ti at16:33UTC and failed. Startup/frame API calls returned success, but all three images were identical and lacked the expected triangle. Shutdown hit its15-second internal deadline (child exit30); the managed wrapper exited1/41.681s. [Exact source, raw results, image pins, process cleanup and limitations](../remaster-audit/modern-remix-gpu-result-20261114/README.md).

The child and parent are absent, owned resource markers are gone, and the shared GPU reservation was explicitly released at16:35:17UTC/revision10. Root continues CPU-only diagnosis while bounded Claude texture work resumes. No global driver/power setting changed. Actual game geometry, ray tracing, DLSS, gameplay/audio and seven-stage release acceptance remain open.
'''
(r/doc).write_text(doc_text,encoding='utf-8',newline='\n');shutil.copy2(r/doc,w/doc)
docs=['docs/'+f for f in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md','SHARED-GPU-RESULTS-20261114.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
current='''## Actual modern GPU result —16:35UTC

The private modern Remix probe ran on3090Ti and FAILED: three identical outputs with zero expected triangle pixels; Shutdown exceeded its15-second deadline, child exit30/40.159s, wrapper exit1/41.681s. Startup/frame return codes and the initial GL readback pass do not establish rendering. Both processes are absent, markers removed and shared grant explicitly released revision10. [Actual evidence and remaining work](../docs/MODERN-REMIX-GPU-RESULT-20261114.md).

Root continues CPU-only diagnosis/publication; bounded Claude texture/HUD work resumes. No game/audio test, installed runtime, RT/DLSS gameplay or full remaster acceptance is claimed. Six native sessions are registered. Metadata monitor PID37252 ends17:06:21.828UTC and proves monitoring only. Earlier dated checkpoints below are historical.

'''
for rel in docs:
    f=r/rel;title,tail=f.read_text(encoding='utf-8').split('\n',1)
    f.write_text(title+'\n\n'+current+tail.lstrip(),encoding='utf-8',newline='\n');shutil.copy2(f,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';s=json.loads(statefile.read_text(encoding='utf-8'))
s['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
s['latest_verified_component']=dict(id='Modern Remix private GPU qualification failed',evidence='remaster-audit/'+name+'/README.md',gpu_run=True,passed=False,game_run=False,audio_run=False,clean_shutdown=False,owned_processes_absent=True,shared_grant_explicitly_released=True,live_acceptance=False)
s['actual_monitor']=dict(pid=37252,bound_end_utc='2026-11-14T17:06:21.828Z',watcher_only=True,proves_model_activity=False)
statefile.write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8');shutil.copy2(statefile,w/statefile.relative_to(r))
shutil.copy2(r/'coordination/CLAUDE-SESSIONS-20261114.json',w/'coordination/CLAUDE-SESSIONS-20261114.json')
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dst=r/'remaster-audit'/name/f.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
changed=['.gitattributes','remaster-audit/'+name,doc,*docs,'coordination/CLAUDE-SESSIONS-20261114.json',statefile.relative_to(r).as_posix()]
subprocess.run(['git','add','-f','--',*changed],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),staged=True,pushed=False,gpu_run=True,probe_passed=False)
(n/'modern-gpu-result-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
