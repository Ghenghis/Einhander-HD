from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED'; hold=marker.read_bytes()
assert hashlib.sha256(hold).hexdigest()=='64f6472862310facb2a0f0247d0470ea3da2b8b5b88915f9b6a6be46249443b6'
out=n/'user-release-20261114T1403';out.mkdir(exist_ok=False)
release=dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_chat='01a1da2a-6273-7051-92a9-fc914070d84e',source_user_message='01a1da5d-d9df-7000-95e5-44b85363c268',user_text='I don’t need any more time on the 3090 Ti: I finished with it at about 6:55. ComfyUI is stopped and the card is back at its normal 450 W, so the other project can have it now.',verification='Root read actual userMessage via Codex read_thread, not only forwarded agent mail.',user_power_report='450 W; not independently measured and no setting changed',gpu_test_run=False)
for file,data in [('expired-user-reservation.json',hold),('release.json',(json.dumps(release,indent=2)+'\n').encode())]:
    with (out/file).open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
assert marker.read_bytes()==hold and not (marker.parent/'GPU-LOCK').exists()
marker.unlink()
inventory=['nvidia-smi','--query-gpu=uuid,name,memory.used,memory.total,utilization.gpu,power.limit','--format=csv,noheader,nounits']
x=subprocess.run(inventory,capture_output=True,text=True,timeout=5,creationflags=0x08000000)
(out/'inventory.csv').write_text(x.stdout);(out/'inventory-stderr.log').write_text(x.stderr)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),release=release,archived_hold_sha256=hashlib.sha256(hold).hexdigest(),marker_removed=True,inventory_command=inventory,inventory_exit=x.returncode,inventory=x.stdout,driver_power_setting_changed=False,gpu_render_started=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(result))
