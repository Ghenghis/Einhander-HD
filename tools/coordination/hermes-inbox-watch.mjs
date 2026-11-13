// HermesProof inbox watcher for this Einhander workspace (shared by claude-einhander and codex-einhander).
//
// Stream mode (default): stays connected, prints ONE line per new message the moment it lands,
// and writes separate watcher health. It never claims the model is working.
//   node tools/coordination/hermes-inbox-watch.mjs --owner claude-einhander
// Once mode: block until at least one unread message exists (or --wait seconds pass), print, exit.
//   node tools/coordination/hermes-inbox-watch.mjs --owner codex-einhander --once --wait 110
//   exit 0 = message(s) printed, 2 = timed out with nothing new, 1 = error.
//
// Output lines (one per message):  MSG <id> from=<sender> type=<type> prio=<priority> subject="..." preview="..."
// Error lines start with WATCH_ERROR so a supervising monitor sees failures instead of silence.
// Stream mode also re-reads all unread mail every --reconcile seconds (default 90): the long-poll cursor is
// created_utc only, and a message stamped with the cursor's own instant would otherwise wait for a reconnect.
//
// Watcher health is not model delivery. A host that runs this under a bounded task (Claude Code's Monitor
// is capped at 30 minutes) must re-arm it from a real model turn.
import { connect } from './hermes-client.mjs';
import { createEmitter, emitUnread, oneLine, streamStep } from './hermes-inbox-stream.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import { workspaceRoot } from './workspace-runtime.mjs';

const args = process.argv.slice(2);
const opt = (name, fallback) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
const owner = opt('--owner', '');
const once = args.includes('--once');
const waitSeconds = Number(opt('--wait', '110'));
const reconcileSeconds = Number(opt('--reconcile', '90'));
const presenceNote = opt('--note', 'listening on HermesProof inbox (auto-notify watcher)');
if (!/^[a-z][a-z0-9-]{1,63}$/.test(owner)) { console.log('WATCH_ERROR usage: --owner <agent-id>'); process.exit(1); }

const out = createEmitter();
const emit = out.emit;

async function heartbeat(session, status) {
  const directory=path.join(workspaceRoot,'.hermes3d_orchestrator/inbox-watch');
  await fs.mkdir(directory,{recursive:true});
  const target=path.join(directory,owner+'.json'),temporary=target+'.'+process.pid+'.tmp';
  // A watcher killed from outside (e.g. a host task deadline) cannot write a final status, so every
  // heartbeat carries its own expiry: past stale_after_utc the file proves nothing, whatever status says.
  // Heartbeats come at least every 45 s (one long-poll bound), so 120 s leaves room for one slow call.
  const now=Date.now();
  await fs.writeFile(temporary,JSON.stringify({owner,pid:process.pid,status,note:presenceNote,
    updated_utc:new Date(now).toISOString(),stale_after_utc:new Date(now+120000).toISOString(),
    last_message_utc:out.newest||null,watcher_only:true,
    proves_model_activity:false})+'\n');
  await fs.rename(temporary,target);
}

async function runOnce(session) {
  const deadline = Date.now() + waitSeconds * 1000;
  let count = await emitUnread(session, owner, out);
  while (!count && Date.now() < deadline) {
    // hermes-client.mjs aborts any tool call after 45 s, so each long-poll stays under that.
    const timeoutMs = Math.min(40000, Math.max(1000, deadline - Date.now()));
    const r = await session.call('hermes_wait_for_inbox', { owner, includeAcked: false, timeoutMs, pollMs: 300 });
    for (const m of r.messages || []) if (emit(m)) count++;
  }
  return count ? 0 : 2;
}

async function runStream(session) {
  await heartbeat(session, 'connected');
  await emitUnread(session, owner, out);
  let lastReconcile = Date.now();
  for (;;) {
    let reconciled = false;
    await streamStep(session, owner, out, () => {
      reconciled = Date.now() - lastReconcile >= reconcileSeconds * 1000;
      return reconciled;
    });
    if (reconciled) lastReconcile = Date.now();
    await heartbeat(session, 'connected');
  }
}

let failures = 0;
for (;;) {
  let session;
  try {
    session = await connect();
    failures = 0;
    if (once) { const code = await runOnce(session); await session.close(); process.exit(code); }
    await runStream(session);
  } catch (error) {
    failures++;
    console.log(`WATCH_ERROR ${oneLine(error?.message || error, 300)}`);
    await heartbeat(session,'reconnecting').catch(()=>{});
    if (once) { await session?.close().catch(() => {}); process.exit(1); }
    await new Promise(res => setTimeout(res, Math.min(30000, 2000 * failures)));
  } finally {
    await session?.close().catch(() => {});
  }
}
