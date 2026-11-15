"""Prepare a new evidence packet and current-state docs, without staging unrelated work."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
w=Path('C:/github/Einhander-wt/display-history-opt-in')
name='cpu-hour-integration-20261114';dst=w/'remaster-audit'/name;dst.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
assert json.loads(hold)['expires_utc']=='2026-11-14T12:44:30Z'
assert subprocess.check_output(['git','status','--porcelain'],cwd=w,text=True)==''
excluded={'.exe','.dll','.obj','.bin','.hdcm','.png','.i','.d','.rsp','.ppm'}
omitted=[]
def copy_file(p,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
def copy_tree(source,target,omit=True):
    for p in sorted(source.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(source)
        if omit and p.suffix.lower() in excluded:
            omitted.append(dict(source=str(p),sha256=sha(p),bytes=p.stat().st_size,reason='Local payload; source/report subset published'))
        else:copy_file(p,target/rel)
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v4'
assert sha(f/'READY.json')=='93a97669e6d9cf5fbd75536d5261efbe5855f1299bb91683badea4f7a395299e'
pins=0
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
    h,p=line.split('  ',1);assert sha(f/p)==h,p;pins+=1
assert pins==306
copy_tree(f,dst/'claude-v4-source-report-subset')
for p in ['verify_v4_cpu.py','build_private_class_v63.py','prepare_v64_builder.py','build_private_scene_v64.py','set_timed_gpu_hold.py','user-gpu-hold-timed-1144.json','prior-user-hold-before-timed-update.json','fetch_sdk_diagnostics.py']:
    copy_file(n/p,dst/'root'/p)
for p in ['v4-cpu-verification-r1','v4-cpu-verification-r2','scene-export','sdk-diagnostic-reference']:
    copy_tree(n/p,dst/'root'/p)
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
for p in ['sampling-build-v63-classmip-r1','sampling-build-v64-scene-capture-r1','sampling-build-v64-scene-capture-r2']:
    b=e/p
    for q in sorted(b.iterdir()):
        if q.is_dir():
            if q.name=='src':copy_tree(q,dst/'private-builds'/p/'src')
            continue
        if q.suffix.lower() in excluded:
            omitted.append(dict(source=str(q),sha256=sha(q),bytes=q.stat().st_size,reason='Private binary/object/link payload remains local'))
        else:copy_file(q,dst/'private-builds'/p/q.name)
copy_file(e/'sampling-build-v61-view-metrics-r2/include/pgxp.h',dst/'root/scene-export/vendor/pgxp.h')
census=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/runs-census/20261114T114657Z/result.json'
assert sha(census)=='406ef8fb2f0226110561397336eb1e6d4c889b4d39da0d1e2ad23740ce3eb29d'
copy_file(census,dst/'claude-rgb-fringe-census.json')
(dst/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(frozen_v4_original_pins_verified=pins,omitted=omitted,
    note='All v4 original pins verified locally. Published subset does not include all original payloads. Root source/report files and recipes are included; complete executable clean build and proprietary game inputs are not supplied.'),indent=2)+'\n')
readme='''# CPU-only texture and scene bridge integration — November 14, 2026

This packet records work performed while the user reserves the RTX3090Ti for another project. The reservation runs from **11:44:30 to12:44:30UTC (04:44:30–05:44:30Phoenix)**. The user authorizes reuse after that hour and permits the3060 if needed. This packet's new work uses **neither GPU**, does not launch the game and leaves the user's timed marker unchanged. Work remains on C:. Compilation and host replay use one logical CPU, below normal priority, sequentially. Earlier probe results are historical, not rerun here.

## Texture renderer and independent replay

Claude froze v4: READY93a97669e6d9cf5fbd75536d5261efbe5855f1299bb91683badea4f7a395299e; SHA256SUMS f60c41b365e7cc6a49cbf11b4ac4df16e87e0183e0784df3b3386fd9cecc689f. Root independently verifies **all306 original file pins**, then recompiles/replays **6,185fixture checks, zero failures**, and six exact-glue modes: off2, invalid-env2, combined33, levels-only32, RGB-only25, opaque-control25; all pass. These are CPU tests with recording GL stubs. Root did not rerun the author's28/28 implementation and8/8 glue mutation tests, GPU self-test, full game or visual acceptance.

V4 adds identity-bound has-cutout gating to the reviewed RGB-only filter and combines it with offline class-aware mip levels. Both env opt-ins require exactly `1`, default OFF, and an explicit directory containing eight verified class sidecars. RGB-only uploads no levels; opaque pages bypass the extra shader fetches. Point sampling, native-edge override and PSX class/STP/discard behavior retain their respective paths. At mixed edges, isotropic four-tap reconstruction differs from hardware anisotropy. Real GPU cost is unmeasured. Offline levels avoid the rejected95–344ms synchronous builder; admission still hashes/checks pixels on first slot use, with measurable CPU cost, so no stutter fix is claimed.

Root's first v4 replay used wrong integer widths to decode the opaque-control sidecar header. Its fixtures and first five integration modes ran, but the opaque case failed. That erroneous runner/log is preserved under `root/v4-cpu-verification-r1`; corrected `r2` passes. This was a replay-harness error, not proof of a renderer defect.

The unlaunched v62 global-RGB executable is **retired**. Claude's review found that its env scope conflicted with v4, opaque textures paid unnecessary fetches, a new runtime `fprintf` violated the core rule, and a counter could count facade draws where the RGB branch was inactive. Its old evidence stays immutable; its prepared visual recipe must not be used. Scoped v4 semantics are authoritative.

## Private executable builds — compiled, not launched

V63 rebuilds renderer/debug TUs against pinned v61 headers and retained parent objects, adding a read-only `hd_class_mips` RPC. Complete executable SHA256 **9b47f310e5de31762bdd815a59c73f21170be6456146b701d3baa908cbb65c3e**. Its renderer is byte-identical to frozen v4 b41b7ab5843ce1a6d4710cc010be6d44f3127a77ce660cc2527eb98e6cd0cb16. No production binary/config was installed.

V64r2 adds the GP0 observer described below. Six TUs compile and the executable links with155 pinned link inputs: three rebuilt core TUs, three observer TUs, other parent guest/platform objects retained. Complete executable SHA256 **2bfb715fca71fff81f70d2e4d1acd61f1e83ddd1f803663467a528b5800972c5**. This is not a clean full-source rebuild. First v64r1 failed compilation because Python removed escaped quotes in the new RPC's JSON literals; failed source/log/build receipt are retained. R2 corrects the raw-string generation and links. Neither executable has run.

## Actual draw-packet capture bridge

The new default-OFF `PSXRECOMP_SCENE_CAPTURE=1` observer hooks each fully collected GP0 command before dispatch and ticks at the existing frame-counter increments. Explicit `scene_capture` RPC arm waits until the next frame boundary, captures one bounded interval and seals at the following boundary. Enable the existing `pgxp_view` census/transport before arming when provenance is required; capture does not secretly change geometry/texture correction. All calls run at the emulation safe point on the actual Windows owner thread.

The fixed buffer holds1024 submitted textured polygons in663,552bytes, with no per-primitive file I/O, allocation, logging or SDK/GL call. Every admitted triangle/quad preserves exact command words and source addresses, native split `(0,1,2),(2,1,3)`, UV/color, CLUT/tpage/depth/blend/raw/semitransparency, texture window, mask flags, draw area/offset, model V, raw MAC, projection metadata and combined RT/TR. Provenance qualification checks DATAFLOW, exact word, source age0/1 including wrap, commit, valid command/lane, divergence flags, live transform/frame/hash and MAC consistency. It retains rejected vertices with reasons; overflow or malformed packets invalidate interval completeness. Complete interval does **not** mean full scene coverage: sprites, untextured draws and final culling/raster results are outside this observer. Reserved texture depth3 can have qualified geometry; it is not an accepted material.

Independent host checks: **1,626enabled +6disabled, zero failures**, including all16 textured polygon opcode variants, lifecycle, missing/stale/future/overflow/wrap/transform failures, wrong-thread guard, native quad topology and bounded JSON serialization. The exact v64 TCP handler plus actual Windows runtime adapter also passes **eight CPU RPC cases**, using fixture provenance rather than a running guest. It validates real handler syntax, JSON parse, arm/seal/read/cancel and exact env opt-in. One early host build failed on warnings-as-errors (existing nested comment plus unused fixture variables); preserved r1, corrected r2/r3. The observer still needs live packet capture, timing measurement and CPU adapter consumption. It does not submit a scene to Remix, establish world/camera separation or solve PSX material/compositing fidelity.

## Remaining texture and Remix work

Claude's read-only world-v4 fringe census finds1,699keys:1,135 with cutout and564 opaque. In the sampled captures,1,110keys were drawn;437(39%) are opaque.569 drawn keys have mixed footprints;136 exceed a mean RGB fringe of8/255,101 exceed32/255. These are texture-key counts and a CPU bilinear metric, not unique sign counts or a measured screen-space visual improvement. Of the101 high-fringe keys,59 fail the strict native-class audit. Root approved a separate, identity-bound **RGB-only sidecar v5** for the136-key list: it must not fabricate class authority or mark those artwork defects fixed. V5 remains ongoing at this checkpoint. RISE's patched hybrid was visually rejected; root selected a faithful upright HD composition using the actual native class/UV map, including inter-letter gaps and separate arrow. A new CPU vector draft is authorized; no replacement is accepted or composed here. Five previously approved sign keys remain protected.

Earlier real SDK probes still fail: successful API calls, black image, stalled Shutdown. A [pinned official SDK source reference](https://github.com/NVIDIAGameWorks/dxvk-remix/blob/42b54bbe2a9280f7720e5b64415c78aa3e15224f/src/dxvk/rtx_render/rtx_remix_api.cpp) was fetched for CPU inspection. Its Present helper obtains a swapchain reference without an apparent matching Release; this is a **source-only lifecycle hypothesis**, not a demonstrated cause in the different installed5a7eec84 renderer. Its exact source/URL/hash and404 metric-source request are retained. No SDK/runtime update or additional GPU retry occurred. Live scene capture, material/camera/world mapping, image/lifecycle success, ray tracing, DLSS and HUD composition remain unverified.

Prior v61 live audio/smoothness acceptance remains failed. Far-background signs/buildings, full texture coverage, realistic player/enemy/boss ship and weapon skins/selectors, modern HUD/menus, audio remastering and all seven stages remain incomplete. Component test passes do not complete the remaster.

## Payload and reproducibility limits

`SHA256SUMS.txt` pins every published file except itself. `LOCAL-PAYLOADS.json` enumerates omitted local payloads and their hashes; the v4 subset is explicitly not the complete306-file payload. Private executables, objects, sidecar binaries, source art, BIOS/discs/cards and generated guest artifacts are not uploaded. Build receipts pin retained local inputs and compiler commands; recipes require the recovered C: workspace/toolchain. The portable scene component includes its frozen `pgxp.h` dependency. Runtime observer/renderer source, host fixtures, exact extracted glue, failed evidence and actual results are included.
'''
(dst/'README.md').write_text(readme)
current='''## Current verified state — timed GPU reservation; CPU integration November14

The user's3090Ti reservation runs **11:44:30–12:44:30UTC (04:44:30–05:44:30Phoenix)**. CPU-only work continues from C:, one below-normal compiler/worker at a time. The3060 is permitted if needed but has not been used for this work. The user already authorizes3090 reuse after the hour; check actual availability and take an owned bounded test reservation then. The previous indefinite hold is superseded.

Root independently verifies all306 Claude-v4 pins, recompiles/replays6,185fixture checks and six exact GL-stub integration modes, all passing. Scoped default-off RGB edges skip opaque pages and combine with offline class mips; no GPU/game acceptance is claimed. V62's broad unlaunched candidate is retired after review. Private v63 and v64r2 compile/link; v64 adds actual submitted GP0 packet capture. Its collector passes1,626enabled/6disabled CPU checks, and its exact TCP handler plus Windows adapter passes eight CPU RPC cases. Both executables remain unlaunched; retained parent objects mean these are not clean full-source rebuilds. [Source, raw results, hashes, retained failures and payload limits](../remaster-audit/cpu-hour-integration-20261114/README.md).

The bounded scene observer is a real private engine hook, default OFF: explicit next-frame arm/seal,1024polygon cap, full raw topology/material/projection input, copied readback and overflow rejection. It still needs live qualification and connection to scene submission. Combined camera/object transforms, PSX compositing/material fidelity and full scene coverage remain unresolved. Prior real Remix SDK output remains black and Shutdown stalls; ray tracing/DLSS are not working in-game. A newly inspected official source lifecycle issue is only a hypothesis against a different runtime revision.

The fringe census identifies136 sampled drawn texture keys above8/255 mean bilinear RGB bleed;437/1,110 drawn keys are opaque. Claude is implementing separately identity-bound RGB-only sidecars, while strict native-class defects remain open. RISE's hybrid repair was rejected; faithful upright HD composition with exact native gaps/arrow is the chosen replacement direction. Far-background clarity/buildings, full artwork coverage, ship/weapon/enemy/boss skins and selectors, modern HUD/menus, audio remastering and seven-stage acceptance remain incomplete. The prior v61 live run still fails audio/smoothness acceptance; no new game/audio test was run during this CPU checkpoint.

'''
docs=['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md']
for name2 in docs:
    p=w/'docs'/name2;old=p.read_text();title,body=old.split('\n',1)
    new=title+'\n\n'+current+'<details>\n<summary>Earlier checkpoints — superseded resource policy and retained historical evidence</summary>\n'+body+'\n</details>\n'
    p.write_text(new);(r/'docs'/name2).write_text(new)
copy_file(Path(__file__),dst/'root/publish_cpu_hour.py')
(dst/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(dst).as_posix()+'\n' for p in sorted(dst.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'))
attr=w/'.gitattributes';text=attr.read_text();line=f'remaster-audit/{name}/** -text -whitespace'
assert line not in text;attr.write_text(text+'\n'+line+'\n')
local=r/'remaster-audit'/name;assert not local.exists();shutil.copytree(dst,local)
assert marker.read_bytes()==hold
print(json.dumps(dict(packet=str(dst),files=sum(1 for p in dst.rglob('*') if p.is_file()),v4_original_pins_verified=pins,omitted=len(omitted),gpu_executed=False,hold_unchanged=True)))
