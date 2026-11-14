from pathlib import Path
import datetime,hashlib,json,psutil,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
source=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/95a3-cage/frozen/95A3BCF8-C-cage-v2'
target=r/'remaster-audit/claude-backlog/95a3-cage/frozen/95A3BCF8-C-cage-v2'
p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.cpu_affinity([11])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(source/'READY.json')=='cac09df8fd21172f59cdea978f029ab243b745f332db06310d379d85b6c0d372'
assert sha(source/'SHA256SUMS.txt')=='be3aa465dfa28674c8088a6bb361d982ee02207ce7f1844a09ce9e9d189bf6e9'
pins={}
for line in (source/'SHA256SUMS.txt').read_text().splitlines():
    h,name=line.split('  ',1);f=(source/name).resolve()
    assert f.is_relative_to(source.resolve()) and sha(f)==h,name
    pins[name]=h
assert len(pins)==6
target.mkdir(parents=True,exist_ok=False)
for f in sorted(source.rglob('*')):
    if f.is_file():
        dest=target/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(f,dest);assert sha(dest)==sha(f)
out=n/'cage-v2-canonical-preservation-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
    source=str(source),canonical_copy=str(target),ledger_pins_verified=len(pins),all_files_copied=len(list(target.rglob('*'))),
    ready_sha256=sha(target/'READY.json'),manifest_sha256=sha(target/'manifest.json'),
    png_sha256=sha(target/'page2048/95A3BCF8-857DB48E.png'),pins=pins,
    correctness_candidate_only=True,look_accepted=False,integrated=False,game_run=False,gpu_run=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
