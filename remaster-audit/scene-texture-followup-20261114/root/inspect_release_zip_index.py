"""Bounded HTTP-range ZIP directory read; no archive install or execution."""
from pathlib import Path
import datetime,json,requests,struct
n=Path(__file__).resolve().parent;out=n/'sdk-release-zip-index';out.mkdir(exist_ok=False)
release=json.loads((n/'sdk-package-protocol/result.json').read_text())['release']
asset=next(x for x in release['assets'] if x['name'].endswith('.jar'))
url=asset['browser_download_url'];size=asset['size'];requests_log=[]
def get_range(start,end,label):
    with requests.get(url,headers={'Range':f'bytes={start}-{end}'},timeout=20,stream=True) as x:
        row=dict(label=label,status=x.status_code,content_range=x.headers.get('Content-Range'),requested=[start,end]);requests_log.append(row)
        if x.status_code!=206:raise RuntimeError('Server did not honor bounded byte range')
        expected=end-start+1;assert expected<=4*1024*1024
        content=x.raw.read(expected+1);assert len(content)==expected
        (out/(label+'.bin')).write_bytes(content);row['received_bytes']=len(content);return content
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),asset=asset,requests=requests_log,software_installed=False,gpu_executed=False,archive_sha256_verified=False)
try:
    tail=get_range(size-65557,size-1,'zip-tail');pos=tail.rfind(b'PK\x05\x06');assert pos>=0
    _,disk,cdisk,entries_disk,entries,cdsize,cdoffset,comment=struct.unpack_from('<4s4H2IH',tail,pos)
    assert disk==cdisk==0 and entries==entries_disk and cdsize<=4*1024*1024 and cdoffset+cdsize<=size
    central=get_range(cdoffset,cdoffset+cdsize-1,'zip-directory');offset=0;rows=[]
    for _ in range(entries):
        h=struct.unpack_from('<4s6H3I5H2I',central,offset);assert h[0]==b'PK\x01\x02'
        filename=central[offset+46:offset+46+h[10]].decode('utf-8')
        rows.append(dict(name=filename,compression=h[4],crc32=f'{h[7]:08x}',compressed_bytes=h[8],bytes=h[9],local_offset=h[-1]))
        offset+=46+h[10]+h[11]+h[12]
    assert offset==len(central)
    (out/'all-entries.json').write_text(json.dumps(rows,indent=2)+'\n')
    receipt.update(passed=True,entries=entries,relevant=[v for v in rows if any(k in v['name'].lower() for k in ['d3d9.dll','remix_c.h','win64','version.txt'])])
except Exception as ex:receipt.update(passed=False,error=repr(ex))
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='asset'}))
