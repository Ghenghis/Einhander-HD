from pathlib import Path
import datetime,hashlib,json,psutil,requests
n=Path(__file__).resolve().parent;out=n/'sdk-diagnostic-reference';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
commit='42b54bbe2a9280f7720e5b64415c78aa3e15224f';items=[]
for path in ['src/dxvk/rtx_render/rtx_remix_api.cpp','tests/rtx/apps/RemixAPI_C/remixapi_example_c.c','src/dxvk/rtx_render/rtx_metrics.cpp']:
    url=f'https://raw.githubusercontent.com/NVIDIAGameWorks/dxvk-remix/{commit}/{path}'
    x=requests.get(url,timeout=20)
    row=dict(url=url,status=x.status_code,repository_path=path)
    if x.status_code==200:
        f=out/Path(path).name;f.write_bytes(x.content);row.update(bytes=len(x.content),sha256=hashlib.sha256(x.content).hexdigest())
    items.append(row)
(out/'fetch.json').write_text(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=commit,items=items,scope='Reference commit differs from installed runtime build; not proof of installed implementation.'),indent=2)+'\n')
print(json.dumps(items))
