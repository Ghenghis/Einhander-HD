"""Read official package metadata only; no download/install/runtime startup."""
from pathlib import Path
import datetime,hashlib,json,psutil,requests
n=Path(__file__).resolve().parent;out=n/'sdk-package-reference';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
commit='4b228424b5794b91a994198c3e48b3a00c25e87e';repo='NVIDIAGameWorks/rtx-remix-minecraft'
url=f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1';x=requests.get(url,timeout=20);x.raise_for_status()
tree=x.json();paths=[v['path'] for v in tree['tree'] if v['type']=='blob' and ('packman' in v['path'].lower() or v['path'].lower() in ['readme.md','pull_dependencies.bat'])]
items=[]
for path in paths:
    if not (path.lower().endswith(('.xml','.json','.toml','.md','.bat')) and len(items)<8):continue
    u=f'https://raw.githubusercontent.com/{repo}/{commit}/{path}';v=requests.get(u,timeout=15)
    if v.status_code==200 and len(v.content)<=120000:
        p=out/path.replace('/','__');p.write_bytes(v.content)
        items.append(dict(path=path,url=u,sha256=hashlib.sha256(v.content).hexdigest(),bytes=len(v.content)))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),repository=repo,commit=commit,tree_url=url,
             relevant_paths=paths,items=items,software_installed=False,runtime_started=False,gpu_executed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(relevant_paths=paths,files=len(items),gpu=False)))
