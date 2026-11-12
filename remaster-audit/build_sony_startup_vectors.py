"""Fresh Sony startup lettering across its full upload and right-page alias."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import struct
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from build_three_asset_proof import verify_stock

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit';S=16
OUT=AUDIT/'menu-restoration/sony-startup-vector-candidate-v1'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
SOURCE=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
EXE=Path('C:/github/REMASTER_STAGING/disc_stock/files/SCUS_942.43')
FONT=Path('C:/Windows/Fonts/arialbd.ttf')
FULL='1AEAD6A5-B20FDBC4';RIGHT='7F7452F9-B20FDBC4'
LINES=[dict(text='Sony Computer Entertainment America',center=159.5,baseline=118),
       dict(text='Presents',center=160.0,baseline=134)]
RECEIPTS=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/evidence/draws.jsonl')
SQUARE_RECEIPTS=Path('C:/github/REMASTER_STAGING/stage1_remaster/integration-uhd/evidence/draws.jsonl')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def decode(raw,clut,width,height):
    words=np.frombuffer(raw,dtype='<u2').reshape(height,width//4);idx=np.empty((height,width),np.uint8)
    for c in range(4):idx[:,c::4]=(words>>(c*4))&15
    v=np.frombuffer(clut,dtype='<u2');pal=np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,
        np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)
    return pal[idx],pal

def text_field():
    mask=Image.new('L',(320*S,240*S));draw=ImageDraw.Draw(mask);font=ImageFont.truetype(str(FONT),15*S)
    records=[]
    for line in LINES:
        origin=line['center']*S-font.getlength(line['text'])/2
        draw.text((origin,line['baseline']*S),line['text'],font=font,fill=255,anchor='ls')
        records.append(dict(**line,font_size_native=15,origin_native=origin/S,
            advance_native=font.getlength(line['text'])/S))
    coverage=np.asarray(mask);result=np.zeros((240*S,320*S,4),np.uint8)
    result[:,:,3]=255  # Actual native black is0x8000/STP set.
    result[:,:,:3]=np.rint(coverage[:,:,None].astype(float)*248/255).astype(np.uint8)
    result[:,:,3][coverage>0]=127 # Actual native white0x7FFF/STP clear, including gray AA.
    return result,records

def svg_text():
    font=ImageFont.truetype(str(FONT),15*S);tt=TTFont(FONT);glyphs=tt.getGlyphSet();cmap=tt.getBestCmap();units=tt['head'].unitsPerEm
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">',
        '<title>Sony Computer Entertainment America Presents startup lettering</title>',
        '<rect width="320" height="240" fill="black"/>']
    for line in LINES:
        text=line['text'];origin=line['center']-font.getlength(text)/S/2
        parts.append('<g aria-label="'+html.escape(text,quote=True)+'" fill="#f8f8f8">')
        for i,char in enumerate(text):
            if char==' ':continue
            pen=SVGPathPen(glyphs);glyphs[cmap[ord(char)]].draw(pen)
            # Prefix plus current minus current advance includes its kerning
            # with the preceding character, matching the raster font layout.
            x=origin+(font.getlength(text[:i+1])-font.getlength(char))/S
            parts.append('<path transform="translate('+f'{x:.6f} {line["baseline"]}'+') scale('+f'{15/units:.9f} {-15/units:.9f}'+')" d="'+pen.getCommands()+'"/>')
        parts.append('</g>')
    parts.append('</svg>');tt.close();return '\n'.join(parts)+'\n'

def visual(a):return Image.fromarray(a[:,:,:3])

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes())
    for field in ['parent_candidate','font','builder','svg','native_composed_proof','embedded_executable']:
        assert sha(m[field]['path'])==m[field]['sha256']
    for sr in m['source_archives']:assert sha(sr['path'])==sr['sha256']
    md,raw,clut=verify_stock(out/'sources',FULL);rm,rr,rc=verify_stock(out/'sources',RIGHT)
    native,pal=decode(raw,clut,320,480);right_native,_=decode(rr,rc,256,256)
    assert np.array_equal(native,pixels(out/'sources'/(FULL+'.png')))
    assert np.array_equal(right_native,pixels(out/'sources'/(RIGHT+'.png')))
    assert np.array_equal(pal[[0,15]],np.array([[248,248,248,127],[0,0,0,255]],np.uint8))
    assert clut==rc and np.array_equal(np.frombuffer(raw,'<u2').reshape(480,80)[:256,64:80],np.frombuffer(rr,'<u2').reshape(256,64)[:,:16])
    field,records=text_field();rows={r['key']:r for r in m['files']}
    full=pixels(rows[FULL]['outputs']['pack']['path']);right=pixels(rows[RIGHT]['outputs']['pack']['path'])
    assert full.shape==(7680,5120,4) and right.shape==(4096,4096,4)
    assert np.array_equal(full[:240*S],field)
    baseline=np.repeat(np.repeat(native[240:],S,0),S,1)
    assert np.array_equal(full[240*S:],baseline),'Unrelated lower upload rows changed'
    del baseline
    prior=pixels(rows[RIGHT]['parent']['path']);upscaled=np.repeat(np.repeat(prior,2,0),2,1)
    mask=np.zeros((4096,4096),bool);mask[:240*S,:64*S]=True
    assert np.array_equal(right[~mask],upscaled[~mask]),'Right-page unrelated pixels changed'
    assert np.array_equal(right[:240*S,:64*S],full[:240*S,256*S:320*S]),'Sony page seam differs'
    for row in rows.values():
        assert sha(row['outputs']['pack']['path'])==row['outputs']['pack']['sha256']
        assert set(np.unique(pixels(row['outputs']['pack']['path'])[:,:,3]))<={127,255}
    exe=Path(m['embedded_executable']['path']).read_bytes()
    assert exe[0x13D14:0x13D14+38400]==raw[:38400]
    assert exe[0xE294:0xE294+32]==clut
    assert records==m['line_registration']
    assert (out/'sony-startup-native-vector.svg').read_text()==svg_text()
    result=dict(outcome='PASS',new_key_source_crc_clut_verified=True,native_decode_exact=True,
        native_classes_actual_black255_white127=True,lower240rows_nearest_source_exact=True,
        right_page_outside_nearest_parent_exact=True,page_seam_rgba_exact=True,
        svg_font_outline_recipe_exact=True,embedded_320x240_bitmap_exact=True,
        full_dimensions=[5120,7680],right_dimensions=[4096,4096],live_acceptance='NOT RUN',
        at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result

def build(out):
    if out.exists():raise ValueError('Immutable output already exists')
    parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    assert FULL not in parents and RIGHT in parents
    (out/'sources').mkdir(parents=True);pack=out/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
    (out/'pack/Hashes.ini').write_text('');archives=[]
    for key in [FULL,RIGHT]:
        verify_stock(SOURCE,key)
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            dest=out/'sources'/(key+suffix);shutil.copyfile(SOURCE/(key+suffix),dest);archives.append(ref(dest))
    md,raw,clut=verify_stock(out/'sources',FULL);native,pal=decode(raw,clut,320,480)
    field,records=text_field();full=np.repeat(np.repeat(native,S,0),S,1);full[:240*S]=field
    fullpath=pack/(FULL+'.png');Image.fromarray(full).save(fullpath)
    rightparent=Path(parents[RIGHT]['composed_path']);assert sha(rightparent)==parents[RIGHT]['sha256']
    prior=pixels(rightparent);assert prior.shape==(2048,2048,4)
    right=np.repeat(np.repeat(prior,2,0),2,1);right[:240*S,:64*S]=full[:240*S,256*S:320*S]
    rightpath=pack/(RIGHT+'.png');Image.fromarray(right).save(rightpath)
    (out/'sony-startup-native-vector.svg').write_text(svg_text(),encoding='utf-8')
    # Keep the original composed Sony proof, distinct from generated artwork.
    proof=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/captures/boot.png')
    shutil.copyfile(proof,out/'native-sony-composed-proof.png')
    preview=Image.new('RGB',(1280,1980),(12,23,39));draw=ImageDraw.Draw(preview)
    draw.text((8,8),'Verified native Sony startup / original320x240 composition at4x',fill='white')
    preview.paste(visual(native[:240]).resize((1280,960),Image.Resampling.NEAREST),(0,28))
    draw.text((8,998),'Fresh Arial Bold vectors / actual4x / full upload and right-page shared exact pixels',fill='white')
    preview.paste(visual(field).resize((1280,960),Image.Resampling.LANCZOS),(0,1020))
    preview.save(out/'sony-startup-before-after-actual4x.png')
    shutil.copyfile(__file__,out/'build-source.py')
    files=[dict(key=FULL,native_dimensions=[320,480],source_verified_new_key=True,
        parent_key_present=False,parent_candidate=ref(PARENT),source=ref(out/'sources'/(FULL+'.png')),
        baseline_policy='Verified full native320x480 decoded image; unrelated lower240rows nearest16exact',
        selected_native_regions=[[0,0,320,240]],full_rebuild=True,allow_integer_resolution_increase=True,
        outputs=dict(pack=dict(**ref(fullpath),size=[5120,7680])),protected_outside_exact=True,live_verified=False),
      dict(key=RIGHT,native_dimensions=[256,256],source_verified_new_key=False,parent=ref(rightparent),
        source=ref(out/'sources'/(RIGHT+'.png')),baseline_policy='Entire parent8x image nearest2x; replace only source-proven right64nativepixels of Sony screen',
        selected_native_regions=[[0,0,64,240]],full_rebuild=True,allow_integer_resolution_increase=True,
        outputs=dict(pack=dict(**ref(rightpath),size=[4096,4096])),protected_outside_exact=True,live_verified=False)]
    m=dict(schema_version=1,contract='sony-startup-vector-and-page-seam-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),font=ref(FONT),builder=ref(out/'build-source.py'),asset_count=2,files=files,
        source_archives=archives,svg=ref(out/'sony-startup-native-vector.svg'),native_composed_proof=ref(out/'native-sony-composed-proof.png'),
        preview=ref(out/'sony-startup-before-after-actual4x.png'),embedded_executable=ref(EXE),
        embedded_source=dict(original_bitmap_dimensions=[320,240],bitmap_file_offset=0x13D14,bitmap_bytes=38400,
            bitmap_guest_address='0x80023514',clut_file_offset=0xE294,clut_guest_address='0x8001DA94',
            note='The480rowGPUupload includes240unrelatedlowerrows; onlyupper320x240occursinEXE andisSony splash'),
        exact_wording=[r['text'] for r in LINES],line_registration=records,
        alpha_contract=dict(white='ActualCLUT0=0x7FFF,R248G248B248,alpha127/STPclear',
            black='ActualCLUT15=0x8000,R0G0B0,alpha255/STPset',
            antialias='Fresh grayRGBsamples carryalpha127, matching original nonblack graypalette classes',semi=-1),
        seam_proof=dict(source_prefix_raw_equality='Right page first16words perrow equals fulluploadwords64..79 for256rows, ownCLUTidentical',
            selected_authored_rgba='Rightupper240x64pixels are exact16x crop of fullupper240x320field'),
        source_draw_receipts=[dict(**ref(RECEIPTS),line=2,frame=69,key=FULL,uv_inclusive=[0,0,254,254],xy=[[0,240],[255,240],[0,495]]),
            dict(**ref(RECEIPTS),line=1,frame=69,key=RIGHT,uv_inclusive=[0,0,254,254],xy=[[256,240],[511,240],[256,495]]),
            dict(**ref(SQUARE_RECEIPTS),line=3,frame=498,key='4E783C96-E2D2473F',role='Historical next startup mark; no new logo acceptance')],
        boot_sequence_gate=dict(required_order=['Sony Computer Entertainment America Presents','SQUARESOFT','FMV/next native state'],
            must_capture_both_before_fmv_skip=True,new_sony_draw_and_capture_pass=False,new_square_draw_and_capture_pass=False,
            allow_fmv_skip=False,scope='Root must capture final candidate coldboot source/draw receipts and fresh composedframes for BOTHlogos before any Start/skip'),
        decode_budget=dict(full_rgba_bytes=5120*7680*4,right_rgba_bytes=4096*4096*4,maximum_edge=7680),
        method='Fresh Arial Bold15native pixel letter outlines with original wording, opticalcenters and nativebaselines118/134. New fulluploadkey removes the previous missingleft/maintexturepath; rightpage is16xgeometriccrop with unrelated parentpixels protected.',
        live_verified=False,remaining=['Finalcoldboot bothlogos sourceadmission/capture beforeFMVskip','Natural fade and reentry verification'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');result=verify(out)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
