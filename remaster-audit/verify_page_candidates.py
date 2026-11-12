"""Verify recorded native page sources, class masks and protected lettering."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_three_asset_proof import verify_stock

ROOT = Path('C:/github/REMASTER_STAGING/stage1_remaster/page-candidates')
rows = json.loads((ROOT/'pages-manifest.json').read_text())['pages']
checks, failures, protected = 0, [], 0
for row in rows:
    try:
        source, output = Path(row['source']), Path(row['output'])
        verify_stock(source.parent, row['key'])
        with Image.open(source) as image:
            native = image.convert('RGBA')
        if hashlib.sha256(native.tobytes()).hexdigest() != row['source_pixel_sha256']:
            raise ValueError('source pixels changed')
        if hashlib.sha256(output.read_bytes()).hexdigest() != row['output_sha256']:
            raise ValueError('candidate bytes changed')
        with Image.open(output) as image:
            candidate = image.convert('RGBA')
        if candidate.getchannel('A').tobytes() != native.getchannel('A').resize(candidate.size, Image.Resampling.NEAREST).tobytes():
            raise ValueError('native transparency/STP class changed')
        if not row['neural_detail'] and candidate.resize(native.size, Image.Resampling.NEAREST).tobytes() != native.tobytes():
            raise ValueError('native RGB changed in conservative page')
        for rect in row['protected_rects']:
            scale = candidate.width // native.width
            target = tuple(v * scale for v in rect)
            wanted = native.crop(rect).resize((target[2]-target[0], target[3]-target[1]), Image.Resampling.NEAREST)
            if candidate.crop(target).tobytes() != wanted.tobytes():
                raise ValueError('protected glyph region changed')
            protected += 1
        checks += 1
    except Exception as error:
        failures.append({'key': row['key'], 'error': str(error)})
    if (checks + len(failures)) % 50 == 0:
        print(json.dumps({'checked': checks, 'failures': len(failures)}), flush=True)
report = {'pages_checked':checks,'failures':failures,'protected_regions_checked':protected,
    'checks':'Raw/CLUT CRC, independent native decode, source/output SHA256, exact nearest alpha classes, conservative RGB and protected glyph rectangles.'}
Path('C:/github/REMASTER_STAGING/hd-coverage/page-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2), flush=True)
raise SystemExit(bool(failures))
