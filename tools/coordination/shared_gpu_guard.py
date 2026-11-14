"""Fail-closed launcher checks for the cooperative shared 3090 Ti broker.

This is coordination, not OS authorization. Live tokens stay out of receipts.
"""
from pathlib import Path
import datetime,json,os,subprocess,tempfile

ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'.hermes3d_orchestrator/shared-gpu/state.json'
OWNER='claude-einhander'
GPU='GPU-ff51fa52-74c8-c785-e000-53fe58844033'

def permission(state,token,now=None,new_starts=True):
    now=now or datetime.datetime.now(datetime.timezone.utc);errors=[]
    if not isinstance(state,dict):return dict(allowed=False,owner=None,errors=['Shared GPU state unavailable'])
    grant=state.get('grant');grant=grant if isinstance(grant,dict) else {}
    if state.get('schema')!='shared-gpu-v1' or state.get('gpu_uuid')!=GPU:errors.append('Wrong shared GPU schema/device')
    if grant.get('owner')!=OWNER:errors.append('Shared GPU is not granted to Einhander')
    if not token or token!=grant.get('token'):errors.append('Missing or stale shared GPU fence')
    if new_starts:
        denied=state.get('denied',[])
        if not isinstance(denied,list):errors.append('Invalid shared GPU deny list');denied=[]
        if grant.get('new_starts_allowed') is not True or OWNER in denied:errors.append('New shared GPU starts disallowed')
        expires=grant.get('expires_utc')
        if expires is not None:
            try:
                deadline=datetime.datetime.fromisoformat(expires.replace('Z','+00:00'))
                if deadline.tzinfo is None or deadline<=now:errors.append('Shared GPU grant expired')
            except (AttributeError,TypeError,ValueError):errors.append('Invalid shared GPU deadline')
    return dict(allowed=not errors,owner=grant.get('owner'),revision=state.get('revision'),errors=errors)

def current_permission(token,new_starts=True):
    try:
        if STATE.stat().st_size>2*1024*1024:raise ValueError('Shared state exceeds bounded size')
        return permission(json.loads(STATE.read_text(encoding='utf-8-sig')),token,new_starts=new_starts)
    except (OSError,ValueError,TypeError) as error:return dict(allowed=False,owner=None,errors=['Shared GPU state unavailable: '+type(error).__name__])

def broker_action(action,token,output,**fields):
    if action not in ('check','start'):raise ValueError('Launcher may only check or register an actual runner')
    script=ROOT/'tools/coordination/shared-gpu.mjs'
    if '--no-flush' not in script.read_text():raise RuntimeError('Broker lacks bounded no-flush launcher support')
    # Fenced arguments are transient and never belong in an evidence packet.
    # TemporaryDirectory removes them on success, refusal and timeout.
    with tempfile.TemporaryDirectory(prefix='einhander-gpu-') as temporary:
        private=Path(temporary)/'broker.private'
        with private.open('x',encoding='utf8') as stream:
            json.dump(dict(token=token,**fields),stream);stream.flush();os.fsync(stream.fileno())
        args=['node',str(script),action,'--owner',OWNER,'--file',str(private),'--no-flush']
        x=subprocess.run(args,capture_output=True,text=True,timeout=8,creationflags=0x08004000)
        if x.returncode:raise RuntimeError('Shared GPU '+action+' refused')
        first,_=json.JSONDecoder().raw_decode(x.stdout.lstrip())
    return dict(action=action,exit=x.returncode,allowed=first.get('allowed'),committed=first.get('ok'),event_id=first.get('event',{}).get('id'),scope='Live token/private broker arguments intentionally omitted')
