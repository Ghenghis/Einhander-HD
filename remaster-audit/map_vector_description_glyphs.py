"""Map confirmed English lines to complete GP0 glyph rectangles, then author vectors.

Only complete, visually confirmed GP0/VRAM brackets can establish character
ownership. Research source sampling is deliberately not treated as a text log.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
AUDIT=ROOT/'remaster-audit'
OUT=AUDIT/'menu-restoration/description-vector-candidate-v4'
KEY='BDAE4156-B88C038E'
FONT=Path('C:/Windows/Fonts/EcoSansMono.ttf')
FONT_SIZE=148
BASELINE=114
TRANSCRIPTS={
 'mkii':['Lead fighter with','loadable spare gunpod.','Can instantly adapt',
         'to battle conditions by','switching equipped','and loaded gunpods.',
         'Set Weapons:','machine guns x1','gunpods x3'],
 'mkiii':['New fighter cannot','load spare gunpods,','but can strengthen',
          'multiple weapons and','has simplified firearms','system. Easy to pilot.',
          'Set Weapons:','machine guns x2','gunpods x1'],
 'astraea':['Special steam-powered','fighter uses 2 gunpods','simultaneously.',
            'Equip both gunpods','differently for a myriad','of fighting techniques.',
            'Set Weapons:','machine guns x1','gunpods x2'],
 'arm':['Manipulator : Standard issue. Seizes gunpods',
        'from incapacitated enemies and equips them.'],
}
ARM_WORDS=[
 {'text':'Dafoe','key':'41E75A55-678CA3BD','uv':[80,80,104,88]},
 {'text':'Mark','key':'AAE3C8F2-678CA3BD','uv':[96,88,115,96]},
 {'text':'IV','key':'7D2C7E3C-678CA3BD','uv':[121,72,128,80]},
 {'text':'20mm GUN','key':'3DA22883-678CA3BD','uv':[80,104,126,112]},
]
ARM_REGISTRATION={
 'Dafoe':[(0,6,'D'),(6,11,'a'),(11,15,'f'),(15,20,'o'),(20,24,'e')],
 'Mark':[(0,6,'M'),(6,11,'a'),(11,15,'r'),(15,19,'k')],
 '20mm GUN':[(0,5,'2'),(5,11,'0'),(11,18,'m'),(18,25,'m'),(25,28,' '),
             (28,34,'G'),(34,40,'U'),(40,46,'N')],
 # The shared/faint I/V material cannot establish individual source ownership.
 # Author this confirmed Roman numeral as one vector word in its exact quad.
 'IV':[(0,7,'IV')],
}

def sha(data):return hashlib.sha256(data).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(Path(path).read_bytes())}
def signed(value,bits):
 value&=(1<<bits)-1
 return value-(1<<bits) if value&(1<<(bits-1)) else value

def parse_frame(frame):
 offset=[0,0];area=[0,0,1023,511];page=0;window=0;draws=[]
 for entry in frame['entries']:
  op=int(entry['op'],16);w=[int(x,16) for x in entry['w']]
  if op==0xE1:page=w[0]&0x1ff
  elif op==0xE2:window=w[0]&0xfffff
  elif op==0xE3:area[:2]=[w[0]&1023,(w[0]>>10)&511]
  elif op==0xE4:area[2:]=[w[0]&1023,(w[0]>>10)&511]
  elif op==0xE5:offset=[signed(w[0],11),signed(w[0]>>11,11)]
  elif (op&0xfc)==0x2c and len(w)>=9:
   page=(w[4]>>16)&0x1ff;clut=w[2]>>16
   uvs=[(w[n]&255,(w[n]>>8)&255) for n in (2,4,6,8)]
   vertices=[(signed(w[n],16)+offset[0],signed(w[n]>>16,16)+offset[1]) for n in (1,3,5,7)]
   x=min(p[0] for p in vertices);y=min(p[1] for p in vertices)
   draws.append({'frame':frame['frame'],'seq':entry['seq'],'op':entry['op'],
                 'page_xy_words':[(page&15)*64,((page>>4)&1)*256],
                 'depth':(page>>7)&3,'clut_xy_words':[(clut&63)*16,clut>>6],
                 'source_uv_half_open':[min(p[0] for p in uvs),min(p[1] for p in uvs),max(p[0] for p in uvs),max(p[1] for p in uvs)],
                 'uv_sampling_convention':'Axis-aligned font quad endpoint is exclusive; matches actual renderer sampled limits',
                 'draw_xy':[x,y],'area':area.copy(),'display_local_xy':[x-area[0],y-area[1]],
                 'vertices':vertices,'uv_vertices':uvs,
                 'packet_address':entry['src'],'submission_pc':entry['pc'],'texture_window':window})
  elif (op&0xe0)==0x60 and op&4:
   size=(op>>3)&3
   if size==0:
    if len(w)<4:continue
    width,height=w[3]&0xffff,w[3]>>16
   elif size==2:width=height=8
   elif size==3:width=height=16
   else:width=height=1
   x=signed(w[1],16)+offset[0];y=signed(w[1]>>16,16)+offset[1]
   u,v=w[2]&255,(w[2]>>8)&255;clut=w[2]>>16
   draws.append({'frame':frame['frame'],'seq':entry['seq'],'op':entry['op'],
                 'page_xy_words':[(page&15)*64,((page>>4)&1)*256],
                 'depth':(page>>7)&3,'clut_xy_words':[(clut&63)*16,clut>>6],
                 'source_uv_half_open':[u,v,u+width,v+height],
                 'draw_xy':[x,y],'area':area.copy(),'display_local_xy':[x-area[0],y-area[1]],
                 'packet_address':entry['src'],'submission_pc':entry['pc'],
                 'texture_window':window})
 return draws

def proof_frames(proof):
 return proof.get('gp0_frames',proof.get('frames',[]))

def read_proof(scene,path):
 proof=json.loads(path.read_bytes());frames=proof_frames(proof)
 if proof.get('scene')!=scene or proof.get('visual_confirmed') is not True:
  raise ValueError('The requested scene must have explicit composed-image confirmation')
 if proof.get('ram_writes') is not False or proof.get('assisted') is not False:
  raise ValueError('This source corpus requires natural, unassisted menu states')
 if not frames:raise ValueError('A full GP0 frame bracket is required: '+str(path))
 shot=proof.get('capture',proof.get('screenshot'))
 if not shot:raise ValueError('A linked visually confirmed composed screenshot is required')
 if sha(Path(shot['path']).read_bytes())!=shot['sha256']:raise ValueError('Screenshot hash changed')
 vram_path=Path(proof['vram']['path']);vram=vram_path.read_bytes()
 if proof['vram'].get('sha256') and sha(vram)!=proof['vram']['sha256']:
  raise ValueError('VRAM bracket hash changed')
 page_bytes=b''.join(vram[((256+y)*1024+960)*2:((256+y)*1024+1024)*2] for y in range(256))
 palette_bytes=vram[(482*1024+272)*2:(482*1024+288)*2]
 actual_key=f'{zlib.crc32(page_bytes):08X}-{zlib.crc32(palette_bytes):08X}'
 if actual_key!=KEY:raise ValueError('Current captured glyph source/palette differs: '+actual_key)
 # Use the central complete frame once: repeats are independent witnesses, not
 # three copies of every printed character.
 frame=frames[len(frames)//2];draws=parse_frame(frame)
 glyphs=[d for d in draws if d['page_xy_words']==[960,256] and d['depth']==0
         and d['clut_xy_words']==[272,482] and d['texture_window']==0
         and 0<d['source_uv_half_open'][2]-d['source_uv_half_open'][0]<=12
         and 0<d['source_uv_half_open'][3]-d['source_uv_half_open'][1]<=12]
 glyphs=[d for d in glyphs if (d['display_local_xy'][1]>=170 if scene=='arm'
                              else 65<=d['display_local_xy'][1]<230 and d['display_local_xy'][0]<145)]
 native=Image.open('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements/'+KEY+'.png').convert('RGBA')
 spaces=[d for d in glyphs if native.crop(tuple(d['source_uv_half_open'])).getchannel('A').getbbox() is None]
 glyphs=[d for d in glyphs if d not in spaces]
 lines=[]
 for d in sorted(glyphs,key=lambda d:(d['display_local_xy'][1],d['display_local_xy'][0])):
  # Known font offsets/punctuation may differ by one native row. Larger
  # disagreements stay visible as separate lines instead of being guessed.
  y=d['display_local_xy'][1]
  candidates=[line for line in lines if abs(line['y']-y)<=1]
  if candidates:candidates[0]['draws'].append(d)
  else:lines.append({'y':y,'draws':[d]})
 lines.sort(key=lambda line:line['y']);expected=TRANSCRIPTS[scene]
 mapped=[];ambiguities=[]
 if len(lines)!=len(expected):ambiguities.append({'reason':'line_count_mismatch','expected':len(expected),'observed':len(lines)})
 for index,line in enumerate(lines):
  ordered=sorted(line['draws'],key=lambda d:d['display_local_xy'][0]);text=expected[index] if index<len(expected) else None
  letters=[c for c in text if c!=' '] if text else []
  if len(letters)!=len(ordered):
   ambiguities.append({'reason':'glyph_count_mismatch','line_index':index,'text':text,'expected':len(letters),'observed':len(ordered),
                       'draws':ordered});continue
  assignments=[]
  for c,d in zip(letters,ordered):
   item={'character':c,'scene':scene,'line_index':index,'confirmed_text':text,**d}
   mapped.append(item);assignments.append(item)
  line.update(text=text,assignments=assignments)
 return {'scene':scene,'proof':ref(path),'screenshot':shot,'frame':frame['frame'],'lines':lines,
         'captured_source':{'vram':ref(vram_path),'key':actual_key,'raw_sha256':sha(page_bytes),'clut_sha256':sha(palette_bytes)},
         'assignments':mapped,'spaces':spaces,'ambiguities':ambiguities,'all_source_draws':draws}

def vector_glyph(character,rect,native,font):
 """Fresh vector strokes; native texels supply registration metrics only."""
 scale=16;x0,y0,x1,y1=rect;w=(x1-x0)*scale;h=(y1-y0)*scale
 crop=np.asarray(native.crop(tuple(rect)).convert('RGBA'))
 strength=np.max(crop[:,:,:3],axis=2)
 brightest=int(strength[crop[:,:,3]>0].max()) if np.any(crop[:,:,3]>0) else 0
 primary=crop[:,:,3]>0
 yy,xx=np.where(primary)
 if not len(xx):raise ValueError('No primary native face for proven character '+repr(character))
 # Metric extraction never becomes a new stroke silhouette. The TTF supplies
 # all contours/counters. A common7.125-native-pixel baseline and size148 fit
 # both ascenders and descenders without clipping their authored outlines.
 box=[int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1]
 mask=Image.new('L',(w,h));draw=ImageDraw.Draw(mask)
 baseline=BASELINE
 if character in ('i','l'):
  center=(box[0]+box[2])*scale/2;stroke=.58*scale
  top=(box[1]*scale if character=='l' else max(2*scale,box[1]*scale))
  draw.rounded_rectangle((center-stroke/2,top,center+stroke/2,baseline),radius=stroke/2,fill=255)
  if character=='i':
   radius=.34*scale;cy=(box[1]+.4)*scale
   draw.ellipse((center-radius,cy-radius,center+radius,cy+radius),fill=255)
 elif character=='-':
  cy=(box[1]+box[3])*scale/2;stroke=.58*scale
  draw.rounded_rectangle((box[0]*scale,cy-stroke/2,box[2]*scale,cy+stroke/2),radius=stroke/2,fill=255)
 elif character in ('.',':'):
  groups=[]
  for row in sorted(set(map(int,yy))):
   if groups and row==groups[-1][-1]+1:groups[-1].append(row)
   else:groups.append([row])
  if len(groups)!=(2 if character==':' else 1):raise ValueError('Ambiguous punctuation registration')
  radius=.48*scale;cx=(box[0]+box[2])*scale/2
  for group in groups:
   cy=(min(group)+max(group)+1)*scale/2
   draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=255)
 else:
  temporary=Image.new('L',(256,256));td=ImageDraw.Draw(temporary)
  td.text((24,160),character,font=font,fill=255,anchor='ls')
  inkbox=temporary.getbbox()
  if not inkbox:raise ValueError('Empty vector glyph '+repr(character))
  glyph=temporary.crop(inkbox)
  # Preserve the native alpha-footprint registration and each quad/advance. Horizontal
  # fitting alone accommodates the original proportional cells; vertical scale
  # and baseline are shared across all ordinary letters.
  target_width=max(scale//2,round(((box[2]-box[0])-.75 if box[2]-box[0]>2 else box[2]-box[0])*scale))
  glyph=glyph.resize((target_width,glyph.height),Image.Resampling.LANCZOS)
  top=baseline+inkbox[1]-160
  if top<0 or top+glyph.height>h:raise ValueError('Vector ascender/descender would be clipped: '+character)
  mask.paste(glyph,(box[0]*scale,top))
 pixels=np.asarray(mask).copy()
 # Categorical PSX coverage is derived from the new vector mask. RGB edge
 # coverage uses its own antialiasing, never a brightened native shadow ramp.
 rgba=np.zeros((h,w,4),np.uint8)
 rgba[:,:,:3]=np.rint(pixels[:,:,None].astype(np.float32)*248/255).astype(np.uint8)
 rgba[:,:,3]=np.where(pixels==0,0,np.where(pixels>=220,127,255)).astype(np.uint8)
 return rgba,{'native_alpha_footprint_registration_bbox':box,'native_maximum_tone_for_reference':brightest,'baseline_native':BASELINE/16,'font_size_authoring':FONT_SIZE,
              'new_vector_ink_bbox':list(mask.getbbox()) if mask.getbbox() else None,
              'shape_source':'Eco Sans Mono Regular vector outline or bounded narrow/punctuation override',
              'native_pixels_used_for':'registration metrics only; no native threshold becomes stroke coverage'}

def map_arm_words(scenes):
 arm=[scene for scene in scenes if scene['scene']=='arm']
 if len(arm)!=1:raise ValueError('Exactly one ARM source bracket is required')
 scene=arm[0];proof=json.loads(Path(scene['proof']['path']).read_bytes())
 vram=Path(proof['vram']['path']).read_bytes();records=[]
 source_dir=AUDIT/'menu-restoration/font-strip-candidate-v6/sources'
 for item in ARM_WORDS:
  matches=[draw for draw in scene['all_source_draws']
           if draw['page_xy_words']==[832,256] and draw['depth']==0
           and draw['clut_xy_words']==[256,493]
           and draw['source_uv_half_open']==item['uv'] and draw['texture_window']==0]
  if len(matches)!=1:raise ValueError('Missing or ambiguous exact ARM word quad: '+item['text'])
  row=item['uv'][1]
  raw=b''.join(vram[((256+row+y)*1024+832)*2:((256+row+y)*1024+896)*2] for y in range(8))
  palette=vram[(493*1024+256)*2:(493*1024+272)*2]
  actual=f'{zlib.crc32(raw):08X}-{zlib.crc32(palette):08X}'
  if actual!=item['key']:raise ValueError('ARM exact row source/palette changed: '+actual)
  if raw!=(source_dir/(actual+'.words.bin')).read_bytes():raise ValueError('ARM row alias raw bytes differ')
  if palette!=(source_dir/(actual+'.clut.bin')).read_bytes():raise ValueError('ARM row alias palette differs')
  records.append({**item,'draw':matches[0],'native_local_uv':[item['uv'][0],0,item['uv'][2],8],
                  'source':ref(source_dir/(actual+'.png')),'raw_sha256':sha(raw),'clut_sha256':sha(palette),
                  'ownership':'Exact word quad, proven by composed ARM image, full GP0 and current GPU-truth VRAM',
                  'internal_character_ownership':'Baked artwork has no individual character draw packets; registration is recorded separately'})
 return records

def vector_word(word,native,font):
 """Vector word art in exact quads; internal registration remains explicit."""
 scale=16;mask=Image.new('L',(native.width*scale,native.height*scale))
 # The source has a six-pixel optical face, lighter and smaller than the body.
 # These baked words share a screen line but do not expose character baselines.
 word_font=ImageFont.truetype(str(FONT),128);baseline=104
 registrations=[]
 for start,end,text in ARM_REGISTRATION[word['text']]:
  registrations.append({'text':text,'source_local_x_interval':[start,end],
                         'evidence':'Manually identified optical registration inside source-proven word quad; not a character draw address'})
  if text==' ':continue
  if text=='0':
   # The source numeral is an unslashed zero. The installed technical font's
   # slashed zero would be a visible identity change, so use an explicit oval.
   draw=ImageDraw.Draw(mask);inset=.35*scale
   draw.ellipse((start*scale+inset,baseline-5.7*scale,end*scale-inset,baseline),outline=255,width=10)
   continue
  if text=='IV':
   # The exact quad contains a plain narrow I followed by V. Keep it as one
   # authored word, with a simple stem instead of the font's wider serifed I.
   draw=ImageDraw.Draw(mask);draw.line((.6*scale,baseline-5.7*scale,.6*scale,baseline),fill=255,width=10)
   temporary=Image.new('L',(256,256));td=ImageDraw.Draw(temporary)
   td.text((24,160),'V',font=word_font,fill=255,anchor='ls');box=temporary.getbbox();glyph=temporary.crop(box)
   glyph=glyph.resize((round(4.7*scale),glyph.height),Image.Resampling.LANCZOS)
   top=baseline+box[1]-160
   if top<0 or top+glyph.height>mask.height:raise ValueError('Roman word contour would be clipped')
   mask.paste(glyph,(round(1.8*scale),top))
   continue
  temporary=Image.new('L',(512,256));draw=ImageDraw.Draw(temporary)
  draw.text((24,160),text,font=word_font,fill=255,anchor='ls')
  box=temporary.getbbox();glyph=temporary.crop(box)
  width=round((end-start-.75)*scale);glyph=glyph.resize((width,glyph.height),Image.Resampling.LANCZOS)
  top=baseline+box[1]-160;left=round((start+.25)*scale)
  if top<0 or top+glyph.height>mask.height or left+glyph.width>mask.width:
   raise ValueError('Baked word vector contour would be clipped: '+text)
  mask.paste(glyph,(left,top))
 pixels=np.asarray(mask);rgba=np.zeros((mask.height,mask.width,4),np.uint8)
 # Source palette 678CA3BD is entirely STP-set grayscale. Its maximum is160;
 # retain that tone and class, rather than promoting the art into white127.
 rgba[:,:,:3]=np.rint(pixels[:,:,None].astype(np.float32)*160/255).astype(np.uint8)
 rgba[:,:,3]=np.where(pixels>0,255,0).astype(np.uint8)
 return rgba,{'shape_source':'Fresh Eco Sans Mono Regular outlines, no source shadow/threshold coverage',
              'font_size_authoring':128,'optical_authored_baseline_native':baseline/16,
              'source_baseline':'Not individually encoded in baked GP0 quad; original optical baseline differs by word',
              'native_quad_geometry_and_screen_advance_preserved':True,
              'internal_registration':registrations,
              'ambiguities':['Source 2/0 faint edges overlap near global U85; internal split is optical registration',
                             'IV is retained as one word because the I/V source boundary is not independently provable'],
              'source_tone_maximum':160,'psx_nonclear_class':255}

def verify_candidate(output,negative_controls=False):
 """Check the immutable artifact against native proofs, parent RGBA and vectors."""
 manifest=json.loads((output/'manifest.json').read_bytes())
 def check_ref(item):
  if sha(Path(item['path']).read_bytes())!=item['sha256']:raise ValueError('Evidence hash changed: '+item['path'])
 for field in ('font','source_map','parent_candidate','native_source','preview'):check_ref(manifest[field])
 source=json.loads(Path(manifest['source_map']['path']).read_bytes())
 if source['uv_conflicts'] or source['unmapped_known_text_characters']:raise ValueError('Incomplete or conflicting English glyph ownership')
 if sorted(x['scene'] for x in source['scenes'])!=sorted(TRANSCRIPTS):raise ValueError('Missing required scene')
 rebuilt=[]
 for scene in source['scenes']:
  check_ref(scene['proof']);check_ref(scene['captured_source']['vram'])
  current=read_proof(scene['scene'],Path(scene['proof']['path']))
  if json.dumps(current['assignments'],sort_keys=True)!=json.dumps(scene['assignments'],sort_keys=True) or json.dumps(current['spaces'],sort_keys=True)!=json.dumps(scene['spaces'],sort_keys=True):
   raise ValueError('Saved character ownership differs from full GP0 source')
  if current['ambiguities']:raise ValueError('Ambiguous current source mapping')
  rebuilt.append(current)
 if json.dumps(map_arm_words(rebuilt),sort_keys=True)!=json.dumps(source['arm_words'],sort_keys=True):raise ValueError('ARM source word evidence differs')
 if len(manifest['files'])!=15 or len({x['key'] for x in manifest['files']})!=15:
  raise ValueError('Expected eleven coherent glyph outputs plus four exact ARM words')
 font=ImageFont.truetype(str(FONT),FONT_SIZE)
 native=Image.open(manifest['native_source']['path']).convert('RGBA')
 canonical_item=next(x for x in manifest['files'] if x['key']==KEY)
 canonical=np.asarray(Image.open(canonical_item['outputs']['pack']['path']).convert('RGBA'))
 glyph_mask=np.zeros((4096,4096),bool)
 for glyph in source['glyphs']:
  x0,y0,x1,y1=glyph['uv'];glyph_mask[y0*16:y1*16,x0*16:x1*16]=True
  expected,_=vector_glyph(glyph['character'],glyph['uv'],native,font)
  if not np.array_equal(canonical[y0*16:y1*16,x0*16:x1*16],expected):
   raise ValueError('Canonical glyph differs from fresh vector recipe: '+glyph['character'])
 checks=0;decoded={};parents={};masks={}
 for item in manifest['files']:
  check_ref(item['outputs']['pack']);check_ref(item['parent'])
  pixels=np.asarray(Image.open(item['outputs']['pack']['path']).convert('RGBA'))
  parent=np.asarray(Image.open(item['parent']['path']).convert('RGBA'))
  if pixels.shape!=parent.shape:raise ValueError('Output changed source geometry')
  if item['source_key']==KEY:
   if item['key']==KEY:mask=glyph_mask
   else:
    _,row,_,end=item['source_region'];mask=glyph_mask[row*16:end*16]
    if not np.array_equal(pixels[mask],canonical[row*16:end*16][mask]):
     raise ValueError('Alias differs from continuous canonical glyph field')
  else:
   word=next(w for w in source['arm_words'] if w['key']==item['key']);x0,y0,x1,y1=word['native_local_uv']
   mask=np.zeros(pixels.shape[:2],bool);mask[y0*16:y1*16,x0*16:x1*16]=True
   expected,_=vector_word(word,Image.open(word['source']['path']).convert('RGBA').crop((x0,y0,x1,y1)),font)
   if not np.array_equal(pixels[y0*16:y1*16,x0*16:x1*16],expected):raise ValueError('ARM word differs from vector recipe')
  if not np.array_equal(pixels[~mask],parent[~mask]):raise ValueError('Protected parent pixels changed: '+item['key'])
  if set(map(int,np.unique(pixels[:,:,3])))-{0,127,255}:raise ValueError('Non-categorical PSX alpha')
  decoded[item['key']]=pixels;parents[item['key']]=parent;masks[item['key']]=mask;checks+=1
 negative=[]
 if negative_controls:
  # These controls change rendered evidence in memory only. No PNG/proof or
  # parent is rewritten. They exercise protected logos and shared UV continuity.
  row_item=next(x for x in manifest['files'] if x['source_key']==KEY and x['key']!=KEY)
  key=row_item['key'];pixels=decoded[key].copy();mask=masks[key];outside=np.argwhere(~mask)[0];y,x=map(int,outside)
  pixels[y,x,0]^=1
  if np.array_equal(pixels[~mask],parents[key][~mask]):raise ValueError('Protected-pixel control was not detected')
  negative.append('Protected non-glyph corruption rejected')
  pixels=decoded[key].copy();y,x=map(int,np.argwhere(mask)[0]);pixels[y,x,0]^=1
  row=row_item['source_region'][1]
  if np.array_equal(pixels[mask],canonical[row*16:(row+8)*16][mask]):raise ValueError('Alias-continuity control was not detected')
  negative.append('Shared-glyph alias corruption rejected')
  changed=json.loads(json.dumps(rebuilt));changed[0]['all_source_draws']=[]
  # The actual word mapper must fail with the complete ARM source draws removed.
  next(s for s in changed if s['scene']=='arm')['all_source_draws']=[]
  try:map_arm_words(changed)
  except ValueError:negative.append('Missing ARM exact-word quad rejected')
  else:raise ValueError('Missing ARM source quad was accepted')
  try:vector_glyph('f',[40,32,44,33],native,font)
  except ValueError as error:
   if 'clipped' not in str(error):raise ValueError('Truncation control failed for an unrelated reason') from error
   negative.append('Truncated ascender rectangle rejected')
  else:raise ValueError('Clipped vector contour was accepted')
 receipt={'format':1,'at_utc':datetime.now(timezone.utc).isoformat(),'candidate':ref(output/'manifest.json'),
          'script':ref(Path(__file__)),'outcome':'PASS','source_scenes':len(rebuilt),'proven_glyphs':len(source['glyphs']),
          'exact_arm_word_quads':len(source['arm_words']),'output_pngs_verified':checks,'uv_ambiguities':0,
          'protected_outside_exact':True,'vector_recipe_reproduced_exact':True,'negative_controls':negative,
          'live_acceptance':'NOT RUN; isolated offline candidate only'}
 (output/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))

def build_vectors(source_map,base_candidate):
 if source_map['uv_conflicts'] or any(x['ambiguities'] for x in source_map['scenes']):
  raise ValueError('Ambiguous source ownership cannot be authored')
 manifest_path=OUT/'manifest.json'
 if manifest_path.exists():raise ValueError('Vector candidates are immutable')
 parent=json.loads(base_candidate.read_bytes());parents={Path(x['name']).stem:x for x in parent['files']}
 if KEY not in parents:raise ValueError('Parent lacks canonical description book')
 stock=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
 native_path=stock/(KEY+'.png');native=Image.open(native_path).convert('RGBA')
 raw=(stock/(KEY+'.words.bin')).read_bytes();clut=(stock/(KEY+'.clut.bin')).read_bytes()
 assert f'{zlib.crc32(raw):08X}'==KEY[:8] and f'{zlib.crc32(clut):08X}'==KEY[9:]
 baseline_path=Path(parents[KEY]['composed_path']);assert sha(baseline_path.read_bytes())==parents[KEY]['sha256']
 base=np.array(Image.open(baseline_path).convert('RGBA'));result=base.copy()
 selected=np.zeros(base.shape[:2],bool);vector_layer=np.zeros_like(base)
 font=ImageFont.truetype(str(FONT),FONT_SIZE);glyph_records=[]
 for glyph in source_map['glyphs']:
  rect=glyph['uv'];x0,y0,x1,y1=rect
  if not (0<=x0<x1<=256 and 0<=y0<y1<=128):raise ValueError('Proven glyph outside reviewed font book')
  pixels,metrics=vector_glyph(glyph['character'],rect,native,font)
  target=vector_layer[y0*16:y1*16,x0*16:x1*16]
  if np.any((target[:,:,3]>0)&(pixels[:,:,3]>0)):raise ValueError('Conflicting vector glyph footprints')
  ink=pixels[:,:,3]>0;target[ink]=pixels[ink]
  selected[y0*16:y1*16,x0*16:x1*16]=True
  glyph_records.append({**glyph,'metrics':metrics})
 result[selected]=vector_layer[selected]
 if not np.array_equal(result[~selected],base[~selected]):raise ValueError('Unbound canonical pixels changed')
 # Every alias shares the canonical authored glyph field, including descenders.
 # Its own protected logo/fill pixels remain exact to its own parent.
 font_manifest_path=AUDIT/'menu-restoration/font-strip-candidate-v6/manifest.json'
 font_manifest=json.loads(font_manifest_path.read_bytes());aliases=[]
 for item in font_manifest['files']:
  if not item['key'].endswith('B88C038E'):continue
  matches=[x for x in item.get('all_raw_matches',[]) if x['key']==KEY]
  row=item.get('raw_parent',{}).get('native_row')
  if row is None and item.get('base_key')==KEY:row=item.get('base_output_region',[None,None])[1]
  if row is None and len(matches)==1:row=matches[0]['native_row']
  if row is None or item['key'] not in parents:continue
  if row not in (32,40,48,56,64,72,80,88,96,112):continue
  aliases.append((item['key'],row))
 if len(aliases)!=10:raise ValueError('Expected all ten source-exact aliases')
 pack=OUT/'pack/einhander-texture-replacements';pack.mkdir(parents=True,exist_ok=True)
 (pack.parent/'Hashes.ini').write_text('');rows=[]
 def save(key,pixels,mask,parent_pixels,source_region,source_key=KEY):
  if not np.array_equal(pixels[~mask],parent_pixels[~mask]):raise ValueError('Unbound alias pixels changed: '+key)
  path=pack/(key+'.png');Image.fromarray(pixels).save(path)
  with Image.open(path) as decoded:assert decoded.convert('RGBA').tobytes()==pixels.tobytes()
  rows.append({'key':key,'outputs':{'pack':{'path':str(path),'sha256':sha(path.read_bytes()),'size':[pixels.shape[1],pixels.shape[0]]}},
               'source_key':source_key,'source_region':source_region,'parent':ref(Path(parents[key]['composed_path'])),
               'protected_outside_exact':True,'alpha_classes':list(map(int,np.unique(pixels[:,:,3]))),
               'actual_live_acceptance':False})
 save(KEY,result,selected,base,[0,0,256,256])
 for key,row in aliases:
  canonical=result[row*16:(row+8)*16];mask=selected[row*16:(row+8)*16]
  parent_pixels=np.array(Image.open(parents[key]['composed_path']).convert('RGBA'))
  pixels=parent_pixels.copy();pixels[mask]=canonical[mask]
  save(key,pixels,mask,parent_pixels,[0,row,256,row+8])
 arm_images={};arm_records=[]
 for word in source_map['arm_words']:
  key=word['key'];parent_path=Path(parents[key]['composed_path'])
  if sha(parent_path.read_bytes())!=parents[key]['sha256']:raise ValueError('ARM parent changed')
  parent_pixels=np.array(Image.open(parent_path).convert('RGBA'));pixels=parent_pixels.copy()
  u0,v0,u1,v1=word['native_local_uv'];word_native=Image.open(word['source']['path']).convert('RGBA').crop((u0,v0,u1,v1))
  word_pixels,metrics=vector_word(word,word_native,font)
  mask=np.zeros(pixels.shape[:2],bool);mask[v0*16:v1*16,u0*16:u1*16]=True
  pixels[v0*16:v1*16,u0*16:u1*16]=word_pixels
  save(key,pixels,mask,parent_pixels,word['uv'],key)
  arm_images[key]=word_pixels;arm_records.append({**word,'metrics':metrics})
 preview=Image.new('RGB',(1280,3200),(12,23,39));draw=ImageDraw.Draw(preview)
 y=20
 for scene in source_map['scenes']:
  draw.text((20,y),scene['scene']+' | rebuilt vectors at actual4x; original positions/advances',fill='white');y+=35
  minimum_y=min(a['display_local_xy'][1] for a in scene['assignments'])
  if scene['scene']=='arm':minimum_y=min(minimum_y,min(w['draw']['display_local_xy'][1] for w in source_map['arm_words']))
  maximum_y=minimum_y
  def paste_preview(source_pixels,xy):
   height,width=source_pixels.shape[:2];size=(width//4,height//4)
   im=Image.fromarray(source_pixels[:,:,:3]).resize(size,Image.Resampling.LANCZOS).convert('RGBA')
   alpha=Image.fromarray(np.where(source_pixels[:,:,3]>0,255,0).astype(np.uint8)).resize(size,Image.Resampling.NEAREST);im.putalpha(alpha)
   preview.paste(im,(int(xy[0]*4),y+int((xy[1]-minimum_y)*4)),im)
  for line in scene['lines']:
   if 'assignments' not in line:continue
   for assignment in line['assignments']:
    u0,v0,u1,v1=assignment['source_uv_half_open'];x=assignment['display_local_xy'][0]
    source_pixels=result[v0*16:v1*16,u0*16:u1*16]
    # Alpha127 is an opaque PSX class, not 50-percent opacity. Resize RGB and
    # categorical coverage independently; RGBA resize would premultiply the
    # class value and produce a misleading hollow/etched preview.
    paste_preview(source_pixels,assignment['display_local_xy'])
    maximum_y=max(maximum_y,assignment['display_local_xy'][1]+v1-v0)
  if scene['scene']=='arm':
   for word in source_map['arm_words']:
    paste_preview(arm_images[word['key']],word['draw']['display_local_xy'])
  y+=int((maximum_y-minimum_y)*4)+45
 if y>preview.height:raise ValueError('Proof preview would clip a source state')
 preview=preview.crop((0,0,1280,y))
 preview_path=OUT/'vector-description-actual4x.png';preview.save(preview_path)
 manifest={'format':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
           'method':'Fresh Eco Sans Mono Regular vector contours within exact English-to-GP0 glyph rectangles; no source-tone threshold used as stroke shape',
           'font':ref(FONT),'font_size_authoring':FONT_SIZE,'baseline_native':BASELINE/16,
           'source_map':ref(OUT/'source-map.json'),'parent_candidate':ref(base_candidate),
           'native_source':ref(native_path),'native_words_sha256':sha(raw),'native_clut_sha256':sha(clut),
           'glyph_records':glyph_records,'arm_word_records':arm_records,'files':rows,'asset_count':len(rows),
           'preview':ref(preview_path),'source_alias_continuity_exact_within_mapped_glyphs':True,
           'protected_alias_logos_fills_keep_their_own_parent_rgba':True,'game_actions':0,'production_installed':False,
           'unmapped_characters':source_map['unmapped_known_text_characters'],
           'remaining':['Actual settled fighter and ARM state replay, readability/counter/descender review at window4x and2160p',
                        'Baked ARM word quads are source-proven; internal character registration is visually identified rather than individual draw ownership',
                        'Any character absent from the exact proof corpus remains unchanged/unverified']}
 manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'manifest':str(manifest_path),'asset_count':len(rows),'live_verified':False}))

def main():
 global OUT
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--proof',action='append',default=[],help='scene=full-bracket.json; scene is mkii/mkiii/astraea/arm')
 parser.add_argument('--output',type=Path,default=OUT)
 parser.add_argument('--verify',action='store_true',help='Verify an immutable candidate without rewriting evidence or assets')
 parser.add_argument('--negative-controls',action='store_true',help='Also require independent corruption controls to fail')
 parser.add_argument('--build',action='store_true');parser.add_argument('--base-candidate',type=Path,
     default=AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9/candidate.json')
 args=parser.parse_args()
 OUT=args.output.resolve()
 if args.verify:
  verify_candidate(OUT,args.negative_controls);return
 if (OUT/'manifest.json').exists():raise ValueError('Immutable candidate already exists; use --verify or a new --output')
 if not args.proof:raise ValueError('Provide complete visually confirmed GP0/VRAM proof brackets')
 scenes=[]
 for item in args.proof:
  scene,name=item.split('=',1)
  if scene not in TRANSCRIPTS:raise ValueError('Unknown scene: '+scene)
  scenes.append(read_proof(scene,Path(name)))
 if sorted(scene['scene'] for scene in scenes)!=sorted(TRANSCRIPTS):
  raise ValueError('Exactly one complete bracket for each of the four known text states is required')
 by_uv=defaultdict(set);by_char=defaultdict(set)
 for scene in scenes:
  for assignment in scene['assignments']:
   uv=tuple(assignment['source_uv_half_open']);by_uv[uv].add(assignment['character']);by_char[assignment['character']].add(uv)
 conflicts=[{'uv':list(uv),'characters':sorted(chars)} for uv,chars in by_uv.items() if len(chars)!=1]
 OUT.mkdir(parents=True,exist_ok=True)
 source_map={'format':1,'at_utc':datetime.now(timezone.utc).isoformat(),'font':ref(FONT),
             'scenes':scenes,'uv_conflicts':conflicts,
             'glyphs':[{'character':next(iter(chars)),'uv':list(uv)} for uv,chars in sorted(by_uv.items()) if len(chars)==1],
             'unmapped_known_text_characters':sorted(set(''.join(''.join(v) for v in TRANSCRIPTS.values()))-set(by_char)-{' '}),
             'limitations':['English joins require complete settled frames and exact nonspace glyph counts; mismatches are not guessed',
                            'Transparent SPACE quads are identified from native alpha; draw coordinates preserve all whitespace advances',
                            'Only exact mapped source rectangles may change; all unrelated logos/fills remain protected']}
 source_map['arm_words']=map_arm_words(scenes)
 (OUT/'source-map.json').write_text(json.dumps(source_map,indent=2)+'\n')
 print(json.dumps({'source_map':str(OUT/'source-map.json'),'glyphs':len(source_map['glyphs']),
                   'conflicts':conflicts,'ambiguities':[[{k:v for k,v in a.items() if k!='draws'} for a in x['ambiguities']] for x in scenes],
                   'unmapped':source_map['unmapped_known_text_characters']}))
 if args.build:build_vectors(source_map,args.base_candidate)

if __name__=='__main__':main()
