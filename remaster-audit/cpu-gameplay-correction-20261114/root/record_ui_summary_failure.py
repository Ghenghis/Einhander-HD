from pathlib import Path
import datetime,hashlib,json,shutil
from PIL import Image
n=Path(__file__).resolve().parent
u=Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui')
summary=u/'integration/near-pass-runtime-summary-20261114T173158Z.json'
s=json.loads(summary.read_bytes());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
out=n/'ui-runtime-summary-readback-r2';out.mkdir(exist_ok=False)
shutil.copy2(n/'verify_ui_runtime_summary.py',out/'executed-verifier.py')
rows=[];identities={}
for unit in s['units_detail']:
    for m in unit['members']:
        for field,hfield in [('candidate','candidate_sha256'),('noR5','noR5_sha256'),('clut','clut_sha256')]:
            f=Path(m[field]);f=f if f.is_absolute() else u/f
            if not f.resolve().is_relative_to(Path('C:/github/Einhander').resolve()):
                rows.append(dict(path=str(f),kind=field,match=False,error='Outside canonical C: project; no read attempted'))
                continue
            actual=sha(f)
            row=dict(source_unit=unit['folder'],runtime_dir=unit['dir'],member=m['file'],kind=field,
                path=str(f),expected_sha256=m[hfield],actual_sha256=actual,match=actual==m[hfield])
            if field!='clut':
                with Image.open(f) as im:row['actual_dimensions']=list(im.size)
            rows.append(row)
            identities.setdefault(str(f),[]).append(dict(runtime_dir=unit['dir'],expected_sha256=m[hfield]))
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=False,
    original_verifier_exit=1,original_failure='AssertionError: first candidate PNG hash mismatch',
    summary_sha256=sha(summary),checks=len(rows),mismatches=sum(not x['match'] for x in rows),
    conflicts={p:v for p,v in identities.items() if len({x['expected_sha256'] for x in v})>1},
    rows=rows,files_modified=False,gpu_run=False,game_run=False,class_replay=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','conflicts')}))
print(json.dumps(dict(path_collisions=len(result['conflicts']),first_mismatch=next(x for x in rows if not x['match']))))
