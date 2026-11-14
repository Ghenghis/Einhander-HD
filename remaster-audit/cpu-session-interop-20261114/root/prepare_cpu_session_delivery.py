"""Freeze a new CPU-only source/report subset; old published packets stay immutable."""
from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess
r=Path('C:/github/Einhander'); n=Path(__file__).resolve().parent
w=Path('C:/github/Einhander-wt/display-history-opt-in'); name='cpu-session-interop-20261114'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='648b12ee0cbf2da4f5ea92dd3e70532a926cdab6'
p=w/'remaster-audit'/name; p.mkdir(exist_ok=False)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
extensions={'.py','.c','.cpp','.h','.inc','.json','.jsonl','.md','.txt','.log','.mjs','.java','.csv','.tsv'}
copied=[]; omitted=[]
def cp(src,dst):
    data=src.read_bytes(); assert b'\0' not in data,src
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    assert sha(dst)==hashlib.sha256(data).hexdigest()
    copied.append(dict(source=str(src),published=dst.relative_to(p).as_posix(),sha256=sha(dst),bytes=len(data)))
def tree(src,dst):
    assert src.is_dir(),src
    for f in sorted(src.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:continue
        if f.suffix.lower() not in extensions or f.stat().st_size>8*1024*1024:
            omitted.append(dict(source=str(f),bytes=f.stat().st_size,reason='Private binary/image or large payload; local pins remain in author/build receipts.'))
        else:cp(f,dst/f.relative_to(src))
for folder in ['sdk-modern-gl-cpu-r1','sdk-modern-gl-cpu-r2','sdk-modern-gl-cpu-r3','sdk-modern-gl-reference','sdk-modern-gl-client','session-interop-cpu-review-r1','source-draw-guard-review-r1','v6-pack-base-from-v48']:
    tree(n/folder,p/'root'/folder)
for file in ['sdk_modern_gl_probe.cpp','build_modern_gl_cpu.py','build_modern_gl_cpu_r2.py','build_modern_gl_cpu_r3.py','audit_modern_gl_image.py','test_modern_gl_image.py','verify_cpu_session_sources.py','verify_source_draw_guard.py','fetch_modern_gl_reference.py','fetch_release_gl_client.py','freeze_v6_pack_base.py','prepare_cpu_session_delivery.py']:
    cp(n/file,p/'root'/file)
cp(n/'sdk-release-header/remix_c.h',p/'root/sdk-release-header/remix_c.h')
assert json.loads((n/'sdk-modern-gl-cpu-r3/result.json').read_text())['passed']
assert sha(n/'sdk_modern_gl_probe.cpp')==json.loads((n/'sdk-modern-gl-cpu-r3/result.json').read_text())['source_sha256']
handoff=r/'coordination/claude-session-briefs-20261114/handoff-2026-11-14T13-46-36-132Z'
manifest=json.loads((handoff/'manifest.json').read_text())
for row in manifest['files']:assert sha(handoff/row['snapshot'])==row['sha256'],row['source']
tree(handoff,p/'native-session-handoff')
# Canonical hook changes are delivered only if still identical to independently replayed sources.
review=json.loads((n/'session-interop-cpu-review-r1/result.json').read_text())
canonical=[]
for rel,h in review['source_pins'].items():
    assert sha(r/rel)==h; dst=w/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(r/rel,dst);canonical.append(rel)
stage=r/'remaster-audit/parallel-stages-20261114'
for lane,folders,files in [
    ('s23',['runs/selection-20261114T133254Z','runs/j1-20261114T134041Z','runs/phase-coverage-20261114T134554Z','tools'],['S2-S3-GATES.md']),
    ('s45',['source-map/20261114T133831Z','strict-audit/20261114T135014Z-s4','clut-coverage/20261114T135254Z','tools'],['README.md','DUERER-8BPP-PLAN.md','PANORAMA-05E1881C-OWNERSHIP.md','REPAIR-PROPOSALS.md']),
    ('s67',['stage6','stage7','runs/20261114T135603Z','requests','reports','tools'],[])]:
    for folder in folders:tree(stage/lane/folder,p/'stage-audits'/lane/folder)
    for file in files:cp(stage/lane/file,p/'stage-audits'/lane/file)
tree(r/'remaster-audit/runtime-review/session-continuation-20261114',p/'source-draw-proposal')
# Preserve the authored reference/failed invariant reports, not the large generated art payload.
rise=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector'
for folder in ['authored/20261114T132814Z','expand33/20261114T134710Z']:
    tree(rise/folder,p/'rise-reference'/folder)
result=json.loads((stage/'s67/runs/20261114T135603Z/result.json').read_text())
assert result['complete'] and result['aborted'] is None
totals={}
for group in ('S6 selected','S7 selected','S6 alternate'):
    rows=[v for k,v in result['summary'].items() if k.startswith(group)]
    totals[group]={key:sum(v[key] for v in rows) for key in ('keys','files','strict_pass','primary_pass','errors','sha_ok')}
assert totals['S6 selected']['files']==202 and totals['S6 selected']['strict_pass']==178
assert totals['S7 selected']['files']==52 and totals['S7 selected']['strict_pass']==52
(p/'STAGE-AUDIT-TOTALS.json').write_text(json.dumps(totals,indent=2)+'\n')
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted,scope='No game/ROM/BIOS/cards, SDK DLL/JAR, private executables/objects, generated PNGs or native words/CLUT binaries are redistributed. Recipes require the pinned C: workspace inputs. Source/report subsets are snapshots, not installed assets.'),indent=2)+'\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=copied,canonical_delivered=canonical),indent=2)+'\n')
(p/'README.md').write_text('''# CPU interop, native Claude continuity and texture defect audit — November 14, 2026

These are actual CPU-only results from C:. The RTX 3090 Ti remains reserved for the user's other project until explicit release; 07:00 Phoenix is an earliest time, not automatic permission. No GPU, game, graphics window or new audio test ran in this packet. Root compilation/tests use one logical CPU below normal priority; heavier native-worker jobs are individually scheduled. All prior evidence packets and failed freezes remain unchanged.

## Matching modern Remix/OpenGL probe

The private `root/sdk_modern_gl_probe.cpp` implements the API 0.16.1 Submit → external-memory/timeline semaphore wait/read/signal → Present path documented by the exact release bridge/client. It uses a 320×180 diagnostic scene and bounded frame count, not a game backend. Correct physical image size, format/allocation checks, monotonically increasing timeline values, duplicated Win32 handles, per-frame image imports and an owned nonce-bound reservation are explicit. The child refuses a missing, foreign or user reservation before graphics startup. The owned-lease recognizer expects the parent's canonical serialization; it is coordination validation, not a general JSON parser or security boundary. No parent GPU runner has been qualified yet. The installed toolkit and engine executable are unchanged.

Actual `sdk-modern-gl-cpu-r3` syntax, object and link commands exit 0. Its 14 CPU metadata/lease checks pass; the reservation guard exits the expected 77 without DLL loading, GL or window creation. Source SHA256 is `3137ef3bc0e53ad5af6b321749ed413291ce4ef1763b1a8b0a1b67d64dad033b`. The earlier combined compiler-driver timeout is retained under r1; a later output file did not establish successful compiler exit and was never accepted or executed. R2 is a separate successful older source checkpoint, not proof of the latest source. Actual rendering, semaphore interoperability, clean Shutdown and final-image acceptance remain **NOT RUN**.

The independent Python image oracle requires a projected triangle in its expected interior and rejects uniform green, black, fallback magenta, shifted geometry, contaminated corners and malformed PPMs. Root executed all eight synthetic controls successfully. No actual GPU image was audited. The C++ green-pixel count alone is not sufficient acceptance. The exact SDK header and primary Khronos/NVIDIA reference sources are pinned alongside the implementation. This work does not establish in-game ray tracing, DLSS, any later DLSS feature, HUD composition or engine scene submission.

## Four actual native Claude sessions and crash continuity

Three additional real native Claude sessions have started and produced own-owner hooks, checkpoints and first artifacts: S2–3, S4–5 and S6–7. The original native session retains Stage 1/RISE/shared runtime. The dated session snapshot records actual desktop and CLI aliases and distinct output roots. Eighteen hook/checkpoint tests pass in both the author's run and root's independent replay, including registered alias routing, unknown-ID refusal, own-inbox scope, atomic checkpoint writes and explicit user-pause behavior. The four reviewed hook/test sources are delivered at their canonical paths. A monitor/checkpoint is metadata only and never proves uninterrupted future model activity. Snapshot checkpoints are historical and must not be compared with later live files as immutable pins.

## Actual texture coverage and defects

S2/S3: 39 selected keys each, 156 selected PNGs. A separate numpy implementation agrees with all eight DLL counters for all 156 files; strict class checks pass. This is the native worker's independently implemented audit, not a root rerun of every pixel. Sampling simulations still flag dark cutout fringes: 44/78 Stage 2 files and 32/78 Stage 3 files. Their errors are simulated filtering outcomes, not screen-space or in-game measurements. Dither/blob repairs and missing animated palette phases remain unfinished.

S4: 26 files pass the frozen strict/connection checks. This is weak coverage: all 23 selected S4/S5 review palettes have no cutout texels, and most Stage 4 pages are uniform alpha class. The light CLUT coverage map finds 186 alternative static key pairings with cutouts. Static pairing frequency is not proof of a live draw. Targeted alternative-palette probes and live pairing confirmation are needed before texture acceptance. The Stage 5 strict job and repair proposals are pending at this checkpoint.

S6/S7: the native worker actually audited 282 files in 42.81 s, including 28 alternatives. All recorded file hashes match. **Stage 6 selected: 178/202 strict pass, 24 fail** across explosion, electric-bolt and smoke families. **Stage 7 selected: 52/52 strict pass**, while the inferred planet pairing `C4FDEDD2-EAD968A1` remains unconfirmed. The readiness addendum corrects two omitted Stage 6 base-pack folders containing 23 selected keys; the total remains 101 keys. None of these class checks proves final detail, complete stage coverage or visual/game acceptance.

Four failing Stage 6 explosion keys are byte-identical to Stage 1's frozen large-explosion-v2 files. That shared Stage 1 impact is routed to the original Claude owner; its Stage 1 folder was not independently re-audited here. Frozen predecessors remain untouched and no repair is accepted yet.

The separate source/draw admission proposal now uses the actual recorder's `uv_bounds` and `native_words` schema. Root independently replays all 13 focused controls, including a pinned real-row schema fixture. It requires complete byte-identical source/CLUT plus an exact in-window native-page draw, but a query match still does not prove visibility. The stage/route frame window must be qualified independently. Malformed logs conservatively block admission; ROI derivatives and 16bpp are excluded. The original validator is preserved; no actual planet key is newly admitted.

## RISE and decode-worker implementation gates

Root visually approved the upright v5 RISE reference for private palette expansion only. The first 33-palette run passes its class checks but fails the intended byte-identical approved-reference invariant: float16 weights alter 3,122 visible pixels by one RGB level. That run is preserved as superseded; a new float32 correction is being scheduled. No installed sign or live artwork acceptance is claimed, and the five previously protected sign revisions remain untouched.

For v6, root caught that the canonical pack header would drop existing incremental-upload ABI/stat fields. The frozen `v6-pack-base-from-v48` closure preserves the header matching frozen v61 and its implementation; exact old object/source equivalence is not established. Claude rebased its additive decode-worker identity generator to these exact pins. The longer host/mutant/pack-lifetime tests, rebuilt pack TU, private link and in-game performance tests are still pending. No draw-thread stutter fix or installed release is claimed.

The whole remaster remains incomplete: final world/background coverage, all ship/weapon/enemy/boss skins and selectors, HUD/menus, modern audio, engine scene/material/world mapping, qualified Remix rendering and seven-stage gameplay/audio/release acceptance remain open. See `SOURCE-MAP.json` for original C: paths and `SHA256SUMS.txt` for this immutable source/report subset. Binary/art payload omissions are explicit in `LOCAL-PAYLOADS.json`.
''')
current='''CPU-only continuation now has four actual native Claude sessions with distinct stage ownership. Root replays 18 hook/checkpoint tests, 14 modern Remix/OpenGL metadata/lease checks, eight image-oracle controls and 13 corrected source/draw controls successfully. The private probe compiles/links; GPU image/synchronization/Shutdown and in-game Remix remain NOT RUN. The user's 3090 Ti reservation requires explicit release. No new game/audio test ran.

The actual later-stage audit finds 178/202 Stage 6 selected files strict-pass and 24 failures; Stage 7 selected files pass 52/52 but the inferred planet pairing remains unconfirmed. S2/S3 class passes retain simulated cutout-fringe defects; S4's 26-file pass does not cover transparency because the chosen review palettes are opaque. Distant texture/art repairs, RISE float32 reference correction, decode-worker v6 tests, live source/draw confirmation and whole-stage acceptance remain unfinished. These are measured component results, not full coverage or a release. [Source, exact commands, preserved failures and limitations](../remaster-audit/cpu-session-interop-20261114/README.md).

'''
docs=['docs/'+x for x in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md','STAGE1-COMPLETION-STATUS.md']]
for rel in docs:
    f=w/rel;s=f.read_text();title,tail=s.split('\n',1);f.write_text(title+'\n\n## Latest CPU verification — November 14, 2026\n\n'+current+tail.lstrip());shutil.copy2(f,r/rel)
for rel in ['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']:
    f=r/rel;s=f.read_text();title,tail=s.split('\n',1)
    intro=current.replace('../remaster-audit/','../remaster-audit/')
    if rel.endswith('Codex-HANDOFF.md'):
        intro+='Current native owners: claude-einhander (Stage 1/shared runtime), claude-einhander-s23, claude-einhander-s45 and claude-einhander-s67. Extra sessions are actually launched, not merely planned. The crash-check coordinator now schedules individual bounded texture CPU jobs; root retains runtime/v6/GPU/build/publication and bounded monitor rearm. Preserve older dated paragraphs as history; current session snapshot and new packet supersede their planned-launch state. The current monitor PID28164 ends14:07:14 UTC and must be actually replaced before then; no future rearm is claimed here.\n\n'
    f.write_text(title+'\n\n## Current CPU continuation\n\n'+intro+tail.lstrip());shutil.copy2(f,w/rel)
statepath=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statepath.read_text());state['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();state['latest_verified_component']=dict(id='CPU-only modern GL probe, native session hooks and stage defect audits',status='CPU checks pass; texture failures explicitly retained; no GPU/game acceptance',evidence='remaster-audit/'+name+'/README.md',github_commit_scope='Current PR branch source/report checkpoint; exact publication hash is recorded in delivery receipts and PR body');state['active_work']['later_stage_lane']['owner']='Three actual native Claude workers: s23, s45, s67; original Claude owns Stage1/shared runtime';state['active_work']['later_stage_lane']['actual_owners']=['claude-einhander-s23','claude-einhander-s45','claude-einhander-s67'];state['cpu_session_interop']=dict(packet='remaster-audit/'+name,stage_totals=totals,hook_tests=18,probe_cpu_tests=14,image_oracle_controls=8,source_draw_tests=13,gpu_run=False,game_run=False,project_complete=False);statepath.write_text(json.dumps(state,indent=2)+'\n');shutil.copy2(statepath,w/statepath.relative_to(r))
attrs=w/'.gitattributes';entry='/remaster-audit/'+name+'/** -text -whitespace\n';attrs.write_text(attrs.read_text()+'\n'+entry)
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'))
for f in p.rglob('*'):
    if f.is_file():dst=r/'remaster-audit'/name/f.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
paths=['.gitattributes','remaster-audit/'+name,*canonical,*docs,'coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md',statepath.relative_to(r).as_posix()]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
print(json.dumps(dict(packet=str(p),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),bytes=sum(f.stat().st_size for f in p.rglob('*') if f.is_file()),staged=True,committed=False,pushed=False,stage_totals=totals)))
