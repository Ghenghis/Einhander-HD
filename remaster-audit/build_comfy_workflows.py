"""Export explicit ComfyUI API graphs for each remaster asset category."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent/'workflows';OUT.mkdir(exist_ok=True)
def graph(neural,cleanup=False):
 g={
 '1':{'class_type':'LoadImage','inputs':{'image':'einhander/source.png'},'_meta':{'title':'Untouched native RGB and original PS1 class mask'}},
 '2':{'class_type':'UpscaleModelLoader','inputs':{'model_name':'4x-UltraSharp.pth'},'_meta':{'title':'Existing local UltraSharp; no diffusion or prompt reinterpretation'}},
 '3':{'class_type':'ImageUpscaleWithModel','inputs':{'image':['1',0],'upscale_model':['2',0]},'_meta':{'title':'RGB restoration pass 1 (4x)'}},
 '4':{'class_type':'ImageUpscaleWithModel','inputs':{'image':['3',0],'upscale_model':['2',0]},'_meta':{'title':'RGB restoration pass 2 (16x total)'}},
 '5':{'class_type':'ImageScale','inputs':{'image':['4',0] if neural else ['1',0],'upscale_method':'lanczos' if neural else 'nearest-exact','width':4096,'height':4096,'crop':'disabled'},'_meta':{'title':'Set per-asset target dimensions; preserve source aspect ratio'}},
 '6':{'class_type':'MaskToImage','inputs':{'mask':['1',1]},'_meta':{'title':'Bypass RGB models for transparency/STP authority'}},
 '7':{'class_type':'ImageScale','inputs':{'image':['6',0],'upscale_method':'nearest-exact','width':4096,'height':4096,'crop':'disabled'}},
 '8':{'class_type':'ImageToMask','inputs':{'image':['7',0],'channel':'red'}},
 '9':{'class_type':'JoinImageWithAlpha','inputs':{'image':['5',0],'alpha':['8',0]},'_meta':{'title':'Restore original 0/127/255 class map at target size'}},
 '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':'Einhander/candidate'},'_meta':{'title':'Candidate only; verify source, spelling, masks, palettes and in-game UVs'}}}
 if not neural:
  for n in ('2','3','4'):g.pop(n)
 if cleanup:
  g['11']={'class_type':'UpscaleModelLoader','inputs':{'model_name':'1x-DitherDeleterV3-Smooth.pth'},'_meta':{'title':'Optional cleanup, only for reviewed dithered artwork'}}
  g['12']={'class_type':'ImageUpscaleWithModel','inputs':{'image':['1',0],'upscale_model':['11',0]}}
  g['3']['inputs']['image']=['12',0]
 return g
for name,g in [('01-mechanical-ultrasharp',graph(True)),('02-dithered-art-cleanup-trial',graph(True,True)),
               ('03-ui-art-ultrasharp-proof',graph(True)),('04-text-effects-class-preserving',graph(False))]:
 (OUT/(name+'.api.json')).write_text(json.dumps(g,indent=2)+'\n')
print('Wrote 4 category-specific ComfyUI API graphs to '+str(OUT))
