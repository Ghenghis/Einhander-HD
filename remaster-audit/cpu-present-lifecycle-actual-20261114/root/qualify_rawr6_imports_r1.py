"""Hash and inspect the declared local import graph without importing the target."""
from pathlib import Path
import ast, datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
p=R/'remaster-audit/parallel-stages-20261114/s67/proposals/raw37c-diagnostic/raw37c_driver_r6.py'
raw=p.read_bytes(); h=hashlib.sha256(raw).hexdigest(); assert h=='21daa0f436588291d82529fbcd5981cd19213b9f88eab393c1a8c1aa2cb7b394'
tables={}
for node in ast.parse(raw).body:
    if isinstance(node,ast.Assign):
        for target in node.targets:
            if isinstance(target,ast.Name) and target.id in ('PACING_CLOSURE','PACING_CLOSURE_LAZY'): tables[target.id]=ast.literal_eval(node.value)
assert len(tables['PACING_CLOSURE'])==11 and len(tables['PACING_CLOSURE_LAZY'])==4
rows=[]
for group,table in tables.items():
    for name,(rel,want) in table.items():
        source=R/rel; b=source.read_bytes(); got=hashlib.sha256(b).hexdigest(); assert got==want,(name,got,want)
        rows.append(dict(name=name,group=group,path=str(source),sha256=got,bytes=len(b)))
def imports(nodes):
    for n in nodes:
        if isinstance(n,ast.Import):
            for a in n.names: yield a.name.split('.')[0]
        elif isinstance(n,ast.ImportFrom) and n.module: yield n.module.split('.')[0]
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        elif isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='__name__': continue
        elif isinstance(n,(ast.If,ast.Try,ast.ClassDef,ast.With,ast.For,ast.While)):
            for field in ('body','orelse','finalbody'): yield from imports(getattr(n,field,[]))
            for handler in getattr(n,'handlers',[]): yield from imports(handler.body)
def local(name):
    for root in [R/'remaster-audit',R/'windows-x64/tools']:
        f=root/(name+'.py')
        if f.is_file(): return f
todo=[N/'pacing-own-cache.py']; seen_paths=set(); names=set()
while todo:
    f=todo.pop()
    if f in seen_paths: continue
    seen_paths.add(f)
    for name in imports(ast.parse(f.read_bytes()).body):
        target=local(name)
        if target is not None: names.add(name); todo.append(target)
assert names==set(tables['PACING_CLOSURE']),(sorted(names),sorted(tables['PACING_CLOSURE']))
out=N/'rawr6-import-source-qualification-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_hash_and_static_local_graph_pass=True,driver=str(p),driver_sha256=h,load_time_modules=sorted(names),local_module_pins=rows,scope='Static local import statements through module/if/try/class bodies; no target import or dynamic/third-party closure proof.',target_imported=False,target_executed=False,third_party_closure_qualified=False,gpu_used=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(source_hash_and_static_local_graph_pass=True,driver_sha256=h,load_time_modules=len(names),all_local_pins=len(rows),target_executed=False)))
