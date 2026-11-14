from pathlib import Path
import datetime,hashlib,io,json,psutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
roots=[r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip',n,r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v66-reviewed-scene-r3']
extensions={'.json','.jsonl','.md','.py','.c','.cpp','.h','.inc','.txt','.log','.frag','.vert'}
rows=[];checked=0
for root in roots:
    for f in root.rglob('*'):
        if not f.is_file() or f.suffix.lower() not in extensions or f.stat().st_size>8*1024*1024:continue
        data=f.read_bytes();checked+=1;count=data.count(b'\0')
        if count:rows.append(dict(path=str(f),bytes=len(data),null_bytes=count,all_zero=count==len(data),sha256=hashlib.sha256(data).hexdigest(),mtime_utc=datetime.datetime.fromtimestamp(f.stat().st_mtime,datetime.timezone.utc).isoformat()))
expected={}
for name in ['gpu-integration-20261114','gpu-shader-followup-20261114']:
    doc=json.loads((w/'remaster-audit'/name/'SHA256.json').read_text());expected.update({f'remaster-audit/{name}/{k}':v for k,v in doc['files'].items()})
for line in (w/'remaster-audit/cpu-hour-integration-20261114/SHA256SUMS.txt').read_text().splitlines():
    h,p=line.split('  ',1);expected['remaster-audit/cpu-hour-integration-20261114/'+p]=h
raw=subprocess.check_output(['git','cat-file','--batch'],cwd=w,input=''.join('HEAD:'+f+'\n' for f in expected).encode());stream=io.BytesIO(raw);errors=[]
for f,h in expected.items():
    header=stream.readline().decode().split()
    if len(header)!=3 or header[1]!='blob':errors.append(dict(path=f,error='missing git blob'));continue
    data=stream.read(int(header[2]));assert stream.read(1)==b'\n'
    if hashlib.sha256(data).hexdigest()!=h:errors.append(dict(path=f,error='committed hash mismatch'))
    for label,root in [('delivery',w),('root',r)]:
        if not (root/f).exists() or hashlib.sha256((root/f).read_bytes()).hexdigest()!=h:errors.append(dict(path=f,error=label+' working file mismatch'))
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),boot_utc=datetime.datetime.fromtimestamp(psutil.boot_time(),datetime.timezone.utc).isoformat(),text_files_checked=checked,
             nul_files=rows,prior_committed_files_verified=len(expected),prior_packet_errors=errors,gpu_executed=False,files_repaired=False,
             scope='Bounded known recent folders and three published packet manifests; not a full drive/filesystem check.')
(n/'post-restart-audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(text_files_checked=checked,nul_files=len(rows),all_zero=sum(x['all_zero'] for x in rows),prior_hashes=len(expected),prior_packet_errors=errors,affected=[x['path'] for x in rows][:18])))
