"""Read-only inspection of descendants attributable to preserved monitor identities.

No process is stopped. Command lines are hashed, not dumped. No environment reads.
"""
from pathlib import Path
import collections
import datetime as dt
import hashlib
import json
import psutil

ROOT = Path('C:/github/Einhander')
HERE = Path(__file__).resolve().parent
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([11])
out = HERE / 'monitor-orphan-inspection-r1'
out.mkdir(exist_ok=False)
health = json.loads((ROOT / '.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json').read_bytes())
current = health['watcher_pid']
known = {}
for path in sorted(HERE.glob('monitor-renewal-*/result.json')):
    raw = path.read_bytes()
    row = json.loads(raw)
    if row.get('pid') and row.get('creation_unix'):
        known[(row['pid'], row['creation_unix'])] = dict(pid=row['pid'], creation_unix=row['creation_unix'],
            receipt=str(path.relative_to(ROOT)), receipt_sha256=hashlib.sha256(raw).hexdigest())
snapshot = {}
for proc in psutil.process_iter(['pid', 'ppid', 'name', 'create_time', 'memory_info']):
    try:
        item = proc.info
        snapshot[item['pid']] = dict(pid=item['pid'], parent_pid=item['ppid'], name=item['name'],
            creation_unix=item['create_time'], rss_bytes=item['memory_info'].rss)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
protected = {current, me.pid}
changed = True
while changed:
    added = {pid for pid, row in snapshot.items() if row['parent_pid'] in protected}
    changed = bool(added - protected)
    protected |= added
rows = []
for (pid, created), old in known.items():
    live = snapshot.get(pid)
    old['same_identity_live'] = bool(live and abs(live['creation_unix'] - created) < .001)
    old['current_monitor'] = pid == current and old['same_identity_live']
    old['direct_candidates'] = []
    if not old['same_identity_live']:
        for child_pid, child in snapshot.items():
            # Only a child born at this monitor's startup can be attributed here.
            if (child['parent_pid'] != pid or child_pid in protected
                    or not created <= child['creation_unix'] <= created + 30
                    or child['name'].lower() != 'node.exe'):
                continue
            try:
                proc = psutil.Process(child_pid)
                if abs(proc.create_time() - child['creation_unix']) >= .001:
                    continue
                command = proc.cmdline()
                expected = str(ROOT / 'tools/coordination/hermes-workspace.mjs').lower()
                exact = len(command) == 2 and command[1].lower().replace('/', '\\') == expected.replace('/', '\\')
                old['direct_candidates'].append(dict(**child, command_sha256=hashlib.sha256(
                    json.dumps(command, ensure_ascii=True).encode()).hexdigest(), exact_project_mcp_launcher=exact,
                    descendants=[r for r in snapshot.values() if r['parent_pid'] == child_pid]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    rows.append(old)
receipt = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), read_only=True,
    processes_stopped=0, process_total=len(snapshot), counts=dict(collections.Counter(r['name'] for r in snapshot.values())),
    current_monitor=current, current_monitor_live=current in snapshot, protected_ids=sorted(protected),
    monitors=rows, command_environments_read=False, gpu_run=False, game_run=False)
(out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(path=str(out / 'result.json'), total=len(snapshot), known_monitors=len(rows),
    candidate_ids=[c['pid'] for r in rows for c in r['direct_candidates']], processes_stopped=0,
    current_monitor=current, current_monitor_live=current in snapshot)))
