"""Correct unpublished pending-state notes and add completed native evidence."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
name='roi-menu-results-20261114';p=w/'remaster-audit'/name
backup=n/'roi-menu-preparation-r0-partial';shutil.copytree(p,backup)
mapping=json.loads((p/'SOURCE-MAP.json').read_text());sources=mapping['sources'];sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def cp(src,rel):
    src=Path(src);dest=p/rel;assert not dest.exists();data=src.read_bytes();assert b'\0' not in data
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
def texts(src,rel):
    src=Path(src)
    for f in sorted(src.rglob('*')):
        if f.is_file() and f.suffix in {'.json','.py','.md','.txt','.log','.c','.h','.diff'} and '__pycache__' not in f.parts:cp(f,Path(rel)/f.relative_to(src))
for f in ['prepare_mijpq_roi_plan.py','mijpq-roi-plan-r1.json','run_mijpq_roi_composition_r2.py','run_mijpq_native_admission_r2.py','verify_mijpq_roi_candidate.py','record_mijpq_prestart_failure.py','finalize_roi_menu_delivery.py']:cp(n/f,'root/followup/'+f)
texts(n/'mijpq-freeze-verification-r1','root/followup/mijpq-freeze-verification-r1')
texts(n/'mijpq-roi-composition-r1','root/followup/mijpq-prestart-failure')
freeze=json.loads((n/'mijpq-freeze-verification-r1/result.json').read_text())
for row in freeze['freezes']:
    f=Path(row['path'])
    for file in ['READY.json','manifest.json','validation.json','SHA256SUMS.txt']:
        cp(f/file,'native-freezes/'+f.name+'/'+file)
    for file in f.glob('*.py'):cp(file,'native-freezes/'+f.name+'/'+file.name)
for i,row in enumerate(freeze['actual_runs']):
    src=Path(row['path']);cp(src,f'native-freezes/run-{i}/rc.json')
    if (src.parent/'mem.json').exists():cp(src.parent/'mem.json',f'native-freezes/run-{i}/mem.json')
ui=r/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
for folder in ['classsnap/20261114T171339Z','classsnap-batch/20261114T171404Z','classsnap-batch/20261114T171757Z']:
    texts(ui/folder,'native-ui-followup/'+folder)
summary=ui/'integration/near-pass-runtime-summary-20261114T171934Z.json'
assert sha(summary)=='5ef7b279c34002665f010bd0f5502298c75ce164700963f9ff1187b7f712c769';cp(summary,'native-ui-followup/near-pass-runtime-summary.json')
for file in ['J-R2-20261114T171337Z.json','J-R3c1-20261114T171402Z.json','J-R3c2-20261114T171755Z.json']:cp(ui/'receipts'/file,'native-ui-followup/receipts/'+file)
cp(ui/'tools/ui_menu_classsnap_v3.py','dated-ui-current/ui_menu_classsnap_v3.py')
stage=r/'remaster-audit/parallel-stages-20261114'
texts(stage/'s23/runs/actors-20261114T171053Z','native-s23/corrected-actor-ownership')
cp(stage/'s23/tools/actor_ownership_map.py','native-s23/dated-corrected-actor_ownership_map.py')
support=r/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
cp(support/'pods/POD-KEYS-SOURCE-MAP-20261114.md','native-support/pods/POD-KEYS-SOURCE-MAP-20261114.md')
notes=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_message='msg_2b4a0612d39490ac',author='claude-einhander',m_freeze_functional_pass=True,pq_freeze_functional_pass=True,pq_scheduling_compliant=False,pq_late_seconds_approximately=87,observer_self_match_reported_proven=True,observer_peak_scope='Sampled max over worker and observer, not exact per-worker or Job Object peak.',root_copied_builders_executed=False,initial_pending_notes_preserved_at=str(backup))
(p/'NATIVE-RUN-CORRECTION.json').write_text(json.dumps(notes,indent=2)+'\n',encoding='utf-8')
readme=(p/'README.md').read_text()
readme=readme.replace('Their freeze and integration into the newer O parent remain separate steps.', 'Their three immutable freezes are now verified; integration into the newer O parent remains pending at this packet checkpoint.')
readme=readme.replace('A continuous-glass proposal and P/Q native cutout restoration are source work until actual execution receipts establish otherwise.', 'The continuous-glass alternative is still a source proposal. P/Q native cutout correction has actual frozen outputs, as recorded below.')
readme=readme.replace('This packet does not claim those repairs were built or installed.', 'The two P/Q repairs are built and pinned; they are not installed or live-accepted.')
readme=readme.replace('Later quota/reset or resumed work must be established by a new actual result.', 'Later source review found the original M freeze had already completed while its separate observer lingered; all original native results are used instead of rerunning the copies.')
readme+='''
## Later actual results and preserved scheduling failure

Root independently verifies all 39 frozen file pins across M/I/J/P/Q, all five READY/manifest/SUMS bindings and original worker/wrapper absence. M ran in its window: child/outer exit 0, 64.786 seconds, sampled peak 0.765 GiB. Its companion observer matched its own command and delayed the shell. P/Q subsequently ran for 2.415 seconds and passed functionally, but started about 87 seconds outside the granted batch bound. That is a scheduling violation, not an overall compliant PASS. The author disclosed stopping only its own second observer. Receipts, sampled memory data and the disclosure remain preserved. No successful freeze was rerun by root.

Root viewed the P/Q sheets: native holes are restored around the antenna/ladder/tank, retaining authored visible surface colors. Edges remain native-cell shaped; this is private correctness review, not final fidelity or in-game acceptance. An eight-entry ROI plan binds those frozen inputs to the newer O parent. Its first integration attempt refused a changed shared runner hash before Popen, so no composition child or candidate was created. The failure is preserved. A fresh run requires a new grant and the already preserved exact reviewed runner; no retry under an expired or consumed grant.

UI follow-up runs fix the white background blotches using exact native colors on newly visible pixels. The author reports remaining stair-steps and pinholes; root has not live-accepted the labels. Two chunks process all 72 near-pass runtime representative units with primary passes, with separate source hashes and resume records. These units are not a new count of accepted menus. Remaining at that checkpoint: 46 palette twins, 41 higher-resolution pack units, 51 substantial-error units requiring look review, and about 1,400 PNGs outside the selected audit. All interaction/live gates remain open.

The initial S2 actor map missed existing candidate indexes. Its corrected map is included: three previously labelled missing enemy keys and eleven Stage-2 HUD palette keys already have candidate assets. Do not author duplicates from the superseded map. Two other shared-file keys have complete source but draw only tiny flat gray slivers; the support source review does not prove a pod identity or a skin-selector mapping. Native-equivalent coverage is not a new realistic skin.

The initial unpublished packet preparation is preserved locally with its outdated pending-state text. This final packet corrects that text before GitHub publication and preserves the raw old/new reports with their dates.
'''
(p/'README.md').write_text(readme,encoding='utf-8',newline='\n')
mapping['sources']=sources;mapping['finalized_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(p/'SOURCE-MAP.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8')
docs=['docs/ROI-COMPOSITION-RESULTS-20261114.md','docs/RUNTIME-CONTINUATION-20261113.md','docs/RTX-REMIX-SETUP-20261114.md','docs/STAGE1-COMPLETION-STATUS.md','docs/STAGE1-SIGN-QUALITY-20261114.md','docs/4K-REMIX-IMPLEMENTATION-PLAN.md','coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
for rel in docs:
    f=r/rel;s=f.read_text();s=s.replace('M/I/J and P/Q freezes remain separate work.', 'M/I/J/P/Q freezes are verified; eight-ROI composition remains pending after a prestart runner-pin refusal. The P/Q late-start violation is preserved.')
    s=s.replace('M/I/J refinements, P/Q cutout repairs and remaining engine/skin/HUD/audio/seven-stage work continue separately.', 'M/I/J/P/Q frozen repairs are verified as private candidates. Their eight-ROI composition, remaining fidelity work and engine/skin/HUD/audio/seven-stage acceptance continue separately.')
    f.write_text(s,encoding='utf-8',newline='\n');shutil.copy2(f,w/rel)
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dest=r/'remaster-audit'/name/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
subprocess.run(['git','add','-f','--','remaster-audit/'+name,*docs],cwd=w,check=True,timeout=20)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),corrected_unpublished_preparation=True,prior_preparation_preserved=str(backup),pushed=False)
(n/'roi-menu-final-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
