"""Rebuild source-identified narrow English glyphs without guessed atlas aliases.

B77contains26Latin capitals,26lowercase letters and10digits. FileOption's
completeGP0 corroborates the actual cropped metrics of observed text. The
native contact sheet records every remaining single-glyph identification.
Only three captured strip families are byte-exact B77row aliases.9D8DF52A is
explicitly excluded because its source words differ, including the foverhang.
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

import map_vector_description_glyphs as gp0
from build_results_vector_candidate import sha, ref, load, pixels, write, require
from build_three_asset_proof import verify_stock
from build_ranking_banner_vectors import render

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10'
SOURCE=AUDIT/'menu-restoration/banner-font-candidate-v2/sources'
STRIPS=AUDIT/'menu-restoration/font-strip-candidate-v6/sources'
DEFAULT_OUT=AUDIT/'menu-restoration/narrow-menu-vector-candidate-v1'
FONT=Path('C:/Windows/Fonts/bahnschrift.ttf')
GP0=AUDIT/'dev-center-evidence/hud-4k-candidate-20261112-v4/native-extra-menus/source-bracket-gp0.json'
GP0_RECEIPT=GP0.with_name('source-bracket.json')
ALIAS_ROWS={'C544AC0D':88,'2C6866AA':96,'8D0FCF8A':104}
UPPER=[('A',[72,104,81,111]),('B',[12,96,19,103]),('C',[22,96,28,103]),
 ('D',[30,96,37,103]),('E',[40,96,46,103]),('F',[48,96,54,103]),
 ('G',[56,96,63,103]),('H',[66,96,73,103]),('I',[76,96,79,103]),
 ('J',[82,96,88,103]),('K',[90,96,98,103]),('L',[110,96,116,103]),
 ('M',[128,96,139,103]),('N',[142,96,149,103]),('O',[152,96,159,103]),
 ('P',[170,96,177,103]),('Q',[182,96,190,103]),('R',[192,96,200,103]),
 ('S',[202,96,209,103]),('T',[212,96,219,103]),('U',[222,96,229,103]),
 ('V',[12,104,21,111]),('W',[24,104,35,111]),('X',[38,104,47,111]),
 ('Y',[50,104,59,111]),('Z',[62,104,69,111])]
LOWER=[('a',[56,90,62,95]),('b',[64,88,70,95]),('c',[72,90,77,95]),
 ('d',[80,88,86,95]),('e',[88,90,94,95]),('f',[96,87,101,95]),
 ('g',[102,90,108,96]),('h',[110,88,116,95]),('i',[118,88,120,95]),
 ('j',[122,88,126,96]),('k',[128,88,134,95]),('l',[136,88,138,95]),
 ('m',[140,90,148,95]),('n',[150,90,156,95]),('o',[158,90,164,95]),
 ('p',[166,90,172,96]),('q',[174,90,180,96]),('r',[182,90,186,95]),
 ('s',[188,90,194,95]),('t',[196,89,201,95]),('u',[204,90,210,95]),
 ('v',[212,90,219,95]),('w',[222,90,230,95]),('x',[232,90,238,95]),
 ('y',[240,90,246,96]),('z',[248,90,253,95])]
DIGITS=[(str(i),[x,104,end,111]) for i,(x,end) in enumerate(
 [(84,90),(92,95),(98,104),(106,112),(114,120),(122,128),(130,136),(138,144),(146,152),(154,160)])]
PUNCT=[(':',[204,105,206,110]),('-',[198,107,202,108]),('.', [178,109,180,111]),(',', [182,109,184,112])]
GLYPHS=UPPER+LOWER+DIGITS+PUNCT
FILE_GROUPS=[('Create data file',[40,54,134,64]),('Discard data file',[40,70,138,80]),
 ('Score',[40,87,76,97]),('Score Ranking',[40,103,126,113]),
 ('Data Load',[40,119,101,129]),('Exit',[40,151,64,161]),
 ('Enter',[227,197,261,209]),('Exit',[274,197,301,209])]

def font():
 f=ImageFont.truetype(str(FONT),296);f.set_variation_by_axes([550,100]);return f

def decode(raw,height=256):
 words=np.frombuffer(raw,dtype='<u2').reshape(height,64);indices=np.empty((height,256),np.uint8)
 for n in range(4):indices[:,n::4]=((words>>(n*4))&15).astype(np.uint8)
 return indices

def palette(clut):
 w=np.frombuffer(clut,dtype='<u2');return np.stack(((w&31)*8,((w>>5)&31)*8,((w>>10)&31)*8,
  np.where(w==0,0,np.where(w&32768,255,127))),1).astype(np.uint8)

def source_map():
 proof=load(GP0);receipt=load(GP0_RECEIPT);shot=receipt['capture']
 require(sha(shot['path'])==shot['sha256'],'FileOption capture changed')
 require(proof['frame']==receipt['gp0_frame'] and len(proof['entries'])==receipt['gp0_count'],'GP0 bracket changed')
 draws=gp0.parse_frame(proof);assignments=[];lines=[];lookup={tuple(uv):c for c,uv in GLYPHS}
 for text,box in FILE_GROUPS:
  x0,y0,x1,y1=box;selected=[d for d in draws if d['page_xy_words']==[640,0] and d['depth']==0 and
   x0<=d['display_local_xy'][0]<x1 and y0<=d['display_local_xy'][1]<y1 and d['source_uv_half_open'][1]>=80]
  # The footer is drawn twice with different CLUTs; both agree on source/XY.
  selected=list({(tuple(d['display_local_xy']),tuple(d['source_uv_half_open'])):d for d in selected}.values())
  selected.sort(key=lambda d:d['display_local_xy'][0]);letters=text.replace(' ','')
  require(len(letters)==len(selected),'FileOption text count mismatch: '+text)
  mapped=[]
  for c,d in zip(letters,selected):
   uv=tuple(d['source_uv_half_open']);require(lookup.get(uv)==c,'Native optical metric conflicts with actual GP0: '+c+' '+str(uv))
   item={'character':c,'text':text,**d};assignments.append(item);mapped.append(item)
  lines.append({'text':text,'rect':box,'assignments':mapped})
 return {'gp0':ref(GP0),'receipt':ref(GP0_RECEIPT),'capture':shot,'lines':lines,
  'known_english_text_glyphs':len(assignments),'gp0_corroborated_characters':sorted({r['character'] for r in assignments}),
  'mapping_limit':'Historical complete GP0 binds FileOption source UVs and English wording. Native raw/CLUT source proofs independently bind source pixels; this is not a claim of a contemporaneous historical VRAM snapshot.'}

def mask(character,uv,f):
 x0,y0,x1,y1=uv;w=(x1-x0)*16;h=(y1-y0)*16
 result=Image.new('L',(w,h));d=ImageDraw.Draw(result)
 if character in 'iIl':
  # Preserve a simple narrow stem instead of expanding a cropped font stem to
  # the whole sourcecell. Dot/stem gaps are deliberate, continuous elsewhere.
  center=w/2;stroke=.68*16;top=.2*16;bottom=(y1-y0-.2)*16
  if character=='i':
   radius=.32*16;cy=.55*16;d.ellipse((center-radius,cy-radius,center+radius,cy+radius),fill=255);top=2.1*16
  d.rounded_rectangle((center-stroke/2,top,center+stroke/2,bottom),radius=.12*16,fill=255)
  return np.asarray(result)
 if character in ':-.,':
  if character=='-':d.rounded_rectangle((.2*16,.18*16,w-.2*16,h-.18*16),radius=.2*16,fill=255)
  else:
   radius=min(.38*16,w*.3);center=w/2
   if character==':':ys=[.75*16,h-.75*16]
   else:ys=[h-(.55 if character=='.' else 1.2)*16]
   for cy in ys:d.ellipse((center-radius,cy-radius,center+radius,cy+radius),fill=255)
   if character==',':d.line((center+.1*16,ys[0],center-.25*16,h-.15*16),fill=255,width=5)
  return np.asarray(result)
 tmp=Image.new('L',(1024,512));td=ImageDraw.Draw(tmp);baseline=400
 td.text((64,baseline),character,font=f,fill=255,anchor='ls');box=tmp.getbbox();require(box is not None,'Empty glyph')
 ink=tmp.crop(box);target_width=max(8,round((x1-x0-.4)*16));left=round(.2*16)
 if character in 'gpqyj':
  above=6.6 if character=='j' else 4.6;below=1.0;top=round(.2*16)
  upper=tmp.crop((box[0],box[1],box[2],baseline)).resize((target_width,round(above*16)),Image.Resampling.LANCZOS)
  lower=tmp.crop((box[0],baseline,box[2],box[3])).resize((target_width,round(below*16)),Image.Resampling.LANCZOS)
  result.paste(upper,(left,top));result.paste(lower,(left,top+upper.height))
 elif character=='f':
  ink=ink.resize((target_width,round(6.6*16)),Image.Resampling.LANCZOS);result.paste(ink,(left,round(1.2*16)))
 else:
  ink=ink.resize((target_width,round((y1-y0-.4)*16)),Image.Resampling.LANCZOS);result.paste(ink,(left,round(.2*16)))
 require(result.getbbox() is not None and result.getbbox()[2]<=w and result.getbbox()[3]<=h,'Vector glyph clips sourcequad')
 return np.asarray(result)

def build(output):
 require(not output.exists(),'Choose a new immutable output directory');mapping=source_map()
 parent=load(PARENT/'candidate.json');parents={r['name'][:-4]:r for r in parent['files']}
 full_keys=sorted(k for k in parents if k.startswith('B77B98B9-'));require(len(full_keys)==7,'Expected seven fullpage palettes')
 _,raw,clut=verify_stock(SOURCE,full_keys[0]);indices=decode(raw);selected=np.zeros((256,256),bool)
 f=font();vectors={c:mask(c,uv,f) for c,uv in GLYPHS}
 for c,(x0,y0,x1,y1) in GLYPHS:
  require(np.any(indices[y0:y1,x0:x1]!=0),'Source glyph is empty: '+c);selected[y0:y1,x0:x1]=True
 require(set(map(int,np.unique(indices[selected])))<={0,10,11,12,13,14,15},'Unexpected source tone codes')
 changed=np.repeat(np.repeat(selected,16,0),16,1);output.mkdir(parents=True)
 pack=output/'pack/einhander-texture-replacements';pack.mkdir(parents=True);(pack.parent/'Hashes.ini').write_text('')
 rows=[];before={};after={}
 def field(pal):
  a=np.zeros((4096,4096,4),np.uint8)
  for c,(x0,y0,x1,y1) in GLYPHS:a[y0*16:y1*16,x0*16:x1*16]=render(vectors[c],pal)
  return a
 def save(key,a,pmask,parent_path,kind,source_refs,source_region=None):
  require(np.array_equal(a[~pmask],pixels(parent_path)[~pmask]),'Protected pixels changed: '+key)
  target=pack/(key+'.png');Image.fromarray(a).save(target);require(np.array_equal(pixels(target),a),'PNG roundtrip changed')
  rows.append({'key':key,'kind':kind,'outputs':{'pack':{**ref(target),'size':[a.shape[1],a.shape[0]]}},
    'parent':ref(parent_path),'source_region':source_region,'selected_native_regions':[
      [x0,max(y0,source_region[1])-source_region[1],x1,min(y1,source_region[3])-source_region[1]]
      for c,(x0,y0,x1,y1) in GLYPHS if source_region and y0<source_region[3] and y1>source_region[1]] if source_region else [uv for c,uv in GLYPHS],
    'source_archives':source_refs,'protected_outside_exact':True,'alpha_classes':list(map(int,np.unique(a[:,:,3]))),
    'live_acceptance':'NOT RUN'})
 for key in full_keys:
  _,words,cl=verify_stock(SOURCE,key);require(words==raw,'Fullpage source variants differ')
  row=parents[key];parent_path=Path(row['composed_path']);require(sha(parent_path)==row['sha256'],'Parent changed')
  base=pixels(parent_path);fresh=field(palette(cl));a=base.copy();a[changed]=fresh[changed]
  save(key,a,changed,parent_path,'narrow_full_page',[ref(SOURCE/(key+s)) for s in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json')])
  before[key]=base;after[key]=a
 for key,row in sorted(parents.items()):
  family=key.split('-')[0]
  if family not in ALIAS_ROWS:continue
  start=ALIAS_ROWS[family];_,words,cl=verify_stock(STRIPS,key)
  require(words==raw[start*128:(start+8)*128],'Strip source is not the exact canonical row: '+key)
  parent_path=Path(row['composed_path']);require(sha(parent_path)==row['sha256'],'Alias parent changed')
  base=pixels(parent_path);fresh=field(palette(cl))[start*16:(start+8)*16];pmask=changed[start*16:(start+8)*16]
  a=base.copy();a[pmask]=fresh[pmask]
  save(key,a,pmask,parent_path,'source_exact_row_alias',[ref(STRIPS/(key+s)) for s in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json')],[0,start,256,start+8])
 require(len(rows)==27,'Expected seven fullpages and20source-exact existing rowkeys')
 preview(output,mapping,indices,before,after)
 write(output/'source-map.json',{'glyphs':[{'character':c,'uv':uv,'identity':'Directly visually identified single native glyph; opticalUV bounds are exact source rectangles'} for c,uv in GLYPHS],
  'file_option':mapping,'source_native':ref(SOURCE/'B77B98B9-8EAF967E.png'),
  'source_character_count':62,'additional_punctuation':[':', '-', '.', ','],
  'excluded_9D8DF52A':'Not B77row80: canonical rowCRC D3D55094, selected foverhang raw words also differ; no invented alias is authored'})
 np.savez_compressed(output/'changed-masks.npz',page=changed)
 shutil.copyfile(__file__,output/'build-source.py')
 manifest={'format':1,'contract':'narrow-menu-vectors-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
  'method':'Fresh Bahnschrift550weight outlines within66exact native opticalUVs; sharedcap/xheight6.6/4.6nativepx and1pxdescenders; each actual source palette retains its0/10..15 classes',
  'parent_composition':ref(PARENT/'candidate.json'),'source_map':ref(output/'source-map.json'),'font':ref(FONT),'font_axes':[550,100],
  'builder':ref(Path(__file__)),'render_library':ref(AUDIT/'build_ranking_banner_vectors.py'),
  'files':rows,'asset_count':len(rows),'character_count':62,'punctuation_count':4,
  'production_installed':False,'game_actions':0,'live_acceptance':'NOT RUN',
  'limits':['Fresh native letteridentifications and GP0source registration are distinct evidence; only observedFileOption wording is claimed.',
   '9D8DF52A source is not the canonical row80 and remains unchanged.',
   'Other nonLatin,buttons and symbols remain unchanged; actual Configuration/Ranking replay and2160pquality review remain required.']}
 write(output/'manifest.json',manifest);verify(output)

def preview(output,mapping,indices,before,after):
 canvas=Image.new('RGB',(1536,1380),(10,17,25));d=ImageDraw.Draw(canvas);key='B77B98B9-C04F65C0';y=12
 for label,book in [('Parent narrow font',before[key]),('Fresh narrow font550weight',after[key])]:
  d.text((10,y),label+' | actual4x, original sprite advances and offsets',fill='white');y+=32
  for line in mapping['lines']:
   minimum_x=min(a['display_local_xy'][0] for a in line['assignments']);minimum_y=min(a['display_local_xy'][1] for a in line['assignments'])
   for item in line['assignments']:
    x0,y0,x1,y1=item['source_uv_half_open'];a=book[y0*16:y1*16,x0*16:x1*16]
    rgb=Image.fromarray(a[:,:,:3]).resize(((x1-x0)*4,(y1-y0)*4),Image.Resampling.LANCZOS)
    alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
    canvas.paste(rgb,(12+(item['display_local_xy'][0]-minimum_x)*4,y+(item['display_local_xy'][1]-minimum_y)*4),alpha)
   y+=52
  y+=16
 require(y<=canvas.height,'Preview clips');canvas.crop((0,0,1536,y)).save(output/'narrow-before-after-actual4x.png')
 sheet=Image.new('RGB',(1536,640),(10,17,25));sd=ImageDraw.Draw(sheet);native=pixels(SOURCE/'B77B98B9-8EAF967E.png')
 for n,(c,uv) in enumerate(GLYPHS):
  x=n%16*96;y=n//16*128;x0,y0,x1,y1=uv;sd.text((x+2,y+2),c+' '+str(uv[:2]),fill='white')
  im=Image.fromarray(native[y0:y1,x0:x1,:3]).resize(((x1-x0)*7,(y1-y0)*7),Image.Resampling.NEAREST);sheet.paste(im,(x+2,y+24))
 sheet.save(output/'native-narrow-glyph-contact-sheet.png')

def verify(output):
 m=load(output/'manifest.json')
 for field in ('parent_composition','source_map','font','builder','render_library'):
  require(sha(m[field]['path'])==m[field]['sha256'],'Referenced input changed: '+field)
 source=load(output/'source-map.json');require(json.dumps(source_map(),sort_keys=True)==json.dumps(source['file_option'],sort_keys=True),'FileOption mapping changed')
 _,raw,_=verify_stock(SOURCE,'B77B98B9-8EAF967E');f=font();vectors={c:mask(c,uv,f) for c,uv in GLYPHS}
 with np.load(output/'changed-masks.npz') as masks:changed=masks['page']
 checked=0
 for row in m['files']:
  out=row['outputs']['pack'];require(sha(out['path'])==out['sha256'],'Output hash changed');require(sha(row['parent']['path'])==row['parent']['sha256'],'Parent changed')
  for r in row['source_archives']:require(sha(r['path'])==r['sha256'],'Source changed')
  current=pixels(out['path']);parent=pixels(row['parent']['path']);start=row['source_region'][1] if row['source_region'] else 0
  pmask=changed[start*16:(start+8)*16] if row['source_region'] else changed
  require(np.array_equal(current[~pmask],parent[~pmask]),'Protected page/row pixels changed')
  directory=STRIPS if row['source_region'] else SOURCE;_,words,cl=verify_stock(directory,row['key']);pal=palette(cl)
  if row['source_region']:require(words==raw[start*128:(start+8)*128],'Invalid row alias')
  for c,(x0,y0,x1,y1) in GLYPHS:
   if row['source_region'] and not(y0<start+8 and y1>start):continue
   expected=render(vectors[c],pal);lo=max(y0,start);hi=min(y1,start+8) if row['source_region'] else y1
   require(np.array_equal(current[(lo-start)*16:(hi-start)*16,x0*16:x1*16],expected[(lo-y0)*16:(hi-y0)*16]),'Vector/alias recipe differs: '+c)
  require(set(map(int,np.unique(current[:,:,3])))<={0,127,255},'Noncategorical PSX class');checked+=1
 receipt={'outcome':'PASS','verified_output_pngs':checked,'english_characters':62,'punctuation':4,
  'source_exact_strip_aliases':20,'fullpage_variants':7,'file_option_gp0_characters':source['file_option']['known_english_text_glyphs'],
  'all_vector_recipes_reproduced_exact':True,'protected_parent_rgba_exact':True,
  '9D8DF52A_untouched_because_not_source_alias':True,'live_acceptance':'NOT RUN'}
 write(output/'verification.json',receipt);print(json.dumps({'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUT);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
 if args.verify:verify(args.output.resolve())
 else:build(args.output.resolve())
