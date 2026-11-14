from pathlib import Path
import datetime,hashlib,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-release-bridge-source';out.mkdir(exist_ok=False)
commit='7d2ba9f18415a6b518b9824a3b8faa79da0d96ac'
url=f'https://raw.githubusercontent.com/NVIDIAGameWorks/rtx-remix-minecraft/{commit}/rtxremix-java/native/remixbridge.cpp'
x=requests.get(url,timeout=20);x.raise_for_status();(out/'remixbridge.cpp').write_bytes(x.content)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=commit,url=url,sha256=hashlib.sha256(x.content).hexdigest(),bytes=len(x.content),gpu_executed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
