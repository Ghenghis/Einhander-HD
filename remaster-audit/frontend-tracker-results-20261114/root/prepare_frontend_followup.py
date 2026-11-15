from pathlib import Path
import hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;out=n/'development-frontend-cpu-r1'
d=json.loads((out/'result.json').read_text());assert d['passed']
for rel,h in d['source_normalized_sha256'].items():
    f=r/rel;assert hashlib.sha256(f.read_text(encoding='utf-8').encode()).hexdigest()==h
    dest=out/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
shutil.copy2(n/'verify_development_frontend.py',out/'executed-runner.py')
review=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/reviews/SAVED-MATERIAL-ROUTE-REVIEW-20261114.md'
assert hashlib.sha256(review.read_bytes()).hexdigest()=='ac72e03ceac061d352077802462607813ebba3b25d867f794511f8f401ac09fb'
shutil.copy2(review,out/'native-review.md');print('Preserved passing r1 source and actual native review before follow-up edits.')
