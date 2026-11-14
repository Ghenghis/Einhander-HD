from pathlib import Path
import datetime,hashlib,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in')
src=(w/'remaster-audit/texture-composer-followup-20261114').resolve();dst=(n/'packet-preparation-r0-partial').resolve()
assert src.is_relative_to((w/'remaster-audit').resolve()) and src.parent==(w/'remaster-audit').resolve()
assert dst.is_relative_to(n.resolve()) and dst.parent==n.resolve() and not dst.exists()
assert not (src/'SHA256SUMS.txt').exists(),'Do not move a completed evidence packet'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
bad=r/'remaster-audit/parallel-stages-20261114/s67/tooling/timeout-profile/README.md';data=bad.read_bytes();where=data.index(b'\0')
src.rename(dst)
report=n/'packet-preparation-r0-failure';report.mkdir(exist_ok=False)
(report/'README-original-with-NUL.bin').write_bytes(data)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),preparation_tool_chunk='f510c2',preparation_exit=1,failed_assertion='NUL in purported text README.md',source=str(bad),source_bytes=len(data),source_sha256=hashlib.sha256(data).hexdigest(),nul_count=data.count(b'\0'),nul_offset=where,escaped_context=repr(data[max(0,where-45):where+50]),partial_source=str(src),partial_preserved=str(dst),completed_manifest_or_commit=False,scope='Preparation failure preserved; character content must be inspected before inferring disk corruption.')
(report/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,report/'executed-runner.py');print(json.dumps(result))
