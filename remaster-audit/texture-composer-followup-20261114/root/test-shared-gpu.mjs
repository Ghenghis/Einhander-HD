import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {initialState,transition,withMutex,assertNoLivePids,deliverOutbox} from './shared-gpu.mjs';
const coordinator='codex-einhander-crash-check',pizza='claude-pizza-tycoon-hd',ein='claude-einhander';
const grant=(state,target=pizza,seconds)=>transition(state,'grant',coordinator,{target,evidence:'verified no owned jobs',seconds},1000).state;
test('exclusive grant, fencing, explicit release and transfer',()=>{
  let s=grant(initialState()),token=s.grant.token;
  assert.throws(()=>grant(s,ein),/explicitly release/);
  assert.throws(()=>transition(s,'check',ein,{token},1100),/not granted/);
  assert.throws(()=>transition(s,'check',pizza,{token:'old'},1100),/token mismatch/);
  assert.equal(transition(s,'check',pizza,{token},1100).result.allowed,true);
  assert.throws(()=>transition(s,'release',pizza,{token,evidence:'done'},1100),/no-GPU-jobs/);
  s=transition(s,'release',pizza,{token,no_gpu_jobs:true,evidence:'owned processes absent'},1100).state;
  s=grant(s,ein);assert.equal(s.grant.owner,ein);assert.notEqual(s.grant.token,token);
});
test('expiry disallows starts but never gives card to another project',()=>{
  const s=grant(initialState(),pizza,1);
  assert.throws(()=>transition(s,'check',pizza,{token:s.grant.token},2000),/expired/);
  assert.throws(()=>grant(s,ein),/explicitly release/);
});
test('deny preserves existing ownership and requires explicit allow',()=>{
  let s=grant(initialState());s=transition(s,'deny',coordinator,{target:pizza,evidence:'user changes priority'},1100).state;
  assert.equal(s.grant.owner,pizza);
  assert.throws(()=>transition(s,'check',pizza,{token:s.grant.token},1100),/disallowed/);
  assert.throws(()=>transition(s,'allow',pizza,{target:pizza,evidence:'self grant'},1100),/coordinator/);
  s=transition(s,'allow',coordinator,{target:pizza,evidence:'user allows'},1100).state;
  assert.equal(transition(s,'check',pizza,{token:s.grant.token},1100).result.allowed,true);
});
test('requests are durable and do not silently grant permission',()=>{
  let s=transition(initialState(),'request',ein,{purpose:'bounded gameplay capture'},1000).state;
  assert.equal(s.grant,null);assert.equal(s.requests.length,1);assert.equal(s.outbox.length,1);
  assert.throws(()=>transition(s,'request',ein,{purpose:'duplicate'},1100),/pending request/);
  assert.throws(()=>grant(s,'unknown'),/Unknown target/);
});
test('actual job identity required, old-token starts and owner self-grants rejected',()=>{
  const s=grant(initialState()),token=s.grant.token;
  assert.throws(()=>transition(s,'start',pizza,{token,pid:123},1100),/creation time/);
  assert.throws(()=>transition(s,'grant',pizza,{target:pizza,evidence:'self'},1100),/coordinator/);
  const n=transition(s,'start',pizza,{token,pid:123,command:'owned runner',created_utc:'2026-11-14T14:00:00Z'},1100).state;
  assert.equal(n.grant.jobs[0].pid,123);
});
test('concurrent cross-project mutations cannot both acquire mutex',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'ein-shared-gpu-test-'));
  let unlock;const gate=new Promise(resolve=>{unlock=resolve;});
  let entered;const ready=new Promise(resolve=>{entered=resolve;});
  const first=withMutex(dir,async()=>{entered();await gate;});await ready;
  await assert.rejects(withMutex(dir,async()=>{}),{code:'EEXIST'});unlock();await first;
  await withMutex(dir,async()=>{});await fs.rm(dir,{recursive:true});
});
test('release blocks a real live PID and fails closed on unknown access',()=>{
  assert.throws(()=>assertNoLivePids([{pid:process.pid}]),/still exists/);
  assert.throws(()=>assertNoLivePids([{pid:123}],()=>{throw Object.assign(Error('denied'),{code:'EPERM'});}),/denied/);
  assert.doesNotThrow(()=>assertNoLivePids([{pid:123}],()=>{throw Object.assign(Error('absent'),{code:'ESRCH'});}));
});
test('notification failure retains durable event; delivery does not hold state mutex',async()=>{
  let rows=[{id:'first'}],locked=false,mutationSurvived=false;
  const next=async()=>{locked=true;const e=rows[0];locked=false;return e;};
  const ack=async id=>{locked=true;rows=rows.filter(e=>e.id!==id);locked=false;};
  await assert.rejects(deliverOutbox({next,ack,send:async()=>{assert.equal(locked,false);throw Error('offline');}}),/offline/);
  assert.equal(rows.length,1);
  let count=0;
  const result=await deliverOutbox({next,ack,send:async()=>{assert.equal(locked,false);if(count++===0){rows.push({id:'concurrent'});mutationSurvived=true;}}});
  assert.equal(mutationSurvived,true);assert.equal(result.sent,2);assert.deepEqual(rows,[]);
});
