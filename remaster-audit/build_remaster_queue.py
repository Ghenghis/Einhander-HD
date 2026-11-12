"""Inventory every native dump for the full 4K-class restoration batch."""
import hashlib,json,collections
from pathlib import Path
from PIL import Image
from build_three_asset_proof import verify_stock

OUT=Path('C:/github/REMASTER_STAGING/full-remaster')
SOURCES=[Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements'),
 Path('C:/github/REMASTER_STAGING/three_asset_proof/proof-run-uhd/stock/einhander-texture-replacements')]
SOURCES+=sorted(Path('C:/github/REMASTER_STAGING/hd-expansion').glob('capture-*/stock/einhander-texture-replacements'))
SOURCES+=sorted(Path('C:/github/REMASTER_STAGING/full-remaster').glob('ui-capture-*/stock/einhander-texture-replacements'))
OUT.mkdir(parents=True,exist_ok=True)
rows={};rejected=[]
for source in SOURCES:
 for p in sorted(source.glob('*.source.json')):
  key=p.name.removesuffix('.source.json')
  try:
   meta,raw,pal=verify_stock(source,key)
   with Image.open(source/(key+'.png')) as im:im=im.convert('RGBA');size=list(im.size);digest=hashlib.sha256(im.tobytes()).hexdigest()
   if key in rows:
    if rows[key]['source_pixel_sha256']!=digest:raise ValueError('Conflicting source pixels for same key')
    continue
   rows[key]={'key':key,'source':str(source/(key+'.png')),'source_size':size,'source_pixel_sha256':digest,
     'raw_sha256':hashlib.sha256(raw).hexdigest(),'clut_sha256':hashlib.sha256(pal).hexdigest(),
     'source_verified':True,'kind':'native_page' if not meta['upload_serial'] else 'upload',
     'first_frame':meta['frame'],'target_scale':min(16,4096//max(size)),'source_metadata':meta}
  except (ValueError,FileNotFoundError,json.JSONDecodeError) as error:rejected.append({'key':key,'source':str(p),'error':str(error)})
 print(json.dumps({'source':str(source),'verified_keys':len(rows),'rejected_observations':len(rejected)}),flush=True)
legacy=Path('C:/github/Einhander/windows-x64/hd_dump_rgba/einhander-texture-replacements')
for p in sorted(legacy.glob('*.png.orig')):
 key=p.name.removesuffix('.png.orig')
 if key in rows:continue
 with Image.open(p) as im:im=im.convert('RGBA');size=list(im.size);digest=hashlib.sha256(im.tobytes()).hexdigest()
 rows[key]={'key':key,'source':str(p),'source_size':size,'source_pixel_sha256':digest,'source_verified':False,
    'kind':'legacy_original','target_scale':min(16,4096//max(size)),
    'status':'Generate candidate only; requires raw/CLUT recapture before installation'}
# UI strips, splash uploads and small atlases first, then full pages. All
# categories remain queued; this is scheduling, not an exclusion policy.
queue=sorted(rows.values(),key=lambda r:(r['kind']=='native_page',r.get('first_frame',999999)>6800,max(r['source_size']),r['key']))
report={'scope':'All available original dumps; 16x native dimensions capped at 4096 pixels per axis; originals retained',
 'assets':queue,'rejected_observations':rejected,'counts':dict(collections.Counter(r['kind'] for r in queue))}
(OUT/'queue.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'queued':len(queue),'verified':sum(r['source_verified'] for r in queue),'counts':report['counts'],'queue':str(OUT/'queue.json')},indent=2),flush=True)
