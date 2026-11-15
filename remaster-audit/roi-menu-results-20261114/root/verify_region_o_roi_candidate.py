"""Independent readback of the real private O composition; never launch it."""
from pathlib import Path
import datetime,hashlib,json,os,psutil
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from PIL import Image
import numpy as np
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'region-o-roi-candidate-verification-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=json.loads((n/'region-o-roi-plan-r1.json').read_text());parentpath=Path(plan['parent']['path'])
assert sha(parentpath)==plan['parent']['sha256'];parent=json.loads(parentpath.read_text())
candidatepath=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-o-roi-r1/candidate.json';candidate=json.loads(candidatepath.read_text())
old={x['name']:x for x in parent['files']};new={x['name']:x for x in candidate['files']}
assert old.keys()==new.keys() and len(new)==1699
selected={x['key']+'.png':x for x in plan['entries']};unchanged=0;changed=[]
for name,row in new.items():
    assert sha(row['composed_path'])==row['sha256'] and sha(old[name]['composed_path'])==old[name]['sha256']
    if name not in selected:
        assert row['sha256']==old[name]['sha256'];unchanged+=1;continue
    entry=selected[name]
    with Image.open(row['composed_path']) as im:a=np.array(im)
    with Image.open(old[name]['composed_path']) as im:b=np.array(im)
    with Image.open(entry['image']['path']) as im:source=np.array(im)
    assert a.shape==b.shape==source.shape==(2048,2048,4)
    x0,y0,x1,y1=[x*8 for x in entry['roi_overlay']['uv']]
    outside=np.ones((2048,2048),bool);outside[y0:y1,x0:x1]=False
    assert np.array_equal(a[outside],b[outside]) and np.array_equal(a[y0:y1,x0:x1],source[y0:y1,x0:x1])
    assert np.array_equal(a[:,:,3],b[:,:,3]) and set(np.unique(a[:,:,3]))=={127}
    changed.append(dict(key=entry['key'],png_sha256=row['sha256'],dimensions=[2048,2048],outside_rgba_identical=True,alpha_identical=True,roi_matches_frozen=True,rgb_pixels_changed=int(np.any(a[:,:,:3]!=b[:,:,:3],axis=2).sum())))
assert unchanged==1697 and len(changed)==2 and not candidate['production_installed'] and not candidate['live_visual_accepted']
rc=json.loads((n/'region-o-roi-composition-r1/rc.json').read_text())
assert rc['rc']==0 and rc['child_exit_code']==0 and rc['tree_absent']
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,total_pages=1699,unchanged_pngs=unchanged,changed_pages=changed,parent_unchanged=True,candidate_sha256=sha(candidatepath),composition_child_pid=rc['child_pid'],composition_child_creation_unix=rc['child_create_time'],composition_exit=rc['rc'],composition_seconds=rc['elapsed_s'],composition_tree_absent=True,gpu_run=False,game_run=False,installed=False,live_accepted=False,native_runtime_admission_not_rerun=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
