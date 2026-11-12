"""Read-only reconstruction and offline source-GP0 typography inspection."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def load(path):return json.loads(Path(path).read_bytes())
def pixels(path):return np.array(Image.open(path).convert('RGBA'))
def require(value,message):
 if not value:raise ValueError(message)
def checked(r):
 require(sha(r['path'])==r['sha256'],'Hash differs: '+str(r['path']));return pixels(r['path'])

def main(manifest_path,output):
 require(not output.exists(),'Choose new immutable review output')
 manifest=load(manifest_path);rows={r['key']:r for r in manifest['files']}
 parent=load(manifest['parent_candidate']['path']);parents={r['name'][:-4]:r for r in parent['files']}
 require(sha(manifest['parent_candidate']['path'])==manifest['parent_candidate']['sha256'],'Parent candidate changed')
 findings=[];checks=[]
 for key,row in rows.items():
  result=checked(row['outputs']['pack']);base=checked(row['parent']);expected=base.copy();owned=np.zeros(base.shape[:2],bool)
  for lineage in row['composition']:
   require(sha(lineage['manifest']['path'])==lineage['manifest']['sha256'],'Input manifest changed')
   before=checked(lineage['parent']);after=checked(lineage['output']);changed=np.any(before!=after,axis=2)
   require(int(changed.sum())==lineage['changed_pixels'],'Recorded delta count differs')
   require(not np.any(changed & owned & np.any(expected!=after,axis=2)),'Overlapping authors disagree: '+key)
   require(not np.any(changed & ~owned & np.any(base!=before,axis=2)),'New delta has a different base: '+key)
   expected[changed]=after[changed];owned|=changed
  require(np.array_equal(result,expected),'Final pixels differ from independent delta reconstruction: '+key)
  require(np.array_equal(result[~owned],base[~owned]),'Protected pixels changed: '+key)
  require(set(map(int,np.unique(result[:,:,3])))<={0,127,255},'Noncategorical PSX alpha: '+key)
  checks.append({'key':key,'lineage_inputs':len(row['composition']),'changed_pixels':int(owned.sum()),
   'delta_reconstruction_exact':True,'protected_outside_exact':True,'categorical_alpha_exact':True})
 bodydir=AUDIT/'menu-restoration/description-vector-candidate-v4';body=load(bodydir/'manifest.json');source=load(bodydir/'source-map.json')
 original=pixels(next(r['outputs']['pack']['path'] for r in body['files'] if r['key']=='BDAE4156-B88C038E'))
 merged=pixels(rows['BDAE4156-B88C038E']['outputs']['pack']['path']);body_diffs=[]
 for g in source['glyphs']:
  x0,y0,x1,y1=g['uv'];changed=np.any(merged[y0*16:y1*16,x0*16:x1*16]!=original[y0*16:y1*16,x0*16:x1*16],axis=2)
  if changed.any():body_diffs.append({'character':g['character'],'uv':g['uv'],'changed_pixels':int(changed.sum())})
 require([r['character'] for r in body_diffs]==['2'],'An existing nonnumeric body glyph was overwritten')
 resultsdir=AUDIT/'menu-restoration/results-vector-candidate-v2';results=load(resultsdir/'manifest.json')
 with np.load(resultsdir/'changed-masks.npz') as masks:resultsmask=masks['body']
 alias_checks=[]
 for row in results['files']:
  if row['key']=='8E1A509D-02491337':continue
  expected=pixels(row['outputs']['pack']['path']);actual=pixels(rows[row['key']]['outputs']['pack']['path'])
  start,end=(0,256) if row['key']=='BDAE4156-B88C038E' else (row['source_region'][1],row['source_region'][3])
  mask=resultsmask[start*16:end*16]
  require(np.array_equal(actual[mask],expected[mask]),'Results glyph/numeral/t shadow repair overwritten: '+row['key'])
  alias_checks.append({'key':row['key'],'supplement_pixel_field_exact':True})
 output.mkdir(parents=True);proofs=[]
 def actual(key):
  if key in rows:return pixels(rows[key]['outputs']['pack']['path'])
  return pixels(parents[key]['composed_path'])
 def draw_assignments(scene,lines,book,arm_words=None):
  assignments=[a for line in lines for a in line.get('assignments',[])]
  require(assignments,'No source-proven GP0 assignments')
  ys=[a['display_local_xy'][1] for a in assignments];min_y=min(ys);max_y=max(a['display_local_xy'][1]+a['source_uv_half_open'][3]-a['source_uv_half_open'][1] for a in assignments)
  if arm_words:
   min_y=min(min_y,min(w['draw']['display_local_xy'][1] for w in arm_words))
  canvas=Image.new('RGB',(1280,int((max_y-min_y+8)*4)+36),(12,23,39));d=ImageDraw.Draw(canvas)
  d.text((12,7),scene+' | OFFLINE source-GP0 layout at4x; class127 treated as opaque; no liveblend acceptance',fill='white')
  def paste(a,xy):
   rgb=Image.fromarray(a[:,:,:3]).resize((a.shape[1]//4,a.shape[0]//4),Image.Resampling.LANCZOS)
   alpha=Image.fromarray(np.where(a[:,:,3]>0,255,0).astype(np.uint8)).resize(rgb.size,Image.Resampling.NEAREST)
   canvas.paste(rgb,(xy[0]*4,36+(xy[1]-min_y)*4),alpha)
  for a in assignments:
   x0,y0,x1,y1=a['source_uv_half_open'];paste(book[y0*16:y1*16,x0*16:x1*16],a['display_local_xy'])
  if arm_words:
   for word in arm_words:
    x0,y0,x1,y1=word['native_local_uv'];paste(actual(word['key'])[y0*16:y1*16,x0*16:x1*16],word['draw']['display_local_xy'])
  path=output/(scene+'-offline-actual4x.png');canvas.save(path);proofs.append(ref(path))
 for scene in source['scenes']:
  draw_assignments(scene['scene'],scene['lines'],merged,source['arm_words'] if scene['scene']=='arm' else None)
 resultssource=load(resultsdir/'source-map.json')
 # Results labels occupy several independent columns; preserve their realXYs.
 draw_assignments('results',resultssource['lines'],merged)
 report={'outcome':'PASS','manifest':ref(manifest_path),'independent_delta_checks':checks,
  'existing_body_glyphs':37,'body_glyphs_unchanged_exact':36,'intentional_body_glyph_changes':body_diffs,
  'body_change_reason':'Only narrow2 differs; exact_results-vector-v2 pixels reproduced in merged canonical and aliases',
  'results_alias_checks':alias_checks,'offline_gp0_layout_proofs':proofs,
  'findings':findings,'game_actions':0,'live_acceptance':'NOT RUN',
  'limits':['Offline proofs preserve actual sourceGP0positions and binary visibility, but do not simulate modulation/semitransparent background blending.',
   'The34keycomposition does not include the new narrowfont candidate; finalv12composition needs its own validation.']}
 (output/'review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'output':str(output/'review.json'),'files_verified':len(checks),'body_unchanged':36,'findings':findings,'live_acceptance':'NOT RUN'}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.manifest.resolve(),a.output.resolve())
