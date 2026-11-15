from pathlib import Path
import hashlib,json,shutil
from PIL import Image
p=Path(__file__).resolve().parent;r=p.parents[2]
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
out=p/'qualification';out.mkdir(exist_ok=False)
proof=e/'v61-live-census-r2/hd-off_rewind-off/census-proof.json';d=json.loads(proof.read_text())
a,b=d['samples'][0],d['samples'][-1];tri=b['census']['triangles'];quad=b['census']['quads']
fields=d['final_phase']['fields'];rows=[dict(zip(fields,row)) for row in d['final_phase']['rows']]
summary={'proof_sha256':sha(proof),'game_exe_sha256':'c6e573f317e5faaa624612320c5468ed8e0158092b4e53e3a0357e607e325686',
 'scope':'30s early Stage1 city, HDoff, rewindoff, scale2, visual PGXP corrections off, diagnostics on, initially empty own cache and autocompile off. No foreign executable cache, RAM writes or save states.',
 'frames':[x['registers']['frame'] for x in d['samples']],'sample_seconds':[x['seconds'] for x in d['samples']],
 'triangles':tri,'quads':quad,'audio':{'first':a['audio'],'last':b['audio'],'frontend_underrun_delta':b['audio']['underruns']-a['audio']['underruns'],'bridge_underrun_delta':b['audio']['out']['underruns']-a['audio']['out']['underruns']},
 'phase_scope':{'rows':len(rows),'first_frame':rows[0]['frame'],'last_frame':rows[-1]['frame'],'truncated':d['final_phase']['truncated'],'city_start':a['registers']['frame'],'usable_for_city_timing':False,'limitation':'RPC returned first2048 rows rather than the city window; no late-frame phase attribution can be made.'},
 'errors':d['errors'],'exit':d['owned_process_exit'],'pid_gone':d['pid_gone'],'close':d['close'],
 'acceptance':{'diagnostic_route':True,'smoothness_audio':False,'full_stage_geometry_coverage':False,'ray_traced_gameplay':False}}
(out/'live-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
f=r/'remaster-audit/claude-backlog/class-mip/frozen/class-mip-v2b-breakdown-v1'
assert sha(f/'READY.json')=='2d578d83d3792d3b19cff50ab63d1c10cd176bfb2384a7be21fe0c3a4e7d88dc'
assert sha(f/'SHA256SUMS.txt')=='306b0b6bf089f4bd4cc6c8a6cec1cead5133016b7eb1111f4fb69ba31adac640'
checked=[]
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
 h,name=line.split('  ',1);file=f/name;assert file.resolve().is_relative_to(f.resolve());assert sha(file)==h,name;checked.append(name)
(out/'claude-frozen-verification.json').write_text(json.dumps({'files':len(checked),'all_hashes_match':True,'ready_sha256':sha(f/'READY.json'),'sums_sha256':sha(f/'SHA256SUMS.txt'),'scope':'Root verified frozen bytes; author fixture/mutant claims are not independently replayed by this check.'},indent=2)+'\n')
for run in ['r1','r2']:
 s=e/f'v61-live-census-{run}/hd-off_rewind-off';dest=out/f'game-{run}';dest.mkdir()
 for name in ['census-proof.json','candidate.json','executed-run-script.py','executed-prepare-script.py','native-boot.json','launch.json','stdout.log','stderr.log']:
  if (s/name).exists():shutil.copy2(s/name,dest/name)
 for pattern in ['*boot*.json','*route*.json','*launch*.json']:
  for file in s.glob(pattern):shutil.copy2(file,dest/file.name)
 for file in (s/'captures').glob('*.png'):
  if 'v61-census-city' in file.name:shutil.copy2(file,dest/file.name)
print(json.dumps({'freeze':'complete','checked_author_files':len(checked),'frontend_underruns':summary['audio']['frontend_underrun_delta'],'bridge_underruns':summary['audio']['bridge_underrun_delta'],'phase_frame_range':[rows[0]['frame'],rows[-1]['frame']]}))
