// Stream logic for hermes-inbox-watch.mjs, kept apart from the entry script so it can be tested
// against a fake session (test-hermes-inbox-watch.mjs).

export const oneLine = (s, n) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n).replace(/"/g, "'");

// Prints each message once, by id, and keeps the newest created_utc as the stream cursor.
export function createEmitter(print = console.log) {
  const seen = new Set();
  const out = { newest: '' };
  out.emit = (m) => {
    if (seen.has(m.id)) return false;
    seen.add(m.id);
    if (m.created_utc > out.newest) out.newest = m.created_utc;
    const lagMs = Date.now() - Date.parse(m.created_utc);
    print(`MSG ${m.id} from=${m.sender} type=${m.type} prio=${m.priority} sent=${m.created_utc} lag_ms=${lagMs} subject="${oneLine(m.subject, 160)}" preview="${oneLine(m.body, 220)}"`);
    return true;
  };
  return out;
}

// Prints every unread message not printed yet. Returns how many were new.
export async function emitUnread(session, owner, out) {
  const unread = await session.call('hermes_get_inbox', { owner, includeAcked: false });
  let count = 0;
  for (const m of unread.messages || []) if (out.emit(m)) count++;
  return count;
}

// One stream step: long-poll for messages after the cursor, then, when due, re-read all unread mail.
// The cursor is created_utc only, so a message stamped with the same instant as the cursor can be
// passed over by afterCreatedUtc. The unread re-read delivers it, and emit() never prints an id twice.
export async function streamStep(session, owner, out, reconcileDue) {
  const r = await session.call('hermes_wait_for_inbox', {
    owner, includeAcked: false, newOnly: Boolean(out.newest), afterCreatedUtc: out.newest, timeoutMs: 40000, pollMs: 300,
  });
  let count = 0;
  for (const m of r.messages || []) if (out.emit(m)) count++;
  // The poll can consume forty seconds. Evaluate a deadline after that wait,
  // so a poll crossing it does not defer recovery for another full poll.
  const due = typeof reconcileDue === 'function' ? reconcileDue() : reconcileDue;
  if (due) count += await emitUnread(session, owner, out);
  return count;
}
