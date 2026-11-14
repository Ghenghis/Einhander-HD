// Cooperative cross-project GPU scheduler. It does not change drivers, power,
// permissions, or kill jobs. Launchers must check their current fenced grant.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const directory=path.join(root,'.hermes3d_orchestrator/shared-gpu');
const coordinators=new Set(['codex-einhander','codex-einhander-crash-check']);
const participants=new Set(['claude-einhander','claude-pizza-tycoon-hd']);
const requireThat=(ok,message)=>{if(!ok)throw Error(message);};
export function initialState(){return {schema:'shared-gpu-v1',gpu_uuid:'GPU-ff51fa52-74c8-c785-e000-53fe58844033',name:'RTX 3090 Ti',revision:0,grant:null,denied:[],requests:[],history:[],outbox:[]};}
export function transition(previous,action,actor,args={},now=Date.now()){
  const state=structuredClone(previous),utc=new Date(now).toISOString();
  requireThat(coordinators.has(actor)||participants.has(actor),'Unregistered GPU inbox owner');
  const coordinator=coordinators.has(actor);
  const holder=()=>{requireThat(state.grant?.owner===actor,'GPU is not granted to this owner');requireThat(args.token===state.grant.token,'Grant token mismatch (stale handoff)');return state.grant;};
  if(action==='request'){
    requireThat(participants.has(actor),'Only project workers request GPU time');
    requireThat(String(args.purpose||'').trim(),'Purpose required');
    requireThat(!state.requests.some(r=>r.owner===actor),'This owner already has a pending request');
    state.requests.push({id:crypto.randomUUID(),owner:actor,purpose:args.purpose,requested_utc:utc});
  }else if(action==='grant'){
    requireThat(coordinator,'Only a coordinator grants GPU time');
    requireThat(participants.has(args.target),'Unknown target project');
    requireThat(!state.grant,'Current owner must explicitly release first; expiry never transfers ownership');
    requireThat(!state.denied.includes(args.target),'Target project is denied new GPU grants');
    requireThat(String(args.evidence||'').trim(),'Availability/release evidence required');
    if(args.seconds!==undefined)requireThat(Number.isInteger(args.seconds)&&args.seconds>0&&args.seconds<=3600,'Grant seconds must be 1..3600 or omitted for explicit user reservation');
    state.grant={owner:args.target,token:crypto.randomUUID(),granted_utc:utc,expires_utc:args.seconds?new Date(now+args.seconds*1000).toISOString():null,evidence:args.evidence,jobs:[],new_starts_allowed:true};
    state.requests=state.requests.filter(r=>r.owner!==args.target);
  }else if(action==='deny'||action==='allow'){
    requireThat(coordinator,'Only a coordinator changes allow/deny policy');
    requireThat(participants.has(args.target),'Unknown target project');
    requireThat(String(args.evidence||'').trim(),'Policy reason/evidence required');
    state.denied=state.denied.filter(o=>o!==args.target);
    if(action==='deny')state.denied.push(args.target);
    if(state.grant?.owner===args.target)state.grant.new_starts_allowed=action==='allow';
  }else if(action==='check'||action==='start'){
    const grant=holder();
    requireThat(grant.new_starts_allowed&&!state.denied.includes(actor),'New GPU work is disallowed; finish/checkpoint existing work and release');
    requireThat(!grant.expires_utc||Date.parse(grant.expires_utc)>now,'Grant expired; ownership is retained until explicit safe release');
    if(action==='check')return {state:previous,result:{allowed:true,gpu_uuid:state.gpu_uuid,grant:structuredClone(grant)}};
    requireThat(Number.isInteger(args.pid)&&args.pid>0&&String(args.command||'').trim()&&String(args.created_utc||'').trim(),'Actual PID, creation time and command required');
    requireThat(!grant.jobs.some(j=>j.pid===args.pid),'PID already registered');
    grant.jobs.push({pid:args.pid,created_utc:args.created_utc,command:args.command,registered_utc:utc});
  }else if(action==='release'){
    holder();
    requireThat(args.no_gpu_jobs===true&&String(args.evidence||'').trim(),'Explicit no-GPU-jobs confirmation and cleanup evidence required');
    // The CLI also independently checks every registered PID before mutation.
    state.grant=null;
  }else throw Error('Unknown GPU action');
  state.revision++;
  const event={id:crypto.randomUUID(),utc,revision:state.revision,actor,action,target:args.target||actor,evidence:args.evidence||args.purpose||null};
  state.history.push(event);
  state.outbox.push({...event,subject:`3090 Ti ${action}: ${args.target||actor}`,body:JSON.stringify({event,grant:state.grant,denied:state.denied,requests:state.requests}),recipients:[...coordinators,...participants].filter(o=>o!==actor)});
  return {state,result:{ok:true,event,grant:state.grant,denied:state.denied,requests:state.requests}};
}
async function readState(){return JSON.parse((await fs.readFile(path.join(directory,'state.json'),'utf8')).replace(/^\uFEFF/,''));}
export function assertNoLivePids(jobs,probe=(pid)=>process.kill(pid,0)){
  for(const job of jobs){
    let absent=false;try{probe(job.pid);}catch(e){if(e.code==='ESRCH')absent=true;else throw e;}
    requireThat(absent,`Registered PID ${job.pid} still exists; verify exact identity and finish cleanup before release`);
  }
}
export async function withMutex(dir,work){
  await fs.mkdir(dir,{recursive:true});
  const mutex=path.join(dir,'MUTEX');
  const handle=await fs.open(mutex,'wx'); // Never steal by timeout; crash recovery requires actual owner absence.
  try{await handle.writeFile(JSON.stringify({pid:process.pid,created_utc:new Date().toISOString()}));await handle.sync();return await work();}
  finally{await handle.close();await fs.unlink(mutex);}
}
async function save(state){
  const file=path.join(directory,'state.json'),temporary=file+'.'+crypto.randomUUID()+'.tmp';
  const handle=await fs.open(temporary,'wx');
  try{await handle.writeFile(JSON.stringify(state,null,2)+'\n');await handle.sync();}finally{await handle.close();}
  await fs.rename(temporary,file);
}
export async function deliverOutbox({next,send,ack}){
  let sent=0;
  for(;;){const event=await next();if(!event)return {sent};await send(event);await ack(event.id);sent++;}
}
async function flush(){
  const {connect}=await import('./hermes-client.mjs');const client=await connect();
  try{return await deliverOutbox({
    next:()=>withMutex(directory,async()=>(await readState()).outbox[0]),
    send:e=>client.call('hermes_send_message',{sender:e.actor,recipients:e.recipients,subject:e.subject,body:e.body,metadata:{gpu_event_id:e.id},requiresAck:true,priority:'high'}),
    ack:id=>withMutex(directory,async()=>{const state=await readState();state.outbox=state.outbox.filter(e=>e.id!==id);await save(state);}),
  });}finally{await client.close();}
}
async function main(){
  const [action,...argv]=process.argv.slice(2),opt=(name)=>{const i=argv.indexOf('--'+name);return i<0?undefined:argv[i+1];};
  const actor=opt('owner');
  if(action==='status'){console.log(JSON.stringify(await readState(),null,2));return;}
  if(action==='flush'){console.log(JSON.stringify(await flush()));return;}
  if(action==='inbox'||action==='ack'){
    requireThat(participants.has(actor)||coordinators.has(actor),'Unknown GPU inbox owner');
    const {connect}=await import('./hermes-client.mjs');const client=await connect();
    try{console.log(JSON.stringify(await client.call(action==='inbox'?'hermes_get_inbox':'hermes_ack_message',action==='inbox'?{owner:actor,includeAcked:false}:{owner:actor,messageId:opt('message'),notifySender:false})));}finally{await client.close();}return;
  }
  const args=opt('file')?JSON.parse((await fs.readFile(opt('file'),'utf8')).replace(/^\uFEFF/,'')):{};
  for(const key of ['target','purpose','evidence','token','command','created_utc'])if(opt(key)!==undefined)args[key]=opt(key);
  for(const key of ['seconds','pid'])if(opt(key)!==undefined)args[key]=Number(opt(key));
  if(argv.includes('--no-gpu-jobs'))args.no_gpu_jobs=true;
  const result=await withMutex(directory,async()=>{
    let state;try{state=await readState();}catch(e){if(e.code!=='ENOENT')throw e;state=initialState();}
    if(action==='release')assertNoLivePids(state.grant?.jobs||[]);
    if(action==='start'){requireThat(Number.isInteger(args.pid)&&args.pid>0,'Actual live PID required');process.kill(args.pid,0);}
    const next=transition(state,action,actor,args);if(action!=='check')await save(next.state);return next.result;
  });
  console.log(JSON.stringify(result));
  if(action!=='check'&&argv.includes('--no-flush'))console.log(JSON.stringify({delivery_pending:true,reason:'Explicit --no-flush; use flush outside the launch critical path'}));
  else if(action!=='check')try{console.log(JSON.stringify({delivery:await flush()}));}catch(e){console.log(JSON.stringify({delivery_pending:true,error:String(e.message)}));}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error(e.message);process.exitCode=1;});
