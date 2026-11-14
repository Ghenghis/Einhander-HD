"""CPU-only input pins and concrete live gates; never launch or allocate a GPU."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import psutil

r = Path('C:/github/Einhander')
n = Path(__file__).resolve().parent
e = r / 'remaster-audit/dev-center-evidence/stage1-completion-20261112'
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([11])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
runtime = e / 'sampling-build-v67-decode-identity-r3'
candidate = e / 'world-integrated-mijpq-roi-r1/candidate.json'
assert sha(runtime/'Einhander_Recompiled.exe') == '8bc3ac3daedcbb08790905c228d1dc7b052bd5ed52d3bb739c02009ec86bb772'
assert sha(candidate) == '903bd84a6be19fdef2b6d19293121515035b68c61b7d0ff67f4ff7cf38b30b20'
c = json.loads(candidate.read_text(encoding='utf-8'))
assert c['production_installed'] is False and len(c['files']) == 1699

def pin(path):
    return dict(path=str(path), sha256=sha(path))

out = n / 'stock-gameplay-review-plan-r1'
out.mkdir(exist_ok=False)
runner = r / 'remaster-audit/run_stage1_unassisted_review.py'
plan = dict(schema='einhander-stock-gameplay-review-plan-v1', created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    state='CPU preparation only; live execution NOT RUN', gpu_run=False, game_run=False, audio_run=False,
    inputs=dict(runtime=pin(runtime/'Einhander_Recompiled.exe'), build_receipt=pin(runtime/'build.json'),
        candidate=pin(candidate), runner=pin(runner), tests=pin(r/'remaster-audit/test_stage1_unassisted_review.py'),
        user_hold=pin(n/'user-cpu-only-hold-20261114T173705Z.json')),
    texture_entries=1699, full_png_hash_replay_this_step=False,
    prior_full_readback=pin(n/'mijpq-roi-candidate-verification-r1/result.json'),
    runtime_limit='Retained parent objects; not a clean full-source build. Never run in-game yet.',
    preparation_command=['python',str(runner),'--batch','v67-unassisted-r1','--candidate',str(candidate),
        '--runtime',str(runtime/'build.json'),'--capture-seconds','60','--supersampling','2',
        '--cpu-profile','1','--telemetry-only','--native-menus','--prepare-only'],
    preparation_executed=False,
    execution_command=['python',str(runner),'--batch','v67-unassisted-r1','--capture-seconds','60',
        '--supersampling','2','--telemetry-only','--run-prepared'],
    prerequisites=['Independent source review and CPU refusal tests',
        'Actual isolated runtime/cache/card staging, then validate every prepared PNG and settings hash',
        'User hold elapsed; fresh broker grant and exact token required, never elapsed-time takeover',
        'Fresh CPU below60%, free RAM at least16GiB; all heavy native workers quiet',
        'Independent exact-PID/creation-time watchdog and real adapter verification before launch',
        'Private GPU reservation markers, ports4373-4378 unused; leave installed port4370 untouched'],
    route=dict(renderer='stock OpenGL; Remix disabled', ordinary_menu_input=True,
        stage_warps=False, state_loads=False, ram_writes=False, timer_assistance=False,
        rewind=False, turbo=False, display_history=False, render_scale=2,
        default_experimental_features=False,
        focus='Brief owned-window handoff required; unfocused samples are diagnostic only'),
    passes=[dict(id='qualification', cap_seconds=30,
        purpose='Confirm exact v67 process, GL upload restoration, 98-value adapter and owned cleanup; separate from timing',
        implemented_in_runner=False),
        dict(id='unassisted-timing', cap_measurement_seconds=60, total_watchdog_seconds=210,
            video=False, source_recording=False, screenshots=False, ram_writes=False,
            purpose='Audio counters, CPU frame-phase sequence and focus through normal early Stage1',
            caveat='Native death or transition ends scope. This does not guarantee reaching the mini-boss.'),
        dict(id='mini-boss-timing', cap_measurement_seconds=120, total_watchdog_seconds=270,
            purpose='Separate later run if normal play reaches the mini-boss; correlate actual frame/sequence brackets',
            caveat='No matched-state or fix claim without actual matching evidence. Assisted alternatives require explicit labeling.'),
        dict(id='texture-source-review', cap_measurement_seconds=60, total_watchdog_seconds=210,
            purpose='Separate short native/HD captures around O/M/I/J/P/Q and distant green/pink sign draws',
            blocker='Recorder F3 mark-row reserve leak must be reproduced/fixed or a reviewed runner guard used.',
            recorder_load_disclosed=True)],
    audio=dict(counters='before/after starvation, underflow and queue statistics with frame/time correlation',
        audible_review='Separate bounded owned callback/process-output capture after measurement; no shared desktop audio',
        unproven=['Synchronized video/audio','Remastered audio quality','No audible defect','Full-stage acceptance']),
    later_stages=dict(policy='Separate stock-first ordinary-play captures; no claim that a60-second Stage1 run reaches later stages.',
        s23=pin(r/'remaster-audit/parallel-stages-20261114/s23/capture/S23-CAPTURE-TRIGGERS.md'),
        s45=pin(r/'remaster-audit/parallel-stages-20261114/s45/capture/20261114T174241Z/addendum.json'),
        s67='T6 CB07BBCB/hull UV+CLUT identity; T7 fleet87C91293/675828CE/D887C7F4 with actual CLUT coordinates and screenshot marks'),
    cleanup=['Release input; stop only owned capture workers; request quit; wait on retained process handle',
        'On deadline, terminate only exact retained owned process tree; preserve failure and exit code',
        'Verify process absence and private debug port closure; then explicitly release fenced broker grant'],
    acceptance_open=['Live look/motion','Mini-boss stutter','Audio quality','4K performance/fidelity',
        'Realistic skins/selectors','All seven stages','Working Remix images and Shutdown','In-game ray tracing/DLSS','Installed release'])
(out/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(plan=str(out/'PLAN.json'),sha256=sha(out/'PLAN.json'),gpu_run=False,game_run=False,staged_runtime=False)))
