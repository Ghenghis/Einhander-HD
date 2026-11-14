// A model-authored scheduler journal, not a worker launcher or liveness monitor.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {read,writeJson} from '../../../tools/coordination/claude-continuity-hook.mjs';
const directory=path.dirname(fileURLToPath(import.meta.url));
const file=path.join(directory,'texture-cpu-slot.json');
const [action,owner,arg1,arg2]=process.argv.slice(2);
const current=await read(file,null),now=new Date();
const authority='msg_71c92af58749e7e9';
if(!/^claude-einhander(?:-s(?:23|45|67))?$/.test(owner||''))throw Error('Unknown worker');
let next;
if(action==='grant'){
  if(current&&!['released','expired_without_start'].includes(current.state))throw Error('Prior slot has no actual release');
  const caps={'rise-f32':90,'s45-jb':30,'s23-j2':240,'s45-jd':80,'s45-je':80};
  if(!(arg1 in caps))throw Error('Job is not in the main delegated queue');
  next={schema:'ein-texture-cpu-slot-v1',scheduler:'codex-einhander-crash-check',authority_message:authority,
    state:'granted',owner,job:arg1,granted_utc:now.toISOString(),start_by_utc:new Date(now.getTime()+60000).toISOString(),
    max_total_seconds:caps[arg1],actual_pid:null,one_process_at_a_time:true,one_logical_cpu:true,
    priority:'BelowNormal',gpu_allowed:false,root_only:['v6 long host test','GPU/game tests']};
}else{
  if(current?.owner!==owner)throw Error('Caller does not own the current slot');
  next={...current};
  if(action==='start'){
    if(!['granted','running'].includes(current.state))throw Error('Slot is not granted/running');
    if(!/^\d+$/.test(arg1||'')||!arg2)throw Error('Actual PID and run folder required');
    next.state='running';next.actual_pid=Number(arg1);next.run_folder=arg2;next.observed_start_utc=now.toISOString();
    next.start_evidence='Actual model reported PID/run; coordinator must independently check process/exit.';
  }else if(action==='release'){
    if(!arg1)throw Error('Actual exit/result evidence required');
    next.state='released';next.released_utc=now.toISOString();next.release_evidence=arg1;next.actual_pid=null;
  }else if(action==='expire'){
    if(current.state!=='granted'||Date.parse(current.start_by_utc)>now.getTime())throw Error('Grant has not expired without a start');
    if(!arg1)throw Error('Actual no-job confirmation required');
    next.state='expired_without_start';next.expired_utc=now.toISOString();next.release_evidence=arg1;
  }else throw Error('Expected grant/start/release/expire');
}
next.updated_utc=now.toISOString();
const history=path.join(directory,'texture-slot-events.jsonl');
const event={utc:now.toISOString(),action,owner,arg1,arg2,state:next};
const handle=await fs.open(history,'a');try{await handle.writeFile(JSON.stringify(event)+'\n');await handle.sync();}finally{await handle.close();}
await writeJson(file,next);
console.log(JSON.stringify(next));
