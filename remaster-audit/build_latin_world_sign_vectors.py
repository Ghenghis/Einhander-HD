"""Author bounded Latin city signs and all32observed RISEpalette phases.

Raw/CLUT/validity/PNG checks and actual source-query UVs bind each sign.
The photograph bank and all nonLatin signs remain protected. New4096pages
preserve every outside-ROI pixel exactly to the nearest2x2048parent.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from build_three_asset_proof import verify_stock
from build_results_vector_candidate import sha, ref, load, pixels, write, require

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
STREAM=AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9/native-v9-world-gameover-results/capture.jsonl'
DEFAULT_OUT=AUDIT/'menu-restoration/latin-world-sign-vector-candidate-v1'
FONTS={name:Path('C:/Windows/Fonts')/file for name,file in {
 'condensed':'bahnschrift.ttf','italic':'SourceSansPro-BlackItalic.ttf','sans':'SourceSansPro-Bold.ttf',
 'serif':'times.ttf','slab':'georgiab.ttf'}.items()}
SCALE=16
FIXED=[('combat','31214B41-1F9C3DA0',[128,0,192,32]),
 ('parts','31214B41-9EAAA5BD',[156,32,192,56]),
 ('heh','31214B41-5663458B',[192,0,256,32]),
 ('legend','31214B41-1C8E76AE',[192,56,256,80])]

def decode_palette(clut):
 w=np.frombuffer(clut,dtype='<u2');return np.stack(((w&31)*8,((w>>5)&31)*8,((w>>10)&31)*8,
  np.where(w==0,0,np.where(w&32768,255,127))),1).astype(np.uint8)

def type_mask(text,box,size,font_name='sans'):
 x0,y0,x1,y1=box;mask=Image.new('L',size);f=ImageFont.truetype(str(FONTS[font_name]),600)
 if font_name=='condensed':f.set_variation_by_axes([650,75])
 temp=Image.new('L',(8192,1200));draw=ImageDraw.Draw(temp);draw.text((40,800),text,font=f,fill=255,anchor='ls')
 bounds=temp.getbbox();require(bounds is not None,'Empty vector text')
 glyph=temp.crop(bounds).resize((round((x1-x0)*SCALE),round((y1-y0)*SCALE)),Image.Resampling.LANCZOS)
 mask.paste(glyph,(round(x0*SCALE),round(y0*SCALE)));return mask

def shape(size,kind,coords,width=1):
 mask=Image.new('L',size);d=ImageDraw.Draw(mask);points=[tuple(round(v*SCALE) for v in p) for p in coords]
 if kind=='polygon':d.polygon(points,fill=255)
 elif kind=='line':d.line(points,fill=255,width=round(width*SCALE),joint='curve')
 elif kind=='rectangle':d.rectangle((*points[0],*points[1]),outline=255,width=round(width*SCALE))
 return mask

class Sign:
 def __init__(self,width,height,palette,background):
  self.size=(width*SCALE,height*SCALE);self.palette=palette
  self.rgb=np.empty((height*SCALE,width*SCALE,3),np.float32);self.rgb[:]=palette[background,:3]
  self.alpha=np.full((height*SCALE,width*SCALE),palette[background,3],np.uint8)
 def paint(self,mask,code,strength=1):
  a=np.asarray(mask,dtype=np.float32)/255*strength;a=np.clip(a,0,1)
  self.rgb=self.rgb*(1-a[:,:,None])+self.palette[code,:3]*a[:,:,None]
  active=a>1/255;self.alpha[active]=self.palette[code,3]
 def field(self,coverage,code,strength=1):
  self.paint(Image.fromarray(np.rint(np.clip(coverage*strength,0,1)*255).astype(np.uint8)),code)
 def rgba(self):
  return np.dstack((np.rint(np.clip(self.rgb,0,255)).astype(np.uint8),self.alpha))

def neon(sign,mask,face,edge,shadow=None,glow=None,stroke=.45):
 """Light only freshly authored vector contours; no nativepixel smoothing."""
 if glow is not None:sign.paint(mask.filter(ImageFilter.GaussianBlur(SCALE*.6)),glow,.45)
 if shadow is not None:
  shifted=Image.new('L',mask.size);shifted.paste(mask,(round(.45*SCALE),round(.55*SCALE)))
  sign.paint(shifted,shadow,.85)
 outer=mask.filter(ImageFilter.MaxFilter(round(stroke*SCALE)*2+1));sign.paint(outer,edge)
 sign.paint(mask,face)
 # A compact upper-facing bevel supplies depth without erasing stroke cores.
 shifted=Image.new('L',mask.size);shifted.paste(mask,(0,3))
 rim=np.maximum(np.asarray(mask,dtype=np.int16)-np.asarray(shifted,dtype=np.int16),0).astype(np.uint8)
 sign.paint(Image.fromarray(rim),face,.6)

def rise(palette):
 s=Sign(64,32,palette,15);mask=type_mask('RISE',(1.5,8,47.8,26),s.size,'italic')
 # Keep the original palette's green/gold face roles; cycling all32CLUTs
 # changes colors using identical newly authored geometry.
 neon(s,mask,5,3,shadow=1,glow=2,stroke=.35)
 top=Image.new('L',s.size);top.paste(mask,(0,3));rim=np.maximum(np.asarray(mask,dtype=np.int16)-np.asarray(top,dtype=np.int16),0).astype(np.uint8)
 s.paint(Image.fromarray(rim),9,.7)
 arrow=shape(s.size,'polygon',[(48,6.8),(63,16.1),(48,26.5),(48,22.1),(57.1,16.1),(48,11.1)])
 s.paint(arrow.filter(ImageFilter.GaussianBlur(.6*SCALE)),10,.55);s.paint(arrow,14)
 inset=shape(s.size,'line',[(49,8),(60.7,16.1),(49,24.7)],width=.65);s.paint(inset,12,.5)
 return s.rgba(),{'wording':'RISE >','style':'SourceSansProBlackItalic green/gold face and cyan arrow; original palette roles5/3/1/2/9 and14/10/12',
  'geometry':'Fresh vectorword, bounded chevron polygon and narrow new contour lighting; no original raster contour retained'}

def combat(palette):
 s=Sign(64,32,palette,15);yy,xx=np.mgrid[0:32*SCALE,0:64*SCALE].astype(np.float32);xx/=SCALE;yy/=SCALE
 # The original free middleband locates the four brightest orbtexels at
 # mean(30.5,15.5). Reconstruct that same abstract light rather than textblur.
 radius=np.sqrt(((xx-30.5)/19.0)**2+((yy-15.5)/10.8)**2)
 for code,r in [(14,1.15),(13,1.0),(12,.87),(11,.74),(10,.60),(9,.48),(7,.35),(6,.25),(3,.16),(2,.09)]:
  s.field(np.clip((r-radius)*12,0,1),code)
 for x,y,code in [(1,0,5),(10,1,8),(22,0,5),(1,22,5),(63,27,8),(56,30,5),(9,31,8)]:
  s.paint(shape(s.size,'rectangle',[(x,y),(x+.3,y+.3)],width=.25),code)
 top=type_mask("it's all new!!",(1.2,2,62.7,11.5),s.size,'condensed')
 bottom=type_mask('COMBAT',(6.2,23,61.5,30.8),s.size,'slab')
 for mask in (top,bottom):
  neon(s,mask,1,5,shadow=8,glow=5,stroke=.55)
  # Original face0 is a silvery upper highlight; gold1 stays the main face.
  a=np.asarray(mask,dtype=np.float32)/255;ys=np.where(a.max(1)>0)[0];fraction=np.clip((ys[0]+(ys[-1]-ys[0])*.40-np.arange(a.shape[0]))/SCALE,0,1)
  s.field(a*fraction[:,None],0,.85)
 dash=shape(s.size,'line',[(0,27.5),(8,27.5)],width=.75);s.paint(dash,1)
 return s.rgba(),{'wording':"it's all new!! / COMBAT",'style':'Condensed bold headline, compact magenta rim/purple depth, serif goldCOMBATface and source-registered redorb',
  'orb_center_native':[30.5,15.5],'orb_source_evidence':'Four nativeindex1hottexels in the unobstructed middleband13..21 average30.5/15.5; original poster owns the complete64x32ROI'}

def parts(palette):
 s=Sign(36,24,palette,0);welcome=type_mask('Welcom!!',(.5,1.1,35.7,9.4),s.size,'sans')
 neon(s,welcome,11,12,shadow=14,glow=None,stroke=.18)
 mask=type_mask('parts',(.8,12,35.2,22.5),s.size,'sans')
 outer=mask.filter(ImageFilter.MaxFilter(19));s.paint(outer.filter(ImageFilter.GaussianBlur(5)),5,.45);s.paint(outer,1)
 s.paint(mask,0)
 inner=mask.filter(ImageFilter.MinFilter(11));rim=np.maximum(np.asarray(mask,dtype=np.int16)-np.asarray(inner,dtype=np.int16),0).astype(np.uint8)
 s.paint(Image.fromarray(rim),3,.75)
 return s.rgba(),{'wording':'Welcom!! / parts','wording_note':'Native word is Welcom!! without a final e; preserved exactly instead of silently correcting the original sign',
  'style':'Compact bold blue Welcom!! and rounded green outlined parts; nonLatin magenta block to the left is outside theROI'}

def heh(palette):
 s=Sign(64,32,palette,15);yy,xx=np.mgrid[0:32*SCALE,0:64*SCALE].astype(np.float32);xx/=SCALE;yy/=SCALE
 beam=np.exp(-((xx-(5+yy*1.05))/7)**2);s.field(beam,8,.85);s.field(beam**3,7,.5)
 s.paint(shape(s.size,'rectangle',[(1,1),(63,31)],width=.65),0)
 s.paint(shape(s.size,'rectangle',[(2,2),(62,30)],width=.25),4)
 for text,box in [('HEH-HEH,',(5,5,60.5,13.8)),('WELCOME',(4,20,60.5,28.7))]:
  mask=type_mask(text,box,s.size,'serif');s.paint(mask,0)
 return s.rgba(),{'wording':'HEH-HEH, / WELCOME','style':'Source-serif cyan lettering, continuous doubleborder and original diagonalblue reflection direction'}

def legend(palette):
 s=Sign(64,24,palette,15);yy,xx=np.mgrid[0:24*SCALE,0:64*SCALE].astype(np.float32);xx/=SCALE;yy/=SCALE
 path=31+3*np.sin((yy-10)*.25);cloud=np.exp(-((xx-path)/9)**2-((yy-12)/17)**2);s.field(cloud,8,.6);s.field(cloud**2,6,.75)
 ell=shape(s.size,'polygon',[(1,1),(3.4,1),(3.4,10.5),(11.6,10.5),(11.6,12.2),(1,12.2)])
 neon(s,ell,1,3,shadow=10,stroke=.18)
 for text,box in [('EGEND OF',(5.8,1.2,51.7,9.6)),('SUPER POWERS',(1,14.2,62.8,22.6))]:
  mask=type_mask(text,box,s.size,'condensed');neon(s,mask,1,3,shadow=10,stroke=.22)
 points=[]
 for n in range(10):
  angle=-np.pi/2+n*np.pi/5;r=4.0 if n%2==0 else 1.8;points.append((58+np.cos(angle)*r,5.7+np.sin(angle)*r))
 star=shape(s.size,'polygon',points);neon(s,star,1,3,shadow=10,stroke=.18)
 return s.rgba(),{'wording':'LEGEND OF / SUPER POWERS','style':'Source-condensed goldglyphs, enlarged leadingL, fivepointgoldstar and deepblueabstractlight field'}

RENDER={'rise':rise,'combat':combat,'parts':parts,'heh':heh,'legend':legend}

def plan():
 queue={r['key']:r for r in load(QUEUE)['assets'] if r.get('source_verified')};parent=load(PARENT);parents={r['name'][:-4]:r for r in parent['files']}
 data=STREAM.read_bytes();records=[json.loads(l) for l in data.splitlines() if l]
 events=[(n,r) for n,r in enumerate(records,1) if r.get('event') in ('source_draw_query_matched','replacement_gl_draw_submitted')]
 rise_keys=sorted({r['key'] for n,r in events if r.get('key','').startswith('FD81C3C7-') and
  (u:=r.get('uv_bounds')) and u[0] in (64,65) and u[1]==128 and 155<=u[3]<=159})
 require(len(rise_keys)==32,'ObservedRISEpalette corpus changed; no silent omission allowed')
 work=FIXED+[('rise',key,[64,128,128,160]) for key in rise_keys];items=[]
 for kind,key,roi in work:
  require(key in queue and key in parents,'Source/currentparent key missing: '+key)
  source=Path(queue[key]['source']);meta,raw,clut=verify_stock(source.parent,key)
  receipts=[]
  for n,r in events:
   if r.get('key')!=key:continue
   uv=r.get('uv_bounds',[0,0,0,0]);x0,y0,x1,y1=roi
   # Parts'actual quad includes the protectednonLatin leftblock; sampledUV
   # overlap is enough for sourcebinding, never proof of every visible texel.
   if uv[0]<x1 and uv[2]>=x0 and uv[1]<y1 and uv[3]>=y0:
    receipts.append({'line':n,**{f:r.get(f) for f in ('event','key','frame','host_mono_ms','page_xy','clut_xy','uv_bounds','xy','semi','not_visibility_proof','cpu_vram_may_be_stale')}})
  require(receipts,'No actual source/draw witness for signROI: '+key)
  items.append({'kind':kind,'key':key,'roi':roi,'source':source,'metadata':meta,'raw':raw,'clut':clut,'parent':parents[key],'receipts':receipts})
 return items,{'path':str(STREAM),'sha256':hashlib.sha256(data).hexdigest()}

def build(output):
 require(not output.exists(),'Choose a new immutable output directory');items,stream=plan()
 output.mkdir(parents=True);pack=output/'pack/einhander-texture-replacements';pack.mkdir(parents=True);(pack.parent/'Hashes.ini').write_text('')
 rows=[];previews=[];masters={}
 for item in items:
  key=item['key'];roi=item['roi'];parent_path=Path(item['parent']['composed_path']);require(sha(parent_path)==item['parent']['sha256'],'Parent changed')
  before=pixels(parent_path);require(before.shape==(2048,2048,4),'Expected current8xworld source')
  baseline=np.repeat(np.repeat(before,2,0),2,1);after=baseline.copy();palette=decode_palette(item['clut'])
  patch,recipe=RENDER[item['kind']](palette);x0,y0,x1,y1=roi
  require(patch.shape==((y1-y0)*16,(x1-x0)*16,4),'Signrecipe dimensions differ')
  after[y0*16:y1*16,x0*16:x1*16]=patch
  # OutsideROI comparison must include every channel, including PSXclasses.
  changed=np.any(after!=baseline,axis=2);allowed=np.zeros((4096,4096),bool);allowed[y0*16:y1*16,x0*16:x1*16]=True
  require(not np.any(changed&~allowed),'Sign escaped sourceROI')
  target=pack/(key+'.png');Image.fromarray(after).save(target,compress_level=3);require(np.array_equal(pixels(target),after),'PNG roundtrip failed')
  rows.append({'key':key,'kind':item['kind'],'parent':ref(parent_path),'parent_resize':'Nearest2x integer projection only; no filtering/new detail outsideROI',
   'allow_integer_resolution_increase':True,'outputs':{'pack':{**ref(target),'size':[4096,4096]}},'selected_native_regions':[roi],
   'recipe':recipe,'source_archives':[ref(item['source'].with_suffix(s)) for s in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json')],
   'source_metadata':item['metadata'],'actual_source_draw_receipts':item['receipts'],'protected_outside_exact_to_nearest2x_parent':True,
   'alpha_classes':list(map(int,np.unique(patch[:,:,3]))),'live_acceptance':'NOT RUN'})
  if item['kind']!='rise' or key in ('FD81C3C7-24425A14','FD81C3C7-6EB1953F','FD81C3C7-CE46E1E1'):
   old=baseline[y0*16:y1*16,x0*16:x1*16];previews.append((item['kind']+' '+key,old,patch))
  print(json.dumps({'key':key,'kind':item['kind'],'output':'PASS SOURCE/PNG/BOUNDS'}),flush=True)
 preview(output,previews);shutil.copyfile(__file__,output/'build-source.py')
 manifest={'format':1,'contract':'latin-world-sign-vectors-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
  'parent_candidate':ref(PARENT),'source_queue':ref(QUEUE),'draw_stream':stream,'builder':ref(Path(__file__)),
  'fonts':{k:ref(v) for k,v in FONTS.items()},'files':rows,'asset_count':len(rows),'semantic_sign_designs':5,
  'RISE_observed_palette_variants':32,'method':'Fresh vector letterforms and source-registered compact lighting within semantic signboards; originalCLUTroles reused across actual32phaseRISEsources',
  'allow_integer_resolution_increase':True,'production_installed':False,'game_actions':0,'live_acceptance':'NOT RUN',
  'limits':['OriginalnonLatinblocks and photographbanks remain untouched; no wholeworld/art completion asserted.',
   'RISE32CLUTs are actual observed phases; sampledlogs do not prove every temporal transition or fullcycle ordering.',
   'AlloutsideROIcontent is exact nearest2xparent, representing no new authored detail outside the specific signs.',
   'Actual near/far/palette/motion/2160pquality and cache/pacing replay remain required.',
   'STAR,otherLatin/nonLatinsigns and all unassigned worldcomponents remain open.']}
 write(output/'manifest.json',manifest);verify(output)

def preview(output,items):
 width=1536;canvas=Image.new('RGB',(width,len(items)*430),(10,17,25));d=ImageDraw.Draw(canvas)
 for n,(label,before,after) in enumerate(items):
  y=n*430;d.text((8,y+5),label+' | parent / authored at source12x comparison; class127treatedopaque',fill='white')
  for x,a in ((0,before),(768,after)):
   rgb=Image.fromarray(a[:,:,:3]).resize((a.shape[1]*12//16,a.shape[0]*12//16),Image.Resampling.LANCZOS)
   alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
   canvas.paste(rgb,(x,y+32),alpha)
 canvas.save(output/'signs-before-after-source12x.png')

def verify(output):
 m=load(output/'manifest.json')
 for field in ('parent_candidate','source_queue','builder'):require(sha(m[field]['path'])==m[field]['sha256'],'Input changed: '+field)
 for font in m['fonts'].values():require(sha(font['path'])==font['sha256'],'Font changed')
 items,stream=plan();require(stream==m['draw_stream'],'Drawsource stream changed');planned={i['key']:i for i in items};count=0
 for row in m['files']:
  item=planned[row['key']];out=row['outputs']['pack'];require(sha(out['path'])==out['sha256'],'Outputhash changed');require(sha(row['parent']['path'])==row['parent']['sha256'],'Parenthash changed')
  for source in row['source_archives']:require(sha(source['path'])==source['sha256'],'Sourcearchive changed')
  baseline=np.repeat(np.repeat(pixels(row['parent']['path']),2,0),2,1);actual=pixels(out['path']);x0,y0,x1,y1=item['roi']
  allowed=np.zeros((4096,4096),bool);allowed[y0*16:y1*16,x0*16:x1*16]=True
  require(np.array_equal(actual[~allowed],baseline[~allowed]),'OutsideROI differs from exactnearest2xparent')
  expected,recipe=RENDER[item['kind']](decode_palette(item['clut']))
  require(recipe==row['recipe'] and np.array_equal(actual[y0*16:y1*16,x0*16:x1*16],expected),'Signrecipe not reproducible')
  require(set(map(int,np.unique(actual[:,:,3])))<={0,127,255},'NoncategoricalPSXalpha');count+=1
 receipt={'outcome':'PASS','output_pngs_verified':count,'semantic_sign_designs':5,'observed_RISE_palettes':32,
  'raw_clut_validity_decode_checked':True,'all_vector_recipes_reproduced_exact':True,
  'all_outside_ROI_RGBA_exact_nearest2x_parent':True,'photo_bank_and_nonLatin_not_modified':True,'live_acceptance':'NOT RUN'}
 write(output/'verification.json',receipt);print(json.dumps({'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUT);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:verify(a.output.resolve())
 else:build(a.output.resolve())
