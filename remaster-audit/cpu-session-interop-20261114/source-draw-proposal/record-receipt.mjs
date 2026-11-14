import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {writeJson,read} from '../../../tools/coordination/claude-continuity-hook.mjs';
const folder=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(folder,'../../..');
const now=new Date().toISOString();
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
const executionFiles=(await fs.readdir(folder)).filter(n=>n.startsWith('test-execution-')&&n.endsWith('.json')).sort();
const executionFile=executionFiles.at(-1);
const execution=await read(path.join(folder,executionFile),null);
const passed=Number(/Ran (\d+) tests/.exec(execution.output)?.[1]);
const seconds=Number(/tests in ([\d.]+)s/.exec(execution.output)?.[1]);
if(execution.exit_code!==0||passed!==13||!execution.output.trimEnd().endsWith('OK'))throw Error('Expected actual13-test pass');
const files=['source_draw_admission.py','test_source_draw_admission.py','README.md','record-receipt.mjs',
  'real-draw-row.jsonl','real-draw-row.provenance.json',executionFile].map(n=>path.join(folder,n));
files.push(path.join(root,'remaster-audit/fullgame-prep/static-extraction/validate_predicted.py'));
files.push(path.join(root,'remaster-audit/fullgame-prep/static-extraction/stages-v4/stage7/textures/C4FDEDD2.words.bin'));
const pins=[];
for(const file of files){const bytes=await fs.readFile(file);pins.push({path:path.relative(root,file).replaceAll('\\','/'),bytes:bytes.length,sha256:sha(bytes)});}
const report={observed_utc:now,task:'EIN-SESSION-CONTINUATION-20261114',kind:'isolated_source_draw_admission_proposal',
  tests:{command:'python -B remaster-audit/runtime-review/session-continuation-20261114/test_source_draw_admission.py',
    actual_tool_output_chunk:execution.chunk_id,output_file:executionFile,exit_code:execution.exit_code,
    tests_passed:passed,tests_failed:0,python_reported_seconds:seconds,observed_utc:execution.observed_utc,
    resource_scope:'BelowNormal parent shell; inherited processor affinity1; tiny synthetic files only',
    warnings:'Unmodified legacy gate emits ResourceWarning about its own unclosed file handles.',
    note:'This script records the already observed tool result and current unchanged source pins; it does not claim a new test execution.'},
  supersedes:'receipt-2026-11-14T13-54-05-206Z.json: real recorder uv_bounds/native_words schema correction, verbatim pinned real-row test and13-case actual run. Earlier preliminary receipt retained.',
  files:pins,real_key_admitted:false,gpu_executed:false,stage_complete:false,project_complete:false,
  native_sessions:{last_actual_metadata_message:'msg_e8a80b1349210e6f',all_four_running_at_utc:'2026-11-14T13:49:54Z'},
  remaining:['Main independent review and integration of additional key-level guard.',
    'Qualified stage7 run, complete live key source and actual matching832,0/CLUT0,504 draw.',
    'Four Claude workers continue implementation and source/art/gameplay/audio acceptance for seven stages.']};
const file=path.join(folder,'receipt-'+now.replaceAll(/[:.]/g,'-')+'.json');
await writeJson(file,report);
const checkpoint={owner:'codex-einhander-crash-check',chat_id:'01a1da2a-6273-7051-92a9-fc914070d84e',checkpoint_utc:now,
  phase:'working',task_id:report.task,pending_task_ids:[report.task],project_complete:false,
  latest_receipt:path.relative(root,file).replaceAll('\\','/'),receipt_sha256:sha(await fs.readFile(file)),
  next_action:'Read real inbox and keep four native Claude models working, recover only actual interrupted/stopped sessions; main grants heavy CPU/GPU and publishes reviewed results.',
  monitor:{owner:'codex-einhander',pid:28164,bound_end_utc:'2026-11-14T14:07:14.706Z',proves_model_activity:false},
  gpu_policy:'3090Ti reserved for Pizza Tycoon HD until at least07:00Phoenix AND explicit user release; no automatic expiry.'};
await writeJson(path.join(root,'.hermes3d_orchestrator/continuity/codex-einhander-crash-check.json'),checkpoint);
console.log(JSON.stringify({receipt:file,sha256:sha(await fs.readFile(file)),pins:pins.length,tests_passed:passed}));
