"""Prepare a scoped new immutable source/evidence packet. Does not commit/push."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
w=Path('C:/github/Einhander-wt/display-history-opt-in');name='scene-texture-followup-20261114'
p=w/'remaster-audit'/name;p.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
assert subprocess.check_output(['git','branch','--show-current'],cwd=w,text=True).strip()=='codex/display-history-opt-in'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
extensions={'.py','.c','.cpp','.h','.inc','.json','.jsonl','.md','.txt','.log','.frag','.vert','.conf','.xml','.csv','.tsv'}
omitted=[]
def cp(src,dst):
    assert src.is_file(),src
    data=src.read_bytes()
    if src.suffix.lower() in extensions:assert b'\0' not in data,(str(src),'NUL in purported text')
    dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
def tree(src,dst):
    assert src.is_dir(),src
    for f in sorted(src.rglob('*')):
        if not f.is_file():continue
        if f.suffix.lower() not in extensions or f.stat().st_size>8*1024*1024:
            omitted.append(dict(path=str(f),bytes=f.stat().st_size,sha256=sha(f) if f.stat().st_size<100*1024*1024 else None,reason='Private generated binary/image/link payload; source/report subset published. Large binary digest is in its build receipt.'))
        else:cp(f,dst/f.relative_to(src))
for folder in ['scene-export','sdk-direct-cpu-r1','sdk-direct-cpu-r2','sdk-direct-3060-r1','sdk-direct-after-hour-r1','sdk-modern-table-build','sdk-modern-table-r1','sdk-release-header','sdk-release-bridge-source','sdk-package-reference','sdk-package-protocol','sdk-package-endpoint','sdk-package-zip-metadata','sdk-release-zip-index']:
    tree(n/folder,p/'root'/folder)
for file in ['prepare_scene_delivery.py','prepare_v65_builder.py','build_private_scene_v65.py','prepare_v66_builder.py','build_private_scene_v66.py','sdk_direct_control.cpp','build_sdk_direct_cpu.py','run_sdk_direct_3060.py','prepare_after_hour_probe.py','run_sdk_direct_after_hour.py','sdk_modern_table_probe.cpp','build_modern_table_probe.py','run_modern_table_cpu.py','run_modern_table_cpu_rejected_r0.py','check_sdk_package_source.py','check_sdk_package_endpoint.py','read_packman_protocol.py','check_package_zip_metadata.py','inspect_release_zip_index.py','stage_official_sdk_runtime.py','fetch_release_sdk_header.py','fetch_release_bridge_source.py','audit_recent_after_restart.py','check_post_reload_files.py','group_restart_findings.py','post-restart-audit.json','post-restart-grouped.json','post-reload-file-check.json','user-gpu-hold-timed-1144.json']:
    cp(n/file,p/'root'/file)
cp(n/'sdk-v016-release/staging-result.json',p/'root/sdk-v016-release/staging-result.json')
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
for folder in ['sampling-build-v65-word-sources-r1','sampling-build-v66-reviewed-scene-r1','sampling-build-v66-reviewed-scene-r2','sampling-build-v66-reviewed-scene-r3']:
    src=e/folder
    for f in sorted(src.iterdir()):
        if f.name=='src' and f.is_dir():tree(f,p/'private-builds'/folder/'src')
        elif f.is_file():
            if f.suffix.lower() in extensions:cp(f,p/'private-builds'/folder/f.name)
            else:omitted.append(dict(path=str(f),bytes=f.stat().st_size,sha256=sha(f) if f.stat().st_size<100*1024*1024 else None,reason='Private executable/object/link payload, retained locally with build-receipt pins.'))
cp(e/'sampling-build-v61-view-metrics-r2/include/pgxp.h',p/'root/scene-export/vendor/pgxp.h')
assert sha(e/'sampling-build-v66-reviewed-scene-r3/Einhander_Recompiled.exe')=='51ec32e3fdf4fc7567e807bce7106576a51e0c39ae73e65cb0599c33bd6a5a98'
assert json.loads((n/'scene-export/host-r8/result.json').read_text())['passed']
assert json.loads((n/'scene-export/runtime-glue-v66-r2/result.json').read_text())['passed']
assert json.loads((n/'scene-export/snapshot-audit-r2/result.json').read_text())['passed']
assert json.loads((n/'sdk-modern-table-r1/result.json').read_text())['passed']
omitted.append(dict(path=str(n/'sdk-v016-release/official-release.jar'),bytes=1035282184,sha256='13e1c2ea214b4156e91afb8d6034bf76f1a14a117cd59ec166e53c3840c5bd30',reason='Official release package verified during staging; not redistributed. Extracted DLL/runtime payloads also remain local; staging receipt pins all190 files.'))
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted,scope='Published source/report subset; no game/BIOS/ROM/cards, JAR, SDK DLLs, private executables, PDBs or generated link/object payloads. Build recipes require the recovered C: workspace and pinned retained inputs. Full clean source rebuild is not established.'),indent=2)+'\n')
(p/'README.md').write_text('''# Scene-capture review, SDK qualification and restart integrity — November 14, 2026

This packet records actual private implementation and test results from C:. The user's one-hour3090Ti reservation ended12:44:30UTC (05:44:30Phoenix); reuse after that hour was explicitly authorized. CPU work uses one below-normal worker. Two short SDK controls below are the only new GPU attempts in this packet; no game was launched. Every owned probe is closed and leases released. The installed game, installed Remix toolkit, global driver settings and unrelated projects were not modified.

## Reviewed scene transport — real engine hooks, no live acceptance

V65 replaces the earlier assumed contiguous GP0 source addressing with the actual source address recorded for each collected word, including cross-block/decrement cases. Reset/snapshot load invalidates partial capture without changing the guest snapshot format. V66 additionally implements generation-bound gp0-scene-v3 reads, sealed/complete admission, SF=1 and transform/lag validation, native signed11-bit coordinates and per-triangle culling/oversize eligibility. Unknown widescreen/correction mappings are ineligible. A quad preserves its native `(0,1,2),(2,1,3)` split; transform consistency is checked for each triangle even when another vertex is missing. Omissions are counted explicitly: sprites, untextured polygons/rectangles, lines and VRAM fills are not silently called a complete scene. Runtime owner binding occurs only on the emulation entry path; RPC cannot claim ownership. Default-OFF `PSXRECOMP_SCENE_CAPTURE=1` captures at most1024 polygons in770048bytes with no per-primitive file I/O, allocation, SDK or GL calls. Diagnostic PGXP lookup statistics do increment.

Actual CPU evidence: host-r8 recompiles the component and passes2932 enabled checks plus6 disabled checks, zero failures. Runtime-glue-v66-r2 compiles the exact v66r3 JSON/TCP handler with the actual Windows adapter and passes14 RPC cases plus foreign-thread rejection. Snapshot-audit-r2 is a separate Python oracle: positive/wrap controls pass and28 negative mutations are rejected. Its zero ideal-projection error applies only to the coherent fixture; it is not live geometry or world-camera proof. Earlier host/glue/oracle failures, incoherent early fixture values and superseded recipes remain included. No broad test rerun is substituted for a missing live test.

Private v66r3 compiles six translation units and links155 pinned inputs. EXE SHA256 `51ec32e3fdf4fc7567e807bce7106576a51e0c39ae73e65cb0599c33bd6a5a98`. Renderer source is frozen Claude-v4 `b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16`. Parent guest/platform objects are retained: this is not a clean full-source rebuild. Neither v65 nor any v66 candidate has run in-game. The current source and final handler are included alongside previous private revisions. Full scene/material coverage, camera/object factorization, real packet/render comparison and SDK submission remain unfinished.

## GPU controls — failed or aborted, retained as failures

During the user's3090hour, one permitted3060 diagnostic selected and confirmed the3060 adapter. The owned PID subsequently appeared on both3060 and3090 WDDM contexts, so the guard terminated it after9.994s before readback. Context appearance does not prove3090 ray-tracing compute, but the3090 was not proven untouched. No image/lifecycle test completed; result booleans are unexecuted, not evidence of image failure. The user's reservation marker stayed byte-identical and the3060 lease was released. No retry ran during the hour.

After the hour, one320x180,10fps,120-frame control explicitly selected3090Ti using the old installed API0.6 runtime. The initial owned D3D9 clear/readback correctly returns57600 magenta pixels. SDK final-color reads at frames7,31,119 all return the same configured magenta fallback with zero green scene pixels. Bypassing the SDK Present helper with the registered device's Present does not resolve the problem. Shutdown then stalls; the45s watchdog terminates the owned PID. It is gone and owned reservations are released. Image/lifecycle qualification FAILS. Fallback is consistent with an unavailable final rendering image; shader readiness was not measured and the cause is not established. The older source swapchain-reference hypothesis is not demonstrated as the sole cause.

## Matching modern SDK — privately staged, CPU table check only

The [official Minecraft Remix v0.1.1 release](https://github.com/NVIDIAGameWorks/rtx-remix-minecraft/releases/tag/v0.1.1) includes a newer native runtime. Its1035282184-byte JAR was downloaded at a bounded32MiB/s and full SHA256 verified: `13e1c2ea214b4156e91afb8d6034bf76f1a14a117cd59ec166e53c3840c5bd30`.190 non-PDB win64 files were extracted into a private folder with ZIP CRC and local SHA256 checks; PDB exclusions and exact staging metadata are recorded. The installed toolkit is unchanged. Requests for bare/ZIP package endpoints returned403 before the official release alternative; those failed requests are retained.

Matching [release commit7d2ba9f](https://github.com/NVIDIAGameWorks/rtx-remix-minecraft/tree/7d2ba9f18415a6b518b9824a3b8faa79da0d96ac) supplies API0.16.1 header SHA256 `e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c`. The new private d3d9.dll is `a8365272734cf5541e3600aeacb445c0fd102187dc3a167495a56809ce5891d9`. A fresh process initializes the288-byte interface successfully in0.268s, exits0 and is gone. Startup, Submit, interop-info and memory-texture function pointers are present. **Startup/Submit/Present, GPU rendering and gameplay were NOT called.** An initial wrapper KeyError occurred before DLL loading; that rejected wrapper is retained. Do not mix0.6 and0.16 structures.

The exact release bridge source and header document an explicit OpenGL external-memory/timeline-semaphore path with Submit separated from Present. This establishes an implementation route for a custom OpenGL engine; it does not make legacy runtime injection automatically compatible or establish working Einhander integration. Correct synchronization, adapter matching, image lifetime, HUD composition and clean Shutdown still need implementation/qualification. No working ray tracing, DLSS or newer DLSS feature set is claimed.

## Restart integrity incident and texture status

Windows restarted at12:49:22UTC (05:49:22Phoenix). A scoped scan of5066 known recent text files found90 entirely zero-filled files, all in the unpublished frozen renderer-v61-classmip-v5 folder. READY.json is10030 NUL bytes, SHA256 `e14183c9442b7279c1c07e6e0dd6d293e2bccd7b65a813f2cf5bcf01e716d67d`. It cannot establish acceptance. The failed freeze remains unchanged. Published990 file pins independently match committed Git blobs and both root/publication copies with zero errors. V66r3 receipt and modern header are intact. This is not a whole-drive filesystem health guarantee, and the restart/corruption cause is not established.

Native Claude was resumed in its original desktop session and visibly read the new Codex handoff/queue and began its own source integrity recovery. A mail watcher is not used as model-progress evidence. V5 recovery must use intact originals, fresh CPU replay and a NEW immutable freeze. At this publication preparation checkpoint no recovered v5 is accepted. V4's already published root replay remains the accepted CPU baseline; GPU/game qualification is still pending. RISE's earlier soft vector draft is rejected; faithful upright hand-authored lettering and all33 palette/fade variants remain in progress. Opaque far-background windows/buildings need actual artwork improvements; class mips cannot manufacture detail.

No new game/audio test ran. Prior v61 audio/smoothness acceptance still fails. Full background/texture coverage, realistic player/enemy/boss/weapon skins and selectors, modern HUD/menus, audio remastering and all seven stages remain incomplete. The overall remaster remains active.

## Included evidence and reproduction limits

SHA256SUMS.txt pins published bytes except itself. LOCAL-PAYLOADS.json explains omitted local payloads and digest sources. Private build scripts, exact patched source, host fixtures, JSON handler, separate oracle, commands/results/logs and SDK/recovery failures are included. Game/BIOS/ROM/cards, generated guest assets, executables, objects, sidecar/image assets, SDK DLLs and the JAR remain local. Reproduction of a complete executable requires those pinned retained local inputs; only the portable component tests are self-contained with the included pgxp.h. Source/report subsets do not constitute an installed release or end-to-end project acceptance.
''')
current='''## Current verified state — reviewed scene capture, modern SDK and restart recovery, November 14

The user's one-hour3090Ti reservation ended **12:44:30UTC (05:44:30Phoenix)**; reuse afterward is authorized. No owned renderer/game process remains. Current work is CPU-only integrity recovery and implementation, sequential and below normal, from C:. [Actual source, raw checks, failed controls and payload limits](../remaster-audit/scene-texture-followup-20261114/README.md).

Private v66r3 now compiles/links, with exact per-word GP0 sources, generation/complete gates, native raster eligibility and omitted-family diagnostics. Actual CPU checks pass2932 enabled/6 disabled; the exact handler/Windows adapter passes14 RPC cases plus foreign-thread control; an independent snapshot oracle rejects28 negative mutations. The executable has **not run**; retained parent objects prevent a clean full-source rebuild claim. World/camera/material mapping and scene submission remain incomplete.

One permitted3060 SDK attempt was guard-aborted when its owned PID appeared on both GPU contexts; no image result. After the hour, an old-runtime3090 direct-device control passed initial magenta readback but returned only fallback magenta for SDK output and stalled Shutdown; the45s watchdog closed it. A privately staged official runtime with matching API0.16.1 header now passes CPU function-table initialization only. Startup/Submit/Present and modern-runtime rendering have not run. Ray tracing/DLSS are not working in-game.

Windows restarted12:49:22UTC. Scoped integrity checks found90 all-zero text files, all in unpublished frozenv5; preserve the failed freeze and reconstruct/replay a NEW revision with native Claude. All990 published file pins match Git/root/publication copies. Native Claude's original session has resumed real recovery work. V5, RISE lettering, opaque far-background signs/buildings and full coverage remain unaccepted. Skins/selectors, HUD/menus, audio remastering and seven-stage acceptance remain unfinished. No new gameplay/audio test ran; prior v61 audio/smoothness failure remains open.

'''
for fn in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md']:
    f=w/'docs'/fn;s=f.read_text();title=s.split('\n',1)[0];tail=s[s.index('<details>'):]
    f.write_text(title+'\n\n'+current+tail)
    shutil.copy2(f,r/'docs'/fn)
for fn in ['AGENTS.md','coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']:cp(r/fn,w/fn)
attrs=w/'.gitattributes';s=attrs.read_text();entry=f'/remaster-audit/{name}/** -text -whitespace\n'
if entry not in s:attrs.write_text(s+'\n'+entry)
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'))
for f in p.rglob('*'):
    if f.is_file():dst=r/'remaster-audit'/name/f.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(dict(packet=str(p),files=len((p/'SHA256SUMS.txt').read_text().splitlines()),bytes=sum(f.stat().st_size for f in p.rglob('*') if f.is_file()),omitted=len(omitted),staged=False,committed=False,pushed=False)))
