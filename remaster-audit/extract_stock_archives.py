"""Bounded Einhander BININDEX/BINPACK extraction with lossless TIM sidecars.

Archive layout reference: Xeeynamo/einhander/einpack.go (MIT).
Sources are read-only. Existing output must be byte-identical to be reused.
Neither archive entries nor TIM files imply complete runtime texture coverage.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image
from extract_disc_stock import validate_tim, decode_tim

ALIGN = 2048


def digest(data):
    return hashlib.sha256(data).hexdigest()


def preserve(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Refusing to overwrite different output: {path}')
    else:
        path.write_bytes(data)


def entries(index, pack_sizes):
    if not index or len(index) % ALIGN or len(index) // ALIGN != len(pack_sizes):
        raise ValueError('Index must contain exactly one 2048-byte table per pack')
    result = []
    for pack, size in enumerate(pack_sizes):
        terminated = False
        for ordinal in range(ALIGN // 4):
            offset, length = struct.unpack_from('<HH', index, pack * ALIGN + ordinal * 4)
            if length == 0:
                terminated = True
                break
            offset *= ALIGN
            length *= ALIGN
            if offset + length > size:
                raise ValueError(f'Out-of-bounds pack {pack}, entry {ordinal}')
            result.append((pack, ordinal, offset, length))
        if not terminated:
            raise ValueError(f'No terminator in pack {pack} index table')
    return result


def write_tim(data, offset, tim, folder):
    base = folder / f'{offset:08X}'
    preserve(base.with_suffix('.tim'), data[offset:offset + tim['length']])
    preserve(Path(str(base) + '.pixels.bin'), tim['pixels'])
    palette = tim['palette']
    if palette:
        preserve(Path(str(base) + '.clut.bin'), palette['bytes'])
    count = len(palette['bytes']) // (palette['colors'] * 2) if palette else 1
    variants = []
    for pi in range(count):
        image, palhash = decode_tim(tim, pi)
        if image is None:
            continue
        # This PNG carries the recomp contract, not ordinary opacity.
        output = Path(str(base) + f'-P{pi:03d}-{palhash:08X}.png')
        if output.exists():
            with Image.open(output) as existing:
                if existing.size != image.size or existing.convert('RGBA').tobytes() != image.tobytes():
                    raise ValueError(f'Different existing PNG: {output}')
        else:
            image.save(output)
        alpha = image.getchannel('A')
        classes = alpha.point(lambda x: 0 if x == 0 else 2 if x == 255 else 1)
        mask = Path(str(base) + f'-P{pi:03d}.classes.png')
        if not mask.exists():
            classes.save(mask)
        variants.append({'palette': pi, 'clut_crc32': f'{palhash:08X}',
                         'replacement_png': str(output), 'class_map': str(mask),
                         'class_counts': {str(k): v for v, k in classes.getcolors(256)},
                         'size': list(image.size)})
    return {'offset': offset, 'length': tim['length'], 'bpp_code': tim['bpp'],
            'raw_tim': str(base.with_suffix('.tim')), 'raw_tim_sha256': digest(data[offset:offset+tim['length']]),
            'pixels_sha256': digest(tim['pixels']),
            'clut_sha256': digest(palette['bytes']) if palette else None,
            'clut_geometry': {k: palette[k] for k in ('x','y','width','height','colors')} if palette else None,
            'vram': [tim['x'],tim['y']], 'variants': variants}


def run(source, output):
    index_path = source / 'BININDEX.BIN'
    index = index_path.read_bytes()
    pack_count = len(index) // ALIGN
    paths = [source / f'BINPACK{i}.BIN' for i in range(pack_count)]
    sources = [index_path] + paths
    before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns, digest(p.read_bytes())) for p in sources}
    listing = entries(index, [p.stat().st_size for p in paths])
    rows = []
    for pack, ordinal, offset, length in listing:
        with paths[pack].open('rb') as stream:
            stream.seek(offset)
            data = stream.read(length)
        if len(data) != length:
            raise ValueError('Short archive read')
        name = f'pack{pack}_file{ordinal:03d}'
        destination = output / 'entries' / f'{name}.bin'
        preserve(destination, data)
        # Verify the written archive entry, independently of the write call.
        if digest(destination.read_bytes()) != digest(data):
            raise ValueError('Entry verification failed')
        tims = []
        cursor = 0
        while True:
            cursor = data.find(b'\x10\x00\x00\x00', cursor)
            if cursor < 0:
                break
            tim = validate_tim(data, cursor)
            if tim:
                tims.append(write_tim(data, cursor, tim, output / 'tim' / name))
                cursor += tim['length']
            else:
                cursor += 1
        rows.append({'pack': paths[pack].name, 'entry': ordinal, 'index_offset': pack*ALIGN+ordinal*4,
                     'archive_offset': offset, 'length': length, 'sha256': digest(data),
                     'output': str(destination), 'header_hex': data[:32].hex(), 'tims': tims})
    after = {str(p): (p.stat().st_size, p.stat().st_mtime_ns, digest(p.read_bytes())) for p in sources}
    if after != before:
        raise ValueError('Source archive changed during extraction')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'format': 1, 'layout_reference': 'https://github.com/Xeeynamo/einhander/blob/master/einpack.go',
                'source_mode': 'read-only', 'sources': before,
                'alpha_contract': {'0': 'raw word 0000 / cutout', '127': 'nonzero, STP clear / opaque',
                                   '255': 'STP set; primitive blend mode decides transparency'},
                'class_map_contract': {'0':'cutout','1':'opaque/STP clear','2':'STP set'}, 'entries': rows}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding='utf-8')
    summary = {'packs':pack_count, 'entries':len(rows), 'extracted_bytes':sum(r['length'] for r in rows),
               'entries_verified':len(rows), 'source_hashes_unchanged':True,
               'validated_TIMs':sum(len(r['tims']) for r in rows),
               'palette_variants':sum(len(t['variants']) for r in rows for t in r['tims']),
               'TIMs_by_pack':{p.name:sum(len(r['tims']) for r in rows if r['pack']==p.name) for p in paths},
               'manifest':str(output/'manifest.json'),
               'scope':'Lossless archive extraction; custom texture formats/streamed assets require runtime mapping.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('C:/github/REMASTER_STAGING/disc_stock/files'))
    parser.add_argument('--output',type=Path,default=Path('C:/github/REMASTER_STAGING/disc_stock/archives'))
    args=parser.parse_args()
    run(args.source,args.output)
