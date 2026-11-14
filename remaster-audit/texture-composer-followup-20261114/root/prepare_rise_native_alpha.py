"""Preserve the failed exact-alpha assumption and create a separate native-alpha option."""
from pathlib import Path
import ctypes,datetime,hashlib,json,psutil,shutil,time,zlib
import numpy as np
from PIL import Image
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
out=n/'rise-native-alpha-r1';out.mkdir(exist_ok=False);(out/'palettes').mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector/expand33/20261114T135902Z'
manifest=source/'result.json';assert sha(manifest)=='d4379b41b64bbeff1e38fb965a93a5880f677e3779b716859f60ba8fce1326ec'
data=json.loads(manifest.read_text());pd=json.loads((e/'world-integrated-crisp-v4/candidate.json').read_text());pack=Path(pd['launches']['candidate']['environment_overrides']['PSXRECOMP_HD_TEXTURE_ROOT'])
shutil.copy2(n/'compose_rise_f32.py',out/'compose-precheck-FAILED.py')
(out/'failed-precheck.json').write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),tool_chunk='f02d34',command='python -X utf8 remaster-audit/runtime-review/gpu-texture-remix-20261114/compose_rise_f32.py',exit=1,failure='AssertionError: 82831823-06BDD2F5 exact-native-nearest-alpha comparison',candidate_created=False,reason='The v5 polygon silhouette intentionally refines native-nearest alpha inside the allowed strict class rules. Palette class-map equality does not imply all HD alpha pixels equal native-nearest. Earlier class audits remain valid; no source repair occurred.'),indent=2)+'\n')
lib=ctypes.CDLL(str(source/'class_mip.dll'))
class Report(ctypes.Structure):_fields_=[(x,ctypes.c_uint64) for x in ('pixels','cells','r1_centre_bad','r2_displaced_px','r3_uniform_bad_px','r4_island_px','r5_fringe_px','cells_bad','pinhole_cells','nonclass_px')]
lib.cm_fill_cutout_rgb.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int];lib.cm_fill_cutout_rgb.restype=ctypes.c_int64
lib.cm_validate.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.POINTER(Report)]
rows=[];t=time.monotonic()
for item in data['rows']:
    key=item['key'];src=source/'palettes'/item['png'];assert sha(src)==item['sha256']
    wb=(pack/(key+'.words.bin')).read_bytes();cb=(pack/(key+'.clut.bin')).read_bytes();assert len(wb)==1024 and len(cb)==32 and f'{zlib.crc32(wb):08X}-{zlib.crc32(cb):08X}'==key
    words=np.frombuffer(wb,dtype='<u2').reshape(32,16);idx=((words[:,:,None]>>np.array([0,4,8,12],dtype=np.uint16))&15).reshape(32,64);clut=np.frombuffer(cb,dtype='<u2')
    native=np.ascontiguousarray(np.where(clut==0,0,np.where(clut&0x8000,255,127)).astype(np.uint8)[idx]);alpha=np.repeat(np.repeat(native,16,axis=0),16,axis=1)
    with Image.open(src) as im:before=np.array(im.convert('RGBA'))
    assert before.shape==(512,1024,4)
    a=before.copy();a[:,:,3]=alpha;assert lib.cm_fill_cutout_rgb(a.ctypes.data,1024,512)>=0
    common=(before[:,:,3]!=0)&(alpha!=0);assert np.array_equal(before[:,:,:3][common],a[:,:,:3][common])
    rep=Report();lib.cm_validate(a.ctypes.data,1024,512,native.ctypes.data,64,32,16,ctypes.byref(rep))
    counters={x:getattr(rep,x) for x,_ in Report._fields_};assert all(counters[x]==0 for x in counters if x not in ('pixels','cells'))
    dest=out/'palettes'/item['png'];Image.fromarray(a).save(dest)
    rows.append(dict(key=key,png=dest.name,sha256=sha(dest),source_png_sha256=sha(src),alpha_changed_vs_approved_vector_pixels=int((before[:,:,3]!=alpha).sum()),newly_visible_vs_approved_vector=int(((before[:,:,3]==0)&(alpha!=0)).sum()),newly_hidden_vs_approved_vector=int(((before[:,:,3]!=0)&(alpha==0)).sum()),common_visible_rgb_identical=True,alpha_exact_native=True,strict=counters,limits='Newly visible pixels retain the previous cutout RGB fill; not new hand-authored detail. No live acceptance.'))
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,summary=dict(palettes=len(rows),all_alpha_exact_native=True,all_strict_zero=True,approved_vector_inputs_unchanged=True,common_visible_rgb_unchanged=True,seconds=round(time.monotonic()-t,3)),validator_dll_sha256=sha(source/'class_mip.dll'),source_manifest_sha256=sha(manifest),gpu_run=False,installed=False,live_accepted=False,scope='Separate native-nearest-alpha alternative; original approved vector outputs preserved. Native alpha change counts compare against vector v5, not original game alpha.')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps(dict(summary=result['summary'],first_key=rows[0],result_sha256=sha(out/'result.json'))))
