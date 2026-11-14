"""Record source reviews and a durable continuation checkpoint; no imports of reviewed code."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import psutil

R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
U=R/'.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui'
S=R/'.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
checks=[]
def pin(path,expected):
    raw=Path(path).read_bytes();got=hashlib.sha256(raw).hexdigest()
    if got!=expected:raise RuntimeError('Reviewed source changed: '+str(path))
    checks.append(dict(path=str(path),sha256=got,bytes=len(raw)))
pin(U/'tools/ui_speck_repair_v2.py','4957470c32b26d374691b4216a39176a8cb8277bf7d467349d08fd14afd8fcb6')
pin(U/'tools/ui_speck_measure_r3.py','f00af9d6f59735ff6440deea95e2dbddfc89dac14e6ef8a76e78107ffb509114')
pin(S/'watchdog/run_rc2_envelope.py','0d4078fcfdc71bd2163780c7a2887eefb74909e2517294f3e3f8500f9ea3e102')
pin(S/'watchdog/selftest_envelope.py','1f6d58bb5339a93352d936727a523b7e229e10133ebaf6aa13bf06720afacd27')
pin(R/'remaster-audit/parallel-stages-20261114/s23/tools/j10_preview.py','9ba10f175b403ec71fa89f4666e0a450381e0f285725a0d1502e06d900220907')
pin(R/'remaster-audit/parallel-stages-20261114/s23/tools/scale2x_cg.py','0c0517d37b033f469330c65d1bd533cd69bf210a4fbb2688fafae0d2954cd7ee')
pin(R/'remaster-audit/parallel-stages-20261114/s45/tools/s45_diag_bands_repair.py','ae2d61dc00e88d632be19cfae734b171c9a14dce77c20332c32736f6bc0b4f4f')
reviews=[dict(component='UI speckv2',status='source-blocked/superseded',
    findings=['versions recorded but not checked','sidecar hash not bound to expected metadata',
        'author modules imported before closure pins','CLI can widen beyond exact three known keys',
        'CRC/CLUT bounds missing before decode','wrong-mask control and R5 claims exceed implemented checks'],
    replacement='r3 measure-only source f00af9d6 addresses binding/versions/fixed scope; source cleared only, unrun'),
    dict(component='watchdog envelope-r0',status='source-blocked/new revision requested',
        findings=['wider job mask may not expand inherited one-core child affinity; explicitly set while suspended then verify',
            'selftest exceptions can orphan its unrelated sentinel; finally/identity cleanup and partial receipts required',
            'memory-cap test must distinguish controlled allocation refusal from wrapper failure; peak is report-only',
            'test harness needs full source pins and bounded whole-owned cleanup without one-core outer Job']),
    dict(component='S23 J10 previewv1',status='source-blocked/new revision requested',
        findings=['caught errors and partial/failed output currently exit0','unfinished output directories can be reused/overwritten',
            'critical assert checks vanish under optimized Python','numeric budget unused/step hardcodes120',
            'full imported source closure is recorded after use rather than pinned before execution']),
    dict(component='S45 stripev0',status='source-blocked/new revision requested',
        findings=['native validation return codes ignored','critical assert and unpinned dependencies/versions',
            'image decode before exact fixed header bounds; numerical threads not pinned before import',
            'compile step excluded from stated cost','skipped/failed audit does not fail the process',
            'nearest same-palette donor may cross distant material components; bound/locality evidence required'])]
out=N/('source-review-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(exist_ok=False)
data=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),owner='codex-einhander',
    task_id='EIN-CODEX-CONTINUITY-20261114',sources=checks,reviews=reviews,
    source_code_executed=False,images_decoded=0,native_tests_run=False,gpu_run=False,
    runtime_acceptance=False,next_action='Await native new revisions and coordinator host quiet-window clearance; old grants remain suspended')
(out/'result.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
checkpoint=dict(at_utc=data['at_utc'],owner=data['owner'],task_id=data['task_id'],project_complete=False,
    latest_remote_head='47eea3c8a7922a1d57fca3c20fa3c23304d65ef2',
    latest_delivery=str(N/'cpu-texture-delivery.json'),latest_pr_readback=str(N/'cpu-texture-pr-verification.json'),
    actual_results=['118/118 native class replay, no look/live acceptance','private v68 C:staging verified, no game/install',
        'cage ROI composition plan51de1e96 prepared only, zero image decode/composition'],
    source_review=str(out/'result.json'),host_hold='All new heavy/GPU launches held by coordinator pending quiet-window check after actual user unplugged externalD',
    no_gpu_job=True,no_active_heavy_root_job=True,
    pending=['coordinator explicit clearance + fresh first PR7 CPU grant, not old grant reuse',
        'native GL identity/material proof source proposal','watchdog new revision/source review + later bounded dummy tests',
        'UI r3 measure-only source cleared; later fresh grant and actual sheets/count review',
        'S23/S45 revised bounded previews + all later-stage native draws/look acceptance',
        'S67 source-only audio path audit','Cage ROI future composition/admission/live acceptance',
        'engine scene transport/RT/DLSS, skins/selectors/HUD, seven stages/release still open'],
    actual_metadata_monitor=dict(pid=35628,creation_unix=1794682582.0896692,bound_end_utc='2026-11-14T19:26:22.146Z',watcher_only=True),
    next_wake='Bounded actual Hermes inbox long-poll <=30s; renew verified owned monitor before bound; continue independent authorized work')
tmp=N/'current-checkpoint.tmp.json'
with tmp.open('w',encoding='utf-8') as stream:json.dump(checkpoint,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
os.replace(tmp,N/'current-checkpoint.json')
print(json.dumps(dict(checkpoint=str(N/'current-checkpoint.json'),source_review=str(out/'result.json'),sources=len(checks),executed_reviewed_code=False)))
