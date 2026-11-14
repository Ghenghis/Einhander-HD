"""Normalize line endings for bounded source-only review; no image or author imports."""
from pathlib import Path
import ast
import difflib
import hashlib
import json
import psutil

notes=Path(__file__).resolve().parent
base=Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/tools')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def literal(text,name):
    for node in ast.parse(text).body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id==name for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError('missing source literal '+name)
versions={}
for revision in (5,6):
    path=base/f'ui_speck_measure_r{revision}.py';raw=path.read_bytes()
    versions[revision]=(raw.decode('utf-8').replace('\r\n','\n'),hashlib.sha256(raw).hexdigest())
for revision in (6,):
    older,older_hash=versions[revision-1];newer,newer_hash=versions[revision]
    if literal(older,'EXPECTED')!=literal(newer,'EXPECTED'):raise RuntimeError('source pin table changed')
    print(json.dumps(dict(from_revision=revision-1,to_revision=revision,old_sha256=older_hash,new_sha256=newer_hash,expected_table_identical=True)))
    print(''.join(difflib.unified_diff(older.splitlines(keepends=True),newer.splitlines(keepends=True),
                                      fromfile=f'r{revision-1}',tofile=f'r{revision}',n=3)))
