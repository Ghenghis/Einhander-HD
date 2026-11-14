"""Main coordinator commits one fresh project grant after actual quiet checks."""
from pathlib import Path
import datetime,hashlib,json,psutil,re,subprocess
r=Path('C:/github/Einhander');n=Path('C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114');out=n/'modern-gpu-grant-r2';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
statefile=r/'.hermes3d_orchestrator/shared-gpu/state.json';state=json.loads(statefile.read_text(encoding='utf-8-sig'))
assert state['grant'] is None and any(x['owner']=='claude-einhander' for x in state['requests'])
assert all(not (r/'remaster-audit/comfy-authoring'/name).exists() for name in ['GPU-RESERVED','GPU-LOCK','CPU-QUIET'])
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3);assert cpu<60 and free>=16,(cpu,free)
heavy=[]
for p in psutil.process_iter(['pid','name','cmdline','create_time']):
    if p.pid==me.pid:continue
    name=(p.info['name'] or '').lower();command=' '.join(p.info['cmdline'] or [])
    candidate=name in ['clang.exe','clang++.exe','lld.exe','sdk-modern-gl.exe','einhander_recompiled.exe'] or name in ['python.exe','pythonw.exe'] and re.search(r'j[0-9]+_|s45_|s6_fx|o_city_rebuild|window_ramp_rebuild|build_private|verify_v6|verify_v67',command,re.I)
    if not candidate:continue
    try:
        cwd=Path(p.cwd()).resolve()
        if cwd.is_relative_to(r.resolve()):heavy.append(dict(pid=p.pid,name=name,creation_unix=p.info['create_time']))
    except psutil.NoSuchProcess:continue
    except psutil.AccessDenied:raise RuntimeError('Cannot verify candidate process identity: '+str(p.pid))
assert not heavy,heavy
evidence='Main codex-einhander is a registered coordinator. Actual user shared-protocol authorization; Pizza explicit release92302852 at14:56:05, rev3; legacy marker91c25 archived at16:17:32. All art returns independently reported d980a185; fresh owned-heavy process inventory empty and CPU gate passes. Root-managed reviewed private GL probe only; child45s deadline, no game or driver/power change.'
private=out/'grant.private';private.write_text(json.dumps(dict(target='claude-einhander',seconds=240,evidence=evidence)),encoding='utf-8')
run=subprocess.run(['node',str(r/'tools/coordination/shared-gpu.mjs'),'grant','--owner','codex-einhander','--file',str(private),'--no-flush'],cwd=r,capture_output=True,text=True,timeout=8,creationflags=0x08004000)
assert run.returncode==0,run.stderr
result,_=json.JSONDecoder().raw_decode(run.stdout.lstrip());assert result['ok'] and result['grant']['owner']=='claude-einhander'
after=json.loads(statefile.read_text(encoding='utf-8-sig'));assert after['grant']['token']==result['grant']['token']
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),actor='codex-einhander',event_id=result['event']['id'],revision=after['revision'],owner=after['grant']['owner'],expires_utc=after['grant']['expires_utc'],owned_heavy_processes=heavy,cpu_percent=cpu,free_gib=free,token_omitted=True,grant_committed=True,gpu_started=False,outbox_pending=True,child_deadline_seconds=45)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
