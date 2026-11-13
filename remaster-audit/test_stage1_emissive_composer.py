"""Exercise real composition against tiny synthetic masked immutable parents."""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib
from PIL import Image
from build_stage1_frozen_candidate import EVIDENCE,sha

def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prefix',required=True);a=p.parse_args()
    assert re.fullmatch('[a-z0-9-]+',a.prefix)
    root=EVIDENCE/(a.prefix+'-fixtures');assert root.resolve().parent==EVIDENCE.resolve() and not root.exists();root.mkdir()
    pack=root/'pack';images=pack/'einhander-texture-replacements';images.mkdir(parents=True)
    words=struct.pack('<H',0x1111)*4;clut=struct.pack('<16H',0,*([0x1CE7]*15))
    source_key=f'{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}'
    key=f'{zlib.crc32(words[2:6]):08X}-{zlib.crc32(clut):08X}'
    w=root/'words.bin';c=root/'clut.bin';w.write_bytes(words);c.write_bytes(clut)
    original=images/(key+'.png');old_mask=images/(key+'-emissive.png')
    Image.new('RGBA',(8,4),(10,20,30,127)).save(original);Image.new('L',(8,4),0).save(old_mask)
    (pack/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n')
    parent=root/'candidate.json';write(parent,dict(files=[dict(name=original.name,composed_path=str(original),sha256=sha(original),dimensions=[8,4],bytes=original.stat().st_size)],
        final_count=1,emissive_files=[dict(name=old_mask.name,composed_path=str(old_mask),sha256=sha(old_mask),dimensions=[8,4],bytes=old_mask.stat().st_size)],
        launches=dict(candidate=dict(environment_overrides=dict(PSXRECOMP_HD_TEXTURE_ROOT=str(pack))))))
    rgb=root/'new.png';mask=root/'new-emissive.png';Image.new('RGBA',(8,8),(100,120,140,127)).save(rgb)
    im=Image.new('L',(8,8));im.putdata([y*32 for y in range(8) for x in range(8)]);im.save(mask)
    manifest=root/'manifest.json';write(manifest,dict(status='synthetic fixture'))
    row=dict(key=source_key,manifest=ref(manifest),image=ref(rgb),emissive=ref(mask),image_space_native=[4,4],image_uv=[0,1,4,3],
        exact=dict(source_words=ref(w),source_clut=ref(c),source_shape_words=[1,4],depth=0,page_xy=[384,0],clut_xy=[800,480],uv=[0,1,4,3]))
    pins=[ref(original),ref(old_mask)];results=[]
    for label,invalid in [('valid',None),('bad-size','L'),('bad-mode','RGB')]:
        current=dict(row)
        if invalid:
            bad=root/(label+'.png');Image.new(invalid,(4,4) if label=='bad-size' else (8,8)).save(bad);current['emissive']=ref(bad)
        plan=root/(label+'-plan.json');write(plan,dict(parent=ref(parent),entries=[current]))
        out=EVIDENCE/(a.prefix+'-'+label);assert not out.exists()
        command=[sys.executable,str(Path(__file__).with_name('build_stage1_frozen_candidate.py')),'--plan',str(plan),'--output',str(out)]
        result=subprocess.run(command,capture_output=True,text=True);(root/(label+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==(1 if invalid else 0),(label,result.stdout,result.stderr)
        assert all(sha(Path(x['path']))==x['sha256'] for x in pins),'Immutable parent altered'
        if invalid:assert not (out/'candidate.json').exists()
        else:
            composed=json.loads((out/'candidate.json').read_text());assert composed['final_count']==1 and len(composed['emissive_files'])==1
            f=composed['emissive_files'][0];assert f['name']==key+'-emissive.png' and Path(f['composed_path']).is_relative_to(out)
            with Image.open(f['composed_path']) as got,Image.open(mask) as source:
                assert got.mode=='L' and got.size==(8,4) and got.tobytes()==source.crop((0,2,8,6)).tobytes()
            assert sha(Path(f['composed_path']))==f['sha256']
        results.append(dict(case=label,exit_code=result.returncode,expected_rejection=bool(invalid),parent_unchanged=True,passed=True))
    write(root/'results.json',dict(cases=results,all_passed=True));print(json.dumps(dict(evidence=str(root),cases=results)))

if __name__=='__main__':main()
