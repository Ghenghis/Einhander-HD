"""Freeze the actual ROI composition and scoped UI/validator results for GitHub."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
name='roi-menu-results-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='7bb769797f8030e5590e1fe124d8a0a5f56e9db3'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
p.mkdir(exist_ok=False);sources=[];omitted=[];sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
extensions={'.py','.json','.jsonl','.md','.c','.h','.log','.txt','.diff','.ps1'}
def cp(src,rel):
    src=Path(src);dest=p/rel;data=src.read_bytes();assert b'\0' not in data,src
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
def tree(src,rel):
    src=Path(src);assert src.is_dir(),src
    for f in sorted(src.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:continue
        if f.suffix in extensions and f.stat().st_size<12*1024**2:cp(f,Path(rel)/f.relative_to(src))
        else:omitted.append(dict(source=str(f),bytes=f.stat().st_size,reason='Private generated/binary/native payload omitted.'))
for rel in ['remaster-audit/build_stage1_frozen_candidate.py','remaster-audit/test_frozen_candidate_roi.py']:cp(r/rel,'source/'+rel);shutil.copy2(r/rel,w/rel)
for folder in ['roi-composer-cpu-r2','region-o-roi-composition-r1','region-o-roi-candidate-verification-r1']:
    tree(n/folder,'root/'+folder)
for f in ['verify_roi_composer_r2.py','prepare_roi_verification_r2.py','prepare_region_o_roi_plan.py','region-o-roi-plan-r1.json','run_region_o_roi_composition.py','verify_region_o_roi_candidate.py','refresh_six_session_roster.py','prepare_roi_menu_delivery.py']:
    cp(n/f,'root/'+f)
cp(n/'root-claude-freeze-inputs-r1/input-receipt.json','root/unexecuted-freeze-source-copy-receipt.json')
candidate=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-o-roi-r1/candidate.json'
assert sha(candidate)=='3a83b481010f1c27c99e51eca13a62240c6e6e74684c723dbb0169f35f22a25c'
cp(candidate,'private-candidate/candidate.json')
ui=r/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
for folder in ['classsnap/20261114T165701Z','gauge-classmip/20261114T165719Z','primary-audit/20261114T165725Z','census']:
    tree(ui/folder,'native-ui/'+folder)
for f in sorted((ui/'receipts').glob('J-*.json')):cp(f,'native-ui/receipts/'+f.name)
for f in sorted((ui/'tools').glob('*')):
    if f.is_file() and f.suffix in extensions:cp(f,'dated-ui-tools/'+f.name)
stage=r/'remaster-audit/parallel-stages-20261114'
timeout=stage/'s67/tooling/timeout-profile'
for f in ['validate_timeout_leg.py','test_timeout_leg.py','test-results-r5-run1-FAILED-fixture-K.json','test-results-r5-run2.json','README.md','r4-to-r5-tests.diff','r4-to-r5-validator.diff']:
    cp(timeout/f,'native-s67/timeout-profile/'+f)
assert sha(timeout/'test-results-r5-run2.json')=='c97274c3973aba5d85d45289bed0bd2d26b9cc76e45106653fe5b0b652739b1d'
support=r/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
cp(support/'replay-r5-20261114T170028Z/result.json','native-support/replay/result.json')
cp(support/'tools/replay_timeout_r5.py','native-support/replay_timeout_r5.py')
for f in sorted((support/'reviews').glob('*.md')):cp(f,'native-support/reviews/'+f.name)
tree(stage/'s23/runs/actors-20261114T170432Z','native-s23/actor-ownership')
cp(stage/'s23/tools/actor_ownership_map.py','native-s23/actor_ownership_map.py')
cp(stage/'s45/repairs/J-G-20261114T164606Z.json','native-s45/J-G-result.json')
cp(stage/'s45/menu-hud/receipts/J-D2-20261114T164606Z.json','native-s45/J-D2-memory-failure-receipt.json')
cp(n/'six-session-roster-refresh-r1/result.json','dated-session-metadata/result.json')
health=json.loads((r/'.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json').read_text())
assert health['watcher_pid']==38020 and psutil.pid_exists(38020)
rosterfile=r/'coordination/CLAUDE-SESSIONS-20261114.json';roster=json.loads(rosterfile.read_text())
roster['actual_monitor']=dict(pid=38020,bound_end_utc=health['bound_end_utc'],verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),watcher_only=True,proves_model_activity=False)
roster['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
rosterfile.write_text(json.dumps(roster,indent=2)+'\n',encoding='utf-8');shutil.copy2(rosterfile,w/rosterfile.relative_to(r));cp(rosterfile,'dated-session-metadata/roster.json')
cp(n/'roi-menu-results-readme.md','README.md')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources),indent=2)+'\n',encoding='utf-8')
(p/'LOCAL-PAYLOADS.json').write_text(json.dumps(dict(omitted=omitted),indent=2)+'\n',encoding='utf-8')
doc='docs/ROI-COMPOSITION-RESULTS-20261114.md'
body='''# Region-only texture composition — actual CPU results

Two far-building corrections are composed into a new private 1,699-page comparison pack. Independent readback confirms 1,697 unchanged PNGs; both changed pages retain their original alpha and every pixel outside the approved region. The composer binds the rectangle and artifact baseline to a pinned manifest, preserving newer parent artwork. Seven unit cases, twenty negative cases and an actual CLI fixture pass. [Source, process results, independent verification and limits](../remaster-audit/roi-menu-results-20261114/README.md).

The scoped menu census now checks all 261 selected files, with only 19 primary passes. Numeric class-valid repairs can still fail visual review: the white-blotch label repair is rejected. The timeout-profile validator has author and independent 72/72 passes, while a timeout remains rejected as a stage clear. These are component results; live captures, menu interactions and gameplay acceptance remain incomplete.

No GPU, game, audio or installation ran in this checkpoint. The earlier modern Remix probe remains a failure. M/I/J refinements, P/Q cutout repairs and remaining engine/skin/HUD/audio/seven-stage work continue separately. Root prepared exact source copies after reported native usage limits, without running those freeze jobs at this checkpoint.
'''
(r/doc).write_text(body,encoding='utf-8',newline='\n');shutil.copy2(r/doc,w/doc)
docs=['docs/'+f for f in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
current='''## Verified region-O integration —17:02 UTC

The private O ROI composition passes: 1,699 page hashes checked, 1,697 unchanged PNGs, two size-neutral corrected pages with identical alpha and all outside-region pixels retained. Composer source and a real CLI fixture are checked; runtime admission/live motion remain pending. The scoped menu census finds only 19/261 primary passes and preserves visual repair failures. Timeout validation passes 72/72 in author and independent runs, without establishing a stage clear. [Actual results and unfinished work](../docs/ROI-COMPOSITION-RESULTS-20261114.md).

No new GPU/game/audio run or installation. M/I/J and P/Q freezes remain separate work. The failed modern Remix GPU result is preserved. Metadata monitor PID38020 is bounded to17:33:42.232 UTC and proves monitoring only. Earlier dated paragraphs below are historical.

'''
for rel in docs:
    f=r/rel;title,tail=f.read_text(encoding='utf-8').split('\n',1);f.write_text(title+'\n\n'+current+tail.lstrip(),encoding='utf-8',newline='\n');shutil.copy2(f,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';s=json.loads(statefile.read_text())
s['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
s['latest_verified_component']=dict(id='Region-O private ROI composition and scoped UI/validator results',evidence='remaster-audit/'+name+'/README.md',composition_passed=True,total_pages=1699,unchanged_pages=1697,gpu_run=False,game_run=False,audio_run=False,installed=False,live_acceptance=False)
s['actual_monitor']=roster['actual_monitor'];statefile.write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8');shutil.copy2(statefile,w/statefile.relative_to(r))
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dest=r/'remaster-audit'/name/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
changed=['.gitattributes','remaster-audit/'+name,doc,*docs,'remaster-audit/build_stage1_frozen_candidate.py','remaster-audit/test_frozen_candidate_roi.py','coordination/CLAUDE-SESSIONS-20261114.json',statefile.relative_to(r).as_posix()]
subprocess.run(['git','add','-f','--',*changed],cwd=w,check=True,timeout=20);subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),packet=str(p),staged=True,pushed=False,gpu_run=False)
(n/'roi-menu-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
