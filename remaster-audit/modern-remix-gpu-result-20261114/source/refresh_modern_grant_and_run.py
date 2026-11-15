"""Explicitly return unused rev5, then freshly grant and immediately run.

Never prints fenced tokens. An existing job or a changed owner fails closed.
"""
from pathlib import Path
import datetime, json, subprocess, sys

r = Path('C:/github/Einhander')
n = Path(__file__).resolve().parent
out = n / 'modern-gpu-window-refresh-r1'
out.mkdir(exist_ok=False)
statefile = r / '.hermes3d_orchestrator/shared-gpu/state.json'
state = json.loads(statefile.read_text(encoding='utf-8-sig'))
grant = state['grant']
assert state['revision'] == 5 and grant['owner'] == 'claude-einhander'
assert grant['jobs'] == [], 'Never release another live job'
assert not (n / 'modern-granted-execution-r1').exists()
assert all(not (r/'remaster-audit/comfy-authoring'/name).exists()
           for name in ['GPU-RESERVED', 'GPU-LOCK', 'CPU-QUIET'])
private = out/'release.private'
private.write_text(json.dumps(dict(token=grant['token'], no_gpu_jobs=True,
    evidence='Unused rev5 expired during context recovery. No probe execution directory, no registered jobs, no resource markers. Explicit holder release; no expiry takeover.')), encoding='utf-8')
run = subprocess.run(['node', str(r/'tools/coordination/shared-gpu.mjs'),
    'release', '--owner', 'claude-einhander', '--file', str(private), '--no-flush'],
    cwd=r, capture_output=True, text=True, timeout=8, creationflags=0x08004000)
assert run.returncode == 0, run.stderr
release, _ = json.JSONDecoder().raw_decode(run.stdout.lstrip())
assert release['ok'] and release['grant'] is None
receipt = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    released_revision=release['event']['revision'], release_event=release['event']['id'],
    gpu_started=False, token_omitted=True)
(out/'release-result.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
print(json.dumps(receipt), flush=True)
# Run the reviewed request/grant recipes with fresh immutable output directories.
for file, old, new in [
    ('request_modern_gpu_window.py', 'modern-gpu-request-r1', 'modern-gpu-request-r2'),
    ('grant_modern_gpu_window.py', 'modern-gpu-grant-r1', 'modern-gpu-grant-r2')]:
    source = (n/file).read_text(encoding='utf-8')
    assert source.count(old) == 1
    recipe = out/file
    recipe.write_text(source.replace(old, new).replace('n=Path(__file__).resolve().parent',
        'n=Path('+repr(str(n))+')'), encoding='utf-8')
    run = subprocess.run([sys.executable, '-X', 'utf8', str(recipe)], cwd=r,
        timeout=20, creationflags=0x08004000)
    assert run.returncode == 0, (file, run.returncode)
run = subprocess.run([sys.executable, '-X', 'utf8', str(n/'run_granted_modern_probe.py')],
    cwd=r, timeout=110, creationflags=0x08004000)
# The reviewed inner wrapper owns the complete cleanup path. Never kill its child here.
(out/'result.json').write_text(json.dumps(dict(
    ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    wrapper_exit=run.returncode, broker_release_not_automatic=True), indent=2)+'\n', encoding='utf-8')
raise SystemExit(run.returncode)
