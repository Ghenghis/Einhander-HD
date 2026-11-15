from pathlib import Path
import datetime,hashlib,json
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'worktree-checkpoint-registration-r1';out.mkdir(exist_ok=False)
file=r/'coordination/CLAUDE-SESSIONS-20261114.json';old=file.read_bytes();(out/'prior-roster.json').write_bytes(old)
d=json.loads(old);row=d['sessions'][0];assert row['cli_session_id']=='1c56db97-2f5d-4f18-aece-e2a77dbf7a70'
relative='.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/continuity/claude-einhander.json'
assert (r/relative).resolve().is_relative_to(Path(row['worktree']).resolve())
row['canonical_checkpoint_predecessor']=row['checkpoint'];row['checkpoint']=relative
row['checkpoint_routing_note']='Owner writes actual state only in its allowed native worktree. Hook/helper and metadata watcher read the registered path; guarded canonical predecessor preserved.'
d['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
file.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
receipt=dict(at_utc=d['updated_utc'],registered_checkpoint=relative,roster_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),worker_checkpoint_written_by_root=False,canonical_predecessor_unchanged=True,tests='worktree-checkpoint-cpu-r1/result.json')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
