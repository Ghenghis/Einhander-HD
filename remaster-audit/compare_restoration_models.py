"""Small measured GPU comparison; mask authority never enters an RGB model."""
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

COMFY=Path('L:/Github/ComfyUI')
sys.path.insert(0,str(COMFY))
import comfy.utils
import numpy as np
import torch
from PIL import Image,ImageDraw,ImageFont
from spandrel import ModelLoader

ROOT=Path('C:/github/REMASTER_STAGING/three_asset_proof')
SOURCE=ROOT/'proof-run-uhd/stock/einhander-texture-replacements'
OUT=ROOT/'model-comparison'


def load(path):
    model=ModelLoader().load_from_state_dict(torch.load(path,map_location='cpu',weights_only=True))
    model=model.eval().to('cuda')
    return model.half() if model.supports_half else model.float()


def infer(image,model):
    data=torch.from_numpy(np.array(image.convert('RGB'),dtype=np.float32)/255).permute(2,0,1).unsqueeze(0)
    with torch.inference_mode():
        result=comfy.utils.tiled_scale(data,lambda x:model(x.to('cuda',dtype=model.dtype)).float(),
            tile_x=128,tile_y=128,overlap=16,upscale_amount=model.scale,output_device='cpu').clamp(0,1)
    pixels=(result[0].permute(1,2,0).numpy()*255).round().astype(np.uint8)
    output=Image.fromarray(pixels)
    output.putalpha(image.getchannel('A').resize(output.size,Image.Resampling.NEAREST))
    return output


def main():
    torch.set_num_threads(4)
    if not torch.cuda.is_available():raise RuntimeError('3090 CUDA runtime required')
    OUT.mkdir(exist_ok=True)
    key='5CC44E5F-053D9A00'
    source=Image.open(SOURCE/(key+'.png')).convert('RGBA')
    cached=ROOT/'pack/einhander-texture-replacements'/(key+'.png')
    modelroot=Path('C:/github/REMASTER_STAGING/models')
    records=[]
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for label in ['dedither-ultrasharp','pbrify-dat2']:
        path=OUT/(label+'.png')
        if path.exists():
            with Image.open(path) as prior:
                if prior.getchannel('A').tobytes()!=source.getchannel('A').resize(prior.size,Image.Resampling.NEAREST).tobytes():
                    raise ValueError('Cached mask mismatch')
                records.append({'method':label,'output':str(path),'size':list(prior.size),
                                'alpha_exact':True,'status':'reused cached candidate; visual comparison required'})
            print('CACHED',label,flush=True);continue
        began=time.monotonic();torch.cuda.reset_peak_memory_stats()
        if label=='dedither-ultrasharp':
            checkpoint=modelroot/'1x-DitherDeleterV3-Smooth.pth'
            model=load(checkpoint)
            if model.scale!=1:raise ValueError('Expected 1x cleanup model')
            cleaned=infer(source,model);cleaned.save(OUT/'dedither-1x.png')
            del model;torch.cuda.empty_cache()
            model=load(COMFY/'models/upscale_models/4x-UltraSharp.pth')
            result=infer(infer(cleaned,model),model)
        else:
            checkpoint=modelroot/'4x-PBRify_UpscalerDAT2_V1.pth'
            model=load(checkpoint)
            result=infer(infer(source,model),model)
        expected=source.getchannel('A').resize(result.size,Image.Resampling.NEAREST)
        if expected.tobytes()!=result.getchannel('A').tobytes():raise ValueError('Mask mismatch')
        result.save(path)
        row={'method':label,'output':str(path),'size':result.size,
             'seconds':round(time.monotonic()-began,3),
             'gpu_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
             'source_rgba_sha256':hashlib.sha256(source.tobytes()).hexdigest(),
             'checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
             'alpha_exact':True,'status':'candidate; visual comparison required'}
        records.append(row);print(json.dumps(row),flush=True)
        del model;torch.cuda.empty_cache()
    manifest={'gpu':torch.cuda.get_device_name(0),'start_utc':start,
              'end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'note':'GPU comparison overlaps authoring capture; exclude this interval from performance acceptance.',
              'candidates':records}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    options=[('Stock (nearest)',source),('Existing UltraSharp',Image.open(cached)),
             ('1x cleanup + UltraSharp',Image.open(OUT/'dedither-ultrasharp.png')),
             ('PBRify DAT2',Image.open(OUT/'pbrify-dat2.png'))]
    sheet=Image.new('RGB',(1600,450),'#151b23');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',20)
    for i,(label,img) in enumerate(options):
        img=img.convert('RGBA');img.putalpha(img.getchannel('A').point(lambda a:255 if a else 0))
        img=img.resize((392,392),Image.Resampling.NEAREST if i==0 else Image.Resampling.LANCZOS)
        sheet.paste(img,(i*400+4,48),img);draw.text((i*400+8,10),label,font=font,fill='white')
    sheet.save(OUT/'comparison.png')


if __name__=='__main__':main()
