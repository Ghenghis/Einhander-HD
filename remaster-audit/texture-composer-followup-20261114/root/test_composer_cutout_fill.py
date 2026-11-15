"""CPU checks of invisible-RGB fill, pin rejection and alpha/visible-RGB guards."""
from pathlib import Path
import ctypes,datetime,hashlib,json,psutil,shutil,sys
import numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
sys.path.insert(0,str(r/'remaster-audit'));import build_stage1_frozen_candidate as composer
out=n/'composer-cutout-fill-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector/expand33/20261114T135902Z'
policy=dict(method='cm_fill_cutout_rgb-v2b',**{name:dict(path=str(run/file),sha256=sha(run/file)) for name,file in [('library','class_mip.dll'),('source','class_mip.c'),('header','class_mip.h'),('build_receipt','result.json')]})
fill=composer.load_cutout_rgb_fill(policy);cases=[]
def record(name):cases.append(dict(case=name,passed=True))
assert composer.load_cutout_rgb_fill(None) is None;record('default_no_library')
bad=dict(policy,library=dict(policy['library'],sha256='0'*64))
try:composer.load_cutout_rgb_fill(bad)
except ValueError:record('wrong_library_pin_rejected')
else:raise AssertionError('Bad library pin accepted')
a=np.zeros((5,5,4),np.uint8);a[2,2]=[220,100,30,127];a[2,3]=[100,140,200,255];image=Image.fromarray(a)
b,info=composer.apply_cutout_rgb_fill(image,fill[1]);b=np.array(b);mask=a[:,:,3]!=0
assert info['rgb_pixels_changed']>0 and np.array_equal(a[:,:,3],b[:,:,3]) and np.array_equal(a[:,:,:3][mask],b[:,:,:3][mask]);record('black_cutout_filled_alpha_visible_rgb_preserved')
c,info2=composer.apply_cutout_rgb_fill(Image.fromarray(b),fill[1]);assert np.array_equal(np.array(c),b);record('fill_idempotent')
opaque=np.full((2,2,4),127,np.uint8)
def forbidden(*args):raise AssertionError('Opaque page called fill')
c,info3=composer.apply_cutout_rgb_fill(Image.fromarray(opaque),forbidden);assert not info3['applied'] and np.array_equal(np.array(c),opaque);record('opaque_page_skips_function')
zero=np.zeros((2,2,4),np.uint8);c,_=composer.apply_cutout_rgb_fill(Image.fromarray(zero),fill[1]);assert np.array_equal(np.array(c),zero);record('all_cutout_no_visible_colour_invented')
nonclass=a.copy();nonclass[0,0,3]=1
try:composer.apply_cutout_rgb_fill(Image.fromarray(nonclass),fill[1])
except ValueError:record('noncategorical_alpha_rejected')
else:raise AssertionError('Noncategorical alpha accepted')
for label,index in [('alpha_mutation',3),('visible_rgb_mutation',(2*5+2)*4)]:
    def mutate(pointer,w,h):
        raw=(ctypes.c_uint8*(w*h*4)).from_address(pointer);raw[index]=(raw[index]+1)%256;return 1
    try:composer.apply_cutout_rgb_fill(image,mutate)
    except ValueError:record(label+'_rejected')
    else:raise AssertionError('Mutating fill accepted')
assert np.array_equal(np.array(image),a);record('original_image_unchanged')
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,cases=cases,cpu_cases=len(cases),policy=policy,source_sha256=sha(r/'remaster-audit/build_stage1_frozen_candidate.py'),below_normal=True,cpu_affinity=me.cpu_affinity(),gpu_run=False,composition_run=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'executed-test.py');shutil.copy2(r/'remaster-audit/build_stage1_frozen_candidate.py',out/'executed-source.py');print(json.dumps(report))
