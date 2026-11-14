from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');name='decode-worker-results-20261114';p=w/'remaster-audit'/name
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
mapping=json.loads((p/'SOURCE-MAP.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def cp(src,relative):
    src=Path(src);dest=p/relative;assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True);data=src.read_bytes();assert b'\0' not in data
    if src.suffix=='.json':json.loads(data)
    dest.write_bytes(data);mapping['sources'].append(dict(source=str(src),published=relative,bytes=len(data),sha256=sha(dest)))
def tree(src,relative):
    for f in sorted(src.rglob('*')):
        if f.is_file() and f.suffix in {'.py','.md','.json','.jsonl','.txt','.log','.mjs','.patch'}:cp(f,relative+'/'+f.relative_to(src).as_posix())
tree(n/'worktree-checkpoint-cpu-r1','root/worktree-checkpoint-cpu-r1')
tree(n/'worktree-checkpoint-registration-r1','root/worktree-checkpoint-registration-r1')
for name1 in ['verify_worktree_checkpoint.py','register_worktree_checkpoint.py','supplement_decode_worker_packet.py']:cp(n/name1,'root/'+name1)
hooks=['tools/coordination/'+f for f in ['claude-checkpoint.mjs','claude-continuity-hook.mjs','test-claude-checkpoint.mjs','test-claude-continuity.mjs']]
for rel in hooks:cp(r/rel,'root/hooks/'+Path(rel).name);shutil.copy2(r/rel,w/rel)
session=r/'remaster-audit/runtime-review/session-continuation-20261114'
for f in ['skin-selector-trace-20261114.json','saved-material-development-route.patch','record-skin-trace.py']:cp(session/f,'skin-trace/'+f)
stage=r/'remaster-audit/parallel-stages-20261114'
for lane,folder in [('s23','runs/j6u-20261114T153839Z'),('s23','proposals/s2-phase-union-20261114T153839Z')]:tree(stage/lane/folder,'stage-work/'+lane+'/'+folder)
cp(r/'coordination/CLAUDE-SESSIONS-20261114.json','dated-coordination/roster-after-checkpoint-routing.json')
readme=p/'README.md';text=readme.read_text(encoding='utf-8');text=text.replace('Phase-union repair remains unexecuted at this snapshot.','A later phase-union run completes8 keys/16 strict-pass files and24/24 same-position phase-pair/size controls with zero outline differences, exit0/52.41s. Frozen prep-v2 remains unchanged;60 unknown phase CLUTs and live sequence acceptance remain open.')
text+='''
## Registered checkpoint path and skin trace follow-up

Twenty actual hook/checkpoint controls pass on CPU11/below-normal. The project hook/helper now uses each registered owner's checkpoint path, confined to the project and exact owner filename. This lets the primary write its actual state inside its allowed worktree while the guarded canonical predecessor remains untouched. Stop reads the registered state; path escapes/foreign owner filenames are rejected. Framework activity metadata is not a fabricated model/presence heartbeat. The registered path changed after the earlier dated roster snapshot; both snapshots are retained. Actual future checkpoints/receivers remain the worker's responsibility.

The coordinator's read-only skin trace corrects a broad assumption: normal Play-HD already loads the saved validated material selection into runtime shader uniforms. It currently selects AuroraTeal/CrimsonRed and verified the existing runtime digest; these checks do not rerun gameplay. Start-Development directly launches the runtime and bypasses that selection. An isolated proposed patch reuses the validated launch plan and frontend mode, but is NOT applied or tested here. Fourteen palette profiles scope to five player/six enemy atlas keys; full per-craft/gunpod/boss-part mapping and in-game selectors remain missing. Concept skin.json assets are empty/draft/uninstalled; concept images are not loaded model textures. These are scoped source/plan findings, not a complete binary/UI audit or successful skin live acceptance.
'''
readme.write_text(text,encoding='utf-8',newline='\n')
(p/'SOURCE-MAP.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8')
doc=r/'docs/DECODE-WORKER-RESULTS-20261114.md';text=doc.read_text(encoding='utf-8');text+='\nTwenty hook/checkpoint controls also pass for registered worktree paths without touching a guarded predecessor. Normal Play-HD already applies saved materials; development-launch parity remains a proposed fix. Full boss/gun skin mapping and in-game selectors remain missing. The Stage2 phase-union repair passes24/24 CPU outline-consistency controls; unknown palettes and live sequence acceptance remain open.\n';doc.write_text(text,encoding='utf-8',newline='\n');shutil.copy2(doc,w/doc.relative_to(r))
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
for f in p.rglob('*'):
    if f.is_file():dest=r/'remaster-audit'/name/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
subprocess.run(['git','add','-f','--','remaster-audit/'+name,'docs/DECODE-WORKER-RESULTS-20261114.md',*hooks],cwd=w,check=True,timeout=20)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True,timeout=20)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),staged=True,committed=False,pushed=False)
(n/'decode-worker-final-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
