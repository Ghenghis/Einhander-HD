from pathlib import Path
import datetime,hashlib,io,json,psutil,re,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/scene-texture-followup-20261114'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
docs=['docs/'+f for f in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-SIGN-QUALITY-20261114.md','STAGE1-COMPLETION-STATUS.md']]
# Edit prose only: imported source, prior logs and immutable evidence retain their exact bytes.
replace={'one-hour3090Ti':'one-hour 3090 Ti','ended12:44:30UTC':'ended 12:44:30 UTC','05:44:30Phoenix':'05:44:30 Phoenix',"user's3090hour":"user's 3090 hour",'permitted3060':'permitted 3060','both3060 and3090':'both 3060 and 3090','the3060':'the 3060','the3090':'the 3090','after9.994s':'after 9.994 s','one320x180,10fps,120-frame':'one 320x180, 10 fps, 120-frame','selected3090Ti':'selected 3090 Ti','API0.6':'API 0.6','returns57600':'returns 57600','frames7,31,119':'frames 7,31,119','the45s':'the 45 s','Its1035282184-byte':'Its 1,035,282,184-byte','bounded32MiB/s':'bounded 32 MiB/s','`.190 ':'`. 190 ','verified: `':'verified: `','\n+':'\n','API0.16.1':'API 0.16.1','commit7d2ba9f':'commit 7d2ba9f','the288-byte':'the 288-byte','in0.268s':'in 0.268 s','exits0':'exits 0','mix0.6 and0.16':'mix 0.6 and 0.16','at12:49:22UTC':'at 12:49:22 UTC','05:49:22Phoenix':'05:49:22 Phoenix','of5066':'of 5,066','found90':'found 90','is10030':'is 10,030','Published990':'Published 990','published990':'published 990','all33':'all 33','all190':'all 190','Stage1':'Stage 1','November14':'November 14','passes2932':'passes 2,932','plus6':'plus 6','plus foreign':'plus foreign','passes14':'passes 14','and28':'and 28','rejects28':'rejects 28','at most1024':'at most 1,024','in770048bytes':'in 770,048 bytes','signed11-bit':'signed 11-bit','links155':'links 155','same configured':'same configured','confined to unpublished frozenv5':'confined to unpublished frozen v5','all990':'all 990','hour ended12':'hour ended 12','restarted12':'restarted 12','below-normal':'below normal','/6 disabled':' / 6 disabled','/6disabled':' / 6 disabled','checks,14':'checks, 14','CPU checks,14':'CPU checks, 14','checks plus6':'checks plus 6','rejects28':'rejects 28','CPUchecks':'CPU checks','passes2932 enabled/6 disabled':'passes 2,932 enabled / 6 disabled','checks plus foreign-thread':'checks plus foreign-thread','in0.268s':'in 0.268 s'}
for f in [p/'README.md']+[w/x for x in docs]:
    s=f.read_text()
    if f.parent==w/'docs' and '<details>' in s:head,tail=s.split('<details>',1);tail='<details>'+tail
    else:head,tail=s,''
    for a,b in replace.items():head=head.replace(a,b)
    for a,b in {'pass2932':'pass 2,932','All990':'All 990','old-runtime3090':'old-runtime 3090','frozenv5':'frozen v5','12:44:30UTC':'12:44:30 UTC','12:49:22UTC':'12:49:22 UTC','prove3090':'prove 3090','returned403':'returned 403','user\'s3090Ti':"user's 3090 Ti",'with14':'with 14','checks,14':'checks, 14','of28':'of 28'}.items():head=head.replace(a,b)
    for a,b in {'the3090Ti':'the RTX 3090 Ti','at least07:00Phoenix /14:00UTC':'at least 07:00 Phoenix / 14:00 UTC','all874':'all 874','verifies874':'verifies 874','verified874':'verified 874','replays7520':'replays 7,520','replays 7520':'replays 7,520','pins,7520':'pins, 7,520','pins and14':'pins and 14','and14':'and 14','recompiles/replays7520':'recompiles/replays 7,520','checks and14':'checks and 14','the author\'s52':"the author's 52",'implementation/20':'implementation / 20','remain6.6ms4096²/1.2ms2048²':'remain 6.6 ms at 4096² / 1.2 ms at 2048²','READY5f96':'READY 5f96','manifestbb270':'manifest bb270','files,263':'files, 263','pins and concrete':'pins and concrete','pins reviewed':'pins reviewed','pins,263':'pins, 263','rechecked: all874':'rechecked: all 874','S2–S7 selected candidates39':'S2–S7 selected candidates 39','have28':'have 28','pins,7520':'pins, 7,520','pass; no GPU':'pass; no GPU'}.items():head=head.replace(a,b)
    head=head.replace('190 non-PDB','190 non-PDB').replace('`.190','`. 190')
    f.write_text(head+tail)
    if f.parent==w/'docs':shutil.copy2(f,r/f.relative_to(w))
handoff=r/'coordination/Codex-HANDOFF.md';s=handoff.read_text().replace('The native Claude app reopened cold after reboot; actual model resume is pending at this checkpoint.','The native Claude app reopened cold after reboot; root resumed the original session and observed a real model recovery turn. Hermes message msg_23d0f67f0f8ea0ec confirms actual native continuation and source verification; fresh replay/new freeze remain pending.')
handoff.write_text(s);shutil.copy2(handoff,w/handoff.relative_to(r))
queue=r/'coordination/Codex-WORK-QUEUE.md';s=queue.read_text().replace('- [ ] Reconnect native Claude on C:, observe a real model turn and reconcile current inbox.','- [x] Reconnect native Claude on C: and observe a real model turn (msg_23d0f67f0f8ea0ec,13:10UTC).\n- [ ] Continue reconciling the historical duplicate inbox after the identity handoff; current recovery messages are read and acted on.')
queue.write_text(s);shutil.copy2(queue,w/queue.relative_to(r))
shutil.copy2(__file__,p/'root/stage_scene_delivery.py')
if (n/'deliver_scene_followup.py').exists():shutil.copy2(n/'deliver_scene_followup.py',p/'root/deliver_scene_followup.py')
(p/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.relative_to(p).as_posix()+'\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'))
paths=['.gitattributes','AGENTS.md','coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md','remaster-audit/stage1-completion-20261112/execution-state.json','remaster-audit/scene-texture-followup-20261114',*docs]
subprocess.run(['git','add','-f','--',*paths],cwd=w,check=True)
expected={}
for name in ['gpu-integration-20261114','gpu-shader-followup-20261114']:
    d=json.loads((w/'remaster-audit'/name/'SHA256.json').read_text());expected.update({f'remaster-audit/{name}/{f}':h for f,h in d['files'].items()})
for name in ['cpu-hour-integration-20261114','scene-texture-followup-20261114']:
    for line in (w/'remaster-audit'/name/'SHA256SUMS.txt').read_text().splitlines():
        h,f=line.split('  ',1);expected[f'remaster-audit/{name}/'+f]=h
raw=subprocess.check_output(['git','cat-file','--batch'],cwd=w,input=''.join(':'+f+'\n' for f in expected).encode());stream=io.BytesIO(raw)
for f,h in expected.items():
    hdr=stream.readline().decode().split();assert len(hdr)==3 and hdr[1]=='blob',(f,hdr)
    assert hashlib.sha256(stream.read(int(hdr[2]))).hexdigest()==h,f;assert stream.read(1)==b'\n'
assert stream.read()==b''
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True)
for f in p.rglob('*'):
    if f.is_file():dst=r/'remaster-audit/scene-texture-followup-20261114'/f.relative_to(p);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),historical_and_new_staged_pins_verified=len(expected),new_pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),gpu_executed=False)
(n/'scene-stage-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
