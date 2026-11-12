"""Resume the user's local RTX/UltraSharp full-dump batch, checkpoint per PNG."""
import argparse,hashlib,json,time,os,shutil
from pathlib import Path
from checkpoint_json import write_json
from PIL import Image
from prototype_upscale import COMFY,upscale
from spandrel import ModelLoader
import torch

parser=argparse.ArgumentParser()
parser.add_argument('--keys',nargs='*',help='Representative proofs before a category-wide batch')
parser.add_argument('--output-name',default='candidates')
parser.add_argument('--profile',choices=['all-candidates','world-machines'],default='all-candidates')
args=parser.parse_args()
ROOT=Path('C:/github/REMASTER_STAGING/full-remaster')
OUT=ROOT/args.output_name/'einhander-texture-replacements';OUT.mkdir(parents=True,exist_ok=True)
(OUT.parent/'Hashes.ini').touch(exist_ok=True)
manifest=OUT.parent/'manifest.json'
old=json.loads(manifest.read_text()) if manifest.exists() else {'assets':[]}
done={r['key']:r for r in old['assets']}
torch.set_num_threads(4)
checkpoint=COMFY/'models/upscale_models/4x-UltraSharp.pth'
model=None;started=time.monotonic()
queue=json.loads((ROOT/'queue.json').read_text())['assets']
cache_manifest=json.loads(Path('C:/github/REMASTER_STAGING/stage1_remaster/candidates/manifest.json').read_text())
neural_cached={r['key'] for r in cache_manifest['assets'] if 'UltraSharp' in r['method']}
if args.profile=='world-machines':
 world=set('2294438F 3955512F 46D3938E 57AC02A0 73BF9877 87C52FC0 95A3BCF8 AB2DB563 AB58BBA4 B4C7A0EB 1263A036 38DC02FE'.split())
 queue=[r for r in queue if r['source_verified'] and (r['key'] in neural_cached or (r['kind']=='native_page' and r['key'].split('-')[0] in world))]
selected_keys={r['key'] for r in queue}
if args.keys:
 selected=set(args.keys);queue=[r for r in queue if r['key'] in selected]
 if {r['key'] for r in queue}!=selected:raise RuntimeError('Requested proof key missing from source inventory')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for index,row in enumerate(queue):
 key=row['key'];source=Path(row['source']);dest=OUT/(key+'.png')
 if key in done and done[key].get('pipeline_version')==2 and done[key]['source_pixel_sha256']==row['source_pixel_sha256'] and dest.exists() and digest(dest)==done[key]['output_sha256']:continue
 with Image.open(source) as image:native=image.convert('RGBA')
 if hashlib.sha256(native.tobytes()).hexdigest()!=row['source_pixel_sha256']:raise RuntimeError('Source changed: '+key)
 target=tuple(v*row['target_scale'] for v in native.size)
 # Reuse only a result whose complete native source pixels match and whose
 # dimensions already meet this batch's target. Other earlier candidates stay.
 reused=False
 caches=[Path('C:/github/REMASTER_STAGING/stage1_remaster/page-model-cache')/(key+'.png'),
         Path('C:/github/REMASTER_STAGING/stage1_remaster/candidates/einhander-texture-replacements')/(key+'.png')]
 for cache in caches:
  if not cache.exists():continue
  if cache.parent.name!='page-model-cache' and key not in neural_cached:continue
  with Image.open(cache) as image:
   if image.size!=target:continue
  # Cached candidates have source provenance in their adjacent authoring
  # manifest, or a page source independently validated by the inventory.
  meta=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')/(key+'.png')
  if meta.exists():
   with Image.open(meta) as image:match=hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()==row['source_pixel_sha256']
   if match:shutil.copy2(cache,dest);reused=True;break
 if not reused:
  if model is None:
   if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
   model=ModelLoader().load_from_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)).eval().to('cuda').half()
  passes=1 if row['target_scale']<=4 else 2
  upscale(source,model,passes,dest,tile_size=512)
 with Image.open(dest) as image:result=image.convert('RGBA')
 if result.size!=target:result=result.resize(target,Image.Resampling.LANCZOS)
 # Alpha is a PS1 transparency/STP class, not ordinary image opacity.
 result.putalpha(native.getchannel('A').resize(target,Image.Resampling.NEAREST))
 result.save(dest)
 with Image.open(dest) as image:
  if image.size!=target or image.getchannel('A').tobytes()!=native.getchannel('A').resize(target,Image.Resampling.NEAREST).tobytes():raise RuntimeError('Output verification failed: '+key)
 done[key]={**row,'output':str(dest),'output_size':list(target),'output_sha256':digest(dest),
    'pipeline_version':2,
    'method':'exact-source cached UltraSharp' if reused else 'local UltraSharp RGB, native transparency/STP classes',
    'neural_detail':True,'status':'generated; in-game/category review required'}
 write_json(manifest,{'model':str(checkpoint),'scope':'Full original-dump restoration batch; source-verified assets and legacy candidates distinguished','assets':list(done.values())})
 completed=sum(k in done for k in selected_keys)
 write_json(OUT.parent/'progress.json',{'pid':os.getpid(),'completed':completed,'queued':len(queue),'all_manifest_assets':len(done),'current_key':key,'profile':args.profile,'elapsed_seconds':time.monotonic()-started,'model':'4x-UltraSharp','cuda':True,'manifest':str(manifest)})
 print(json.dumps({'completed':completed,'queued':len(queue),'key':key,'reused':reused,'seconds':round(time.monotonic()-started,1)}),flush=True)
write_json(OUT.parent/'complete.json',{'completed':sum(k in done for k in selected_keys),'queued':len(queue),'elapsed_seconds':time.monotonic()-started})
