"""AST/literal/hash metadata only; do not import or execute the staging driver."""
from pathlib import Path
import ast, datetime as dt, hashlib, json, psutil
R=Path('C:/github/Einhander'); N=Path(__file__).resolve().parent
me=psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([11])
p=R/'remaster-audit/parallel-stages-20261114/s67/proposals/raw37c-diagnostic/raw37c_driver_r5.py'
data=p.read_bytes(); h=hashlib.sha256(data).hexdigest()
assert h=='b72bceabbb1302ab46a0d27e1258c2a729f0c77750d9c73c6787db218cd54437'
tree=ast.parse(data); tables={}
for node in tree.body:
    if isinstance(node,ast.Assign):
        for target in node.targets:
            if isinstance(target,ast.Name) and target.id in ('PACING_CLOSURE','PACING_CLOSURE_LAZY'):
                tables[target.id]=ast.literal_eval(node.value)
assert len(tables['PACING_CLOSURE'])==10 and len(tables['PACING_CLOSURE_LAZY'])==2
rows=[]
for group,table in tables.items():
    for name,want in table.items():
        source=R/'remaster-audit'/(name+'.py'); raw=source.read_bytes(); got=hashlib.sha256(raw).hexdigest(); assert got==want,(name,got,want)
        ast.parse(raw)
        rows.append(dict(name=name,group=group,path=str(source),sha256=got,bytes=len(raw)))
out=N/'rawr5-import-source-qualification-r1'; out.mkdir(exist_ok=False)
rec=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_qualification_pass=True,driver=str(p),driver_sha256=h,local_module_pins=rows,target_imported=False,target_executed=False,third_party_closure_qualified=False,gpu_used=False)
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(source_qualification_pass=True,driver_sha256=h,local_modules_verified=len(rows),target_executed=False)))
