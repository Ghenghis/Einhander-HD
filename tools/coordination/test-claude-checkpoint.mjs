import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {buildCheckpoint,saveCheckpoint} from './claude-checkpoint.mjs';
import {stopDecision,handle,sessionProfile} from './claude-continuity-hook.mjs';
const now=Date.parse('2026-11-13T16:00:00Z');
const args=['--session','session-a','--monitor','provider-task-a','--wake','2026-11-13T16:25:00Z','--tasks','sys-parity','--next','Read the actual trace and continue'];

test('registered worktree checkpoint is written/read without touching the guarded canonical predecessor',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-checkpoint-route-'));
  try{
    const coordination=path.join(base,'coordination');await fs.mkdir(coordination);
    const relative='.claude/worktrees/worker/remaster-audit/primary/continuity/claude-einhander.json';
    await fs.writeFile(path.join(coordination,'CLAUDE-SESSIONS-20261114.json'),JSON.stringify({sessions:[{owner:'claude-einhander',session_id:'session-a',checkpoint:relative}]}));
    await fs.writeFile(path.join(coordination,'work-continuity.json'),JSON.stringify({owner:'claude-einhander',max_wait_minutes:30,completion_state:'completion.json'}));
    const predecessor=path.join(base,'.hermes3d_orchestrator/continuity/claude-einhander.json');
    await fs.mkdir(path.dirname(predecessor),{recursive:true});
    const previous='{"user_stop":{"requested":true,"reason":"historical predecessor"}}';await fs.writeFile(predecessor,previous);
    const actual=Date.now(),options=[...args];options[options.indexOf('--wake')+1]=new Date(actual+60000).toISOString();
    const saved=await saveCheckpoint(base,options,{now:actual});
    assert.equal(saved.file,path.join(base,relative).replaceAll('\\','/'));
    assert.equal(await fs.readFile(predecessor,'utf8'),previous);
    assert.deepEqual(await handle({session_id:'session-a',cwd:base,hook_event_name:'Stop'},base),{});
    const state=JSON.parse(await fs.readFile(saved.file,'utf8'));state.continuation.armed=false;await fs.writeFile(saved.file,JSON.stringify(state));
    assert.equal((await handle({session_id:'session-a',cwd:base,hook_event_name:'Stop'},base)).decision,'block');
  }finally{
    const target=await fs.realpath(base),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-checkpoint-route-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});
test('registered checkpoint paths reject workspace escape and foreign owner filenames',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-checkpoint-path-'));
  try{
    const directory=path.join(base,'coordination');await fs.mkdir(directory);
    const roster=path.join(directory,'CLAUDE-SESSIONS-20261114.json');
    for(const [checkpoint,pattern] of [['../claude-einhander.json',/escaped/],['inside/claude-einhander-s45.json',/filename/]]){
      await fs.writeFile(roster,JSON.stringify({sessions:[{owner:'claude-einhander',session_id:'session-a',checkpoint}]}));
      await assert.rejects(sessionProfile(base,'session-a'),pattern);
    }
  }finally{
    const target=await fs.realpath(base),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-checkpoint-path-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});

