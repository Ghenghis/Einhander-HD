// Write claude-einhander's continuity checkpoint (schema from coordination/CLAUDE-HANDOFF.md) before a waiting turn.
// Usage: node tools/coordination/claude-checkpoint.mjs --session ID --monitor TASK_ID --wake ISO_UTC --tasks a,b --next "text"
//        node tools/coordination/claude-checkpoint.mjs --user-stop "reason"   (explicit user stop/pause only)
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { read,writeJson } from './claude-continuity-hook.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const args = process.argv.slice(2);
const opt = (n, d = '') => { const i = args.indexOf(n); return i >= 0 && args[i + 1] !== undefined ? args[i + 1] : d; };
const dir = path.join(root, '.hermes3d_orchestrator', 'continuity');
const file = path.join(dir, 'claude-einhander.json');
await fs.mkdir(dir, { recursive: true });
const previous = await read(file,{});
const state = {
  session_id: opt('--session', previous.session_id || ''),
  checkpoint_utc: new Date().toISOString(),
  phase: 'waiting',
  pending_task_ids: opt('--tasks', (previous.pending_task_ids || []).join(',')).split(',').map(s => s.trim()).filter(Boolean),
  next_action: opt('--next', previous.next_action || ''),
  continuation: {
    armed: true,
    monitor_task_id: opt('--monitor', previous.continuation?.monitor_task_id || ''),
    next_wakeup_utc: opt('--wake', previous.continuation?.next_wakeup_utc || ''),
  },
};
const stopReason = opt('--user-stop');
if (stopReason) state.user_stop = { requested: true, reason: stopReason };
await writeJson(file,state);
console.log(JSON.stringify({ ok: true, file: file.replace(/\\/g, '/'), ...state }));
