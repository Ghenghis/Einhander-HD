// Reconcile coordinator-verified actual startup messages/checkpoints. No liveness inference.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { read, writeJson, normalizeSessionId } from '../../tools/coordination/claude-continuity-hook.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const file=path.join(root,'coordination/CLAUDE-SESSIONS-20261114.json');
const roster=await read(file,null);
const messages={'claude-einhander-s23':'msg_3cd56d0bd060dcd2','claude-einhander-s45':'msg_0ff886bb8bbc6e88','claude-einhander-s67':'msg_9ce4ae21306423ff'};
const confirmedCliIds={'claude-einhander-s23':'981b7d04-19b2-40aa-a1d4-7a90c912e441'}; // actual-model message msg_2a6d79edaf8535c8
for(const row of roster.sessions){
  if(!messages[row.owner])continue;
  const checkpointPath=path.join(root,row.checkpoint),bytes=await fs.readFile(checkpointPath);
  if(bytes.includes(0))throw Error('NUL checkpoint: '+row.owner);
  const checkpoint=JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/,''));
  if(checkpoint.owner!==row.owner)throw Error('Wrong checkpoint owner');
  const message=await read(path.join(root,'.hermes3d_orchestrator/inbox/codex-einhander-crash-check',messages[row.owner]+'.json'),null);
  if(message.sender!==row.owner||!message.body.includes(normalizeSessionId(checkpoint.session_id)))throw Error('Startup evidence/session mismatch');
  row.session_id=normalizeSessionId(checkpoint.session_id);
  row.native_session_id=checkpoint.session_id;
  if(checkpoint.cli_session_id||confirmedCliIds[row.owner])row.cli_session_id=checkpoint.cli_session_id||confirmedCliIds[row.owner];
  if(checkpoint.worktree)row.worktree=checkpoint.worktree;
  row.actual_ui_title=checkpoint.session_title;
  row.state='actual_model_startup_verified';
  row.startup_message_id=messages[row.owner];
  row.startup_utc=message.created_utc;
  row.task_ids=checkpoint.pending_task_ids;
  row.checkpoint_sha256=crypto.createHash('sha256').update(bytes).digest('hex');
  row.checkpoint_verified_utc=new Date().toISOString();
  row.first_outputs=checkpoint.latest_outputs;
}
roster.updated_utc=new Date().toISOString();
await writeJson(file,roster);
const saved=await fs.readFile(file);JSON.parse(saved.toString());
console.log(JSON.stringify({path:file,sha256:crypto.createHash('sha256').update(saved).digest('hex'),sessions:roster.sessions.map(s=>({owner:s.owner,session_id:s.session_id,cli_session_id:s.cli_session_id,state:s.state}))}));
