// Write claude-einhander's continuity checkpoint (schema from coordination/CLAUDE-HANDOFF.md) before a waiting turn.
// Usage: node tools/coordination/claude-checkpoint.mjs --session ID --monitor TASK_ID --wake ISO_UTC --tasks a,b --next "text"
//        node tools/coordination/claude-checkpoint.mjs --user-stop "reason"   (explicit user stop/pause only)
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { read,writeJson } from './claude-continuity-hook.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export function buildCheckpoint(previous, args, {now=Date.now(),maxWaitMinutes=30}={}) {
const opt = (n, d = '') => { const i = args.indexOf(n); return i >= 0 && args[i + 1] !== undefined ? args[i + 1] : d; };
const state = {
  session_id: opt('--session', previous.session_id || ''),
  checkpoint_utc: new Date(now).toISOString(),
  phase: 'waiting',
  pending_task_ids: opt('--tasks', (previous.pending_task_ids || []).join(',')).split(',').map(s => s.trim()).filter(Boolean),
  next_action: opt('--next', previous.next_action || ''),
  continuation: {
    armed: true,
    monitor_task_id: opt('--monitor'),
    next_wakeup_utc: opt('--wake'),
  },
};
const stopReason = opt('--user-stop');
if (args.includes('--user-stop')) {
  if (!stopReason.trim()) throw Error('An explicit user-stop reason is required');
  state.user_stop = { requested: true, reason: stopReason };
  state.phase = 'paused';state.continuation.armed = false;
  return state;
}
// A timestamp refresh is not a receiver renewal. Require explicit current
// task/wake references rather than inheriting an expired or completed task.
const wake=Date.parse(state.continuation.next_wakeup_utc);
if (!state.session_id.trim() || state.session_id.startsWith('--') ||
    !state.continuation.monitor_task_id.trim() || state.continuation.monitor_task_id.startsWith('--'))
  throw Error('Waiting checkpoint requires a session and explicit --monitor task ID from the actual armed receiver');
if (!Number.isFinite(wake) || wake<=now || wake-now>maxWaitMinutes*60000)
  throw Error(`Waiting checkpoint requires an explicit future --wake within ${maxWaitMinutes} minutes`);
if (!state.pending_task_ids.length || !state.next_action.trim())
  throw Error('Waiting checkpoint requires pending tasks and a concrete next action');
return state;
}

export async function saveCheckpoint(base,args,{now=Date.now()}={}) {
const dir=path.join(base,'.hermes3d_orchestrator','continuity');
const file=path.join(dir,'claude-einhander.json');
const previous=await read(file,{});
const config=await read(path.join(base,'coordination/work-continuity.json'),{});
const maxWaitMinutes=Number(config.max_wait_minutes)||30;
const state=buildCheckpoint(previous,args,{now,maxWaitMinutes});
await fs.mkdir(dir,{recursive:true});
await writeJson(file,state);
return {ok:true,file:file.replace(/\\/g,'/'),...state};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{console.log(JSON.stringify(await saveCheckpoint(root,process.argv.slice(2))));}
  catch(error){console.error(JSON.stringify({ok:false,error:error.message}));process.exitCode=1;}
}
