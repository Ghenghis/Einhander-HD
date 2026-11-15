from pathlib import Path
import ast,datetime,hashlib,json
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
before=n/'fake-transport-ft1-r1/runs/20261114T181704Z/C1/fake-batch/hd-on_rewind-off/executed-world-flypast.py'
after=r/'remaster-audit/run_stage1_unassisted_review.py'
sha=lambda b:hashlib.sha256(b).hexdigest()
def function(path,name):
    text=path.read_text(encoding='utf-8')
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(text,node)
assert sha(before.read_bytes())=='c47b10929c318280b471cc60dc84a89f3b8fe4db59f325e7630dee482d1939a5'
assert function(before,'run')==function(after,'run')
guard=r/'remaster-audit/unassisted_command_guard.py'
assert sha(guard.read_bytes())=='9e6ca8159a2f471fcbbde996464a6ba2eb6a51846c44567eefdb6e5cceaa2240'
out=n/'ft1-current-run-verification-r1';out.mkdir(exist_ok=False)
d=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
    tested_runner_sha256=sha(before.read_bytes()),current_runner_sha256=sha(after.read_bytes()),
    unchanged_run_function_sha256=sha(function(after,'run').encode()),command_guard_unchanged=True,
    change_scope='Preparation explicitly enables diagnostic rings; run() body unchanged; actual current CLI/policy14 tests passed separately.',
    gpu_run=False,game_run=False,live_qualified=False)
(out/'result.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(d))
