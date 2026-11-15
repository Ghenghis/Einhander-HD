from pathlib import Path
import datetime,hashlib,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/scene-texture-followup-20261114'
base=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip';f=base/'frozen/renderer-v61-classmip-v5-r2'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:]);sha=lambda x:hashlib.sha256(Path(x).read_bytes()).hexdigest()
replay=json.loads((n/'v5r2-cpu-verification-r1/result.json').read_text());assert replay['passed'] and replay['frozen_files_verified']==874
ext={'.py','.c','.cpp','.h','.inc','.md','.json','.jsonl','.txt','.log','.frag','.vert','.conf','.csv','.tsv'};omitted=[]
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def tree(src,dst):
    for x in sorted(src.rglob('*')):
        if not x.is_file():continue
        if x.suffix.lower() in ext and x.stat().st_size<=8*1024*1024:
            assert b'\0' not in x.read_bytes(),x;copy(x,dst/x.relative_to(src))
        else:omitted.append(dict(path=str(x),bytes=x.stat().st_size,sha256=sha(x),reason='Recovered frozen payload retained locally; source/report subset published, not the complete874-pin runtime/art payload.'))
tree(f,p/'claude-v5r2-source-report-subset')
tree(n/'v5r2-cpu-verification-r1',p/'root/v5r2-cpu-verification-r1');copy(n/'verify_v5r2_cpu.py',p/'root/verify_v5r2_cpu.py')
recovery=base/'recovery/20261114-restart';manifest=json.loads((recovery/'MANIFEST.json').read_text())
for name,h in manifest['files'].items():assert sha(recovery/name)==h
tree(recovery,p/'claude-recovery')
dm=base/'frozen/DAMAGED-renderer-v61-classmip-v5.json';assert sha(dm)=='3eb8c3420bfc671176e91d69a162d1ab364662888e811a5092252c2547fc683f'
damaged=json.loads(dm.read_text());count=0
for row in damaged['listing']:
    x=Path(damaged['damaged'])/row['path'];data=x.read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256'],x
    if data and not any(data):count+=1
assert count==263
copy(dm,p/'claude-recovery/DAMAGED-renderer-v61-classmip-v5.json')
status=r/'remaster-audit/runtime-review/seven-stage-status-20261114/status-20261114T131542Z.json';lanes=status.parent/'lane-readiness-20261114T131712Z.json'
assert sha(status)=='56dbeeece106197cbef1ea3706c362353df7a5e70ae03215ab78e0d90d3abc0c'
assert sha(lanes)=='07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8'
copy(status,p/'root/later-stages/status.json');copy(lanes,p/'root/later-stages/lane-readiness.json');report=json.loads(lanes.read_text());verified=0
for stage in report['stages']:
    for row in stage['candidate_folders']:
        x=Path(row['manifest']);assert x.resolve().is_relative_to(r.resolve()) and sha(x)==row['manifest_sha256'];verified+=1
        copy(x,p/f'root/later-stages/manifest-metadata/stage{stage["stage"]}'/(x.parent.name+'-'+x.name))
