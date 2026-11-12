"""Extract pristine disc files and validated TIMs using the project's ISO reader.

Source BIN is opened read-only. Raw movie sectors are retained separately so
XA/Form2 video/audio payloads are not truncated by the ISO 2048-byte view.
"""
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image

sys.path.insert(0, 'C:/github/Einhander/windows-x64/psxrecomp/tools')
from extract_overlays import DiscReader, enumerate_files

SOURCE=Path('C:/github/Einhander/ROM/Einhander (USA).bin')
ROOT=Path('C:/github/REMASTER_STAGING/disc_stock')
FILES=ROOT/'files'
TIMS=ROOT/'tim_images'


def file_sha(path):
    with path.open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()


def validate_tim(data,offset):
    if offset+20>len(data):return None
    flags=struct.unpack_from('<I',data,offset+4)[0]
    if flags not in (0,1,2,3,8,9):return None
    bpp=flags&7;cursor=offset+8;palette=None
    if flags&8:
        if cursor+12>len(data):return None
        length,x,y,width,height=struct.unpack_from('<IHHHH',data,cursor)
        if not (0<width<=1024 and 0<height<=512 and x<1024 and y<512):return None
        if length!=12+width*height*2 or cursor+length>len(data):return None
        colors=16 if bpp==0 else 256
        if width*height<colors or width*height%colors:return None
        palette={'x':x,'y':y,'width':width,'height':height,'bytes':data[cursor+12:cursor+length], 'colors':colors}
        cursor+=length
    if cursor+12>len(data):return None
    length,x,y,width,height=struct.unpack_from('<IHHHH',data,cursor)
    if not(0<width<=1024 and 0<height<=512 and x<1024 and y<512):return None
    if length!=12+width*height*2 or cursor+length>len(data):return None
    pixels=data[cursor+12:cursor+length]
    return {'flags':flags,'bpp':bpp,'x':x,'y':y,'width_words':width,'height':height,
            'palette':palette,'pixels':pixels,'length':cursor+length-offset}


def decode_tim(tim,palette_index):
    bpp=tim['bpp'];width=tim['width_words']*(4 if bpp==0 else 2 if bpp==1 else 1)
    height=tim['height'];data=tim['pixels']
    if bpp==3:
        width=tim['width_words']*2//3
        rows=[data[y*tim['width_words']*2:y*tim['width_words']*2+width*3] for y in range(height)]
        return Image.frombytes('RGB',(width,height),b''.join(rows)).convert('RGBA'),0
    if bpp<2:
        if tim['palette'] is None:return None,None
        colors=tim['palette']['colors'];start=palette_index*colors*2
        paldata=tim['palette']['bytes'][start:start+colors*2]
        palette=struct.unpack('<'+'H'*colors,paldata)
        if bpp==0:words=[palette[(value>>shift)&15] for value in data for shift in (0,4)]
        else:words=[palette[value] for value in data]
        palhash=zlib.crc32(paldata)&0xffffffff
    else:
        words=struct.unpack('<'+'H'*(width*height),data);palhash=0
    rgba=bytearray(width*height*4)
    for index,value in enumerate(words):
        rgba[index*4:index*4+4]=bytes(((value&31)<<3,((value>>5)&31)<<3,((value>>10)&31)<<3,
                                     0 if value==0 else 255 if value&0x8000 else 127))
    return Image.frombytes('RGBA',(width,height),bytes(rgba)),palhash


def main():
    ROOT.mkdir(parents=True,exist_ok=True);FILES.mkdir(exist_ok=True);TIMS.mkdir(exist_ok=True)
    source_stat=SOURCE.stat()
    disc=DiscReader(str(SOURCE),raw=True)
    records=[];textures=[]
    try:
        entries=list(enumerate_files(disc))
        print('ISO9660 files:',len(entries),flush=True)
        for name,lba,size in entries:
            if any(part in ('..','.') or re.search(r'[<>:"\\|?*]',part) for part in Path(name).parts):
                raise ValueError('Unsafe ISO name: '+name)
            destination=(FILES/name).resolve()
            if not destination.is_relative_to(FILES.resolve()):raise ValueError('ISO path escaped output')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and destination.stat().st_size==size:
                data=destination.read_bytes();status='reused extracted file'
            else:
                data=disc.read_file_bytes(lba,size)
                if len(data)!=size:raise ValueError('Truncated file '+name)
                destination.write_bytes(data);status='extracted'
            row={'iso_path':name,'lba':lba,'logical_bytes':size,'sha256':hashlib.sha256(data).hexdigest(),
                 'output':str(destination),'status':status,'tim_candidates':0,'validated_TIMs':0}
            if name.startswith('MOV') and name.endswith('.STR'):
                raw=ROOT/'raw_movies'/name;raw.parent.mkdir(exist_ok=True)
                count=(size+2047)//2048;raw_size=count*2352
                if not raw.exists() or raw.stat().st_size!=raw_size:
                    with SOURCE.open('rb') as original,raw.open('wb') as target:
                        original.seek(lba*2352);remaining=raw_size
                        while remaining:
                            chunk=original.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('Truncated raw movie '+name)
                            target.write(chunk);remaining-=len(chunk)
                row['raw_movie_path']=str(raw);row['raw_movie_bytes']=raw_size
            # Movie sectors are not standalone texture sheets.
            if not name.startswith('MOV'):
                offset=0
                while True:
                    offset=data.find(b'\x10\x00\x00\x00',offset)
                    if offset<0:break
                    row['tim_candidates']+=1
                    tim=validate_tim(data,offset)
                    if tim:
                        row['validated_TIMs']+=1
                        txhash=zlib.crc32(tim['pixels'])&0xffffffff
                        count=len(tim['palette']['bytes'])//(tim['palette']['colors']*2) if tim['palette'] else 1
                        entry={'file':name,'offset':offset,'length':tim['length'],'bpp':tim['bpp'],
                               'vram':[tim['x'],tim['y']],'width_words':tim['width_words'],
                               'height':tim['height'],'palette_variants':count,'texture_crc32':f'{txhash:08X}',
                               'decoded_files':[]}
                        for pi in range(count):
                            image,palhash=decode_tim(tim,pi)
                            if image is not None:
                                folder=TIMS/name;folder.mkdir(exist_ok=True)
                                path=folder/f'{offset:08X}-P{pi:03d}-{txhash:08X}-{palhash:08X}.png'
                                if not path.exists():image.save(path)
                                entry['decoded_files'].append(str(path))
                        textures.append(entry)
                        offset+=tim['length']
                    else:offset+=4
            records.append(row)
            print(json.dumps({'file':name,'MiB':round(size/2**20,2),'TIMs':row['validated_TIMs'],'status':status}),flush=True)
            (ROOT/'files_manifest.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
            (ROOT/'textures_manifest.json').write_text(json.dumps(textures,indent=2)+'\n',encoding='utf-8')
    finally:disc.close()
    assert SOURCE.stat().st_size==source_stat.st_size and SOURCE.stat().st_mtime_ns==source_stat.st_mtime_ns
    summary={'source':str(SOURCE),'source_open_mode':'read-only','source_size':source_stat.st_size,
             'source_mtime_unchanged':True,'iso_files':len(records),'extracted_logical_bytes':sum(r['logical_bytes'] for r in records),
             'validated_TIMs':len(textures),'decoded_PNGs':sum(len(t['decoded_files']) for t in textures),
             'raw_movie_streams':sum('raw_movie_path' in r for r in records),
             'scope':'Pristine file extraction. Custom archive/compression decoding and runtime mapping may still be needed.'}
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
