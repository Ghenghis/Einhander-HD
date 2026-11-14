"""Verify actual changed-object build/link and closure comparison; never execute the game."""
from pathlib import Path
import datetime as dt,hashlib,json,os,psutil
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
A=R/'remaster-audit/parallel-stages-20261114/s67/runs/v69-build-2206'
REPRO=A.parent/'v69-repro-2200/manifest.json';E=A.parent/'v69-build-2206-envelope.json'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(p):return os.path.normcase(os.path.abspath(str(p)))
need(sha(REPRO)=='af6fa0329b243e7d9e490431069ac8c0c6edba5107206da94dfe134db1e84b0c','repro changed')
m=json.loads((A/'manifest.json').read_bytes());rm=json.loads(REPRO.read_bytes());e=json.loads(E.read_bytes())
need(m['phase']=='build' and m['verdict']=='PASS' and not m['errors'] and not m['reasons'],'build failed')
need(m['driver_sha256']=='45a73ed13b58cbbff8f3164260c7d0f735736206c4a7223bd27f45ad72161003','driver changed')
need(m['inputs']['repro_manifest']['sha256']==sha(REPRO),'build/repro binding')
pins={'combined_main_cpp':'8022b148d92dede3a7afd5c6f372eba4e144172266fd578122fb3bceb011ff36',
    'combined_debug_c':'b50aef2a4de7ef8ceb621ffc681d072699f88cc5247357a435ebe405cebc0185',
    'combined_header':'c84258e13238a1fe8f70e783a0db2fa957d3eb5b7660df88641e0614dd67651c'}
copies={}
for key,pin in pins.items():
    ent=m['inputs'][key+'_copy'];path=Path(ent['copy'])
    need(ent['ok'] and ent['read_sha256']==ent['copy_sha256']==sha(path)==pin,'changed source mismatch')
    need(sha(Path(m['inputs'][key]['path']))==pin,'original proposal changed');copies[key]=path
closures=[]
for label,src_key,old_key in [('main','combined_main_cpp','v58_main_cpp'),('debug','combined_debug_c','v67_debug_server_c')]:
    current=m['build'][label];base=rm['repro'][label]
    need(current['closure_equal_to_repro'],'recorded closure mismatch')
    skip_new={norm(copies[src_key])};skip_old={norm(rm['inputs'][old_key]['path'])}
    if label=='main':skip_new.add(norm(copies['combined_header']));skip_old.update(rm['repro_main_audio_header'])
    new={p:h for p,h in current['closure'].items() if p not in skip_new}
    old={p:h for p,h in base['closure'].items() if p not in skip_old}
    need(new==old,'independent closure comparison failed')
    need(current['closure'][norm(copies[src_key])]==pins[src_key],'source dependency binding')
    if label=='main':need(current['closure'][norm(copies['combined_header'])]==pins['combined_header'],'new header not consumed')
    need(sha(Path(current['obj']))==current['obj_sha256'] and sha(Path(current['depfile']))==current['depfile_sha256'],'object/depfile changed')
    closures.append(dict(label=label,closure_count=len(current['closure']),unchanged_dependencies=len(new),obj_sha256=current['obj_sha256']))
need(m['link_inputs']['recorded']==155 and m['link_inputs']['retained_checked']==153 and not m['link_inputs']['mismatched'],'link input receipt')
need([c['step'] for c in m['children']]==['build:main','build:debug','build:link'] and all(c['rc']==0 and not c['timed_out'] for c in m['children']),'compile/link result')
exe=Path(m['v69_executable']['path']);need(sha(exe)==m['v69_executable']['sha256']=='f1ccb34dc0d06ba945fd822c9e807fe14b452b0d61584b731dcd4163f27759e5','executable changed')
need(exe.stat().st_size==m['v69_executable']['bytes']==21468672,'executable size')
wrapper=A.parent/'v69-build-2206-runner/executed-watchdog.py'
need(sha(wrapper)=='fa5e42fa7b7dd08c75f97ece9bf82ad749f9bf66346fce955c9b8e23b85b3e36','copied wrapper mismatch')
need(e['rc']==e['wrapper_exit']==e['child_exit_code']==0 and not e['timeout_killed'],'Job exit')
need(e['precheck']['system_cpu_pct']<60 and e['precheck']['free_gib']>=16,'gate')
need(e['job_assigned_before_resume'] and e['child_readback_before_resume']=={'cpu_affinity':[15],'priority':16384},'child resource readback')
need(e['job_limits_readback']['job_memory_limit']==1073741824 and e['job_limits_readback']['affinity_mask']==32768,'Job readback')
need(e['job']['active']==0 and e['tree_absent'] and e['child_absent'] and not e['descendants_left'],'cleanup receipt')
identities=[('wrapper',e['wrapper_pid'],e['wrapper_create_time']),('driver',e['child_pid'],e['child_create_time'])]
identities += [(c['step'],c['pid'],c['creation_unix']) for c in m['children']];known=[]
for label,pid,created in identities:
    need(created is not None,'missing creation time')
    try:absent=psutil.Process(pid).create_time()!=created
    except psutil.NoSuchProcess:absent=True
    need(absent,'known owned identity remains');known.append(dict(label=label,pid=pid,creation_unix=created,identity_absent=True))
out=N/'v69-audio-build-readback-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),readback_pass=True,actual_private_build_pass=True,
    manifest_sha256=sha(A/'manifest.json'),envelope_sha256=sha(E),executable_sha256=sha(exe),executable_bytes=exe.stat().st_size,
    copied_wrapper_sha256=sha(wrapper),closure_comparisons=closures,known_identities=known,
    elapsed_s=e['elapsed_s'],peak_job_memory_bytes=e['peak_job_memory_bytes'],retained_link_inputs=153,
    original_reproduction_deviation_preserved=True,all_dependency_files_rehashed_by_root=False,
    full_source_rebuild=False,compiler_or_fixture_replayed=False,game_run=False,gpu_run=False,
    real_sdl_device_tested=False,listening=False,performance_gain_proved=False,installed=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('closure_comparisons','known_identities')}))
