"""Root read-only verification of the exact NEW v6 freeze, not a replay claim."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v6'
out=n/'v6-freeze-integrity-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=me.cpu_affinity();me.cpu_affinity([11 if 11 in allowed else allowed[0]])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();start=time.monotonic()
assert sha(f/'READY.json')=='33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0'
assert sha(f/'SHA256SUMS.txt')=='904cc6bc33510f1e6c205d5a7201f7e81875e71f19120b3a7ae967d5ed2b8af9'
names=[];total=0
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
    h,rel=line.split('  ',1);p=(f/rel).resolve();assert p.is_relative_to(f.resolve());data=p.read_bytes()
    assert hashlib.sha256(data).hexdigest()==h and (not data or any(data)),rel
    names.append(rel);total+=len(data)
extra=sorted(p.relative_to(f).as_posix() for p in f.rglob('*') if p.is_file() and p.relative_to(f).as_posix() not in set(names)|{'READY.json','SHA256SUMS.txt'})
assert len(names)==1111 and not extra
ready=json.loads((f/'READY.json').read_text());rd=f/'host-run/20261114T142204Z';result=rd/'result.json'
assert sha(result)=='c53dfe6bbc41ec2e413ad21907b3515d8378106e329ca3e0fcb0ed4b41ed228a'
assert json.loads(result.read_text())['verdict']=='pass'
for name,h in ready['pack']['files'].items():assert sha(f/ready['pack']['dir']/name)==h
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,ready_sha256=sha(f/'READY.json'),manifest_sha256=sha(f/'SHA256SUMS.txt'),file_pins=1111,bytes_verified=total,all_zero_files=0,unlisted_files=extra,pack_source_pins=ready['pack']['files'],host_result_sha256=sha(result),host_outer_exit='NOT CAPTURED by author; do not infer from final report',host_tests_replayed=False,gpu_run=False,game_run=False,below_normal=True,cpu_affinity=me.cpu_affinity(),seconds=round(time.monotonic()-start,3))
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(report))
