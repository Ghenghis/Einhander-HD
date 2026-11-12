"""Inventory Einhander assets without changing packs, saves, or emulator settings.

An optional --duckstation-dump enables an observed filename-key difference.
It is deliberately never reported as full-game coverage: that requires a
recorded playthrough of every relevant stage, route, ship, menu, and palette.
"""
import argparse
import collections
import csv
import hashlib
import json
import mmap
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

PACK_NAME = re.compile(
    r'^texpage-(?P<format>STP4|STP8|P4|P8|C16)-'
    r'(?P<texture_hash>[0-9A-F]+)(?:-(?P<palette_hash>[0-9A-F]+))?-'
    r'(?P<page_w>\d+)x(?P<page_h>\d+)-(?P<x>\d+)-(?P<y>\d+)-'
    r'(?P<source_w>\d+)x(?P<source_h>\d+)(?:-P(?P<p_first>\d+)-(?P<p_last>\d+))?\.png$',
    re.I,
)
CATEGORIES = [
    '01_ui_menus', '02_hud', '03_player', '04_enemies', '05_bosses',
    '06_weapons', '07_stages', '08_fmv', '09_fonts_text', '10_misc',
]


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def inventory_pack(root):
    records = []
    for path in sorted(root.rglob('*.png')):
        match = PACK_NAME.fullmatch(path.name)
        if not match:
            raise ValueError(f'Unrecognized DuckStation filename: {path}')
        fields = match.groupdict()
        for key in ['page_w', 'page_h', 'x', 'y', 'source_w', 'source_h']:
            fields[key] = int(fields[key])
        with Image.open(path) as image:
            image.load()  # Read every PNG, rather than trusting its header.
            width, height = image.size
            alpha = image.convert('RGBA').getchannel('A')
            counts = alpha.histogram()
        records.append({
            'filename': path.name, 'relative_path': path.relative_to(root).as_posix(),
            **fields, 'width': width, 'height': height,
            'scale_x': width / fields['source_w'],
            'scale_y': height / fields['source_h'],
            'target16_w': fields['source_w'] * 16,
            'target16_h': fields['source_h'] * 16,
            'bytes': path.stat().st_size, 'sha256': digest(path),
            'alpha_levels': [i for i, n in enumerate(counts) if n],
            'transparent_pixels': counts[0], 'opaque_pixels': counts[255],
            'partial_alpha_pixels': sum(counts[1:255]),
            'category': 'unclassified', 'stage': 'unverified',
            'review': 'unscaled' if width == fields['source_w'] and height == fields['source_h'] else 'unreviewed',
        })
    return records


def inventory_recomp(root):
    records = []
    for path in sorted(root.rglob('*.png')):
        original = Path(str(path) + '.orig')
        with Image.open(path) as image:
            current = image.size
        source = None
        if original.is_file():
            with Image.open(original) as image:
                source = image.size
        records.append({
            'key': path.stem, 'path': str(path), 'current_size': current,
            'backup_size': source, 'backup_path': str(original) if source else None,
            'current_scale_vs_backup': [current[i] / source[i] for i in (0, 1)] if source else None,
            'provenance': 'local .orig backup; not a new stock capture' if source else 'no original backup; scale unverified',
        })
    return records


