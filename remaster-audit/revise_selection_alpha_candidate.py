"""Refine only D036 selection contour alpha; preserve every accepted RGB byte."""
from datetime import datetime,timezone
import hashlib,importlib.util,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'remaster-audit/menu-restoration/palette-field-candidate-v7'
OUT=ROOT/'remaster-audit/menu-restoration/palette-field-candidate-v8'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if OUT.exists():raise ValueError('Choose a new isolated immutable menu revision')
    manifest=json.loads((BASE/'manifest.json').read_bytes());assets=manifest['assets']
    if len(assets)!=12 or sum(a['key'].startswith('D0365088-') for a in assets)!=2:raise ValueError('Expected complete twelve-key menu-v7')
    for a in assets:
        for v,item in a['outputs'].items():
            if sha(Path(item['path']))!=item['sha256']:raise ValueError('Prior menu artifact changed')
    OUT.mkdir()
    for d in ['pack','strict-mask-pack','masters','previews']:shutil.copytree(BASE/d,OUT/d)
    for name in ['palette-contour-library.py','menu-field-library.py']:
        if (BASE/name).exists():shutil.copy2(BASE/name,OUT/name)
    shutil.copy2(__file__,OUT/'build-source.py')
    spec=importlib.util.spec_from_file_location('selection_alpha_hud',ROOT/'windows-x64/tools/build_hud_ui_candidate.py');hud=importlib.util.module_from_spec(spec);spec.loader.exec_module(hud)
    changes=[]
    for a in assets:
        prior={k:dict(v) for k,v in a['outputs'].items()}
        for variant,item in a['outputs'].items():item['path']=str(OUT/variant/'einhander-texture-replacements'/(a['key']+'.png'))
        if not a['key'].startswith('D0365088-'):
            for variant,item in a['outputs'].items():
                if sha(Path(item['path']))!=prior[variant]['sha256']:raise ValueError('Unrelated menu key changed')
            a['revision']='Byte-identical accepted v7 output';continue
        metadata,raw,clut=hud.verify_stock(Path(a['source']).parent,a['key']);indices,palette=hud.decode_indices(raw,metadata),hud.palette_rgba(clut)
        with np.load(BASE/'masters/D0365088.npz',allow_pickle=False) as master:
            if not np.array_equal(indices,master['native_indices']):raise ValueError('Selection master differs from independently verified source')
            contours=master['contour_indices'].copy()
        with Image.open(prior['pack']['path']) as image:before=np.array(image.convert('RGBA'))
        restored=before.copy();selected=np.zeros(before.shape[:2],bool)
        for x0,y0,x1,y1 in a['selected_native_regions']:selected[y0*16:y1*16,x0*16:x1*16]=True
        alpha=palette[contours,3];restored[:,:,3][selected]=alpha[selected]
        if not np.array_equal(restored[:,:,:3],before[:,:,:3]) or not np.array_equal(restored[~selected],before[~selected]):raise ValueError('RGB or protected outside region changed')
        if not set(np.unique(restored[:,:,3]))<={0,127,255}:raise ValueError('Noncategorical contour alpha')
        target=Path(a['outputs']['pack']['path']);Image.fromarray(restored).save(target)
        with Image.open(target) as image:
            if image.tobytes()!=restored.tobytes():raise ValueError('Written selection PNG roundtrip mismatch')
        a['outputs']['pack']['sha256']=sha(target)
        if sha(Path(a['outputs']['strict-mask-pack']['path']))!=prior['strict-mask-pack']['sha256']:raise ValueError('Strict comparison changed')
        a['revision']='Only main categorical contour alpha refined; entire v7 RGB unchanged and strict output copied byte-for-byte'
        a['checks']['main_original_alpha_footprint_exact']=False
        a['checks']['native_center_alpha_classes_exact']=bool(np.array_equal(restored[8::16,8::16,3],palette[indices][:,:,3]))
        a['checks']['main_rgb_byte_exact_to_v7']=True;a['checks']['main_contour_alpha_categorical']=True;a['checks']['outside_selected_rgba_exact_to_v7']=True;a['checks']['strict_output_byte_exact_to_v7']=True
        a['changed_alpha_pixels_vs_v7']=int(np.count_nonzero(restored[:,:,3]!=before[:,:,3]));changes.append({'key':a['key'],'alpha_pixels_changed':a['changed_alpha_pixels_vs_v7'],'rgb_bytes_changed':0})
        if a['key']=='D0365088-79902A90':
            box=(0,168,248,232);crop=tuple(v*16 for v in box);size=(992,256)
            def view(data):
                x0,y0,x1,y1=crop;v=data[y0:y1,x0:x1,:3].copy();v[data[y0:y1,x0:x1,3]==0]=0;return Image.fromarray(v).resize(size,Image.Resampling.LANCZOS)
            preview=Image.new('RGB',(992,568),(10,14,25));d=ImageDraw.Draw(preview);d.text((6,4),'V7 RESTRAINED RGB / ORIGINAL ALPHA FOOTPRINT',fill='white');preview.paste(view(before),(0,24));d.text((6,288),'V8 IDENTICAL RGB / CONTINUOUS CATEGORICAL CONTOUR ALPHA',fill='white');preview.paste(view(restored),(0,312));preview.save(OUT/'previews/D0365088-alpha-only-actual4x.png')
        print(json.dumps(changes[-1]),flush=True)
    manifest['contract']='verified-menu-d036-alpha-v8';manifest['created_at_utc']=datetime.now(timezone.utc).isoformat();manifest['revision_source']=str(BASE);manifest['revision_source_manifest_sha256']=sha(BASE/'manifest.json');manifest['revision']='Only two D036 main alpha maps refined to existing continuous source contours. Both main RGB planes, all twelve strict PNGs and ten other main PNGs remain byte-identical to v7.';manifest['d036_method']='Use existing source-index continuous alpha classes. Preserve restrained v7 RGB lighting exactly; no shade inversion or etched-RGB reconstruction.';manifest['tool_sha256']=sha(Path(__file__));manifest['revision_checks']={'changed_main_keys':2,'unchanged_main_keys':10,'unchanged_strict_keys':12,'changed_rgb_bytes':0,'changed_alpha':changes};manifest['live_acceptance']='pending final fighter/title/badge state review; actual output has not been observed in runtime'
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');print(json.dumps({'pack':str(OUT/'pack'),'assets':12,'changed_main_keys':2,'unchanged_main_keys':10,'unchanged_strict_keys':12,'checks':'PASS'}))

if __name__=='__main__':main()
