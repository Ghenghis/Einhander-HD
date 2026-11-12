"""Explicit italic SQUARE logo vectors plus the verified fresh copyright date."""
from datetime import datetime,timezone
import hashlib,importlib.util,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PRIOR=AUDIT/'menu-restoration/copyright-vector-candidate-v1'
OUT=AUDIT/'menu-restoration/copyright-vector-candidate-v2'
REGION=(144,236,199,248)
# Custom outline geometry, registered optically to the actual SQUARE wordmark.
# Counter loops belong to Q, A and R. The mark is deliberately not TTF text.
GLYPHS=[
 ([('M',13,2),('C',10.6,.8,7.4,1.2,5.9,3.4),('C',4.9,5,6.3,6.2,8.4,6.2),('C',9.6,6.2,9.7,6.6,8.8,7.4),('C',7.5,8.7,5.5,8.6,3.7,7.4),('L',1.5,9),('C',4.4,10.5,8.3,10.3,10.6,8.2),('C',12.9,6.2,12.1,4.3,9.1,4.2),('C',7.5,4.1,7.4,3.7,8.1,3.2),('C',9.1,2.5,10.5,2.6,11.6,3.2),('Z',)],[]),
 ([('M',21,1.8),('C',15,1.2,11.3,3.8,10.9,6.8),('C',10.5,9.2,13.4,10,17.1,9.8),('L',25,9.8),('L',24,8),('L',21,8),('C',24,6.3,25.7,2.5,21,1.8),('Z',)],
  [[('M',19.6,3.5),('C',16.4,3.2,13.8,4.5,13.6,6.2),('C',13.3,7.4,15.4,7.9,17.1,7.7),('C',20.2,7.4,22.6,3.7,19.6,3.5),('Z',)]]),
 ([('M',25,2),('L',28,2),('L',25.9,7),('C',25.6,8,26.6,8.4,27.9,7.7),('L',31.2,2),('L',34.2,2),('L',30.5,8.4),('C',28.4,10.8,23.2,10.6,22.6,8.2),('Z',)],[]),
 ([('M',29.5,9.8),('L',36.5,2),('L',40.3,2),('L',40.7,9.8),('L',37.5,9.8),('L',37.3,7.7),('L',34.1,7.7),('L',32.4,9.8),('Z',)],
  [[('M',35.5,5.8),('L',37.2,3.9),('L',37.2,5.8),('Z',)]]),
 ([('M',41.5,2),('L',46.6,2),('C',49.2,2,50.1,3.5,48.7,5.2),('C',48,6.1,46.8,6.8,45.5,6.9),('L',47.4,9.8),('L',43.6,9.8),('L',41.8,7.1),('L',40.8,7.1),('L',39.6,9.8),('L',36.9,9.8),('Z',)],
  [[('M',43.2,3.8),('L',45.5,3.8),('C',47.2,3.8,46.2,5.2,44.4,5.2),('L',42.5,5.2),('Z',)]]),
 ([('M',49,2),('L',54.6,2),('L',53.6,4),('L',51,4),('L',50.6,5.1),('L',53.7,5.1),('L',52.7,7),('L',49.8,7),('L',49.3,8),('L',54,8),('L',53,9.8),('L',45.6,9.8),('Z',)],[]),
]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 if OUT.exists():raise ValueError('Existing candidates are immutable')
 hud=module(ROOT/'windows-x64/tools/build_hud_ui_candidate.py','square_logo_hud')
 vector=module(AUDIT/'build_gameover_vector_candidate.py','square_logo_vector')
 ss=2;factor=16*ss;size=(55*factor,12*factor);white=np.zeros((size[1],size[0]),np.uint8)
 for outer,holes in GLYPHS:
  glyph=Image.new('L',size);d=ImageDraw.Draw(glyph)
  def points(path):return [(round(x*factor),round(y*factor)) for x,y in vector.flatten(path)]
  d.polygon(points(outer),fill=255)
  for hole in holes:d.polygon(points(hole),fill=0)
  white=np.maximum(white,np.asarray(glyph))
 white=np.asarray(Image.fromarray(white).resize((55*16,12*16),Image.Resampling.LANCZOS))
 red=Image.new('L',size);rd=ImageDraw.Draw(red);rd.polygon([(round(x*factor),round(y*factor)) for x,y in [(31.3,10.2),(37.2,5.8),(38.7,10.2)]],fill=255)
 red=np.asarray(red.resize((55*16,12*16),Image.Resampling.LANCZOS))
 prior=json.loads((PRIOR/'manifest.json').read_bytes());rows=[]
 (OUT/'pack/einhander-texture-replacements').mkdir(parents=True);(OUT/'previews').mkdir();(OUT/'pack/Hashes.ini').write_text('');shutil.copy2(__file__,OUT/'build-source.py')
 for item in prior['assets']:
  key=item['key'];source=Path(item['source']['path']);m,raw,clut=hud.verify_stock(source.parent,key);palette=hud.palette_rgba(clut);native=palette[hud.decode_indices(raw,m)]
  previous=Path(item['outputs']['pack']['path']);before=np.array(Image.open(item['parent']['path']).convert('RGBA'));after=np.array(Image.open(previous).convert('RGBA'))
  wf=white.astype(np.float32)/255;rf=red.astype(np.float32)/255
  rgb=palette[0,:3][None,None,:]*wf[:,:,None]*(1-rf[:,:,None])+palette[9,:3][None,None,:]*rf[:,:,None]
  alpha=np.where(np.maximum(white,red)==0,0,np.where(np.maximum(white,red)>=230,palette[0,3],palette[1,3])).astype(np.uint8)
  alpha[red>=230]=palette[9,3]
  patch=np.dstack((np.rint(rgb).clip(0,255).astype(np.uint8),alpha));x0,y0,x1,y1=REGION;after[y0*16:y1*16,x0*16:x1*16]=patch
  selected=np.zeros(before.shape[:2],bool);selected[236*16:248*16,80*16:199*16]=True
  if not np.array_equal(before[~selected],after[~selected]):raise ValueError('Protected outside footer changed')
  if not set(np.unique(after[:,:,3]))<={0,127,255}:raise ValueError('Noncategorical coverage')
  target=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(after).save(target)
  if np.array(Image.open(target).convert('RGBA')).tobytes()!=after.tobytes():raise ValueError('PNG roundtrip mismatch')
  preview=Image.new('RGB',(800,3*100),(10,14,45));d=ImageDraw.Draw(preview)
  for n,(label,pixels,scale) in enumerate([('Native registered footer / actual6x',native,1),('Previous v10 date and SQUARE',before,16),('Fresh copyright/date + explicit SQUARE logo contours',after,16)]):
   a=pixels[236*scale:248*scale,80*scale:199*scale];v=a[:,:,:3].copy();v[a[:,:,3]==0]=[10,14,45]
   d.text((6,n*100+3),label,fill='white');preview.paste(Image.fromarray(v).resize((714,72),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS),(6,n*100+24))
  pp=OUT/'previews'/(key+'.png');preview.save(pp)
  rows.append({'key':key,'parent':item['parent'],'source':item['source'],'raw_sha256':hashlib.sha256(raw).hexdigest(),'clut_sha256':hashlib.sha256(clut).hexdigest(),'selected_native_regions':[[80,236,199,248]],'outputs':{'pack':{**ref(target),'size':[4096,4096]}},'preview':ref(pp),'protected_rgba_exact':True,'categorical_alpha':True,'png_roundtrip_exact':True})
 manifest={'schema_version':1,'contract':'copyright-square-explicit-vector-v2','created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':3,'production_installed':False,'game_actions':0,'tool':ref(__file__),'date_parent':ref(PRIOR/'manifest.json'),'exact_wording':'©1997/1998 SQUARE','method':'Source-registered explicit filled Bezier/polygon paths for stylized italic SQUARE letters, genuine Q/A/R counters and original palette9 red triangle. Fresh copyright/date from verified date parent. No generic font substituted for the SQUARE wordmark.','assets':rows,'live_verified':False,'remaining':['Independent SQUARE logo identity/fit review','Natural title fade/cold-load replacement and2160p footer review']}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'candidate':str(OUT),'assets':3,'source_crc':'PASS','outside_footer_rgba':'PASS','png_roundtrip':'PASS'}))

if __name__=='__main__':main()
