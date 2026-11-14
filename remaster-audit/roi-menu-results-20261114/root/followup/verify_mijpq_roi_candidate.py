"""Independent final readback against both the O parent and the original baseline."""
from pathlib import Path
import datetime,hashlib,json,os,psutil
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'mijpq-roi-candidate-verification-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([int(__import__('sys').argv[1])])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=json.loads((n/'mijpq-roi-plan-r1.json').read_text());parent=json.loads(Path(plan['parent']['path']).read_text())
original=json.loads((r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-rise-f32-r1/candidate.json').read_text())
file=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-mijpq-roi-r1/candidate.json';final=json.loads(file.read_text())
old={x['name']:x for x in parent['files']};base={x['name']:x for x in original['files']};new={x['name']:x for x in final['files']}
assert new.keys()==old.keys()==base.keys() and len(new)==1699
selected={x['key']+'.png':x for x in plan['entries']};rows=[];unchanged=0;original_unchanged=0
for name,row in new.items():
    assert sha(row['composed_path'])==row['sha256'] and sha(old[name]['composed_path'])==old[name]['sha256']
    assert sha(base[name]['composed_path'])==base[name]['sha256']
    if row['sha256']==base[name]['sha256']:original_unchanged+=1
    if name not in selected:
        assert row['sha256']==old[name]['sha256'];unchanged+=1;continue
    entry=selected[name]
    with Image.open(row['composed_path']) as im:a=np.array(im)
    with Image.open(old[name]['composed_path']) as im:b=np.array(im)
    with Image.open(entry['image']['path']) as im:source=np.array(im)
    assert a.shape==b.shape==source.shape==(2048,2048,4)
    l,t,right,bottom=entry['roi_overlay']['uv'];x0,y0,x1,y1=l*8,t*8,right*8,bottom*8
    outside=np.ones((2048,2048),bool);outside[y0:y1,x0:x1]=False
    assert np.array_equal(a[outside],b[outside]) and np.array_equal(a[y0:y1,x0:x1],source[y0:y1,x0:x1])
    native=entry['native_source'];words=Path(native['source_words']['path']).read_bytes();clut=Path(native['source_clut']['path']).read_bytes()
    assert hashlib.sha256(words).hexdigest()==native['source_words']['sha256'] and hashlib.sha256(clut).hexdigest()==native['source_clut']['sha256']
    raw=np.frombuffer(words,dtype='<u2').reshape(256,64)
    indices=((raw[:,:,None]>>np.array([0,4,8,12],dtype=np.uint16))&15).reshape(256,256)
    colors=np.frombuffer(clut,dtype='<u2');classes=np.where(colors==0,0,np.where(colors&0x8000,255,127)).astype(np.uint8)[indices[t:bottom,l:right]]
    alpha=np.repeat(np.repeat(classes,8,axis=0),8,axis=1)
    assert np.array_equal(a[y0:y1,x0:x1,3],alpha)
    rows.append(dict(key=entry['key'],png_sha256=row['sha256'],outside_rgba_identical=True,roi_matches_frozen=True,native_alpha_every_pixel_equal=True,rgba_pixels_changed=int(np.any(a!=b,axis=2).sum()),alpha_pixels_changed=int((a[:,:,3]!=b[:,:,3]).sum())))
assert unchanged==1691 and original_unchanged==1689 and len(rows)==8
assert all(new[name]['sha256']==old[name]['sha256'] for name in ['95A3BCF8-60245B3A.png','95A3BCF8-07A9568D.png'])
assert not final['production_installed'] and not final['live_visual_accepted']
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,total_pages=1699,unchanged_from_o_parent=1691,unchanged_from_original_parent=1689,o_pages_preserved=True,source_alpha_exact_in_all_8_new_rois=True,changed_pages=rows,candidate_sha256=sha(file),all_parent_hashes_unchanged=True,gpu_run=False,game_run=False,installed=False,live_accepted=False,pq_freeze_scheduling_compliance=False,pq_scheduling_failure_preserved=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
