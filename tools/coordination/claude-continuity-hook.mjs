// Local, bounded Claude hooks. No network calls, automatic messages, model
// spawning, permission changes, or forged agent-presence heartbeats.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
async function read(file,fallback){try{return JSON.parse((await fs.readFile(file,'utf8')).replace(/^\uFEFF/,''));}catch(e){if(e.code==='ENOENT')return fallback;throw e;}}
function inside(base,relative){const p=path.resolve(base,relative),r=path.relative(base,p);if(r.startsWith('..')||path.isAbsolute(r))throw Error('Continuity path escaped workspace');return p;}
export async function inbox(base,owner){
  const directory=inside(base,`.hermes3d_orchestrator/inbox/${owner}`);let names;
  try{names=await fs.readdir(directory);}catch(e){if(e.code==='ENOENT')return [];throw e;}
  const rows=[];
  for(const name of names.filter(x=>/^msg_[a-zA-Z0-9]+\.json$/.test(x))){
    const m=await read(path.join(directory,name),null);
    if(m&&m.status==='unread'&&!m.metadata?.ack_for_message_id)rows.push(m);
  }
  return rows.sort((a,b)=>String(b.created_utc).localeCompare(String(a.created_utc)));
}
export function stopDecision({config,state,completion,mail,input,now=Date.now()}){
  if(state?.user_stop?.requested===true&&String(state.user_stop.reason||'').trim())return {};
  if(mail.length)return {decision:'block',reason:`Act on ${mail.length} unread Hermes message(s) before yielding: ${mail.slice(0,5).map(m=>m.id).join(', ')}. Read bodies, complete or checkpoint the requests, and acknowledge quietly.`};
  if(config.status==='complete'&&completion?.full_remaster_complete===true)return {};
  const age=now-Date.parse(state?.checkpoint_utc),wake=Date.parse(state?.continuation?.next_wakeup_utc);
  const waiting=typeof input.session_id==='string'&&input.session_id.length>0&&state?.session_id===input.session_id&&state?.phase==='waiting'&&
    Array.isArray(state.pending_task_ids)&&state.pending_task_ids.length>0&&String(state.next_action||'').trim()&&
    age>=0&&age<=120000&&state.continuation?.armed===true&&String(state.continuation.monitor_task_id||'').trim()&&
    wake>now&&wake-now<=(config.max_wait_minutes||30)*60000;
  if(waiting)return {};
  return {decision:'block',reason:'The authorized Einhander project is unfinished. Continue the next concrete task, or read the inbox and record a real bounded waiting checkpoint with an armed monitor and next wake. Read coordination/CLAUDE-HANDOFF.md. A component handoff or mail watcher is not project completion. Honour an explicit user stop/pause; do not spin without tool calls or fabricate continuation receipts.'};
}
export async function handle(input,base=root){
  const config=await read(path.join(base,'coordination/work-continuity.json'),null);
  if(!config||config.owner!=='claude-einhander')return {};
  if(input.cwd){
    const allowed=[base,...(config.project_roots||[])];
    if(!allowed.some(candidate=>{const r=path.relative(path.resolve(candidate),path.resolve(input.cwd));return !r.startsWith('..')&&!path.isAbsolute(r);}))return {};
  }
  const owner=config.owner,privateDir=inside(base,'.hermes3d_orchestrator/continuity');
  const state=await read(path.join(privateDir,owner+'.json'),null);
  const completion=await read(inside(base,config.completion_state),null);
  const mail=await inbox(base,owner),event=input.hook_event_name;
  await fs.mkdir(privateDir,{recursive:true});
  const sessionKey=crypto.createHash('sha256').update(String(input.session_id||'unknown')).digest('hex').slice(0,16);
  const activity=path.join(privateDir,`activity-${sessionKey}.json`);
  const previous=await read(activity,{}),now=Date.now();
  await fs.writeFile(activity,JSON.stringify({session_id:input.session_id,event,model_hook_observed_at_utc:new Date(now).toISOString(),notified_at_utc:previous.notified_at_utc})+'\n');
  if(event==='Stop')return stopDecision({config,state,completion,mail,input,now});
  if(event==='PostToolUse'&&now-Date.parse(previous.notified_at_utc||0)<15000)return {};
  if(event==='SessionStart'||(event==='PostToolUse'&&mail.length)){
    const context=`Einhander autonomous continuation: read CLAUDE.md and coordination/CLAUDE-HANDOFF.md. Overall completion=${completion?.full_remaster_complete===true}. ${mail.length} unread actionable Hermes message(s). `+
      mail.slice(0,5).map(m=>`${m.id} from=${m.sender} ${m.subject}`).join('; ')+
      '. Read actual bodies and acknowledge quietly. Continue unfinished work; checkpoint and arm real continuation before a waiting turn.';
    await fs.writeFile(activity,JSON.stringify({session_id:input.session_id,event,model_hook_observed_at_utc:new Date(now).toISOString(),notified_at_utc:new Date(now).toISOString()})+'\n');
    return {hookSpecificOutput:{hookEventName:event,additionalContext:context}};
  }
  return {};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  let input={hook_event_name:process.argv[2]};
  try{let raw='';for await(const chunk of process.stdin)raw+=chunk;input={...input,...JSON.parse(raw.replace(/^\uFEFF/,'')||'{}')};console.log(JSON.stringify(await handle(input)));}
  catch(error){console.log(JSON.stringify(input.hook_event_name==='Stop'?{decision:'block',reason:'Continuity check failed; inspect project hooks and durable checkpoint before ending: '+String(error.message).slice(0,180)}:{hookSpecificOutput:{hookEventName:input.hook_event_name||'SessionStart',additionalContext:'Continuity check error: '+String(error.message).slice(0,180)}}));}
}
