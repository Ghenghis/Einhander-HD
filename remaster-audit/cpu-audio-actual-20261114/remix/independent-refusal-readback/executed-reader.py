"""Readback of the second corrected-builder refusal and latest source revisions.

Hashes/AST/known process metadata only. No proposal imports/tests/compiler/socket.
"""
from pathlib import Path
import ast
import datetime as dt
import hashlib
import json
import psutil

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
P=R/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary'
A=R/'remaster-audit/parallel-stages-20261114/s67/proposals/audio-telemetry-combined-r1'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
out=N/'cpu-followup-readback-r2';out.mkdir(exist_ok=False)
pins={
 P/'remix-probe-r5/runs/PR7-1-20261114T210152Z-rc.json':'7d7dae89cb87e64ff0d5d7e8447cf2676c4475d5bc1930f27db58d229ead94a3',
 P/'remix-probe-r5/build_r7_cpu.r1.py':'b0e08a6a71b7cab97e3deab5860aaa017bbe7d2d8ff3dcf90c1b424ab924f69e',
 P/'remix-transport/t2/remix_t2.r3.h':'8baba81cdbb402585f4f535d830cea822ca9b81f963fb64bc809f53ff019911b',
 P/'remix-transport/t2/test_t2.r3.cpp':'215df688a16079308e66a4c2b89fd4ab46ac32a7c5075cf8aa9f0744bdc4fff4',
 P/'remix-transport/t2/build_t2_fixture.r3.py':'fe89c15f33354259dcd6ec346e8475363b6ce9f9e7373794fa6e0c446ba705bc',
 A/'run_combined_r2.py':'a3def870c5acb192c9622685a8be566d7132638ddca57a83fcc84a7fde760ecd',
 A/'test_combined_getters_r1.cpp':'c698ca22c933d635beb411334783fc94b31a8e1ff72189b55a9e7c4101f55368',
 A/'recomp_audio_drc.h.proposed':'c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c',
 A/'main.cpp.proposed':'8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36',
}
rows=[]
for path,want in pins.items():
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=want or b'\0' in raw:raise RuntimeError('Changed source '+str(path))
    raw.decode('utf-8')
    if path.suffix=='.py':ast.parse(raw)
    rows.append(dict(path=str(path.relative_to(R)),sha256=want,bytes=len(raw)))
original=json.loads((P/'remix-probe-r5/runs/PR7-1-20261114T210152Z-rc.json').read_bytes())
if not(original['declined'] is True and original['child_pid'] is None and original['wrapper_exit']==3
       and original['precheck']['system_cpu_pct']==64.6 and original['precheck']['max_cpu']==60.0):
    raise RuntimeError('Unexpected refusal content')
pid=original['wrapper_pid'];created=original['wrapper_create_time']
try:absent=abs(psutil.Process(pid).create_time()-created)>=.001
except psutil.NoSuchProcess:absent=True
if not absent or (P/'remix-probe-r5/runs/PR7-1-20261114T210152Z').exists():
    raise RuntimeError('Refused process identity/output still present')
receipt=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_readback_passed=True,
    source_pins=rows,original_refusal=original,wrapper_identity_absent=True,refused_output_root_absent=True,
    tests_executed=False,proposal_imported=False,compiler_started=False,gpu_run=False,game_run=False,
    builder_r1_executed=False,t2_r3='82AUTHORED/UNRUN; source-cleared future CPU fixture only',
    audio_driver_r2='source-cleared future two-harness CPU fixture only; UNRUN',live_qualified=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
(out/'executed-reader.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(dict(metadata_readback_passed=True,pins=len(rows),wrapper_identity_absent=True,
                     tests_executed=False,compiler_started=False,result=str(out/'result.json'))))
