import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {stopDecision,handle,inbox,pendingWork} from './claude-continuity-hook.mjs';
const now=Date.now(),input={session_id:'test-session'},config={status:'active',max_wait_minutes:30};
const decide=(overrides={})=>stopDecision({config,state:null,completion:{full_remaster_complete:false},mail:[],input,now,...overrides});
test('unfinished work blocks voluntary stop and repeat hook does not silently abandon it',()=>{
  assert.equal(decide().decision,'block');assert.equal(decide({input:{...input,stop_hook_active:true}}).decision,'block');
});
test('explicit user pause permits stop even with unread work',()=>assert.deepEqual(decide({state:{user_stop:{requested:true,reason:'User explicitly paused this project'}},mail:[{id:'m'}]}),{}));
test('component completion cannot claim full project completion',()=>assert.equal(decide({config:{...config,status:'complete'}}).decision,'block'));
test('actual overall completion plus complete registry permits stop',()=>assert.deepEqual(decide({config:{...config,status:'complete'},completion:{full_remaster_complete:true}}),{}));
const waiting={session_id:input.session_id,phase:'waiting',checkpoint_utc:new Date(now-1000).toISOString(),pending_task_ids:['art-gap-census'],next_action:'Read result and continue',continuation:{armed:true,monitor_task_id:'actual-client-monitor',next_wakeup_utc:new Date(now+300000).toISOString()}};
test('fresh checkpoint with bounded armed continuation permits a waiting turn',()=>assert.deepEqual(decide({state:waiting}),{}));
test('unread actionable mail prevents a waiting turn until handled',()=>assert.equal(decide({state:waiting,mail:[{id:'msg_action'}]}).decision,'block'));
test('eligible durable work prevents waiting even with a valid continuation',()=>{
  assert.equal(decide({state:waiting,queued:[{task_id:'independent-art'}]}).decision,'block');
  assert.deepEqual(decide({state:{user_stop:{requested:true,reason:'User paused'}},queued:[{task_id:'independent-art'}]}),{});
});
test('missing/expired/wrong-session continuation blocks stop',()=>{
  for(const state of [{...waiting,continuation:{armed:false}},{...waiting,session_id:'different'},{...waiting,checkpoint_utc:new Date(now-300000).toISOString()},
    {...waiting,continuation:{...waiting.continuation,next_wakeup_utc:new Date(now-1).toISOString()}},
    {...waiting,continuation:{...waiting.continuation,next_wakeup_utc:new Date(now+3600000).toISOString()}}])assert.equal(decide({state}).decision,'block');
});
test('real file hook reads mailbox, ignores acknowledgement chatter and throttles context',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ein-continuity-'));
  try{
    await fs.mkdir(path.join(root,'coordination'));await fs.writeFile(path.join(root,'coordination/work-continuity.json'),JSON.stringify({...config,owner:'claude-einhander',completion_state:'completion.json'}));
    await fs.writeFile(path.join(root,'completion.json'),JSON.stringify({full_remaster_complete:false}));
    const dir=path.join(root,'.hermes3d_orchestrator/inbox/claude-einhander');await fs.mkdir(dir,{recursive:true});
    await fs.writeFile(path.join(dir,'msg_action.json'),JSON.stringify({id:'msg_action',status:'unread',sender:'codex-einhander',subject:'Finish pending work'}));
    await fs.writeFile(path.join(dir,'msg_ack.json'),JSON.stringify({id:'msg_ack',status:'unread',metadata:{ack_for_message_id:'other'}}));
    assert.equal((await inbox(root,'claude-einhander')).length,1);
    const startup=await handle({...input,cwd:root,hook_event_name:'SessionStart'},root);assert.match(startup.hookSpecificOutput.additionalContext,/msg_action/);
    for(let i=0;i<3;i++)assert.deepEqual(await handle({...input,cwd:root,hook_event_name:'PostToolUse'},root),{});
    assert.equal((await handle({...input,cwd:root,hook_event_name:'Stop'},root)).decision,'block');
    assert.deepEqual(await handle({...input,cwd:path.dirname(root),hook_event_name:'Stop'},root),{});
    const pending=path.join(root,'.hermes3d_orchestrator/tasks/pending');await fs.mkdir(pending,{recursive:true});
    for(const row of [{task_id:'mine',target_owner_pattern:'claude-einhander',priority:100},
      {task_id:'other',target_owner_pattern:'codex-einhander'},
      {task_id:'blocked',target_owner_pattern:'claude-einhander',blocked_reason:'Exact missing native palette'},
      {task_id:'claimed',target_owner_pattern:'claude-einhander',claimed_by:'claude-einhander'}])
      await fs.writeFile(path.join(pending,row.task_id+'.json'),JSON.stringify(row));
    assert.deepEqual((await pendingWork(root,'claude-einhander')).map(t=>t.task_id),['mine']);
  }finally{
    const target=await fs.realpath(root),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-continuity-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});
