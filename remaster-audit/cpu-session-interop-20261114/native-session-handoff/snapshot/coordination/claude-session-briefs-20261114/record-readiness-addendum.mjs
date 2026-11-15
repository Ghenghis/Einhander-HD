import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { writeJson } from '../../tools/coordination/claude-continuity-hook.mjs';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const old='remaster-audit/runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json';
const folders=['stage6-vram384-0-8F498326-F07625EE-v1','stage6-vram704-0-20961255-E0849F81-v1'];
const added=[];
for(const folder of folders){
  const manifest=`remaster-audit/comfy-authoring/w7-stage6/frozen/${folder}/manifest.json`;
  const data=await fs.readFile(path.join(root,manifest));JSON.parse(data);
  added.push({folder:manifest.replace('/manifest.json',''),manifest_sha256:crypto.createHash('sha256').update(data).digest('hex')});
}
const value={observed_utc:new Date().toISOString(),reported_by:'claude-einhander-s67',message_id:'msg_ac1d8fb04c619936',
  corrects:{path:old,sha256:'07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8',issue:'Stage6 candidate folder list omitted two retained base packs containing23 selected keys. The101-key selected total remains correct. Original hash-bound report is retained unchanged.'},
  added_candidate_folders:added,selected_keys_in_added_folders:{F07625EE:16,E0849F81:7},
  current_selection_authority:'remaster-audit/parallel-stages-20261114/s67/stage6/selection-map-20261114T133638Z.json',
  stage7_pending_review:'Worker reports validate_predicted gate does not enforce draw/CLUT-slot evidence for inferred C4FDEDD2-EAD968A1. Preserve as unconfirmed; require matching live source plus actual draw at texpage832,0 and CLUT0,504 before admission. This report is not an independently reproduced code bug fix.',
  gpu_executed:false,artwork_accepted:false};
const target=path.join(here,'readiness-addendum-'+new Date().toISOString().replaceAll(/[:.]/g,'-')+'.json');
await writeJson(target,value);
console.log(JSON.stringify({path:target,sha256:crypto.createHash('sha256').update(await fs.readFile(target)).digest('hex'),added_manifests:added}));
