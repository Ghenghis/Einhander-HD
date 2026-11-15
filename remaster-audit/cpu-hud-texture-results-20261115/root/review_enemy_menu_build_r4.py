"""Static menu merge/builder review; no compiler, dependency sweep, game or GPU."""
from pathlib import Path
import ast,datetime as dt,difflib,hashlib,json,psutil
p=psutil.Process();p.cpu_affinity([11]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
u=r/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
b=u/'proposals/p1-player-color/build';s=u/'skin-selector-map/p1r2-enemy-channel'
files={b/'build_p1r2_v69_r4.py':'a8a8f8628de324d640dcdd9e9ae11a18a413f2b66ccc68e894ca32dcbbe50a2f',s/'main.cpp':'91a2bcab3ec889b719de6010537efb82ce3ce906eda820a380b5f169bd7d76fe',s/'v69-merge/main.v69-plus-p1r2.cpp':'fe85c7e4caf7be4f76ce3a8528ba08868e9468113940ea44e716aa68a2ae6dd3',s/'base/main.p1r1-994af594.cpp':None,u/'builds/p1-v69-2240/src/main.cpp':'d8abf287ee313e15b8dbe01837b1a217ef13f57d290e51d2d47947671c82e144'}
rows=[];data={}
for f,want in files.items():
    raw=f.read_bytes();got=hashlib.sha256(raw).hexdigest()
    if want:assert got==want,(str(f),got)
    else:assert got.startswith('994af594')
    rows.append({'path':str(f),'sha256':got,'bytes':len(raw)});data[f]=raw
old=b/'build_p1_v69_r3.py';raw=old.read_bytes();oldsha=hashlib.sha256(raw).hexdigest();assert oldsha.startswith('5f713865');rows.append({'path':str(old),'sha256':oldsha,'bytes':len(raw)})
t0,t1=ast.parse(raw),ast.parse(data[b/'build_p1r2_v69_r4.py'])
def inputs(t):
    node=next(x for x in t.body if isinstance(x,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='PINS' for k in x.targets))
    return {ast.literal_eval(k):ast.dump(v,include_attributes=False) for k,v in zip(node.value.keys,node.value.values)}
a,z=inputs(t0),inputs(t1);assert a.keys()==z.keys()
assert [k for k in a if a[k]!=z[k]]==['p1_main']
def remaining(t):return [ast.dump(x,include_attributes=False) for x in t.body if not(isinstance(x,ast.Expr) and isinstance(x.value,ast.Constant) and isinstance(x.value.value,str)) and not(isinstance(x,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='PINS' for k in x.targets))]
assert remaining(t0)==remaining(t1),'Builder executable logic changed beyond PINS'
def delta(before,after):
    a,b=before.splitlines(keepends=True),after.splitlines(keepends=True)
    return [(tag,a[i:j],b[k:l]) for tag,i,j,k,l in difflib.SequenceMatcher(a=a,b=b).get_opcodes() if tag!='equal']
proposal=delta(data[s/'base/main.p1r1-994af594.cpp'],data[s/'main.cpp'])
merged=delta(data[u/'builds/p1-v69-2240/src/main.cpp'],data[s/'v69-merge/main.v69-plus-p1r2.cpp'])
assert proposal==merged,'Merged delta differs from reviewed menu delta'
out=n/'enemy-menu-build-source-review-r4';out.mkdir(exist_ok=False)
receipt={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'pins':rows,'builder_logic_unchanged_except_p1_main':True,'merged_delta_equals_reviewed_proposal':True,'root_full_menu_patch_read':True,'independent_builder_peer':'codex-einhander-coverage-gaps reported UI-P1R2-V69-R4-SOURCE-REVIEW-20261115 source-clear, no execution','source_clear_for_fresh_private_cpu_compile_link':True,'compiler_invoked':False,'dependency_library_sweep_repeated':False,'gpu_game_used':False,'limits':['Must use fresh coordinator grant/copiedfa5 Job/exclusive outputs; no duplicate R3/R4 build.','Only colour presets on current allowlists; no realistic skins/PBR/detail-map live application or per-role binding.','Strength retained, zero can remain visually inactive; only active row shown in OSD. Persistence/fullmodernmenu unresolved.','Build and actual player/enemy UI/unchangedchannel/atomic-rejection/input/capability behavior remain unverified.','Original37c/v69/frozen sources must remain unchanged.']}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({'out':str(out),'pins':len(rows),'merged_delta_equal':True,'source_clear_only':True}))
