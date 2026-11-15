from pathlib import Path
import importlib.util,json,hashlib,sys,psutil
from types import SimpleNamespace
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112';sys.path.insert(0,str(r/'remaster-audit'))
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
spec=importlib.util.spec_from_file_location('pacing_own_cache',n/'pacing-own-cache.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
args=SimpleNamespace(batch='v62-rgb-visual-r1',candidate=e/'world-integrated-crisp-v4/candidate.json',runtime=e/'sampling-build-v62-rgb-edges-r1/build.json',gpu_queries=0,world_sampling=0,opaque_batch=0,region_index=0,batch_attrib=0,cpu_profile=0,runtime_perf=0,filter_state_cache=0,keep_bracket=0,emissive=0,supersampling=2,rewind_fmv_interval=4,guest_frames=0)
d=mod.prepare('hd-on_rewind-off',args);p=Path(d['evidence']);env=d['launches']['candidate']['environment_overrides'];env.update(PSXRECOMP_HD_RGB_EDGES='1',PSX_FRAME_PHASE_RING='1',PSX_OVERLAY_AUTOCOMPILE_OFF='1',PSXRECOMP_HD_DECODE_BUDGET_MB='256')
d['route_reference_profile']='native-stock-scale2';d['rgb_edge_visual_scope']={'visual_only':True,'seconds':12,'class_mips':False,'world_sampling':False,'rgb_edges':True,'cache_initially_empty':True,'foreign_cache':False,'performance_acceptance':False,'cpu_affinity':[10,11,12,13]}
(p/'candidate.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({'candidate':str(p/'candidate.json'),'sha256':hashlib.sha256((p/'candidate.json').read_bytes()).hexdigest(),'exe_sha256':d['launches']['candidate']['executable_sha256']}))
