"""Read-only preflight for private captures on the shared ComfyUI GPU."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parent/'comfy-authoring'

def queue_state():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=3) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError('ComfyUI returned an HTTP error; GPU queue could not be verified') from error
    except urllib.error.URLError as error:
        # Only an explicit refused connection establishes that no server is
        # listening. Timeouts and other network failures leave queue state unknown.
        reason=error.reason
        if isinstance(reason,ConnectionRefusedError) or getattr(reason,'errno',None) in (111,10061) or getattr(reason,'winerror',None)==10061:
            return None
        raise RuntimeError('ComfyUI queue is unreachable with unknown state') from error

def require_quiet_gpu(*,root=ROOT,fetch_queue=queue_state):
    reservation=Path(root)/'GPU-RESERVED'
    if not reservation.is_file():raise RuntimeError('Reserve the shared GPU before private GL tests or captures')
    reserved=reservation.read_bytes();lock=Path(root)/'GPU-LOCK.json';holder=None
    if lock.exists():
        holder=json.loads(lock.read_bytes())
        raise RuntimeError('Shared GPU is still held by '+str(holder.get('owner','unknown'))+
            '; even an expired lock needs its owner to release it')
    queue=fetch_queue()
    if queue is not None:
        if not isinstance(queue,dict) or not all(isinstance(queue.get(k),list) for k in ('queue_running','queue_pending')):
            raise RuntimeError('ComfyUI queue state is malformed; GPU preflight refused')
        if queue['queue_running'] or queue['queue_pending']:
            raise RuntimeError('ComfyUI has running or pending work; private GPU launch refused')
    # The reservation must remain present across the queue read. We never
    # delete, renew or seize another holder's lock from this observer.
    if not reservation.is_file() or reservation.read_bytes()!=reserved:
        raise RuntimeError('GPU reservation changed during preflight')
    return dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),
        reservation_sha256=hashlib.sha256(reserved).hexdigest(),
        active_holder=False,comfy_server_reachable=queue is not None,
        queue_running=0,queue_pending=0)
