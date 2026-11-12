"""Assemble verified replacements into an isolated, reviewable remaster pack."""
import collections
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image
from build_three_asset_proof import verify_stock
from checkpoint_json import write_json

ROOT = Path('C:/github/REMASTER_STAGING/full-remaster')
BASE = Path('C:/github/Einhander/windows-x64/hd-textures/stage1-v1')
PACK = ROOT/'stage1-expanded'
OUT = PACK/'einhander-texture-replacements'
OUT.mkdir(parents=True, exist_ok=True)
(PACK/'Hashes.ini').touch(exist_ok=True)
PROTECT = {'57AC02A0': [(72,108,132,180)],
           '73BF9877': [(128,96,256,192), (0,216,256,256)],
           'AB2DB563': [(0,216,256,256)],
           'AB58BBA4': [(0,0,256,64), (64,128,128,160)]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


queue = {r['key']: r for r in json.loads((ROOT/'queue.json').read_text())['assets'] if r['source_verified']}
world = {r['key']: r for r in json.loads((ROOT/'world-machines/manifest.json').read_text())['assets']}
base = {r['key']: r for r in json.loads((BASE/'manifest.json').read_text())['files']}
prior_path = PACK/'manifest.json'
prior = {r['key']: r for r in json.loads(prior_path.read_text())['files']} if prior_path.exists() else {}
rows = []
for index, key in enumerate(sorted(set(base)|set(queue))):
    dest = OUT/(key+'.png')
    source = queue.get(key)
    generated = world.get(key)
    rects = PROTECT.get(key.split('-')[0], []) if generated else []
    original = Path(generated['output']) if generated else BASE/'einhander-texture-replacements'/(key+'.png')
    input_hash = sha(original) if original.exists() else source['source_pixel_sha256']
    previous = prior.get(key)
    if (previous and previous.get('input_sha256') == input_hash
            and previous.get('protected_rects') == rects and dest.exists()
            and sha(dest) == previous['sha256']):
        rows.append(previous)
        continue
    method = base[key]['method'] if key in base else 'native 8x fallback; exact RGB and transparency/STP classes'
    neural = base[key].get('neural_detail', False) if key in base else False
    if generated or key not in base:
        native_path = Path(source['source'])
        verify_stock(native_path.parent, key)
        with Image.open(native_path) as image:
            native = image.convert('RGBA')
        assert hashlib.sha256(native.tobytes()).hexdigest() == source['source_pixel_sha256'], key
        if generated:
            assert generated['source_pixel_sha256'] == source['source_pixel_sha256'], key
            assert sha(original) == generated['output_sha256'], key
            with Image.open(original) as image:
                restored = image.convert('RGBA')
            method = generated['method']
            neural = True
        else:
            factor = min(8, source['target_scale'])
            restored = native.resize(tuple(v*factor for v in native.size), Image.Resampling.NEAREST)
        scale = restored.width//native.width
        assert restored.size == tuple(v*scale for v in native.size), key
        for rect in rects:
            target = tuple(v*scale for v in rect)
            protected = native.crop(rect).resize((target[2]-target[0], target[3]-target[1]), Image.Resampling.NEAREST)
            restored.paste(protected, target[:2])
        assert restored.getchannel('A').tobytes() == native.getchannel('A').resize(restored.size, Image.Resampling.NEAREST).tobytes(), key
        if generated and not rects:
            shutil.copy2(original, dest)
        else:
            restored.save(dest, compress_level=2)
        for rect in rects:
            target = tuple(v*scale for v in rect)
            assert restored.crop(target).tobytes() == native.crop(rect).resize((target[2]-target[0],target[3]-target[1]),Image.Resampling.NEAREST).tobytes(), key
    else:
        assert sha(original) == base[key]['sha256'], key
        shutil.copy2(original, dest)
    with Image.open(dest) as image:
        size = list(image.size)
    rows.append({'key': key, 'sha256': sha(dest), 'input_sha256': input_hash,
                 'method': method, 'neural_detail': neural, 'output_size': size,
                 'protected_rects': rects,
                 'source_verified': bool(source) or key in base,
                 'status': 'candidate; in-game review pending'})
    if index % 40 == 0:
        print(json.dumps({'assembled': index+1, 'total': len(set(base)|set(queue)), 'key': key}), flush=True)
    write_json(prior_path, {'version': 2, 'scope': 'Observed verified sources; expanded GPU world assets with native typography protected',
                           'production_installed': False, 'files': rows,
                           'native_ui_redraw': 'pending; source-exact fallbacks retain wording and glyph layout'})
write_json(prior_path, {'version': 2, 'scope': 'Observed verified sources; expanded GPU world assets with native typography protected',
                       'production_installed': False, 'files': rows,
                       'native_ui_redraw': 'pending; source-exact fallbacks retain wording and glyph layout'})
print(json.dumps({'files': len(rows), 'neural': sum(r['neural_detail'] for r in rows),
                  'protected_pages': sum(bool(r['protected_rects']) for r in rows),
                  'pack': str(PACK), 'status': 'isolated candidate; not installed'}, indent=2), flush=True)
