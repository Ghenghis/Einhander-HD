"""Reconstruct the actual centered startup SQUARESOFT logo as custom vectors.

All contours are explicit Bezier/polygon geometry, registered to the verified
256x26 source. The native bitmap supplies geometry/identity evidence only.
"""
from datetime import datetime,timezone
import hashlib,json,shutil,zlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
SOURCE=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
OUT=AUDIT/'menu-restoration/startup-squaresoft-vector-candidate-v1'
KEY='4E783C96-E2D2473F'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/pack/einhander-texture-replacements'/(KEY+'.png')
EXE=Path('C:/github/REMASTER_STAGING/disc_stock/files/SCUS_942.43')
S=[('M',25.6,3.5),('C',20.2,.4,15.5,1.8,11.2,5.7),('C',7,9.5,9,11.8,13.6,13.3),('C',16.3,14.2,16.1,15.8,14,17),('C',11,18.8,7.3,17.5,5,15.4),('L',1,20.1),('C',6,24.3,14.5,24.6,20.4,20),('C',26.0,15,24.5,10.8,20.3,9.1),('C',17.6,8,16.8,7.2,18.4,6.2),('C',20.3,5,22,6,23,6.6),('Z',)]
Q=[('M',48,2),('C',58,2,62,7.5,55.2,15.5),('C',52.8,18.5,49.8,20,47,20.5),('L',58,20.5),('L',56.5,23),('L',37,23),('C',23,23,25.5,14.5,31.5,8),('C',35.6,3.8,41.8,2,48,2),('Z',)]
QHOLE=[('M',46.5,7),('C',40.5,7,36.5,10.2,34,14),('C',31.5,18,35,19,40,18),('C',46,17,50.4,13,51.5,9.5),('C',52,7.5,49.5,7,46.5,7),('Z',)]
U=[('M',65,2.5),('L',73,2.5),('L',65.8,16.2),('C',64.6,18.5,67.6,19.2,70,17.8),('L',78.2,2.5),('L',86,2.5),('L',76.8,19.4),('C',73.9,24,58.4,25.3,58.2,18.3),('Z',)]
A=[('M',74,23),('L',98.3,.5),('L',105.5,23),('L',98.5,23),('L',96,9),('L',81,23),('Z',)]
RED=[('M',79.8,23),('L',96.3,8.7),('L',97.6,23),('Z',)]
R=[('M',114,3),('L',126,3),('C',133.5,3,136,6,133.8,11),('C',132.4,14,130,15.8,126.2,16.4),('L',131.2,23),('L',121.5,23),('L',118.7,17.2),('L',114.1,17.2),('L',111.1,23),('L',103.2,23),('Z',)]
RHOLE=[('M',120,7),('L',125,7),('C',129.2,7,127.4,12.1,123.3,12.1),('L',117.8,12.1),('Z',)]
E=[('M',141,3),('L',159,3),('L',157,7.3),('L',147.1,7.3),('L',145.3,10.8),('L',155.4,10.8),('L',153,15.1),('L',143.1,15.1),('L',141.2,18.7),('L',152.2,18.7),('L',150,23),('L',131.7,23),('Z',)]
O=[('M',198,3),('C',209,3,214,9.3,205,18),('C',198,25,180,24.5,178.3,19.2),('C',174.5,9,188.3,3,198,3),('Z',)]
OHOLE=[('M',196.5,7.2),('C',191,6.6,186.2,9.8,184.5,13.5),('C',181.5,20,191.6,20.6,198,15.4),('C',203.4,11,203.9,7.4,196.5,7.2),('Z',)]
F=[('M',216.2,3),('L',233,3),('L',231,7.5),('L',221,7.5),('L',219.3,11),('L',229,11),('L',226.8,15.2),('L',217.2,15.2),('L',213.1,23),('L',205.8,23),('Z',)]
T=[('M',234,3.5),('L',253.6,3.5),('L',251.3,8),('L',246.3,8),('L',239,23),('L',231.2,23),('L',239,8),('L',231.8,8),('Z',)]

