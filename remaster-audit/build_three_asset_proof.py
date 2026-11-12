"""Build a small reversible native-runtime texture proof from verified stock.

Three categories: fighter mechanical atlas, palette-cycled translucent beams,
and the font sheet. Black STP texels remain STP, not ordinary PNG cutouts.
"""
import collections
import hashlib
import json
import shutil
import zlib
from pathlib import Path

from PIL import Image

ROOT = Path('C:/github/REMASTER_STAGING/three_asset_proof')
SOURCES = [ROOT/'source-run/stock/einhander-texture-replacements',
           ROOT/'stock-run/stock/einhander-texture-replacements']
OUT = ROOT/'pack/einhander-texture-replacements'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stock(key):
    for source in SOURCES:
        path = source/(key+'.png')
        if path.exists() and (source/(key+'.source.json')).exists():
            metadata=json.loads((source/(key+'.source.json')).read_text())
            if (metadata['known_words']==metadata['total_words'] and
                metadata['reconstructed_crc32']==key.split('-')[0]):
                return source,path
    raise FileNotFoundError(key)


def verify_stock(source,key):
    metadata = json.loads((source/(key+'.source.json')).read_text())
    raw = (source/(key+'.words.bin')).read_bytes()
    palette = (source/(key+'.clut.bin')).read_bytes()
    valid = (source/(key+'.valid.bin')).read_bytes()
    if not valid or any(v!=1 for v in valid):
        raise ValueError('Incomplete upload cannot be used as a proof source: '+key)
    if f'{zlib.crc32(raw):08X}' != key.split('-')[0]:
        raise ValueError('Texture CRC mismatch: '+key)
    if palette and f'{zlib.crc32(palette):08X}' != key.split('-')[1]:
        raise ValueError('Palette CRC mismatch: '+key)
    # Independently re-decode all indexed words, including STP black 0x8000.
    import struct
    words = struct.unpack('<'+'H'*(len(raw)//2),raw)
    clut = struct.unpack('<'+'H'*(len(palette)//2),palette) if palette else None
    depth = metadata['depth']; rgba = bytearray()
    for word in words:
        values = [clut[(word>>s)&15] for s in (0,4,8,12)] if depth==0 else (
                 [clut[word&255],clut[word>>8]] if depth==1 else [word])
        for value in values:
            rgba.extend(((value&31)<<3,((value>>5)&31)<<3,((value>>10)&31)<<3,
                         0 if value==0 else 255 if value&0x8000 else 127))
    with Image.open(source/(key+'.png')) as image:
        if image.convert('RGBA').tobytes()!=rgba:
            raise ValueError('Independent raw/CLUT decode differs from source PNG: '+key)
    return metadata,raw,palette


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT.parent/'Hashes.ini').touch(exist_ok=True)
    keys = [('mechanical','5CC44E5F-053D9A00'), ('hud_font','DD0B6963-4C1DD349')]
    effects = sorted({p.stem for source in SOURCES for p in source.glob('1FD36785-*.png')})
    keys += [('transparent_effect',key) for key in effects]
    if not effects:
        raise ValueError('No verified translucent beam palettes captured')
    rows = []
    archives = json.loads(Path('C:/github/REMASTER_STAGING/disc_stock/archives/manifest.json').read_text())['entries']
    matched_categories=set()
    for category,key in keys:
        source,path = stock(key)
        metadata,raw,palette = verify_stock(source,key)
        native = Image.open(path).convert('RGBA')
        output = OUT/(key+'.png')
        if category=='mechanical':
            cached=Path('C:/github/REMASTER_STAGING/stage01_city/candidates/ultrasharp16x/einhander-texture-replacements')/path.name
            earlier=Path('C:/github/REMASTER_STAGING/stage01_city/stock/einhander-texture-replacements')/path.name
            with Image.open(earlier) as old:
                if old.convert('RGBA').tobytes()!=native.tobytes():
                    raise ValueError('Cached UltraSharp source does not match current verified stock')
            shutil.copy2(cached,output)
            method='Reused exact-source UltraSharp 16x candidate; no new model pass'
        else:
            factor=8 if category=='transparent_effect' else 16
            native.resize((native.width*factor,native.height*factor),Image.Resampling.NEAREST).save(output)
            method=f'Nearest neighbor {factor}x; exact source RGB and transparency classes'
        with Image.open(output) as result:
            result=result.convert('RGBA')
            expected=native.getchannel('A').resize(result.size,Image.Resampling.NEAREST)
            if result.getchannel('A').tobytes()!=expected.tobytes():
                raise ValueError('Transparency class map changed: '+key)
            if category!='mechanical' and result.resize(native.size,Image.Resampling.NEAREST).tobytes()!=native.tobytes():
                raise ValueError('Deterministic RGB round-trip failed: '+key)
            size=list(result.size)
        matches=[]
        if category not in matched_categories:
            matched_categories.add(category)
            for entry in archives:
                data=Path(entry['output']).read_bytes()
                pixel_offset=data.find(raw);palette_offset=data.find(palette) if palette else -1
                if pixel_offset>=0 or palette_offset>=0:
                    matches.append({'archive':entry['pack'],'entry':entry['entry'],
                                    'entry_sha256':entry['sha256'],
                                    'pixel_offset':pixel_offset if pixel_offset>=0 else None,
                                    'clut_offset':palette_offset if palette_offset>=0 else None})
        rows.append({'category':category,'key':key,'source':str(path),'source_pixel_sha256':sha(native.tobytes()),
                     'source_size':list(native.size),'output':str(output),'output_size':size,
                     'output_sha256':sha(output.read_bytes()),'method':method,
                     'source_metadata':metadata,'raw_words_sha256':sha(raw),'raw_clut_sha256':sha(palette),
                     'source_crc_verified':True,'source_decode_verified':True,'mask_exact_nearest_verified':True,
                     'source_alpha_counts':dict(collections.Counter(native.getchannel('A').tobytes())),
                     'archive_matches':matches,'in_game':'pending actual draw receipt'})
    manifest={'format':1,'purpose':'Isolated functional proof; visual acceptance remains separate',
              'categories':['mechanical','transparent_effect','hud_font'],
              'effect_scope':'Palette-cycled Stage 1 light beams, STP set including black texels, primitive semi mode 0 (half blend).',
              'palette_scope':'Observed beam variants only; full-game palette coverage is not claimed',
              'production_installed':False,'assets':rows}
    (ROOT/'pack/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'replacement_pngs':len(rows),'category_counts':dict(collections.Counter(x['category'] for x in rows)),
                      'mask_checks_passed':len(rows),'pack':str(OUT.parent)},indent=2))


if __name__=='__main__':main()
