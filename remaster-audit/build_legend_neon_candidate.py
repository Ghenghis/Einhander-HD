"""Prepare the approved ImageGen LEGEND trial against the final v4 compact parent.

No resizing of generated RGB, no runtime writes, no other replacement keys.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, sys

import numpy as np
from PIL import Image

from compose_typography_repairs_v2 import verify_new_native

AUDIT = Path(__file__).resolve().parent
ASSETS = AUDIT/'assets/neon/legend'
PARENT = AUDIT/'menu-restoration/typography-composed-v4/manifest.json'
REGION_PARENT = AUDIT/'menu-restoration/latin-world-sign-regions-v1/manifest.json'
OUTPUT = AUDIT/'menu-restoration/legend-neon-imagegen-candidate-v1'
KEY = '9AB7B731-1C8E76AE'

def ref(path):
    path = Path(path).resolve()
    return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def load(path): return json.loads(Path(path).read_bytes())
def pixels(path): return np.asarray(Image.open(path).convert('RGBA'))
def write(path,value): Path(path).write_text(json.dumps(value,indent=2)+'\n')

def build():
    if OUTPUT.exists(): raise ValueError('Immutable candidate exists: '+str(OUTPUT))
    parent_manifest = load(PARENT)
    parent_row = next(r for r in parent_manifest['files'] if r['key']==KEY)
    parent = parent_row['outputs']['pack']
    assert ref(parent['path'])['sha256']==parent['sha256']
    before = pixels(parent['path'])
    assert before.shape==(384,1024,4)
    region_row = next(r for r in load(REGION_PARENT)['files'] if r['key']==KEY)
    master_manifest = load(ASSETS/'legend-master-v1-manifest.json')
    master = ASSETS/'legend-master-v1.png'
    assert ref(master)['sha256']==master_manifest['master']['sha256']
    rgb = np.asarray(Image.open(master).convert('RGB'))
    assert rgb.shape==(768,2048,3)
    assert rgb.shape[1]//64 == rgb.shape[0]//24 == 32
    patch = np.dstack((rgb,np.full(rgb.shape[:2],127,np.uint8)))
    pack = OUTPUT/'pack/einhander-texture-replacements'
    proofdir = OUTPUT/'source-proof'
    pack.mkdir(parents=True)
    proofdir.mkdir()
    (pack.parent/'Hashes.ini').write_text('')
    source_proofs=[]
    for source in region_row['region_plan']['source_proof']:
        assert ref(source['path'])['sha256']==source['sha256']
        path=Path(source['path'])
        target=proofdir/path.name
        shutil.copyfile(path,target)
        source_proofs.append(ref(target))
        if path.suffix=='.bin': shutil.copyfile(path,pack.parent/path.name)
    native = proofdir/(KEY+'.png')
    verify_new_native(KEY,ref(native),[64,24])
    assert np.unique(pixels(native)[:,:,3]).tolist()==[127]
    target = pack/(KEY+'.png')
    Image.fromarray(patch).save(target,compress_level=3)
    assert np.array_equal(pixels(target),patch)
    assert np.array_equal(pixels(target)[:,:,:3],rgb)
    assert np.unique(pixels(target)[:,:,3]).tolist()==[127]
    assert list(pack.glob('*.png'))==[target]
    (pack.parent/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+KEY+' 880 56 16 24 0 32 482\n')
    shutil.copyfile(__file__,OUTPUT/'build-source.py')
    region = dict(key=KEY,source_rect=[880,56,16,24],depth=0,clut_xy=[32,482],
                  page_xy=[832,0],source_uv_half_open=[192,56,256,80],
                  source_fullpage_key='31214B41-1C8E76AE',source_directory=str(pack.parent),
                  source_native=ref(native),source_metadata=ref(proofdir/(KEY+'.source.json')),
                  source_proof=source_proofs)
    row = dict(key=KEY,parent={k:parent[k] for k in ('path','sha256')},
               outputs={'pack':dict(**ref(target),size=[2048,768])},
               native_dimensions=[64,24],selected_native_regions=[[0,0,64,24]],
               full_rebuild=True,allow_integer_resolution_increase=True,
               previous_dimensions=[1024,384],source_alpha_classes=[127],output_alpha_classes=[127],
               source_archives=source_proofs,region_plan=region,
               recipe={'method':'Approved built-in ImageGen RGB preserved exactly; add fixed PSX alpha127 to every texel',
                       'wording':'LEGEND OF / SUPER POWERS',
                       'material':'Brushed gold, compact bevels, cyan energy, deep blue backing, restrained violet accents',
                       'same_vector_contours':False,
                       'actual_resolution_note':'Actual 2048x768 generator output at32x native64x24; no artificial 4K dimensions claimed'},
               provenance={'master':ref(master),'master_manifest':ref(ASSETS/'legend-master-v1-manifest.json'),
                           'prompt':ref(ASSETS/'legend-master-v1-prompt.txt')},
               protected_outside_exact=True,
               protected_scope='Only this compact64x24 source region is replaced; all other keys and atlas content are external and untouched',
               live_acceptance='NOT RUN')
    write(OUTPUT/'manifest.json',dict(format=1,contract='source-bound-imagegen-compact-neon-v1',
          created_at_utc=datetime.now(timezone.utc).isoformat(),parent_composition=ref(PARENT),
          original_region_manifest=ref(REGION_PARENT),builder=ref(__file__),
          files=[row],exact_regions=[region],asset_count=1,production_installed=False,game_actions=0,
          live_acceptance='NOT RUN',all_png_roundtrips_exact=True,
          resolution_policy='Master RGB native output unchanged; uniform integer scale32x from64x24 native',
          limits=['Generated contours differ slightly from the prior vectors; wording and design were visually reviewed.',
                  'Actual near/far, motion, alpha and2160p visual acceptance require the parent game trial.']))
    report=dict(status='PASS',command='python remaster-audit/build_legend_neon_candidate.py',
                checked_at_utc=datetime.now(timezone.utc).isoformat(),
                assertions={'native_raw_clut_decode':True,'parent_hash_bound':True,
                            'rgb_byte_exact_to_approved_master':True,'output_alpha_127_only':True,
                            'dimensions_2048_768':True,'integer_native_scale_32':True,
                            'single_replacement_key':True,'png_roundtrip':True},
                manifest=ref(OUTPUT/'manifest.json'),output=ref(target),
                production_installed=False,game_actions=0,live_acceptance='NOT RUN')
    write(OUTPUT/'verification.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__': build()