def shift(path,dx):return [(p[0],*[v+dx if n%2==0 else v for n,v in enumerate(p[1:])]) for p in path]
GLYPHS=[('S',S,[]),('Q',Q,[QHOLE]),('U',U,[]),('A',A,[]),('R',R,[RHOLE]),('E',E,[]),('S',shift(S,151),[]),('O',O,[OHOLE]),('F',F,[]),('T',T,[])]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(path),'sha256':sha(path)}
def flatten(path):
 points=[];start=None;current=None
 for entry in path:
  if entry[0]=='M':current=np.array(entry[1:],float);start=current.copy();points.append(tuple(current))
  elif entry[0]=='L':current=np.array(entry[1:],float);points.append(tuple(current))
  elif entry[0]=='C':
   p0=current.copy();p1=np.array(entry[1:3]);p2=np.array(entry[3:5]);p3=np.array(entry[5:7])
   for t in np.linspace(0,1,193)[1:]:points.append(tuple((1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3))
   current=p3
  elif entry[0]=='Z':points.append(tuple(start));current=start
 return points
def dpath(path):return ' '.join(e[0]+' '+' '.join(map(str,e[1:])) for e in path)

def main():
 if OUT.exists():raise ValueError('Existing candidates are immutable')
 metadata=json.loads((SOURCE/(KEY+'.source.json')).read_bytes());raw=(SOURCE/(KEY+'.words.bin')).read_bytes();clut=(SOURCE/(KEY+'.clut.bin')).read_bytes();valid=(SOURCE/(KEY+'.valid.bin')).read_bytes()
 if metadata['depth']!=1 or metadata['width_words']!=128 or metadata['height']!=26:raise ValueError('Unexpected native dimensions/depth')
 if f'{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}'!=KEY:raise ValueError('Source/CLUT CRC mismatch')
 if len(raw)!=6656 or len(clut)!=512 or len(valid)!=3328 or set(valid)!={1}:raise ValueError('Incomplete native source proof')
 palette_words=np.frombuffer(clut,dtype='<u2');palette=np.stack(((palette_words&31)<<3,((palette_words>>5)&31)<<3,((palette_words>>10)&31)<<3,np.where(palette_words==0,0,np.where(palette_words&32768,255,127))),axis=1).astype(np.uint8)
 decoded=palette[np.frombuffer(raw,np.uint8).reshape(26,256)];native=np.asarray(Image.open(SOURCE/(KEY+'.png')).convert('RGBA'))
 if not np.array_equal(decoded,native) or set(np.unique(decoded[:,:,3]))!={0,127}:raise ValueError('Independent8bpp RGBA decode differs')
 exe=EXE.read_bytes();pixel_offset=exe.find(raw);clut_offset=exe.find(clut)
 if pixel_offset!=0xE2D4 or clut_offset!=0xE034:raise ValueError('Embedded source locations differ')
 parent=Image.open(PARENT).convert('RGBA')
 if parent.size!=(2048,208):raise ValueError('Expected existing8x startup logo parent')
 ss=4;factor=16*ss;size=(256*factor,26*factor);white=np.zeros((size[1],size[0]),np.uint8)
 def points(path):return [(round(x*factor),round(y*factor)) for x,y in flatten(path)]
 for name,outer,holes in GLYPHS:
  glyph=Image.new('L',size);gd=ImageDraw.Draw(glyph);gd.polygon(points(outer),fill=255)
  for hole in holes:gd.polygon(points(hole),fill=0)
  white=np.maximum(white,np.asarray(glyph))
 red=Image.new('L',size);ImageDraw.Draw(red).polygon(points(RED),fill=255)
 white=np.asarray(Image.fromarray(white).resize((4096,416),Image.Resampling.LANCZOS));red=np.asarray(red.resize((4096,416),Image.Resampling.LANCZOS))
 wf=white.astype(np.float32)/255;rf=red.astype(np.float32)/255
 rgb=np.rint(np.array([248,248,248])[None,None,:]*wf[:,:,None]*(1-rf[:,:,None])+np.array([240,8,16])[None,None,:]*rf[:,:,None]).clip(0,255).astype(np.uint8)
 authored=np.dstack((rgb,np.where(np.maximum(white,red)>0,127,0).astype(np.uint8)))
 if set(np.unique(authored[:,:,3]))!={0,127}:raise ValueError('Opaque/clear classes changed')
 (OUT/'pack/einhander-texture-replacements').mkdir(parents=True);(OUT/'source-proof').mkdir();(OUT/'previews').mkdir();(OUT/'pack/Hashes.ini').write_text('')
 target=OUT/'pack/einhander-texture-replacements'/(KEY+'.png');Image.fromarray(authored).save(target)
 if np.asarray(Image.open(target).convert('RGBA')).tobytes()!=authored.tobytes():raise ValueError('PNG roundtrip failed')
 for suffix in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json'):shutil.copy2(SOURCE/(KEY+suffix),OUT/'source-proof'/(KEY+suffix))
 receipts=[]
 for role,path in [('native_source_query',Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/evidence/draws.jsonl')),('existing8xGLdraw',Path('C:/github/REMASTER_STAGING/stage1_remaster/integration-uhd/evidence/draws.jsonl'))]:
  record=json.loads(path.read_text().splitlines()[2])
  if record.get('key')!=KEY:raise ValueError('Expected startup draw receipt')
  receipts.append({'role':role,'log':ref(path),'line':3,'record':record})
 (OUT/'source-proof/native-draw-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 provenance={'disc_executable':ref(EXE),'pixel_file_offset':pixel_offset,'pixel_offset_hex':hex(pixel_offset),'clut_file_offset':clut_offset,'clut_offset_hex':hex(clut_offset),'psx_exe_load_address':'0x80010000','pixel_guest_address':'0x8001DAD4','clut_guest_address':'0x8001D834','source_crc':'4E783C96','clut_crc':'E2D2473F','decoded_rgba_sha256':hashlib.sha256(decoded.tobytes()).hexdigest(),'native_dimensions':[256,26],'depth':1,'source_complete':True}
 (OUT/'source-proof/embedded-source-proof.json').write_text(json.dumps(provenance,indent=2)+'\n')
 svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 26" width="4096" height="416"><g fill="#f8f8f8" fill-rule="evenodd">']
 for name,outer,holes in GLYPHS:svg.append('<path aria-label="'+name+'" d="'+dpath(outer)+' '+' '.join(dpath(h) for h in holes)+'"/>')
 svg+=['</g><path fill="#f00810" d="'+dpath(RED)+'"/></svg>'];master=OUT/'squaresoft-master.svg';master.write_text('\n'.join(svg)+'\n');shutil.copy2(__file__,OUT/'build-source.py')
 previews=[]
 for scale in (4,9):
  width,height=256*scale,26*scale;canvas=Image.new('RGB',(width,(height+26)*3),(0,0,0));d=ImageDraw.Draw(canvas)
  for n,(label,im) in enumerate([('Verified native SQUARESOFT / actual'+str(scale)+'x',Image.fromarray(native)),('Previous8x texture / same output scale',parent),('New explicit vector artwork / same output scale',Image.fromarray(authored))]):
   a=np.array(im.convert('RGBA'));p=a[:,:,:3].copy();p[a[:,:,3]==0]=0
   d.text((6,n*(height+26)+5),label,fill='white');canvas.paste(Image.fromarray(p).resize((width,height),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS),(0,n*(height+26)+26))
  path=OUT/'previews'/('startup-squaresoft-actual'+str(scale)+'x.png');canvas.save(path);previews.append(ref(path))
 item={'key':KEY,'parent':ref(PARENT),'source':ref(OUT/'source-proof'/(KEY+'.png')),'native_dimensions':[256,26],'selected_native_regions':[[0,0,256,26]],'allow_integer_resolution_increase':True,'full_rebuild':True,'outputs':{'pack':{**ref(target),'size':[4096,416]}},'source_crc':'4E783C96','palette_crc':'E2D2473F','depth':1,'alpha_classes':[0,127],'png_roundtrip_exact':True,'source_proof':ref(OUT/'source-proof/embedded-source-proof.json'),'native_draw_receipts':ref(OUT/'source-proof/native-draw-receipts.json')}
 manifest={'schema_version':1,'contract':'startup-squaresoft-explicit-vector-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':1,'production_installed':False,'game_actions':0,'tool':ref(__file__),'native_dimensions':[256,26],'allow_integer_resolution_increase':True,'full_rebuild':True,'vector_master':ref(master),'method':'Explicit custom italic S/Q/U/A/R/E/S/O/F/T Bezier/polygon contours, Q/R/O counters, original large triangular A and red emblem; source-registered placement and source white/red identity. Rendered16x with supersampled edge coverage, categorical alpha0/127. No native bitmap contour interpolation or blur.','assets':[item],'previews':previews,'live_verified':False,'remaining':['Independent native/logo identity and spacing review','Actual fresh2160p cold-boot replacement submission and composed centered splash review']}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'candidate':str(OUT),'png_size':[4096,416],'source_crc':'PASS','clut_crc':'PASS','8bpp_decode':'PASS','embedded_exe_match':'PASS','png_roundtrip':'PASS'}))

if __name__=='__main__':main()
