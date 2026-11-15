"""Static ledger R2/R3 source+literal-input closure review; no target imports or compilation."""
from pathlib import Path
import ast,datetime as dt,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
c=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/capture'
pins={'ledger-r2/scene_ledger.r2.h':'9bcb4ea1f5bb5da219d11072b547300ea4c5f178381964751b6b57c293d5167d','ledger-r2/scene_ledger.r2.cpp':'10585241c8546b00bf3c3580089ad7f373e41f68bc81327f013cdc55ff91528d','ledger-r2/test_scene_ledger.r2.cpp':'7f7bd5ddbba09279c2c08ef4250a47d53e01da92c00eaa566ec317346a13a5e6','ledger-r2/build_scene_ledger_fixture.r2.py':'2d31c89c1f7507046c4df960bc15dfe66a900cee6507d331a8dda4e763633b35','ledger-r3/scene_ledger.r3.h':'9a0af4a903cfbd653ed858cec2f23e71ade8322fe6e55255e1dbddff833073fd','ledger-r3/scene_ledger.r3.cpp':'234993106083f7ed5633d50b6a0872851397c8d6198bc8f508ecb1cb4564513e','ledger-r3/test_scene_ledger.r3.cpp':'a51b2c1d6676cab2642e7196f28fdebc509029c4035db82f21b450f568af23b4','ledger-r3/build_scene_ledger_fixture.r3.py':'f08a5a2e2b51f6761f4a81bb6621fd6e96a8421a5fb1936340db4c1c9b2a81fc'}
rows=[];trees={}
for rel,want in pins.items():
    path=c/rel;raw=path.read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(rel,got)
    rows.append({'path':str(path),'sha256':got,'bytes':len(raw)})
    if rel.endswith('.py'):trees[rel]=ast.parse(raw,filename=rel)
env={'HERE':c/'ledger-r3','LEDGER0':c/'ledger-r0','LEDGER1':c/'ledger-r1','LEDGER2':c/'ledger-r2','V66':r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3/src'}
def lit(node):
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,ast.Name):return env[node.id]
    if isinstance(node,ast.Tuple):return tuple(lit(x) for x in node.elts)
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):return lit(node.left)/lit(node.right)
    if isinstance(node,ast.Dict):return {lit(k):lit(v) for k,v in zip(node.keys,node.values)}
    raise ValueError('Not permitted literal path expression '+ast.dump(node))
tree=trees['ledger-r3/build_scene_ledger_fixture.r3.py'];node=next(node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='INPUTS' for t in node.targets))
inputs=lit(node.value);assert len(inputs)==11
input_rows=[]
for name,(path,want) in inputs.items():
    got=hashlib.sha256(path.read_bytes()).hexdigest();assert got==want,(name,got)
    input_rows.append({'name':name,'path':str(path),'sha256':got})
base=ast.parse((c/'ledger-r1/build_scene_ledger_fixture.r1.py').read_bytes())
funcs=lambda t:{x.name:ast.dump(x,include_attributes=False) for x in t.body if isinstance(x,ast.FunctionDef)}
f0=funcs(base)
for t in trees.values():
    fs=funcs(t);assert fs.keys()==f0.keys()
    for name in fs:
        if name!='main':assert fs[name]==f0[name],name
cpp=(c/'ledger-r3/scene_ledger.r3.cpp').read_text(encoding='utf-8');assert 'if (s->native_screen_mapping != 1) return LEDGER_OK;' in cpp
out=n/'ledger-r3-source-review-r1';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'source_pins':rows,'literal_input_pins':input_rows,'unchanged_builder_helpers_except_main':True,'source_clear_for_separate_cpu_fixture':True,'target_imported':False,'compiler_invoked':False,'gpu_game_used':False,'review':'Root read full R1-toR2 implementation/header additions/new28suite and builderdelta, full R2-toR3 cpp/test/builderdelta. Stateless footprint rejects unknownmapping, allbodywrites still need runtimeclosed-at-sealgate. Oldstructlayouts unchanged.','authored_suites':{'r0_regression':99,'r1_regression':32,'r2_regression':28,'r3':29},'limits':['Counts overlap; not188uniquenewchecks.','R2/R3 not executed yet; freshcopiedfa5CPUgrant120s1GiBoneCPU/Bnormal/freshresources/exclusiveoutputs required.','No transportable realframe, glueR3/composition/G4/camera/RT/DLSS/install proof.','Closed-at-seal body check must be implemented and meaningfullytested in glueR3 before any live binding.','No compiler library/header sweep in this static source review.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'source_pins':len(rows),'literal_inputs':len(input_rows),'source_clear_only':True,'tests_executed':0}))
