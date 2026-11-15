"""Read-only independent file/receipt integrity, not visual/class replay."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
u=r/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.cpu_affinity([11])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
summary=u/'integration/near-pass-runtime-summary-20261114T173158Z.json'
assert sha(summary)=='b04211596c7ca8bc0bc3447ccd4a46a076cec8442e0ad252a72efab2f66c7986'
s=json.loads(summary.read_bytes());assert (s['units'],s['files'],s['files_pass'],s['missing'])==(72,118,118,[])
checks=[]
for unit in s['units_detail']:
    assert unit['shape_identical'] is True
    for m in unit['members']:
        assert m['primary_pass'] is True
        for field,hashfield in [('candidate','candidate_sha256'),('noR5','noR5_sha256'),('clut','clut_sha256')]:
            f=Path(m[field]);f=f if f.is_absolute() else u/f
            assert f.resolve().is_relative_to(r.resolve()),str(f)
            assert sha(f)==m[hashfield],str(f)
            checks.append(dict(path=str(f),sha256=m[hashfield]))
for rel,run in s['runs'].items():assert sha(u/rel/'result.json')==run['result_sha256']
receipt=u/'receipts/J-R3tw2-20261114T173025Z.json'
assert sha(receipt)=='176af75c67bb22566fe9523d19432ffa83b88a9cfd986ef6912fbfbbe12e2f03'
d=json.loads(receipt.read_bytes());assert d['outer_exit']==0 and not d['killed'] and d['python_processes_left']==0
out=n/'ui-runtime-summary-readback-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),summary_sha256=sha(summary),
    independent_hash_checks=len(checks),units=72,files=118,reported_class_passes=118,
    class_algorithm_replayed=False,images_decoded=False,visual_accepted=False,game_run=False,gpu_run=False,
    competing_candidates=s['cross_folder_conflicts']['count'],receipt_sha256=sha(receipt),
    author_seconds=d['wall_s'],author_peak_ws_mib=d['peak_ws_mib'],files_checked=checks)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='files_checked'}))
