from pathlib import Path
import ast,hashlib,importlib.util,json,psutil,sys
from types import SimpleNamespace
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
sys.path.insert(0,str(r/'remaster-audit'));psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
source=r/'remaster-audit/run_stage1_pacing_ab.py';s=source.read_text()
old='    shutil.copytree(original.parent / "cache", runtime / "cache")';assert s.count(old)==1
s=s.replace(old,'    (runtime / "cache").mkdir()  # Empty own cache; never transplant a foreign executable cache.')
ast.parse(s);f=n/'pacing-own-cache.py';f.write_text(s,encoding='utf-8')
spec=importlib.util.spec_from_file_location('pacing_own_cache',f);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
args=SimpleNamespace(batch='v61-live-census-r1',candidate=e/'world-integrated-crisp-v4/candidate.json',runtime=e/'sampling-build-v61-view-metrics-r2/build.json',gpu_queries=0,world_sampling=0,opaque_batch=0,region_index=0,batch_attrib=0,cpu_profile=0,runtime_perf=0,filter_state_cache=0,keep_bracket=0,emissive=0,supersampling=2,rewind_fmv_interval=4,guest_frames=0)
d=mod.prepare('hd-off_rewind-off',args);p=Path(d['evidence']);env=d['launches']['candidate']['environment_overrides'];env.update(PSX_FRAME_PHASE_RING='1',PSX_OVERLAY_AUTOCOMPILE_OFF='1',PSXRECOMP_HD_DECODE_BUDGET_MB='256')
d['route_reference_profile']='native-stock-scale2'
d['live_census_profile']={'cache_initially_empty':True,'foreign_cache_staged':False,'hd_disabled':True,'renderer_correction_off':True,'seconds':30,'timer_assistance':False,'frame_phase_ring':True,'scope':'First v61 startup/actual textured-primitive provenance qualification with no cache transplant. No scene or rendering fidelity acceptance.'}
(p/'candidate.json').write_text(json.dumps(d,indent=2)+'\n')
assert not list((p/'runtime/cache').rglob('*'))
result={'candidate':str(p/'candidate.json'),'sha256':hashlib.sha256((p/'candidate.json').read_bytes()).hexdigest(),'exe_sha256':d['launches']['candidate']['executable_sha256'],'cache_initially_empty':True,'game_launched':False,'pacing_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'private_pacing_sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(n/'v61-live-preparation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
