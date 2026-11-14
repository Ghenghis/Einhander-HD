"""Freeze the accepted v67 source plus only the CPU-reviewed recorder header fix."""
from pathlib import Path
import datetime,hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=e/'sampling-build-v67-decode-identity-r3';out=e/'sampling-build-v68-recorder-reserve-r1'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(base/'Einhander_Recompiled.exe')=='8bc3ac3daedcbb08790905c228d1dc7b052bd5ed52d3bb739c02009ec86bb772'
out.mkdir(exist_ok=False)
for folder in ['src','include','third_party']:shutil.copytree(base/folder,out/folder)
header=r/'windows-x64/psxrecomp/runtime/src/hd_research_renderer.h'
assert sha(header)=='e12716f980b28eec2da093408ba522f3d7e8316108433f2b95706efdaded68ee'
assert not (out/'src/hd_research_renderer.h').exists()
shutil.copy2(header,out/'src/hd_research_renderer.h')
# Snapshot the directly related recorder headers so this change does not rely
# on a mutable canonical include during compilation.
recorder_headers={}
for f in sorted(header.parent.glob('hd_research*.h')):
    target=out/'src'/f.name
    if not target.exists():shutil.copy2(f,target)
    recorder_headers[f.name]=sha(target)
receipt=dict(prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),parent=str(base),
    parent_executable_sha256=sha(base/'Einhander_Recompiled.exe'),parent_build_sha256=sha(base/'build.json'),
    sources={f.relative_to(out).as_posix():sha(f) for folder in ['src','include','third_party']
             for f in sorted((out/folder).rglob('*')) if f.is_file()},
    recorder_headers=recorder_headers,fresh_compile='gpu_gl_renderer.c only',
    retained_objects='All other linked v67r3 objects; not a clean full-source rebuild',
    gpu_run=False,game_run=False,installed=False)
(out/'prepared.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(out=str(out),prepared_sha256=sha(out/'prepared.json'),frozen_source_files=len(receipt['sources']),gpu_run=False)))
