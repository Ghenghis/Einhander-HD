from pathlib import Path
import datetime,hashlib,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-modern-gl-client';out.mkdir(exist_ok=False);commit='7d2ba9f18415a6b518b9824a3b8faa79da0d96ac';rows=[]
for path in ['src/main/java/com/nvidia/rtxremix/minecraft/gl/GlInterop.java','src/main/java/com/nvidia/rtxremix/minecraft/RemixRenderer.java','forge-1.12.2/bridge/native/legacy-gl-interop.cpp']:
    url=f'https://raw.githubusercontent.com/NVIDIAGameWorks/rtx-remix-minecraft/{commit}/{path}';x=requests.get(url,timeout=15);row=dict(path=path,url=url,status=x.status_code)
    if x.status_code==200:(out/Path(path).name).write_bytes(x.content);row.update(bytes=len(x.content),sha256=hashlib.sha256(x.content).hexdigest())
    rows.append(row)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=commit,files=rows,gpu_executed=False);(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
