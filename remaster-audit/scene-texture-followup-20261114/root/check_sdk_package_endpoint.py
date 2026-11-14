from pathlib import Path
import datetime,json,psutil,requests
n=Path(__file__).resolve().parent;out=n/'sdk-package-endpoint';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
version='minecraft-rtx2-a00da12a-win64-release';name='rtx_remix_runtime'
locations=[f'https://{host}/{name}@{version}' for host in ['d4i3qtqj3r0z5.cloudfront.net','d1oqksizpb0e3d.cloudfront.net']]
rows=[]
for url in locations:
    x=requests.head(url,timeout=15,allow_redirects=True)
    rows.append(dict(url=url,method='HEAD',status=x.status_code,headers={k:v for k,v in x.headers.items() if k.lower() in ['content-length','content-type','last-modified','etag']},final_url=x.url))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source='Pinned official packman config and remix-sdk manifest in sdk-package-reference',requests=rows,
             package_body_downloaded=False,software_installed=False,runtime_started=False,gpu_executed=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(rows))
