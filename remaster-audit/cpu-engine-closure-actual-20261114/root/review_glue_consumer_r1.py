"""Read-only pinned consumer-closure review; no target import, compiler, SDK or game."""
from pathlib import Path
import ast,datetime as dt,hashlib,json,os,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
c=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/capture'
b=c/'ledger-glue-r2-build-r1/build_glue_fixture.r1.py'
pins={b:'8c7bbfb8dad37e3aefe206b1a66052f9f5574f15f8a65c6e025e3e7db55ca4c1',c/'ledger-glue-r2-build/test_glue.r0.cpp':'7cce4f6b163ec606296b9e3cb03e45cae56ba3058c85d4414062e13abbde5f3c',r/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206/manifest.json':'e6ab30e9c9c03697b3c4dcd64a253d232cd0de1d1fbc9bc73d5c7880748de8b4',r/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206/src/debug_server.c':'b50aef2a4de7ef8ceb621ffc681d072699f88cc5247357a435ebe405cebc0185'}
rows=[]
for path,want in pins.items():
    got=hashlib.sha256(path.read_bytes()).hexdigest();assert got==want,(str(path),got)
    rows.append({'path':str(path),'sha256':got})
raw=b.read_bytes();tree=ast.parse(raw,filename=str(b))
headers=None
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DEBUG_HEADERS' for t in node.targets):headers=ast.literal_eval(node.value)
assert headers and len(headers)==56
v67=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v67-decode-identity-r3'
record=json.loads(next(path for path in pins if path.name=='manifest.json').read_bytes())['build']['debug']
recorded={os.path.normcase(os.path.normpath(k)):v for k,v in record['closure'].items()}
for name,(rel,want) in headers.items():
    path=v67/rel;got=hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.name==name and got==want and recorded[os.path.normcase(os.path.normpath(str(path)))]==want,(name,got)
    rows.append({'path':str(path),'sha256':got,'recorded_v69_project_dependency':True})
assert record['obj_sha256']=='dc75afc26f599ac93d20d877122312c0054900e85d9c3a9569a61d9c3c87a37f'
assert record['depfile_sha256']=='939b9cd139336fdb885bb3e0abfc944f74552894cfd4ab5d9e711831fe23acd8'
assert b'(CAPTURE / "ledger-glue-r2-build" / "test_glue.r0.cpp"' in raw
out=n/'glue-consumer-source-review-r1';out.mkdir(exist_ok=False)
res={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'source_pins':rows,'pins_checked':len(rows),'project_headers_checked':56,'recorded_closure_count':len(record['closure']),'source_clear_for_separate_cpu_diagnostic':True,'target_imported':False,'compiler_invoked':False,'toolchain_headers_read_or_hashed':False,'gpu_game_used':False,'review':'Full r0 builder and harness previously read; all r1 additions/changes read. Source pin and56 recorded project headers checked. Actual v69 debugconsumer base/patched compile-only plus unchanged28checkfakewiring.','correction':'Root initially misstated HERE fixture as missing; immediately retracted after actual line110 showed explicit CAPTURE/old-folder path. Frozen8c7 driver never required a fix.','limits':['No compile/run result yet; separate fresh coordinator CPUgrant required.','Baseobject byteequality informational only; consumer objects never linked/run.','Toolchain dependency contents checked by futurebuilder aftercompile, not rehashed inthismetadatareview.','Actualnativecommand defines are retained source constants; manifestclosure alone carries no command proof.','No T2r6/rendering/G4/material/camera/compositor/RT/DLSS/liveacceptance.']}
(out/'result.json').write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'pins':len(rows),'project_headers':56,'recorded_closure':len(record['closure']),'source_clear_only':True}))
