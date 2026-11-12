"""Extract the authored Latin boards into small source-verified indexed regions.

This uses the existing runtimev4 exact-region path without changing runtime.
Four32/24pixel signboards plus32RISEphase regions decode to71MiB in total,
instead of36full4096atlases. The sourceproof includes the ENTIRE sampled quad,
including unchangednonLatin content left of Welcom!!/parts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import hashlib
import json
import zlib
import numpy as np
from PIL import Image

from build_three_asset_proof import verify_stock
from build_results_vector_candidate import sha, ref, load, pixels, write, require

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
ATLAS=AUDIT/'menu-restoration/latin-world-sign-vector-candidate-v1'
DEFAULT_OUT=AUDIT/'menu-restoration/latin-world-sign-regions-v1'

def full_roi(row):
 if row['kind']=='parts':return [128,32,192,56]
 return row['selected_native_regions'][0]

def native_decode(raw,clut,w,h):
 words=np.frombuffer(raw,dtype='<u2').reshape(h,w);indices=np.empty((h,w*4),np.uint8)
 for n in range(4):indices[:,n::4]=((words>>(n*4))&15).astype(np.uint8)
 p=np.frombuffer(clut,dtype='<u2');v=p[indices]
 return np.stack(((v&31)*8,((v>>5)&31)*8,((v>>10)&31)*8,np.where(v==0,0,np.where(v&32768,255,127))),2).astype(np.uint8)

def build(output):
 require(not output.exists(),'Choose new immutable region output')
 atlas=load(ATLAS/'manifest.json');require(len(atlas['files'])==36,'Complete36atlasfallbacks required')
 output.mkdir(parents=True);pack=output/'pack';png=pack/'einhander-texture-replacements';png.mkdir(parents=True)
 (pack/'Hashes.ini').write_text('');proof=output/'source-proof';proof.mkdir();parents=output/'parents';parents.mkdir()
 plans=[];rows=[]
 for row in atlas['files']:
  source_key=row['key'];source_path=Path(next(r['path'] for r in row['source_archives'] if r['path'].endswith('.png')))
  meta,fullraw,clut=verify_stock(source_path.parent,source_key)
  require(sha(row['outputs']['pack']['path'])==row['outputs']['pack']['sha256'],'Authored atlas changed')
  x0,y0,x1,y1=full_roi(row);require(x0%4==x1%4==0,'Indexed source ROI must align on words')
  ww=(x1-x0)//4;hh=y1-y0;raw=b''.join(fullraw[y*128+x0//4*2:y*128+x1//4*2] for y in range(y0,y1))
  key=f'{zlib.crc32(raw):08X}-{zlib.crc32(clut):08X}'
  # Queue source metadata explicitly locates the original fullpage. Actual
  # sampled nativepage records must agree before deriving the physicalROI.
  fragment=meta['fragments'];require(len(fragment)==1 and fragment[0][2:]==[64,256,0,0],'Expected source-verified complete fullpage fragment')
  page=fragment[0][:2];cx,cy=meta['clut_xy'];physical=[page[0]+x0//4,page[1]+y0,ww,hh]
  witnesses=row['actual_source_draw_receipts']
  require(all(w['page_xy']==page and w['clut_xy']==[cx,cy] for w in witnesses),'Actual draw source origin differs from source-proof metadata')
  require(any(w['uv_bounds'][0]>=x0 and w['uv_bounds'][2]<x1 and w['uv_bounds'][1]>=y0 and w['uv_bounds'][3]<y1 for w in witnesses),
   'No actual complete draw query is covered by this ROI')
  native=native_decode(raw,clut,ww,hh);require(np.array_equal(native,pixels(source_path)[y0:y1,x0:x1]),'ROI raw/CLUT independentdecode differs')
  archives=[]
  for suffix,data in (('.words.bin',raw),('.clut.bin',clut),('.valid.bin',bytes([1])*(ww*hh))):
   target=pack/(key+suffix);target.write_bytes(data);archives.append(ref(target));shutil.copyfile(target,proof/target.name)
  native_path=proof/(key+'.png');Image.fromarray(native).save(native_path)
  metadata={'key':key,'width_words':ww,'height':hh,'depth':0,'clut_xy':[cx,cy],'clut_words':16,
   'known_words':ww*hh,'total_words':ww*hh,'page_xy':physical[:2],'fragments':[[*physical,0,0]],
   'raw_origin':'Exact independently decoded ROI of immutable source-verified fullpage','reconstructed_crc32':key[:8],
   'fullpage_source_key':source_key,'fullpage_raw_sha256':hashlib.sha256(fullraw).hexdigest(),
   'fullpage_source':ref(source_path),'fullpage_source_uv_half_open':[x0,y0,x1,y1]}
  metadata_path=proof/(key+'.source.json');write(metadata_path,metadata)
  # The existing independent original-source checker must accept this new key.
  check,checked_raw,checked_clut=verify_stock(proof,key);require(checked_raw==raw and checked_clut==clut,'Saved ROI proof differs')
  original=pixels(row['parent']['path']);baseline=np.repeat(np.repeat(original[y0*8:y1*8,x0*8:x1*8],2,0),2,1)
  parent_path=parents/(key+'.png');Image.fromarray(baseline).save(parent_path)
  authored=pixels(row['outputs']['pack']['path'])[y0*16:y1*16,x0*16:x1*16]
  target=png/(key+'.png');Image.fromarray(authored).save(target);require(np.array_equal(pixels(target),authored),'Authored ROI PNG differs')
  # The authored English subrectangle can be smaller than the exact sourceROI.
  selected=[]
  for ax0,ay0,ax1,ay1 in row['selected_native_regions']:selected.append([ax0-x0,ay0-y0,ax1-x0,ay1-y0])
  plan={'key':key,'source_rect':physical,'depth':0,'clut_xy':[cx,cy],
   'page_xy':page,'source_uv_half_open':[x0,y0,x1,y1],'source_fullpage_key':source_key,
   'source_proof':archives+[ref(native_path),ref(metadata_path)],'png':ref(target),'dimensions':[authored.shape[1],authored.shape[0]],
   'actual_source_draw_receipts':witnesses,'live_admission':'NOT RUN'}
  plans.append(plan)
  rows.append({'key':key,'kind':row['kind'],'parent':ref(parent_path),'outputs':{'pack':{**ref(target),'size':plan['dimensions']}},
    'selected_native_regions':selected,'region_plan':plan,'source_fullpage_asset':ref(row['outputs']['pack']['path']),
    'new_exact_region_entry':True,'protected_outside_authored_subregion':True,'live_acceptance':'NOT RUN'})
 tsv='EIN_EXACT_REGIONS_V1\n'+''.join(' '.join(map(str,[p['key'],*p['source_rect'],p['depth'],*p['clut_xy']]))+'\n' for p in plans)
 (pack/'ExactRegions.tsv').write_text(tsv,encoding='ascii')
 shutil.copyfile(__file__,output/'build-source.py')
 total=sum(r['outputs']['pack']['size'][0]*r['outputs']['pack']['size'][1]*4 for r in rows)
 manifest={'format':1,'contract':'latin-world-indexed-exact-regions-v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
  'atlas_fallback':ref(ATLAS/'manifest.json'),'builder':ref(Path(__file__)),'files':rows,'asset_count':len(rows),
  'exact_regions':plans,'exact_regions_tsv':ref(pack/'ExactRegions.tsv'),'decoded_rgba_bytes_all_entries':total,
  'decoded_rgba_mib_all_entries':total/(1024*1024),'runtime_changes':False,'production_installed':False,'game_actions':0,
  'precedence':'Runtime genuineupload first; manifested exactregion before nativepage fallback. Current signwitnesses are nativepage sources.',
  'remaining':['Cold actual exactregionadmission and visible32phasepalette replay','Actual UV/semitransparency/nearfar/readability/performance checks',
    'Parentfinalstager must append these36rows to existing6 exactregions and any supported posterregions; no manifest overlap or64entryoverflow allowed'],
  'live_acceptance':'NOT RUN'}
 write(output/'manifest.json',manifest);verify(output)

def verify(output):
 m=load(output/'manifest.json')
 for field in ('atlas_fallback','builder','exact_regions_tsv'):require(sha(m[field]['path'])==m[field]['sha256'],'Input changed: '+field)
 atlas={r['key']:r for r in load(ATLAS/'manifest.json')['files']};seen=set();count=0
 for row in m['files']:
  p=row['region_plan'];require(p['key']==row['key'] and row['key'] not in seen,'Duplicate/inconsistent region key');seen.add(row['key'])
  source=atlas[p['source_fullpage_key']];x0,y0,x1,y1=p['source_uv_half_open']
  metadata,raw,clut=verify_stock(output/'source-proof',row['key'])
  require(metadata['page_xy']==p['source_rect'][:2] and [metadata['width_words'],metadata['height']]==p['source_rect'][2:],'Sourcegeometry differs')
  for archive in p['source_proof']:require(sha(archive['path'])==archive['sha256'],'Region proof changed')
  require(sha(p['png']['path'])==p['png']['sha256'],'RegionPNG changed')
  authored=pixels(p['png']['path']);require(np.array_equal(authored,pixels(source['outputs']['pack']['path'])[y0*16:y1*16,x0*16:x1*16]),'Region no longer matches reviewed authoredatlas')
  before=pixels(row['parent']['path']);allowed=np.zeros(authored.shape[:2],bool)
  for a,b,c,d in row['selected_native_regions']:allowed[b*16:d*16,a*16:c*16]=True
  require(np.array_equal(authored[~allowed],before[~allowed]),'Unrelated nonLatin pixels changed inside region')
  require(set(map(int,np.unique(authored[:,:,3])))<={0,127,255},'Noncategorical alpha');count+=1
 receipt={'outcome':'PASS','indexed_regions_verified':count,'all_native_raw_palette_validity_decode_checked':True,
  'authored_region_pixels_exact_to_reviewed_atlas':True,'unmodified_subregions_exact':True,
  'decoded_rgba_mib_all_entries':m['decoded_rgba_mib_all_entries'],'runtime_loader_match_test':'NOT RUN',
  'actual_game_GL_admission':'NOT RUN','game_actions':0}
 write(output/'verification.json',receipt);print(json.dumps({'manifest':ref(output/'manifest.json'),**receipt}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT_OUT);p.add_argument('--verify',action='store_true');a=p.parse_args()
 if a.verify:verify(a.output.resolve())
 else:build(a.output.resolve())
