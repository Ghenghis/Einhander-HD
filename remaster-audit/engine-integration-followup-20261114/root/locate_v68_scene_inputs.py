"""Inspect two known private build manifests only; no recursive filesystem search."""
from pathlib import Path
import json
import psutil

base=Path('C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def walk(value,path=''):
    if isinstance(value,dict):
        for key,item in value.items():
            if 'scene_capture' in str(key):print(json.dumps(dict(location=path,key=key,value=item)))
            else:walk(item,path+'/'+str(key))
    elif isinstance(value,list):
        for index,item in enumerate(value):walk(item,path+'/'+str(index))
    elif isinstance(value,str) and 'scene_capture' in value:print(json.dumps(dict(location=path,value=value)))
for name in ('build.json','prepared.json'):
    path=base/name
    if path.exists():walk(json.loads(path.read_bytes()),name)
