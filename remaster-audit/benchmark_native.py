"""Measure a larger real original-backup input; outputs are throughput tests."""
import json
from pathlib import Path

from prototype_upscale import COMFY, DUMP, upscale
from spandrel import ModelLoader
import torch

out = Path('C:/github/REMASTER_STAGING/prototypes/benchmark-only')
model_path = COMFY / 'models/upscale_models/RealESRGAN_x4plus.pth'
model = ModelLoader().load_from_state_dict(torch.load(model_path, map_location='cpu', weights_only=True)).eval().to('cuda').half()
torch.set_num_threads(4)
rows = []
for name in ['5CC44E5F-053D9A00.png', 'DD0B6963-4C1DD349.png']:
    row = upscale(DUMP / (name + '.orig'), model, 2, out / name)
    row['purpose'] = 'throughput benchmark; text sheet is not an approved remaster asset'
    rows.append(row)
(out / 'timings.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
print(json.dumps(rows, indent=2), flush=True)
