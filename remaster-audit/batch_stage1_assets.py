"""Incremental local UltraSharp batch. Preserve stock; skip unchanged outputs."""
import hashlib
import json
import sys
import time
from pathlib import Path

from prototype_upscale import COMFY, upscale
from spandrel import ModelLoader
from PIL import Image
import torch

ROOT=Path('C:/github/REMASTER_STAGING/stage01_city')
SOURCE=ROOT/'stock/einhander-texture-replacements'
OUT=ROOT/'candidates/ultrasharp16x/einhander-texture-replacements'
MANIFEST=ROOT/'candidates/ultrasharp16x/manifest.json'
PLAYER={'5CC44E5F-053D9A00.png','724E77DA-21FDE894.png','7E3ADD56-21FDE894.png',
        'B16492B1-21FDE894.png','E2F3477C-21FDE894.png'}

def pixels_hash(path):
    with Image.open(path) as image:
        return hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()

all_assets='--all-nontext' in sys.argv
assets=[]
for path in sorted(SOURCE.glob('*.png')):
    with Image.open(path) as image:
        if path.name in PLAYER or (all_assets and image.height>=32 and image.width<=256 and path.stem.split('-')[0]!='E584DC41'):
            assets.append(path)
OUT.mkdir(parents=True,exist_ok=True)
previous=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'assets':[]}
records={row['key']:row for row in previous['assets']}
model=None
started=time.monotonic()
for path in assets:
    source_hash=pixels_hash(path)
    output=OUT/path.name
    prior=records.get(path.stem)
    if output.exists() and prior and prior.get('source_pixel_sha256')==source_hash:
        print('CACHED',path.name,flush=True)
        continue
    # Reuse the prior 1024 proof when the actual decoded stock pixels match.
    earlier=Path('C:/github/REMASTER_STAGING/prototypes/4x-UltraSharp/native16x/einhander-texture-replacements')/path.name
    original=Path('C:/github/Einhander/windows-x64/hd_dump_rgba/einhander-texture-replacements')/(path.name+'.orig')
    if earlier.exists() and original.exists() and pixels_hash(original)==source_hash:
        import shutil
        shutil.copy2(earlier,output)
        with Image.open(path) as image:source_size=list(image.size)
        with Image.open(output) as image:output_size=list(image.size)
        row={'source':str(path),'output':str(output),'source_size':source_size,'output_size':output_size,
             'method':'reused existing exact-source UltraSharp result','seconds':0,'model_passes':0}
        print('REUSED',path.name,flush=True)
    else:
        if model is None:
            torch.set_num_threads(4)
            checkpoint=COMFY/'models/upscale_models/4x-UltraSharp.pth'
            model=ModelLoader().load_from_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)).eval().to('cuda').half()
        row=upscale(path,model,2,output)
        row['method']='UltraSharp two 4x passes from untouched stock (16x source dimensions)'
        print('GENERATED',path.name,row['output_size'],flush=True)
    row.update(key=path.stem,source_pixel_sha256=source_hash,
               category='player' if path.name in PLAYER else 'unclassified',
               stage='observed capture; full-stage coverage unverified',
               status='candidate; in-game visual approval pending')
    records[path.stem]=row
    MANIFEST.write_text(json.dumps({'model':'4x-UltraSharp','scope':'source-based restoration candidates; not newly authored native-4K artwork',
                                   'assets':list(records.values())},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'candidate_assets':len(records),'seconds':round(time.monotonic()-started,2),'manifest':str(MANIFEST)},indent=2),flush=True)
