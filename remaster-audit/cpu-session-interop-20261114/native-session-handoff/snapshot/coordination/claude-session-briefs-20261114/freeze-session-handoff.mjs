import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {read,writeJson} from '../../tools/coordination/claude-continuity-hook.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const base='coordination/claude-session-briefs-20261114';
const verified=base+'/verified-2026-11-14T13-45-49-189Z/verification.json';
const addendum=base+'/readiness-addendum-2026-11-14T13-43-01-325Z.json';
const receipt=await read(path.join(root,verified),null);
const roster=await read(path.join(root,'coordination/CLAUDE-SESSIONS-20261114.json'),null);
const files=new Set([...Object.keys(receipt.files),verified,addendum,base+'/RECOVERY.md',base+'/freeze-session-handoff.mjs',
  ...roster.sessions.map(row=>row.checkpoint)]);
const now=new Date().toISOString();
const output=base+'/handoff-'+now.replaceAll(/[:.]/g,'-');
const pins=[];
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
for(const file of files){
  const bytes=await fs.readFile(path.join(root,file));
  if(receipt.files[file]&&receipt.files[file]!==sha(bytes))throw Error('Verified source changed: '+file);
  const target=path.join(root,output,'snapshot',file);await fs.mkdir(path.dirname(target),{recursive:true});
  const handle=await fs.open(target,'wx');try{await handle.writeFile(bytes);await handle.sync();}finally{await handle.close();}
  if(sha(await fs.readFile(target))!==sha(bytes))throw Error('Snapshot readback differs: '+file);
  pins.push({source:file,snapshot:'snapshot/'+file,bytes:bytes.length,sha256:sha(bytes)});
}
const manifest={created_utc:now,launch_task:'EIN-CLAUDE-SESSIONS-20261114',new_sessions:3,total_sessions:4,
  monitor_handoff:roster.monitoring_handoff,files:pins,verification:verified,readiness_correction:addendum,
  source_edit_locks:'Released after immutable snapshot and exact handoff message',project_complete:false};
const file=path.join(root,output,'manifest.json');await writeJson(file,manifest);
console.log(JSON.stringify({manifest:file,sha256:sha(await fs.readFile(file)),files:pins.length,verified_passed:receipt.tests.passed}));
