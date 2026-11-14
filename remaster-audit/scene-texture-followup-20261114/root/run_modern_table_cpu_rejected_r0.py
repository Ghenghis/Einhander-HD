from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess,time
n=Path(__file__).resolve().parent;r=n.parents[2]
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';hold=marker.read_bytes()
deadline=datetime.datetime.fromisoformat(json.loads(hold)['expires_utc'].replace('Z','+00:00'))
assert datetime.datetime.now(datetime.timezone.utc)>=deadline,'User GPU hour must end before loading the new runtime'
out=n/'sdk-modern-table-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stage=json.loads((n/'sdk-v016-release/staging-result.json').read_text());assert stage['passed'] and stage['archive_digest_verified']
dll=n/'sdk-v016-release/win64/d3d9.dll';expected=next(x for x in stage['extracted_files'] if x['path']=='d3d9.dll')['sha256'];assert sha(dll)==expected
exe=n/'sdk-modern-table-build/sdk-modern-table.exe';assert sha(exe)=='978861830ab9b334f94a30dab6400c2f854a90b9a93d1c59b19efb3e5f7eab47'
t=time.monotonic();process=None;result=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_hour_elapsed=True,
    scope='Function-table initialization only. No Startup, Submit, Present, rendering or game calls.',dll_sha256=expected,
    executable_sha256=sha(exe),header_sha256=sha(n/'sdk-release-header/remix_c.h'),installed_toolkit_modified=False)
try:
    with (out/'stdout.jsonl').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
        process=subprocess.Popen([str(exe)],cwd=n/'sdk-v016-release/win64',stdout=stdout,stderr=stderr,creationflags=0x4000)
        result['pid']=process.pid
        try:rc=process.wait(timeout=20)
        except subprocess.TimeoutExpired:process.terminate();rc=process.wait(timeout=5);result['watchdog_terminated']=True
    result['exit']=rc;lines=(out/'stdout.jsonl').read_text().splitlines();result['response']=json.loads(lines[-1]) if lines else None
    result['passed']=rc==0 and result['response']['rc']==0 and all(result['response'][k] for k in ['startup','submit','interop_info','memory_texture'])
finally:
    if process is not None and process.poll() is None:process.terminate();process.wait(timeout=5)
    result.update(seconds=round(time.monotonic()-t,3),process_gone=process is None or process.poll() is not None,user_marker_unchanged=marker.read_bytes()==hold,
                  ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(result))
raise SystemExit(0 if result.get('passed') else 1)
