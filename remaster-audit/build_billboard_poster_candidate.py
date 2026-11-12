"""Integrate three generated photo masters with independently authored labels.

Only three source/draw/CLUT bindings identify these poster designs. Other
mixed-page palettes remain unchanged and are never counted as poster states.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from build_three_asset_proof import verify_stock

ROOT=Path(__file__).resolve().parents[1];AUDIT=ROOT/'remaster-audit';S=16
OUT=AUDIT/'world-sign-mapping/photoreal-poster-candidate-v2'
PARENT=AUDIT/'dev-center-evidence/typography-repair-20261112-v10/candidate.json'
MAP=AUDIT/'world-sign-mapping/poster-references-v1/poster-map-verified.json'
MASTERS=AUDIT/'assets/billboards/master-manifest-v1.json'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
GOTHIC=Path('C:/Windows/Fonts/cambria.ttc')
ITALIC=Path('C:/Windows/Fonts/arialbi.ttf')
BOLD=Path('C:/Windows/Fonts/arialbd.ttf')
SUBJECTS={'fallen-skull':'skull','leben-woman':'woman','volks-gasmaske':'gasmask'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pixels(p):
    with Image.open(p) as im:im.load();return np.asarray(im.convert('RGBA')).copy()
def decode(raw,clut,md):
    assert md['depth']==0
    words=np.frombuffer(raw,dtype='<u2').reshape(md['height'],md['width_words']);idx=np.empty((md['height'],md['width_words']*4),np.uint8)
    for c in range(4):idx[:,c::4]=(words>>(c*4))&15
    v=np.frombuffer(clut,dtype='<u2');pal=np.stack(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,np.where(v==0,0,np.where(v&32768,255,127))),axis=1).astype(np.uint8)
    return pal[idx]

def fraktur(text):
    result=''
    for c in text:
        if 'A'<=c<='Z':result+=chr(0x1D56C+ord(c)-ord('A'))
        elif 'a'<=c<='z':result+=chr(0x1D586+ord(c)-ord('a'))
        else:result+=c
    return result

def label_specs(poster):
    if poster['id'] in ['fallen-skull','leben-woman']:
        x0,y0,x1,y1=poster['header_region_local_uv']
        return [dict(text=poster['wording'],display=fraktur(poster['wording']),font=GOTHIC,font_index=1,
            native_box=[x0+.4,y0+.6,x1-.7,y1-.7],shadow_offset_native=[.65,.55],style='Cambria Math boldFraktur outlines; original Gothic casing/wording')]
    return [dict(text='VOLKS',display='VOLKS',font=ITALIC,font_index=0,native_box=[3,2,46,14],shadow_offset_native=[.55,.45],style='fresh industrial italic'),
        dict(text='GASMASKE',display='GASMASKE',font=ITALIC,font_index=0,native_box=[17,16,95,29],shadow_offset_native=[.55,.45],style='fresh industrial italic'),
        dict(text='VT',display='VT',font=BOLD,font_index=0,native_box=[85,112,95.5,119.2],shadow_offset_native=[0,0],style='fresh tiny source mark on darkplate')]

def mask_for_label(spec):
    font=ImageFont.truetype(str(spec['font']),512,index=spec['font_index'])
    temp=Image.new('L',(4000,900));d=ImageDraw.Draw(temp)
    d.text((20,20),spec['display'],font=font,fill=255)
    bbox=temp.getbbox();assert bbox
    ink=temp.crop(bbox);x0,y0,x1,y1=spec['native_box']
    target=(round((x1-x0)*S),round((y1-y0)*S));ink=ink.resize(target,Image.Resampling.LANCZOS)
    result=Image.new('L',(96*S,120*S));result.paste(ink,(round(x0*S),round(y0*S)))
    return np.asarray(result),dict(source_ink_bbox=list(bbox),target_size=list(target),font_size_authoring=512)

def vector_svg(poster):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="96" height="120" viewBox="0 0 96 120">',
        '<title>'+html.escape(poster['wording'])+' poster labels, separate vector layer</title>']
    for spec in label_specs(poster):
        font=ImageFont.truetype(str(spec['font']),512,index=spec['font_index'])
        _,metrics=mask_for_label(spec);bx0,by0,bx1,by1=metrics['source_ink_bbox'];x0,y0,x1,y1=spec['native_box']
        tt=TTFont(spec['font'],fontNumber=spec['font_index']);gs=tt.getGlyphSet();cmap=tt.getBestCmap();units=tt['head'].unitsPerEm
        baseline=20+font.getmetrics()[0]
        transform='translate('+f'{x0:.5f} {y0:.5f}'+') scale('+f'{(x1-x0)/(bx1-bx0):.8f} {(y1-y0)/(by1-by0):.8f}'+') translate('+f'{-bx0} {-by0}'+')'
        paths=[]
        for i,char in enumerate(spec['display']):
            if char==' ':continue
            pen=SVGPathPen(gs);gs[cmap[ord(char)]].draw(pen)
            x=20+font.getlength(spec['display'][:i+1])-font.getlength(char)
            paths.append('<path transform="translate('+f'{x:.6f} {baseline}'+') scale('+f'{512/units:.9f} {-512/units:.9f}'+')" d="'+pen.getCommands()+'"/>')
        label=html.escape(spec['text'],quote=True);parts.append('<g aria-label="'+label+'" transform="'+transform+'" fill="#eeeeee">')
        parts.extend(paths);parts.append('</g>');tt.close()
    parts.append('</svg>');return '\n'.join(parts)+'\n'

def photo_field(master_path,poster,native):
    with Image.open(master_path) as im:
        im.load();size=im.size;gray=ImageOps.grayscale(im.convert('RGB'))
    w,h=size;desired=.8
    if w/h>desired:
        cw=h*desired;box=((w-cw)/2,0,(w+cw)/2,h)
    else:
        ch=w/desired;box=(0,(h-ch)/2,w,(h+ch)/2)
    image=gray.resize((96*S,120*S),Image.Resampling.LANCZOS,box=box)
    lo=int(native[:,:,:3].min());hi=int(native[:,:,:3].max())
    luminance=lo+np.asarray(image).astype(float)*(hi-lo)/255
    labels=[]
    if poster['id']=='volks-gasmaske':
        luminance[111*S:120*S,84*S:96*S]=lo
    for spec in label_specs(poster):
        mask,metrics=mask_for_label(spec);a=mask.astype(float)/255
        dx,dy=spec['shadow_offset_native'];offset=Image.new('L',(96*S,120*S));offset.paste(Image.fromarray(mask),(round(dx*S),round(dy*S)))
        shadow=np.asarray(offset).astype(float)/255*.9
        luminance=luminance*(1-shadow)+lo*shadow
        luminance=luminance*(1-a)+hi*a
        labels.append(dict(text=spec['text'],display_codepoints=[f'U+{ord(c):04X}' for c in spec['display']],
            font=ref(spec['font']),font_collection_index=spec['font_index'],native_box=spec['native_box'],
            shadow_offset_native=list(spec['shadow_offset_native']),style=spec['style'],**metrics))
    channel=np.rint(np.clip(luminance,lo,hi)).astype(np.uint8);rgba=np.empty((120*S,96*S,4),np.uint8)
    rgba[:,:,:3]=channel[:,:,None];rgba[:,:,3]=127
    return rgba,dict(actual_master_size=list(size),native_poster_size=[96,120],authored_poster_size=[1536,1920],
        master_native_4k=False,resampling='Lanczos only; no synthetic grain or detail generation during integration',
        master_crop_box=list(box),master_to_texture_ratio=[1536/w,1920/h],source_luma_range=[lo,hi],labels=labels)

def classified_palettes(mapping,parent_keys):
    actual={p['key']:p for p in mapping['posters']};result=[]
    for asset in json.loads(QUEUE.read_bytes())['assets']:
        if not asset.get('source_verified') or not asset['key'].startswith(('31214B41-','A9D437BF-')):continue
        p=actual.get(asset['key'])
        result.append(dict(key=asset['key'],source_verified=True,clut_xy=asset['source_metadata']['clut_xy'],
            parent_key_present=asset['key'] in parent_keys,
            semantic_binding=p['id'] if p else 'mixed_atlas_no_verified_portrait_draw_binding',
            treatment='replace_only_verified_single_poster_ROI' if p else 'unchanged_not_counted_as_poster_state',
            selected_native_regions=[p['native_uv_half_open']] if p else []))
    return result

def visual(a):
    rgb=a[:,:,:3].copy();rgb[a[:,:,3]==0]=(12,23,39);return Image.fromarray(rgb)

def verify(out):
    m=json.loads((out/'manifest.json').read_bytes());mapping=json.loads(Path(m['poster_mapping']['path']).read_bytes())
    for field in ['parent_candidate','poster_mapping','generated_master_manifest','builder']:
        assert sha(m[field]['path'])==m[field]['sha256']
    posters={p['id']:p for p in mapping['posters']};checks=[]
    for r in m['files']:
        p=posters[r['poster_id']];key=r['key'];md,raw,clut=verify_stock(out/'sources',key);decoded=decode(raw,clut,md)
        assert np.array_equal(decoded,pixels(out/'sources'/(key+'.png')))
        for source in r['source_archives']:assert sha(source['path'])==source['sha256']
        assert sha(r['parent']['path'])==r['parent']['sha256'] and sha(r['generated_master']['path'])==r['generated_master']['sha256']
        assert sha(r['outputs']['pack']['path'])==r['outputs']['pack']['sha256']
        x0,y0,x1,y1=p['native_uv_half_open'];native=decoded[y0:y1,x0:x1]
        assert np.all(native[:,:,3]==127)
        field,info=photo_field(r['generated_master']['path'],p,native)
        actual=pixels(r['outputs']['pack']['path']);parent=pixels(r['parent']['path']);baseline=np.repeat(np.repeat(parent,2,0),2,1)
        assert actual.shape==(4096,4096,4)
        mask=np.zeros((4096,4096),bool);mask[y0*S:y1*S,x0*S:x1*S]=True
        assert np.array_equal(actual[~mask],baseline[~mask])
        assert np.array_equal(actual[y0*S:y1*S,x0*S:x1*S],field)
        assert np.array_equal(pixels(r['authored_poster']['path']),field)
        bands=[pixels(b['path']) for b in r['bands']]
        assert len(bands)==5 and all(b.shape==(384,1536,4) for b in bands)
        assert np.array_equal(np.concatenate(bands),field)
        assert info==r['art_registration']
        assert (out/'vector-labels'/(p['id']+'.svg')).read_text(encoding='utf-8')==vector_svg(p)
        checks.append(dict(key=key,poster=p['id'],source_crc_clut_decode_exact=True,opaque127_roi=True,
            outside_nearest2_parent_exact=True,master_and_vector_recipe_exact=True,all5_bands_concat_exact=True,
            final_poster_rgba_sha256=hashlib.sha256(field.tobytes()).hexdigest()))
    assert len(checks)==3 and {r['key'] for r in m['files']}=={p['key'] for p in mapping['posters']}
    result=dict(outcome='PASS',asset_count=3,checks=checks,
        other_mixed_palette_pages_changed=0,master_resolution_claim='1122x1402 generated detail;1536x1920resampled poster in4096atlas; not native4Kmaster',
        live_acceptance='NOT RUN; projected2160p still/motion/5bandmesh replay required',at_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps(result),flush=True);return result

def build(out,gas_master=None):
    if out.exists():raise ValueError('Immutable candidate exists')
    mapping=json.loads(MAP.read_bytes());parents={r['name'][:-4]:r for r in json.loads(PARENT.read_bytes())['files']}
    masters={r['subject']:r for r in json.loads(MASTERS.read_bytes())['artworks']}
    if gas_master is not None:
        gas_master=Path(gas_master).resolve()
        with Image.open(gas_master) as im:actual_size=list(im.size)
        masters['gasmask']=dict(subject='gasmask',**ref(gas_master),actual_generated_size=actual_size,
            native_4k=False,tool='built-in image_gen',scope='Selectively brighter lens rims/filter/hood edge variant; original dark master retained',
            original_dark_master=ref(AUDIT/'assets/billboards/gasmask-master-v1.png'))
    for folder in ['sources','masters','posters','bands','vector-labels','previews','pack/einhander-texture-replacements']:(out/folder).mkdir(parents=True,exist_ok=True)
    (out/'pack/Hashes.ini').write_text('');rows=[];masks={}
    for p in mapping['posters']:
        key=p['key'];assert key in parents
        original=next(Path(r['path']) for r in p['source_archives'] if r['path'].endswith('.png'))
        for source in p['source_archives']:assert sha(source['path'])==source['sha256']
        md,raw,clut=verify_stock(original.parent,key);decoded=decode(raw,clut,md);assert np.array_equal(decoded,pixels(original))
        source_refs=[]
        for suffix in ['.png','.words.bin','.clut.bin','.valid.bin','.source.json']:
            target=out/'sources'/(key+suffix);shutil.copyfile(original.with_suffix(suffix),target);source_refs.append(ref(target))
        master=masters[SUBJECTS[p['id']]];assert sha(master['path'])==master['sha256']
        master_path=out/'masters'/(SUBJECTS[p['id']]+'-generated-master.png');shutil.copyfile(master['path'],master_path)
        parent_path=Path(parents[key]['composed_path']);assert sha(parent_path)==parents[key]['sha256']
        parent=pixels(parent_path);assert parent.shape==(2048,2048,4)
        before=np.repeat(np.repeat(parent,2,0),2,1);after=before.copy()
        x0,y0,x1,y1=p['native_uv_half_open'];native=decoded[y0:y1,x0:x1];assert np.all(native[:,:,3]==127)
        field,registration=photo_field(master_path,p,native);after[y0*S:y1*S,x0*S:x1*S]=field
        selected=np.zeros((4096,4096),bool);selected[y0*S:y1*S,x0*S:x1*S]=True
        assert np.array_equal(after[~selected],before[~selected]);masks[key]=selected
        target=out/'pack/einhander-texture-replacements'/(key+'.png');Image.fromarray(after).save(target)
        poster_path=out/'posters'/(p['id']+'-1536x1920.png');Image.fromarray(field).save(poster_path)
        svg=out/'vector-labels'/(p['id']+'.svg');svg.write_text(vector_svg(p),encoding='utf-8')
        bands=[]
        for band in range(5):
            path=out/'bands'/(p['id']+f'-band{band+1}-1536x384.png');Image.fromarray(field[band*384:(band+1)*384]).save(path)
            bands.append(dict(**ref(path),local_native_uv=[0,band*24,96,(band+1)*24],atlas_native_uv=p['five_horizontal_strip_uvs'][band]))
        preview=Image.new('RGB',(1728,800),(12,23,39));d=ImageDraw.Draw(preview)
        for n,(label,pix) in enumerate([('Verified native / source-nearest6x',native),('Inherited parent / actual6x',before[y0*S:y1*S,x0*S:x1*S]),('Generated photo + fresh vector labels / actual6x',field)]):
            d.text((n*576+6,6),label,fill='white');preview.paste(visual(pix).resize((576,720),Image.Resampling.NEAREST if n==0 else Image.Resampling.LANCZOS),(n*576,28))
        d.text((8,760),p['wording']+' | generatedmaster1122x1402; moderateLanczos to1536x1920; opaque127; finalgameprojectionnotyetreviewed',fill='white')
        preview_path=out/'previews'/(p['id']+'-source-parent-photo-labels-actual6x.png');preview.save(preview_path)
        rows.append(dict(key=key,poster_id=p['id'],parent=ref(parent_path),source_archives=source_refs,
            native_dimensions=[256,256],selected_native_regions=[p['native_uv_half_open']],
            full_rebuild=True,allow_integer_resolution_increase=True,source_verified_new_key=False,
            outputs=dict(pack=dict(**ref(target),size=[4096,4096])),generated_master=ref(master_path),
            generated_tool_metadata=master,authored_poster=ref(poster_path),art_registration=registration,
            vector_labels=ref(svg),bands=bands,preview=ref(preview_path),protected_outside_exact=True,
            protected_outside_baseline='Entire parent8x image nearest2x; all RGBA outside exact96x120nativeposter ROI remain identical',
            alpha_class_in_roi=127,live_verified=False))
    np.savez_compressed(out/'changed-masks.npz',**masks);shutil.copyfile(__file__,out/'build-source.py')
    m=dict(schema_version=1,contract='source-bound-photoreal-posters-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        parent_candidate=ref(PARENT),poster_mapping=ref(MAP),generated_master_manifest=ref(MASTERS),builder=ref(out/'build-source.py'),
        asset_count=3,files=rows,changed_masks=ref(out/'changed-masks.npz'),palette_semantic_register=classified_palettes(mapping,set(parents)),
        wording=['Fallen?','Leben?','VOLKS','GASMASKE','VT'],
        method='Three builtinImageGen photoreal monochrome masters, independently sourcebound96x120posterROIs. Lanczos integrationonly, originalgrayscalelumarange, opaque127. FreshFraktur/industrialvectorlabels separatefromphoto. Wholemasters insertedbefore5x24bandchecks; alloutsideparent pixels preservedexactnearest2x.',
        actual_generated_master_dimensions=[1122,1402],authored_poster_dimensions=[1536,1920],atlas_dimensions=[4096,4096],
        generated_master_native_4k=False,
        source_palette_rule='Only three captured actualportraitCLUTbindings receive photos. Other mixedpageCLUTs remainunchanged; no13poster-state claim.',
        disjoint_other_work='31214posterROIsy136..255; LatinSIGNSagenttopbank writesy<136. No A9signchanges.',
        motion_and_animation='Singlecontinuouswholeimage spansfive24native-rowmeshbands; nativeframe/timing/rotationordering unproven. No independentbandupscale/repaint.',
        exposure_variant='selectively_brighter_gasmask' if gas_master is not None else 'original_dark_gasmask',
        original_dark_candidate=ref(AUDIT/'world-sign-mapping/photoreal-poster-candidate-v1/manifest.json') if gas_master is not None else None,
        gas_master_override=ref(gas_master) if gas_master is not None else None,
        live_verified=False,remaining=['Finalcandidate2160p actualposterprojection','Allfive meshbandsinmotion/transition','Allactualpalette/placementstates and semanticomissionaudit'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');result=verify(out)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--gas-master',type=Path,help='Explicit separately generated gas exposure variant; original dark candidate is preserved')
    args=ap.parse_args()
    if args.verify:verify(args.output.resolve())
    else:build(args.output.resolve(),args.gas_master)
