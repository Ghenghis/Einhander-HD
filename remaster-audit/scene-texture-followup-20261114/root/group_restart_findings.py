from pathlib import Path
import collections,datetime,hashlib,json,psutil
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);p.cpu_affinity(p.cpu_affinity()[-1:])
audit=json.loads((n/'post-restart-audit.json').read_text())
groups=collections.Counter();rows=[]
for item in audit['nul_files']:
    f=Path(item['path']);data=f.read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['sha256'],f
    rel=f.relative_to(r).as_posix();prefix=rel.split('/frozen/')[0]+'/frozen/'+rel.split('/frozen/')[1].split('/')[0] if '/frozen/' in rel else str(f.parent)
    groups[prefix]+=1;rows.append(dict(path=rel,bytes=len(data),sha256=item['sha256'],still_all_zero=bool(data) and not any(data)))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_audit_sha256=hashlib.sha256((n/'post-restart-audit.json').read_bytes()).hexdigest(),groups=dict(groups),all_zero_still=sum(x['still_all_zero'] for x in rows),files=rows,files_repaired=False,scope=audit['scope'])
(n/'post-restart-grouped.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))
