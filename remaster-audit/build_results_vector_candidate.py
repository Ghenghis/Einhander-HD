"""Fresh Results typography in source-proven UVs; never modifies a prior pack.

Supplement description-vector-v4 with eight Results glyphs, a clearer narrow2,
and the baked Total/Evaluation words and 0-9 row of the exact024 Results CLUT.
Source metrics register vectors; source pixel shadows never become contours.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import map_vector_description_glyphs as body
from build_three_asset_proof import verify_stock

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'menu-restoration/description-vector-candidate-v4'
V9=AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9'
DEFAULT_OUT=AUDIT/'menu-restoration/results-vector-candidate-v2'
RESULTS_KEY='8E1A509D-02491337'
BAKED_FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
GROUPS=[('Score',44,80,120),('Boss Bonus',44,210,280),
        ('Shot Down',108,14,80),('Highest %',108,244,310),
        ('S Bonus',174,74,120),('Tech Pts.',174,210,265),
        ('Field Graph',207,184,250),('Exit',207,280,310)]
BAKED=[('Total',[0,156,34,165]),('Evaluation',[0,166,68,179])]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def load(path):return json.loads(Path(path).read_bytes())
def pixels(path):return np.array(Image.open(path).convert('RGBA'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def require(value,message):
 if not value:raise ValueError(message)

def source_map():
 proof_path=V9/'v9-results-font-context-gp0.json';proof=load(proof_path)
 shot=proof['capture'];require(sha(shot['path'])==shot['sha256'],'Results capture changed')
 vram_path=Path(proof['vram']['path']);vram=vram_path.read_bytes()
 require(len(vram)==1048576,'Invalid complete VRAM size')
 raw=b''.join(vram[((256+y)*1024+960)*2:((256+y)*1024+1024)*2] for y in range(256))
 clut=vram[(482*1024+272)*2:(482*1024+288)*2]
 require(f'{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}'==body.KEY,'Results body source/palette mismatch')
 native=Image.open(
  'C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/'+body.KEY+'.png')
 native=native.convert('RGBA');draws=body.parse_frame(proof['dump']);mapping=[];by_uv=defaultdict(set);lines=[]
 for text,y,x0,x1 in GROUPS:
  selected=sorted([d for d in draws if d['page_xy_words']==[960,256] and d['depth']==0 and
    d['clut_xy_words']==[272,482] and d['display_local_xy'][1]==y and x0<=d['display_local_xy'][0]<x1],
    key=lambda d:d['display_local_xy'][0])
  selected=[d for d in selected if native.crop(tuple(d['source_uv_half_open'])).getchannel('A').getbbox()]
  letters=text.replace(' ','');require(len(letters)==len(selected),'Results glyph count mismatch: '+text)
  items=[]
  for character,draw in zip(letters,selected):
   uv=tuple(draw['source_uv_half_open']);by_uv[uv].add(character)
   item={'character':character,'confirmed_text':text,**draw};mapping.append(item);items.append(item)
  lines.append({'text':text,'assignments':items})
 require(all(len(chars)==1 for chars in by_uv.values()),'Conflicting Results glyph mapping')
 old={tuple(g['uv'][:2]):g for g in load(PARENT/'source-map.json')['glyphs']}
 additions=[]
 for uv,characters in sorted(by_uv.items()):
  character=next(iter(characters));existing=old.get(uv[:2])
  if existing:require(existing['character']==character,'Results/body identity conflict')
  else:additions.append({'character':character,'uv':list(uv)})
 require({g['character'] for g in additions}==set('BDH%TPFG'),'Unexpected supplementary Results corpus')
 # Exact packet ownership of the baked title words, at their current CLUT.
 baked=[]
 for text,uv in BAKED:
  matches=[d for d in draws if d['page_xy_words']==[512,0] and d['depth']==0 and
    d['clut_xy_words']==[16,480] and d['source_uv_half_open']==uv]
  require(len(matches)==1,'Missing exact Results word draw: '+text)
  baked.append({'text':text,'uv':uv,'draw':matches[0]})
 result_raw=b''.join(vram[(y*1024+512)*2:(y*1024+576)*2] for y in range(256))
 result_clut=vram[(480*1024+16)*2:(480*1024+32)*2]
 require(f'{zlib.crc32(result_raw):08X}-{zlib.crc32(result_clut):08X}'==RESULTS_KEY,'Results baked source/palette mismatch')
 return {'proof':ref(proof_path),'capture':shot,'vram':ref(vram_path),'body_key':body.KEY,
   'source_words_sha256':hashlib.sha256(raw).hexdigest(),'source_clut_sha256':hashlib.sha256(clut).hexdigest(),
   'lines':lines,'glyph_additions':additions,'baked_words':baked,
   'expanded_t_quad':{'character':'t','uv':[32,48,37,56],'v4_vector_uv':[32,48,36,56],
      'method':'Keep v4vector in first4columns and clear the fifth oldshadow column exposed by Results packets'},
   'baked_source_words_sha256':hashlib.sha256(result_raw).hexdigest(),
   'baked_source_clut_sha256':hashlib.sha256(result_clut).hexdigest(),
   'mapping_scope':'Source ownership from the actual composed Results frame and GP0/VRAM; no claim about the gameplay route used to reach it'},native

def class_rgba(mask,face=(248,248,248),face_class=127,edge_class=255):
 coverage=np.asarray(mask).astype(np.float32)/255
 rgba=np.zeros((mask.height,mask.width,4),np.uint8)
 rgba[:,:,:3]=np.rint(coverage[:,:,None]*np.asarray(face)[None,None,:]).astype(np.uint8)
 rgba[:,:,3]=np.where(coverage==0,0,np.where(coverage>=.86,face_class,edge_class)).astype(np.uint8)
 return rgba

def numeral2(native):
 rect=[208,96,214,104];scale=16
 glyph=Image.new('L',(256,256));d=ImageDraw.Draw(glyph)
 font=ImageFont.truetype(str(BAKED_FONT),148);d.text((24,160),'2',font=font,fill=255,anchor='ls')
 bounds=glyph.getbbox();ink=glyph.crop(bounds).resize((60,bounds[3]-bounds[1]),Image.Resampling.LANCZOS)
 mask=Image.new('L',(96,128));left=32;top=body.BASELINE+bounds[1]-160
 require(top>=0 and top+ink.height<=mask.height,'Narrow2 clipped')
 mask.paste(ink,(left,top))
 return class_rgba(mask),{'character':'2','uv':rect,'font':ref(BAKED_FONT),'font_size':148,
  'baseline_native':body.BASELINE/16,'left_native':2,'ink_width_native':3.75,
  'reason':'A continuous diagonal and wider horizontal foot improve recognition in the narrow original numeric quad'}

def baked_word(text,uv,native):
 """A whole exact source word uses one fresh, consistently weighted vector."""
 crop=native.crop(tuple(uv));a=np.asarray(crop);ink=(a[:,:,3]>0)&(a[:,:,:3].max(2)>0)
 yy,xx=np.where(ink);require(len(xx)>0,'Empty baked registration')
 box=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
 width,height=crop.width*16,crop.height*16
 # Native edge coverage defines optical bounds only; no sampled tone enters strokes.
 target_w=max(1,round((box[2]-box[0]-.35)*16));target_h=max(1,round((box[3]-box[1]-.3)*16))
 font=ImageFont.truetype(str(BAKED_FONT),196)
 tmp=Image.new('L',(4096,512));draw=ImageDraw.Draw(tmp);draw.text((20,20),text,font=font,fill=255)
 glyph=tmp.crop(tmp.getbbox()).resize((target_w,target_h),Image.Resampling.LANCZOS)
 mask=Image.new('L',(width,height));mask.paste(glyph,(box[0]*16,box[1]*16))
 return class_rgba(mask),{'text':text,'uv':uv,'native_optical_registration':box,
   'fresh_outline_font':ref(BAKED_FONT),'entire_word_quad_verified':True,
   'internal_character_positions':'Fresh word layout fitted to the exact optical word bounds; not inferred individual guest addresses'}

def numeric_cell(digit,native):
 uv=[digit*8,180,(digit+1)*8,188];crop=native.crop(tuple(uv));a=np.asarray(crop)
 yy,xx=np.where((a[:,:,3]>0)&(a[:,:,:3].max(2)>0));require(len(xx)>0,'Empty numeric cell')
 box=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
 font=ImageFont.truetype(str(BAKED_FONT),148);tmp=Image.new('L',(256,256));d=ImageDraw.Draw(tmp)
 d.text((24,160),str(digit),font=font,fill=255,anchor='ls');bounds=tmp.getbbox();glyph=tmp.crop(bounds)
 # Shared numeric cap height/baseline and width keep the ten digits stable in motion.
 glyph=glyph.resize((max(16,round((box[2]-box[0]-.5)*16)),104),Image.Resampling.LANCZOS)
 mask=Image.new('L',(128,128));left=round((box[0]+.25)*16);mask.paste(glyph,(left,8))
 return class_rgba(mask),{'digit':str(digit),'uv':uv,'native_optical_registration':box,
   'mapping':'Native source artwork visibly contains the ordered0-9 row at these eight-pixel cells;0/1/4 also have actual Results sprite packets',
   'authored_numeric_cap_height_native':6.5,'authored_numeric_baseline_native':7}

def build(output):
 require(not output.exists(),'Choose a new immutable output directory')
 mapping,native=source_map();parent=load(PARENT/'manifest.json')
 parent_rows={r['key']:r for r in parent['files'] if r['source_key']==body.KEY}
 require(len(parent_rows)==11,'Expected canonical font page and10source-exact aliases')
 p=parent_rows[body.KEY];canonical=pixels(p['outputs']['pack']['path']);original=canonical.copy()
 selection=np.zeros(canonical.shape[:2],bool);font=ImageFont.truetype(str(body.FONT),body.FONT_SIZE);glyphs=[]
 for g in mapping['glyph_additions']:
  x0,y0,x1,y1=g['uv'];rgba,metrics=body.vector_glyph(g['character'],g['uv'],native,font)
  canonical[y0*16:y1*16,x0*16:x1*16]=rgba;selection[y0*16:y1*16,x0*16:x1*16]=True
  glyphs.append({**g,'metrics':metrics})
 # The exact Results tquad is onecolumn wider than the body-only corpus.
 # Leaving that unrebuilt column exposed leaks the native shadow as a blot.
 t=mapping['expanded_t_quad'];x0,y0,x1,y1=t['uv'];tx0,ty0,tx1,ty1=t['v4_vector_uv']
 t_rgba,_=body.vector_glyph('t',t['v4_vector_uv'],native,font)
 canonical[y0*16:y1*16,x0*16:x1*16]=0
 canonical[ty0*16:ty1*16,tx0*16:tx1*16]=t_rgba
 selection[y0*16:y1*16,x0*16:x1*16]=True
 rgba,two=numeral2(native);x0,y0,x1,y1=two['uv']
 canonical[y0*16:y1*16,x0*16:x1*16]=rgba;selection[y0*16:y1*16,x0*16:x1*16]=True
 output.mkdir(parents=True);pack=output/'pack/einhander-texture-replacements';pack.mkdir(parents=True)
 (pack.parent/'Hashes.ini').write_text('');rows=[]
 def save(key,a,parent_path,mask,method,source_region=None):
  before=pixels(parent_path);require(np.array_equal(a[~mask],before[~mask]),'Protected pixels changed: '+key)
  path=pack/(key+'.png');Image.fromarray(a).save(path);require(np.array_equal(pixels(path),a),'PNG round-trip failed')
  rows.append({'key':key,'outputs':{'pack':{**ref(path),'size':[a.shape[1],a.shape[0]]}},
    'parent':ref(parent_path),'method':method,'source_region':source_region,
    'protected_outside_exact':True,'alpha_classes':list(map(int,np.unique(a[:,:,3]))),'live_accepted':False})
 for key,row in parent_rows.items():
  path=row['outputs']['pack']['path'];before=pixels(path);require(sha(path)==row['outputs']['pack']['sha256'],'Parent changed')
  if key==body.KEY:a=canonical;mask=selection;region=[0,0,256,256]
  else:
   _,start,_,end=row['source_region'];mask=selection[start*16:end*16]
   a=before.copy();a[mask]=canonical[start*16:end*16][mask];region=row['source_region']
  save(key,a,path,mask,'Eight source-proven Results glyphs and clearer narrow2; v4body/ARM vectors preserved',region)
 # The exact actual Results CLUT only; do not invent fade/palette aliases.
 source_dir=AUDIT/'menu-restoration/results-palette-024-candidate-v1/source-proof'
 _,words,clut=verify_stock(source_dir,RESULTS_KEY);baked_native=Image.open(source_dir/(RESULTS_KEY+'.png')).convert('RGBA')
 v9=load(V9/'candidate.json');v9row=next(r for r in v9['files'] if r['name']==RESULTS_KEY+'.png')
 results_parent=Path(v9row['composed_path']);require(sha(results_parent)==v9row['sha256'],'Results parent changed')
 baked=pixels(results_parent);bmask=np.zeros(baked.shape[:2],bool);baked_records=[]
 for word in mapping['baked_words']:
  rgba,record=baked_word(word['text'],word['uv'],baked_native);x0,y0,x1,y1=word['uv']
  baked[y0*16:y1*16,x0*16:x1*16]=rgba;bmask[y0*16:y1*16,x0*16:x1*16]=True;baked_records.append(record)
 for digit in range(10):
  rgba,record=numeric_cell(digit,baked_native);x0,y0,x1,y1=record['uv']
  baked[y0*16:y1*16,x0*16:x1*16]=rgba;bmask[y0*16:y1*16,x0*16:x1*16]=True;baked_records.append(record)
 save(RESULTS_KEY,baked,results_parent,bmask,'Fresh vector Total/Evaluation and numerical row within exact024Results palette')
 write(output/'source-map.json',mapping);np.savez_compressed(output/'changed-masks.npz',body=selection,results=bmask)
 preview(output,mapping,canonical,original,baked,pixels(results_parent))
 shutil.copyfile(__file__,output/'build-source.py')
 manifest={'format':1,'contract':'results-vector-supplement-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
   'parent_body':ref(PARENT/'manifest.json'),'parent_composition':ref(V9/'candidate.json'),
   'source_map':ref(output/'source-map.json'),'font':ref(body.FONT),'baked_font':ref(BAKED_FONT),
   'builder':ref(Path(__file__)),'vector_library':ref(Path(body.__file__)),'files':rows,'asset_count':len(rows),
   'glyph_additions':glyphs,'numeral2':two,'baked_records':baked_records,
   'alpha_policy':'0transparent/127nonSTP/255STP are categorical; fresh vector face127 and antialiased rim255 retain exact024source conventions',
   'production_installed':False,'game_actions':0,'live_acceptance':'NOT RUN',
   'limits':['Only actually proven Results English glyphs are supplemented; other unseen language/symbol states remain unchanged.',
     'Only exact024baked palette is rebuilt; other8Epalette variants remain unchanged.',
     'Ranking/file grid uppercase/lowercase/digits are a different source and remain outside this bounded candidate.',
     'Fresh typeface is a deliberate legibility replacement, not an identified exact original font.']}
 write(output/'manifest.json',manifest);verify(output)

def preview(output,mapping,canonical,old,baked,baked_old):
 bg=(12,23,39);canvas=Image.new('RGB',(1280,1190),bg);d=ImageDraw.Draw(canvas)
 y=12
 def paste(a,x,y,factor=4):
  rgb=Image.fromarray(a[:,:,:3]).resize((a.shape[1]*factor//16,a.shape[0]*factor//16),Image.Resampling.LANCZOS)
  alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
  canvas.paste(rgb,(x,y),alpha)
 for label,book in [('Parent v4body, unsupplemented Results capitals',old),('Supplement: fresh continuous Results English contours',canonical)]:
  d.text((16,y),label,fill='white');y+=32
  for line in mapping['lines']:
   start=min(a['display_local_xy'][0] for a in line['assignments'])
   for a in line['assignments']:
    x0,y0,x1,y1=a['source_uv_half_open'];paste(book[y0*16:y1*16,x0*16:x1*16],16+(a['display_local_xy'][0]-start)*4,y)
   y+=49
  y+=12
 for label,page in [('Baked Results: parent','old'),('Baked Results: fresh vectors','new')]:
  d.text((620,35 if page=='old' else 230),label,fill='white');py=60 if page=='old' else 255
  source=baked_old if page=='old' else baked
  for text,uv in BAKED:
   x0,y0,x1,y1=uv;paste(source[y0*16:y1*16,x0*16:x1*16],620,py);py+=64
  paste(source[180*16:188*16,0:80*16],620,py)
 canvas.crop((0,0,1280,y)).save(output/'results-before-after-actual4x.png')

def verify(output):
 manifest=load(output/'manifest.json');require(manifest['contract']=='results-vector-supplement-v1','Unexpected contract')
 for field in ('parent_body','parent_composition','source_map','font','baked_font','builder','vector_library'):
  require(sha(manifest[field]['path'])==manifest[field]['sha256'],'Referenced input changed: '+field)
 source,native=source_map();require(json.dumps(source,sort_keys=True)==json.dumps(load(output/'source-map.json'),sort_keys=True),'Source mapping no longer reproducible')
 with np.load(output/'changed-masks.npz') as masks:bodymask=masks['body'];resultsmask=masks['results']
 rows={r['key']:r for r in manifest['files']};canonical=pixels(rows[body.KEY]['outputs']['pack']['path'])
 font=ImageFont.truetype(str(body.FONT),body.FONT_SIZE)
 for g in source['glyph_additions']:
  x0,y0,x1,y1=g['uv'];expected,_=body.vector_glyph(g['character'],g['uv'],native,font)
  require(np.array_equal(canonical[y0*16:y1*16,x0*16:x1*16],expected),'Vector glyph changed: '+g['character'])
 expected,_=numeral2(native);require(np.array_equal(canonical[96*16:104*16,208*16:214*16],expected),'Numeral2 changed')
 t=source['expanded_t_quad'];expected=np.zeros((128,80,4),np.uint8)
 t_rgba,_=body.vector_glyph('t',t['v4_vector_uv'],native,font);expected[:,:64]=t_rgba
 require(np.array_equal(canonical[48*16:56*16,32*16:37*16],expected),'Expanded tquad differs')
 baked_row=rows[RESULTS_KEY];baked_page=pixels(baked_row['outputs']['pack']['path'])
 baked_native=Image.open(AUDIT/'menu-restoration/results-palette-024-candidate-v1/source-proof'/f'{RESULTS_KEY}.png').convert('RGBA')
 for word in source['baked_words']:
  expected,_=baked_word(word['text'],word['uv'],baked_native);x0,y0,x1,y1=word['uv']
  require(np.array_equal(baked_page[y0*16:y1*16,x0*16:x1*16],expected),'Baked word vector differs')
 for digit in range(10):
  expected,r=numeric_cell(digit,baked_native);x0,y0,x1,y1=r['uv']
  require(np.array_equal(baked_page[y0*16:y1*16,x0*16:x1*16],expected),'Numeric row vector differs')
 checked=0
 for row in manifest['files']:
  out=row['outputs']['pack'];require(sha(out['path'])==out['sha256'],'Output hash changed');require(sha(row['parent']['path'])==row['parent']['sha256'],'Parent changed')
  current=pixels(out['path']);parent=pixels(row['parent']['path']);require(current.shape==parent.shape,'Geometry changed')
  if row['key']==RESULTS_KEY:mask=resultsmask
  elif row['key']==body.KEY:mask=bodymask
  else:
   _,y0,_,y1=row['source_region'];mask=bodymask[y0*16:y1*16]
   require(np.array_equal(current[mask],canonical[y0*16:y1*16][mask]),'Alias glyph field differs')
  require(np.array_equal(current[~mask],parent[~mask]),'Protected pixels changed')
  require(set(map(int,np.unique(current[:,:,3])))<={0,127,255},'Noncategorical alpha')
  checked+=1
 # Meaningful corruption control: changing protected evidence cannot pass.
 row=rows[body.KEY];candidate=canonical.copy();y,x=map(int,np.argwhere(~bodymask)[0]);candidate[y,x,0]^=1
 require(not np.array_equal(candidate[~bodymask],pixels(row['parent']['path'])[~bodymask]),'Protected corruption control failed')
 receipt={'outcome':'PASS','output_pngs_verified':checked,'results_glyph_additions':len(source['glyph_additions']),
  'exact_baked_words':2,'numeric_cells':10,'protected_parent_rgba_exact':True,'alias_continuity_exact':True,
  'source_map_reproduced_exact':True,'supplementary_body_vector_recipe_exact':True,
  'negative_controls':['Protected canonical pixel corruption rejected'],'live_acceptance':'NOT RUN'}
 write(output/'verification.json',receipt);print(json.dumps({'output':str(output),'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUT);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
 if args.verify:verify(args.output.resolve())
 else:build(args.output.resolve())
