"""Return the actual failed-probe grant only after exact cleanup evidence."""
from pathlib import Path
import datetime,json,psutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'modern-gpu-release-r1';out.mkdir(exist_ok=False)
receipt=json.loads((n/'modern-granted-execution-r1/result.json').read_text())
assert receipt['managed_parent_identity_absent'] and receipt['owned_child_gone']
assert receipt['owned_marker_released'] and receipt['owned_lock_released']
state=json.loads((r/'.hermes3d_orchestrator/shared-gpu/state.json').read_text(encoding='utf-8-sig'))
assert state['grant']['owner']=='claude-einhander'
assert all(not psutil.pid_exists(job['pid']) for job in state['grant']['jobs'])
assert not psutil.pid_exists(receipt['start']['managed_parent_pid'])
assert all(not (r/'remaster-audit/comfy-authoring'/name).exists() for name in ['GPU-RESERVED','GPU-LOCK','CPU-QUIET'])
p=out/'release.private';p.write_text(json.dumps(dict(token=state['grant']['token'],no_gpu_jobs=True,evidence='Modern probe failed, outer exit1/41.681s. Actual parent38504 absent, owned child gone and both nonce markers released. Result2c19e083 preserved. No game/audio or driver/power settings changed.')))
run=subprocess.run(['node',str(r/'tools/coordination/shared-gpu.mjs'),'release','--owner','claude-einhander','--file',str(p),'--no-flush'],cwd=r,capture_output=True,text=True,timeout=8,creationflags=0x08004000)
assert run.returncode==0,run.stderr
a,_=json.JSONDecoder().raw_decode(run.stdout.lstrip());assert a['ok'] and a['grant'] is None
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),revision=a['event']['revision'],event_id=a['event']['id'],owner=None,explicit_release=True,all_registered_pids_absent=True,resource_markers_absent=True,token_omitted=True,outbox_pending=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