def scan_str(path):
    """Scan raw 2352-byte sectors for validated standard STR video headers.

    Groups are contiguous video runs split on frame-counter resets/gaps, not
    semantic cutscene names. No claim about non-STR/proprietary/RAM videos.
    """
    groups = []
    group = None
    frame_chunks = {}

    def finish():
        if group is not None:
            group['unique_frames'] = len(frame_chunks)
            group['incomplete_chunk_sets'] = sum(
                len(c['seen']) != c['expected'] for c in frame_chunks.values())

    with path.open('rb') as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        if len(mm) % 2352:
            raise ValueError('Expected a raw 2352-byte-sector BIN')
        for sector in range(len(mm) // 2352):
            offset = sector * 2352 + 24
            if mm[offset:offset + 4] != b'\x60\x01\x01\x80':
                continue
            _, chunk, chunks, frame, size, width, height = struct.unpack_from('<IHHIIHH', mm, offset)
            if not (0 < width <= 640 and 0 < height <= 512 and chunk < chunks <= 100 and 0 < size <= 300000):
                continue
            if (group is None or sector - group['last_sector'] > 150 or
                    (frame < group['last_frame'] and chunk == 0) or
                    (width, height) != (group['width'], group['height'])):
                finish()
                frame_chunks = {}
                group = {'index': len(groups) + 1, 'first_sector': sector,
                         'last_sector': sector, 'first_frame': frame,
                         'last_frame': frame, 'width': width, 'height': height,
                         'video_sectors': 0}
                groups.append(group)
            group['last_sector'] = sector
            group['last_frame'] = frame
            group['video_sectors'] += 1
            entry = frame_chunks.setdefault(frame, {'expected': chunks, 'seen': set()})
            entry['seen'].add(chunk)
        finish()
    return {'source': str(path), 'method': 'standard STR headers at raw sector byte 24',
            'limitations': 'Detected stream runs only; no audio extraction, semantic naming, fps proof, playback, or proprietary-stream enumeration.',
            'groups': groups, 'total_frames': sum(g['unique_frames'] for g in groups)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, default=Path('C:/github/Einhänder_HDtext01/textures/SCUS-94243/replacements'))
    parser.add_argument('--recomp-dump', type=Path, default=Path('C:/github/Einhander/windows-x64/hd_dump_rgba'))
    parser.add_argument('--disc', type=Path, default=Path('C:/github/Einhander/ROM/Einhander (USA).bin'))
    parser.add_argument('--staging', type=Path, default=Path('C:/github/REMASTER_STAGING'))
    parser.add_argument('--duckstation-dump', type=Path)
    args = parser.parse_args()
    if not args.pack.is_dir() or not args.recomp_dump.is_dir() or not args.disc.is_file():
        parser.error('Pack, recomp dump, and disc paths must exist')
    if args.duckstation_dump and not args.duckstation_dump.is_dir():
        parser.error('--duckstation-dump must name an existing directory')
    args.staging.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        (args.staging / category).mkdir(exist_ok=True)
    records = inventory_pack(args.pack)
    if not records:
        parser.error('Pack contains no PNGs')
    originals = inventory_recomp(args.recomp_dump)
    formats = collections.Counter(r['format'] for r in records)
    scales = collections.Counter(f"{r['scale_x']:g}x{r['scale_y']:g}" for r in records)
    native_pixels = sum(r['source_w'] * r['source_h'] for r in records)
    decoded_pixels = sum(r['width'] * r['height'] for r in records)
    summary = {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'pack_root': str(args.pack),
        'pack_files': len(records), 'formats': dict(formats), 'scales': dict(scales),
        'pack_bytes': sum(r['bytes'] for r in records),
        'largest_side_px': max(max(r['width'], r['height']) for r in records),
        'files_with_side_ge_2048': sum(max(r['width'], r['height']) >= 2048 for r in records),
        'unscaled_files': [r['filename'] for r in records if r['review'] == 'unscaled'],
        'all_resident_RGBA8_bytes_current': decoded_pixels * 4,
        'all_resident_RGBA8_bytes_16x': native_pixels * 16 * 16 * 4,
        'memory_caveat': 'Hypothetical all-images-resident base levels, not a measured runtime requirement; mipmaps add approximately 1/3. Recomp has a bounded decode cache.',
        'recomp_png_files': len(originals),
        'recomp_original_backups': sum(r['backup_size'] is not None for r in originals),
        'coverage_status': 'unknown; no complete compatible DuckStation stock dump',
        'missing_full_game_count': None,
        'compatibility': 'DuckStation texpage 64-bit keys cannot be filename-diffed or renamed into recomp upload/CLUT CRC32 keys.',
        'duplicates_by_file_sha256': len(records) - len({r['sha256'] for r in records}),
    }
    missing = []
    observed_count = 0
    if args.duckstation_dump:
        observed = {p.name.lower(): p.name for p in args.duckstation_dump.rglob('*.png') if PACK_NAME.fullmatch(p.name)}
        if not observed:
            parser.error('Provided dump contains no recognized DuckStation texpage PNGs')
        replacements = {r['filename'].lower() for r in records}
        missing = sorted(name for key, name in observed.items() if key not in replacements)
        observed_count = len(observed)
        summary['coverage_status'] = 'partial observation only; full-game coverage unverified'
    summary['observed_duckstation_keys'] = observed_count
    summary['observed_exact_filename_gaps'] = len(missing) if args.duckstation_dump else None
    for filename, data in [('pack_inventory.json', records), ('summary.json', summary),
                           ('recomp_dump_inventory.json', originals), ('fmv_inventory.json', scan_str(args.disc))]:
        (args.staging / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with (args.staging / 'pack_inventory.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    text = [
        'FULL-GAME MISSING TEXTURE COUNT: UNKNOWN',
        'No full coverage run has been recorded. This is not a zero-missing result.',
        'The 593 recomp PNG keys use another namespace and include modified files.',
        'DuckStation filename keys identify drawn rectangles and palette variants, not unique physical assets.',
        'Exact filename gaps below, if any, need review for alternate/larger replacement rectangles.',
        f'Observed compatible dump keys: {observed_count}',
        f'Observed exact filename gaps: {len(missing) if args.duckstation_dump else "NOT COMPUTED"}',
        '', *missing,
    ]
    (args.staging / 'manifest_missing.txt').write_text('\n'.join(text) + '\n', encoding='utf-8')
    (args.staging / 'manifest_unscaled.txt').write_text('\n'.join(summary['unscaled_files']) + '\n', encoding='utf-8')
    checklist = {
        'scope': 'US SCUS-94243; downloaded pack namespace', 'complete': False,
        'required_capture_groups': ['boot/title/attract', 'options/configuration', 'fighter/weapon selection',
                                    'stages 1-7 and all discovered route variants', 'bosses/midbosses',
                                    'all available player craft and weapon/effect variants',
                                    'game-over/continue/results/name-entry/save', 'gallery/unlocks/endings'],
        'captured_and_verified_groups': [],
        'note': 'Do not infer completion from file count. Record capture provenance and palette cycles. FMV is a separate stream inventory.',
    }
    checklist_path = args.staging / 'coverage_checklist.json'
    if not checklist_path.exists():
        checklist_path.write_text(json.dumps(checklist, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
