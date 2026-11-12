"""Visual catalog of observed native page families and their palette variants."""
import json
import os
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(os.environ.get('EIN_PAGE_SESSION','C:/github/REMASTER_STAGING/stage1_remaster/page-source'))
SOURCE=ROOT/'stock/einhander-texture-replacements'
groups={}
for path in sorted(SOURCE.glob('*.source.json')):
    meta=json.loads(path.read_text())
    if meta['upload_serial']==0:groups.setdefault(meta['key'].split('-')[0],[]).append(meta)
items=list(groups.items())
for start in range(0,len(items),16):
    canvas=Image.new('RGB',(1200,1200),(45,45,45));draw=ImageDraw.Draw(canvas)
    for i,(th,rows) in enumerate(items[start:start+16]):
        x=(i%4)*300;y=(i//4)*300;meta=rows[len(rows)//2]
        with Image.open(SOURCE/(meta['key']+'.png')) as image:canvas.paste(image.convert('RGB'),(x+20,y+30))
        draw.text((x+8,y+8),f'{th} variants {len(rows)} f{meta["frame"]}',fill='white')
    path=ROOT/'captures'/f'page-catalog-{start//16+1}.jpg';canvas.save(path,quality=95);print(path)
print(json.dumps({'families':len(items),'palette_variants':sum(len(rows) for _,rows in items)}))
