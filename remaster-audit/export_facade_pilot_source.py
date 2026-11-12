"""Export one immutable, source-bound building reference; no authoring/inference."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil,zlib
from collections import Counter
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from build_three_asset_proof import verify_stock
ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit';OUT=AUDIT/'world-sign-mapping/facade-pilot-source-v2'
KEY='73BF9877-5E9B9AC3';ROI=[0,0,64,64]
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert not OUT.exists(),'Versioned reference output already exists'
 OUT.mkdir();proof=OUT/'source-proof';proof.mkdir();full=OUT/'original-fullpage';full.mkdir()
 qpath=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json');assets=json.loads(qpath.read_text())['assets'];row=next(a for a in assets if a['key']==KEY);source=Path(row['source']);meta,raw,clut=verify_stock(source.parent,KEY)
 assert meta['depth']==0 and meta['fragments']==[[768,0,64,256,0,0]] and meta['clut_xy']==[0,480]
 im=Image.open(source).convert('RGBA');native=im.crop(ROI);rgba=np.asarray(native);crop_raw=b''.join(raw[y*128:y*128+32] for y in range(64));crop_key=f'{zlib.crc32(crop_raw):08X}-{zlib.crc32(clut):08X}'
 native_path=proof/(crop_key+'.png');native.save(native_path)
 for suffix,data in (('.words.bin',crop_raw),('.clut.bin',clut),('.valid.bin',b'\1'*(16*64))):(proof/(crop_key+suffix)).write_bytes(data)
 crop_meta={'key':crop_key,'width_words':16,'height':64,'depth':0,'clut_xy':[0,480],'clut_words':16,'known_words':1024,'total_words':1024,'fragments':[[768,0,16,64,0,0]],'reconstructed_crc32':crop_key[:8],'raw_origin':'Exact bounded facade crop of independently source-verified 73BF9877 fullpage','fullpage_source_key':KEY,'fullpage_source_uv_half_open':ROI,'fullpage_source':ref(source)}
 write(proof/(crop_key+'.source.json'),crop_meta);_,check_raw,check_clut=verify_stock(proof,crop_key);assert check_raw==crop_raw and check_clut==clut
 refs=[]
 for suffix in ('.png','.words.bin','.clut.bin','.valid.bin','.source.json'):
  p=source.with_suffix(suffix);dest=full/p.name;shutil.copy2(p,dest);refs.append(ref(dest))
 native_alias=OUT/'facade-native-64x64.png';native.save(native_alias)
 # Opaque RGB is an authoring reference only. The actual categorical class
 # map is exported independently and must be restored after inference.
 rgb=native.convert('RGB');rgb.resize((1024,1024),Image.Resampling.NEAREST).save(OUT/'facade-reference-nearest16x-1024.png')
 alpha=Image.fromarray(rgba[:,:,3]);alpha.save(OUT/'alpha-class-native-64x64.png');alpha.resize((1024,1024),Image.Resampling.NEAREST).save(OUT/'alpha-class-nearest16x-1024.png')
 repeated=Image.new('RGB',(192,192))
 for y in range(3):
  for x in range(3):repeated.paste(rgb,(x*64,y*64))
 repeated.resize((768,768),Image.Resampling.NEAREST).save(OUT/'facade-3x3-repeat-nearest4x-reference.png')
 screenshot=Path('C:/Users/Admin/Documents/Lightshot/Screenshot_4895.png');context=Image.open(screenshot).convert('RGB');context.crop((1350,225,1937,1285)).save(OUT/'provided-city-screenshot-facade-context.png')
 annotated=context.copy();d=ImageDraw.Draw(annotated);d.rectangle((1350,225,1937,1285),outline='#00ffff',width=4);d.text((1360,234),'Repeated blue-window facade context',font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',20),fill='#00ffff');annotated.save(OUT/'provided-city-screenshot-context-location.png')
 # Find existing upload aliases by both physical fragment registration and
 # exact overlapping raw bytes, rather than assuming every palette shares
 # this material or that a short upload is a mip.
 aliases=[]
 for a in assets:
  if a['key']==KEY:continue
  if not a.get('source_verified') or not a.get('source_metadata'):continue
  am=a['source_metadata']
  if am['depth']!=0 or am['clut_xy']!=[0,480]:continue
  ap=Path(a['source']);ar=None
  for fx,fy,fw,fh,sx,sy in am['fragments']:
   x0=max(768,fx);y0=max(0,fy);x1=min(784,fx+fw);y1=min(64,fy+fh)
   if x1<=x0 or y1<=y0:continue
   if ar is None:ar=ap.with_suffix('.words.bin').read_bytes()
   good=True
   for y in range(y0,y1):
    original=raw[y*128+(x0-768)*2:y*128+(x1-768)*2];offset=((sy+y-fy)*am['width_words']+sx+x0-fx)*2
    if ar[offset:offset+(x1-x0)*2]!=original:good=False;break
   if good:aliases.append({'key':a['key'],'source':ref(ap),'kind':a['kind'],'full_source_dimensions':a['source_size'],'physical_matching_overlap_words':[x0,y0,x1-x0,y1-y0],'source_metadata':am,'scope':'Only this overlapping source content proven; do not overwrite unrelated atlas pixels'})
 receipts=[]
 captures=[AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9/native-v9-world-gameover-results/capture.jsonl',AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v2/native-menu/capture.jsonl']
 for p in captures:
  if not p.exists():continue
  for line in p.open():
   r=json.loads(line);uv=r.get('uv_bounds')
   if r.get('key')==KEY and uv and 0<=uv[0]<=uv[2]<64 and 0<=uv[1]<=uv[3]<64 and r.get('event') in ('source_draw_query_matched','replacement_gl_draw_submitted'):receipts.append({'evidence':str(p),**r})
 assert receipts
 write(OUT/'actual-draw-receipts.json',receipts)
 original_variants=[{'key':a['key'],'clut_xy':a['source_metadata']['clut_xy']} for a in assets if a['key'].startswith('73BF9877-')]
 palette=np.frombuffer(clut,dtype='<u2');alpha_hist={str(int(a)):int(n) for a,n in zip(*np.unique(rgba[:,:,3],return_counts=True))}
 renderer=ROOT/'windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c'
 manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Read-only source registration and reference exports for one future ComfyUI building pilot','pilot_description':'Dark modular three-floor rectangular blue-window facade, structural red/brown horizontal bands and narrow yellow marker. Clearly repeated on the right building in supplied Screenshot_4895. This is a facade tile, not a complete building model.','original_fullpage_key':KEY,'source_uv_half_open':ROI,'physical_source_rect_words':[768,0,16,64],'depth':0,'clut_xy':[0,480],'native_dimensions':[64,64],'cropped_exact_source_key':crop_key,'native_crop':ref(native_alias),'independent_native_source_proof':ref(native_path),'source_proof':[ref(p) for p in sorted(proof.iterdir())],'fullpage_source_proof':refs,'opaque_authoring_reference':ref(OUT/'facade-reference-nearest16x-1024.png'),'authoring_reference_is_nearest_preview_not_new_detail':True,'alpha_class_map':ref(OUT/'alpha-class-native-64x64.png'),'alpha_class_map_1024':ref(OUT/'alpha-class-nearest16x-1024.png'),'alpha_classes_and_counts':alpha_hist,'palette_1555_words':[int(v) for v in palette],'source_RGB_to_PSX_class_contract':'127 is non-STP colour;255 is STP. These are categorical PSX source classes, not ordinary visual opacity; do not apply a soft generative alpha. No class0 texels in this tile.','repeat_reference':ref(OUT/'facade-3x3-repeat-nearest4x-reference.png'),'repeat_and_uv_notes':['Same64x64source rectangle drawn at multiple world placements/perspectives, as exact source receipts show','Partial native v21..42 and42..63 band draws also observed; keep the three-floor divisions registered','No wrapped UV interval observed in the scoped receipts. Exact native mesh repeat/placement count is not proven by sampled logs','Top/bottom tile edges are not identical; the 3x3 preview exposes original seams. Preserve structural registration; do not invent a seamless period or move windows casually'],'verified_existing_source_aliases':aliases,'all_73BF_atlas_palette_keys':original_variants,'palette_guard':'Only5E9B9AC3 withCLUT[0,480] is proven for this facade. The other21palettekeys belong to a mixed atlas and must not automatically receive this material.','actual_draw_receipts':ref(OUT/'actual-draw-receipts.json'),'actual_draw_receipt_count':len(receipts),'actual_uv_variants':sorted({tuple(r['uv_bounds']) for r in receipts}),'screenshot_context':ref(OUT/'provided-city-screenshot-facade-context.png'),'provided_screenshot':ref(screenshot),'screenshot_pairing_limit':'Visual pattern correspondence to the supplied screenshot; historical draw receipts are not atomic with that user screenshot.','mipmaps':{'native_source_mip_assets_proven':0,'source_metadata_has_mip_chain':False,'renderer_generates_HD_mips':True,'runtime_source':ref(renderer),'runtime_lines':[2528,2532],'interpretation':'No separate authored/native mip files established. The current renderer usesGL_LINEAR_MIPMAP_LINEAR andglGenerateMipmap for HD replacements; live mip/seam acceptance still required.'},'proposed_future_render_canvas':[4096,4096],'future_canvas_contract':'4096square is64authoredpixelspernativeUVpixel for this64square tile. This reference export does not create or install that authored asset.','game_actions':0,'inference_submitted':False,'pack_or_runtime_mutations':False,'verification':{'original_fullpage_raw_palette_validity_decode':'PASS','bounded_raw_crc_palette_crc_and_independent_decode':'PASS','native_crop_pixel_exact_to_original':'PASS','PNG_roundtrip':'PASS'},'remaining':['Root gate after current game trial before inference','Canny/source registration and authored material review','Categorical class postprocess, exact region admission and all repeated UV/mip/seam live checks']}
 write(OUT/'manifest.json',manifest);print(json.dumps({'manifest':ref(OUT/'manifest.json'),'cropped_exact_source_key':crop_key,'alpha':alpha_hist,'source_aliases':len(aliases),'draw_receipts':len(receipts)}))
if __name__=='__main__':main()
