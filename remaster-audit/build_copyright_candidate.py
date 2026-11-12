"""Restore the exact source copyright/date/SQUARE strip, including its red A."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"remaster-audit/menu-restoration/copyright-square-candidate-v1"
BASE = ROOT/"remaster-audit/menu-restoration/palette-field-candidate-v7"
LIBRARY = ROOT/"windows-x64/tools/build_hud_ui_candidate.py"
QUEUE = Path("C:/github/REMASTER_STAGING/full-remaster/queue.json")
CAPTURE = ROOT/"remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v4/native-title/capture.jsonl"
REGION = (80, 236, 199, 248)
SCALE = 16


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_hud():
    spec = importlib.util.spec_from_file_location("copyright_hud", LIBRARY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def geometry(indices, reference):
    x0, y0, x1, y1 = REGION
    crop = indices[y0:y1, x0:x1]
    red = np.isin(crop, [9, 13])
    white_levels = np.max(reference[:, :3], axis=1).astype(np.float32)/248
    white_levels[[9, 13, 15]] = 0
    white = cv2.resize(white_levels[crop], ((x1-x0)*SCALE, (y1-y0)*SCALE), interpolation=cv2.INTER_CUBIC)
    # A shared high-contrast face field retains the native glyph contours,
    # counters and spacing. Original gray samples guide the contour rather
    # than becoming independent surfaces or importing the reserved red slots.
    white = np.clip((white-.10)/.80, 0, 1)
    white = white*white*(3-2*white)
    red_levels = np.zeros(16, np.float32);red_levels[9]=1;red_levels[13]=72/248
    red_field = np.clip(cv2.resize(red_levels[crop], white.shape[::-1], interpolation=cv2.INTER_CUBIC), 0, 1)
    red_cover = np.clip(cv2.resize(red.astype(np.float32), white.shape[::-1], interpolation=cv2.INTER_CUBIC), 0, 1)
    # A single traced color region keeps the stylized A red at every level;
    # grayscale interpolation never passes through its reserved palette slots.
    red_cover = np.clip((red_cover-.08)/.84, 0, 1)
    red_cover = red_cover*red_cover*(3-2*red_cover)
    gx = cv2.Sobel(white, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(white, cv2.CV_32F, 0, 1, ksize=3)
    norm = np.maximum(np.hypot(gx, gy), .001)
    light = (-.6*gx-.8*gy)/norm
    edge = 4*white*(1-white)
    white = np.clip(white*(1+.065*light*edge), 0, 1)
    return crop, white, red_field, red_cover


def render(geometry_data, palette, reference):
    crop, white, red_field, red_cover = geometry_data
    # The white ramp excludes both source-red slots. Palette animation/tints
    # still come from each exact draw CLUT rather than an invented typeface.
    gray_order = np.array([15, 14, 12, 11, 10, 8, 7, 6, 5, 4, 2, 1, 0])
    levels = np.max(reference[gray_order, :3], axis=1).astype(float)/248
    rgb = np.stack([np.interp(white, levels, palette[gray_order, channel]) for channel in range(3)], axis=2)
    red_rgb = np.stack([np.interp(red_field, [0, 72/248, 1], palette[[15, 13, 9], channel]) for channel in range(3)], axis=2)
    rgb = rgb*(1-red_cover[:, :, None])+red_rgb*red_cover[:, :, None]
    nearest_gray = gray_order[np.argmin(np.abs(white[:, :, None]-levels), axis=2)]
    alpha = palette[nearest_gray, 3].copy()
    # Coverage remains categorical. The nearest source class for each traced
    # white/red surface owns the pixel; no interpolated opacity is written.
    red_owner = red_cover >= .5
    red_indices = np.where(red_field >= (1+72/248)/2, 9, 13)
    alpha[red_owner] = palette[red_indices[red_owner], 3]
    result = np.dstack((np.rint(np.clip(rgb, 0, 255)).astype(np.uint8), alpha))
    return result


def composite(data):
    rgb=data[:, :, :3].astype(int);bg=np.full(rgb.shape, [10, 14, 45])
    return np.where((data[:, :, 3]>=128)[:, :, None], np.minimum(255, rgb+bg), rgb).astype(np.uint8)


def main():
    if OUT.exists():
        raise ValueError("Copyright candidates are immutable; choose another output")
    cv2.setNumThreads(2)
    hud=load_hud()
    rows=[r for r in json.loads(QUEUE.read_bytes())["assets"] if r["key"].startswith("8E1A509D-")]
    if len(rows)!=3 or not all(r["source_verified"] for r in rows):
        raise ValueError("Expected the three independently verified palette keys")
    refrow=next(r for r in rows if r['key']=="8E1A509D-8808F70A")
    m,raw,clut=hud.verify_stock(Path(refrow['source']).parent,refrow['key'])
    indices,reference=hud.decode_indices(raw,m),hud.palette_rgba(clut)
    geom=geometry(indices,reference)
    output_preview=render(geom,reference,reference)
    for folder in ('pack/einhander-texture-replacements','previews'):(OUT/folder).mkdir(parents=True,exist_ok=True)
    shutil.copy2(__file__,OUT/'build-source.py')
    (OUT/'pack/Hashes.ini').write_text('',encoding='utf-8')
    # Actual4xscale comparison uses the draw's native119x12 UV rectangle.
    x0,y0,x1,y1=REGION
    native=reference[indices[y0:y1,x0:x1]]
    old=Image.open(BASE/'pack/einhander-texture-replacements'/(refrow['key']+'.png')).convert('RGBA').crop(tuple(c*SCALE for c in REGION))
    samples=[('VERIFIED SOURCE / NATIVE x4',Image.fromarray(composite(native)).resize((476,48),Image.Resampling.NEAREST)),
             ('PREVIOUS CANDIDATE / ACTUAL x4',Image.fromarray(composite(np.array(old))).resize((476,48),Image.Resampling.LANCZOS)),
             ('RESTORED COPYRIGHT + SQUARE / ACTUAL x4',Image.fromarray(composite(output_preview)).resize((476,48),Image.Resampling.LANCZOS))]
    preview=Image.new('RGB',(600,231),(10,14,25));draw=ImageDraw.Draw(preview)
    for i,(label,pic) in enumerate(samples):draw.text((6,i*77+3),label,fill='white');preview.paste(pic,(6,i*77+23))
    preview.save(OUT/'previews/copyright-square-actual4x.png')
    outputs=[];evidence=[json.loads(l) for l in CAPTURE.read_text().splitlines() if l.strip()]
    for row in rows:
        key=row['key'];source=Path(row['source']);metadata,words,palbytes=hud.verify_stock(source.parent,key)
        palette=hud.palette_rgba(palbytes);decoded=palette[hud.decode_indices(words,metadata)]
        if hashlib.sha256(words).hexdigest()!=row['raw_sha256'] or hashlib.sha256(palbytes).hexdigest()!=row['clut_sha256'] or hashlib.sha256(decoded.tobytes()).hexdigest()!=row['source_pixel_sha256']:
            raise ValueError('Independent source verification mismatch: '+key)
        if not np.array_equal(hud.decode_indices(words,metadata),indices):raise ValueError('Palette variant changed geometry')
        basepath=BASE/'pack/einhander-texture-replacements'/(key+'.png')
        with Image.open(basepath) as image:before=np.array(image.convert('RGBA'))
        if before.shape!=(4096,4096,4):raise ValueError('Expected complete v7 atlas')
        authored=before.copy();patch=render(geom,palette,reference)
        authored[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE]=patch
        outside_exact=(np.array_equal(before[:y0*SCALE],authored[:y0*SCALE]) and np.array_equal(before[y1*SCALE:],authored[y1*SCALE:]) and np.array_equal(before[y0*SCALE:y1*SCALE,:x0*SCALE],authored[y0*SCALE:y1*SCALE,:x0*SCALE]) and np.array_equal(before[y0*SCALE:y1*SCALE,x1*SCALE:],authored[y0*SCALE:y1*SCALE,x1*SCALE:]))
        if not outside_exact or not set(np.unique(patch[:,:,3]))<={0,127,255}:raise ValueError('Bounded coverage check failed')
        out=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(authored).save(out)
        with Image.open(out) as verify:
            if verify.tobytes()!=authored.tobytes():raise ValueError('PNG roundtrip mismatch')
        receipts=[dict(line=i,event=e['event'],frame=e['frame'],uv_bounds=e.get('uv_bounds'),xy=e.get('xy'),semi=e.get('semi')) for i,e in enumerate(evidence,1) if e.get('key')==key and e.get('uv_bounds')==[80,236,198,247]]
        outputs.append({'key':key,'source':str(source),'source_sha256':sha(source),'source_words_sha256':hashlib.sha256(words).hexdigest(),'source_clut_sha256':hashlib.sha256(palbytes).hexdigest(),'source_metadata':metadata,'base':str(basepath),'base_sha256':sha(basepath),'selected_native_regions':[list(REGION)],'outputs':{'pack':{'path':str(out),'sha256':sha(out)}},'checks':{'source_crc_clut_decode_exact':True,'outside_copyright_region_byte_exact_to_v7':outside_exact,'categorical_classes_only':True,'png_roundtrip_exact':True},'draw_evidence':receipts,'changed_rgb_pixels':int(np.any(patch[:,:,:3]!=before[y0*SCALE:y1*SCALE,x0*SCALE:x1*SCALE,:3],axis=2).sum()),'in_game_acceptance':'pending actual title/footer review'})
        print(json.dumps({'key':key,'protected_outside_exact':True}),flush=True)
    manifest={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':len(outputs),'production_installed':False,'game_actions':0,'exact_wording':'©1997/1998 SQUARE','method':'Source grayscale coverage becomes one shared high-contrast contour/bevel field. Reserved red9/13 pixels define a separate coherent A surface. No fonts/OCR/new wording. The full119x12source strip is rebuilt; all outside pixels remain byte-identical to menu v7.','region_native_half_open':list(REGION),'base_manifest_sha256':sha(BASE/'manifest.json'),'tool_sha256':sha(Path(__file__)),'capture_source':str(CAPTURE),'capture_sha256':sha(CAPTURE),'assets':outputs,'limits':['The main strip intentionally refines source coverage, while output alpha remains categorical. Native alpha footprint equality is not claimed.','Live draw receipts above concern the prior candidate and prove source/UV binding only; new overlay runtime acceptance remains pending.','The4xpreview demonstrates texture appearance on a sample blue background; it is not a gameplay screenshot.']}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pack':str(OUT/'pack'),'manifest':str(OUT/'manifest.json'),'assets':len(outputs),'checks':'PASS'}))


if __name__=='__main__':main()
