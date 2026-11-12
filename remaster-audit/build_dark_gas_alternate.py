"""Retain original dark gas artwork as a bounded alternate over lighter v2."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit';S=16
LIGHT=AUDIT/'world-sign-mapping/photoreal-poster-candidate-v2/manifest.json'
DARK=AUDIT/'world-sign-mapping/photoreal-poster-candidate-v1/manifest.json'
OUT=AUDIT/'world-sign-mapping/photoreal-poster-dark-gas-alternate-v1'
KEY='A9D437BF-502B076B';ROI=[0,0,96,120]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def mask():
    selected=np.zeros((4096,4096),bool);selected[:120*S,:96*S]=True;return selected

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes())
    for name in ['parent_candidate','dark_candidate','builder','comparison_preview']:
        assert sha(m[name]['path'])==m[name]['sha256']
    row=m['files'][0];assert row['key']==KEY and row['selected_native_regions']==[ROI]
    for name in ['parent','source_dark_output','generated_master','vector_labels']:
        assert sha(row[name]['path'])==row[name]['sha256']
    assert sha(row['outputs']['pack']['path'])==row['outputs']['pack']['sha256']
    light=pixels(row['parent']['path']);dark=pixels(row['source_dark_output']['path']);actual=pixels(row['outputs']['pack']['path'])
    selected=mask();expected=light.copy();expected[selected]=dark[selected]
    assert np.array_equal(actual,expected)
    assert np.array_equal(actual[~selected],light[~selected])
    assert np.array_equal(actual[selected],dark[selected])
    assert np.all(actual[:120*S,:96*S,3]==127)
    # The two other posters and all three vector label layers are unchanged
    # between the accepted lighter choice and the retained original artwork.
    lm=json.loads(Path(m['parent_candidate']['path']).read_bytes());dm=json.loads(Path(m['dark_candidate']['path']).read_bytes())
    drows={r['key']:r for r in dm['files']}
    for r in lm['files']:
        original=drows[r['key']]
        assert r['vector_labels']['sha256']==original['vector_labels']['sha256']
        if r['key']!=KEY:assert r['outputs']['pack']['sha256']==original['outputs']['pack']['sha256']
    result=dict(outcome='PASS',asset_count=1,dark_roi_exact_to_v1=True,outside_exact_to_light_v2=True,
        labels_unchanged=True,woman_skull_unchanged=True,roi_alpha127=True,
        live_acceptance='NOT RUN; light chosen as default, original dark retained for actualgamecomparison',
        at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result

def build(out):
    if out.exists():raise ValueError('Immutable alternate already exists')
    light_manifest=json.loads(LIGHT.read_bytes());dark_manifest=json.loads(DARK.read_bytes())
    light=next(r for r in light_manifest['files'] if r['key']==KEY)
    dark=next(r for r in dark_manifest['files'] if r['key']==KEY)
    for r in [light,dark]:assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
    baseline=pixels(light['outputs']['pack']['path']);old=pixels(dark['outputs']['pack']['path'])
    selected=mask();result=baseline.copy();result[selected]=old[selected]
    (out/'pack/einhander-texture-replacements').mkdir(parents=True);(out/'pack/Hashes.ini').write_text('')
    target=out/'pack/einhander-texture-replacements'/(KEY+'.png');Image.fromarray(result).save(target)
    np.savez_compressed(out/'changed-masks.npz',**{KEY:selected});shutil.copyfile(__file__,out/'build-source.py')
    preview=Image.new('RGB',(1152,800),(12,23,39));draw=ImageDraw.Draw(preview)
    for n,(label,a) in enumerate([('Original dark / retained backup',old),('Selectively brighter / chosen default',baseline)]):
        draw.text((n*576+6,7),label,fill='white')
        crop=Image.fromarray(a[:120*S,:96*S,:3]).resize((576,720),Image.Resampling.LANCZOS)
        preview.paste(crop,(n*576,28))
    draw.text((8,760),'Both original1122x1402generatedmasters retained. Samephotorealposterregistration andlabels. Actual2160pgametestpending.',fill='white')
    pp=out/'gas-exposure-dark-backup-vs-light-default-actual6x.png';preview.save(pp)
    darkmean=float(old[:120*S,:96*S,:3].mean());lightmean=float(baseline[:120*S,:96*S,:3].mean())
    m=dict(schema_version=1,contract='dark-gas-backup-over-light-default-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(LIGHT),dark_candidate=ref(DARK),builder=ref(out/'build-source.py'),asset_count=1,
        changed_masks=ref(out/'changed-masks.npz'),comparison_preview=ref(pp),
        default_choice='Lighter gas poster, per user preference; this one-key overlay is retained dark backup',
        files=[dict(key=KEY,parent=dict(**light['outputs']['pack']),source_dark_output=dict(**dark['outputs']['pack']),
            generated_master=dark['generated_master'],vector_labels=dark['vector_labels'],source_archives=dark['source_archives'],
            native_dimensions=[256,256],selected_native_regions=[ROI],full_rebuild=False,
            allow_integer_resolution_increase=False,source_verified_new_key=False,
            outputs=dict(pack=dict(**ref(target),size=[4096,4096])),protected_outside_exact=True,live_verified=False)],
        exposure_summary=dict(dark_poster_mean_luma=darkmean,light_poster_mean_luma=lightmean,
            qualification='Wholeposter mean includes unchangedwording and darkbackground; actualin-gamereadability remains a visual test'),
        retained_backups=[dark['generated_master'],ref(DARK),dict(**dark['outputs']['pack'])],
        live_verified=False,remaining=['Root actual2160p projectedposter test, lighter default first; dark overlay available for boundedcomparison'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');r=verify(out)
    (out/'verification.json').write_text(json.dumps(r,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=OUT);p.add_argument('--verify',action='store_true');args=p.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve())
