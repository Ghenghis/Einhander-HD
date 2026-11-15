"""One fresh CPU grant, pinned tests, bounded child; no game or GPU."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

r = Path('C:/github/Einhander')
n = Path(__file__).resolve().parent
cpu = int(sys.argv[1])
grant = dt.datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'))
assert cpu in (11,13,15) and 0 <= (dt.datetime.now(dt.timezone.utc)-grant).total_seconds() < 180
pins = {
    r/'remaster-audit/run_stage1_unassisted_review.py':'2e758a8f94fb8907c6d746ee3a5fa143bc1060907b6ecb919cf29f304843eb9f',
    r/'remaster-audit/test_stage1_unassisted_review.py':'95cbbff36600a43694f63b5d9c9fa0bf70424c990924580d57d8818ade6f4dfb',
    r/'remaster-audit/unassisted_command_guard.py':'9e6ca8159a2f471fcbbde996464a6ba2eb6a51846c44567eefdb6e5cceaa2240',
    r/'tools/coordination/shared_gpu_guard.py':'cb767d1f5cf4c1795eb46d369a558bdfedf33c9e51b529123893c53c47685ac7',
    n/'region-o-roi-composition-r1/run_rc2.py':'cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'
}
for p,h in pins.items():
    assert hashlib.sha256(p.read_bytes()).hexdigest()==h, str(p)
out = n/'unassisted-policy-tests-r5'
out.mkdir(exist_ok=False)
args = [sys.executable,'-B','-I',str(n/'region-o-roi-composition-r1/run_rc2.py'),
    '--out',str(out/'rc.json'),'--cpu',str(cpu),'--timeout','30','--max-cpu','60',
    '--min-free-gib','16','--',sys.executable,'-B',str(r/'remaster-audit/test_stage1_unassisted_review.py')]
env = dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
    run = subprocess.run(args,cwd=r,env=env,stdout=stdout,stderr=stderr,
        creationflags=0x08004000,timeout=40)
result = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),outer_exit=run.returncode,
    command=args,pins={str(p):h for p,h in pins.items()},guard_receipt=json.loads((out/'rc.json').read_bytes()),
    gpu_run=False,game_run=False,broker_mutation=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
raise SystemExit(run.returncode)
