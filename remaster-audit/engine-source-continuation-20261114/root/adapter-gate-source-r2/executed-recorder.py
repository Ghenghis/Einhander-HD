"""Small source/AST receipt only. Does not import or execute the guard/tests."""
from pathlib import Path
import ast
import datetime as dt
import hashlib
import json
import psutil

root = Path('C:/github/Einhander')
notes = Path(__file__).resolve().parent
process = psutil.Process()
process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
process.cpu_affinity([11])
out = notes / 'adapter-gate-source-r2'
out.mkdir(exist_ok=False)
sources = []
names = []
for name in ('gl_adapter_identity_guard.py', 'test_gl_adapter_identity_guard.py'):
    path = root / 'remaster-audit' / name
    raw = path.read_bytes()
    tree = ast.parse(raw, filename=str(path))
    sources.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
    if name.startswith('test_'):
        names = [node.name for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    (out / name).write_bytes(raw)
receipt = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), sources=sources,
    syntax_valid=True, test_methods_declared=len(names), test_method_names=names,
    tests_executed=False, passing_tests=None, gpu_run=False, game_run=False,
    integrated_into_launcher=False,
    peer_review='8a3c1e4e32b79ed3734d13a17ff40e4423d7f050530f3070d17007bba2a257c6',
    changes=['UTF-8 original bounded bytes; no silent startup truncation',
             'identity must precede GL-ready; software fallback still rejects',
             'listener PID/creation checked before AND after each of two RPC queries',
             'extra controls for exact dual-raster marker, invalid decoding, ordering and model suffix'],
    remaining=['execute focused controls on a fresh grant',
               'implement retained-process/exact-port listener sampling in real runner',
               'compile one-time GL identity patch in a new private build',
               'qualify actual game adapter/focus/frame progression separately from performance'])
(out / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
(out / 'executed-recorder.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({key:value for key,value in receipt.items() if key!='test_method_names'}))
