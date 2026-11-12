"""Remove inherited bitmap halo gutters around the fresh vector word quads."""
from datetime import datetime,timezone
import hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
PRIOR=AUDIT/'menu-restoration/selection-vector-candidate-v11'
BASE=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/pack/einhander-texture-replacements'
OUT=AUDIT/'menu-restoration/selection-vector-candidate-v12'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}

def main():
 if OUT.exists():raise ValueError('Existing candidates are immutable')
 old=json.loads((PRIOR/'manifest.json').read_bytes());rows=[]
 (OUT/'pack/einhander-texture-replacements').mkdir(parents=True);(OUT/'previews').mkdir();(OUT/'pack/Hashes.ini').write_text('');shutil.copy2(__file__,OUT/'build-source.py')
 for item in old['assets']:
  key=item['key'];p=BASE/(key+'.png');base=np.asarray(Image.open(p).convert('RGBA'));before=np.asarray(Image.open(item['outputs']['pack']['path']).convert('RGBA'));after=base.copy()
  original_regions=item['selected_native_regions'];regions=list(original_regions);gutter=np.zeros(after.shape[:2],bool)
  if key.startswith('D036'):
   for word in item['registered_words']:
    x0,y0,x1,y1=word['native_uv_half_open'];r=[max(0,x0-4),max(168,y0-3),min(248,x1+4),min(232,y1+3)]
    regions.append(r);gutter[r[1]*16:r[3]*16,r[0]*16:r[2]*16]=True
  elif key.startswith('1AD'):
   regions.append([0,0,220,48]);gutter[0:48*16,0:220*16]=True
  # Clear only bounded old surroundings; then restore every fresh glyph byte.
  after[gutter]=0;authored=np.zeros(after.shape[:2],bool)
  for x0,y0,x1,y1 in original_regions:
   after[y0*16:y1*16,x0*16:x1*16]=before[y0*16:y1*16,x0*16:x1*16]
   authored[y0*16:y1*16,x0*16:x1*16]=True
  if not np.array_equal(after[authored],before[authored]):raise ValueError('Existing new vector glyph changed')
  selected=authored|gutter
  if not np.array_equal(after[~selected],base[~selected]):raise ValueError('Protected v10 RGBA changed')
  if not set(np.unique(after[:,:,3]))<={0,127,255}:raise ValueError('Noncategorical coverage')
  target=OUT/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(after).save(target)
  if np.asarray(Image.open(target).convert('RGBA')).tobytes()!=after.tobytes():raise ValueError('PNG roundtrip mismatch')
  pp=OUT/'previews'/(key+'.png')
  if key.startswith('D036'):box=[0,168,136,189]
  elif key.startswith('1AD'):box=[0,0,220,48]
  else:box=[0,43,112,104]
  x0,y0,x1,y1=box;w=(x1-x0)*6;h=(y1-y0)*6;preview=Image.new('RGB',(w,2*(h+24)),(0,0,0));d=ImageDraw.Draw(preview)
  for n,(label,a) in enumerate([('Previous vectors with inherited outside gutters',before),('Same vector glyphs; old glyph gutters cleared',after)]):
   rgb=a[y0*16:y1*16,x0*16:x1*16,:3].copy();rgb[a[y0*16:y1*16,x0*16:x1*16,3]==0]=0
   d.text((4,n*(h+24)+4),label,fill='white');preview.paste(Image.fromarray(rgb).resize((w,h),Image.Resampling.LANCZOS),(0,n*(h+24)+24))
  preview.save(pp)
  row={**item,'parent':ref(p),'outputs':{'pack':{**ref(target),'size':[after.shape[1],after.shape[0]]}},'selected_native_regions':regions,'preview':ref(pp),'original_vector_cells_byte_exact':True,'protected_rgba_exact':True,'cleared_old_gutter_texels':int(np.any(before!=after,axis=2)[gutter&~authored].sum()),'live_acceptance':'pending new final candidate'}
  rows.append(row)
 manifest={**old,'contract':'selection-vector-clean-gutters-v12','created_at_utc':datetime.now(timezone.utc).isoformat(),'tool':ref(__file__),'glyph_parent':ref(PRIOR/'manifest.json'),'method':'Preserve every reviewed v11 vector cell byte; remove old bitmap/glow remnants in bounded word gutters (including source-native trailing R) and English1AD top-band gaps. Compose from current v10 parent so all unrelated v10 work remains exact.','assets':rows,'live_verified':False}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'candidate':str(OUT),'assets':len(rows),'glyph_bytes_exact':'PASS','protected_rgba':'PASS','png_roundtrip':'PASS'}))

if __name__=='__main__':main()
