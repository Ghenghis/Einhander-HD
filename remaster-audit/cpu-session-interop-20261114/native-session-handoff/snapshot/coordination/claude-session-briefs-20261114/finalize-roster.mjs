import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {read,writeJson} from '../../tools/coordination/claude-continuity-hook.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const file=path.join(root,'coordination/CLAUDE-SESSIONS-20261114.json');
const roster=await read(file,null);
const primary=roster.sessions.find(row=>row.owner==='claude-einhander');
primary.cli_session_id='11357b05-21ce-4470-8da8-e1597e772a7f';
primary.native_session_id='local_'+primary.session_id;
primary.identity_evidence={message_id:'msg_3b5f8bf61de9e710',reported_utc:'2026-11-14T13:44:34.137Z',
  source:'Actual original Claude model read its own CLAUDE_CODE_SESSION_ID and CLAUDE_CODE_HOST_SESSION_ID',
  native_metadata_crosscheck:'msg_f60e9c857847663f',cwd:'C:/github',pid_reported:13920,
  live_hook_reload:'Not independently requalified for this pre-existing parent-root session'};
roster.monitoring_handoff={owner:'codex-einhander',accepted_message_id:'msg_7b8737f92c0ecbba',
  accepted_utc:'2026-11-14T13:42:48.980Z',watcher_pid:28164,
  current_bound_end_utc:'2026-11-14T14:07:14.706Z',
  responsibility:'Main model accepts reading worker inboxes/checkpoints and rearming or replacing the bounded monitor before its end. Actual model turns required; watcher does not prove model operation.'};
roster.updated_utc=new Date().toISOString();
await writeJson(file,roster);
console.log(JSON.stringify({updated:file,primary_identity:primary.identity_evidence,monitoring_handoff:roster.monitoring_handoff}));
