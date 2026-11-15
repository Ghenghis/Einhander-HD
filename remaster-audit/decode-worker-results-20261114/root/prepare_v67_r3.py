"""Add missing local scene headers; retain already-passing adapter/renderer evidence."""
from pathlib import Path
import hashlib,json,shutil,datetime
n=Path(__file__).resolve().parent;e=Path('C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112')
old=e/'sampling-build-v67-decode-identity-r2';out=e/'sampling-build-v67-decode-identity-r3';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
b=json.loads((old/'build.json').read_text(encoding='utf-8'))
assert b['counter_adapter_passed'] and b['counter_adapter_cases']==8 and b['real_growth_mutant_detected']
assert next(c for c in b['commands'] if c['label']=='compile-gpu_gl_renderer.c')['exit']==0
assert all(c['child_absent'] for c in b['commands'])
for name in ['src','include','third_party']:shutil.copytree(old/name,out/name)
for name in ['counter-handler.inc','counter-handler-test.c','counter-contract.json']:shutil.copy2(old/name,out/name)
base=e/'sampling-build-v66-reviewed-scene-r3'
for name in ['scene_runtime.h','scene_capture.h']:shutil.copy2(base/'src'/name,out/'src'/name)
d=json.loads((old/'prepared.json').read_text(encoding='utf-8'))
d['sources'].update({('src/'+name):sha(out/'src'/name) for name in ['scene_runtime.h','scene_capture.h']})
d['retained_validation']=dict(path=str(old/'build.json'),sha256=sha(old/'build.json'),counter_cases=8,source_handler_sha256=sha(old/'counter-handler.inc'),source_test_sha256=sha(old/'counter-handler-test.c'),renderer_object=str(old/'gpu_gl_renderer.c.obj'),renderer_object_sha256=sha(old/'gpu_gl_renderer.c.obj'),renderer_source_sha256=sha(old/'src/gpu_gl_renderer.c'))
d['revision_note']='r2 missing scene_runtime.h prevented debug TU compile; exact v66 local header closure added. Already-passing adapter8/growth control and renderer compilation retained; no duplicate tests.'
d['prepared_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(out/'prepared.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
s=(n/'build_private_v67.py').read_text(encoding='utf-8')
assert s.count("sampling-build-v67-decode-identity-r2")==1;s=s.replace('sampling-build-v67-decode-identity-r2','sampling-build-v67-decode-identity-r3')
a=s.index('    # Compile the exact adapter');z=s.index('    def arguments(old):',a)
sub='''    # Keep successful, unchanged adapter and renderer controls from the preserved r2.
    retained=prep['retained_validation'];prior=json.loads(Path(retained['path']).read_text(encoding='utf-8'))
    assert sha(retained['path'])==retained['sha256'] and prior['counter_adapter_passed'] and prior['real_growth_mutant_detected']
    assert sha(out/'counter-handler.inc')==retained['source_handler_sha256'] and sha(out/'counter-handler-test.c')==retained['source_test_sha256']
    assert sha(src/'gpu_gl_renderer.c')==retained['renderer_source_sha256'] and sha(retained['renderer_object'])==retained['renderer_object_sha256']
    receipt.update(counter_adapter_cases=8,counter_adapter_passed=True,real_growth_mutant_detected=True,adapter_controls_retained_not_replayed=True,retained_renderer_object=retained['renderer_object']);save()
'''
s=s[:a]+sub+s[z:]
s=s.replace('    rebuilt={}\n',"    rebuilt={'gpu_gl_renderer.c.obj':Path(retained['renderer_object'])}\n")
s=s.replace("for name in ['gpu_gl_renderer.c','debug_server.c','hd_texture_pack.cpp']:","for name in ['debug_server.c','hd_texture_pack.cpp']:")
s=s.replace('rebuilt_tus=3,retained_link_inputs=len(inputs)-3','freshly_rebuilt_tus=2,renderer_rebuilt_in_preserved_r2=True,retained_link_inputs=len(inputs)-2')
target=n/'build_private_v67_r3.py';assert not target.exists();compile(s,str(target),'exec');target.write_text(s,encoding='utf-8',newline='\n')
print(json.dumps(dict(out=str(out),recipe=str(target),recipe_sha256=sha(target),retained=d['retained_validation'])))
