from pathlib import Path
import datetime,hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/scene-texture-followup-20261114'
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';data=marker.read_bytes();assert hashlib.sha256(data).hexdigest()=='64f6472862310facb2a0f0247d0470ea3da2b8b5b88915f9b6a6be46249443b6'
hold=json.loads(data);assert hold['expires_utc'] is None and hold['requires_explicit_user_release']
(p/'root/user-gpu-hold-1320.json').write_bytes(data);shutil.copy2(__file__,p/'root'/Path(__file__).name)
latest='''**Latest resource instruction, verified in the user\'s crash-status chat:** the3090Ti is reserved for Pizza Tycoon HD until **at least07:00Phoenix /14:00UTC**, with no automatic expiry. Wait for explicit user release. This supersedes the earlier one-hour reuse permission. Continue CPU-only work; leave the unrelated project and its other Claude session untouched. The current reservation marker is copied as `root/user-gpu-hold-1320.json`; no owned GPU/game job is running.\n\n'''
docnames=['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md','STAGE1-COMPLETION-STATUS.md']
for name in docnames:
    f=w/'docs'/name;s=f.read_text();head,tail=s.split('\n',1);s=head+'\n\n'+latest+tail.lstrip()
    s=s.replace("The user's one-hour 3090 Ti reservation ended **12:44:30 UTC (05:44:30 Phoenix)**; reuse afterward is authorized.","Historical earlier policy: the one-hour reservation ended12:44:30UTC. The latest hold above supersedes reuse authorization.")
    if name=='STAGE1-COMPLETION-STATUS.md':s=s.replace("The user's 3090 Ti hour ended12:44:30UTC and reuse afterward is authorized;",'The earlier GPU hour has been superseded by the latest explicit-release hold;')
    f.write_text(s);shutil.copy2(f,r/'docs'/name)
readme=p/'README.md';s=readme.read_text();head,tail=s.split('\n',1);s=head+'\n\n'+latest+tail.lstrip();s=s.replace('The user\'s one-hour 3090 Ti reservation ended 12:44:30 UTC (05:44:30 Phoenix); reuse after that hour was explicitly authorized.','The earlier one-hour reservation ended12:44:30UTC and authorized the historical after-hour control below; the latest user hold above now governs all new work.');readme.write_text(s)
for name in ['Codex-HANDOFF.md','Codex-WORK-QUEUE.md']:
    f=r/'coordination'/name;s=f.read_text();head,tail=s.split('\n',1);s=head+'\n\n'+latest+tail.lstrip()
    s=s.replace('That hour has elapsed. No owned renderer/game process is running at this checkpoint. Continue CPU integrity recovery before another GPU test; afterward check actual inventory and acquire a bounded owned reservation.','That historical hour has elapsed, but the new explicit-release hold above supersedes reuse. No owned renderer/game process is running. Continue CPU-only work.')
    s=s.replace("User's one-hour3090Ti reservation expired12:44:30UTC; reuse is authorized after a fresh availability check.",'The latest user3090Ti hold above requires explicit release; no automatic reuse.')
    f.write_text(s);shutil.copy2(f,w/f.relative_to(r))
statepath=r/'remaster-audit/stage1-completion-20261112/execution-state.json';state=json.loads(statepath.read_text());state['active_work']['user_3090_hold_previous']=state['active_work'].pop('user_3090_hold');state['active_work']['user_3090_hold']=hold;state['active_work']['gpu_work_active']=False;state['active_work']['state']='CPU-only recovery verification passed; shared engine/texture/seven-stage preparation and actual-results publication continue while user holds3090Ti until explicit release';state['updated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();statepath.write_text(json.dumps(state,indent=2)+'\n');shutil.copy2(statepath,w/statepath.relative_to(r))
print(json.dumps(dict(user_hold_sha256=hashlib.sha256(data).hexdigest(),earliest_release_utc=hold['earliest_release_utc'],automatic_expiry=False,gpu_executed=False)))
