from pathlib import Path
import datetime,hashlib,json,os,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';lock=marker.parent/'GPU-LOCK'
names={'sdk-modern-gl.exe','sdk-direct-control.exe','einhander_hd_powerprobe.exe'}
owned=[dict(pid=p.pid,name=p.info['name']) for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in names]
assert not owned and not marker.exists() and not lock.exists()
out=n/'user-gpu-handback-20261114T1438';out.mkdir(exist_ok=False)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
hold=dict(owner='user-external-project',at_utc=now,gpu='RTX3090Ti',project='Pizza Tycoon HD',expires_utc=None,requires_explicit_user_release=True,source_chat='01a1da2a-6273-7051-92a9-fc914070d84e',user_request='can pizza tycoon project use3090ti?',reservation_basis='Codex yields the available card to the requested other project; do not start a queued probe while the user takes it.',modern_gpu_probe_started=False,scope='Einhander stays CPU-only until user release. No automatic expiry. No power/driver settings changed. The modern probe is built but GPU image/lifecycle qualification has NOT RUN.')
data=(json.dumps(hold,indent=2)+'\n').encode()
with marker.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
(out/'user-reservation.json').write_bytes(data)
result=dict(at_utc=now,owned_probe_processes=owned,owned_gpu_lock_present=False,modern_gpu_probe_started=False,handed_back_to_user=True,reservation_sha256=hashlib.sha256(data).hexdigest(),reservation_basis=hold['reservation_basis'],driver_settings_changed=False,project_work_continues_cpu_only=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(result))
