from pathlib import Path
import datetime,hashlib,io,json,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/cpu-hour-integration-20261114'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
report=w/'docs/media/gallery/cpu-hour-documentation-verification-results.json'
shutil.copy2(report,p/'root/prestage-documentation-verification.json')
# Improve only this checkpoint's prose; preserve imported/frozen source bytes.
replacements={'November14':'November 14','user\'s3090Ti':"user's 3090 Ti",'The3060':'The 3060','authorizes3090':'authorizes 3090',
'all306':'all 306','replays6,185fixture':'replays 6,185 fixture','passes1,626enabled/6disabled':'passes 1,626 enabled / 6 disabled',
'seal,1024polygon':'seal, 1024 polygon','identifies136':'identifies 136','above8/255':'above 8/255','437/1,110':'437 / 1,110',
'RTX3090Ti':'RTX 3090 Ti','to12:44:30UTC':'to 12:44:30 UTC','05:44:30Phoenix':'05:44:30 Phoenix','permits the3060':'permits the 3060',
'all306 original':'all 306 original','6,185fixture':'6,185 fixture','off2, invalid-env2, combined33, levels-only32, RGB-only25, opaque-control25':'off 2, invalid-env 2, combined 33, levels-only 32, RGB-only 25, opaque-control 25',
"author's28/28":"author's 28/28",'and8/8':'and 8/8','rejected95–344ms':'rejected 95–344 ms','with155':'with 155','holds1024':'holds 1024','in663,552bytes':'in 663,552 bytes',
'age0/1':'age 0/1','depth3':'depth 3','all16':'all 16','finds1,699keys:1,135':'finds 1,699 keys: 1,135','and564':'and 564','captures,1,110keys':'captures, 1,110 keys',
'drawn;437(39%)':'drawn; 437 (39%)','opaque.569':'opaque. 569','footprints;136':'footprints; 136','of8/255,101':'of 8/255, 101','exceed32/255':'exceed 32/255',
'the101':'the 101','keys,59':'keys, 59','the136-key':'the 136-key','different installed5a7eec84':'different installed 5a7eec84','and404':'and 404',
'complete306-file':'complete 306-file','READY93a976':'READY 93a976'}
files=[p/'README.md']+[w/'docs'/x for x in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md']]
for f in files:
    text=f.read_text()
    if f.parent==w/'docs':head,tail=text.split('<details>',1)
    else:head,tail=text,''
    for a,b in replacements.items():head=head.replace(a,b)
    f.write_text(head+('<details>'+tail if tail else ''))
    if f.parent==w/'docs':shutil.copy2(f,r/'docs'/f.name)
# Include the actual final staging recipe, then hash all published bytes.
shutil.copy2(__file__,p/'root/stage_cpu_hour.py')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'))
paths=['.gitattributes','remaster-audit/cpu-hour-integration-20261114',*[str(f.relative_to(w)) for f in files[1:]]]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True)
expected={}
for name in ['gpu-integration-20261114','gpu-shader-followup-20261114']:
    d=json.loads((w/'remaster-audit'/name/'SHA256.json').read_text())
    expected.update({f'remaster-audit/{name}/{k}':v for k,v in d['files'].items()})
for line in (p/'SHA256SUMS.txt').read_text().splitlines():
    h,f=line.split('  ',1);expected['remaster-audit/cpu-hour-integration-20261114/'+f]=h
raw=subprocess.check_output(['git','cat-file','--batch'],cwd=w,input=''.join(':'+f+'\n' for f in expected).encode())
stream=io.BytesIO(raw)
for f,h in expected.items():
    header=stream.readline().decode().split();assert len(header)==3 and header[1]=='blob',(f,header)
    data=stream.read(int(header[2]));assert stream.read(1)==b'\n';assert hashlib.sha256(data).hexdigest()==h,f
assert stream.read()==b''
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True)
# Synchronize the explicit evidence copy without changing older evidence packets.
local=r/'remaster-audit/cpu-hour-integration-20261114'
for f in p.rglob('*'):
    if f.is_file():target=local/f.relative_to(p);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),staged_historical_and_new_hashes_verified=len(expected),
             new_manifest_files=sum(1 for x in (p/'SHA256SUMS.txt').read_text().splitlines() if x),gpu_executed=False)
(n/'cpu-hour-stage-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
