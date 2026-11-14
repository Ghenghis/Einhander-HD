"""Metadata/source readback only. Does not import or execute proposal code."""
from pathlib import Path
import ast
import datetime as dt
import hashlib
import json
import psutil

R = Path('C:/github/Einhander')
N = Path(__file__).resolve().parent
P = R / '.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary'
S = R / '.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([11])
out = N / 'cpu-followup-readback-r1'
out.mkdir(exist_ok=False)
pins = {
    P / 'remix-probe-r5/runs/PR7-1-20261114T204240Z-rc.json': 'f211c63437ce5fd3ccfc41c5e613019fe209f78462fba8c4101074c7a6103365',
    P / 'remix-probe-r5/build_r7_cpu.r1.py': 'b0e08a6a71b7cab97e3deab5860aaa017bbe7d2d8ff3dcf90c1b424ab924f69e',
    P / 'remix-transport/t2/remix_t2.r1.h': 'a00ca23f99477082101db4ab41bab71c53d6b92b185ecee02b8906143edcdf15',
    P / 'remix-transport/t2/test_t2.r1.cpp': '752855bf3c34905a9e784e8feacd7adc08c3b9b5172e1049ab91fcdb184405ae',
    P / 'remix-transport/t2/build_t2_fixture.r1.py': 'fc07ca5fa907ae357009668e671aaad43c8463e97944e3047e4b2a8028959418',
    P / 'remix-transport/capture/CAPTURE-LEDGER-REVISION-SPEC-r1-20261114.md': '48d7fbfd0232d46fbcf4d0dbddefd4a9222de0478c72432be439fa3a09e3cf87',
    S / 'adapter-controls/controls_c457b58e_r1.py': 'f8b517c11cb32f0d3b2cfcee3ba51ebbf6cb2f5c13498cc2d9caff8bc223a907',
    S / 'adapter-controls/CONTROLS-R1-c457b58e-20261114.md': '2451c63404a139cf19e566a62f3474307e6dc2ec803a6c0299d2ea86abe2d7c7',
}
rows = []
for path, want in pins.items():
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != want:
        raise RuntimeError('Changed or oversized source: ' + str(path))
    raw.decode('utf-8')
    if path.suffix == '.py':
        ast.parse(raw)
    rows.append(dict(path=str(path.relative_to(R)), sha256=want, bytes=len(raw)))
receipt = json.loads((P / 'remix-probe-r5/runs/PR7-1-20261114T204240Z-rc.json').read_bytes())
if not (receipt['declined'] is True and receipt['child_pid'] is None and receipt['wrapper_exit'] == 3
        and receipt['precheck']['system_cpu_pct'] == 78.6 and receipt['precheck']['max_cpu'] == 60.0):
    raise RuntimeError('Unexpected refusal receipt')
pid, created = receipt['wrapper_pid'], receipt['wrapper_create_time']
try:
    absent = abs(psutil.Process(pid).create_time() - created) >= .001
except psutil.NoSuchProcess:
    absent = True
out_root = P / 'remix-probe-r5/runs/PR7-1-20261114T204240Z'
if not absent or out_root.exists():
    raise RuntimeError('Refused wrapper identity/output-root is still present')
data = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), source_pins=rows,
    metadata_readback_passed=True, wrapper_identity_absent=absent, wrapper_pid=pid, wrapper_creation_unix=created,
    refused_output_root_absent=True, original_refusal=receipt,
    tests_executed=False, proposal_imported=False, compiler_started=False, gpu_run=False, game_run=False,
    pr7_builder_r1_executed=False, pr7_cpu_controls_executed=False, t2_r1_source_blocked=True,
    t2_r1_controls_authored=71, t2_r1_controls_passed=None,
    collector_controls_r1_authored=74, collector_controls_r1_passed=None,
    source_review_limits='T2 r1 predicted B11 interleave failure and wrap/bounds/receipt corrections requested; no runtime validation')
(out / 'result.json').write_text(json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
(out / 'executed-reader.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(dict(metadata_readback_passed=True, source_pins=len(rows), wrapper_identity_absent=absent,
    tests_executed=False, compiler_started=False, result=str(out / 'result.json'))))
