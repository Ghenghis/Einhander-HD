"""Visual candidate search only; scores never establish replacement coverage."""
import json
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
PACK = Path('C:/github/Einhänder_HDtext01/textures/SCUS-94243/replacements')
DUMP = Path('C:/github/Einhander/windows-x64/hd_dump_rgba/einhander-texture-replacements')
RECT = re.compile(r'-(\d+)x(\d+)(?:-P\d+-\d+)?\.png$')
sources = ['0878817D-9414AA42', '5CC44E5F-053D9A00', 'B16492B1-21FDE894']
best = {s: [] for s in sources}
templates = {}
for key in sources:
    image = np.asarray(Image.open(DUMP / (key + '.png.orig')).convert('RGBA'))
    templates[key] = (image[:, :, :3].copy(), (image[:, :, 3] > 0).astype(np.uint8) * 255)
for path in sorted(PACK.glob('*.png')):
    m = RECT.search(path.name)
    if not m:
        continue
    size = tuple(map(int, m.groups()))
    if min(size) < 64:
        continue
    atlas = np.asarray(Image.open(path).convert('RGB').resize(size, Image.Resampling.BOX))
    for key, (template, mask) in templates.items():
        scores = cv2.matchTemplate(atlas, template, cv2.TM_SQDIFF_NORMED, mask=mask)
        scores[~np.isfinite(scores)] = 100
        score, _, pos, _ = cv2.minMaxLoc(scores)
        best[key].append({'score': score, 'pack_file': path.name, 'xy': pos})
for key in best:
    best[key] = sorted(best[key], key=lambda x: x['score'])[:4]
(ROOT / 'visual-candidates.json').write_text(json.dumps(best, indent=2), encoding='utf-8')
print(json.dumps(best, indent=2), flush=True)
