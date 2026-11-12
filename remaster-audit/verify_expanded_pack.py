"""Independently check the assembled pack's bytes, native sources and masks."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_three_asset_proof import verify_stock
from checkpoint_json import write_json

ROOT = Path('C:/github/REMASTER_STAGING/full-remaster')
PACK = ROOT/'stage1-expanded'
rows = json.loads((PACK/'manifest.json').read_text())['files']
sources = {r['key']: r for r in json.loads((ROOT/'queue.json').read_text())['assets'] if r['source_verified']}
report_path = PACK/'verification.json'
previous = json.loads(report_path.read_text()).get('passed', {}) if report_path.exists() else {}
passed, failures, reused = {}, [], 0
for index, row in enumerate(rows):
    key = row['key']
    try:
        source = sources[key]
        output = PACK/'einhander-texture-replacements'/(key+'.png')
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        assert digest == row['sha256'], 'replacement hash changed'
        signature = {'sha256': digest, 'source_pixel_sha256': source['source_pixel_sha256']}
        if previous.get(key) == signature:
            passed[key] = signature
            reused += 1
            continue
        native_path = Path(source['source'])
        verify_stock(native_path.parent, key)
        with Image.open(native_path) as image:
            native = image.convert('RGBA')
        assert hashlib.sha256(native.tobytes()).hexdigest() == source['source_pixel_sha256'], 'source pixels changed'
        with Image.open(output) as image:
            restored = image.convert('RGBA')
        scale = restored.width//native.width
        assert scale >= 1 and restored.size == tuple(v*scale for v in native.size), 'invalid dimensions'
        assert list(restored.size) == row['output_size'], 'size differs from manifest'
        assert restored.getchannel('A').tobytes() == native.getchannel('A').resize(restored.size,Image.Resampling.NEAREST).tobytes(), 'transparency/STP class map changed'
        if not row['neural_detail']:
            assert restored.resize(native.size,Image.Resampling.NEAREST).tobytes() == native.tobytes(), 'native fallback pixels changed'
        for rect in row['protected_rects']:
            target = tuple(v*scale for v in rect)
            assert restored.crop(target).tobytes() == native.crop(rect).resize((target[2]-target[0],target[3]-target[1]),Image.Resampling.NEAREST).tobytes(), 'protected lettering changed'
        passed[key] = signature
    except Exception as error:
        failures.append({'key': key, 'error': str(error)})
    if index%40 == 0:
        write_json(report_path, {'complete': False, 'passed': passed, 'failures': failures})
        print(json.dumps({'checked':index+1,'passed':len(passed),'failures':len(failures)}),flush=True)
report = {'complete': True, 'files_checked': len(rows), 'passed': passed,
          'failures': failures, 'unchanged_previously_verified': reused,
          'checks': 'PNG hashes and dimensions, independent raw/CLUT decode, native source hashes, exact transparency/STP masks, conservative RGB roundtrip, protected lettering rectangles.',
          'in_game_status': 'Separate visual and playback review required.'}
write_json(report_path,report)
print(json.dumps({k:v for k,v in report.items() if k!='passed'},indent=2),flush=True)
raise SystemExit(bool(failures))
