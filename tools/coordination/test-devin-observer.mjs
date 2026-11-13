import test from 'node:test';
import assert from 'node:assert/strict';
import {authorize, owner, exposedTools} from './devin-observer-policy.mjs';

test('read-only catalog excludes mutations and workspace switches', () => {
  for (const name of ['hermes_lock_files','hermes_claim_task','hermes_connect_project','hermes_set_workspace','hermes_execute','hermes_complete_work']) {
    assert.equal(exposedTools.has(name),false);
    assert.throws(() => authorize(name,{}));
  }
  assert.deepEqual(authorize('hermes_get_workspace'),{});
});
test('mail and presence cannot impersonate another actor', () => {
  for (const name of ['hermes_get_inbox','hermes_wait_for_inbox','hermes_ack_message','hermes_update_presence','hermes_heartbeat']) {
    assert.throws(() => authorize(name,{owner:'codex-einhander'}));
  }
  assert.throws(() => authorize('hermes_send_message',{sender:'claude-einhander',recipients:['codex-einhander']}));
});
test('onboarding messages stay between intended project peers', () => {
  for (const recipients of [[],['someone-else'],['claude-einhander','someone-else']]) {
    assert.throws(() => authorize('hermes_send_message',{sender:owner,recipients}));
  }
  assert.deepEqual(authorize('hermes_send_message',{sender:owner,recipients:['claude-einhander']}),{sender:owner,recipients:['claude-einhander']});
});
test('wait and presence lifetimes are bounded; role remains observation', () => {
  assert.equal(authorize('hermes_wait_for_inbox',{owner,timeoutMs:999999}).timeoutMs,40000);
  const result=authorize('hermes_update_presence',{owner,status:'reviewing',role:'release operator',ttlSeconds:999999});
  assert.equal(result.ttlSeconds,900);
  assert.equal(result.role,'read-only synchronization and review');
  assert.throws(() => authorize('hermes_update_presence',{owner,status:'done'}));
});
test('invalid argument containers are rejected', () => {
  for (const input of [null,[],1,'x']) assert.throws(() => authorize('hermes_get_workspace',input));
});
