from pathlib import Path
import datetime,hashlib,json,os,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'primary-replacement-registration-r2';out.mkdir(exist_ok=False)
f=r/'coordination/CLAUDE-SESSIONS-20261114.json';prior=f.read_bytes()
(out/'prior-roster.json').write_bytes(prior)
p=psutil.Process(35656);args=p.cmdline()
assert '--project-config-root' in args
root=args[args.index('--project-config-root')+1].replace('\\','/').rstrip('/').lower()
assert root=='c:/github/einhander',root
# Native CLI ID comes from the actual worker's own environment report, corroborated by
# coordinator startup metadata. It is not necessarily present in process arguments.
handoff=r/'remaster-audit/claude-backlog/ORIGINAL-HANDOFF-20261114T1450Z.md'
assert hashlib.sha256(handoff.read_bytes()).hexdigest()=='1c57e2330f3dde8da0a4cf517ab04042e5a2a84721852913e5a8fae79e3afece'
d=json.loads(prior);old=d['sessions'][0]
assert old['owner']=='claude-einhander' and old['session_id']=='11357b05-21ce-4470-8da8-e1597e772a7f'
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
old.update(retired_utc='2026-11-14T15:04:18.440Z',retirement_message='msg_dd7e0a48c04a5c71',retired_from_new_assignments=True,user_stop=False)
d.setdefault('retired_sessions',[]).append(old)
d['sessions'][0]=dict(owner='claude-einhander',session_id='43668750-1a3c-49e9-8775-c31ee3df3847',native_session_id='local_43668750-1a3c-49e9-8775-c31ee3df3847',cli_session_id='1c56db97-2f5d-4f18-aece-e2a77dbf7a70',title='Einhander Stage1 primary recovery',scope=old['scope'],state='registered_actual_model_startup_hook_activity_pending',checkpoint=old['checkpoint'],
    worktree='C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db',
    edit_root='C:/github/Einhander',shared_worktree_no_edits=True,
    identity_evidence=dict(startup_message='msg_1457a8eecfbcd2de',coordinator_message='msg_2b36c62f2421c517',cli_id_basis='Actual model self environment; not present in process arguments',pid=35656,creation_unix=p.create_time(),actual_cwd_reported='C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db',project_config_root=root,verified_utc=stamp),
    handoff=str(handoff.relative_to(r)).replace('\\','/'),handoff_sha256=hashlib.sha256(handoff.read_bytes()).hexdigest(),
    live_hook_status='Canonical hook unregistered-session context observed by actual model; exact IDs registered now. Actual own-owner activity and inbox proof required before edits/jobs.')
d['updated_utc']=stamp
tmp=f.with_name(f.name+'.replacement-tmp')
with tmp.open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(json.dumps(d,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
os.replace(tmp,f)
receipt=dict(at_utc=stamp,roster_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),original_preserved=True,actual_project_config_root=root,pid=35656,cli_session_id=d['sessions'][0]['cli_session_id'],native_session_id=d['sessions'][0]['native_session_id'],hook_activity_verified=False,gpu_job_started=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
