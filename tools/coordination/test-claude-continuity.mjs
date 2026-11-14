import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {stopDecision,handle,inbox,pendingWork,read,writeJson,sessionProfile} from './claude-continuity-hook.mjs';
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

test('older urgent blockers stay visible ahead of a burst of routine notes',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ein-mail-priority-'));
  try{
    const dir=path.join(root,'.hermes3d_orchestrator/inbox/claude-einhander');await fs.mkdir(dir,{recursive:true});
    const messages=[{id:'msg_urgent',priority:'urgent',created_utc:'2026-11-13T15:00:00Z',body:'Investigate first divergence before promotion'},
      {id:'msg_high',priority:'high',created_utc:'2026-11-13T15:01:00Z'},
      ...Array.from({length:7},(_,i)=>({id:'msg_note'+i,priority:'normal',created_utc:`2026-11-13T16:0${i}:00Z`}))];
    for(const m of messages)await fs.writeFile(path.join(dir,m.id+'.json'),JSON.stringify({...m,status:'unread',sender:'codex-einhander'}));
    const mail=await inbox(root,'claude-einhander');
    assert.deepEqual(mail.slice(0,3).map(m=>m.id),['msg_urgent','msg_high','msg_note6']);
    await fs.mkdir(path.join(root,'coordination'));
    await writeJson(path.join(root,'coordination/work-continuity.json'),{...config,owner:'claude-einhander',completion_state:'completion.json'});
    const result=await handle({...input,cwd:root,hook_event_name:'SessionStart'},root);
    assert.match(result.hookSpecificOutput.additionalContext,/Investigate first divergence before promotion/);
  }finally{
    const target=await fs.realpath(root),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-mail-priority-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});
test('real file hook reads mailbox, ignores acknowledgement chatter and throttles context',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'ein-continuity-'));
  try{
    await fs.mkdir(path.join(root,'coordination'));await fs.writeFile(path.join(root,'coordination/work-continuity.json'),JSON.stringify({...config,owner:'claude-einhander',completion_state:'completion.json'}));
    await fs.writeFile(path.join(root,'completion.json'),JSON.stringify({full_remaster_complete:false}));
    const dir=path.join(root,'.hermes3d_orchestrator/inbox/claude-einhander');await fs.mkdir(dir,{recursive:true});
    await fs.writeFile(path.join(dir,'msg_action.json'),JSON.stringify({id:'msg_action',status:'unread',sender:'codex-einhander',subject:'Finish pending work',body:'Pause competing GPU work for the actual game test.'}));
    await fs.writeFile(path.join(dir,'msg_ack.json'),JSON.stringify({id:'msg_ack',status:'unread',metadata:{ack_for_message_id:'other'}}));
    assert.equal((await inbox(root,'claude-einhander')).length,1);
    const startup=await handle({...input,cwd:root,hook_event_name:'SessionStart'},root);assert.match(startup.hookSpecificOutput.additionalContext,/msg_action/);
    assert.match(startup.hookSpecificOutput.additionalContext,/Pause competing GPU work/);
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
    const racing=path.join(root,'concurrent-state.json');await writeJson(racing,{valid:true});
    const concurrent=await Promise.allSettled(Array.from({length:24},async(_,i)=>{
      await writeJson(racing,{valid:true,index:i});assert.equal((await read(racing,{})).valid,true);
      await handle({...input,cwd:root,hook_event_name:'PostToolUse'},root);
    }));
    assert.deepEqual(concurrent.filter(r=>r.status==='rejected').map(r=>String(r.reason)),[]);
    // Other producers may still write in place. A brief partial read retries;
    // permanently malformed state remains an error, never a silent success.
    await fs.writeFile(racing,'{');
    const repair=(async()=>{await new Promise(resolve=>setTimeout(resolve,15));await writeJson(racing,{repaired:true});})();
    assert.equal((await read(racing,{})).repaired,true);await repair;
    await fs.writeFile(racing,'{');await assert.rejects(read(racing,{}),SyntaxError);
  }finally{
    const target=await fs.realpath(root),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-continuity-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});

test('registered worker reads only its own inbox and accepts its verified CLI/desktop checkpoint aliases',async()=>{
  const base=await fs.mkdtemp(path.join(os.tmpdir(),'ein-session-routing-'));
  try{
    await fs.mkdir(path.join(base,'coordination'));
    await writeJson(path.join(base,'coordination/work-continuity.json'),{...config,owner:'claude-einhander',completion_state:'completion.json'});
    await writeJson(path.join(base,'coordination/CLAUDE-SESSIONS-20261114.json'),{sessions:[
      {owner:'claude-einhander',session_id:'main-desktop'},
      {owner:'claude-einhander-s45',session_id:'worker-desktop',cli_session_id:'worker-cli'}]});
    const privateDir=path.join(base,'.hermes3d_orchestrator/continuity');await fs.mkdir(privateDir,{recursive:true});
    const state={...waiting,session_id:'local_worker-desktop',checkpoint_utc:new Date().toISOString(),continuation:{...waiting.continuation,next_wakeup_utc:new Date(Date.now()+300000).toISOString()}};
    await writeJson(path.join(privateDir,'claude-einhander-s45.json'),state);
    for(const [owner,id,body] of [['claude-einhander','msg_main','MAIN-PRIVATE'],['claude-einhander-s45','msg_worker','WORKER-OWN']]){
      const dir=path.join(base,'.hermes3d_orchestrator/inbox',owner);await fs.mkdir(dir,{recursive:true});
      await writeJson(path.join(dir,id+'.json'),{id,status:'unread',body});
    }
    const workerInput={session_id:'worker-cli',cwd:path.join(base,'.claude/worktrees/worker'),hook_event_name:'SessionStart'};
    const result=await handle(workerInput,base);
    assert.match(result.hookSpecificOutput.additionalContext,/owner=claude-einhander-s45/);
    assert.match(result.hookSpecificOutput.additionalContext,/WORKER-OWN/);
    assert.doesNotMatch(result.hookSpecificOutput.additionalContext,/MAIN-PRIVATE/);
    await writeJson(path.join(base,'.hermes3d_orchestrator/inbox/claude-einhander-s45/msg_worker.json'),{id:'msg_worker',status:'done'});
    assert.deepEqual(await handle({...workerInput,hook_event_name:'Stop'},base),{});
    assert.equal((await inbox(base,'claude-einhander')).length,1);
    const unknown=await handle({...workerInput,session_id:'unregistered',hook_event_name:'Stop'},base);
    assert.equal(unknown.decision,'block');assert.match(unknown.reason,/not mapped/);
    assert.doesNotMatch(unknown.reason,/MAIN-PRIVATE/);
    await assert.rejects(sessionProfile(base,'worker-cli','claude-einhander'),/does not belong/);
    const roster=await read(path.join(base,'coordination/CLAUDE-SESSIONS-20261114.json'));
    roster.sessions.push({owner:'claude-einhander-s67',session_id:'worker-cli'});
    await writeJson(path.join(base,'coordination/CLAUDE-SESSIONS-20261114.json'),roster);
    await assert.rejects(sessionProfile(base,'worker-cli'),/more than once/);
  }finally{
    const target=await fs.realpath(base),tempRoot=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(target),tempRoot);assert.ok(path.basename(target).startsWith('ein-session-routing-'));
    await fs.rm(target,{recursive:true,force:true});
  }
});
