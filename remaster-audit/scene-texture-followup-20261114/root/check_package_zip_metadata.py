from pathlib import Path
import datetime,json,requests
n=Path(__file__).resolve().parent;out=n/'sdk-package-zip-metadata';out.mkdir(exist_ok=False)
rows=[]
for host in ['d4i3qtqj3r0z5.cloudfront.net','d1oqksizpb0e3d.cloudfront.net']:
    url=f'https://{host}/rtx_remix_runtime@minecraft-rtx2-a00da12a-win64-release.zip'
    x=requests.head(url,timeout=15,allow_redirects=True)
    rows.append(dict(url=url,status=x.status_code,final_url=x.url,headers={k:v for k,v in x.headers.items() if k.lower() in ['content-length','content-type','last-modified','etag']}))
(out/'result.json').write_text(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),requests=rows,
    note='ZIP suffix tested separately from configured bare package location; inferred from official Packman bootstrap ZIP protocol. HEAD only; no body fetched or runtime installed.',gpu_executed=False),indent=2)+'\n')
print(json.dumps(rows))
