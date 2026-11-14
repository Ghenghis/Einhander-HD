from pathlib import Path
import datetime,hashlib,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-release-header';out.mkdir(exist_ok=False)
url='https://api.github.com/repos/NVIDIAGameWorks/rtx-remix-minecraft/commits/7d2ba9f'
x=requests.get(url,timeout=15);x.raise_for_status();commit=x.json()['sha']
source=f'https://raw.githubusercontent.com/NVIDIAGameWorks/rtx-remix-minecraft/{commit}/rtxremix-java/native/include/remix_c.h'
h=requests.get(source,timeout=15);h.raise_for_status();(out/'remix_c.h').write_bytes(h.content)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=commit,commit_url=url,source_url=source,sha256=hashlib.sha256(h.content).hexdigest(),relation='Commit suffix of official v0.1.1 release jar/installer; artifact digest recorded separately',gpu_executed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
