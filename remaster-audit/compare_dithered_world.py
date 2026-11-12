"""Selective cleanup comparison on actual city/water stock crops, GPU-only RGB."""
import json
import time
from pathlib import Path
from PIL import Image,ImageDraw
import torch
from compare_restoration_models import load,infer,COMFY
ROOT=Path('C:/github/REMASTER_STAGING/stage1_remaster')
SOURCE=ROOT/'page-source/stock/einhander-texture-replacements'
OUT=ROOT/'dither-comparison'
OUT.mkdir(exist_ok=True)
torch.set_num_threads(4)
cases=[('AB2DB563',(0,0,64,64)),('B4C7A0EB',(0,128,64,192))]
records=[]
sheet=Image.new('RGB',(1536,840),(25,25,25));draw=ImageDraw.Draw(sheet)
for row,(family,rect) in enumerate(cases):
    paths=sorted(SOURCE.glob(family+'-*.png'));path=paths[len(paths)//2]
    native=Image.open(path).convert('RGBA').crop(rect)
    labels=['stock nearest','UltraSharp','dedither + UltraSharp','PBRify DAT2']
    for col,label in enumerate(labels):
        out=OUT/(family+'-'+str(col)+'.png');started=time.monotonic()
        if col==0:result=native.resize((1024,1024),Image.Resampling.NEAREST)
        elif out.exists():result=Image.open(out).convert('RGBA')
        else:
            source=native
            if col==2:
                model=load(Path('C:/github/REMASTER_STAGING/models/1x-DitherDeleterV3-Smooth.pth'))
                source=infer(source,model);del model;torch.cuda.empty_cache()
            model=load(COMFY/'models/upscale_models/4x-UltraSharp.pth' if col<3 else Path('C:/github/REMASTER_STAGING/models/4x-PBRify_UpscalerDAT2_V1.pth'))
            result=infer(infer(source,model),model);del model;torch.cuda.empty_cache()
        assert result.getchannel('A').tobytes()==native.getchannel('A').resize(result.size,Image.Resampling.NEAREST).tobytes()
        result.save(out)
        sheet.paste(result.convert('RGB').resize((376,376),Image.Resampling.LANCZOS),(col*384+4,row*420+36))
        draw.text((col*384+4,row*420+8),family+' '+label,fill='white')
        records.append({'source':str(path),'crop':rect,'method':label,'output':str(out),'mask_exact':True,'seconds':round(time.monotonic()-started,2)})
        print(json.dumps(records[-1]),flush=True)
sheet.save(OUT/'comparison.png')
(OUT/'manifest.json').write_text(json.dumps({'cases':records,'status':'visual review pending; authoring load, not game performance'},indent=2)+'\n')
