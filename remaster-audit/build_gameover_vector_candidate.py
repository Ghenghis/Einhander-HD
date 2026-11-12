"""Source-registered vector reconstruction of the bespoke GAME OVER wordmark.

Explicit paths retain the large G, serif structure, interlocking letters,
hollow counters and teal/silver outline. No native bitmap field is enlarged.
"""
from datetime import datetime,timezone
import hashlib,json,shutil,zlib
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'remaster-audit'
SOURCE=AUDIT/'menu-restoration/gameover-region-candidate-v3/source-proof'
OUT=AUDIT/'menu-restoration/gameover-vector-candidate-v3'
KEY='5125FF82-00000000'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/pack/einhander-texture-replacements'/(KEY+'.png')
# Optical vector registration to the verified256x64 upright source. Closed
# paths describe the white perimeter, with separate genuine counters.
PATHS=[
 [('M',43,9),('L',27,9),('C',17,9,9.5,19,9.5,30.5),('C',9.5,43,18.5,51.5,29,51.5),('C',37,51.5,43,48.5,46,45),('L',46,35),('L',49,32.5),('L',30,32.5),('L',34.5,35.5),('L',34.5,41.5),('C',31.5,44.5,27.5,44.7,24,42.7),('C',18.6,39.5,16,35,16,30.5),('C',16,23.5,21,17,27,15.5),('L',34,15.5),('L',43,21),('Z',)],
 [('M',44,46),('L',47,42),('L',58.8,15),('L',72,42),('L',77,46),('L',64,46),('L',61,37.5),('L',54.5,37.5),('L',51.3,46),('Z',)],
 [('M',57,32.5),('L',59,27),('L',61,32.5),('Z',)],
 [('M',73.5,17.5),('L',84,17.5),('L',81.5,20),('L',90,28.5),('L',99,20),('L',96.5,17.5),('L',107,17.5),('L',104,20),('L',104,42.5),('L',107,46),('L',96.5,46),('L',99,42.5),('L',99,30.5),('L',90,38.5),('L',81.5,30.5),('L',81.5,42.5),('L',84.5,46),('L',73.5,46),('L',76.5,42.5),('L',76.5,20),('Z',)],
 [('M',104,17.5),('L',122,17.5),('L',125,14.5),('L',125,27),('L',122,25),('L',111,25),('L',111,28.5),('L',123,28.5),('L',123,35.5),('L',111,35.5),('L',111,39.5),('L',122,39.5),('L',125,37.5),('L',125,49),('L',122,46),('L',104,46),('L',107,42.5),('L',107,20),('Z',)],
 [('M',159.5,17.5),('C',150,17.5,144,23.5,144,32.5),('C',144,42,150,48,159.5,48),('C',169,48,175,42,175,32.5),('C',175,23.5,169,17.5,159.5,17.5),('Z',)],
 [('M',159.5,23),('C',153.5,23,150,26.5,150,32.5),('C',150,38.5,153.5,42.5,159.5,42.5),('C',165.5,42.5,169,38.5,169,32.5),('C',169,26.5,165.5,23,159.5,23),('Z',)],
 [('M',170,17.5),('L',181,17.5),('L',178,20),('L',188,36),('L',197,20),('L',194,17.5),('L',205,17.5),('L',201,20),('L',188,46.5),('L',174,20),('Z',)],
 [('M',200,17.5),('L',218,17.5),('L',221,14.5),('L',221,27),('L',218,25),('L',207,25),('L',207,28.5),('L',219,28.5),('L',219,35.5),('L',207,35.5),('L',207,39.5),('L',218,39.5),('L',221,37.5),('L',221,49),('L',218,46),('L',200,46),('L',203,42.5),('L',203,20),('Z',)],
 [('M',218,17.5),('L',235,17.5),('C',242,17.5,245,21.5,245,27),('C',245,31,242.5,33.8,239,35),('L',246,42.5),('L',248.5,46),('L',239,46),('L',229,35.5),('L',229,42.5),('L',232,46),('L',218,46),('L',222,42.5),('L',222,20),('Z',)],
 [('M',229,23),('L',234,23),('C',237.5,23,239,24.2,239,27),('C',239,29.4,237.5,30,234,30),('L',229,30),('Z',)],
]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def flatten(path):
 points=[];start=None;current=None
 for entry in path:
  if entry[0]=='M':current=np.array(entry[1:],float);start=current.copy();points.append(tuple(current))
  elif entry[0]=='L':current=np.array(entry[1:],float);points.append(tuple(current))
  elif entry[0]=='C':
   p0=current.copy();p1=np.array(entry[1:3]);p2=np.array(entry[3:5]);p3=np.array(entry[5:7])
   for t in np.linspace(0,1,129)[1:]:points.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3))
   current=p3
  elif entry[0]=='Z':points.append(tuple(start));current=start
 return points

