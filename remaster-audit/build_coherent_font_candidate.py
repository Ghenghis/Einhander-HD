"""Unify actual fighter/arm text fields and admit verified missing menu strips."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt

from build_three_asset_proof import verify_stock
from build_font_strip_candidates import raw_verified,native_decode

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v4'
OUT=ROOT/'remaster-audit/menu-restoration/font-strip-candidate-v6'
LIVE=ROOT/'remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
BODY_KEYS={
 '5F101F62-B88C038E','921FC559-B88C038E','AAA5C104-B88C038E',
 '2C781811-B88C038E','E1F18F98-B88C038E','786B98BF-B88C038E',
 '5C02D3C1-B88C038E','D050AD1B-B88C038E','913A6603-B88C038E',
}
ARM_ROWS={'3DA22883-678CA3BD':104,'7D2C7E3C-678CA3BD':72,
          'AAE3C8F2-678CA3BD':88,'41E75A55-678CA3BD':80}
RANK_KEYS={'2C6866AA-30A66678','2C6866AA-B1A4FC51','8D0FCF8A-30A66678',
           'C544AC0D-30A66678','C544AC0D-B1A4FC51'}

def sha(data):return hashlib.sha256(data).hexdigest()

def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded

def copy_source(directory,key):
 archives={}
 for tag,suffix in (('words','.words.bin'),('clut','.clut.bin'),('validity','.valid.bin'),('metadata','.source.json')):
  source=directory/(key+suffix);target=OUT/'sources'/(key+suffix);shutil.copy2(source,target)
  archives[tag]={'path':str(target),'sha256':sha(target.read_bytes())}
 return archives

def parent_proof(key,raw,clut,parent,row):
 path=Path(parent['source']);metadata,words,palette=verify_stock(path.parent,parent['key'])
 if words[row*128:(row+8)*128]!=raw:raise ValueError('Raw parent row mismatch: '+key)
 return {'key':parent['key'],'source':str(path),'source_words_path':str(path.with_suffix('.words.bin')),
         'source_words_sha256':sha(words),'source_clut_path':str(path.with_suffix('.clut.bin')),
         'source_clut_sha256':sha(palette),'native_row':row,'raw_words_exact':True,'clut_exact':palette==clut}

def preview(path,key,native,before,after):
 box=(0,0,128,8);w,h=1024,64
 canvas=Image.new('RGB',(w,3*(h+28)),(10,17,23));draw=ImageDraw.Draw(canvas)
 for n,(label,pixels,scale) in enumerate((('Native RGB geometry reference',native,1),('Inherited main RGB; source-tone islands',before,16),('Unified original RGB field; coherent categorical contour',after,16))):
  im=Image.fromarray(pixels[:,:,:3]).crop(tuple(v*scale for v in box)).resize((w,h),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS)
  y=n*(h+28);draw.text((4,y+5),key+' | '+label,fill='white');canvas.paste(im,(0,y+25))
 canvas.save(path)

def glyph_field(indices,palette,regions):
 """One midpoint silhouette defines solid faces and a compact original rim.

 Description glyph books are solid small type. Their neighboring outlined
 weapon logos are deliberately excluded from these authored rectangles.
 """
 result=np.repeat(np.repeat(palette[indices],16,0),16,1)
 selected=np.zeros(result.shape[:2],bool)
 knots=np.array([-.30,-.20,-.12,-.04,.04,.12,.22],np.float32)
 tones=np.array([15,13,10,7,4,2,0],np.float32)
 for x0,y0,x1,y1 in regions:
  crop=indices[y0:y1,x0:x1]
  ink=crop<=8
  padded=np.pad(ink,1,constant_values=False)
  signed=(distance_transform_edt(padded)-distance_transform_edt(~padded)).astype(np.float32)
  field=cv2.resize(signed,((crop.shape[1]+2)*16,(crop.shape[0]+2)*16),interpolation=cv2.INTER_CUBIC)
  field=cv2.GaussianBlur(field,(0,0),16*.18,borderType=cv2.BORDER_REPLICATE)[16:-16,16:-16]
  tonal=np.interp(field,knots,tones,left=15,right=0).astype(np.float32)
  lo=np.floor(tonal).astype(np.uint8);hi=np.minimum(lo+1,15);part=(tonal-lo)[:,:,None]
  rgb=np.rint(palette[lo,:3]*(1-part)+palette[hi,:3]*part).astype(np.uint8)
  result[y0*16:y1*16,x0*16:x1*16,:3]=rgb
  result[y0*16:y1*16,x0*16:x1*16,3]=palette[np.rint(tonal).astype(np.uint8),3]
  selected[y0*16:y1*16,x0*16:x1*16]=True
 return result,selected

def main():
 if OUT.exists():raise ValueError('Existing font candidates are immutable')
 prior=json.loads((PRIOR/'manifest.json').read_bytes())
 if prior['contract']!='verified-font-strip-v4' or prior['source_keys']!=39:raise ValueError('Expected complete reviewed39-key fontv4')
 old={a['key']:a for a in prior['files']}
 if not BODY_KEYS<=set(old):raise ValueError('Missing an actual fighter-description row')
 menu=module(PRIOR/'menu-field-library.py','coherent_body_menu');hud=module(PRIOR/'palette-contour-library.py','coherent_body_hud')
 queue=json.loads(QUEUE.read_bytes())['assets'];by_key={a['key']:a for a in queue if a.get('source_verified')}
 for folder in ('pack','strict-mask-pack','sources'):shutil.copytree(PRIOR/folder,OUT/folder)
 (OUT/'previews').mkdir()
 for name in ('menu-field-library.py','palette-contour-library.py'):shutil.copy2(PRIOR/name,OUT/name)
 shutil.copy2(__file__,OUT/'build-source.py')
 cv2.setNumThreads(2)
 rows=[]
 for row in prior['files']:
  item=json.loads(json.dumps(row))
  for variant,info in item['outputs'].items():
   target=OUT/variant/'einhander-texture-replacements'/(item['key']+'.png')
   if sha(target.read_bytes())!=info['sha256']:raise ValueError('Prior output changed: '+item['key'])
   info['path']=str(target)
  if item['kind']=='standalone_native_font':
   item['source']=str(OUT/'sources'/Path(item['source']).name)
   for archive in item['source_archives'].values():archive['path']=str(OUT/'sources'/Path(archive['path']).name)
  rows.append(item)
 result={a['key']:a for a in rows}
 capture_paths=[LIVE/'native-final-files/capture.jsonl',LIVE/'native-live-gameplay/capture.jsonl']
 capture_data={str(p):p.read_bytes() for p in capture_paths}
 captures={str(p):[json.loads(line) for line in data.splitlines()] for p,data in ((Path(k),v) for k,v in capture_data.items())}
 work=[(k,'body') for k in sorted(BODY_KEYS)]+[(k,'arm') for k in sorted(ARM_ROWS)]+[(k,'rank') for k in sorted(RANK_KEYS)]
 for key,role in work:
  previous=old.get(key)
  if role=='body':
   directory=Path(previous['source']).parent
   parent=by_key[previous['base_key']];native_row=previous['base_output_region'][1]
  else:
   directory=LIVE/('native-live-gameplay' if role=='arm' else 'native-final-files')
   parent=by_key['1AD90FC9-79902A90'] if role=='arm' else None
   native_row=ARM_ROWS.get(key)
  metadata,raw,clut=raw_verified(directory,key)
  indices=hud.decode_indices(raw,metadata);palette=hud.palette_rgba(clut);native=palette[indices]
  if native.tobytes()!=native_decode(raw,clut):raise ValueError('Independent raw decode mismatch: '+key)
  if role=='rank':
   codes=np.array([15,14,13,12,11,10,0],np.uint8);levels=np.array([0,3,6,9,11,13,15],np.uint8)
   if not set(map(int,np.unique(indices)))<={0,10,11,12,13,14,15}:raise ValueError('Unreviewed ranking source ramp')
   lookup=np.zeros(16,np.uint8);lookup[codes]=levels;canonical=lookup[indices];ramp=np.empty((16,4),np.uint8)
   for channel in range(3):ramp[:,channel]=np.rint(np.interp(np.arange(16),levels,palette[codes,channel])).astype(np.uint8)
   nearest_anchor=np.abs(np.arange(16)[:,None]-levels.astype(int)[None,:]).argmin(axis=1);ramp[:,3]=palette[codes[nearest_anchor],3]
   profile='seven_used_source_anchors'
  else:
   canonical=indices;ramp=palette;codes=np.arange(16,dtype=np.uint8);levels=codes.copy();profile='descending_native_ramp'
  if not np.array_equal(ramp[canonical],native):raise ValueError('Tonal field changed native source identities: '+key)
  regions=[(0,0,128,8)] if role=='arm' else [(0,0,64,8),(192,0,256,8)] if role=='body' else [(0,0,256,8)]
  if role in ('body','arm'):
   rebuilt,selected=glyph_field(indices,palette,regions)
   nearest=np.repeat(np.repeat(native,16,0),16,1)
   profile='source_midpoint_glyph_silhouette'
  else:
   contours,selected=menu.menu_contour_indices(canonical,16,regions)
   rebuilt,nearest=menu.menu_render(canonical,contours,ramp,regions,native_alpha=False)
  if previous:
   base_path=Path(previous['outputs']['pack']['path'])
  else:base_path=LIVE/'pack/einhander-texture-replacements'/(key+'.png')
  if not base_path.is_file():
   base_path=OUT/'sources'/(key+'.baseline.png');Image.fromarray(nearest).save(base_path)
   base_kind='decoded_native_nearest'
  else:base_kind='prior_accepted_main' if previous else 'existing_candidate_asset'
  with Image.open(base_path) as image:baseline=np.array(image.convert('RGBA'))
  if baseline.shape!=(128,4096,4):raise ValueError('Unexpected baseline strip dimensions: '+key)
  authored=baseline.copy();authored[selected]=rebuilt[selected]
  if not np.array_equal(authored[~selected],baseline[~selected]):raise ValueError('Protected strip pixels changed')
  if not set(map(int,np.unique(authored[:,:,3])))<={0,127,255}:raise ValueError('Noncategorical alpha')
  source_archives=copy_source(directory,key);source=OUT/'sources'/(key+'.png');Image.fromarray(native).save(source)
  if previous:item=result[key]
  else:
   item={'key':key,'outputs':{}};rows.append(item);result[key]=item
  for variant in ('pack','strict-mask-pack'):
   if previous and variant=='strict-mask-pack':continue
   pixels=authored.copy()
   if variant=='strict-mask-pack':
    pixels[:,:,3]=nearest[:,:,3]
    if not np.array_equal(pixels[~selected],baseline[~selected]):raise ValueError('Strict protected region changed')
   output=OUT/variant/'einhander-texture-replacements'/(key+'.png');Image.fromarray(pixels).save(output)
   with Image.open(output) as check:
    if check.convert('RGBA').tobytes()!=pixels.tobytes():raise ValueError('PNG roundtrip changed')
   item['outputs'][variant]={'path':str(output),'sha256':sha(output.read_bytes()),'size':[4096,128],
                              'rgba_sha256':sha(pixels.tobytes()),'exact_parent_rgba_crop':False,
                              'native_alpha_footprint_exact':variant=='strict-mask-pack'}
  native_receipts=[]
  for path,records in captures.items():
   matches=[{'line':n,**{k:r.get(k) for k in ('event','key','frame','source_kind','native_words','source_word_xy','uv_bounds','xy','not_visibility_proof','cpu_vram_may_be_stale')}}
            for n,r in enumerate(records,1) if r.get('key')==key and r.get('event') in ('source_draw_query_matched','replacement_gl_draw_submitted')][:8]
   if matches:native_receipts.append({'capture_path':path,'capture_sha256':sha(capture_data[path]),'draws':matches})
  item.update(kind='standalone_native_font' if role=='rank' else 'reconstructed_font_row',
              role={'body':'Actual fighter/arm description glyph row','arm':'Actual arm/weapon specification row','rank':'Actual ranking font palette variant'}[role],
              source=str(source),source_sha256=sha(source.read_bytes()),source_size=[256,8],source_archives=source_archives,
              source_words_sha256=sha(raw),source_clut_sha256=sha(clut),source_metadata=metadata,
              source_crc_verified=True,source_decode_verified=True,source_validity_complete=True,native_rgba_sha256=sha(native.tobytes()),
              canonical_profile=profile,canonical_source_codes=codes.tolist(),canonical_levels=levels.tolist(),canonical_native_rgba_exact=True,
              glyph_silhouette_cutoff=8 if role in ('body','arm') else None,
              glyph_field_control_points=[[-.30,15],[-.20,13],[-.12,10],[-.04,7],[.04,4],[.12,2],[.22,0]] if role in ('body','arm') else None,
              selected_native_regions=[list(r) for r in regions],main_contour_alpha_refined=True,
              alpha_policy='categorical_contour_inside_authored_regions',native_alpha_footprint_exact=False,
              strict_native_alpha_footprint_exact=True,source_local_uv_coordinates_preserved=True,
              base_path=str(base_path),base_sha256=sha(base_path.read_bytes()),base_kind=base_kind,
              protected_outside_exact_to_base=True,exact_parent_rgba_crop=False,
              native_ui_receipts=native_receipts,
              in_game_acceptance='Unified source RGB field and categorical contours authored; actual candidate composed visual review pending')
  if parent:item['raw_parent']=parent_proof(key,raw,clut,parent,native_row)
  if previous:item['supersedes_parent_output_crop']=True
  if key=='2C781811-B88C038E':preview(OUT/'previews'/'fighter-description-rgb-before-after.png',key,native,baseline,authored)
  if key=='3DA22883-678CA3BD':preview(OUT/'previews'/'arm-specification-before-after.png',key,native,baseline,authored)
  print(json.dumps({'key':key,'role':role,'checks':'PASS'}),flush=True)
 for path,data in capture_data.items():
  if Path(path).read_bytes()!=data:raise ValueError('Source capture still changing; output not finalized: '+path)
 expected=set(prior['expected_keys'])|set(ARM_ROWS)|RANK_KEYS
 if {r['key'] for r in rows}!=expected or len(rows)!=48:raise ValueError('Incomplete48-key candidate')
 manifest=dict(prior)
 manifest.update(format=6,contract='verified-font-strip-v6',created_at_utc=datetime.now(timezone.utc).isoformat(),
                 source_keys=48,expected_keys=sorted(expected),files=sorted(rows,key=lambda r:r['key']),
                 exact_font_row_alias_count=5,reconstructed_font_row_count=13,standalone_native_font_count=30,
                 reconstructed_existing_description_keys=sorted(BODY_KEYS),new_arm_keys=sorted(ARM_ROWS),new_ranking_keys=sorted(RANK_KEYS),
                 prior_main_outputs_preserved=30,prior_strict_outputs_preserved=39,
                 source_queue=str(QUEUE),source_queue_sha256=sha(QUEUE.read_bytes()),
                 native_capture_refs=[{'path':path,'sha256':sha(data)} for path,data in capture_data.items()],
                 method='Nine actual description glyph books and four new actual ARM specification rows recover a shared midpoint source silhouette with solid original-palette faces and compact tonal rims; categorical alpha follows the same smooth contour. Description center logos/icons and ARM diagram halves are protected exactly. Five new ranking variants use reviewed source-anchor fields. All thirty other existing mains and all thirty-nine existing strict PNGs remain byte-identical to v4.',
                 limits=['A raw-row parent proves original index identity, not an authored RGBA crop; reconstructed rows explicitly supersede the old output-crop claim.',
                         'Main categorical alpha refines original outlines within verified UVs; strict comparisons retain original alpha.',
                         'Other controller diagrams/right-side pixels of the new ARM rows are protected exactly to the current candidate.',
                         'Actual candidate gameplay/menu visual acceptance remains separate.'])
 manifest['parent_manifest_refs']['font_v4']={'path':str(PRIOR/'manifest.json'),'sha256':sha((PRIOR/'manifest.json').read_bytes())}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'pack':str(OUT/'pack'),'source_keys':48,'new_keys':9,'corrected_existing_description_mains':9}))

if __name__=='__main__':main()
