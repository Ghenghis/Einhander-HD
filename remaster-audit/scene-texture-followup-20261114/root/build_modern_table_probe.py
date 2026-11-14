from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess
n=Path(__file__).resolve().parent;out=n/'sdk-modern-table-build';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(n/'sdk-release-header/remix_c.h')=='e1b7f16bf34d7cd701c21feb8da68921ed199822b272c014b8314621465c1c4c'
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe';exe=out/'sdk-modern-table.exe'
args=[cc,'-std=c++17','-O1',str(n/'sdk_modern_table_probe.cpp'),'-o',str(exe)]
x=subprocess.run(args,capture_output=True,text=True,timeout=45,creationflags=0x4000)
(out/'compile.log').write_text(x.stdout+x.stderr)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),args=args,exit=x.returncode,passed=x.returncode==0,
             source_sha256=sha(n/'sdk_modern_table_probe.cpp'),header_sha256=sha(n/'sdk-release-header/remix_c.h'),
             executable_sha256=sha(exe) if exe.exists() else None,software_executed=False,gpu_executed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(n/'sdk_modern_table_probe.cpp',out/'source.cpp');print(json.dumps(receipt))
raise SystemExit(x.returncode)
