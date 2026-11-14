"""Bind the frozen O correction to the latest parent and captured native source."""
from pathlib import Path
import hashlib,json
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):return dict(path=str(p),sha256=sha(p))
f=r/'remaster-audit/claude-backlog/95a3-o-city/frozen/95A3BCF8-O-city-v1'
ready=json.loads((f/'READY.json').read_text());assert ready['validation_passed']
assert sha(f/'manifest.json')==ready['manifest_sha256'] and sha(f/'SHA256SUMS.txt')==ready['sha256sums']
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
    h,rel=line.split('  ',1);assert sha(f/rel)==h
native=r/'remaster-audit/comfy-authoring/t3-green-lights/frozen/atlas-95A3BCF8-t3-v1'
handoff=native/'source-handoff.json';sources={x['key']:x for x in json.loads(handoff.read_text())['keys']}
parent=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-rise-f32-r1/candidate.json'
entries=[]
for key in ['95A3BCF8-60245B3A','95A3BCF8-07A9568D']:
    src=sources[key];refs={}
    for kind in ['words.bin','clut.bin','valid.bin']:
        ref=src['files'][kind];path=native/ref['file'];assert sha(path)==ref['sha256'];refs[kind]=pin(path)
    assert set(Path(refs['valid.bin']['path']).read_bytes())=={1}
    entries.append(dict(key=key,manifest=pin(f/'manifest.json'),image=pin(f/'page2048'/(key+'.png')),
        source_handoff=pin(handoff),native_source=dict(source_words=refs['words.bin'],source_clut=refs['clut.bin'],source_shape_words=[src['width_words'],src['height']],depth=src['depth']),
        roi_overlay=dict(native_size=[256,256],uv=[176,112,240,176])))
plan=dict(parent=pin(parent),entries=entries,purpose='Private size-neutral region-O correctness comparison only. Preserve all latest-parent pixels outside O; no installation or live acceptance.',review_required='Root viewed frozen O preview; current ROI composer source review and coordinated CPU run required.')
path=n/'region-o-roi-plan-r1.json';assert not path.exists();path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(plan=str(path),sha256=sha(path),entries=len(entries),parent_sha256=plan['parent']['sha256'],gpu_run=False,composed=False)))
