"""Rebuild source-proven selection lettering from scalable outlines.

The old candidate interpolated the original shade numbers. That retained the
wide glow and fragmented high-contrast edge pixels. This supplement replaces
only explicitly registered English word quads with new font contours. Native
pixels are registration/provenance evidence; they never define new strokes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'remaster-audit'
PARENT = AUDIT / 'dev-center-evidence/hud-world-region-candidate-20261112-v9'
OUT = AUDIT / 'menu-restoration/selection-vector-candidate-v11'
SOURCE = Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
HEADER_FONT = Path('C:/Windows/Fonts/bahnschrift.ttf')
LABEL_FONT = Path('C:/Windows/Fonts/SourceSansPro-SemiBold.ttf')
TITLE_FONT = Path('C:/Windows/Fonts/georgiab.ttf')
SCALE = 16
HEADER_WORDS = [
    ('FIGHTER', (0,168,104,188)),
    ('ARMAMENT', (0,189,128,209)),
    ('SELECTION', (0,210,136,230)),
]
# These registrations agree with the native word quads and their shared I cell.
# ARM is the first three 16-pixel cells of ARMAMENT, sampled independently.
HEADER_ADVANCES = {'FIGHTER':[16,8,16,16,16,16,16],
                   'ARMAMENT':[16]*8,
                   'SELECTION':[16,16,16,16,16,16,8,16,16]}
LABELS = [
    ('ARM',(89,39,110,48)), ('I',(113,39,117,48)),
    ('II',(120,39,126,48)), ('MACHIN',(48,151,89,160)),
    ('E',(29,0,36,9)), ('GUN',(89,151,113,160)),
]
MANIPULATOR = ('MANIPULATOR',(136,216,212,225))
OTHER_SELECTION = [('Unknown',(136,168,248,188)),('Type',(136,189,192,209)),
                   ('I',(200,189,216,209)),('II',(220,189,240,209))]
# Optical registration inside the verified source atlas. These are explicitly
# distinct from the exact word-draw receipts below. Unclear spec/model numbers
# are omitted; a readable English label is never inferred from a filename.
OTHER_WEAPON_LABELS = [
 ('BLADE',(0,0,36,9)),('CANNON',(38,0,82,9)),('FLASH',(84,0,118,9)),
 ('HEDGEHOG',(0,9,60,19)),('MOSQUITO',(62,9,118,19)),
 ('GRENADE',(0,19,52,29)),('SPREADER',(53,19,109,29)),
 ('PYTHON',(0,29,43,39)),('RIOT',(44,29,71,39)),('VULCAN',(73,29,116,39)),
 ('WASP',(0,39,32,48)),('JUNO',(33,39,64,48)),('ARM',(65,39,88,48)),
 ('SWAP',(128,0,159,8)),('GUNPOD',(162,0,205,8)),
 ('GUNPOD',(128,8,169,16)),('1',(173,8,178,16)),('FIRE',(183,8,205,16)),
 ('GUNPOD',(128,16,169,24)),('2',(173,16,178,24)),('FIRE',(183,16,205,24)),
 ('MACHINEGUN',(128,24,194,32)),('FIRE',(198,24,220,32)),
 ('GUNPOD',(128,32,169,40)),('FIRE',(172,32,195,40)),
 ('ARM',(128,40,150,48)),('SHIFTING',(154,40,202,48)),
 ('FLARES',(0,86,35,95)),('DISPENSER',(38,86,88,95)),
 ('POWER',(0,120,32,128)),('MANIPULATOR',(35,120,101,128)),
 ('GUIDED',(0,128,35,136)),('MISSILE',(38,128,74,136)),('MOUNT',(76,128,109,136)),
 ('40mm',(0,144,26,151)),('GATLING',(29,144,69,151)),('CANNON',(72,144,112,151)),('RAIL',(0,151,21,160)),
 ('Unknown',(0,224,56,232)),('Fighter',(0,232,56,242)),
 ('Type',(0,242,32,256)),('I',(40,242,44,254)),('II',(51,242,56,254)),
]
TITLE_WORDS = [('GAME START',(0,43,88,55)),
               ('CONFIGURATION',(0,58,112,71)),
               ('FILE OPTION',(0,75,88,87)),('GALLERY',(0,91,60,104))]
CRAFT_NAMES = [('Astraea FGA Mk.I',(0,0,95,8)),
               ('Endymion FRS Mk.II',(0,9,105,17)),
               ('Endymion FRS Mk.III',(0,18,108,26)),
               ('J.Fighter Type II',(0,27,104,35))]

def alphabet_cells():
    rows=[('ABCDEFGHIJ',0),('KLMNOPQRST',12),('UVWXYZ():;',24),
          ('abcdefghij',36),('klmnop qr ',48),('stuvw x yz',60),('!?        ',72)]
    # Descenders extend into deliberately blank storage cells on the next
    # row. The source ink proves these are15/13/14px glyphs, not12px glyphs.
    heights={'g':15,'j':13,'p':13,'q':13,'y':14}
    return [(c,(128+n*12,y,140+n*12,y+heights.get(c,12))) for text,y in rows for n,c in enumerate(text) if c!=' ']

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path): return {'path':str(path),'sha256':sha(path)}

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fitted_mask(text,width,height,font_path,cap_height,top=1.0,inset=.35):
    """Rasterize new vector outlines, with a common cap height and baseline."""
    ss=2;factor=SCALE*ss
    if text in ('I','II') and width<=6:
        mask=Image.new('L',(width*factor,height*factor));draw=ImageDraw.Draw(mask)
        centers=[width/2] if text=='I' else [width/2-1,width/2+1]
        for center in centers:
            draw.rectangle((round((center-.34)*factor),round(top*factor),
                            round((center+.34)*factor),round((top+cap_height)*factor)),fill=255)
        return np.asarray(mask.resize((width*SCALE,height*SCALE),Image.Resampling.LANCZOS))
    font=ImageFont.truetype(str(font_path),round(cap_height*factor*1.45))
    temp=Image.new('L',(max(4096,width*factor*3),1024));draw=ImageDraw.Draw(temp)
    draw.text((32,32),text,font=font,fill=255,stroke_width=0)
    box=temp.getbbox()
    if not box:raise ValueError('Empty vector text')
    ink=temp.crop(box)
    target=(max(1,round((width-2*inset)*factor)),round(cap_height*factor))
    ink=ink.resize(target,Image.Resampling.LANCZOS)
    mask=Image.new('L',(width*factor,height*factor))
    mask.paste(ink,(round(inset*factor),round(top*factor)))
    return np.asarray(mask.resize((width*SCALE,height*SCALE),Image.Resampling.LANCZOS))

def new_header_mask(word,rect):
    width,height=rect[2]-rect[0],rect[3]-rect[1]
    result=np.zeros((height*SCALE,width*SCALE),np.uint8);x=0
    for c,advance in zip(word,HEADER_ADVANCES[word]):
        # A shared 15-pixel cap and two-pixel top clearance fit the original
        # twenty-pixel quads without touching either atlas row boundary.
        glyph=fitted_mask(c,advance,height,HEADER_FONT,15,top=2,inset=1.65 if advance==16 else 1.1)
        result[:,x*SCALE:(x+advance)*SCALE]=glyph;x+=advance
    if x!=width:raise ValueError('Header advance registration mismatch')
    return result

def alphabet_mask(character,width,height,native):
    """New serif contour registered to the variable-width native draw cell.

    The12px storage pitch is not a12px draw advance. Registration metrics
    come from source support, while every new stroke/counter comes from TTF.
    """
    ss=2;factor=SCALE*ss
    yy,xx=np.where((native[:,:,3]>0)&(native[:,:,:3].max(2)>0))
    if not len(xx):raise ValueError('Empty source character registration')
    box=(int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1)
    font=ImageFont.truetype(str(TITLE_FONT),round(15*factor))
    temporary=Image.new('L',(1024,1024));draw=ImageDraw.Draw(temporary)
    draw.text((32,32),character,font=font,fill=255)
    ink=temporary.crop(temporary.getbbox())
    shape=(max(1,round((box[2]-box[0]-.4)*factor)),max(1,round((box[3]-box[1]-.4)*factor)))
    ink=ink.resize(shape,Image.Resampling.LANCZOS)
    cell=Image.new('L',(width*factor,height*factor))
    cell.paste(ink,(round((box[0]+.2)*factor),round((box[1]+.2)*factor)))
    result=np.asarray(cell.resize((width*SCALE,height*SCALE),Image.Resampling.LANCZOS))
    # No newly centered I/punctuation can escape the original sampled width.
    if result[:,box[2]*SCALE:].any() or result[box[3]*SCALE:,:].any():
        raise ValueError('New character escaped the variable native draw bounds')
    return result

def color_mask(mask,palette,blue=False,header=False):
    """Compact continuous RGB edges, with categorical PSX coverage classes.

    No old halo or source shade islands are carried forward. STP remains an
    explicit class: bright core/perimeter is opaque127, compact AA is255.
    Blue header faces retain their source blue/STP identity and cyan rim.
    """
    a=mask.astype(np.float32)/255
    inside=mask>=128
    rgba=np.zeros((*mask.shape,4),np.uint8)
    if blue:
        distance=cv2.distanceTransform(inside.astype(np.uint8),cv2.DIST_L2,5)
        edge=np.clip(1-distance/(SCALE*.42),0,1)
        # The blue palette's nonzero indices contain a broad pure-blue glow.
        # Its previous threshold promoted detached highlights and left a dark
        # center. Use a compact continuous cyan-blue face rather than that
        # low-contrast glow. These are only original palette hue mixtures.
        face=palette[0,:3].astype(np.float32)*.82+palette[1,:3].astype(np.float32)*.18
        cyan=palette[0,:3].astype(np.float32)
        color=face[None,None,:]*(1-edge[:,:,None])+cyan[None,None,:]*edge[:,:,None]
        rgba[:,:,:3]=np.rint(color*a[:,:,None]).astype(np.uint8)
        rgba[:,:,3]=np.where(mask==0,0,np.where((edge>.72)&(mask>=230),127,255))
    else:
        peak=palette[0,:3].astype(np.float32)
        rgba[:,:,:3]=np.rint(peak[None,None,:]*a[:,:,None]).astype(np.uint8)
        rgba[:,:,3]=np.where(mask==0,0,np.where(mask>=230,127,255))
    return rgba

def compose_preview(path,key,native,before,after,regions):
    scale=4;strips=[]
    for rect in regions:
        x0,y0,x1,y1=rect;w=(x1-x0)*scale;h=(y1-y0)*scale
        pane=max(w,240);row=Image.new('RGB',(3*pane,h+24),(4,7,15));d=ImageDraw.Draw(row)
        for n,(name,im,factor) in enumerate([('Native reference',native,1),('Previous replacement',before,16),('New vector contours',after,16)]):
            crop=im[y0*factor:y1*factor,x0*factor:x1*factor].copy()
            crop[crop[:,:,3]==0,:3]=0
            frame=Image.fromarray(crop[:,:,:3]).resize((w,h),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS)
            row.paste(frame,(n*pane,24));d.text((n*pane+3,4),name,fill='white')
        strips.append(row)
    canvas=Image.new('RGB',(max(x.width for x in strips),sum(x.height for x in strips)+28),(4,7,15));d=ImageDraw.Draw(canvas);d.text((4,5),key+' / actual native x4 / RGB with categorical coverage',fill='white');y=28
    for strip in strips:canvas.paste(strip,(0,y));y+=strip.height
    canvas.save(path)

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT);args=parser.parse_args();OUT=args.output.resolve()
    if OUT.exists():raise ValueError('Existing candidates are immutable; choose new output')
    if not OUT.is_relative_to((AUDIT/'menu-restoration').resolve()):raise ValueError('Expected isolated menu-restoration output')
    hud=module(ROOT/'windows-x64/tools/build_hud_ui_candidate.py','selection_vector_hud')
    mapmod=module(AUDIT/'map_vector_description_glyphs.py','selection_vector_map')
    source_map=json.loads((AUDIT/'menu-restoration/description-vector-candidate-v4/source-map.json').read_bytes())
    arm=next(s for s in source_map['scenes'] if s['scene']=='arm')
    proof=Path(arm['proof']['path']);proof_json=json.loads(proof.read_bytes())
    if sha(proof)!=arm['proof']['sha256']:raise ValueError('Native ARM source proof changed')
    frames=proof_json.get('gp0_frames',proof_json.get('frames',[]));draws=mapmod.parse_frame(frames[len(frames)//2])
    expected=[([896,256],[304,484],[0,189,48,209]),([896,256],[304,484],[0,210,135,230]),
              ([896,256],[288,484],[136,216,212,225])]
    expected.extend(([832,256],[272,484],list(r)) for t,r in LABELS[:3])
    expected.extend(([832,256],[288,484],list(r)) for t,r in LABELS[3:])
    receipts=[]
    for page,clut,uv in expected:
        found=[d for d in draws if d['page_xy_words']==page and d['clut_xy_words']==clut and d['source_uv_half_open']==uv]
        if not found:raise ValueError('Missing exact visible ARM word draw '+str(uv))
        receipts.extend(found)
    for d in ('pack/einhander-texture-replacements','previews','sources'):(OUT/d).mkdir(parents=True)
    (OUT/'pack/Hashes.ini').write_text('',encoding='utf-8');shutil.copy2(__file__,OUT/'build-source.py')
    rows=[]
    keys=['D0365088-79902A90','D0365088-B5A45715','1AD90FC9-02491337','1AD90FC9-4315989E','1AD90FC9-79902A90','323B5FB0-1C7962B3']
    for key in keys:
        metadata,raw,clut=hud.verify_stock(SOURCE,key)
        indices=hud.decode_indices(raw,metadata);palette=hud.palette_rgba(clut);native=palette[indices]
        parent=PARENT/'pack/einhander-texture-replacements'/(key+'.png')
        before=np.array(Image.open(parent).convert('RGBA'));after=before.copy();selected=np.zeros(before.shape[:2],bool);registrations=[]
        words=(HEADER_WORDS+OTHER_SELECTION+[MANIPULATOR] if key.startswith('D036')
               else OTHER_WEAPON_LABELS+LABELS if key.startswith('1AD')
               else TITLE_WORDS+CRAFT_NAMES+alphabet_cells())
        extra_regions=[]
        if key.startswith('323'):
            # The old continuous-field output bleeds descender glow into
            # unused adjacent storage cells. The source book is completely
            # mapped, including its blank background, so replace that entire
            # bounded book before placing the new variable-width glyphs.
            glyph_cells=np.zeros(native.shape[:2],bool)
            for c,(x0,y0,x1,y1) in alphabet_cells():glyph_cells[y0:y1,x0:x1]=True
            native_ink=(native[:,:,3]>0)&(native[:,:,:3].max(2)>0)
            if np.any(native_ink[0:86,128:248]&~glyph_cells[0:86,128:248]):
                raise ValueError('Unmapped content in alphabet book background')
            after[0:86*SCALE,128*SCALE:248*SCALE]=0
            selected[0:86*SCALE,128*SCALE:248*SCALE]=True
            extra_regions=[(128,0,248,86)]
        for word,rect in words:
            x0,y0,x1,y1=rect;width,height=x1-x0,y1-y0
            if (word,rect) in HEADER_WORDS:mask=new_header_mask(word,rect)
            elif (word,rect) in OTHER_SELECTION:
                if word in ('I','II'):
                    mask=np.zeros((height*SCALE,width*SCALE),np.uint8)
                    cells=[width/2] if word=='I' else [width/2-4,width/2+4]
                    for center in cells:
                        glyph=fitted_mask('I',8,height,TITLE_FONT,15,top=2,inset=1)
                        start=round((center-4)*SCALE);mask[:,start:start+8*SCALE]=glyph
                else:mask=fitted_mask(word,width,height,HEADER_FONT,15,top=2,inset=2)
            elif (word,rect) in TITLE_WORDS:mask=fitted_mask(word,width,height,TITLE_FONT,height-1.4,top=.7,inset=.3)
            elif (word,rect) in alphabet_cells() and key.startswith('323'):mask=alphabet_mask(word,width,height,native[y0:y1,x0:x1])
            else:mask=fitted_mask(word,width,height,LABEL_FONT,min(6.8,height-1.2),top=.6 if height==8 else 1.0,inset=.35)
            patch=color_mask(mask,palette,blue=key.endswith('B5A45715') and ((word,rect) in HEADER_WORDS or (word,rect) in OTHER_SELECTION),header=(word,rect) in HEADER_WORDS)
            after[y0*16:y1*16,x0*16:x1*16]=patch;selected[y0*16:y1*16,x0*16:x1*16]=True
            registrations.append({'text':word,'native_uv_half_open':list(rect),'new_vector_mask_sha256':hashlib.sha256(mask.tobytes()).hexdigest(),
                                  'ownership_evidence':'Exact observed ARM word quad' if (word,rect) in LABELS+[MANIPULATOR] else 'Optical registration in the CRC-verified native source PNG; individual draw ownership not asserted',
                                  'internal_registration':'16px header cells, I8px; fixed native advance' if (word,rect) in HEADER_WORDS else 'New vector outline fitted in explicitly listed source registration rectangle'})
        if not np.array_equal(before[~selected],after[~selected]):raise ValueError('Protected RGBA changed')
        if not set(map(int,np.unique(after[:,:,3])))<={0,127,255}:raise ValueError('Noncategorical alpha')
        target=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(after).save(target)
        if np.array(Image.open(target).convert('RGBA')).tobytes()!=after.tobytes():raise ValueError('PNG roundtrip failed')
        for suffix in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json'):
            src=SOURCE/(key+suffix)
            if src.exists():shutil.copy2(src,OUT/'sources'/src.name)
        preview=OUT/'previews'/(key+'.png');compose_preview(preview,key,native,before,after,[r for _,r in words if ((_,r) in HEADER_WORDS or (_,r) in OTHER_SELECTION or (_,r)==MANIPULATOR or (_,r) in LABELS or (_,r) in TITLE_WORDS)])
        rows.append({'key':key,'role':'Fresh source-registered selection headings and ARM labels','source':ref(SOURCE/(key+'.png')),'raw_sha256':hashlib.sha256(raw).hexdigest(),'clut_sha256':hashlib.sha256(clut).hexdigest(),'parent':ref(parent),'outputs':{'pack':{**ref(target),'size':[after.shape[1],after.shape[0]]}},'selected_native_regions':[list(r) for _,r in words]+[list(r) for r in extra_regions],'registered_words':registrations,'preview':ref(preview),'protected_rgba_exact':True,'categorical_alpha':True,'png_roundtrip_exact':True,'changed_rgba_texels':int(np.any(before!=after,axis=2).sum()),'live_acceptance':'pending actual candidate composed capture'})
    manifest={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),'contract':'selection-vector-source-registered-v10','asset_count':len(rows),'production_installed':False,'game_actions':0,'tool':ref(__file__),'fonts':[ref(HEADER_FONT),ref(LABEL_FONT),ref(TITLE_FONT)],'method':'New scalable font outlines in source-registered word cells; source registration metrics preserve variable character widths; compact categorical coverage and original palette-relative colors; no original bitmap stroke/halo interpolation.','source_arm_proof':ref(proof),'source_arm_screenshot':arm['screenshot'],'exact_draw_receipts':receipts,'assets':rows,'limits':['Professional crispness and exact original typeface fidelity are separate: fresh industrial sans outlines replace the damaged bitmap-derived outlines.','ARM source draws are exact. Other word/character registrations are optical source registration in the CRC-verified source; not individually encoded glyph packets.','Full atlas inventory is not claimed; unclear technical model/numeric specs and Japanese text remain inherited, explicitly outside this rebuilt subset.','No live visual acceptance until fresh replacement submissions and composed native/2160p captures are reviewed.']}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidate':str(OUT),'asset_count':len(rows),'protected_rgba':'PASS','exact_arm_draws':len(receipts),'png_roundtrip':'PASS'}))

if __name__=='__main__':main()