test('explicit bounded receiver checkpoint satisfies the actual stop gate',()=>{
  const state=buildCheckpoint({},args,{now});
  assert.equal(state.continuation.monitor_task_id,'provider-task-a');
  assert.deepEqual(stopDecision({config:{max_wait_minutes:30},state,completion:{full_remaster_complete:false},mail:[],input:{session_id:'session-a'},now}),{});
});
test('timestamp refresh cannot inherit a dead receiver or expired wake',()=>{
  const old={session_id:'session-a',pending_task_ids:['sys-parity'],next_action:'Read trace',continuation:{armed:true,monitor_task_id:'dead-task',next_wakeup_utc:'2026-11-13T15:57:00Z'}};
  assert.throws(()=>buildCheckpoint(old,['--session','session-a'],{now}),/explicit --monitor/);
  const malformed=[...args];malformed.splice(malformed.indexOf('--monitor')+1,1);
  assert.throws(()=>buildCheckpoint({},malformed,{now}),/explicit --monitor/);
});
test('past, invalid and over-limit wake deadlines are rejected',()=>{
  for(const wake of ['2026-11-13T15:59:59Z','not-a-date','2026-11-13T16:30:01Z']){
    const changed=[...args];changed[changed.indexOf('--wake')+1]=wake;
    assert.throws(()=>buildCheckpoint({},changed,{now}),/future --wake/);
  }
});
test('explicit user stop remains possible without a receiver',()=>{
  const state=buildCheckpoint({},['--user-stop','User explicitly paused'],{now});
  assert.equal(state.user_stop.requested,true);assert.equal(state.continuation.armed,false);
  assert.deepEqual(stopDecision({config:{},state,mail:[{id:'pending'}],input:{},now}),{});
});
test('invalid continuation does not overwrite the real checkpoint file',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-checkpoint-'));
  try{
    const dir=path.join(base,'.hermes3d_orchestrator/continuity');await fs.mkdir(dir,{recursive:true});
    const file=path.join(dir,'claude-einhander.json'),old=JSON.stringify({checkpoint_utc:'2026-11-13T15:45:00Z',continuation:{monitor_task_id:'dead-task'}});
    await fs.writeFile(file,old);
    await assert.rejects(saveCheckpoint(base,['--session','session-a'],{now}),/explicit --monitor/);
    assert.equal(await fs.readFile(file,'utf8'),old);
    const saved=await saveCheckpoint(base,args,{now});
    assert.equal(JSON.parse(await fs.readFile(file,'utf8')).continuation.monitor_task_id,'provider-task-a');
    assert.equal(saved.ok,true);
  }finally{
    const target=await fs.realpath(base),tmp=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tmp);assert.ok(path.basename(target).startsWith('ein-checkpoint-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});

test('registered worker checkpoint does not overwrite the primary owner and rejects foreign identities',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-worker-checkpoint-'));
  try{
    const coordination=path.join(base,'coordination');await fs.mkdir(coordination);
    await fs.writeFile(path.join(coordination,'CLAUDE-SESSIONS-20261114.json'),JSON.stringify({sessions:[
      {owner:'claude-einhander',session_id:'primary-session'},
      {owner:'claude-einhander-s23',session_id:'session-a',cli_session_id:'worker-cli'}]}));
    const dir=path.join(base,'.hermes3d_orchestrator/continuity');await fs.mkdir(dir,{recursive:true});
    const primary=path.join(dir,'claude-einhander.json');await fs.writeFile(primary,'{"primary":"preserve"}');
    const saved=await saveCheckpoint(base,[...args,'--owner','claude-einhander-s23'],{now});
    assert.equal(saved.owner,'claude-einhander-s23');
    assert.match(saved.file,/claude-einhander-s23\.json$/);
    assert.equal(await fs.readFile(primary,'utf8'),'{"primary":"preserve"}');
    await assert.rejects(saveCheckpoint(base,[...args,'--owner','claude-einhander'],{now}),/does not belong/);
    const wrong=[...args];wrong[wrong.indexOf('--session')+1]='unknown';
    await assert.rejects(saveCheckpoint(base,wrong,{now}),/not registered/);
    await assert.rejects(saveCheckpoint(base,[...args,'--owner','../bad'],{now}),/Invalid registered/);
  }finally{
    const target=await fs.realpath(base),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-worker-checkpoint-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});

test('registered worker user stop saves a paused checkpoint without a receiver and preserves the primary',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-worker-pause-'));
  try{
    const coordination=path.join(base,'coordination');await fs.mkdir(coordination);
    await fs.writeFile(path.join(coordination,'CLAUDE-SESSIONS-20261114.json'),JSON.stringify({sessions:[
      {owner:'claude-einhander',session_id:'primary-session'},
      {owner:'claude-einhander-s23',session_id:'worker-session',cli_session_id:'worker-cli'}]}));
    const dir=path.join(base,'.hermes3d_orchestrator/continuity');await fs.mkdir(dir,{recursive:true});
    const primary=path.join(dir,'claude-einhander.json');await fs.writeFile(primary,'{"primary":"preserve"}');
    const saved=await saveCheckpoint(base,['--owner','claude-einhander-s23','--user-stop','User explicitly paused'],{now});
    assert.equal(saved.owner,'claude-einhander-s23');
    assert.equal(saved.phase,'paused');assert.equal(saved.user_stop.requested,true);
    assert.equal(saved.continuation.armed,false);assert.equal(saved.continuation.monitor_task_id,'');
    const worker=JSON.parse(await fs.readFile(path.join(dir,'claude-einhander-s23.json'),'utf8'));
    assert.equal(worker.phase,'paused');assert.equal(worker.continuation.armed,false);
    assert.equal(await fs.readFile(primary,'utf8'),'{"primary":"preserve"}');
    await assert.rejects(saveCheckpoint(base,['--user-stop','User explicitly paused'],{now}),/registered --session or explicit --owner/);
    assert.equal(await fs.readFile(primary,'utf8'),'{"primary":"preserve"}');
  }finally{
    const target=await fs.realpath(base),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-worker-pause-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});
