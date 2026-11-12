"""Rebuild actual1ADfighter name quads, independent of unused323name artwork."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import shutil
import zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import map_vector_description_glyphs as gp0
from build_three_asset_proof import verify_stock
from build_results_vector_candidate import sha, ref, load, pixels, write, require

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
KEY='1AD90FC9-4315989E'
SOURCE=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
DEFAULT_OUT=AUDIT/'menu-restoration/fighter-name-vector-candidate-v2'
WORDS={'Astraea':[128,64,173,75],'FGA':[173,64,198,75],'Mk.':[198,64,218,75],
 'I':[218,64,224,75],'Endymion':[128,75,186,87],'FRS':[186,75,210,86]}

def proof_map():
 _,expected_raw,expected_clut=verify_stock(SOURCE,KEY)
 source=load(AUDIT/'menu-restoration/description-vector-candidate-v4/source-map.json');scenes=[]
 by_uv={tuple(uv):text for text,uv in WORDS.items()}
 for scene in source['scenes']:
  if scene['scene']=='arm':continue
  proof_path=Path(scene['proof']['path']);proof=load(proof_path)
  require(proof['visual_confirmed'] is True and proof['ram_writes'] is False and proof['assisted'] is False,'Invalid native name source scene')
  shot=proof['capture'];require(sha(shot['path'])==shot['sha256'],'Source screenshot changed')
  vram_path=Path(proof['vram']['path']);vram=vram_path.read_bytes()
  require(len(vram)==1048576,'Invalid source VRAM size')
  raw=b''.join(vram[((256+y)*1024+832)*2:((256+y)*1024+896)*2] for y in range(256))
  clut=vram[(485*1024+256)*2:(485*1024+272)*2]
  require(raw==expected_raw and clut==expected_clut,'Name page/palette differs from current native scene')
  frames=proof['gp0_frames'];draws=gp0.parse_frame(frames[len(frames)//2])
  names=[d for d in draws if d['page_xy_words']==[832,256] and d['depth']==0 and
   d['clut_xy_words']==[256,485] and d['display_local_xy'][1]==48 and tuple(d['source_uv_half_open']) in by_uv]
  names.sort(key=lambda d:d['display_local_xy'][0]);names=[{'text':by_uv[tuple(d['source_uv_half_open'])],**d} for d in names]
  text=[n['text'] for n in names]
  expected={'mkii':['Endymion','FRS','Mk.','I','I'],'mkiii':['Endymion','FRS','Mk.','I','I','I'],
   'astraea':['Astraea','FGA','Mk.','I']}[scene['scene']]
  require(text==expected,'Name GP0 composition differs: '+scene['scene'])
  scenes.append({'scene':scene['scene'],'proof':ref(proof_path),'capture':shot,'vram':ref(vram_path),
    'source_words_sha256':hashlib.sha256(raw).hexdigest(),'source_clut_sha256':hashlib.sha256(clut).hexdigest(),
    'names':names,'confirmed_name':' '.join(expected[:3])+''.join(expected[3:])})
 require(len(scenes)==3,'All three starter name scenes are required')
 # A freshv11frame proves the still-visible field uses the same actual quads.
 fresh_path=AUDIT/'dev-center-evidence/typography-repair-20261112-v11/fighter-settled-vector-review-live.json'
 fresh=load(fresh_path);frames=fresh['gp0_frames'];draws=gp0.parse_frame(frames[len(frames)//2])
 names=sorted([d for d in draws if d['page_xy_words']==[832,256] and d['clut_xy_words']==[256,485] and
  d['display_local_xy'][1]==48 and tuple(d['source_uv_half_open']) in by_uv],key=lambda d:d['display_local_xy'][0])
 require([by_uv[tuple(d['source_uv_half_open'])] for d in names]==['Endymion','FRS','Mk.','I','I'],'Fresh actual name quads differ')
 return {'key':KEY,'word_quads':WORDS,'native_scenes':scenes,'fresh_v11_actual_gp0':ref(fresh_path),
  'source_binding':'All3sourceVRAMbrackets contain byte-exact1AD90FC9-4315989E and fullGP0name quads; freshv11frame corroborates the actual rendered Endymion field',
  'internal_registration':'Each whole word is source-proven; internal TTFletter spacing is newly authored inside that exact word quad, not inferred individual guest glyph addresses'}

def font():
 f=ImageFont.truetype(str(FONT),200);f.set_variation_by_axes([550,100]);return f

def word(text,uv,native,f):
 x0,y0,x1,y1=uv;w=(x1-x0)*16;h=(y1-y0)*16;crop=np.array(native.crop(tuple(uv)))
 yy,xx=np.where(crop[:,:,3]>0);box=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
 mask=Image.new('L',(w,h));baseline=148
 if text=='I':
  d=ImageDraw.Draw(mask);d.rounded_rectangle((.2*16,.35*16,1.7*16,baseline),radius=.1*16,fill=255)
 else:
  temp=Image.new('L',(4096,512));d=ImageDraw.Draw(temp);d.text((24,320),text,font=f,fill=255,anchor='ls')
  bounds=temp.getbbox();glyph=temp.crop(bounds);target_width=round((box[2]-box[0]-.5)*16)
  glyph=glyph.resize((target_width,glyph.height),Image.Resampling.LANCZOS)
  left=round((box[0]+.2)*16);top=baseline+bounds[1]-320
  require(top>=0 and top+glyph.height<=h and left+glyph.width<=w,'Fighter name outline clipped: '+text)
  mask.paste(glyph,(left,top))
 coverage=np.asarray(mask).astype(np.float32)/255;rgba=np.zeros((h,w,4),np.uint8)
 rgba[:,:,:3]=np.rint(coverage[:,:,None]*240).astype(np.uint8)
 rgba[:,:,3]=np.where(coverage==0,0,np.where(coverage>=.86,127,255)).astype(np.uint8)
 return rgba,{'text':text,'uv':uv,'native_optical_registration':box,'baseline_native':baseline/16,
  'font_size':200,'font_axes':[550,100],'source_face_rgb':[240,240,240],
  'alpha_policy':'0clear/127nonSTPsolidface/255STPedge; actual source431palette face0 is240nonSTP'}

def build(output):
 require(not output.exists(),'Choose a new immutable output directory');source=proof_map()
 parent=load(PARENT);row=next(r for r in parent['files'] if r['name']==KEY+'.png');parent_path=Path(row['composed_path'])
 require(sha(parent_path)==row['sha256'],'Name parent changed');before=pixels(parent_path);after=before.copy()
 native=Image.open(SOURCE/(KEY+'.png')).convert('RGBA');f=font();selected=np.zeros((4096,4096),bool);records=[]
 for text,uv in WORDS.items():
  rgba,record=word(text,uv,native,f);x0,y0,x1,y1=uv;after[y0*16:y1*16,x0*16:x1*16]=rgba;selected[y0*16:y1*16,x0*16:x1*16]=True;records.append(record)
 require(np.array_equal(after[~selected],before[~selected]),'Unrelated name-page pixels changed')
 output.mkdir(parents=True);pack=output/'pack/einhander-texture-replacements';pack.mkdir(parents=True);(pack.parent/'Hashes.ini').write_text('')
 target=pack/(KEY+'.png');Image.fromarray(after).save(target);require(np.array_equal(pixels(target),after),'PNG roundtrip failed')
 write(output/'source-map.json',source);np.savez_compressed(output/'changed-masks.npz',page=selected)
 preview(output,source,before,after);shutil.copyfile(__file__,output/'build-source.py')
 manifest={'format':1,'contract':'actual-fighter-name-vectors-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
  'parent_candidate':ref(PARENT),'source_map':ref(output/'source-map.json'),'font':ref(FONT),'builder':ref(Path(__file__)),
  'method':'Fresh Bahnschrift550weight200px vectors with shared9.25native baseline inside6exact actual fighter name-word quads; no neural/blur/threshold source shapes',
  'asset_count':1,'files':[{'key':KEY,'parent':ref(parent_path),'outputs':{'pack':{**ref(target),'size':[4096,4096]}},
    'selected_native_regions':list(WORDS.values()),'registered_words':records,'protected_outside_exact':True,
    'source_archives':[ref(SOURCE/(KEY+s)) for s in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json')],
    'alpha_classes':list(map(int,np.unique(after[:,:,3]))),'live_acceptance':'NOT RUN'}],
  'production_installed':False,'game_actions':0,'live_acceptance':'NOT RUN',
  'limits':['Only exact actual431palette is authored; other unseen palette variants are not invented.',
   'Every word preserves its original quad and screen advance; internal TTFspacing is newly authored.',
   'Actual3fighter replay at4x/2160p remains required.']}
 write(output/'manifest.json',manifest);verify(output)

def preview(output,source,before,after):
 canvas=Image.new('RGB',(1280,470),(12,23,39));d=ImageDraw.Draw(canvas);y=12
 for label,page in [('Parent actual name quads',before),('Fresh actual name quads',after)]:
  d.text((12,y),label+' | actual4x GP0positions/advances, class127opaque',fill='white');y+=30
  for scene in source['native_scenes']:
   for item in scene['names']:
    x0,y0,x1,y1=item['source_uv_half_open'];a=page[y0*16:y1*16,x0*16:x1*16]
    rgb=Image.fromarray(a[:,:,:3]).resize(((x1-x0)*4,(y1-y0)*4),Image.Resampling.LANCZOS)
    alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
    canvas.paste(rgb,(item['display_local_xy'][0]*4,y),alpha)
   y+=62
  y+=12
 require(y<=canvas.height,'Name preview clipped');canvas.crop((0,0,1280,y)).save(output/'fighter-names-before-after-actual4x.png')

def verify(output):
 m=load(output/'manifest.json')
 for field in ('parent_candidate','source_map','font','builder'):require(sha(m[field]['path'])==m[field]['sha256'],'Input changed: '+field)
 require(json.dumps(proof_map(),sort_keys=True)==json.dumps(load(output/'source-map.json'),sort_keys=True),'Name source mapping changed')
 row=m['files'][0];require(sha(row['outputs']['pack']['path'])==row['outputs']['pack']['sha256'],'Output changed');require(sha(row['parent']['path'])==row['parent']['sha256'],'Parent changed')
 for r in row['source_archives']:require(sha(r['path'])==r['sha256'],'Source proof changed')
 actual=pixels(row['outputs']['pack']['path']);parent=pixels(row['parent']['path']);native=Image.open(SOURCE/(KEY+'.png')).convert('RGBA');f=font()
 with np.load(output/'changed-masks.npz') as masks:selection=masks['page']
 require(np.array_equal(actual[~selection],parent[~selection]),'Protected page pixels changed')
 for text,uv in WORDS.items():
  expected,_=word(text,uv,native,f);x0,y0,x1,y1=uv;require(np.array_equal(actual[y0*16:y1*16,x0*16:x1*16],expected),'Name vector recipe differs')
 require(set(map(int,np.unique(actual[:,:,3])))<={0,127,255},'Noncategorical PSXalpha')
 receipt={'outcome':'PASS','output_pngs':1,'source_proven_native_fighter_scenes':3,'exact_word_quads':6,
  'fresh_v11_actual_draw_quads_corroborated':True,'all_vector_recipes_exact':True,'protected_parent_rgba_exact':True,
  'live_acceptance':'NOT RUN'};write(output/'verification.json',receipt);print(json.dumps({'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUT);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:verify(a.output.resolve())
 else:build(a.output.resolve())
