"""Fresh date/copyright outlines inside the proven footer, preserving SQUARE."""
from datetime import datetime,timezone
import hashlib,importlib.util,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/pack/einhander-texture-replacements'
OUT=AUDIT/'menu-restoration/copyright-vector-candidate-v1'
SOURCE=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
FONT=Path('C:/Windows/Fonts/georgiab.ttf')
REGION=(80,236,144,248)
KEYS=['8E1A509D-4FE32821','8E1A509D-8808F70A','8E1A509D-C7A1F2F0']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 if OUT.exists():raise ValueError('Existing candidates are immutable')
 hud=module(ROOT/'windows-x64/tools/build_hud_ui_candidate.py','copyright_vector_hud')
 helper=module(AUDIT/'build_selection_vector_candidate.py','copyright_vector_helpers')
 # The nine-character year string is one baked word in the actual119x12
 # footer quad. Copyright circle and year share their original optical boxes.
 mask=np.zeros((12*16,64*16),np.uint8)
 circle=helper.fitted_mask('©',9,12,FONT,8,top=1.8,inset=.1)
 date=helper.fitted_mask('1997/1998',44,12,FONT,6.8,top=3,inset=.1)
 mask[:,7*16:16*16]=circle;mask[:,18*16:62*16]=date
 (OUT/'pack/einhander-texture-replacements').mkdir(parents=True);(OUT/'previews').mkdir();(OUT/'pack/Hashes.ini').write_text('')
 shutil.copy2(__file__,OUT/'build-source.py');rows=[]
 prior=json.loads((AUDIT/'menu-restoration/copyright-square-candidate-v1/manifest.json').read_bytes())
 if prior['exact_wording']!='©1997/1998 SQUARE':raise ValueError('Copyright wording proof changed')
 for key in KEYS:
  m,raw,clut=hud.verify_stock(SOURCE,key);indices=hud.decode_indices(raw,m);palette=hud.palette_rgba(clut);native=palette[indices]
  parent=PARENT/(key+'.png');before=np.array(Image.open(parent).convert('RGBA'));after=before.copy()
  patch=np.zeros((*mask.shape,4),np.uint8);patch[:,:,:3]=np.rint(mask[:,:,None].astype(np.float32)*palette[0,:3]/255).astype(np.uint8)
  patch[:,:,3]=np.where(mask==0,0,np.where(mask>=230,palette[0,3],palette[1,3]))
  x0,y0,x1,y1=REGION;after[y0*16:y1*16,x0*16:x1*16]=patch
  selected=np.zeros(before.shape[:2],bool);selected[y0*16:y1*16,x0*16:x1*16]=True
  if not np.array_equal(before[~selected],after[~selected]):raise ValueError('Protected footer/artwork changed')
  if not np.array_equal(before[236*16:248*16,144*16:199*16],after[236*16:248*16,144*16:199*16]):raise ValueError('SQUARE logo changed')
  if not set(np.unique(after[:,:,3]))<={0,127,255}:raise ValueError('Noncategorical alpha')
  target=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(after).save(target)
  if np.array(Image.open(target).convert('RGBA')).tobytes()!=after.tobytes():raise ValueError('PNG roundtrip failed')
  preview=Image.new('RGB',(600,3*76),(10,14,45));d=ImageDraw.Draw(preview)
  for n,(label,pixels,factor) in enumerate([('Native reference / actual4x',native,1),('Previous replacement / actual4x',before,16),('Fresh date outlines / SQUARE byte-exact',after,16)]):
   a=pixels[236*factor:248*factor,80*factor:199*factor].copy();rgb=a[:,:,:3].copy();rgb[a[:,:,3]==0]=[10,14,45]
   d.text((6,n*76+3),label,fill='white');preview.paste(Image.fromarray(rgb).resize((476,48),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS),(6,n*76+24))
  pp=OUT/'previews'/(key+'.png');preview.save(pp)
  rows.append({'key':key,'parent':ref(parent),'source':ref(SOURCE/(key+'.png')),'raw_sha256':hashlib.sha256(raw).hexdigest(),'clut_sha256':hashlib.sha256(clut).hexdigest(),'selected_native_regions':[list(REGION)],'outputs':{'pack':{**ref(target),'size':[4096,4096]}},'preview':ref(pp),'protected_rgba_exact':True,'square_logo_byte_exact':True,'categorical_alpha':True,'png_roundtrip_exact':True})
 manifest={'schema_version':1,'contract':'copyright-date-vector-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':len(rows),'production_installed':False,'game_actions':0,'tool':ref(__file__),'vector_helper':ref(AUDIT/'build_selection_vector_candidate.py'),'font':ref(FONT),'source_mapping':ref(AUDIT/'menu-restoration/copyright-square-candidate-v1/manifest.json'),'exact_wording':'©1997/1998 SQUARE','rebuilt_wording':'©1997/1998','method':'New Georgia Bold outlines inside original copyright/year optical registration; clear old date shadows only within80..144/236..248. Every SQUARE logo and outside pixel remains byte-identical to v10.','assets':rows,'live_verified':False,'remaining':['Natural title fade/cold load replacement submission and2160p composed footer review']}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'candidate':str(OUT),'assets':3,'protected_rgba':'PASS','square_logo_byte_exact':'PASS','png_roundtrip':'PASS'}))

if __name__=='__main__':main()
