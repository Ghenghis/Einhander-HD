"""Make an isolated source replay bundle; never restore old canonical engine files."""
from pathlib import Path
import hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
s=r/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/f3-repro'
out=n/'f3-reproduction-bundle-r1';out.mkdir(exist_ok=False);(out/'inputs').mkdir()
prep=json.loads((s/'prepare.json').read_bytes());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
for name,expected in prep['pins'].items():
    source=(n/'f3-source-integration-r1/original-hd_research_renderer.h') if name=='hd_research_renderer.h' else r/'windows-x64/psxrecomp/runtime/src'/name
    assert sha(source)==expected,name
    shutil.copy2(source,out/'inputs'/name)
for name in ['build_and_run.py','harness.c','f3-hd_research_renderer.patch']:
    shutil.copy2(s/name,out/name)
(out/'EXPECTED.json').write_text(json.dumps(prep,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(bundle=str(out),input_pins_verified=len(prep['pins']),compiler_run=False,gpu_run=False)))
