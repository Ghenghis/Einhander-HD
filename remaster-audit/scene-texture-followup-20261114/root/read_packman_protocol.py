from pathlib import Path
import datetime,hashlib,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-package-protocol';out.mkdir(exist_ok=False)
commit='4b228424b5794b91a994198c3e48b3a00c25e87e';rows=[]
for path in ['packman/bootstrap/install_package.py','packman/packmanconf.py']:
    url=f'https://raw.githubusercontent.com/NVIDIAGameWorks/rtx-remix-minecraft/{commit}/{path}'
    x=requests.get(url,timeout=15);x.raise_for_status();f=out/Path(path).name;f.write_bytes(x.content)
    rows.append(dict(url=url,sha256=hashlib.sha256(x.content).hexdigest(),bytes=len(x.content)))
x=requests.get('https://api.github.com/repos/NVIDIAGameWorks/rtx-remix-minecraft/releases/latest',timeout=15)
release=x.json() if x.status_code==200 else {}
metadata=dict(status=x.status_code,tag=release.get('tag_name'),url=release.get('html_url'),assets=[{k:a.get(k) for k in ['name','size','browser_download_url','digest']} for a in release.get('assets',[])])
(out/'result.json').write_text(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_files=rows,release=metadata,software_installed=False),indent=2)+'\n')
print(json.dumps(metadata))
