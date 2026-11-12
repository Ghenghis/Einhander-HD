"""Small, isolated local-model proof. Never installs a prototype in either game.

Run with L:/Github/ComfyUI/.venv/Scripts/python.exe. Uses the already-installed
ComfyUI tiled upscaler and model loader; no server/model downloads required.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

COMFY = Path('L:/Github/ComfyUI')
sys.path.insert(0, str(COMFY))

import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader
import comfy.utils

OUT = Path('C:/github/REMASTER_STAGING/prototypes')
DUMP = Path('C:/github/Einhander/windows-x64/hd_dump_rgba/einhander-texture-replacements')
PACK = Path('C:/github/Einhänder_HDtext01/textures/SCUS-94243/replacements')
ATLAS = 'texpage-P4-A66CC6DBBDB6CA2B-39C6AF1D67F5C8F0-64x256-128-0-128x256-P0-15.png'
NATIVE_KEY = '5CC44E5F-053D9A00.png'


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def upscale(path, model, passes, output, tile_size=256):
    started = time.monotonic()
    source = Image.open(path).convert('RGBA')
    rgb = np.asarray(source.convert('RGB'), dtype=np.float32) / 255
    image = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
    with torch.inference_mode():
        for i in range(passes):
            print(f'{path.name}: pass {i + 1}/{passes}, input {tuple(image.shape)}', flush=True)
            image = comfy.utils.tiled_scale(
                image, lambda tile: model(tile.to('cuda', dtype=torch.float16)).float(),
                tile_x=tile_size, tile_y=tile_size, overlap=32, upscale_amount=4,
                output_device='cpu',
            ).clamp_(0, 1)
    pixels = (image[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
    result = Image.fromarray(pixels)
    # The PSX alpha channel carries transparency/STP class. Do not invent new
    # intermediate classes with an RGB network or bilinear alpha interpolation.
    result.putalpha(source.getchannel('A').resize(result.size, Image.Resampling.NEAREST))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output)
    expected = tuple(x * 4 ** passes for x in source.size)
    assert result.size == expected
    with Image.open(output) as check:
        check.load()
        assert check.size == expected
        assert check.getchannel('A').tobytes() == source.getchannel('A').resize(expected, Image.Resampling.NEAREST).tobytes()
    return {
        'source': str(path), 'source_sha256': sha(path),
        'output': str(output), 'output_sha256': sha(output),
        'source_size': source.size, 'output_size': result.size,
        'model_passes': passes, 'seconds': round(time.monotonic() - started, 2),
        'alpha': 'exact nearest-neighbor copy of source classes; verified',
        'installed_in_game': False, 'in_game_QA': 'not run',
    }


def main():
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; this proof expects the installed RTX 3090 Ti')
    torch.set_num_threads(4)
    records = []
    for model_name in ['RealESRGAN_x4plus.pth', '4x-UltraSharp.pth']:
        print('Loading', model_name, flush=True)
        path = COMFY / 'models/upscale_models' / model_name
        state = torch.load(path, map_location='cpu', weights_only=True)
        model = ModelLoader().load_from_state_dict(state).eval().to('cuda').half()
        if model.scale != 4:
            raise ValueError('Expected a 4x checkpoint')
        folder = OUT / model_name.removesuffix('.pth')
        rec = upscale(DUMP / (NATIVE_KEY + '.orig'), model, 2,
                      folder / 'native16x/einhander-texture-replacements' / NATIVE_KEY)
        rec.update(model=model_name, model_sha256=sha(path), native_scale=16,
                   note='Two passes from a local original backup. Native source is 64x64, so output is 1024x1024.')
        records.append(rec)
        if model_name == 'RealESRGAN_x4plus.pth':
            rec = upscale(PACK / ATLAS, model, 1,
                          folder / 'duckstation16x/textures/SCUS-94243/replacements' / ATLAS)
            rec.update(model=model_name, model_sha256=sha(path), native_scale=16,
                       note='One additional 4x pass on the downloaded 4x pack. Output is 2048x4096. Inherits earlier upscale/palette decisions; no recovered native atlas.')
            records.append(rec)
        del model, state
        torch.cuda.empty_cache()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'prototype_manifest.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(records, indent=2), flush=True)


if __name__ == '__main__':
    main()
