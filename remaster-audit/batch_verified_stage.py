"""Checkpointed stock-first Stage 1 capture-route candidate pack.

Manually inspected glyph/sign/effect groups stay deterministic. Neural results
are candidates until a full in-game review passes; file dimensions are not a
claim of recovered detail or complete level coverage.
"""
import collections
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

from build_three_asset_proof import verify_stock
from prototype_upscale import COMFY,upscale
from PIL import Image
from spandrel import ModelLoader
import torch

ROOT=Path('C:/github/REMASTER_STAGING/stage1_remaster')
SOURCE=Path('C:/github/REMASTER_STAGING/three_asset_proof/proof-run-uhd/stock/einhander-texture-replacements')
OUT=ROOT/'candidates/einhander-texture-replacements'
MANIFEST=ROOT/'candidates/manifest.json'
TEXT_OR_PIXEL_ART=set('''01C8BE36 0A43BDBC 1CCA84E3 264C5A76 275F4336 285846CF
2864B9D7 2C6866AA 2C781811 2E64C06C 3DA22883 41E75A55 44C16454 4EC9441C
57FFDED8 5C02D3C1 5F101F62 675EC00F 6BCA3D83 786B98BF 7D2C7E3C 83F09674
8D0FCF8A 913A6603 913FE978 921FC559 92B5C656 98FB547F 9B5B049C 9D8DF52A
A2A5D9A5 AAA5C104 AAE3C8F2 C41E89FC C544AC0D C8BD81AB CBC3F6CD D050AD1B
DD0B6963 E1F18F98 E4774D79 EFEB55FF F6B5AA33 09FE00B4 2E54C06C C8BD91AB'''.split())
PLAYER=set('5CC44E5F 724E77DA 7E3ADD56 B16492B1 E2F3477C'.split())


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    torch.set_num_threads(4)
    OUT.mkdir(parents=True,exist_ok=True);(OUT.parent/'Hashes.ini').touch(exist_ok=True)
    prior=json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'assets':[]}
    done={row['key']:row for row in prior['assets']}
    paths=sorted(SOURCE.glob('*.png'))
    variants=collections.Counter(p.stem.split('-')[0] for p in paths)
    model=None;started=time.monotonic();failures=[]
    for index,path in enumerate(paths):
        key=path.stem;th=key.split('-')[0]
        try:
            metadata,raw,palette=verify_stock(SOURCE,key)
        except (ValueError,FileNotFoundError) as error:
            failures.append({'key':key,'reason':str(error),'status':'excluded source'});continue
        with Image.open(path) as loaded:native=loaded.convert('RGBA')
        pixel_hash=digest(native.tobytes())
        output=OUT/path.name
        old=done.get(key)
        if native.height>256:
            failures.append({'key':key,'reason':'Large boot/framebuffer capture; excluded from Stage 1 texture candidates','status':'excluded source'});continue
        early_ui=metadata['frame']<6800 and th not in PLAYER
        deterministic=early_ui or th in TEXT_OR_PIXEL_ART or variants[th]>8 or len(native.convert('RGB').getcolors(256) or [])<=4
        expected_category=('text_or_pixel_art' if th in TEXT_OR_PIXEL_ART or early_ui else 'palette_effect_or_simple_surface') if deterministic else ('player_mechanical' if th in PLAYER else 'world_or_mechanical_candidate')
        if old and old.get('category')==expected_category and old.get('source_pixel_sha256')==pixel_hash and output.exists() and digest(output.read_bytes())==old.get('output_sha256'):
            continue
        if deterministic:
            factor=16 if th in TEXT_OR_PIXEL_ART else 8
            result=native.resize((native.width*factor,native.height*factor),Image.Resampling.NEAREST)
            result.save(output)
            method=f'nearest {factor}x; exact RGB/classes; glyph/sign/palette-cycle preservation'
            category='text_or_pixel_art' if th in TEXT_OR_PIXEL_ART or early_ui else 'palette_effect_or_simple_surface'
        else:
            cached=Path('C:/github/REMASTER_STAGING/stage01_city/candidates/ultrasharp16x/einhander-texture-replacements')/path.name
            original=Path('C:/github/REMASTER_STAGING/stage01_city/stock/einhander-texture-replacements')/path.name
            reuse=False
            if cached.exists() and original.exists():
                with Image.open(original) as old_source:reuse=old_source.convert('RGBA').tobytes()==native.tobytes()
            if reuse:
                shutil.copy2(cached,output);method='Reused cached exact-source UltraSharp 16x'
            else:
                if model is None:
                    model=ModelLoader().load_from_state_dict(torch.load(COMFY/'models/upscale_models/4x-UltraSharp.pth',map_location='cpu',weights_only=True)).eval().to('cuda').half()
                upscale(path,model,2,output)
                method='UltraSharp two 4x RGB passes, exact nearest source alpha classes'
            category='player_mechanical' if th in PLAYER else 'world_or_mechanical_candidate'
        with Image.open(output) as check:
            result=check.convert('RGBA');size=list(result.size)
            if result.getchannel('A').tobytes()!=native.getchannel('A').resize(result.size,Image.Resampling.NEAREST).tobytes():
                raise RuntimeError('Output class map changed: '+key)
            if deterministic and result.resize(native.size,Image.Resampling.NEAREST).tobytes()!=native.tobytes():
                raise RuntimeError('Deterministic source roundtrip failed: '+key)
        row={'key':key,'source':str(path),'source_pixel_sha256':pixel_hash,
             'raw_words_sha256':digest(raw),'clut_sha256':digest(palette),
             'first_frame':metadata['frame'],'source_size':list(native.size),'output_size':size,
             'output':str(output),'output_sha256':digest(output.read_bytes()),'method':method,'category':category,
             'palette_variants_observed':variants[th],'source_alpha_counts':dict(collections.Counter(native.getchannel('A').tobytes())),
             'source_crc_verified':True,'independent_decode_verified':True,'alpha_exact_nearest_verified':True,
             'status':'candidate; stage review pending'}
        done[key]=row
        report={'format':1,'stock_source':str(SOURCE),'scope':'Observed first capture route, level/route provenance requires visual verification',
                'method_decision':'Existing UltraSharp retained after real CUDA comparison against cleanup+UltraSharp and PBRify DAT2. Cleanup is selective, not unconditional.',
                'production_installed':False,'assets':list(done.values()),'excluded':failures}
        MANIFEST.write_text(json.dumps(report,indent=2)+'\n')
        if index%20==0:print(json.dumps({'processed':len(done),'of':len(paths),'key':key,'seconds':round(time.monotonic()-started,1)}),flush=True)
    summary={'candidate_pngs':len(done),'excluded_sources':len(failures),
             'methods':dict(collections.Counter(x['category'] for x in done.values())),
             'all_masks_verified':all(x['alpha_exact_nearest_verified'] for x in done.values()),
             'seconds':round(time.monotonic()-started,2),'manifest':str(MANIFEST)}
    (ROOT/'candidates/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
