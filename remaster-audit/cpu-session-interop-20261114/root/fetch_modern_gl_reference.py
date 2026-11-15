from pathlib import Path
import datetime,hashlib,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-modern-gl-reference';out.mkdir(exist_ok=False);rows=[]
urls=[('NV_timeline_semaphore.txt','https://raw.githubusercontent.com/KhronosGroup/OpenGL-Registry/main/extensions/NV/NV_timeline_semaphore.txt'),('EXT_external_objects_win32.txt','https://raw.githubusercontent.com/KhronosGroup/OpenGL-Registry/main/extensions/EXT/EXT_external_objects_win32.txt'),('EXT_external_objects.txt','https://raw.githubusercontent.com/KhronosGroup/OpenGL-Registry/main/extensions/EXT/EXT_external_objects.txt')]
for name,url in urls:
    x=requests.get(url,timeout=15);row=dict(url=url,status=x.status_code)
    if x.status_code==200:(out/name).write_bytes(x.content);row.update(bytes=len(x.content),sha256=hashlib.sha256(x.content).hexdigest())
    rows.append(row)
url='https://api.github.com/repos/NVIDIAGameWorks/rtx-remix-minecraft/git/trees/7d2ba9f18415a6b518b9824a3b8faa79da0d96ac?recursive=1';x=requests.get(url,timeout=15);row=dict(url=url,status=x.status_code)
if x.status_code==200:
    obj=x.json();(out/'release-tree.json').write_text(json.dumps(obj,indent=2)+'\n');row['matching_paths']=[a['path'] for a in obj['tree'] if a['path'].endswith(('.java','.cpp')) and any(s in a['path'].lower() for s in ['interop','renderer','remixbridge'])];row['truncated']=obj.get('truncated')
rows.append(row);receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),items=rows,gpu_executed=False);(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
