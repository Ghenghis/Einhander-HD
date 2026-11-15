"""Read-only source closure from the documented v48 worktree, retaining v61's actual pack ABI."""
from pathlib import Path
import datetime,hashlib,json,os,shutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;src=Path('C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime');out=n/'v6-pack-base-from-v48';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(src/'src/hd_texture_pack.cpp')=='22a97b569e4c3a3ffaff9fff90f37745d1eee92da97f321a1900b452cfee41cd'
assert sha(src/'include/hd_texture_pack.h')=='78234dfdbe4b574b6054b27a65d4cb64877420fa9e67488355542d547969c794'
frozen=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/include/hd_texture_pack.h';assert sha(frozen)==sha(src/'include/hd_texture_pack.h')
files={}
for rel in ['src/hd_texture_pack.cpp','include/hd_texture_pack.h','src/hd_decode_queue.h','third_party/stb_image.h']:
    f=src/rel;dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('xb') as stream:stream.write(f.read_bytes());stream.flush();os.fsync(stream.fileno())
    assert sha(dst)==sha(f);files[rel]=dict(source=str(f),bytes=f.stat().st_size,sha256=sha(f))
canonical=r/'windows-x64/psxrecomp/runtime/include/hd_texture_pack.h'
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=files,header_matches_frozen_v61=True,canonical_header_sha256=sha(canonical),canonical_incompatible_difference='Canonical drops three incremental-index cost fields and hd_texture_pack_upload_index_incremental; this snapshot preserves both the interface and its implementation.',provenance='sampling-build-v48-upload-index/build.json names this source worktree; exact source/object equivalence is NOT established. New pack TU must be explicitly rebuilt and regression-tested.',frozen_v61_header_sha256=sha(frozen),gpu_executed=False,production_installed=False)
(out/'BASELINE.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-freeze.py');print(json.dumps(receipt))
