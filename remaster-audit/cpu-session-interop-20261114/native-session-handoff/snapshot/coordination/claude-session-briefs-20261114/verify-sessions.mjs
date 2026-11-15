import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { read, writeJson } from '../../tools/coordination/claude-continuity-hook.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const rosterPath=path.join(root,'coordination/CLAUDE-SESSIONS-20261114.json');
const roster=await read(rosterPath,null);
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const artifacts={
  'claude-einhander-s23':['remaster-audit/parallel-stages-20261114/s23/runs/selection-20261114T133254Z/selection-map.json','remaster-audit/parallel-stages-20261114/s23/runs/selection-20261114T133254Z/strict-join.json'],
  'claude-einhander-s45':['remaster-audit/parallel-stages-20261114/s45/source-map/20261114T133831Z/source-map.json'],
  'claude-einhander-s67':['remaster-audit/parallel-stages-20261114/s67/stage6/selection-map-20261114T133638Z.json','remaster-audit/parallel-stages-20261114/s67/stage7/selection-map-20261114T133927Z.json']};
const rows=[];
for(const row of roster.sessions){
  if(!artifacts[row.owner])continue;
  const checkpointBytes=await fs.readFile(path.join(root,row.checkpoint));
  if(checkpointBytes.includes(0))throw Error('Checkpoint has NUL bytes');
  const checkpoint=JSON.parse(checkpointBytes);
  if(checkpoint.owner!==row.owner)throw Error('Owner mismatch');
  const activityFile='.hermes3d_orchestrator/continuity/activity-'+sha(String(row.cli_session_id)).slice(0,16)+'.json';
  const activity=await read(path.join(root,activityFile),null);
  if(activity?.owner!==row.owner||activity?.session_id!==row.cli_session_id)throw Error('Live hook routing not proven: '+row.owner);
  const outputs=[];
  for(const file of artifacts[row.owner]){
    const bytes=await fs.readFile(path.join(root,file));
    if(bytes.includes(0))throw Error('Output has NUL bytes');JSON.parse(bytes);
    outputs.push({path:file,bytes:bytes.length,sha256:sha(bytes)});
  }
  row.first_outputs=outputs;
  row.state='actual_model_work_and_checkpoint_verified';
  row.live_hook_verified_utc=activity.model_hook_observed_at_utc;
  rows.push({owner:row.owner,session_id:row.session_id,cli_session_id:row.cli_session_id,
    startup_message_id:row.startup_message_id,checkpoint:row.checkpoint,checkpoint_sha256:sha(checkpointBytes),
    checkpoint_utc:checkpoint.checkpoint_utc,live_hook_activity:activityFile,
    live_hook_observed_at_utc:activity.model_hook_observed_at_utc,outputs});
}
roster.updated_utc=new Date().toISOString();
await writeJson(rosterPath,roster);
const tracked=['tools/coordination/claude-continuity-hook.mjs','tools/coordination/claude-checkpoint.mjs',
  'tools/coordination/test-claude-continuity.mjs','tools/coordination/test-claude-checkpoint.mjs',
  'coordination/CLAUDE-SESSIONS-20261114.json'];
for(const name of await fs.readdir(path.dirname(fileURLToPath(import.meta.url)))){
  if(/\.(mjs|txt)$/.test(name))tracked.push('coordination/claude-session-briefs-20261114/'+name);
}
const files={};for(const file of tracked)files[file]=sha(await fs.readFile(path.join(root,file)));
const testArgs=['--test','--test-reporter=tap','--test-concurrency=1','tools/coordination/test-claude-continuity.mjs','tools/coordination/test-claude-checkpoint.mjs'];
const testsStarted=new Date().toISOString();
const executed=spawnSync(process.execPath,testArgs,{cwd:root,encoding:'utf8',timeout:10000,windowsHide:true});
const testsEnded=new Date().toISOString();
if(executed.status!==0||executed.error)throw Error('Focused session-routing tests failed: '+executed.stderr);
const testCount=Number(/^# tests (\d+)$/m.exec(executed.stdout)?.[1]);
const failed=Number(/^# fail (\d+)$/m.exec(executed.stdout)?.[1]);
if(testCount!==18||failed!==0)throw Error('Unexpected focused test summary');
const now=new Date();
const destination=path.join(path.dirname(fileURLToPath(import.meta.url)),'verified-'+now.toISOString().replaceAll(/[:.]/g,'-'));
await fs.mkdir(destination);
const receipt={verified_utc:now.toISOString(),new_sessions_verified:rows.length,total_claude_sessions:roster.sessions.length,
  sessions:rows,files,tests:{command:[process.execPath,...testArgs],passed:testCount,failed,exit:executed.status,started_utc:testsStarted,ended_utc:testsEnded,stdout:executed.stdout,stderr:executed.stderr},
  monitor:{pid:28164,bounded_until_utc:'2026-11-14T14:07:14.706Z',watcher_only:true,proves_model_activity:false},
  limitations:['These checks qualify session startup, ownership, routing and first metadata/source artifacts. They do not accept artwork or gameplay.',
    'Original primary CLI identity is confirmed by actual-model message msg_3b5f8bf61de9e710; live hook reload has not been independently requalified in that pre-existing C:/github session.',
    'A bounded monitor cannot provide model operation while the app/computer is off; resume recorded sessions and reverify files after a crash.'],
  supersedes:'verified-2026-11-14T13-41-12-523Z/verification.json: adds the reviewer-requested roster-bound user-stop save test and canonical integration-owner help; original primary CLI identity now confirmed. Prior receipts retained.',project_complete:false};
await writeJson(path.join(destination,'verification.json'),receipt);
console.log(JSON.stringify({path:path.join(destination,'verification.json'),sha256:sha(await fs.readFile(path.join(destination,'verification.json'))),new_sessions:rows.length,total_sessions:roster.sessions.length,artifacts_verified:rows.reduce((n,r)=>n+r.outputs.length,0)}));
