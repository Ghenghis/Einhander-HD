"""Extend the existing accepted UltraSharp proof once; derive 2K from its 4K master."""
import json
from pathlib import Path

from prototype_upscale import COMFY, DUMP, sha, upscale
from spandrel import ModelLoader
import torch
from PIL import Image

ROOT = Path('C:/github/REMASTER_STAGING/prototypes/4x-UltraSharp')
KEY = '5CC44E5F-053D9A00.png'
NATIVE = DUMP / (KEY + '.orig')
EXISTING = ROOT / 'native16x/einhander-texture-replacements' / KEY
OUT = ROOT / 'resolution-ceiling'
OUT.mkdir(parents=True, exist_ok=True)
ORIGINAL_HASH = sha(NATIVE)
EXISTING_HASH = sha(EXISTING)
model_path = COMFY / 'models/upscale_models/4x-UltraSharp.pth'
output4k = OUT / '4096/einhander-texture-replacements' / KEY
output2k = OUT / '2048/einhander-texture-replacements' / KEY
manifest_path = OUT / 'manifest.json'

torch.set_num_threads(4)
if output4k.is_file() and manifest_path.is_file():
    prior = json.loads(manifest_path.read_text())
    if prior['existing_1024_sha256'] != EXISTING_HASH or prior['native_sha256'] != ORIGINAL_HASH:
        raise RuntimeError('Existing source changed; do not silently reuse the cached master')
    print('Reusing existing 4K master', flush=True)
    generation = prior['generation']
else:
    state = torch.load(model_path, map_location='cpu', weights_only=True)
    model = ModelLoader().load_from_state_dict(state).eval().to('cuda').half()
    print('Extending existing 1024 proof; no earlier passes repeated', flush=True)
    generation = upscale(EXISTING, model, 1, output4k)
    del model, state
    torch.cuda.empty_cache()

with Image.open(NATIVE) as original, Image.open(output4k) as master:
    original_alpha = original.convert('RGBA').getchannel('A')
    rgb = master.convert('RGB').resize((2048, 2048), Image.Resampling.LANCZOS)
    rgb.putalpha(original_alpha.resize((2048, 2048), Image.Resampling.NEAREST))
    output2k.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(output2k)
    rows = []
    for size, path, method in [
        (1024, EXISTING, 'Existing two-pass UltraSharp proof, reused unchanged'),
        (2048, output2k, 'One extra 4x pass to 4096, then Lanczos downsample to 2048'),
        (4096, output4k, 'One extra 4x UltraSharp pass on the existing 1024 proof'),
    ]:
        with Image.open(path) as image:
            assert image.size == (size, size)
            expected = original_alpha.resize(image.size, Image.Resampling.NEAREST)
            assert image.convert('RGBA').getchannel('A').tobytes() == expected.tobytes()
            preview = image.convert('RGBA')
            preview.putalpha(preview.getchannel('A').point(lambda v: 255 if v else 0))
            preview_path = OUT / f'preview-{size}.png'
            preview.save(preview_path)
        rows.append({'size': [size, size], 'native_scale': size // 64,
                     'engine_png': str(path), 'preview_png': str(preview_path),
                     'sha256': sha(path), 'method': method,
                     'rgba8_mib': size * size * 4 / 2**20})

assert sha(NATIVE) == ORIGINAL_HASH and sha(EXISTING) == EXISTING_HASH
manifest = {'native_source': str(NATIVE), 'native_size': [64, 64],
            'native_sha256': ORIGINAL_HASH, 'existing_1024_sha256': EXISTING_HASH,
            'model': str(model_path), 'model_sha256': sha(model_path),
            'generation': generation, 'variants': rows,
            'alpha_check': 'PASS: exact original cutout/STP classes at each output size',
            'source_preservation': 'PASS: stock backup and earlier 1024 proof unchanged',
            'in_game_QA': 'not run',
            'detail_limit': 'Larger outputs synthesize detail; they do not recover new stock information.'}
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps(manifest, indent=2), flush=True)
