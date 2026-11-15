"""Commit a cooperative GPU request; it grants nothing and starts no graphics."""
from pathlib import Path
import datetime,json,subprocess,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;out=n/'modern-gpu-request-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
statefile=r/'.hermes3d_orchestrator/shared-gpu/state.json';before=json.loads(statefile.read_text(encoding='utf-8-sig'))
purpose='Root-managed Einhander private modern Remix GL qualification:320x180,32frames/10fps,45s child deadline,~70s cleanup; exactr4pins reviewed, no game or driver/power changes. GPU-ready receipt modern-gpu-ready-r1; old user hold explicitly reconciled after actual Pizza release.'
pending=[x for x in before.get('requests',[]) if x.get('owner')=='claude-einhander']
if pending:
    receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),request_already_pending=True,request_id=pending[0]['id'],gpu_run=False,grant_created=False)
else:
    file=out/'request.private';file.write_text(json.dumps(dict(purpose=purpose)),encoding='utf-8')
    run=subprocess.run(['node',str(r/'tools/coordination/shared-gpu.mjs'),'request','--owner','claude-einhander','--file',str(file),'--no-flush'],cwd=r,capture_output=True,text=True,timeout=8,creationflags=0x08004000)
    assert run.returncode==0,run.stderr
    result,_=json.JSONDecoder().raw_decode(run.stdout.lstrip());assert result['ok']
    receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),request_already_pending=False,event_id=result['event']['id'],revision=result['event']['revision'],gpu_run=False,grant_created=False,outbox_pending=True)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
