"""Static review proof only. No target imports, compiler, DLL, network or game."""
from pathlib import Path
import ast, datetime as dt, hashlib, json, re, psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
n=Path(__file__).resolve().parent
c=Path('C:/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-transport/capture')
pins={
 'ledger-glue-r3-build/build_glue_fixture.r2.py':'b057695aa257b9e7167f6610b6af20b6fe5c92297e4c9cb4e597fc5304f3e86a',
 'ledger-glue-r3-build-r3/build_glue_fixture.r3.py':'11c26259ac40c3db1d9cba06d90e5fd6f54629e90dd0279a05fec6904921157c',
 'ledger-glue-r3/test_glue.r1.cpp':'44ab03a6ef6e76e340750ff5d45ad4864f061727729d1d6384f3fc5056be62cf',
 'ledger-glue-r3-build-r3/test_glue.r2.cpp':'3ec929d534be51104cd368f05c236db8bcf67837440e5db381046f3f42b15e4b',
 'ledger-glue-r3-build/build_glue_fixture.r1-to-r2.diff':'355c51b30f913ca6874030a6eee2aaea750e773936747be1a7b00d703be3e08a',
 'ledger-glue-r3-build-r3/build_glue_fixture.r2-to-r3.diff':'d30f18bb6f60f76e3ff5b51c36a7844a63e78c426460cbb79dddafd9cf9c1956',
 'ledger-glue-r3-build-r3/test_glue.r1-to-r2.diff':'7f4ac03011e1aa35b9be8e70dee69135ca868e08c3c7f894f6ea33be9219bd72',
 'ledger-glue-r3/patched/scene_runtime.cpp':'b0d820a705714fa024475393ce3359f1d8a5a0764f75dccb0cf4e2990e9895b4',
 'ledger-glue-r3/patched/scene_runtime.h':'6c69adcbe2dc078c4062734bf09bf5b3e1c75e7ac45cbddbdf8b437b36076dfc',
 'ledger-glue-r3/patched/scene_t2_bridge.r3.cpp':'5182d80ddb8c4aa6bde518be23ccc54157f21c693d643c222d7d67a97f0476cb',
 'ledger-glue-r3/patched/scene_t2_bridge.r3.h':'f09f3296bb2894fd228799e34bc047d7d655cc87dc88199539f7702cb5156c73'}
rows=[];raws={}
for rel,want in pins.items():
 raw=(c/rel).read_bytes();got=hashlib.sha256(raw).hexdigest();assert got==want,(rel,got)
 rows.append(dict(path=str(c/rel),sha256=got,bytes=len(raw)));raws[rel]=raw
def functions(raw):
 return {a.name:ast.dump(a,include_attributes=False) for a in ast.parse(raw).body if isinstance(a,ast.FunctionDef)}
old=functions((c/'ledger-glue-r2-build-r1/build_glue_fixture.r1.py').read_bytes())
mid=functions(raws['ledger-glue-r3-build/build_glue_fixture.r2.py'])
new=functions(raws['ledger-glue-r3-build-r3/build_glue_fixture.r3.py'])
assert old.keys()==mid.keys()==new.keys()
assert [k for k in old if old[k]!=mid[k]]==['fixture_ok','main']
assert [k for k in mid if mid[k]!=new[k]]==['fixture_ok','main']
before=raws['ledger-glue-r3/test_glue.r1.cpp'].decode().splitlines()
after=raws['ledger-glue-r3-build-r3/test_glue.r2.cpp'].decode().splitlines()
checks=lambda lines:[x for x in lines if x.lstrip().startswith('CHECK(')]
assert checks(before)==checks(after) and len(checks(after))==19
assert 'if (!f) return c;' in '\n'.join(after)
assert len(re.findall(r"diag\('[LOMQPRF]'\);",'\n'.join(after)))==7
builder=raws['ledger-glue-r3-build-r3/build_glue_fixture.r3.py'].decode()
assert 'rows[-1]["passed"] = ran and fixture_passed' in builder
assert builder.index('fixture_passed = fixture_ok')>builder.index('ran = run_child("run-glue"')
out=n/'glue-r3-closure-r3-source-review';out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),pins=rows,unchanged_builder_helpers_except_fixture_ok_and_main=True,unchanged_authored_check_lines=19,null_safe_stamp=True,diagnostic_groups=7,source_clear_for_one_separately_granted_cpu_job=True,tests_executed=0,target_imported=False,compiler_invoked=False,gpu_game_used=False,
 review='Root read full runtime R2-to-R3 changes, bridge and old fixture previously; now read both builder deltas, changed paths/layout/compile/fixture verdict, corrected fixture delta and null-safe function. Runtime and bridge retain reviewed bytes. Private CPU closure only.',
 limits=['Actual compile/link/19 checks still unrun at review time.','Older closure r2 is superseded and must not be granted.','Fresh coordinator grant and copied fa5 whole Job, one CPU, BelowNormal, 120s/1GiB, resource checks and exclusive output required.','The ten compiles may exhaust the outer 120s limit; preserve failure and do not auto-retry.','Gate consumer uses owned taken pointer, gate before release, release once, single consumer; no general checked handle API.','No continuous per-frame scheduling, material consumer, G4, compositor, native suppression, RT, DLSS or live qualification.','No new toolchain library/header sweep in this static review.'])
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(out=str(out),pins=len(rows),source_clear_only=True,tests_executed=0)))
