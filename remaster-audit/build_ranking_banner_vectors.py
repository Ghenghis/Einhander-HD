"""Rebuild the B77 large Latin/numeric font from fresh registered outlines.

Native source artwork identifies each complete glyph. Existing renderer queries
provide observed sampled bounds where available; they are never a text log.
Every one of the seven source-verified palettes retains its original face and
categorical blend classes. Unrelated page data and all prior packs are immutable.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_three_asset_proof import verify_stock
from build_results_vector_candidate import sha, ref, load, pixels, write, require

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9'
SOURCES=AUDIT/'menu-restoration/banner-font-candidate-v2/sources'
PRIOR=AUDIT/'menu-restoration/banner-font-candidate-v2/manifest.json'
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
DEFAULT_OUT=AUDIT/'menu-restoration/ranking-banner-vector-candidate-v2'
QUERY=AUDIT/'dev-center-evidence/hud-4k-candidate-20261112-v6/native-v6-menu-replay/capture.jsonl'
GLYPHS=[
 ('A',[2,32,19,47]),('B',[28,32,43,47]),('C',[46,32,59,47]),('D',[62,32,77,47]),
 ('E',[94,32,108,47]),('F',[118,32,132,47]),('G',[134,32,148,47]),('H',[150,32,165,47]),
 ('I',[168,32,174,47]),('J',[176,32,188,47]),('K',[190,32,207,47]),('L',[210,32,224,47]),
 ('M',[226,32,248,47]),('N',[2,48,17,63]),('O',[20,48,34,63]),('P',[36,48,51,63]),
 ('Q',[54,48,70,63]),('R',[72,48,89,63]),('S',[92,48,106,63]),('T',[108,48,123,63]),
 ('U',[126,48,141,63]),('V',[144,48,162,63]),('W',[164,48,186,63]),('X',[188,48,207,63]),
 ('Y',[210,64,227,79]),('Z',[232,48,246,63]),
 ('0',[56,64,68,79]),('1',[70,64,76,79]),('2',[78,64,90,79]),('3',[92,64,104,79]),
 ('4',[106,64,120,79]),('5',[122,64,134,79]),('6',[136,64,148,79]),('7',[150,64,163,79]),
 ('8',[166,64,178,79]),('9',[182,64,194,79]),
]

def font():
 f=ImageFont.truetype(str(FONT),296);f.set_variation_by_axes([600,100]);return f

def sources():
 prior=load(PRIOR);keys=sorted(r['key'] for r in prior['assets'])
 require(len(keys)==7,'Expected seven source palettes')
 native={};palettes={};word_hash=None
 for key in keys:
  metadata,raw,clut=verify_stock(SOURCES,key)
  if word_hash is None:word_hash=hashlib.sha256(raw).hexdigest()
  require(hashlib.sha256(raw).hexdigest()==word_hash,'Palette variants differ in source words')
  w=np.frombuffer(clut,dtype='<u2');palette=np.stack(((w&31)*8,((w>>5)&31)*8,((w>>10)&31)*8,
    np.where(w==0,0,np.where(w&32768,255,127))),1).astype(np.uint8)
  # Independent 4-bit decode confirms the PNG rather than relying on appearance.
  words=np.frombuffer(raw,dtype='<u2').reshape(256,64);indices=np.empty((256,256),np.uint8)
  for shift in range(4):indices[:,shift::4]=((words>>(shift*4))&15).astype(np.uint8)
  decoded=palette[indices];require(np.array_equal(decoded,pixels(SOURCES/(key+'.png'))),'Source PNG decode differs')
  native[key]=decoded;palettes[key]=palette
 query_bytes=QUERY.read_bytes();records=[json.loads(l) for l in query_bytes.splitlines() if l]
 records=[r for r in records if r.get('key','').startswith('B77B98B9-') and
   r.get('event') in ('source_draw_query_matched','replacement_gl_draw_submitted')]
 recipes=[]
 # Exact native ink registrations have been visually identified on a source
 # contact sheet. This is not OCR or an assertion of an original font family.
 for character,uv in GLYPHS:
  x0,y0,x1,y1=uv;source_crop=indices[y0:y1,x0:x1]
  require(np.any(source_crop!=0),'Registered glyph is empty: '+character)
  matches=[r for r in records if r.get('uv_bounds',[None,None])[:2]==uv[:2]]
  observed=sorted({tuple(r['uv_bounds']) for r in matches})
  width=min([x1-x0]+[b[2]-b[0]+1 for b in observed]);height=min([y1-y0]+[b[3]-b[1]+1 for b in observed])
  require(width>2 and height>=14,'Unexpected clipped native font query: '+character)
  recipes.append({'character':character,'uv':uv,'optical_source_registration':'Manually identified full native Latin/numeric glyph in source-verified B77 atlas',
    'query_bounds_inclusive':[list(b) for b in observed],'observed_queries':len(matches),
    'safe_sample_width_native':width,'safe_sample_height_native':height,
    'authored_cap_height_native':13.25,'authored_top_native':.25,
    'authored_width_native':width-.6,'authored_left_native':.2,
    'source_query_limit':'A sampled texture query establishes sampled UV bounds, not wording or final visibility'})
 return keys,native,palettes,recipes,{'path':str(QUERY),'sha256':hashlib.sha256(query_bytes).hexdigest()},indices

def glyph_mask(recipe,f):
 character=recipe['character'];x0,y0,x1,y1=recipe['uv']
 tmp=Image.new('L',(1024,512));d=ImageDraw.Draw(tmp);d.text((64,420),character,font=f,fill=255,anchor='ls')
 box=tmp.getbbox();require(box is not None,'Empty vector outline')
 glyph=tmp.crop(box).resize((round(recipe['authored_width_native']*16),round(recipe['authored_cap_height_native']*16)),Image.Resampling.LANCZOS)
 mask=Image.new('L',((x1-x0)*16,(y1-y0)*16));left=round(recipe['authored_left_native']*16);top=round(recipe['authored_top_native']*16)
 require(left+glyph.width<=recipe['safe_sample_width_native']*16 and top+glyph.height<=recipe['safe_sample_height_native']*16,'Outline exceeds observed sampled bounds')
 mask.paste(glyph,(left,top));return np.asarray(mask)

def render(mask,palette):
 """Fresh coverage chooses original0/10..15 tones/classes in a narrow AA rim."""
 coverage=mask.astype(np.float32)/255
 anchors=np.array([0,.10,.25,.40,.55,.75,1.0],np.float32);codes=np.array([0,10,11,12,13,14,15])
 rgba=np.empty((*mask.shape,4),np.uint8)
 for channel in range(3):rgba[:,:,channel]=np.rint(np.interp(coverage,anchors,palette[codes,channel])).astype(np.uint8)
 nearest=np.abs(coverage[:,:,None]-anchors[None,None,:]).argmin(2);rgba[:,:,3]=palette[codes[nearest],3]
 return rgba

def preview(output,recipes,before,after):
 keys=['B77B98B9-8EAF967E','B77B98B9-C04F65C0','B77B98B9-30A66678']
 lines=['CONFIGURATION','SCORE RANKING','NO DATA','0123456789'];lookup={r['character']:r for r in recipes}
 canvas=Image.new('RGB',(1536,2300),(10,17,25));d=ImageDraw.Draw(canvas);y=12
 def paste(a,x,y,scale=4):
  rgb=Image.fromarray(a[:,:,:3]).resize((a.shape[1]*scale//16,a.shape[0]*scale//16),Image.Resampling.LANCZOS)
  # PSX alpha is a class;127 does not mean halfopacity.
  alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
  canvas.paste(rgb,(x,y),alpha)
 for key in keys:
  d.text((10,y),key+' | original sourceUVregistration and each actual palette',fill='white');y+=28
  for label,book in [('Parent',before[key]),('Fresh600weight vector',after[key])]:
   d.text((10,y),label,fill='white');y+=28
   for line in lines:
    x=12
    for c in line:
     if c==' ':x+=24;continue
     r=lookup[c];x0,y0,x1,y1=r['uv'];a=book[y0*16:y1*16,x0*16:x1*16]
     paste(a,x,y);x+=(x1-x0+2)*4
    y+=68
   y+=10
 require(y<=canvas.height,'Actual4x preview would clip a palette sample')
 canvas.crop((0,0,1536,y)).save(output/'ranking-before-after-actual4x.png')
 # Native artwork contact sheet documents source identities, including Y at
 # row64 rather than the blank row48 slot. Each opticalquad is explicit.
 native_key='B77B98B9-8EAF967E';source=pixels(SOURCES/(native_key+'.png'))
 sheet=Image.new('RGB',(1280,384),(10,17,25));sd=ImageDraw.Draw(sheet)
 for index,r in enumerate(recipes):
  x=(index%12)*106;y=(index//12)*128;x0,y0,x1,y1=r['uv'];crop=source[y0:y1,x0:x1]
  sd.text((x+2,y+3),r['character']+' '+str(r['uv'][:2]),fill='white')
  rgb=Image.fromarray(crop[:,:,:3]).resize(((x1-x0)*4,(y1-y0)*4),Image.Resampling.NEAREST);sheet.paste(rgb,(x+2,y+25))
 sheet.save(output/'native-glyph-registration-contact-sheet.png')

def build(output):
 require(not output.exists(),'Choose a new immutable output directory')
 keys,native,palettes,recipes,query,indices=sources();parents={r['name'][:-4]:r for r in load(PARENT/'candidate.json')['files']}
 mask=np.zeros((4096,4096),bool);f=font();vectors={r['character']:glyph_mask(r,f) for r in recipes}
 output.mkdir(parents=True);pack=output/'pack/einhander-texture-replacements';pack.mkdir(parents=True);(pack.parent/'Hashes.ini').write_text('')
 rows=[];before={};after={}
 for key in keys:
  row=parents[key];path=Path(row['composed_path']);require(sha(path)==row['sha256'],'Current parent changed')
  base=pixels(path);result=base.copy()
  for r in recipes:
   x0,y0,x1,y1=r['uv'];result[y0*16:y1*16,x0*16:x1*16]=render(vectors[r['character']],palettes[key]);mask[y0*16:y1*16,x0*16:x1*16]=True
  require(np.array_equal(result[~mask],base[~mask]),'Protected page data changed')
  target=pack/(key+'.png');Image.fromarray(result).save(target);require(np.array_equal(pixels(target),result),'Output PNG roundtrip failed')
  before[key]=base;after[key]=result
  rows.append({'key':key,'outputs':{'pack':{**ref(target),'size':[4096,4096]}},'parent':ref(path),
    'selected_native_regions':[r['uv'] for r in recipes],'protected_outside_exact':True,
    'source_archives':[ref(SOURCES/(key+suffix)) for suffix in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json')],
    'source_face_rgba':palettes[key][15].tolist(),'source_background_rgba':palettes[key][0].tolist(),
    'palette_rim_rgba':palettes[key][[10,11,12,13,14]].tolist(),'alpha_classes':list(map(int,np.unique(result[:,:,3]))),
    'live_acceptance':'NOT RUN'})
 preview(output,recipes,before,after);np.savez_compressed(output/'changed-masks.npz',page=mask)
 write(output/'source-map.json',{'glyphs':recipes,'source_artwork':ref(SOURCES/'B77B98B9-8EAF967E.png'),
   'query':query,'source_glyph_count':36,'omitted_unmapped_glyphs':[],
   'wording_witnesses':[ref(PARENT.parent/'hud-4k-candidate-20261112-v6/captures'/name) for name in
    ('resume-v6-configuration-observed.png','resume-v6-score-ranking-confirmed-1.png')]})
 shutil.copyfile(__file__,output/'build-source.py')
 manifest={'format':1,'contract':'ranking-banner-vectors-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
   'method':'Fresh Bahnschrift600weight vector contours at commoncapheight13.25native pixels; registrationUVs and sampled limits remain source-bound; same original palettes0/10..15 supply face/rim/background classes',
   'parent_composition':ref(PARENT/'candidate.json'),'prior_font':ref(PRIOR),'source_map':ref(output/'source-map.json'),
   'font':ref(FONT),'font_axes':[600,100],'builder':ref(Path(__file__)),'files':rows,'asset_count':len(rows),
   'glyph_count':36,'production_installed':False,'game_actions':0,'live_acceptance':'NOT RUN',
   'limits':['Nativeart establishes each single-glyph identity; sampledquery logs do not prove an unobserved word or actual replacement visibility.',
     'These26Latin capitals and10digits are the complete identified largefont. Other symbols,smallfont strips and nonLatin art remain unchanged.',
     'Actual Configuration/Ranking replay and motion/2160pquality review remain required.']}
 write(output/'manifest.json',manifest);verify(output)

def verify(output):
 manifest=load(output/'manifest.json');require(manifest['contract']=='ranking-banner-vectors-v1','Wrong contract')
 for field in ('parent_composition','prior_font','source_map','font','builder'):
  require(sha(manifest[field]['path'])==manifest[field]['sha256'],'Input hash changed: '+field)
 keys,native,palettes,recipes,query,indices=sources();source=load(output/'source-map.json')
 require(recipes==source['glyphs'] and query==source['query'],'Source mapping changed')
 with np.load(output/'changed-masks.npz') as masks:mask=masks['page']
 f=font();vectors={r['character']:glyph_mask(r,f) for r in recipes};count=0
 for row in manifest['files']:
  out=row['outputs']['pack'];require(sha(out['path'])==out['sha256'],'Output hash changed');require(sha(row['parent']['path'])==row['parent']['sha256'],'Parent hash changed')
  current=pixels(out['path']);parent=pixels(row['parent']['path']);require(np.array_equal(current[~mask],parent[~mask]),'Protected page data changed')
  require(set(map(int,np.unique(current[:,:,3])))<={0,127,255},'Noncategorical PSX class')
  for r in recipes:
   x0,y0,x1,y1=r['uv'];require(np.array_equal(current[y0*16:y1*16,x0*16:x1*16],render(vectors[r['character']],palettes[row['key']])),'Vector recipe differs')
  count+=1
 # A changedoutside pixel exercises the protected-grid acceptance condition.
 sample=pixels(manifest['files'][0]['outputs']['pack']['path']);y,x=map(int,np.argwhere(~mask)[0]);sample[y,x,0]^=1
 require(not np.array_equal(sample[~mask],pixels(manifest['files'][0]['parent']['path'])[~mask]),'Protected-grid corruption control failed')
 receipt={'outcome':'PASS','verified_output_pngs':count,'native_source_palettes':len(keys),'vector_glyphs_each':len(recipes),
   'vector_recipes_reproduced_exact':True,'outside_source_bound_regions_exact':True,
   'negative_controls':['Protected grid pixel corruption rejected'],'live_acceptance':'NOT RUN'}
 write(output/'verification.json',receipt);print(json.dumps({'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUT);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
 if args.verify:verify(args.output.resolve())
 else:build(args.output.resolve())