def main():
 if OUT.exists():raise ValueError('Existing candidates are immutable')
 source=np.array(Image.open(SOURCE/(KEY+'.png')).convert('RGBA'));raw=(SOURCE/(KEY+'.words.bin')).read_bytes()
 if source.shape!=(256,64,4) or f'{zlib.crc32(raw):08X}'!='5125FF82':raise ValueError('Native source/CRC mismatch')
 upright=np.rot90(source,-1);rgb_source=upright[:,:,:3];peak=rgb_source.max(2)
 if not np.array_equal(upright[:,:,3],np.where(peak>0,127,255)):raise ValueError('Unreviewed source16bit/STP semantics')
 ss=2;factor=16*ss;canvas=Image.new('RGB',(256*factor,64*factor));draw=ImageDraw.Draw(canvas)
 curves=[[(round(x*factor),round(y*factor)) for x,y in flatten(p)] for p in PATHS]
 # Join interlocking serifs before outlining them. Independently drawing the
 # individual letter perimeters creates spurious X crossings where serifs
 # overlap; the native wordmark has one continuous shared border there.
 union=np.zeros((64*factor,256*factor),np.uint8)
 for outer,holes in [(0,[]),(1,[2]),(3,[]),(4,[]),(5,[6]),(7,[]),(8,[]),(9,[10])]:
  glyph=Image.new('L',canvas.size);gd=ImageDraw.Draw(glyph);gd.polygon(curves[outer],fill=255)
  for hole in holes:gd.polygon(curves[hole],fill=0)
  union=np.maximum(union,np.asarray(glyph))
 contours,_=cv2.findContours(union,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
 borders=[]
 for contour in contours:
  pts=[tuple(map(int,p[0])) for p in contour]
  if len(pts)>2:borders.append(pts+[pts[0]])
 for width,color in [(3.2,(0,20,20)),(2.2,(0,51,51)),(1.35,(40,128,128)),(.65,(232,248,248))]:
  for curve in borders:draw.line(curve,fill=color,width=round(width*factor),joint='curve')
 rgb=np.array(canvas.resize((4096,1024),Image.Resampling.LANCZOS));rgba=np.zeros((1024,4096,4),np.uint8);rgba[:,:,:3]=rgb
 rgba[:,:,3]=np.where(rgb.max(2)>0,127,255)
 encoded=np.rot90(rgba,1)
 (OUT/'pack/einhander-texture-replacements').mkdir(parents=True);(OUT/'pack/Hashes.ini').write_text('');shutil.copytree(SOURCE,OUT/'source-proof')
 target=OUT/'pack/einhander-texture-replacements'/(KEY+'.png');Image.fromarray(encoded).save(target)
 if np.array(Image.open(target).convert('RGBA')).tobytes()!=encoded.tobytes():raise ValueError('PNG roundtrip mismatch')
 Image.fromarray(rgb).save(OUT/'gameover-vector-upright.png')
 old=np.array(Image.open(AUDIT/'menu-restoration/gameover-region-candidate-v3/gameover-encoded-upright.png').convert('RGB'))
 preview=Image.new('RGB',(1536,3*384+75));pd=ImageDraw.Draw(preview)
 for n,(label,im) in enumerate([('Native reference / fixed source composition',Image.fromarray(rgb_source)),('Previous level-set reconstruction',Image.fromarray(old)),('New explicit vector contours / same serif wordmark identity',Image.fromarray(rgb))]):
  y=n*409;pd.text((8,y+4),label,fill='white');preview.paste(im.resize((1536,384),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS),(0,y+25))
 preview.save(OUT/'comparison-native6x.png')
 svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 64"><rect width="256" height="64" fill="black"/><g fill="none" stroke="#e8f8f8" stroke-width="0.65" stroke-linejoin="round">']
 for path in PATHS:svg.append('<path d="'+' '.join(e[0]+' '+' '.join(map(str,e[1:])) for e in path)+'"/>')
 svg.append('</g></svg>');(OUT/'wordmark-outline.svg').write_text('\n'.join(svg)+'\n');shutil.copy2(__file__,OUT/'build-source.py')
 manifest={'schema_version':1,'contract':'gameover-explicit-vector-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':1,'production_installed':False,'game_actions':0,'tool':ref(__file__),'source_words_crc':'5125FF82','source_region_words':[448,256,64,256],'depth':2,'native_source':ref(SOURCE/(KEY+'.png')),'native_words':ref(SOURCE/(KEY+'.words.bin')),'files':[{'key':KEY,**ref(target),'parent':ref(PARENT),'selected_native_regions':[[0,0,64,256]],'outputs':{'pack':{**ref(target),'size':[1024,4096]}},'size':[1024,4096],'source_region_words':[448,256,64,256],'depth':2,'source_crc':'5125FF82','palette_crc':'00000000','native_alpha_stp_exact':False,'categorical_source_class_policy_preserved':True}],'vector_source':ref(OUT/'wordmark-outline.svg'),'upright':ref(OUT/'gameover-vector-upright.png'),'comparison':ref(OUT/'comparison-native6x.png'),'method':'Explicit manually registered line/Bezier paths preserve largeG, outlined serifletter identity, triangleA, M/Vtopology, Eserifs, Ocounter, Rleg, spacing and90degree encoding; compact teal/silver strokes; no bitmap contour interpolation.','alpha_policy':'Same native16bit semantics: nonblackRGB opaque127; blackSTP255. Coverage geometry follows the fresh vector, rather than clipping it to nativepixel classes.','live_verified':False,'remaining':['Independent appearance/identity review','Exact-region submission receipt and natural GameOverfade/re-entry replay']}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'candidate':str(OUT),'png_roundtrip':'PASS','source_crc':'PASS','categorical_class_policy':'PASS'}))

if __name__=='__main__':main()