assert verified==28
copy(__file__,p/'root'/Path(__file__).name)
payloads=p/'LOCAL-PAYLOADS.json';data=json.loads(payloads.read_text());data['omitted']+=omitted;payloads.write_text(json.dumps(data,indent=2)+'\n')
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_freeze_pins_root_verified=874,fixture_checks=7520,glue_cases=14,glue_checks=352,old_failed_file_hashes_reverified=len(damaged['listing']),old_failed_all_zero_files=263,failed_evidence_unchanged=True,later_stage_manifest_pins_verified=verified,gpu_executed=False,mutants_root_replayed=False)
(p/'root/recovered-v5-and-stage-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
readme=p/'README.md';s=readme.read_text();s=s.replace('At this publication preparation checkpoint no recovered v5 is accepted.','Root now independently verifies all874 new freeze pins, recompiles/replays7520 fixture checks and14 GL-stub modes/352 checks, all passing. This accepts the recovered CPU checkpoint only; no GPU/game acceptance. Root did not replay the author\'s52 implementation/20 glue mutants or real-page benchmarks. The author\'s timings remain6.6ms4096²/1.2ms2048² cold admission medians, not a stutter fix. V6 worker-prepared identity is authorized but not yet implemented at this checkpoint.')
s=s.replace('V5 recovery must use intact originals, fresh CPU replay and a NEW immutable freeze.','V5 recovery used intact originals, a fresh replay and NEW immutable renderer-v61-classmip-v5-r2. READY5f96e71566792816917afc39827e04a9227fe9e321617e4d554ff527e207a0be; original manifestbb270f8c91891ab9bc72a698624817057400417ce667444caccd43eb649848a5. The source/report subset is explicit; binary sidecars/executables/images remain local.')
s=s.replace('## Included evidence and reproduction limits','The broader failed-freeze inventory is also independently rechecked: all874 original file hashes remain unchanged,263 are all-zero. Some frozen author wording says writes were not flushed; that cause is **not established**. The later author recovery README corrects it; historical frozen bytes are preserved. A first recovery-report packaging attempt replaced its zero-byte manifest after a wrong-parent error; that disclosure is retained, not recast as a clean first attempt.\n\n## Seven-stage work remains concurrent in scope\n\nThe original plan explicitly includes simultaneous later-stage preparation alongside Stage1. Recent execution concentrated on shared engine/recovery and Stage1 defects; there are not seven active stage authors. A new read-only readiness report pins28 relevant candidate/alternative manifests, with selected key counts S2=39,S3=39,S4=11,S5=12,S6=101,S7=26. Counts are selected metadata, not full required coverage or accepted stages. Per-stage class/CLUT/UV/state/source confirmation and visuals remain open. CPU whole-cell/fringe audits of all six selected later-stage sets are queued independently of Stage1 clear; native Claude owns the next audit lane after its short RISE draft. No later-stage live or installed acceptance is claimed, no completion percentage or equal-finish date is justified.\n\n## Included evidence and reproduction limits')
readme.write_text(s)
new='''Root has now independently verified the recovered v5-r2 freeze:874 pins,7520 fixture checks and14 GL-stub cases/352 checks pass; no GPU/game acceptance. All874 failed-predecessor hashes also remain unchanged, including263 all-zero files. Fsync/readback is a precaution; the crash/corruption cause remains unknown. Later-stage scope is concurrent: S2–S7 selected candidates39/39/11/12/101/26 keys have28 manifests reverified and concrete CPU whole-cell/fringe audits queued. None of the seven stages is fully accepted.\n\n'''
for name in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md','STAGE1-COMPLETION-STATUS.md']:
    doc=w/'docs'/name;text=doc.read_text()
    for a,b in [('no recovered v5 acceptance yet','recovered CPU checkpoint verified; GPU/game acceptance pending'),('reconstruct/replay a NEW revision with native Claude','the recovered NEW revision passes root CPU replay'),('V5, RISE lettering','V5 GPU/live qualification, RISE lettering')]:text=text.replace(a,b)
    if '<details>' in text:text=text.replace('<details>',new+'<details>',1)
    else:head,tail=text.split('\n',1);text=head+'\n\n'+new+tail.lstrip()
    doc.write_text(text);shutil.copy2(doc,r/'docs'/name)
queue=r/'coordination/Codex-WORK-QUEUE.md';s=queue.read_text();s=s.replace('- [ ] Preserve damaged frozen v5 unchanged.','- [x] Preserve damaged frozen v5 unchanged and verify NEW v5-r2 on CPU (root874 pins,7520 fixtures,14 modes/352checks pass). Independent live qualification remains open. Historical preparation note:')
section='\n## Concrete concurrent later-stage CPU/source lane\n\nOwner: native Claude for the next read-only strict whole-cell/fringe audit; Codex schedules source capture and reviews/publishes evidence. These are queued independent of Stage1 clear, not six currently running authors. Audit each selected key against CRC-proven native class maps, explicitly list missing proof, keep R1/R2/R4 and connectivity-only outcomes separate, and do not relabel centre-only checks as whole-cell passes. All GPU/live captures remain sequential and reserved.\n\n'
for st in report['stages']:section+=f'- [ ] EIN-S{st["stage"]}-WHOLE-CELL-20261114: {st["candidate_keys"]} selected keys. {st["independently_ready_work"]} Next source gate: {st["source_acquisition_task"]}; {st["source_gate_rule"]}\n'
s+=section;queue.write_text(s);shutil.copy2(queue,w/queue.relative_to(r))
handoff=r/'coordination/Codex-HANDOFF.md';s=handoff.read_text();s=s.replace('## Identity and resources','## Recovered CPU checkpoint —13:18UTC\n\nRoot independently verifies all874 v5-r2 pins and replays7520 fixtures plus14 GL-stub modes/352checks, all passing, no GPU. All874 old failed-freeze hashes remain unchanged,263 all-zero. Source/report subset and raw replay are included in the new scene/texture packet; GPU/game checks remain pending. Native Claude may resume CPU work after root quiet release. Shared engine/Stage1 incidents temporarily concentrated effort; the queue now restores six concrete later-stage audit/source tasks independent of Stage1 clear, with28 candidate manifest pins reviewed. No seven-stage completion percentage or date is established.\n\n## Identity and resources',1);handoff.write_text(s);shutil.copy2(handoff,w/handoff.relative_to(r))
statepath=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statepath.read_text());state['updated_at_utc']=receipt['at_utc'];state['active_work']['restart_recovery']['new_freeze_accepted']=False;state['active_work']['restart_recovery']['new_freeze_cpu_accepted']=True;state['active_work']['restart_recovery']['new_freeze_pins_verified']=874;state['active_work']['restart_recovery']['root_old_failed_pins_verified']=874;state['active_work']['restart_recovery']['old_all_zero_files']=263;state['active_work']['restart_recovery']['gpu_game_accepted']=False;state['active_work']['later_stage_lane']={'scope':'S2–S7 CPU strict whole-cell/fringe audit queued concurrently with shared engine and Stage1 work; not six active authors','owner':'claude-einhander','selected_key_counts':{'2':39,'3':39,'4':11,'5':12,'6':101,'7':26},'candidate_manifests_verified':28,'fully_accepted_stages':0};statepath.write_text(json.dumps(state,indent=2)+'\n');shutil.copy2(statepath,w/statepath.relative_to(r))
print(json.dumps(receipt))
