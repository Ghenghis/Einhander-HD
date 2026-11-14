from pathlib import Path
import datetime,hashlib,json,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
paths=['remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v5/READY.json',
       'remaster-audit/runtime-review/gpu-texture-remix-20261114/sdk-release-header/remix_c.h',
       'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3/build.json']
rows=[]
for path in paths:
    data=(r/path).read_bytes();rows.append(dict(path=path,bytes=len(data),null_bytes=data.count(b'\0'),prefix=repr(data[:160]),sha256=hashlib.sha256(data).hexdigest()))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),boot_utc=datetime.datetime.fromtimestamp(psutil.boot_time(),datetime.timezone.utc).isoformat(),files=rows)
(n/'post-reload-file-check.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
