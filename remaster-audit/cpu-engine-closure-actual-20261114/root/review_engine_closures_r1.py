"""Source-only pin/AST/additive checks; never imports a target or invokes a compiler."""
from pathlib import Path
import ast,datetime as dt,hashlib,json,psutil
p=psutil.Process(); p.cpu_affinity([11]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
n=Path(__file__).resolve().parent
base=Path('C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/capture')
pins={
'ledger-glue-r2-build/build_glue_fixture.r0.py':'70592507cfd3aab0198aea781dda160d3dfd2ce9951d19c92c098c69aa868730',
'ledger-glue-r2-build/test_glue.r0.cpp':'7cce4f6b163ec606296b9e3cb03e45cae56ba3058c85d4414062e13abbde5f3c',
'ledger-r1/scene_ledger.r1.h':'f080658b11c2692de5d47c88989d203cd78bb2b058b128012ff45a394b62f15c',
'ledger-r1/scene_ledger.r1.cpp':'f39a436311a401873276c3f9ad58d3e5bb2117dcb9d0e858cdb73f9c0fc755fb',
'ledger-r1/test_scene_ledger.r1.cpp':'eb4655ec65a65599b1cf1fbbe5a3cf48eced5ee847a599a9930eabfc7d468cc2',
'ledger-r1/build_scene_ledger_fixture.r1.py':'5430020d4ad710f3f400ea2da958e6c209f8244ca4676edbf5c446d443879f65',
'ledger-r0/scene_ledger.r0.cpp':'9614a6a81bd2175418a68551044601cba85c1621e6a91d2c3dcba2b4e88be62c'}
rows=[]
for rel,want in pins.items():
    raw=(base/rel).read_bytes(); got=hashlib.sha256(raw).hexdigest(); assert got==want,(rel,got)
    if rel.endswith('.py'): ast.parse(raw,filename=rel)
    rows.append({'path':str(base/rel),'sha256':got,'bytes':len(raw),'ast_parse_only':rel.endswith('.py')})
old=(base/'ledger-r0/scene_ledger.r0.cpp').read_text(encoding='utf-8')
new=(base/'ledger-r1/scene_ledger.r1.cpp').read_text(encoding='utf-8')
new='\n'.join(x for x in new.splitlines() if not x.startswith('// r1 (2026-11-14): ADDITIVE revision'))+'\n'
prefix=new.split('// r1 (additive): display hazard of an explicit target rect;')[0].replace('#include "scene_ledger.r1.h"','#include "scene_ledger.r0.h"')
assert prefix==old,'R1 preceding implementation differs from R0'
out=n/'engine-closure-source-review-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'source_pins':rows,'unchanged_r0_implementation':True,'target_imported':False,'compiler_invoked':False,'game_gpu_used':False,'review':'Root read full glue builder/harness; ledgerR1 header/new implementation/new32check suite/full builder and unchangedR0 comparison. Source-clear only for separately granted synthetic CPU diagnostics.','limitations':['Glue28 is empty/refusal wiring with fake GPU/PGXP, not transported primitive rendering or T2r6 integration.','Standalone glue build does not compile the actual retained v69 debug consumer; add exactconsumer closure before merge/build acceptance.','Native C/CPP compile-check preserves original flags; strict warnings apply to changed glue/ledger/harness only.','Hermetic depfile check uses whitespace parsing; a path with spaces would refuse, not silently admit. Compiler hashed then invoked, runtime libraries provenance limited.','LedgerR1 display-hazard still requires old policy;32new+99regression are AUTHORED/UNRUN.','Ledger reference resolution is bounded but quadratic in4096capacity; no live latency claim.','No G4/material/camera/depth/motion/SDK/compositor/RT/DLSS/install/visual proof.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'pins':len(rows),'additive':True,'source_clear_only':True,'executed_targets':0}))
