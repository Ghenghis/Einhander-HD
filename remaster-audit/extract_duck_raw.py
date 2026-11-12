"""Recover original 16-bit uploads from lossless DuckStation VRAM-write PNGs.

Only valid with DumpVRAMWriteForceAlphaChannel=false. Every output must match
the source XXH3-128 name, including all index words and STP bits. These are
native uploads, not ordinary color textures to be sent through an RGB model.
"""
import collections
import hashlib
import json
import struct
from pathlib import Path
import xxhash
from PIL import Image

ROOT=Path('C:/github/REMASTER_STAGING/duckstation-proof')
SOURCE=ROOT/'runtime/textures/SCUS-94243/dumps'
OUT=ROOT/'native-raw'

def recover(path):
    with Image.open(path) as loaded:
        image=loaded.convert('RGBA')
        values=[(r>>3)|((g>>3)<<5)|((b>>3)<<10)|(0x8000 if a>=128 else 0)
                for r,g,b,a in image.getdata()]
        raw=struct.pack('<'+'H'*len(values),*values)
        actual=xxhash.xxh3_128_hexdigest(raw).upper()
        expected=path.stem.removeprefix('vram-write-')
        if actual!=expected:raise ValueError('Lossless native-word verification failed: '+path.name)
        return raw,image.size,dict(collections.Counter(image.getchannel('A').tobytes()))

def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=[]
    for path in sorted(SOURCE.glob('vram-write-*.png')):
        raw,size,alpha=recover(path);dest=OUT/(path.stem+'.words.bin')
        if dest.exists() and dest.read_bytes()!=raw:raise ValueError('Refusing to replace different raw upload')
        if not dest.exists():dest.write_bytes(raw)
        rows.append({'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'words_file':str(dest),'raw_sha256':hashlib.sha256(raw).hexdigest(),
                     'width_words':size[0],'height':size[1],'word_count':len(raw)//2,
                     'xxh3_128_verified':True,'stp_preserved':True,'png_bit15_alpha_counts':alpha,
                     'possible_clut':size[1]==1 and size[0] in (16,256),
                     'classification':'native upload; possible_clut is a dimension hint, not an assigned game role'})
    report={'format':1,'source':str(SOURCE),'raw_uploads':len(rows),
            'all_xxh3_128_verified':all(r['xxh3_128_verified'] for r in rows),
            'source_files_modified':False,'uploads':rows}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'native_uploads':len(rows),'palette_dimension_candidates':sum(r['possible_clut'] for r in rows),
                      'all_raw_hashes_verified':True,'manifest':str(OUT/'manifest.json')},indent=2))

if __name__=='__main__':main()
