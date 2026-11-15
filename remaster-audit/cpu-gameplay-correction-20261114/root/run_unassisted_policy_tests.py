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
    r/'remaster-audit/run_stage1_unassisted_review.py':'6463d4f95c6af98533dee9aca8a6cd57bcce05b9c8ecfd9481f662497e3a913d',
    r/'remaster-audit/test_stage1_unassisted_review.py':'3366682d7ec1bb23382142d3ea07f8d99b59777d4b122452495f08edf83abf65',
    r/'remaster-audit/unassisted_command_guard.py':'243dcd880db4f360540263dd4f6ee997f4757a8feabdaa43b36573922d00f93b',
    r/'tools/coordination/shared_gpu_guard.py':'cb767d1f5cf4c1795eb46d369a558bdfedf33c9e51b529123893c53c47685ac7',
    n/'region-o-roi-composition-r1/run_rc2.py':'cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'
}
for p,h in pins.items():
    assert hashlib.sha256(p.read_bytes()).hexdigest()==h, str(p)
out = n/'unassisted-policy-tests-r3'
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
