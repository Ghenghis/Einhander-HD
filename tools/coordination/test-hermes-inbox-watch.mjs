import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createEmitter, emitUnread, streamStep } from './hermes-inbox-stream.mjs';

// Fake HermesProof session. wait_for_inbox applies afterCreatedUtc strictly (created_utc > cursor),
// which is the behaviour that can pass over a second message stamped with the cursor's own instant.
function fakeSession(messages) {
  const calls = [];
  return {
    calls,
    async call(tool, a) {
      calls.push(tool);
      const unread = messages.filter(m => !m.acked);
      if (tool === 'hermes_get_inbox') return { messages: unread };
      if (tool === 'hermes_wait_for_inbox') return { messages: a.afterCreatedUtc ? unread.filter(m => m.created_utc > a.afterCreatedUtc) : unread };
      throw new Error(`unexpected tool ${tool}`);
    },
  };
}
const msg = (id, created_utc) => ({ id, created_utc, sender: 'codex-einhander', type: 'note', priority: 'high', subject: id, body: 'b' });
const T = '2026-11-13T16:00:00.000Z';

test('same-timestamp message missed by the cursor is delivered by reconciliation, once', async () => {
  const printed = [];
  const out = createEmitter(line => printed.push(line.split(' ')[1]));
  const box = [msg('m1', T)];
  const session = fakeSession(box);
  await emitUnread(session, 'claude-einhander', out);
  assert.deepEqual(printed, ['m1']);
  box.push(msg('m2', T)); // lands after m1 was read, with the identical created_utc
  assert.equal(await streamStep(session, 'claude-einhander', out, false), 0, 'cursor alone passes over m2');
  assert.equal(await streamStep(session, 'claude-einhander', out, true), 1, 'reconciliation delivers m2');
  assert.equal(await streamStep(session, 'claude-einhander', out, true), 0, 'nothing is printed twice');
  assert.deepEqual(printed, ['m1', 'm2']);
});

test('reconciliation never re-prints acknowledged or already printed mail', async () => {
  const printed = [];
  const out = createEmitter(line => printed.push(line.split(' ')[1]));
  const box = [msg('a', T), msg('b', '2026-11-13T16:00:01.000Z')];
  const session = fakeSession(box);
  await emitUnread(session, 'claude-einhander', out);
  box[0].acked = true;
  box.push(msg('c', '2026-11-13T16:00:02.000Z'));
  assert.equal(await streamStep(session, 'claude-einhander', out, true), 1);
  assert.deepEqual(printed, ['a', 'b', 'c']);
  assert.equal(out.newest, '2026-11-13T16:00:02.000Z');
});

test('reconciliation adds one inbox read only when due', async () => {
  const session = fakeSession([]);
  const out = createEmitter(() => {});
  await streamStep(session, 'claude-einhander', out, false);
  await streamStep(session, 'claude-einhander', out, true);
  assert.deepEqual(session.calls, ['hermes_wait_for_inbox', 'hermes_wait_for_inbox', 'hermes_get_inbox']);
});

test('a deadline crossed during a long poll reconciles in that same step', async () => {
  let now = 80;
  const out = createEmitter(() => {}), calls = [];
  const session = { async call(tool) {
    calls.push(tool);
    if (tool === 'hermes_wait_for_inbox') { now = 120; return { messages: [] }; }
    return { messages: [msg('at-boundary', T)] };
  }};
  assert.equal(await streamStep(session, 'claude-einhander', out, () => now >= 90), 1);
  assert.deepEqual(calls, ['hermes_wait_for_inbox', 'hermes_get_inbox']);
});

test('entry script rejects a bad owner with a WATCH_ERROR line and exit 1', async () => {
  const script = path.join(path.dirname(fileURLToPath(import.meta.url)), 'hermes-inbox-watch.mjs');
  const child = spawn(process.execPath, [script, '--owner', 'Bad Owner'], { stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '';
  child.stdout.on('data', d => { stdout += d; });
  const code = await new Promise(res => child.on('close', res));
  assert.equal(code, 1);
  assert.match(stdout, /^WATCH_ERROR usage/);
});
