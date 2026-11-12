"""Reconstruct verified fighter blueprint line fields in bounded native UVs.

The original indexed line/shadow/glow signal defines every stroke. No new
geometry, lettering, 3D details or icons are introduced. All unmapped atlas
pixels stay exact to the current candidate resampled by nearest-neighbour.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw

from build_three_asset_proof import verify_stock


ROOT = Path(__file__).resolve().parents[1]
QUEUE = Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
BASE = ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v4/pack'
CAPTURE = ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v3/native-fighter/capture.jsonl'
OUT = ROOT/'remaster-audit/menu-restoration/fighter-blueprint-candidate-v1'
SCALE = 16
EXPECTED_KEYS = {
    'ECFB77E3-0001B466','ECFB77E3-236629BD','ECFB77E3-411C62A8',
    'ECFB77E3-4FE32821','ECFB77E3-8CBA9638','ECFB77E3-B5956369',
    'ECFB77E3-C1CAA268','ECFB77E3-DD532904','ECFB77E3-F6FBE721',
    'ECFB77E3-F798F5B6','ECFB77E3-FB10C304',
}
REGIONS = [(0,0,127,84),(72,85,127,170),(0,109,71,180)]
REGION_ROLES = ['Primary thin wireframe hull','Curved engine/arm ring','Engine and attachment signal layers']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(raw, clut, metadata):
    words = np.frombuffer(raw,dtype='<u2').reshape(metadata['height'],metadata['width_words'])
    indices = np.empty((words.shape[0],words.shape[1]*4),np.uint8)
    for column,shift in enumerate((0,4,8,12)):
        indices[:,column::4] = (words>>shift)&15
    values = np.frombuffer(clut,dtype='<u2')
    palette = np.stack(((values&31)<<3,((values>>5)&31)<<3,((values>>10)&31)<<3,
                        np.where(values==0,0,np.where(values&0x8000,255,127))),axis=1).astype(np.uint8)
    return indices,palette


def restore(indices,palette,base):
    result = base.copy()
    selected = np.zeros(result.shape[:2],bool)
    for x0,y0,x1,y1 in REGIONS:
        # Two source texels provide the original neighbour context to the
        # cubic contour field; cropped atlas boundaries are not new edges.
        px0,py0,px1,py1=max(0,x0-2),max(0,y0-2),min(256,x1+2),min(256,y1+2)
        source = indices[py0:py1,px0:px1].astype(np.float32)
        field = cv2.resize(source,((px1-px0)*SCALE,(py1-py0)*SCALE),interpolation=cv2.INTER_CUBIC)
        # A restrained line contrast pass counters interpolation softness.
        # It sharpens the existing shared signal without tracing or adding
        # surfaces, so faint technical strokes and their holes remain intact.
        smooth = cv2.GaussianBlur(field,(0,0),SCALE*.22,borderType=cv2.BORDER_REPLICATE)
        field = np.clip(field+.18*(field-smooth),0,15)
        field = field[(y0-py0)*SCALE:(y1-py0)*SCALE,(x0-px0)*SCALE:(x1-px0)*SCALE]
        low = np.floor(field).astype(np.uint8)
        high = np.minimum(low+1,15)
        part = (field-low)[:,:,None]
        rgb = palette[low,:3]*(1-part)+palette[high,:3]*part
        result[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE,:3] = np.rint(np.clip(rgb,0,255)).astype(np.uint8)
        # Alpha/STP are categorical renderer data, not an interpolation
        # channel. Retain the exact current/native footprint at every sample.
        selected[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE] = True
    return result,selected


def preview(path,key,source,base,authored,box):
    x0,y0,x1,y1=box
    w,h=(x1-x0)*4,(y1-y0)*4
    canvas=Image.new('RGB',(w,3*(h+30)),(10,17,23))
    draw=ImageDraw.Draw(canvas)
    panels=[('Native source at4x; geometry authority',source.crop(box).resize((w,h),Image.Resampling.NEAREST)),
            ('Current candidate at the same4x display scale',Image.fromarray(base).crop(tuple(v*SCALE for v in box)).resize((w,h),Image.Resampling.LANCZOS)),
            ('Reconstructed shared line/glow field; exact original alpha',Image.fromarray(authored).crop(tuple(v*SCALE for v in box)).resize((w,h),Image.Resampling.LANCZOS))]
    for row,(label,pixels) in enumerate(panels):
        y=row*(h+30)
        draw.text((4,y+5),label,fill='white')
        canvas.paste(pixels.convert('RGB'),(0,y+27))
    canvas.save(path)


def main():
    if OUT.exists():
        raise ValueError('Existing blueprint candidates are immutable')
    cv2.setNumThreads(2)
    queue=json.loads(QUEUE.read_bytes())['assets']
    assets=[a for a in queue if a.get('source_verified') and a['key'].startswith('ECFB77E3-')]
    if {a['key'] for a in assets}!=EXPECTED_KEYS or len(assets)!=11:
        raise ValueError('Expected all eleven independently verified blueprint palettes')
    draw_records=[json.loads(line) for line in CAPTURE.read_bytes().splitlines()]
    (OUT/'pack/einhander-texture-replacements').mkdir(parents=True)
    (OUT/'pack/Hashes.ini').write_text('',encoding='utf-8')
    (OUT/'previews').mkdir()
    shutil.copy2(__file__,OUT/'build-source.py')
    files=[]
    for asset in sorted(assets,key=lambda a:a['key']):
        key=asset['key'];source=Path(asset['source'])
        metadata,raw,clut=verify_stock(source.parent,key)
        if metadata['depth']!=0 or metadata['width_words']!=64 or metadata['height']!=256:
            raise ValueError('Expected the verified256x256 four-bit blueprint atlas')
        if sha(raw)!=asset['raw_sha256'] or sha(clut)!=asset['clut_sha256']:
            raise ValueError('Source queue changed: '+key)
        indices,palette=decode(raw,clut,metadata)
        native=palette[indices]
        if sha(native.tobytes())!=asset['source_pixel_sha256']:
            raise ValueError('Independent words/CLUT decode mismatch: '+key)
        base_path=BASE/'einhander-texture-replacements'/(key+'.png')
        with Image.open(base_path) as image:
            base_size=list(image.size)
            if image.mode!='RGBA' or image.size!=(2048,2048):
                raise ValueError('Unexpected current blueprint base size/mode')
            base=np.array(image.resize((4096,4096),Image.Resampling.NEAREST))
        authored,selected=restore(indices,palette,base)
        if not np.array_equal(authored[~selected],base[~selected]):
            raise ValueError('Unmapped art/labels changed: '+key)
        native_alpha=np.repeat(np.repeat(native[:,:,3],SCALE,0),SCALE,1)
        if not np.array_equal(authored[:,:,3],base[:,:,3]) or not np.array_equal(authored[:,:,3],native_alpha):
            raise ValueError('Original native/base categorical alpha footprint changed: '+key)
        classes=sorted(map(int,np.unique(authored[:,:,3])))
        if not set(classes)<={0,127,255}:
            raise ValueError('Noncategorical alpha: '+key)
        output=OUT/'pack/einhander-texture-replacements'/(key+'.png')
        Image.fromarray(authored).save(output)
        with Image.open(output) as reopened:
            if reopened.mode!='RGBA' or reopened.tobytes()!=authored.tobytes():
                raise ValueError('PNG round-trip mismatch: '+key)
        receipts=[dict(line=n,**{k:r.get(k) for k in ('event','key','frame','source_kind','native_words','uv_bounds','source_word_xy','xy','not_visibility_proof','cpu_vram_may_be_stale')})
                  for n,r in enumerate(draw_records,1) if r.get('key')==key and r.get('event')=='source_draw_query_matched'][:16]
        source_archives={name:dict(path=str(source.with_suffix(suffix)),sha256=sha(source.with_suffix(suffix).read_bytes()))
                         for name,suffix in (('words','.words.bin'),('clut','.clut.bin'),('validity','.valid.bin'),('metadata','.source.json'))}
        files.append(dict(key=key,kind='bounded_blueprint_lineart',role='Original fighter thin hull and engine/attachment schematic',
                          source=str(source),source_sha256=sha(source.read_bytes()),source_size=[256,256],
                          source_archives=source_archives,source_words_sha256=sha(raw),source_clut_sha256=sha(clut),
                          source_crc_verified=True,source_decode_verified=True,source_validity_complete=True,
                          source_metadata=metadata,selected_native_regions=[list(r) for r in REGIONS],
                          region_roles=REGION_ROLES,base_path=str(base_path),base_sha256=sha(base_path.read_bytes()),
                          base_size=base_size,baseline_resample='nearest-neighbour2x to4096x4096; no outside reconstruction',
                          outside_regions_exact=True,native_alpha_footprint_exact=True,base_alpha_footprint_exact=True,
                          alpha_stp_values=classes,source_local_uv_coordinates_preserved=True,
                          changed_rgb_texels=int(np.any(authored[:,:,:3]!=base[:,:,:3],axis=2).sum()),
                          outputs={'pack':dict(path=str(output),sha256=sha(output.read_bytes()),size=[4096,4096],rgba_sha256=sha(authored.tobytes()))},
                          native_draw_receipts=receipts,in_game_acceptance='Pending composed fighter/arm selection, animation and clipping review'))
        if key in ('ECFB77E3-FB10C304','ECFB77E3-F798F5B6'):
            preview(OUT/'previews'/(key+'-hull-4x.png'),key,Image.fromarray(native),base,authored,(0,0,127,84))
            preview(OUT/'previews'/(key+'-engine-4x.png'),key,Image.fromarray(native),base,authored,(72,85,127,170))
        print(json.dumps(dict(key=key,changed_rgb_texels=files[-1]['changed_rgb_texels'],checks='PASS')),flush=True)
    report=dict(format=1,contract='verified-fighter-blueprint-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
                production_installed=False,game_actions=0,source_keys=11,expected_keys=sorted(EXPECTED_KEYS),files=files,
                source_queue=str(QUEUE),source_queue_sha256=sha(QUEUE.read_bytes()),
                base_pack_root=str(BASE),native_capture=dict(path=str(CAPTURE),sha256=sha(CAPTURE.read_bytes())),
                method='Bounded cubic source-index contour fields with restrained line-contrast recovery; continuous interpolation within each exact captured CLUT. No glyph masks, replacement fonts, invented geometry or new annotations.',
                geometry_changes='Subpixel shared line/glow reconstruction only; original atlas layout and all UV positions retained',
                limits=['Only the three actually mapped hull/engine rectangles are rebuilt; annotations, other icons, unused fill and unobserved alternate hull rectangles remain exact to the nearest-resized current candidate.',
                        'RGB interpolation creates continuous source-palette colors; it does not force exact native-center colors or add technical detail.',
                        'All original native alpha/STP samples remain exact; composed animation and every craft state require real-game review.'])
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(pack=str(OUT/'pack'),source_keys=11,checks='PASS')))


if __name__=='__main__':
    main()
