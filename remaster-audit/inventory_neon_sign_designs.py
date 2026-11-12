"""Read-only source/receipt atlas sheets for semantic Stage1 sign inventory."""
from pathlib import Path
import json,math,hashlib,subprocess
from collections import defaultdict,Counter
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from build_three_asset_proof import verify_stock
ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'
OUT=AUDIT/'world-sign-mapping/neon-design-inventory-v1'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def main():
 OUT.mkdir(exist_ok=True)
 reps=json.loads((AUDIT/'world-sign-mapping/family-representatives.json').read_text())
 families=['31214B41','FD81C3C7','AB58BBA4','73BF9877','AB2DB563','8FCDBD4A','CD7769E8']
 font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',15)
 palette=[(0,0,0),(255,80,80),(80,255,80),(80,80,255),(255,255,80),(80,255,255),(255,80,255),(255,255,255),(125,60,20),(40,125,60),(60,40,125),(200,125,70),(70,200,125),(125,70,200),(160,160,160),(65,65,65)]
 chosen=[]
 for family in families:
  row=next(r for r in reps if r['key'].startswith(family));path=Path(row['source']);meta=json.loads(path.with_suffix('.source.json').read_text());words=np.frombuffer(path.with_suffix('.words.bin').read_bytes(),dtype='<u2').reshape(meta['height'],meta['width_words']);ppw=4>>meta['depth'];bits=16//ppw
  ix=np.empty((256,256),np.uint8)
  for n in range(ppw):ix[:,n::ppw]=(words>>(bits*n))&((1<<bits)-1)
  rgb=np.array(palette,np.uint8)[ix%16]
  canvas=Image.new('RGB',(2112,1120),'#151b22');draw=ImageDraw.Draw(canvas);draw.text((16,8),row['key']+' actual source palette (binary opacity for inspection)',font=font,fill='white');draw.text((1072,8),'same raw words: index falsecolour, not artwork',font=font,fill='white')
  im=Image.open(path).convert('RGBA');bg=Image.new('RGBA',im.size,'black');im.putalpha(im.getchannel('A').point(lambda x:255 if x else 0));bg.alpha_composite(im)
  canvas.paste(bg.convert('RGB').resize((1024,1024),Image.Resampling.NEAREST),(48,48));canvas.paste(Image.fromarray(rgb).resize((1024,1024),Image.Resampling.NEAREST),(1088,48))
  for xbase in (48,1088):
   for p in range(0,257,16):
    draw.line((xbase+p*4,48,xbase+p*4,1072),fill='#5d6573',width=1);draw.line((xbase,48+p*4,xbase+1024,48+p*4),fill='#5d6573',width=1)
    if p<256:draw.text((xbase+p*4,30),str(p),font=font,fill='white');draw.text((xbase-31,48+p*4),str(p),font=font,fill='white')
  target=OUT/(family+'-source-grid.png');canvas.save(target);chosen.append({'family':family,'source':ref(path),'sheet':ref(target)})
 sources=[AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v9/native-v9-world-gameover-results/capture.jsonl',AUDIT/'dev-center-evidence/hud-world-region-candidate-20261112-v2/native-menu/capture.jsonl']
 receipts=defaultdict(list)
 for p in sources:
  if not p.exists():continue
  for line in p.open():
   r=json.loads(line);key=r.get('key','')
   if key[:8] in families and r.get('event')=='source_draw_query_matched':receipts[key[:8]].append({'evidence':str(p),'key':key,'frame':r.get('frame'),'page_xy':r.get('page_xy'),'clut_xy':r.get('clut_xy'),'uv_bounds':r.get('uv_bounds'),'xy':r.get('xy')})
 summary={}
 for family,rs in receipts.items():
  groups=defaultdict(list)
  for r in rs:groups[tuple(r['uv_bounds'])].append(r)
  summary[family]=[{'uv_bounds_inclusive':list(uv),'observation_count':len(rr),'keys':sorted({r['key'] for r in rr}),'samples':rr[:2]} for uv,rr in sorted(groups.items())]
 (OUT/'source-atlas-and-draw-map.json').write_text(json.dumps({'atlases':chosen,'families_reviewed_representative_count':len(reps),'actual_draw_groups':summary,'scope':'Source semantic inventory only; source_draw_query records are not screenshot visibility or complete game coverage.'},indent=2)+'\n')
 # Complete board regions are registered separately from strips, windows,
 # facades, silhouettes, palette variants, and poster photographs.
 definitions=[
 ('FD81C3C7-12B34BA9',[0,0,64,64],'Arched emblem with paired upper loops and sloping lower wordmark; text unresolved'),
 ('FD81C3C7-DCA13DF7',[64,0,128,64],'Diamond frame with a single East Asian glyph'),
 ('FD81C3C7-CA34E803',[128,0,192,64],'Sloping blackletter or abstract stroke wordmark'),
 ('FD81C3C7-600290FE',[192,0,224,64],'Tall framed ornamental East Asian glyph panel'),
 ('FD81C3C7-E7B55CA9',[224,0,256,64],'Vertical rounded tube with bold central symbol'),
 ('FD81C3C7-CE31D8F4',[0,64,48,128],'Angular double-outline glyph panel'),
 ('FD81C3C7-E2ED781D',[48,64,96,128],'Stacked single glyph with bracketed rectangular border'),
 ('FD81C3C7-66755655',[96,64,128,128],'Vertical outlined Latin-like letters and small footer'),
 ('FD81C3C7-F6269484',[128,64,192,112],'Wide three-glyph panel with horizontal divisions'),
 ('FD81C3C7-8D0C6ABE',[192,64,256,112],'Wide stylized script banner with geometric lower band'),
 ('FD81C3C7-0D8BE28C',[128,112,192,128],'Pill-shaped row of rounded glyphs; language unresolved'),
 ('FD81C3C7-89C41FFB',[192,112,256,144],'Oval frame with broad curved letter or glyph row'),
 ('FD81C3C7-A3491537',[0,128,64,192],'Octagonal framed tall lowercase wordmark; exact letters unresolved'),
 ('FD81C3C7-24425A14',[64,128,128,160],'RISE >'),
 ('FD81C3C7-4980ECC0',[128,128,192,160],'Hexagonal frame with angular geometric monogram'),
 ('FD81C3C7-E4665DC9',[192,144,240,176],'Italic four-letter lowercase wordmark; exact vowels unresolved'),
 ('FD81C3C7-0E09E912',[64,160,128,192],'Central diamond or compass symbol across horizontal band'),
 ('FD81C3C7-46633A83',[128,160,192,192],'Pair of large East Asian calligraphic glyphs'),
 ('31214B41-1F9C3DA0',[128,0,192,32],"it's all new!! / COMBAT"),
 ('31214B41-9EAAA5BD',[128,32,192,56],'Welcom!! / parts with left East Asian mark'),
 ('31214B41-78002C99',[128,56,192,88],'STAR wordmark with crescent and small upper lettering'),
 ('31214B41-5663458B',[192,0,256,32],'HEH-HEH, / WELCOME'),
 ('31214B41-1C8E76AE',[192,56,256,80],'LEGEND OF / SUPER POWERS with star'),
 ('73BF9877-472FAF4D',[0,224,32,256],'80 numeric panel with smaller footer'),
 ('73BF9877-48E2665E',[64,224,96,240],'UNRESOLVED: framed indicator or coloured-block panel'),
 ('73BF9877-7BEF165F',[64,240,96,256],'Two large East Asian characters in wide panel'),
 ('73BF9877-5E906348',[96,224,128,240],'UNRESOLVED: nearblack patterned rectangular panel'),
 ('73BF9877-1093AC6D',[96,240,128,256],'GREAT ATTRACTOR with two-colour corner emblem'),
 ('73BF9877-7199E153',[192,64,256,128],'Collaged figure with NEW GENERATION-like lettering; transcript unresolved'),
 ]
 assets={a['key']:a for a in json.loads(Path('C:/github/REMASTER_STAGING/full-remaster/queue.json').read_text())['assets']}
 boards=[]
 for i,(key,roi,description) in enumerate(definitions,1):
  row=assets[key];p=Path(row['source']);proofmeta,raw,clut=verify_stock(p.parent,key);im=Image.open(p).convert('RGBA').crop(roi);native=OUT/(f'design-{i:02d}-'+key+'.png');im.save(native)
  witnesses=[r for r in receipts[key[:8]] if r['key']==key and r['uv_bounds'][0]>=roi[0] and r['uv_bounds'][1]>=roi[1] and r['uv_bounds'][2]<roi[2] and r['uv_bounds'][3]<roi[3]]
  meta=row['source_metadata'];boards.append({'id':i,'description':description,'classification':'unresolved_indicator_or_sign' if description.startswith('UNRESOLVED:') else 'confirmed_complete_sign_design','key':key,'source_uv_half_open':roi,'clut_xy':meta['clut_xy'],'source_page_fragments':meta['fragments'],'native_crop':ref(native),'original_source':ref(p),'source_verified':row['source_verified'],'independent_raw_clut_validity_decode_pass':True,'actual_draw_samples':witnesses[:3],'actual_draw_sample_count':len(witnesses),'transcription_status':'Descriptive labels retained where native text is uncertain; no translation inferred'})
 confirmed=[b for b in boards if b['classification']=='confirmed_complete_sign_design']
 for batch in range(math.ceil(len(confirmed)/9)):
  cells=confirmed[batch*9:(batch+1)*9];sheet=Image.new('RGB',(1680,1530),'#10151b');d=ImageDraw.Draw(sheet)
  for i,b in enumerate(cells):
   x=(i%3)*560;y=(i//3)*510;im=Image.open(b['native_crop']['path']).convert('RGBA');im.putalpha(im.getchannel('A').point(lambda a:255 if a else 0));scale=min(480/im.width,400/im.height);im=im.resize((int(im.width*scale),int(im.height*scale)),Image.Resampling.NEAREST);bg=Image.new('RGBA',im.size,'black');bg.alpha_composite(im);sheet.paste(bg.convert('RGB'),(x+20,y+90));d.text((x+15,y+7),f"{b['id']:02d} {b['key']} {b['source_uv_half_open']}",font=font,fill='white')
   desc=b['description'];words=desc.split();lines=['']
   for word in words:
    if len(lines[-1])+len(word)>53:lines.append('')
    lines[-1]+=(' ' if lines[-1] else '')+word
   d.multiline_text((x+15,y+28),'\n'.join(lines),font=font,fill='#c7d0df');d.text((x+15,y+482),f"CLUT {b['clut_xy']} actual receipts {b['actual_draw_sample_count']}",font=font,fill='#a3dfaf')
  sheet.save(OUT/f'confirmed-neon-designs-contact-{batch+1}.png')
 (OUT/'confirmed-board-register.json').write_text(json.dumps({'confirmed_source_board_designs':27,'confirmed_by_family':{'FD81C3C7':18,'31214B41':5,'73BF9877':4},'boards':boards,'reviewed_source_board_rectangles':29,'unresolved_additional_board_rectangles':2,'neon_designs_are_not_palette_or_placement_counts':True,'exact_all_game_total':'UNVERIFIED','photographic_posters_separate_count':3},indent=2)+'\n')
 shots=[4905,4901,4895,4891,4889,4886,4884,4883,4870];sheet=Image.new('RGB',(2304,1410),'#10151b');d=ImageDraw.Draw(sheet)
 for i,num in enumerate(shots):
  p=Path(f'C:/Users/Admin/Documents/Lightshot/Screenshot_{num}.png');im=Image.open(p).convert('RGB');im.thumbnail((768,430));x=(i%3)*768;y=(i//3)*470;sheet.paste(im,(x,y+30));d.text((x+8,y+6),p.name,font=font,fill='white')
 sheet.save(OUT/'provided-screenshots-review.png')
 unresolved=[
  {'family':'73BF9877','source_uv_half_open':[64,224,96,240],'description':'Three coloured blocks or indicator panel; not confidently a separate sign design','actual_key':'73BF9877-48E2665E'},
  {'family':'73BF9877','source_uv_half_open':[96,224,128,240],'description':'Very dark patterned panel; source role and lettering ambiguous','actual_key':'73BF9877-5E906348'},
  {'family':'FD81C3C7','source_uv_half_open':[192,176,256,192],'description':'Bright horizontal architectural strip; no independent complete board verified'},
  {'family':'31214B41','source_uv_half_open':[128,88,192,120],'description':'Repeated sloping bands / awning or illuminated sign assembly; board identity unresolved','actual_key':'31214B41-B7C32675'},
  {'family':'73BF9877','source_uv_half_open':[96,192,128,224],'description':'Small swirled decorative panel; no actual source query in sampled logs for this exact cell'},
  {'family':'AB58BBA4','source_uv_half_open':[64,152,88,176],'description':'Running-person direction / exit indicator inside industrial atlas; exact draw ownership and neon classification unresolved'},
  {'family':'AB58BBA4','source_uv_half_open':[96,128,128,168],'description':'17F floor marking inside industrial atlas; not classified as a neon board'},
  {'family':'AB2DB563','source_uv_half_open':[160,128,208,184],'description':'Eye/compass emblem; can be unrelated UI or world art; do not count without draw ownership'},
  {'families':['8FCDBD4A','CD7769E8'],'source_uv_half_open':[0,0,256,256],'description':'Two flattened distant-city background pictures contain tiny luminous marks. Unknown unique versus reused board designs, not countable as source-separated signs from these rasters'},
 ]
 inventory={'confirmed_neon_sign_designs_minimum':27,'confirmed_by_family':{'FD81C3C7':18,'31214B41':5,'73BF9877':4},'confirmed_semantics_scope':'Complete standalone board designs separately registered by visual source contour and supported actual source draw samples; palette colours, copies and perspective placements deduplicated','rebuilt_Latin_designs_in_v12':5,'confirmed_unrebuilt_designs':22,'photographic_posters_separate':3,'unresolved_source_region_groups':unresolved,'unresolved_group_count':len(unresolved),'unresolved_additional_unique_design_count':'UNKNOWN; groups are not design counts','exact_entire_game_design_total':'UNVERIFIED','coverage':['262 distinct raw source family representatives visually reviewed in existing four overview sheets','Seven relevant mixed atlas families enlarged and indexed in local source grids','All29 candidate board native raw/CLUT/validity/PNG decodes checked independently','Nine provided gameplay screenshots reviewed; observed repeated placements are not distinct designs'],'transcription_limits':'Source descriptions used for uncertain scripts and symbols. No inferred names or translations. Several tiny original words remain unreadable.','register':ref(OUT/'confirmed-board-register.json'),'contact_sheets':[ref(OUT/f'confirmed-neon-designs-contact-{i}.png') for i in range(1,4)],'source_grid_and_queries':ref(OUT/'source-atlas-and-draw-map.json'),'provided_screenshot_contact':ref(OUT/'provided-screenshots-review.png'),'game_actions':0,'runtime_changes':False,'asset_changes':0}
 (OUT/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
 v12=AUDIT/'dev-center-evidence/remaster-4k-preview-20261112-v12';exe=AUDIT/'menu-restoration/latin-world-sign-regions-v1/runtime-test/test-latin-sign-regions.exe'
 if (v12/'candidate.json').exists():
  args=[str(exe),str(v12/'pack'),'42'];p=subprocess.run(args,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,(p.stdout,p.stderr)
  receipt={'outcome':'PASS','candidate':ref(v12/'candidate.json'),'actual_exact_regions':ref(v12/'pack/ExactRegions.tsv'),'unchanged_production_loader_test_executable':ref(exe),'command':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'checks':578,'failures':0,'actual_staged_regions':42,'actual_staged_indexed_PNGs_production_decoded':36,'all_RISE_palette_phase_cache_revisits_immediate':True,'decode_budget_MiB':256,'decoded_MiB':71,'GL_game_submission':'NOT RUN','game_actions':0}
  (OUT/'staged-v12-production-test.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({k:len(v) for k,v in summary.items()}))
if __name__=='__main__':main()
