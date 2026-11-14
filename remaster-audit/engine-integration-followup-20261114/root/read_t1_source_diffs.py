"""Source text/line-ending review only. No oracle, compiler or author-code execution."""
from pathlib import Path
import difflib
import hashlib
import json
import psutil

root=Path('C:/github/Einhander')
base=root/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/t1'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
for stem,suffix in [('remix_t1_reproject','h'),('test_t1_reproject','cpp'),('build_t1_fixture','py')]:
    texts=[]
    for revision in (0,1):
        path=base/f'{stem}.r{revision}.{suffix}';raw=path.read_bytes()
        print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),crlf=raw.count(b'\r\n'))))
        texts.append(raw.decode('utf-8').replace('\r\n','\n'))
    print(''.join(difflib.unified_diff(texts[0].splitlines(keepends=True),texts[1].splitlines(keepends=True),fromfile=stem+'r0',tofile=stem+'r1',n=3)))
for path in [root/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v61-view-metrics-r2/src/gte.cpp',
             root/'windows-x64/psxrecomp/runtime/src/gte.cpp']:
    raw=path.read_bytes();text=raw.decode('utf-8')
    anchor='static uint8_t s_gte_div_table[0x101];'
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),crlf=raw.count(b'\r\n'),
        exact_raw_anchor_count=sum(line==anchor for line in text.split('\n')),
        normalized_anchor_count=sum(line==anchor for line in text.replace('\r\n','\n').split('\n')))))
