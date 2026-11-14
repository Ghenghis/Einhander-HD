"""Preserve the post-apply encoding failure; accept only exact reviewed LF bytes."""
from pathlib import Path
import datetime,hashlib,json,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'f3-source-integration-r1';target=r/'windows-x64/psxrecomp/runtime/src/hd_research_renderer.h'
data=target.read_bytes();normalized=data.replace(b'\r\n',b'\n');sha=lambda b:hashlib.sha256(b).hexdigest()
expected='e12716f980b28eec2da093408ba522f3d7e8316108433f2b95706efdaded68ee'
failure=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),phase='after git apply',
    script_exit=1,reason='Raw target SHA differs from author LF target',actual_sha256=sha(data),
    normalized_sha256=sha(normalized),expected_lf_sha256=expected)
(out/'post-apply-failure.json').write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
(out/'post-git-apply-raw.h').write_bytes(data)
assert sha(normalized)==expected,'Semantic patch mismatch; stop without further edits'
target.write_bytes(normalized)
assert sha(target.read_bytes())==expected
shutil.copy2(target,out/'patched-hd_research_renderer.h')
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_integrated=True,
    before_sha256=sha((out/'original-hd_research_renderer.h').read_bytes()),after_sha256=expected,
    encoding_normalization='Git apply produced CRLF; exact reviewed LF bytes independently verified before normalization.',
    preserved_post_apply_failure='post-apply-failure.json',full_renderer_build=False,
    private_runtime_relinked=False,gpu_run=False,game_run=False,installed=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
