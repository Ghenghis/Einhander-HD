"""Verify completed native freezes and bind eight overlays to the newer O parent."""
from pathlib import Path
import datetime,hashlib,json,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
out=n/'mijpq-freeze-verification-r1';out.mkdir(exist_ok=False)
base=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):return dict(path=str(p),sha256=sha(p))
regions=[('M','95a3-m-windows','windows',[64,112,112,176]),('I','95a3-m-windows','windows',[0,64,64,128]),('J','95a3-m-windows','windows',[64,64,128,112]),('P','95a3-cutouts','cutout',[240,112,256,176]),('Q','95a3-cutouts','cutout',[0,128,48,192])]
native=r/'remaster-audit/comfy-authoring/t3-green-lights/frozen/atlas-95A3BCF8-t3-v1';handoff=native/'source-handoff.json'
source={x['key']:x for x in json.loads(handoff.read_text())['keys']};entries=[];freezes=[]
for region,directory,label,uv in regions:
    f=base/directory/'frozen'/f'95A3BCF8-{region}-{label}-v1'
    ready=json.loads((f/'READY.json').read_text());manifest=json.loads((f/'manifest.json').read_text())
    assert ready['validation_passed'] and manifest['validation_passed'] and not (f/'FAILED.json').exists()
    assert sha(f/'manifest.json')==ready['manifest_sha256'] and sha(f/'SHA256SUMS.txt')==ready['sha256sums']
    count=0
    for line in (f/'SHA256SUMS.txt').read_text().splitlines():
        h,rel=line.split('  ',1);assert sha(f/rel)==h;count+=1
    assert count==ready['files']
    freezes.append(dict(region=region,path=str(f),ready=pin(f/'READY.json'),manifest=pin(f/'manifest.json'),pins_verified=count))
    for key in manifest['keys']:
        src=source[key];refs={}
        for kind in ['words.bin','clut.bin','valid.bin']:
            ref=src['files'][kind];path=native/ref['file'];assert sha(path)==ref['sha256'];refs[kind]=pin(path)
        assert set(Path(refs['valid.bin']['path']).read_bytes())=={1}
        entries.append(dict(key=key,manifest=pin(f/'manifest.json'),image=pin(f/'page2048'/(key+'.png')),source_handoff=pin(handoff),native_source=dict(source_words=refs['words.bin'],source_clut=refs['clut.bin'],source_shape_words=[src['width_words'],src['height']],depth=src['depth']),roi_overlay=dict(native_size=[256,256],uv=uv)))
assert len(entries)==8 and len({x['key'] for x in entries})==8
receipts=[]
for directory,stamp in [('95a3-m-windows','20261114T170337Z'),('95a3-cutouts','20261114T171019Z')]:
    p=base/directory/'runs'/stamp/'rc.json';rc=json.loads(p.read_text())
    assert rc['rc']==rc['child_exit_code']==rc['wrapper_exit']==0 and rc['tree_absent']
    for key in ['child','wrapper']:
        pid=rc[key+'_pid'];created=rc[key+'_create_time']
        try:assert psutil.Process(pid).create_time()!=created,(key,'original identity still exists')
        except psutil.NoSuchProcess:pass
    receipts.append(dict(path=str(p),sha256=sha(p),child_pid=rc['child_pid'],child_exit=rc['child_exit_code'],outer_exit=rc['wrapper_exit'],seconds=rc['elapsed_s'],original_child_and_wrapper_absent=True,tree_absent=True))
parent=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-o-roi-r1/candidate.json'
assert sha(parent)=='3a83b481010f1c27c99e51eca13a62240c6e6e74684c723dbb0169f35f22a25c'
plan=n/'mijpq-roi-plan-r1.json';assert not plan.exists();plan.write_text(json.dumps(dict(parent=pin(parent),entries=entries,purpose='Private ROI-only M/I/J windows and P/Q cutout correction on the newer O parent. No installation, live appearance or whole-stage acceptance.'),indent=2)+'\n',encoding='utf-8')
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),freezes=freezes,total_frozen_pins=sum(x['pins_verified'] for x in freezes),actual_runs=receipts,plan=pin(plan),entries=8,root_copied_builders_executed=False,gpu_run=False,game_run=False,integrated=False)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
