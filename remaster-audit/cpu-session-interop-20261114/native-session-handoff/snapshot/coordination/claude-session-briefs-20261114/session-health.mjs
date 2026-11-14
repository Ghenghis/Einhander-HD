// Bounded metadata/inbox monitor. It never claims model activity or restarts a session.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { connect } from '../../tools/coordination/hermes-client.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const rosterFile = path.join(root, 'coordination/CLAUDE-SESSIONS-20261114.json');
const healthFile = path.join(root, '.hermes3d_orchestrator/session-watch/claude-sessions-20261114.json');
const args = process.argv.slice(2);
const watchIndex = args.indexOf('--watch');
const durationSeconds = watchIndex < 0 ? 0 : Number(args[watchIndex + 1]);
if (!Number.isFinite(durationSeconds) || durationSeconds < 0 || durationSeconds > 1800) throw new Error('Watch bound must be 0..1800 seconds');
const normalizeId = value => String(value || '').replace(/^local_/, '');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const previous = new Map();
const start = Date.now();
const stopAt = start + durationSeconds * 1000;
let client;
let observations = 0;

async function snapshot() {
  const now = Date.now();
  const bytes = await fs.readFile(rosterFile);
  const roster = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/, ''));
  const live = await client.call('hermes_live_status', { includeAgents: false, includePresence: true, includeEvents: false, includeProfiles: false, includeProviderStats: false });
  const rows = [];
  for (const session of roster.sessions) {
    const presence = (live.presence || []).find(p => p.owner === session.owner);
    const row = { owner: session.owner, session_id: session.session_id, roster_state: session.state,
      presence_updated_utc: presence?.updated_utc || null, presence_stale: presence?.is_stale ?? true,
      model_liveness: 'not established by this monitor', attention: [] };
    try {
      const checkpointBytes = await fs.readFile(path.join(root, session.checkpoint));
      if (checkpointBytes.includes(0)) throw new Error('NUL byte in checkpoint');
      const checkpoint = JSON.parse(checkpointBytes.toString('utf8').replace(/^\uFEFF/, ''));
      const checkpointTime = Date.parse(checkpoint.checkpoint_utc || '');
      row.checkpoint_sha256 = sha(checkpointBytes);
      row.checkpoint_utc = checkpoint.checkpoint_utc || null;
      row.checkpoint_age_seconds = Number.isFinite(checkpointTime) ? Math.round((now - checkpointTime) / 1000) : null;
      row.phase = checkpoint.phase;
      row.pending_task_ids = checkpoint.pending_task_ids;
      row.next_action = checkpoint.next_action;
      if (!Number.isFinite(checkpointTime)) row.attention.push('invalid checkpoint time');
      else if (checkpointTime > now + 120000) row.attention.push('checkpoint time in future');
      else if (now - checkpointTime > 1200000) row.attention.push('checkpoint older than20minutes; inspect actual model before assuming failure');
      const allowedIds = [session.session_id, session.cli_session_id].filter(Boolean).map(normalizeId);
      if (checkpoint.session_id && allowedIds.length && !allowedIds.includes(normalizeId(checkpoint.session_id))) row.attention.push('checkpoint session identity mismatch');
    } catch (error) {
      row.checkpoint_error = String(error?.message || error);
      const launchTime = Date.parse(session.startup_utc || roster.updated_utc || '');
      if (session.session_id && Number.isFinite(launchTime) && now - launchTime > 300000) row.attention.push('checkpoint unavailable after startup grace; inspect native session');
    }
    row.status = row.attention.length ? 'needs_attention' : (row.checkpoint_sha256 ? 'checkpoint_available' : 'awaiting_checkpoint');
    const signature = row.attention.join('|');
    if (signature && signature !== previous.get(session.owner)) {
      await client.call('hermes_send_message', { sender: 'einhander-session-watch', recipients: ['codex-einhander-crash-check', 'codex-einhander'],
        subject: `Session recovery check: ${session.owner}`, priority: 'high', requiresAck: true,
        body: JSON.stringify({ owner: row.owner, session_id: row.session_id, attention: row.attention,
          checkpoint: session.checkpoint, note: 'Metadata alert only. Not proof of a crash. Inspect actual native model/session and preserve failed evidence before recovery.' }) });
    }
    previous.set(session.owner, signature);
    rows.push(row);
  }
  const receipt = { observed_utc: new Date(now).toISOString(), watcher_pid: process.pid,
    watcher_only: true, proves_model_activity: false, observations: ++observations,
    bound_end_utc: durationSeconds ? new Date(stopAt).toISOString() : new Date(now).toISOString(),
    roster_sha256: sha(bytes), sessions: rows };
  await fs.mkdir(path.dirname(healthFile), { recursive: true });
  const temporary = healthFile + '.' + process.pid + '.tmp';
  const file = await fs.open(temporary, 'w');
  try { await file.writeFile(JSON.stringify(receipt, null, 2) + '\n'); await file.sync(); } finally { await file.close(); }
  await fs.rename(temporary, healthFile);
  console.log(JSON.stringify({ observed_utc: receipt.observed_utc, pid: process.pid, bound_end_utc: receipt.bound_end_utc,
    watcher_only: true, sessions: rows.map(r => ({ owner: r.owner, status: r.status, attention: r.attention })) }));
}

try {
  client = await connect();
  do {
    await snapshot();
    if (!durationSeconds || Date.now() >= stopAt) break;
    await new Promise(resolve => setTimeout(resolve, Math.min(30000, stopAt - Date.now())));
  } while (Date.now() < stopAt);
} finally {
  await client?.close();
}
