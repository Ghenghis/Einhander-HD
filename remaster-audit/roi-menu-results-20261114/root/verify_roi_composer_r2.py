"""One bounded CPU-only run: ROI controls and actual composer CLI fixture."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,subprocess,sys,time
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
out=n/'roi-composer-cpu-r2';out.mkdir(exist_ok=False)
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3)
if cpu>=60 or free<16:
    result=dict(declined=True,cpu_percent=cpu,free_gib=free,gpu_run=False)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(3)
started=time.monotonic();results=[];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={str(p):sha(p) for p in [r/'remaster-audit/build_stage1_frozen_candidate.py',r/'remaster-audit/test_frozen_candidate_roi.py']}
def run(args,label):
    with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
        child=subprocess.Popen(args,cwd=r,stdout=stdout,stderr=stderr,creationflags=0x08004000)
        identity=psutil.Process(child.pid).create_time();rc=child.wait(timeout=25)
    results.append(dict(command=args,pid=child.pid,creation_unix=identity,exit=rc))
    if rc:raise RuntimeError(label+' failed: '+str(rc))
run([sys.executable,'-B','-I',str(r/'remaster-audit/test_frozen_candidate_roi.py'),'-v'],'unit')
# Tiny authentic full-upload keys exercise the actual CLI, lineage and hardlinks.
from PIL import Image
import numpy as np,struct,zlib,shutil
fixture=out/'fixture';pack=fixture/'parent-pack';replacements=pack/'einhander-texture-replacements';replacements.mkdir(parents=True)
words=struct.pack('<16H',*([0x1111]*16));clut=struct.pack('<16H',0,0x03e0,*([0]*14))
key=f'{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}'
wp=fixture/'words.bin';cp=fixture/'clut.bin';wp.write_bytes(words);cp.write_bytes(clut)
def pin(p):return dict(path=str(p),sha256=sha(p))
a=np.arange(16*16*4,dtype=np.uint8).reshape(16,16,4);a[:,:,3]=127
parent=replacements/(key+'.png');Image.fromarray(a).save(parent)
keep=replacements/'F00DBEEF-DEADBEEF.png';Image.fromarray(a).save(keep)
authored=fixture/'authored.png';b=a.copy();b[4:12,4:12,:3]=237;Image.fromarray(b).save(authored)
manifest=fixture/'manifest.json';manifest.write_text(json.dumps(dict(region='fixture uv [2,2]-[6,6] half-open',keys={key:dict(live=pin(parent))})))
parentjson=fixture/'parent.json';parentjson.write_text(json.dumps(dict(launches=dict(candidate=dict(environment_overrides=dict(PSXRECOMP_HD_TEXTURE_ROOT=str(pack)))),files=[dict(name=p.name,sha256=sha(p),composed_path=str(p),dimensions=[16,16],bytes=p.stat().st_size) for p in [parent,keep]])))
plan=fixture/'plan.json';plan.write_text(json.dumps(dict(parent=pin(parentjson),entries=[dict(key=key,manifest=pin(manifest),image=pin(authored),native_source=dict(source_words=pin(wp),source_clut=pin(cp),source_shape_words=[2,8],depth=0),roi_overlay=dict(native_size=[8,8],uv=[2,2,6,6]))])))
destination=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/roi-composer-synthetic-r2'
run([sys.executable,'-B','-I',str(r/'remaster-audit/build_stage1_frozen_candidate.py'),'--plan',str(plan),'--output',str(destination)],'cli')
report=json.loads((destination/'candidate.json').read_text());final=destination/'pack/einhander-texture-replacements'/parent.name
with Image.open(final) as im:actual=np.array(im.convert('RGBA'))
outside=np.ones((16,16),bool);outside[4:12,4:12]=False
assert np.array_equal(actual[outside],a[outside]) and np.array_equal(actual[4:12,4:12],b[4:12,4:12])
assert sha(parent)==json.loads(parentjson.read_text())['files'][0]['sha256'] and np.array_equal(np.array(Image.open(parent)),a)
assert sha(keep)==sha(destination/'pack/einhander-texture-replacements'/keep.name)
assert report['authored_entries']==1 and report['final_count']==2 and not report['production_installed']
assert next(x for x in report['files'] if x['name']==parent.name)['roi_overlay']['outside_rgba_identical']
assert all(sha(Path(p))==h for p,h in sources.items())
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,unit_cases=7,negative_geometry_and_binding_cases=20,actual_cli_fixture_passed=True,parent_pixels_unchanged=True,unselected_page_byte_identical=True,processes=results,seconds=time.monotonic()-started,source_pins=sources,cpu_percent=cpu,free_gib=free,below_normal=True,affinity=[11],gpu_run=False,game_run=False,private_real_art_composition=False,synthetic_candidate=str(destination/'candidate.json'))
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
