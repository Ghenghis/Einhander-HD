"""Restore reviewed page families; preserve glyph pages and discrete PS1 classes.

Full pages supply a stable UV mapping when a draw spans multiple native uploads.
Outputs remain candidates until actual stage playback and pacing are reviewed.
"""
import collections
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from PIL import Image
from build_three_asset_proof import verify_stock
from prototype_upscale import COMFY,upscale
from spandrel import ModelLoader
import torch

ROOT=Path('C:/github/REMASTER_STAGING/stage1_remaster')
SOURCE=Path(os.environ.get('EIN_PAGE_SOURCE',str(ROOT/'page-source/stock/einhander-texture-replacements')))
OUT=ROOT/'page-candidates/einhander-texture-replacements'
# Explicit visual review of native contact sheets, not filename inference.
WORLD=set('2294438F 3955512F 46D3938E 57AC02A0 73BF9877 87C52FC0 95A3BCF8 AB2DB563 AB58BBA4 B4C7A0EB'.split())
PROTECT={'57AC02A0':[(72,108,132,180)],'73BF9877':[(128,96,256,192),(0,216,256,256)],
         'AB2DB563':[(0,216,256,256)],'AB58BBA4':[(0,0,256,64),(64,128,128,160)]}

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    torch.set_num_threads(4)
    OUT.mkdir(parents=True,exist_ok=True);(OUT.parent/'Hashes.ini').touch(exist_ok=True)
    base=json.loads((ROOT/'candidates/manifest.json').read_text())
    # Reuse exact approved-source player/font/effect candidates without inference.
    for row in base['assets']:
        dest=OUT/(row['key']+'.png')
        if not dest.exists():shutil.copy2(row['output'],dest)
    manifest_path=OUT.parent/'pages-manifest.json'
    old=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'pages':[]}
    rows={row['key']:row for row in old['pages']}
    model=None;start=time.monotonic();excluded=[]
    paths=sorted(SOURCE.glob('*.source.json'))
    for path in paths:
        meta=json.loads(path.read_text());key=meta['key'];th=key.split('-')[0]
        if meta['upload_serial']!=0:continue
        try:meta,raw,palette=verify_stock(SOURCE,key)
        except (ValueError,FileNotFoundError) as error:
            excluded.append({'key':key,'error':str(error)});continue
        native=Image.open(SOURCE/(key+'.png')).convert('RGBA');digest=sha(native.tobytes())
        out=OUT/(key+'.png');ai=th in WORLD
        method='UltraSharp 16x RGB reduced to 8x; native nearest class map' if ai else 'nearest 8x; native RGB and classes'
        if key in rows and rows[key]['source_pixel_sha256']==digest and rows[key]['method']==method and out.exists() and sha(out.read_bytes())==rows[key]['output_sha256']:continue
        if ai:
            if model is None:
                model=ModelLoader().load_from_state_dict(torch.load(COMFY/'models/upscale_models/4x-UltraSharp.pth',map_location='cpu',weights_only=True)).eval().to('cuda').half()
            cached=ROOT/'page-model-cache'/(key+'.png')
            if not cached.exists():upscale(SOURCE/(key+'.png'),model,2,cached,tile_size=512)
            with Image.open(cached) as loaded:
                result=loaded.convert('RGB').resize((2048,2048),Image.Resampling.LANCZOS)
            # Stencils/status symbols in mixed pages remain source-exact.
            for rect in PROTECT.get(th,[]):
                x0,y0,x1,y1=rect
                result.paste(native.crop(rect).convert('RGB').resize(((x1-x0)*8,(y1-y0)*8),Image.Resampling.NEAREST),(x0*8,y0*8))
            result.putalpha(native.getchannel('A').resize(result.size,Image.Resampling.NEAREST))
        else:result=native.resize((2048,2048),Image.Resampling.NEAREST)
        result.save(out)
        with Image.open(out) as check:
            assert check.getchannel('A').tobytes()==native.getchannel('A').resize(check.size,Image.Resampling.NEAREST).tobytes()
            if not ai:assert check.resize(native.size,Image.Resampling.NEAREST).tobytes()==native.tobytes()
        rows[key]={'key':key,'source':str(SOURCE/(key+'.png')),'source_pixel_sha256':digest,
                   'raw_sha256':sha(raw),'clut_sha256':sha(palette),'source_frame':meta['frame'],
                   'output':str(out),'output_sha256':sha(out.read_bytes()),'output_size':[2048,2048],
                   'method':method,'neural_detail':ai,'protected_rects':PROTECT.get(th,[]),
                   'source_decode_and_crc_verified':True,'alpha_class_exact_verified':True,
                   'status':'candidate; in-game stage and temporal palette review pending'}
        manifest_path.write_text(json.dumps({'pages':list(rows.values()),'excluded':excluded,'production_installed':False},indent=2)+'\n')
        print(json.dumps({'key':key,'pages':len(rows),'neural':ai,'elapsed':round(time.monotonic()-start,1)}),flush=True)
    print(json.dumps({'pages':len(rows),'neural':sum(r['neural_detail'] for r in rows.values()),'excluded':len(excluded),'seconds':round(time.monotonic()-start,1)},indent=2),flush=True)

if __name__=='__main__':main()
