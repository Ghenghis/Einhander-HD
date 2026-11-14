"""Materialize a fresh, reviewable v6 replay recipe without running its compiler."""
from pathlib import Path
import hashlib
n=Path(__file__).resolve().parent
source=n/'verify_v5r2_cpu.py'
s=source.read_text(encoding='utf-8')
def replace(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a))
    s=s.replace(a,b)
replace("renderer-v61-classmip-v5-r2'","renderer-v61-classmip-v6'")
replace("v5r2-cpu-verification-r1'","v6-cpu-verification-r1'")
replace('5f96e71566792816917afc39827e04a9227fe9e321617e4d554ff527e207a0be','33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0')
replace('bb270f8c91891ab9bc72a698624817057400417ce667444caccd43eb649848a5','904cc6bc33510f1e6c205d5a7201f7e81875e71f19120b3a7ae967d5ed2b8af9')
replace('assert pins==874','assert pins==1111')
replace('20261114T131112Z','20261114T142204Z')
replace("rd/'glue/glue.c',", "rd/'glue/glue.c',rd/'glue/hd_texture_identity.h',")
replace("if not k.startswith(('PSXRECOMP_HD_CLASS_MIPS','PSXRECOMP_HD_RGB_EDGES'))", "if not k.startswith(('PSXRECOMP_HD_CLASS_MIPS','PSXRECOMP_HD_RGB_EDGES','PSXRECOMP_HD_DECODE_IDENTITY'))")
replace("me.cpu_affinity(me.cpu_affinity()[-1:])","me.cpu_affinity([15])")
s=s.replace('7520','7534')
replace("for i,(mode,args,e) in enumerate(cases):", "cases += [('rgbid',rbase+['136','1'],env(**rgbdir,PSXRECOMP_HD_RGB_EDGES='1',PSXRECOMP_HD_DECODE_IDENTITY='1')),('rgbdir',rbase+['136','1'],env(**rgbdir,PSXRECOMP_HD_RGB_EDGES='1',PSXRECOMP_HD_DECODE_IDENTITY='true'))]\nfor i,(mode,args,e) in enumerate(cases):")
replace('assert len(cases)==14 and total==352,total','assert len(cases)==16 and total>=400,total')
replace('glue_cases=14','glue_cases=16')
replace("assert (marker.read_bytes() if marker.exists() else None)==before", '''# Rebuild the actual worker implementation and its harness on one CPU; no retained binary is executed.
pk=rd/'pack-v6';basepack=n/'v6-pack-base-from-v48';pt=rd/'pack-test'
run('compile-pack-stb',[cc,'-std=c11','-O1','-c','-I'+str(basepack/'third_party'),str(rd/'inputs/stb_impl.c'),'-o',str(out/'stb_impl.o')])
cxx=str(Path(cc).with_name('clang++.exe'))
run('compile-pack',[cxx,'-std=c++17','-O1','-Wall','-Wextra','-I'+str(pk),'-I'+str(basepack/'include'),'-I'+str(basepack/'src'),str(pk/'hd_texture_pack.cpp'),str(rd/'inputs/pack_identity_test.cpp'),str(out/'stb_impl.o'),'-o',str(out/'pack_identity_test.exe')])
for label,mode,e in [('on','on',env(PSXRECOMP_HD_DECODE_IDENTITY='1')),('off-unset','off',env()),('off-true','off',env(PSXRECOMP_HD_DECODE_IDENTITY='true'))]:
    run('pack-'+label,[str(out/'pack_identity_test.exe'),mode,str(pt/'pack'),str(pt/'expected.tsv')],e)
packtotal=sum(int(re.search(r'checks (\\d+) failures 0',x).group(1)) for row in rows if row['label'].startswith('pack-') for x in row['stdout_tail'] if re.search(r'checks (\\d+) failures 0',x))
assert packtotal==92,packtotal
assert (marker.read_bytes() if marker.exists() else None)==before''')
replace('glue_checks=total,','glue_checks=total,pack_checks=packtotal,pack_source_recompiled=True,')
target=n/'verify_v6_cpu.py'
assert not target.exists()
target.write_text(s,encoding='utf-8',newline='\n')
compile(s,str(target),'exec')
print(str(target),hashlib.sha256(target.read_bytes()).hexdigest())
