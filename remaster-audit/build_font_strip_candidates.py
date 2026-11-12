"""Bind verified 256x8 upload aliases to exact coherent HUD atlas row crops.

Only byte-identical source words and byte-identical CLUTs establish admission.
No guessed font, OCR, UV rearrangement, game input or installed-pack mutation.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw

from build_three_asset_proof import verify_stock


ROOT = Path(__file__).resolve().parents[1]
QUEUE = Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
HUD = ROOT/'remaster-audit/hud-restoration/candidate-20261112-coherent-v4'
LIVE = ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v3/native-fighter'
OUT = ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v1'
LIVE_REQUIRED = {
    '5F101F62-B88C038E', '921FC559-B88C038E', 'AAA5C104-B88C038E',
    '2C781811-B88C038E', 'E1F18F98-B88C038E', '786B98BF-B88C038E',
    '5C02D3C1-B88C038E', 'D050AD1B-B88C038E', '913A6603-B88C038E',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def raw_verified(directory, key):
    metadata = json.loads((directory/(key+'.source.json')).read_bytes())
    raw = (directory/(key+'.words.bin')).read_bytes()
    clut = (directory/(key+'.clut.bin')).read_bytes()
    valid = (directory/(key+'.valid.bin')).read_bytes()
    if metadata.get('depth') != 0 or metadata.get('width_words') != 64 or metadata.get('height') != 8:
        raise ValueError('Expected a256x8 indexed source strip: '+key)
    if len(raw) != 1024 or len(clut) != 32 or len(valid) != 512 or any(v != 1 for v in valid):
        raise ValueError('Incomplete source words, palette or validity: '+key)
    if f'{zlib.crc32(raw):08X}' != key.split('-')[0] or f'{zlib.crc32(clut):08X}' != key.split('-')[1]:
        raise ValueError('Raw source CRC/CLUT key mismatch: '+key)
    return metadata, raw, clut


def build_v1():
    if OUT.exists():
        raise ValueError('Existing strip candidates are immutable; choose a new output')
    source_queue = json.loads(QUEUE.read_bytes())['assets']
    hud_manifest = json.loads((HUD/'manifest.json').read_bytes())
    if hud_manifest['geometry_version'] != 'coherent-glyph-rim-v4':
        raise ValueError('Expected reviewed coherent HUDv4')
    bases = []
    for row in hud_manifest['files']:
        if not row['key'].startswith(('BDAE4156-', '913FE978-')):
            continue
        metadata, raw, clut = verify_stock(Path(row['source']).parent, row['key'])
        for variant, info in row['outputs'].items():
            if sha(Path(info['path']).read_bytes()) != info['sha256']:
                raise ValueError('Coherent HUD artifact hash mismatch: '+row['key'])
        bases.append(dict(row=row, raw=raw, clut=clut,
                          windows=[(raw[y*128:(y+8)*128], y) for y in range(metadata['height']-7)]))
    candidates = []
    for row in source_queue:
        sm = row.get('source_metadata', {})
        if row.get('source_verified') and (sm.get('width_words'), sm.get('height'), sm.get('depth')) == (64, 8, 0):
            candidates.append(row)
    accepted, rejected = [], []
    for row in candidates:
        directory, key = Path(row['source']).parent, row['key']
        metadata, raw, clut = verify_stock(directory, key)
        if sha(raw) != row['raw_sha256'] or sha(clut) != row['clut_sha256']:
            raise ValueError('Verified queue source changed: '+key)
        hits = [(base, y) for base in bases if base['clut'] == clut
                for window, y in base['windows'] if window == raw]
        # Uniform blank padding establishes no font semantics.
        if not hits or len(set(raw)) < 2:
            rejected.append(dict(key=key, reason='No byte-exact font row with matching CLUT' if not hits else 'Uniform padding is not admitted as font art'))
            continue
        # Existing913FE aliases use their own accepted coherent strip, rather
        # than a different full-atlas contour profile for the same source row.
        hits.sort(key=lambda hit: (0 if hit[0]['row']['key'] == key else 1,
                                   0 if hit[0]['row']['key'].startswith('913FE978') else 1,
                                   hit[0]['row']['key'], hit[1]))
        base, y = hits[0]
        live = None
        if (LIVE/(key+'.source.json')).is_file():
            live_metadata, live_raw, live_clut = raw_verified(LIVE, key)
            if live_raw != raw or live_clut != clut:
                raise ValueError('Live source bytes differ from stock font identity: '+key)
            live = dict(source=str(LIVE/(key+'.source.json')), raw_sha256=sha(live_raw),
                        clut_sha256=sha(live_clut), frame=live_metadata['frame'],
                        cpu_vram_may_be_stale=live_metadata.get('cpu_vram_may_be_stale'),
                        scope='Captured bytes independently CRC/CLUT-verified and equal stock; not a fresh framebuffer visibility proof')
        accepted.append(dict(key=key, queue_row=row, metadata=metadata, raw=raw, clut=clut,
                             base=base, y=y, hits=hits, live=live))
    if not LIVE_REQUIRED <= {row['key'] for row in accepted}:
        raise ValueError('Missing a required live fighter-description alias')
    OUT.mkdir()
    for folder in ('pack', 'strict-mask-pack'):
        (OUT/folder/'einhander-texture-replacements').mkdir(parents=True)
        (OUT/folder/'Hashes.ini').write_text('', encoding='utf-8')
    shutil.copy2(__file__, OUT/'build-source.py')
    rows = []
    preview = Image.new('RGB', (1536, 9*130), (12, 18, 25))
    draw = ImageDraw.Draw(preview)
    preview_row = 0
    for item in sorted(accepted, key=lambda item:item['key']):
        key, base, y = item['key'], item['base']['row'], item['y']
        outputs = {}
        source = Image.open(item['queue_row']['source']).convert('RGBA')
        for variant, info in base['outputs'].items():
            with Image.open(info['path']) as master:
                crop = master.convert('RGBA').crop((0, y*16, 4096, (y+8)*16))
            if crop.size != (4096, 128):
                raise ValueError('Atlas crop changed strip dimensions: '+key)
            pixels = np.asarray(crop)
            if not set(map(int, np.unique(pixels[:, :, 3]))) <= {0, 127, 255}:
                raise ValueError('Invalid output alpha class: '+key)
            if variant == 'strict-mask-pack' and crop.getchannel('A').tobytes() != source.getchannel('A').resize(crop.size, Image.Resampling.NEAREST).tobytes():
                raise ValueError('Strict source strip alpha footprint changed: '+key)
            path = OUT/variant/'einhander-texture-replacements'/(key+'.png')
            crop.save(path)
            with Image.open(path) as reopened:
                if reopened.convert('RGBA').tobytes() != crop.tobytes():
                    raise ValueError('PNG round-trip changed atlas crop: '+key)
            outputs[variant] = dict(path=str(path), sha256=sha(path.read_bytes()), size=[4096,128],
                                    rgba_crop_sha256=sha(crop.tobytes()), parent_png_sha256=info['sha256'],
                                    exact_parent_rgba_crop=True)
            if variant == 'pack' and key in LIVE_REQUIRED:
                py = preview_row*130
                draw.text((6, py+4), f'{key} | verified BDAE source row {y} | native above / coherent atlas crop below', fill='white')
                native_view = source.convert('RGB').resize((1536,48), Image.Resampling.NEAREST)
                restored_view = crop.convert('RGB').resize((1536,48), Image.Resampling.LANCZOS)
                preview.paste(native_view, (0,py+24))
                preview.paste(restored_view, (0,py+78))
                preview_row += 1
        rows.append(dict(key=key, role='Verified font atlas eight-row upload alias',
                         source=item['queue_row']['source'], source_size=[256,8],
                         source_words_sha256=sha(item['raw']), source_clut_sha256=sha(item['clut']),
                         source_crc_verified=True, source_decode_verified=True,
                         base_key=base['key'], base_source=base['source'], base_output_region=[0,y,256,y+8],
                         exact_source_words_and_clut_match=True,
                         all_raw_matches=[dict(key=b['row']['key'], native_row=yy) for b,yy in item['hits']],
                         existing_identity_key=key==base['key'], outputs=outputs,
                         source_local_uv_coordinates_preserved=True, live_capture=item['live'],
                         in_game_acceptance='Pending candidate upload draw receipts and composed menu/gameplay visibility review'))
        print(json.dumps({'key':key,'base':base['key'],'row':y,'checks':'PASS'}), flush=True)
    preview.save(OUT/'fighter-description-strip-before-after.png')
    report = dict(format=1, created_at_utc=datetime.now(timezone.utc).isoformat(), production_installed=False,
                  game_actions=0, source_keys=len(rows), files=rows, scanned_verified_strips=len(candidates),
                  rejected_count=len(rejected), rejected=rejected,
                  new_row_aliases=sum(not row['existing_identity_key'] for row in rows),
                  existing_identity_keys=sum(row['existing_identity_key'] for row in rows),
                  required_live_aliases_verified=sorted(LIVE_REQUIRED),
                  source_queue=str(QUEUE), source_queue_sha256=sha(QUEUE.read_bytes()),
                  parent_manifest=str(HUD/'manifest.json'), parent_manifest_sha256=sha((HUD/'manifest.json').read_bytes()),
                  geometry_version='coherent-glyph-rim-v4 atlas crop; no new glyph reconstruction',
                  scope='Exact raw row and CLUT admission with byte-exact coherent atlas RGBA crops; no world sprite guessing or UV rearrangement',
                  limits=['All coverage is limited to independently verified source variants available in this queue.',
                          'Crops inherit reviewed parent contour/alpha choices; strict variants retain the original source alpha footprint.',
                          'CPU VRAM capture staleness annotations remain in live receipts; matching stock bytes establishes identity, not real-time visibility.',
                          'Real-game composed visibility and animation acceptance are separate.'])
    (OUT/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'pack':str(OUT/'pack'), 'source_keys':len(rows),'new_aliases':report['new_row_aliases'], 'rejected':len(rejected)}))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def native_decode(raw, clut):
    """Independent scalar PSX decoder, checked against the vectorized path."""
    import struct
    values = struct.unpack('<16H', clut)
    rgba = bytearray()
    for word in struct.unpack('<512H', raw):
        for shift in (0, 4, 8, 12):
            value = values[(word >> shift) & 15]
            rgba.extend(((value & 31) << 3, ((value >> 5) & 31) << 3, ((value >> 10) & 31) << 3,
                         0 if value == 0 else 255 if value & 0x8000 else 127))
    return bytes(rgba)


def build_v2(prior=None, out=None, capture_dirs=None, expected_prior_count=14,
             contract='verified-font-strip-v2'):
    """Preserve v1 and author independently captured native menu font strips.

    The live small-font uploads are not raw row aliases of AEE/BDAE. They use
    their own original zero-background and10..15 glyph index ramp. The output
    explicitly records standalone source evidence, never a fabricated parent.
    """
    out = out or ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v2'
    if out.exists():
        raise ValueError('Existing font candidates are immutable')
    prior = prior or OUT
    menu_parent = ROOT/'remaster-audit/menu-restoration/file-option-field-candidate-v1'
    captures_root = ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v4'
    capture_dirs = capture_dirs or [captures_root/'native-file-option', captures_root/'native-extra-menus']
    known_families = {'2C6866AA', '8D0FCF8A', '9D8DF52A', 'C544AC0D', '8BE06E98', 'B77B98B9', 'AD49126E'}
    prior_manifest = json.loads((prior/'manifest.json').read_bytes())
    if prior_manifest['source_keys'] != expected_prior_count:
        raise ValueError('Expected the complete reviewed parent key set')
    prior_keys = {row['key'] for row in prior_manifest['files']}
    menu = load_module(menu_parent/'menu-field-library.py', 'standalone_menu_field')
    hud = load_module(menu_parent/'palette-contour-library.py', 'standalone_font_decode')
    cv2.setNumThreads(2)
    snapshots, evidence, queried = {}, {}, set()
    for directory in capture_dirs:
        path = directory/'capture.jsonl'
        body = path.read_bytes()
        snapshots[str(path)] = sha(body)
        records = [json.loads(line) for line in body.splitlines()]
        for record in records:
            key = record.get('key', '')
            if key.split('-')[0] in known_families and record.get('native_words') == [64,8]:
                queried.add(key)
        for path in sorted(directory.glob('*.source.json')):
            metadata = json.loads(path.read_bytes())
            key = metadata['key']
            if key.split('-')[0] not in known_families:
                continue
            metadata, raw, clut = raw_verified(directory, key)
            if key in evidence and (evidence[key]['raw'] != raw or evidence[key]['clut'] != clut):
                raise ValueError('Repeated capture key changed bytes: '+key)
            draws = [dict(line=n, **{k:r.get(k) for k in ('event','key','frame','source_kind','native_words','source_word_xy','uv_bounds','xy','not_visibility_proof','cpu_vram_may_be_stale')})
                     for n,r in enumerate(records,1) if r.get('key') == key and r.get('event') in ('source_draw_query_matched','replacement_gl_draw_submitted')][:8]
            occurrence = dict(metadata_path=str(path), metadata_sha256=sha(path.read_bytes()),
                              capture_path=str(directory/'capture.jsonl'), capture_sha256=snapshots[str(directory/'capture.jsonl')], draws=draws)
            if key not in evidence:
                evidence[key] = dict(metadata=metadata, raw=raw, clut=clut, directory=directory, occurrences=[])
            evidence[key]['occurrences'].append(occurrence)
    # Guard against capturing a moving archive while a bounded recorder is
    # still writing. The caller also waits for the parent-controlled stop.
    for path, digest in snapshots.items():
        if sha(Path(path).read_bytes()) != digest:
            raise ValueError('Capture still changing; wait until finalized: '+path)
    output_rows, rendered_items = [], []
    for key, item in sorted(evidence.items()):
        if key in prior_keys:
            continue
        indices = hud.decode_indices(item['raw'], item['metadata'])
        palette = hud.palette_rgba(item['clut'])
        decoded = palette[indices]
        if decoded.tobytes() != native_decode(item['raw'], item['clut']):
            raise ValueError('Independent native decode mismatch: '+key)
        used = set(map(int, np.unique(indices)))
        if not used <= {0,10,11,12,13,14,15} or 0 not in used or 15 not in used:
            raise ValueError('Unreviewed small-font source ramp: '+key)
        # Only the seven actually used source codes enter this tonal field.
        # Unused CLUT slots can be bright unrelated colors; a full permutation
        # would inject those colors between glyph and background shades.
        source_codes = np.array([15,14,13,12,11,10,0], dtype=np.uint8)
        levels = np.array([0,3,6,9,11,13,15], dtype=np.uint8)
        lookup = np.zeros(16, dtype=np.uint8)
        lookup[source_codes] = levels
        canonical = lookup[indices]
        ramp = np.empty((16,4), dtype=np.uint8)
        for channel in range(3):
            ramp[:,channel] = np.rint(np.interp(np.arange(16), levels, palette[source_codes,channel])).astype(np.uint8)
        nearest_anchor = np.abs(np.arange(16)[:,None]-levels.astype(int)[None,:]).argmin(axis=1)
        ramp[:,3] = palette[source_codes[nearest_anchor],3]
        if not np.array_equal(ramp[canonical], decoded):
            raise ValueError('Canonical native RGB/class identity changed: '+key)
        regions = [(0,0,256,8)]
        contours, selected = menu.menu_contour_indices(canonical,16,regions)
        authored, nearest = menu.menu_render(canonical,contours,ramp,regions,native_alpha=True)
        if not np.array_equal(authored[:,:,3], nearest[:,:,3]):
            raise ValueError('Original alpha footprint changed: '+key)
        if not set(map(int,np.unique(authored[:,:,3]))) <= {0,127,255}:
            raise ValueError('Noncategorical source alpha: '+key)
        rendered_items.append((key,item,decoded,authored,source_codes.tolist(),levels.tolist()))
    out.mkdir()
    for folder in ('pack','strict-mask-pack'):
        shutil.copytree(prior/folder,out/folder)
    if (prior/'sources').is_dir():
        shutil.copytree(prior/'sources',out/'sources')
    else:
        (out/'sources').mkdir()
    shutil.copy2(__file__,out/'build-source.py')
    shutil.copy2(menu_parent/'menu-field-library.py',out/'menu-field-library.py')
    shutil.copy2(menu_parent/'palette-contour-library.py',out/'palette-contour-library.py')
    for old in prior_manifest['files']:
        row = json.loads(json.dumps(old))
        row.setdefault('kind','exact_font_row_alias')
        row['previous_manifest'] = str(prior/'manifest.json')
        for variant, info in row['outputs'].items():
            previous_path = Path(info['path'])
            current_path = out/variant/'einhander-texture-replacements'/previous_path.name
            if sha(current_path.read_bytes()) != info['sha256']:
                raise ValueError('Accepted parent output changed: '+row['key'])
            info['path'] = str(current_path)
        if row['kind'] == 'standalone_native_font':
            row['source'] = str(out/'sources'/Path(row['source']).name)
            for archive in row['source_archives'].values():
                archive['path'] = str(out/'sources'/Path(archive['path']).name)
        output_rows.append(row)
    ui_captures = []
    for name in ('file-option-entered','file-option-source-bracket','name-grid-final','save-confirmation-final','saved-pilot-final','file-options-final'):
        receipt = captures_root/'captures'/(name+'.json')
        if receipt.is_file():
            doc = json.loads(receipt.read_bytes())
            png = Path(doc['path'])
            if sha(png.read_bytes()) != doc['sha256']:
                raise ValueError('Composed UI evidence hash changed: '+name)
            ui_captures.append(dict(receipt=str(receipt),receipt_sha256=sha(receipt.read_bytes()),
                                    image=str(png),image_sha256=doc['sha256'],
                                    frame_before=doc['frame_before'],frame_after=doc['frame_after'],
                                    scope=doc['scope']))
    contact = Image.new('RGB',(1536,6*140),(12,18,25))
    draw = ImageDraw.Draw(contact)
    displayed = set()
    for key,item,decoded,authored,codes,levels in rendered_items:
        source_archives = {}
        for label,suffix in (('words','.words.bin'),('clut','.clut.bin'),('validity','.valid.bin'),('metadata','.source.json')):
            source = item['directory']/(key+suffix)
            target = out/'sources'/(key+suffix)
            shutil.copy2(source,target)
            source_archives[label] = dict(path=str(target),sha256=sha(target.read_bytes()))
        source_image = out/'sources'/(key+'.png')
        Image.fromarray(decoded).save(source_image)
        outputs = {}
        for variant in ('pack','strict-mask-pack'):
            path = out/variant/'einhander-texture-replacements'/(key+'.png')
            Image.fromarray(authored).save(path)
            with Image.open(path) as reread:
                if reread.convert('RGBA').tobytes() != authored.tobytes():
                    raise ValueError('PNG roundtrip mismatch: '+key)
            outputs[variant] = dict(path=str(path),sha256=sha(path.read_bytes()),size=[4096,128],
                                    rgba_sha256=sha(authored.tobytes()))
        output_rows.append(dict(key=key,kind='standalone_native_font',role='Captured file/config/name-grid native font strip; full glyph semantics remain state-specific',
                                source=str(source_image),source_sha256=sha(source_image.read_bytes()),source_size=[256,8],
                                source_archives=source_archives,source_words_sha256=sha(item['raw']),source_clut_sha256=sha(item['clut']),
                                source_crc_verified=True,source_decode_verified=True,source_validity_complete=True,
                                source_metadata=item['metadata'],native_rgba_sha256=sha(decoded.tobytes()),
                                canonical_source_codes=codes,canonical_levels=levels,canonical_native_rgba_exact=True,
                                native_alpha_footprint_exact=True,source_local_uv_coordinates_preserved=True,
                                outputs=outputs,native_ui_receipts=item['occurrences'],composed_ui_capture_refs=ui_captures,
                                base_key=None,base_output_region=None,
                                in_game_acceptance='Candidate source identity and original coverage verified; new composed visibility/animation acceptance pending'))
        family=key.split('-')[0]
        if family not in displayed and (key.endswith('-C04F65C0') or not any(k.startswith(family+'-') and k.endswith('-C04F65C0') for k in evidence)):
            y=len(displayed)*140
            draw.text((5,y+5),key+' | original source above / continuous exact-CLUT field below',fill='white')
            contact.paste(Image.fromarray(decoded[:,:,:3]).resize((1536,48),Image.Resampling.NEAREST),(0,y+27))
            contact.paste(Image.fromarray(authored[:,:,:3]).resize((1536,48),Image.Resampling.LANCZOS),(0,y+82))
            displayed.add(family)
        print(json.dumps(dict(key=key,kind='standalone_native_font',original_alpha_exact=True)),flush=True)
    for path,digest in snapshots.items():
        if sha(Path(path).read_bytes()) != digest:
            raise ValueError('Capture changed during rendering; output remains unfinalized: '+path)
    contact.crop((0,0,1536,max(140,len(displayed)*140))).save(out/'standalone-font-source-before-after.png')
    parent_refs = {name:dict(path=str(path),sha256=sha(path.read_bytes())) for name,path in (
        ('hud',HUD/'manifest.json'),('aee',menu_parent/'manifest.json'),('font_v1',OUT/'manifest.json'))}
    if expected_prior_count > 14:
        parent_refs['font_v2'] = dict(path=str(prior/'manifest.json'),sha256=sha((prior/'manifest.json').read_bytes()))
    report = dict(format=3 if expected_prior_count>14 else 2,contract=contract,created_at_utc=datetime.now(timezone.utc).isoformat(),
                  production_installed=False,game_actions=0,source_keys=len(output_rows),
                  expected_keys=sorted(row['key'] for row in output_rows),files=sorted(output_rows,key=lambda row:row['key']),
                  exact_font_row_alias_count=14,standalone_native_font_count=sum(row['kind']=='standalone_native_font' for row in output_rows),
                  parent_manifest_refs=parent_refs,
                  native_capture_refs=[dict(path=path,sha256=digest) for path,digest in snapshots.items()],
                  missing_source_archives=sorted(queried-set(evidence)-prior_keys),
                  prior_outputs_preserved=expected_prior_count,new_source_keys=len(rendered_items),
                  method='All prior accepted PNG outputs are preserved byte-for-byte. Exact original parent row crops retain their proofs; new standalone captured small fonts use only their actual seven source codes/CLUT colors in a continuous tonal field, with original categorical alpha footprint and all source UV coordinates retained.',
                  limits=['Standalone entries are not AEE/BDAE row aliases; their independent raw source evidence is explicit.',
                          'Native archives may carry CPU VRAM staleness annotations; CRC identity and composed UI observations are sequential rather than atomic.',
                          'Palette variants preserve the exact captured CLUT; unused palette slots never enter the interpolation ramp.',
                          'No new candidate composed visibility or every-state coverage is claimed by this build.'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(pack=str(out/'pack'),source_keys=len(output_rows),standalone=len(rendered_items),missing_source_archives=report['missing_source_archives'])))


def build_v4():
    """Release the accidental native-block alpha clip on standalone fonts.

    RGB already contains a continuous original-source field. Main alpha now
    follows its categorical contour, while every strict comparison and all
    fourteen original row-alias main images remain byte-identical to v3.
    """
    prior=ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v3'
    out=ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v4'
    if out.exists():
        raise ValueError('Existing font candidates are immutable')
    manifest=json.loads((prior/'manifest.json').read_bytes())
    if manifest['contract']!='verified-font-strip-v3' or manifest['source_keys']!=39:
        raise ValueError('Expected the reviewed complete39-key v3 source')
    menu=load_module(prior/'menu-field-library.py','font_v4_field')
    hud=load_module(prior/'palette-contour-library.py','font_v4_decode')
    cv2.setNumThreads(2)
    for row in manifest['files']:
        for info in row['outputs'].values():
            if sha(Path(info['path']).read_bytes())!=info['sha256']:
                raise ValueError('Prior accepted output changed: '+row['key'])
    for folder in ('pack','strict-mask-pack','sources'):
        shutil.copytree(prior/folder,out/folder)
    for name in ('menu-field-library.py','palette-contour-library.py'):
        shutil.copy2(prior/name,out/name)
    shutil.copy2(__file__,out/'build-source.py')
    changed=[]
    for row in manifest['files']:
        key=row['key']
        previous_main=Path(row['outputs']['pack']['path'])
        for variant,info in row['outputs'].items():
            info['path']=str(out/variant/'einhander-texture-replacements'/(key+'.png'))
        row['previous_manifest']=str(prior/'manifest.json')
        if row['kind']!='standalone_native_font':
            continue
        row['source']=str(out/'sources'/Path(row['source']).name)
        for archive in row['source_archives'].values():
            archive['path']=str(out/'sources'/Path(archive['path']).name)
            if sha(Path(archive['path']).read_bytes())!=archive['sha256']:
                raise ValueError('Frozen source archive changed: '+key)
        raw=Path(row['source_archives']['words']['path']).read_bytes()
        clut=Path(row['source_archives']['clut']['path']).read_bytes()
        metadata=json.loads(Path(row['source_archives']['metadata']['path']).read_bytes())
        indices=hud.decode_indices(raw,metadata)
        palette=hud.palette_rgba(clut)
        if palette[indices].tobytes()!=native_decode(raw,clut):
            raise ValueError('Native source decode changed: '+key)
        codes=np.array(row['canonical_source_codes'],dtype=np.uint8)
        levels=np.array(row['canonical_levels'],dtype=np.uint8)
        lookup=np.zeros(16,np.uint8);lookup[codes]=levels
        canonical=lookup[indices]
        ramp=np.empty((16,4),np.uint8)
        for channel in range(3):
            ramp[:,channel]=np.rint(np.interp(np.arange(16),levels,palette[codes,channel])).astype(np.uint8)
        nearest_anchor=np.abs(np.arange(16)[:,None]-levels.astype(int)[None,:]).argmin(axis=1)
        ramp[:,3]=palette[codes[nearest_anchor],3]
        if not np.array_equal(ramp[canonical],palette[indices]):
            raise ValueError('Canonical native source identity changed: '+key)
        regions=[(0,0,256,8)]
        contours,selected=menu.menu_contour_indices(canonical,16,regions)
        authored,nearest=menu.menu_render(canonical,contours,ramp,regions,native_alpha=False)
        with Image.open(previous_main) as image:
            previous=np.asarray(image.convert('RGBA'))
        if not np.array_equal(authored[:,:,:3],previous[:,:,:3]):
            raise ValueError('Alpha-only revision changed RGB: '+key)
        alpha_changes=int(np.count_nonzero(authored[:,:,3]!=previous[:,:,3]))
        if not alpha_changes or not set(map(int,np.unique(authored[:,:,3])))<={0,127,255}:
            raise ValueError('Expected a categorical contour-alpha correction: '+key)
        if not np.array_equal(authored[~selected],previous[~selected]):
            raise ValueError('Correction escaped verified strip UVs: '+key)
        output=Path(row['outputs']['pack']['path'])
        Image.fromarray(authored).save(output)
        with Image.open(output) as image:
            if image.convert('RGBA').tobytes()!=authored.tobytes():
                raise ValueError('PNG correction round-trip failed: '+key)
        info=row['outputs']['pack']
        info.update(sha256=sha(output.read_bytes()),rgba_sha256=sha(authored.tobytes()),
                    native_alpha_footprint_exact=False,categorical_contour_alpha=True)
        row['outputs']['strict-mask-pack']['native_alpha_footprint_exact']=True
        row.update(selected_native_regions=[[0,0,256,8]],
                   alpha_policy='categorical_contour_inside_authored_regions',
                   main_contour_alpha_refined=True,native_alpha_footprint_exact=False,
                   strict_native_alpha_footprint_exact=True,main_rgb_exact_to_v3=True,
                   protected_outside_exact_to_v3=True,changed_alpha_texels=alpha_changes,
                   in_game_acceptance='Coherent categorical contour alpha released from native block clipping; new composed visual acceptance pending')
        changed.append(key)
        if key=='2C6866AA-C04F65C0':
            box=(10,0,22,8)
            canvas=Image.new('RGB',(768,380),(12,18,25));draw=ImageDraw.Draw(canvas)
            for n,(label,pixels) in enumerate((('V3: continuous RGB clipped by nearest native alpha',previous),
                                              ('V4: same RGB with coherent categorical contour alpha',authored))):
                rgba=Image.fromarray(pixels).crop(tuple(v*16 for v in box))
                panel=Image.new('RGBA',rgba.size,(0,0,0,255));panel.alpha_composite(rgba)
                panel=panel.convert('RGB').resize((384,256),Image.Resampling.LANCZOS)
                draw.text((n*384+4,8),label,fill='white')
                canvas.paste(panel,(n*384,45))
            draw.text((5,320),'16x edge inspection; same39 keys, same RGB, original-alpha strict comparison retained',fill='white')
            canvas.save(out/'contour-alpha-before-after.png')
        print(json.dumps({'key':key,'alpha_changes':alpha_changes,'rgb_unchanged':True}),flush=True)
    if len(changed)!=25:
        raise ValueError('Expected exactly the25 standalone corrections')
    manifest.update(format=4,contract='verified-font-strip-v4',created_at_utc=datetime.now(timezone.utc).isoformat(),
                    corrected_standalone_alpha_keys=changed,prior_strict_outputs_preserved=39,
                    prior_alias_main_outputs_preserved=14,
                    method='All39 strict comparisons and14 row-alias main PNGs retained unchanged from v3. For25 standalone main PNGs, RGB remains byte-identical and categorical alpha follows the existing continuous source field inside the verified256x8 UV region, removing nearest-native-block outer clipping.',
                    limits=['Main contour alpha deliberately refines original native0/127/255 boundaries within authored strips; exact native alpha is retained only by the strict comparison.',
                            'Original raw source/CLUT/archive identity, words, glyph positions and every RGB sample remain unchanged from reviewed v3.',
                            'Candidate composed visibility and animation acceptance remain separate.'])
    manifest['parent_manifest_refs']['font_v3']=dict(path=str(prior/'manifest.json'),sha256=sha((prior/'manifest.json').read_bytes()))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pack':str(out/'pack'),'source_keys':39,'corrected_main_alpha_keys':25,'unchanged_pngs':53}))


if __name__ == '__main__':
    build_v4()
