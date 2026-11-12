"""Restore the verified B77 large menu font without altering bars or grid art."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import zlib

import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v4'
VRAM=EVIDENCE/'banner-source-vram.bin'
OUT=ROOT/'remaster-audit/menu-restoration/banner-font-candidate-v2'
MENU=ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v3/menu-field-library.py'
LIBRARY=ROOT/'windows-x64/tools/build_hud_ui_candidate.py'
REGION=(0,32,256,80)
PALETTES={'C04998CA':224,'C04F65C0':176,'B1A4FC51':288,'8EAF967E':192,'30A66678':208,'166E4BE3':256,'CB9F39AB':240}


def sha(data):return hashlib.sha256(data).hexdigest()


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    if OUT.exists():raise ValueError('Choose a new immutable isolated banner output')
    cv2.setNumThreads(2)
    raw_vram=VRAM.read_bytes();vram=np.frombuffer(raw_vram,dtype='<u2').reshape(512,1024)
    raw=vram[:256,640:704].copy().astype('<u2').tobytes()
    if f'{zlib.crc32(raw):08X}'!='B77B98B9':raise ValueError('Snapshot does not contain the verified B77 font page')
    hud=module(LIBRARY,'banner_hud');menu=module(MENU,'banner_menu')
    indices=hud.decode_indices(raw,{'depth':0,'width_words':64,'height':256})
    x0,y0,x1,y1=REGION;crop=indices[y0:y1,x0:x1]
    if not set(np.unique(crop))<={0,10,11,12,13,14,15}:raise ValueError('Unreviewed banner-font source codes')
    codes=np.array([15,14,13,12,11,10,0],dtype=np.uint8);levels=np.array([0,3,6,9,11,13,15],dtype=np.uint8)
    lookup=np.zeros(16,dtype=np.uint8);lookup[codes]=levels;canonical=lookup[crop]
    contours,selected=menu.menu_contour_indices(canonical,16,[(0,0,256,48)])
    for folder in ('pack/einhander-texture-replacements','strict-mask-pack/einhander-texture-replacements','sources','previews'):(OUT/folder).mkdir(parents=True,exist_ok=True)
    (OUT/'pack/Hashes.ini').write_text('',encoding='utf-8')
    (OUT/'strict-mask-pack/Hashes.ini').write_text('',encoding='utf-8')
    shutil.copy2(__file__,OUT/'build-source.py');shutil.copy2(MENU,OUT/'menu-field-library.py');shutil.copy2(LIBRARY,OUT/'palette-contour-library.py')
    archive=[]
    captures=[EVIDENCE/sub/'capture.jsonl' for sub in ('native-file-option','native-extra-menus','native-left-menu','native-config-e2e')]
    captures.append(EVIDENCE.parent/'hud-4k-candidate-20261112-v5/native-final-files/capture.jsonl')
    for path in captures:
        if path.exists():
            archive.extend((str(path),i,json.loads(line)) for i,line in enumerate(path.read_text().splitlines(),1) if line.strip())
    rows=[]
    for suffix,cx in PALETTES.items():
        clut=vram[487,cx:cx+16].copy().astype('<u2').tobytes();key='B77B98B9-'+suffix
        if f'{zlib.crc32(clut):08X}'!=suffix:raise ValueError('Current CLUT does not match recorded identity: '+key)
        palette=hud.palette_rgba(clut);decoded=palette[indices]
        ramp=np.empty((16,4),dtype=np.uint8)
        for channel in range(3):ramp[:,channel]=np.rint(np.interp(np.arange(16),levels,palette[codes,channel])).astype(np.uint8)
        nearest_anchor=np.abs(np.arange(16)[:,None]-levels.astype(int)[None,:]).argmin(axis=1);ramp[:,3]=palette[codes[nearest_anchor],3]
        if not np.array_equal(ramp[canonical],palette[crop]):raise ValueError('Reversible ramp changed native banner colors/classes')
        patch,_=menu.menu_render(canonical,contours,ramp,[(0,0,256,48)],native_alpha=False)
        nearest=np.repeat(np.repeat(decoded,16,axis=0),16,axis=1);authored=nearest.copy();authored[y0*16:y1*16,x0*16:x1*16]=patch
        outside=(np.array_equal(authored[:y0*16],nearest[:y0*16]) and np.array_equal(authored[y1*16:],nearest[y1*16:]))
        alpha_exact=np.array_equal(authored[:,:,3],nearest[:,:,3])
        if not outside or not set(np.unique(authored[:,:,3]))<={0,127,255}:raise ValueError('Categorical coverage or protected outside regions changed')
        strict=authored.copy();strict[:,:,3]=nearest[:,:,3]
        out=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(authored).save(out)
        with Image.open(out) as reopened:
            if reopened.tobytes()!=authored.tobytes():raise ValueError('PNG roundtrip mismatch')
        strict_path=OUT/'strict-mask-pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(strict).save(strict_path)
        with Image.open(strict_path) as reopened:
            if reopened.tobytes()!=strict.tobytes():raise ValueError('Strict PNG roundtrip mismatch')
        (OUT/'sources'/(key+'.words.bin')).write_bytes(raw);(OUT/'sources'/(key+'.clut.bin')).write_bytes(clut);(OUT/'sources'/(key+'.valid.bin')).write_bytes(bytes([1])*16384)
        metadata={'key':key,'frame':67050,'upload_serial':0,'width_words':64,'height':256,'depth':0,'clut_xy':[cx,487],'clut_words':16,'known_words':16384,'total_words':16384,'reconstructed_crc32':'B77B98B9','raw_origin':'Root-captured display-ring GPU VRAM snapshot at final state-gated Configuration frame67050','fragments':[[640,0,64,256,0,0]],'snapshot_sha256':sha(raw_vram)}
        (OUT/'sources'/(key+'.source.json')).write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8');Image.fromarray(decoded).save(OUT/'sources'/(key+'.png'))
        receipts=[{'capture':path,'line':i,'event':e['event'],'frame':e['frame'],'uv_bounds':e.get('uv_bounds'),'xy':e.get('xy'),'semi':e.get('semi')} for path,i,e in archive if e.get('key')==key and 32<=e.get('uv_bounds',[0,0,0,0])[1]<64][:32]
        rows.append({'key':key,'role':'Large16pixel uppercase/digit font used by headers, NO DATA, ranking scores and ordinal digits','source_words_sha256':sha(raw),'source_clut_sha256':sha(clut),'source_metadata':metadata,'selected_native_regions':[list(REGION)],'outputs':{'pack':{'path':str(out),'sha256':sha(out.read_bytes()),'size':[4096,4096]},'strict-mask-pack':{'path':str(strict_path),'sha256':sha(strict_path.read_bytes()),'size':[4096,4096]}},'checks':{'raw_source_crc_exact':True,'clut_crc_exact':True,'canonical_native_rgba_exact':True,'outside_header_band_nearest_source_exact':outside,'entire_original_alpha_footprint_exact':alpha_exact,'main_categorical_contour_alpha':True,'strict_original_alpha_footprint_exact':True,'png_roundtrip_exact':True},'draw_evidence':receipts,'changed_rgb_pixels':int(np.any(authored[:,:,:3]!=nearest[:,:,:3],axis=2).sum()),'changed_alpha_pixels':int(np.count_nonzero(authored[:,:,3]!=nearest[:,:,3])),'in_game_acceptance':'pending final actual headers/NO DATA/ranking digit review'})
        if suffix=='30A66678':
            old=Image.fromarray(palette[crop][:,:,:3]).resize((1024,192),Image.Resampling.NEAREST)
            new=Image.fromarray(patch[:,:,:3]).resize((1024,192),Image.Resampling.LANCZOS)
            preview=Image.new('RGB',(1024,428),(10,14,25));d=ImageDraw.Draw(preview);d.text((6,4),'VERIFIED B77 LARGE GLYPHS AND RANKING DIGITS / NATIVE x4',fill='white');preview.paste(old,(0,22));d.text((6,218),'RESTORED CONTINUOUS CONTOURS / CATEGORICAL SUBPIXEL COVERAGE',fill='white');preview.paste(new,(0,240));preview.save(OUT/'previews/banner-font-native4x.png')
        if suffix=='C04F65C0':
            alpha=patch[:,:,3]!=0;visible=patch[:,:,:3].copy();visible[~alpha]=0
            old_alpha=nearest[y0*16:y1*16,:,3]!=0;old_visible=patch[:,:,:3].copy();old_visible[~old_alpha]=0
            comp=Image.new('RGB',(1024,428),(10,14,25));d=ImageDraw.Draw(comp);d.text((6,4),'V1 NATIVE ALPHA STAIR STEPS / GREEN FONT AT x4',fill='white');comp.paste(Image.fromarray(old_visible).resize((1024,192),Image.Resampling.LANCZOS),(0,22));d.text((6,218),'V2 RECONSTRUCTED CATEGORICAL CONTOUR ALPHA / GREEN FONT AT x4',fill='white');comp.paste(Image.fromarray(visible).resize((1024,192),Image.Resampling.LANCZOS),(0,240));comp.save(OUT/'previews/green-no-data-ranking-alpha-comparison.png')
        print(json.dumps({'key':key,'checks':'PASS'}),flush=True)
    manifest={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':len(rows),'production_installed':False,'game_actions':0,'source_vram':str(VRAM),'source_vram_sha256':sha(raw_vram),'source_frame':67050,'tool_sha256':sha(Path(__file__).read_bytes()),'revision':'v2 adds verified ranking digit row64..79 and releases native outer-alpha staircase while retaining categorical source classes. strict-mask-pack retains native alpha for comparison.','method':'Original B77 glyph codes0/10..15 map reversibly to a shared continuous tonal field. NativeUV rows32..79 receive smooth RGB and categorical subpixel contour coverage; no fonts/OCR/new wording. All outside native-source texels remain unchanged.','why_previous_headers_were_old':'B77 was outside menu-v7; v1 restored RGB only in rows32..63 and retained original alpha. Ranking digits row64..79 stayed nearest-native; green NO DATA retained a native alpha staircase.','region_native_half_open':list(REGION),'assets':rows,'limits':['Existing query receipts establish source/UV ownership but do not accept the newly authored output.','Main alpha geometry intentionally refines native coverage within the bounded band; original alpha footprint equality is not claimed for main output.','The snapshot was captured at Configuration frame67050; the stale earlier frame66908 metadata was not used.','Gradient bars/grid are separate game geometry. This overlay leaves every outside-band texture pixel unchanged.']}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pack':str(OUT/'pack'),'assets':len(rows),'manifest':str(OUT/'manifest.json'),'checks':'PASS'}))


if __name__=='__main__':main()
