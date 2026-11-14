from pathlib import Path
import datetime,hashlib,json,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
out=e/'sampling-build-v68-recorder-reserve-r1';base=e/'sampling-build-v67-decode-identity-r3'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
d=json.loads((out/'build.json').read_bytes());p=json.loads((out/'prepared.json').read_bytes())
assert d['build_complete'] and not d['game_launched'] and not d['gpu_run']
assert [x['label'] for x in d['commands']]==['compile-gpu_gl_renderer.c','link']
assert all(x['exit']==0 and x['owned_handle_exited'] for x in d['commands'])
for f,h in p['sources'].items():assert sha(out/f)==h,f
for ref in d['link_inputs']:assert sha(ref['path'])==ref['sha256'],ref['path']
assert sha(d['executable'])==d['executable_sha256']
assert sha(out/'src/hd_research_renderer.h')=='e12716f980b28eec2da093408ba522f3d7e8316108433f2b95706efdaded68ee'
dependencies=(out/'gpu_gl_renderer.c.obj.d').read_text()
assert (out/'src/hd_research_renderer.h').as_posix() in dependencies.replace('\\:',':')
parent=json.loads((base/'build.json').read_bytes())
changed=[Path(x['path']).name for x in d['link_inputs'] if x not in parent['link_inputs']]
assert changed==['gpu_gl_renderer.c.obj'],changed
guard=json.loads((n/'v68-cpu-build-r1/rc.json').read_bytes());assert guard['tree_absent'] and guard['wrapper_exit']==0
dest=n/'v68-independent-readback-r2';dest.mkdir(exist_ok=False)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
    executable_sha256=d['executable_sha256'],frozen_sources_verified=len(p['sources']),
    link_inputs_verified=len(d['link_inputs']),changed_link_objects=changed,compiler_dependency_uses_new_header=True,
    compile_link_seconds=d['elapsed_seconds'],whole_guard_seconds=guard['elapsed_s'],gpu_run=False,game_run=False,
    complete_source_rebuild=False,installed=False,live_qualified=False,
    prior_verifier_error='Basename-only mapping collided on two different crc32.c.obj paths; failed verifier preserved; exact path/hash records used now.')
(dest/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
