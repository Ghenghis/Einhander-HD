"""Publish a new immutable result packet; never alter the preceding checkpoint."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');w=Path('C:/github/Einhander-wt/display-history-opt-in');n=Path(__file__).resolve().parent
name='roi-native-admission-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()=='5266849c3de88f572ec8c88d395ecb2351c8349a'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
p.mkdir(exist_ok=False);sources=[];sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def cp(src,rel):
    src=Path(src);dest=p/rel;data=src.read_bytes();assert b'\0' not in data
    if src.suffix=='.json':json.loads(data)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    sources.append(dict(source=str(src),published=dest.relative_to(p).as_posix(),bytes=len(data),sha256=sha(dest)))
for folder in ['mijpq-roi-composition-r2','mijpq-native-admission-r1','mijpq-roi-candidate-verification-r1']:
    for f in sorted((n/folder).rglob('*')):
        if f.is_file() and f.suffix in {'.json','.py','.log'}:cp(f,'root/'+folder+'/'+f.relative_to(n/folder).as_posix())
for f in ['run_mijpq_roi_composition_r2.py','run_mijpq_native_admission_r2.py','verify_mijpq_roi_candidate.py','prepare_mijpq_delivery.py','roi-menu-delivery.json','roi-menu-pr-verification.json']:
    cp(n/f,'root/'+f)
cp(n/'mijpq-roi-plan-r1.json','PLAN.json')
verification=json.loads((n/'mijpq-roi-candidate-verification-r1/result.json').read_text())
assert verification['passed'] and verification['unchanged_from_original_parent']==1689
admission=json.loads((n/'mijpq-native-admission-r1/result.json').read_text());assert admission['outer_exit']==0 and admission['guard_receipt']['tree_absent']
assert json.loads((n/'mijpq-native-admission-r1/stdout.log').read_text())==dict(keys=1699,region_checks=226,failures=0)
candidate=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-mijpq-roi-r1/candidate.json'
assert sha(candidate)==verification['candidate_sha256'];c=json.loads(candidate.read_text())
ledger=''.join(x['sha256']+'  '+x['name']+'\n' for x in sorted(c['files'],key=lambda x:x['name']))
(p/'FINAL-PNG-SHA256SUMS.txt').write_text(ledger,encoding='utf-8')
selected={x['key']+'.png' for x in json.loads((n/'mijpq-roi-plan-r1.json').read_text())['entries']}
selected.update(['95A3BCF8-60245B3A.png','95A3BCF8-07A9568D.png'])
(p/'CANDIDATE-SUMMARY.json').write_text(json.dumps(dict(local_candidate=str(candidate),sha256=sha(candidate),parent=c['parent_candidate'],final_count=c['final_count'],changed_from_original=10,selected_pages=[x for x in c['files'] if x['name'] in selected],private_candidate=True,installed=False,live_visual_accepted=False),indent=2)+'\n',encoding='utf-8')
monitor=sorted(n.glob('monitor-renewal-*'))[-1];cp(monitor/'result.json','dated-monitor/result.json')
text='''# Combined window/cutout candidate — actual CPU admission

The newer private O parent now includes eight additional palette-page ROI corrections for M/I/J windows and P/Q cutouts. The final comparison pack has 1,699 PNG entries. Compared with the original pre-O parent, 1,689 PNGs are byte-identical and ten changed pages cover six native regions (O/M/I/J/P/Q). These are texture variants, not ten unique signs or finished objects.

Root independently verifies every final PNG hash and every parent hash. The two earlier O pages remain unchanged. Every pixel outside each new ROI matches the O parent; inside, all pixels match the frozen correction, and alpha exactly matches decoded native words/CLUT classes at every HD pixel. All pages retain their original dimensions. The original and intermediate parent packs are preserved.

Actual composition ran CPU15 BelowNormal from 17:25:16 to17:25:33 UTC: child41240 exit0 in17.423 seconds, outer exit0 in18.626 seconds, Job Object tree absent. The fresh resource gate measured48.3% CPU and71.36GiB free. It used the immutable reviewed cd3988af runner copy; the earlier pin-refusal attempt remains preserved in the preceding packet.

The actual CPU native pack verifier reports keys1699, region_checks226, failures0. It ran child39324 onCPU15 BelowNormal and exited0 in0.218 seconds with its Job Object tree absent. The verifier binary is pinned859fc54e92a8397170f3fb4c6f959c8d49e5d205b8b3fe6bda7c9fed997bfd7b. Native admission checks the pack's structural/source contracts; it does not prove all1,699 artworks are native-class exact or visually accepted. Independent all-pixel source-class equality here covers the eight newly changed ROIs.

Candidate JSON SHA256903bd84a6be19fdef2b6d19293121515035b68c61b7d0ff67f4ff7cf38b30b20. The compact summary includes ten changed-page records; FINAL-PNG-SHA256SUMS lists the entire private PNG ledger. The full candidate and generated PNGs remain on C:. PLAN and the executed source/receipts preserve the lineage. Prior packets are unchanged.

No GPU, game, audio or installation ran. Root explicitly returned CPU15 after verification at17:26:48 UTC. No global driver/power changes. The P/Q original freeze's late-start scheduling violation remains recorded; its functionally passing output and this later freshly granted integration do not erase that violation.

Still required: private gameplay-scale/motion review, native material/skin selector appearance, crisp faithful glass/HUD refinements, complete palette/background/state coverage and normal gameplay/audio checks. The previous modern Remix GPU probe failed; geometry/camera/material transport and accepted in-game RT/DLSS are unfinished. All seven-stage/release gates remain open. Native admission and hash checks are component results, not final4K fidelity or project completion.

Only source, reports and hashes are published. No generated PNGs, executable/DLL/SDK packages, native binary captures, ROM/BIOS/cards/user state or fenced tokens are included. Dated metadata monitoring proves monitoring only.
'''
(p/'README.md').write_text(text,encoding='utf-8',newline='\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources),indent=2)+'\n',encoding='utf-8')
doc='docs/ROI-NATIVE-ADMISSION-20261114.md'
body='''# Combined private texture candidate — actual CPU result

The O parent now includes eight additional M/I/J/P/Q corrections. All1,699 PNG hashes are independently checked;1,689 remain identical to the original pre-O parent. Earlier O pages are retained. Every new outside-region pixel is unchanged, and alpha inside all eight new ROIs exactly matches captured native source classes. CPU native pack admission reports1,699 keys,226 region checks,zero failures. [Executed source, receipts, full private PNG ledger and limits](../remaster-audit/roi-native-admission-20261114/README.md).

Composition exits0 in17.423s and native admission exits0 in0.218s, both on one CPU BelowNormal with empty Job Object trees. No GPU/game/audio/installation. Live appearance and motion are untested. The P/Q original late-start failure remains preserved. This candidate is not a finished4K release or accepted gameplay/Remix integration.
'''
(r/doc).write_text(body,encoding='utf-8',newline='\n');shutil.copy2(r/doc,w/doc)
docs=['docs/'+f for f in ['RUNTIME-CONTINUATION-20261113.md','RTX-REMIX-SETUP-20261114.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md','4K-REMIX-IMPLEMENTATION-PLAN.md','ROI-COMPOSITION-RESULTS-20261114.md']]+['coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md']
current='''## Combined ROI candidate admitted —17:26 UTC

The private O+M/I/J/P/Q pack passes CPU native admission (1,699 keys,226 region checks,zero failures). Independent readback verifies all page hashes,1,689 PNGs unchanged from the pre-O parent, preserved O pages and exact native alpha inside all eight new ROIs. Composition exits0/17.423s and admission0/0.218s; child/job trees absent and CPU15 returned. [Actual results and limits](../docs/ROI-NATIVE-ADMISSION-20261114.md).

No GPU/game/audio run or installation. Live motion/look, full fidelity and seven-stage acceptance remain open; the earlier modern Remix failure and P/Q scheduling violation remain preserved. Metadata monitor PID42612 ends17:58:03.357 UTC and proves monitoring only. Older dated checkpoints below are historical.

'''
for rel in docs:
    f=r/rel;title,tail=f.read_text(encoding='utf-8').split('\n',1);f.write_text(title+'\n\n'+current+tail.lstrip(),encoding='utf-8',newline='\n');shutil.copy2(f,w/rel)
statefile=r/'remaster-audit/stage1-completion-20261112/execution-state.json';s=json.loads(statefile.read_text());s['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
s['latest_verified_component']=dict(id='Combined private O/M/I/J/P/Q ROI candidate with CPU native admission',evidence='remaster-audit/'+name+'/README.md',total_pages=1699,unchanged_from_original_parent=1689,native_region_checks=226,native_admission_failures=0,gpu_run=False,game_run=False,audio_run=False,installed=False,live_acceptance=False)
s['actual_monitor']=dict(pid=42612,bound_end_utc='2026-11-14T17:58:03.357Z',watcher_only=True,proves_model_activity=False);statefile.write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8');shutil.copy2(statefile,w/statefile.relative_to(r))
roster=r/'coordination/CLAUDE-SESSIONS-20261114.json';d=json.loads(roster.read_text());d['actual_monitor']=s['actual_monitor'];d['updated_utc']=s['updated_at_utc'];roster.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');shutil.copy2(roster,w/roster.relative_to(r))
attrs=w/'.gitattributes';attrs.write_text(attrs.read_text()+'\n/remaster-audit/'+name+'/** -text -whitespace\n')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dest=r/'remaster-audit'/name/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
subprocess.run(['git','add','-f','--','.gitattributes','remaster-audit/'+name,doc,*docs,'coordination/CLAUDE-SESSIONS-20261114.json',statefile.relative_to(r).as_posix()],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),staged=True,pushed=False,gpu_run=False)
(n/'mijpq-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
