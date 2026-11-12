// Send / acknowledge HermesProof messages in this Einhander workspace from a shell.
//   node tools/coordination/hermes-say.mjs send --from claude-einhander --to codex-einhander [--type note] [--prio normal] --subject "..." (--body "..." | --body-file path)
//   node tools/coordination/hermes-say.mjs ack  --owner claude-einhander --id msg_x [--status acknowledged|done|dismissed] [--note "..."] [--reply "..." | --reply-file path]
// Prints one JSON line with the result. Use forward slashes in paths inside message text.
import fs from 'node:fs/promises';
import { connect } from './hermes-client.mjs';

const [command, ...rest] = process.argv.slice(2);
const opt = (name, fallback = '') => { const i = rest.indexOf(name); return i >= 0 && rest[i + 1] !== undefined ? rest[i + 1] : fallback; };
const text = async (inline, file) => (file ? await fs.readFile(file, 'utf8') : inline);

const session = await connect();
try {
  let result;
  if (command === 'send') {
    result = await session.call('hermes_send_message', {
      sender: opt('--from'), recipients: opt('--to').split(',').filter(Boolean), type: opt('--type', 'note'),
      priority: opt('--prio', 'normal'), subject: opt('--subject'), body: await text(opt('--body'), opt('--body-file')),
    });
    result = { ok: true, sent: (result.messages || []).map(m => m.id) };
  } else if (command === 'ack') {
    result = await session.call('hermes_ack_message', {
      owner: opt('--owner'), messageId: opt('--id'), status: opt('--status', 'acknowledged'), note: opt('--note'),
      notifySender: true, replyBody: await text(opt('--reply'), opt('--reply-file')),
    });
    result = { ok: true, acked: opt('--id'), status: result.status };
  } else throw new Error('Commands: send, ack');
  console.log(JSON.stringify(result));
} finally { await session.close(); }
