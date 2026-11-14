from pathlib import Path
import datetime,json,os
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED'
old=marker.read_bytes();assert json.loads(old)['owner']=='user-external-project'
record={'owner':'user-external-project','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation_start_utc':'2026-11-14T11:44:30Z','expires_utc':'2026-11-14T12:44:30Z','gpu':'RTX3090Ti','scope':'User requests3090Ti for1hour, then explicitly permits Einhander use again. Continue CPU-only for now;3060 is usable if needed. No global driver changes or interruption of other work. At/after deadline root may transition to an owned bounded3090 test reservation after resource checks, without another permission question.','rtx3060_allowed_if_needed':True,'user_authorized_3090_return_after_expiry':True}
(n/'prior-user-hold-before-timed-update.json').write_bytes(old)
assert marker.read_bytes()==old
tmp=marker.with_name('GPU-RESERVED.codex-timed');tmp.write_text(json.dumps(record,indent=2)+'\n');os.replace(tmp,marker)
(n/'user-gpu-hold-timed-1144.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
