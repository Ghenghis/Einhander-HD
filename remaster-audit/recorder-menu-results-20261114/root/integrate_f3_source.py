"""Apply only the exact CPU-reproduced patch; no build, game or GPU."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
s=r/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/f3-repro'
target=r/'windows-x64/psxrecomp/runtime/src/hd_research_renderer.h'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(target)=='3ffdf13f664a5a69cf84d355d114c7ddf8b263c4412d48299526231824a67b74'
patch=s/'f3-hd_research_renderer.patch'
assert sha(patch)=='d8fb2e26767bc94fda869256f8631749ec24ce836d420ab092ca660871182725'
receipt=s/'run-20261114T175549Z.rc.json';result=s/'run-20261114T175549Z/result.json'
assert sha(receipt)=='fda0ddc92c534cd8ce39360b6a0c340e4425caf9844a4c96d0ffd74d4b0d99b0'
assert sha(result)=='2af3015642ae10e85f8dc8b32125a69b51b0460537ec4002796a22b1ec9e789b'
d=json.loads(result.read_bytes());assert d['all_ok'] and d['sources_unchanged']
out=n/'f3-source-integration-r1';out.mkdir(exist_ok=False)
shutil.copy2(target,out/'original-hd_research_renderer.h')
subprocess.run(['git','apply','--check','--',str(patch)],cwd=r,check=True,timeout=10)
subprocess.run(['git','apply','--',str(patch)],cwd=r,check=True,timeout=10)
assert sha(target)=='e12716f980b28eec2da093408ba522f3d7e8316108433f2b95706efdaded68ee'
shutil.copy2(target,out/'patched-hd_research_renderer.h')
x=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_integrated=True,
    target=str(target),before_sha256=sha(out/'original-hd_research_renderer.h'),after_sha256=sha(target),
    patch_sha256=sha(patch),cpu_result_sha256=sha(result),outer_receipt_sha256=sha(receipt),
    full_renderer_build=False,private_runtime_relinked=False,gpu_run=False,game_run=False,installed=False)
(out/'result.json').write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8');print(json.dumps(x))
