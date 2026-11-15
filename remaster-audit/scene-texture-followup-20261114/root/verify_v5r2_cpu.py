"""Independent replay from the new immutable freeze; CPU fixtures and recording GL stubs only."""
from pathlib import Path
import datetime,hashlib,json,os,psutil,re,shutil,struct,subprocess
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
f=r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v5-r2'
out=n/'v5r2-cpu-verification-r1';out.mkdir(exist_ok=False)
shutil.copy2(__file__,out/'executed-runner.py')
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
marker=r/'remaster-audit/comfy-authoring/GPU-RESERVED';before=marker.read_bytes() if marker.exists() else None
assert sha(f/'READY.json')=='5f96e71566792816917afc39827e04a9227fe9e321617e4d554ff527e207a0be'
assert sha(f/'SHA256SUMS.txt')=='bb270f8c91891ab9bc72a698624817057400417ce667444caccd43eb649848a5'
pins=0;allzero=[]
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
    h,name=line.split('  ',1);file=(f/name).resolve();assert file.is_relative_to(f.resolve()) and sha(file)==h,name;pins+=1
    data=file.read_bytes()
    if data and not any(data):allzero.append(name)
assert pins==874 and not allzero
rd=f/'host-run/20261114T131112Z';result=json.loads((rd/'result.json').read_text());rows=[]
for file in [f/'src/test_hd_class_mips.c',f/'src/hd_class_mips.inc',rd/'glue/glue_harness.c',rd/'glue/glue.c',rd/'inputs/class_mip.c',rd/'inputs/class_mip.h']:shutil.copy2(file,out/file.name)
cc='C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe'
def run(label,args,env=None):
    x=subprocess.run(args,cwd=out,capture_output=True,text=True,env=env,timeout=30,creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr);rows.append(dict(label=label,args=args,exit=x.returncode,stdout_tail=x.stdout.splitlines()[-8:]));assert x.returncode==0,(label,x.stdout[-2000:],x.stderr[-2000:])
flags=[cc,'-std=c11','-O1','-Wall','-Wextra','-Wno-unused-function','-I'+str(out)]
run('compile-fixture',flags+[str(out/'test_hd_class_mips.c'),str(out/'class_mip.c'),'-o',str(out/'fixture.exe')])
run('fixture',[str(out/'fixture.exe')]);assert any('7520' in x for x in rows[-1]['stdout_tail'])
run('compile-glue',flags+[str(out/'glue_harness.c'),'-o',str(out/'glue.exe')])
key=result['steps']['5-glue']['key'];rgbkey=result['steps']['5-glue']['rgb_key'];opaque='95A3BCF8-60245B3A'
def classargs(k,dir,rgba,count):
    blob=(rd/dir/(k+'.hdcm')).read_bytes();nw,nh,s,L=struct.unpack_from('<4H',blob,16);hw,hh=struct.unpack_from('<2I',blob,24)
    assert len((rd/'glue'/rgba).read_bytes())==hw*hh*4
    return [str(rd/'glue'/rgba),str(hw),str(hh),*k.split('-'),str(nw),str(nh),'2',str(nw),str(L),str(count)]
base=classargs(key,'sidecars','rgba.bin',8)+['1']
op=classargs(opaque,'sidecars-opaque-control','rgba-opaque.bin',1)+['0']
rg=(rd/'sidecars-rgb'/(rgbkey+'.hdrg')).read_bytes();nw,nh=struct.unpack_from('<2H',rg,16);hw,hh=struct.unpack_from('<2I',rg,20)
assert len(rg)==48 and rg[:8]==b'HDCMRG01' and len((rd/'glue/rgba-rgb.bin').read_bytes())==hw*hh*4
rbase=[str(rd/'glue/rgba-rgb.bin'),str(hw),str(hh),*rgbkey.split('-'),str(nw),str(nh),'2',str(nw)]
env0={k:v for k,v in os.environ.items() if not k.startswith(('PSXRECOMP_HD_CLASS_MIPS','PSXRECOMP_HD_RGB_EDGES'))}
classdir=dict(PSXRECOMP_HD_CLASS_MIPS_DIR=str(rd/'sidecars'));rgbdir=dict(PSXRECOMP_HD_RGB_EDGES_DIR=str(rd/'sidecars-rgb'))
def env(**kwargs):return dict(env0,**kwargs)
cases=[('off',base,env()),('badenv',base,env(**classdir,PSXRECOMP_HD_CLASS_MIPS='true',PSXRECOMP_HD_RGB_EDGES='0')),
 ('on',base,env(**classdir,PSXRECOMP_HD_CLASS_MIPS='1',PSXRECOMP_HD_RGB_EDGES='1')),
 ('levels',base,env(**classdir,**rgbdir,PSXRECOMP_HD_CLASS_MIPS='1')),
 ('rgb',base,env(**classdir,PSXRECOMP_HD_RGB_EDGES='1')),
 ('rgb',op,env(PSXRECOMP_HD_CLASS_MIPS_DIR=str(rd/'sidecars-opaque-control'),PSXRECOMP_HD_RGB_EDGES='1')),
 ('badenv',base,env(**rgbdir,PSXRECOMP_HD_RGB_EDGES='true')),
 ('badenv',base,env(PSXRECOMP_HD_RGB_EDGES='1',PSXRECOMP_HD_RGB_EDGES_DIR='')),
 ('badenv',base,env(**rgbdir,PSXRECOMP_HD_CLASS_MIPS='1')),
 ('rgbdir',rbase+['136','1'],env(**rgbdir,PSXRECOMP_HD_RGB_EDGES='1')),
 ('rgbfalse',rbase+['1','1'],env(PSXRECOMP_HD_RGB_EDGES_DIR=str(rd/'sidecars-rgb-false'),PSXRECOMP_HD_RGB_EDGES='1')),
 ('rgbcaps',rbase+['1','1'],env(PSXRECOMP_HD_RGB_EDGES_DIR=str(rd/'sidecars-rgb-caps'),PSXRECOMP_HD_RGB_EDGES='1')),
 ('both',rbase+['2','1']+base[:7]+base[9:11],env(**classdir,PSXRECOMP_HD_RGB_EDGES_DIR=str(rd/'sidecars-rgb-both'),PSXRECOMP_HD_CLASS_MIPS='1',PSXRECOMP_HD_RGB_EDGES='1')),
 ('rgbopaque',op[:9]+['1','0'],env(PSXRECOMP_HD_RGB_EDGES_DIR=str(rd/'sidecars-rgb-opaque'),PSXRECOMP_HD_RGB_EDGES='1'))]
for i,(mode,args,e) in enumerate(cases):run(f'glue-{i:02d}-{mode}',[str(out/'glue.exe'),mode]+args,e)
assert (marker.read_bytes() if marker.exists() else None)==before
total=sum(int(re.search(r'checks (\d+) failures 0',x).group(1)) for row in rows if row['label'].startswith('glue-') for x in row['stdout_tail'] if re.search(r'checks (\d+) failures 0',x))
assert len(cases)==14 and total==352,total
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_files_verified=pins,ready_sha256=sha(f/'READY.json'),manifest_sha256=sha(f/'SHA256SUMS.txt'),all_zero_files=allzero,fixture_checks=7520,glue_cases=14,glue_checks=total,commands=rows,gpu_executed=False,recording_gl_stubs_only=True,mutants_replayed=False,real_page_author_benchmarks_replayed=False,marker_unchanged=True,compiler_sha256=sha(cc),below_normal=True,cpu_affinity=me.cpu_affinity(),passed=True)
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-runner.py');print(json.dumps({k:v for k,v in receipt.items() if k!='commands'}))
