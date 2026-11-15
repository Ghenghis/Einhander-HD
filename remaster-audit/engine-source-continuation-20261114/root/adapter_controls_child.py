"""Run exactly the pinned pure-data controls. No GL, devices or transport."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import sys
import time
import types
import unittest

root=Path('C:/github/Einhander/remaster-audit')
out=Path(sys.argv[1])
sources={
    'gl_adapter_identity_guard': 'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08',
    'test_gl_adapter_identity_guard': '18977886193c7dd1bdeedb12bc7df30215e21765ec4c775ef7c75df1dda00503'}
loaded={}
start=time.perf_counter()
for name,expected in sources.items():
    path=root/(name+'.py');raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('pinned source changed: '+name)
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    loaded[name]=module
suite=unittest.defaultTestLoader.loadTestsFromModule(loaded['test_gl_adapter_identity_guard'])
declared=suite.countTestCases()
if declared!=21:raise RuntimeError('expected exactly21 control methods')
result=unittest.TextTestRunner(verbosity=2).run(suite)
passed=result.wasSuccessful() and result.testsRun==21 and not result.skipped
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),passed=passed,
    test_methods_declared=declared,tests_run=result.testsRun,failures=len(result.failures),
    errors=len(result.errors),skipped=len(result.skipped),elapsed_s=time.perf_counter()-start,
    source_pins=sources,scope='pure synthetic evidence controls only',game_run=False,gpu_run=False,
    live_qualified=False,integrated_into_launcher=False)
with out.open('x',encoding='utf-8') as file:json.dump(receipt,file,indent=2);file.write('\n')
sys.exit(0 if passed else 1)
