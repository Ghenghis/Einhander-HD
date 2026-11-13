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
import { connect } from './hermes-client.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import { workspaceRoot } from './workspace-runtime.mjs';

const args = process.argv.slice(2);
const opt = (name, fallback) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : fallback; };
const owner = opt('--owner', '');
const once = args.includes('--once');
const waitSeconds = Number(opt('--wait', '110'));
const presenceNote = opt('--note', 'listening on HermesProof inbox (auto-notify watcher)');
if (!/^[a-z][a-z0-9-]{1,63}$/.test(owner)) { console.log('WATCH_ERROR usage: --owner <agent-id>'); process.exit(1); }

const oneLine = (s, n) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n).replace(/"/g, "'");
const seen = new Set();
let newest = '';
const emit = (m) => {
  if (seen.has(m.id)) return false;
  seen.add(m.id);
  if (m.created_utc > newest) newest = m.created_utc;
  const lagMs = Date.now() - Date.parse(m.created_utc);
  console.log(`MSG ${m.id} from=${m.sender} type=${m.type} prio=${m.priority} sent=${m.created_utc} lag_ms=${lagMs} subject="${oneLine(m.subject, 160)}" preview="${oneLine(m.body, 220)}"`);
  return true;
};

async function heartbeat(session, status) {
  const directory=path.join(workspaceRoot,'.hermes3d_orchestrator/inbox-watch');
  await fs.mkdir(directory,{recursive:true});
  const target=path.join(directory,owner+'.json'),temporary=target+'.'+process.pid+'.tmp';
  await fs.writeFile(temporary,JSON.stringify({owner,pid:process.pid,status,note:presenceNote,
    updated_utc:new Date().toISOString(),last_message_utc:newest||null,watcher_only:true,
    proves_model_activity:false})+'\n');
  await fs.rename(temporary,target);
}

async function runOnce(session) {
  const deadline = Date.now() + waitSeconds * 1000;
  const unread = await session.call('hermes_get_inbox', { owner, includeAcked: false });
  let count = 0;
  for (const m of unread.messages || []) if (emit(m)) count++;
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
  const unread = await session.call('hermes_get_inbox', { owner, includeAcked: false });
  for (const m of unread.messages || []) emit(m);
  for (;;) {
    const r = await session.call('hermes_wait_for_inbox', {
      owner, includeAcked: false, newOnly: Boolean(newest), afterCreatedUtc: newest, timeoutMs: 40000, pollMs: 300,
    });
    for (const m of r.messages || []) emit(m);
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
