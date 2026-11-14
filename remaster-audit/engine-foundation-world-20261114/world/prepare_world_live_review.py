"""Prepare one same-binary/cache private world review. Never starts the game."""
from pathlib import Path
import ast, datetime, hashlib, json, subprocess, sys
root=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=root/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
source=e/'display58-power-maximum-r5b/hd-on_rewind-on/candidate.json'
original=json.loads(source.read_text())
assert original['launches']['candidate']['executable_sha256']=='c2c386bd1f0ea59d84f8e95f1a1103cb777904f3eacaacad0c8e4013448145a6'
candidate=e/'world-integrated-crisp-v1/candidate.json'
c=json.loads(candidate.read_text());verification=json.loads((candidate.parent/'verification.json').read_text())
assert verification['all_checks_pass'] and verification['candidate_sha256']==hashlib.sha256(candidate.read_bytes()).hexdigest()
assert c['final_count']==1698 and not c['production_installed']
prepared=json.loads(json.dumps(original))
for field in ['files','final_count','emissive_files']:prepared[field]=c[field]
prepared['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT']=str(candidate.parent/'pack')
input_path=n/'world-live-input.json';input_path.write_text(json.dumps(prepared,indent=1)+'\n')
script=(n/'run_sign_validation.py').read_text()
needle="            if second%15==0:\n                if report['visual_profile'].get('composed_stills',True):"
assert script.count(needle)==1
script=script.replace(needle,needle.replace('second%15','second%30'))
needle="        proof['geometry_correction_after']=probe.request(report,'geom_correction')"
assert script.count(needle)==1
script=script.replace(needle,"        proof['world_native_upload_tail']=probe.request(report,'native_upload_ledger',n=512)\n"+needle)
ast.parse(script);runner=n/'run_world_live_review.py';runner.write_text(script)
args=[sys.executable,'-X','utf8',str(runner),'--batch','world-integrated-live-r1','--candidate',str(input_path),
 '--runtime',str(e/'sampling-build-v58-frame-phases/build.json'),'--supersampling','2','--rewind','1',
 '--rewind-fmv-interval','4','--cpu-profile','1','--runtime-perf','1','--batch-attrib','1',
 '--filter-state-cache','1','--keep-bracket','1','--opaque-batch','1','--native-menus','--ordinary-fire',
 '--telemetry-only','--capture-seconds','120','--retain-host-audio','--prepare-only']
p=subprocess.run(args,cwd=root,creationflags=0x4000);assert p.returncode==0
directory=e/'world-integrated-live-r1/hd-on_rewind-on';report_path=directory/'candidate.json'
d=json.loads(report_path.read_text());env=d['launches']['candidate']['environment_overrides']
oldenv=original['launches']['candidate']['environment_overrides']
for key in ['PSXRECOMP_HD_UPLOAD_INDEX_INCREMENTAL','PSX_BENCH_WINDOW','PSXRECOMP_HD_UPLOAD_LEDGER','PSXRECOMP_HD_GPU_CACHE_MB','PSXRECOMP_GL_UPLOAD_PBO','PSXRECOMP_NATIVE_UPLOAD_LEDGER','PSX_FRAME_PHASE_RING']:env[key]=oldenv[key]
d['pacing_profile'].update(focus_policy='observe_only',baseline_acceptance=False,foreground_performance_acceptance=False,phase_diagnostic=True)
d['visual_profile'].update(composed_stills=True,source_capture=False,record_video=False,telemetry_only=False,focus_policy_scope='Observed only; 5 synchronous stills add readback load. No recorder, no full source collector, no timing acceptance.')
d['sign_validation']={'post_measurement_perspective_probe':False}
d['world_integration_review']={'composition':str(candidate),'composition_sha256':verification['candidate_sha256'],'patch_count':161,
 'same_tested_binary_and_cache':True,'driver_profile_changes':False,'scope':'Private world integration review. Upload observations do not prove per-key draw/visual acceptance. Distant window atlas unchanged. No full-stage or RT/DLSS acceptance.'}
title=d['launches']['candidate']['arguments'];title[title.index('--window-title')+1]='Einhander HD - world integration private review'
report_path.write_text(json.dumps(d,indent=1)+'\n')
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate':str(report_path),'prepare_arguments':args,
 'prepare_exit':p.returncode,'executable_sha256':d['launches']['candidate']['executable_sha256'],'cache_lineage':str(source.parent/'runtime/cache'),
 'private_cards':True,'source_drive_reads':False,'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),'game_started':False}
(n/'world-live-preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
