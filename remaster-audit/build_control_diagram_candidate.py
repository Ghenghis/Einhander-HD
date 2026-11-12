"""Restore mapped controller/selection line art while preserving menu lettering."""
from datetime import datetime,timezone
import hashlib,importlib.util,json
from pathlib import Path
import shutil
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'remaster-audit/menu-restoration/palette-field-candidate-v7'
OUT=ROOT/'remaster-audit/menu-restoration/control-diagram-candidate-v1'
QUEUE=Path('C:/github/REMASTER_STAGING/full-remaster/queue.json')
HUD=ROOT/'windows-x64/tools/build_hud_ui_candidate.py'
MENU=BASE/'build-source.py'
REGIONS={'1AD90FC9':[(224,40,256,74),(144,96,212,152),(96,160,160,232)],
         'E6B65424':[(144,112,192,124),(0,124,96,140),(0,140,100,188)]}
ROLES={'1AD90FC9':['controller face-button diagram','rotary ARM/SELECT illustration','directional controller illustration'],
       'E6B65424':['triangle/circle/square/cross symbols','Gunpod slot indicators and panel top line','diagonal panel outline and original fill']}

def sha(data):return hashlib.sha256(data).hexdigest()

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def evidence():
    paths=list((ROOT/'windows-x64/tools/research-runs').glob('*/native/capture.jsonl'))
    paths+=list((ROOT/'remaster-audit/dev-center-evidence').glob('*/*/capture.jsonl'))
    result={family:[] for family in REGIONS}
    for p in sorted(set(paths)):
        for i,line in enumerate(p.read_text().splitlines(),1):
            try:e=json.loads(line)
            except json.JSONDecodeError:continue
            f=e.get('key','').split('-')[0]
            if f not in result or e.get('event')!='source_draw_query_matched' or len(result[f])>=100:continue
            u=e.get('uv_bounds')
            if not u:continue
            matches=[j for j,(x0,y0,x1,y1) in enumerate(REGIONS[f]) if u[0]<x1 and u[2]>=x0 and u[1]<y1 and u[3]>=y0]
            if matches:result[f].append({'path':str(p),'line':i,'key':e['key'],'frame':e['frame'],'uv_bounds':u,'xy':e.get('xy'),'source_word_xy':e.get('source_word_xy'),'native_words':e.get('native_words'),'intersected_region_indices':matches})
    return result

def main():
    if OUT.exists():raise ValueError('Existing diagram candidates are immutable; choose another output')
    cv2.setNumThreads(2);hud=module(HUD,'diagram_hud');menu=module(MENU,'diagram_menu')
    source_rows=[r for r in json.loads(QUEUE.read_bytes())['assets'] if r['key'].split('-')[0] in REGIONS]
    if len(source_rows)!=6 or not all(r['source_verified'] for r in source_rows):raise ValueError('Expected six verified diagram palette keys')
    receipts=evidence()
    for d in ('pack/einhander-texture-replacements','strict-mask-pack/einhander-texture-replacements','previews'):(OUT/d).mkdir(parents=True,exist_ok=True)
    for d in ('pack','strict-mask-pack'):(OUT/d/'Hashes.ini').write_text('',encoding='utf-8')
    shutil.copy2(__file__,OUT/'build-source.py');shutil.copy2(HUD,OUT/'palette-contour-library.py');shutil.copy2(MENU,OUT/'menu-field-library.py')
    rows=[];seen=set()
    for row in source_rows:
        key=row['key'];family=key.split('-')[0];source=Path(row['source']);m,raw,clut=hud.verify_stock(source.parent,key)
        indices,palette=hud.decode_indices(raw,m),hud.palette_rgba(clut);decoded=palette[indices]
        if sha(raw)!=row['raw_sha256'] or sha(clut)!=row['clut_sha256'] or sha(decoded.tobytes())!=row['source_pixel_sha256']:raise ValueError('Independent source mismatch:'+key)
        contours,selected=menu.menu_contour_indices(indices,16,REGIONS[family])
        restored,nearest=menu.menu_render(indices,contours,palette,REGIONS[family],lighting=.06,rim_strength=.08)
        if not np.array_equal(restored[~selected],nearest[~selected]):raise ValueError('Diagram processing escaped bounds')
        basepath=BASE/'pack/einhander-texture-replacements'/(key+'.png')
        with Image.open(basepath) as im:baseline=np.array(im.convert('RGBA'))
        authored=baseline.copy();authored[selected]=restored[selected]
        if not np.array_equal(authored[~selected],baseline[~selected]):raise ValueError('Protected menu text/artwork changed')
        strict=authored.copy();strict[:,:,3][selected]=nearest[:,:,3][selected]
        if not set(np.unique(authored[:,:,3]))<={0,127,255}:raise ValueError('Noncategorical alpha')
        outputs={}
        for mode,data in (('pack',authored),('strict-mask-pack',strict)):
            path=OUT/mode/'einhander-texture-replacements'/(key+'.png');Image.fromarray(data).save(path)
            with Image.open(path) as check:
                if check.tobytes()!=data.tobytes():raise ValueError('PNG roundtrip changed pixels')
            outputs[mode]={'path':str(path),'sha256':sha(path.read_bytes()),'size':[4096,4096]}
        if family not in seen:
            samples=[]
            for i,box in enumerate(REGIONS[family]):
                x0,y0,x1,y1=box;size=((x1-x0)*4,(y1-y0)*4)
                old=Image.fromarray(decoded[y0:y1,x0:x1,:3]).resize(size,Image.Resampling.NEAREST)
                new=Image.fromarray(authored[y0*16:y1*16,x0*16:x1*16,:3]).resize(size,Image.Resampling.LANCZOS)
                samples.append((ROLES[family][i],old,new))
            height=sum(max(a.height,b.height)+30 for _,a,b in samples)
            canvas=Image.new('RGB',(max(800,max(a.width+b.width+20 for _,a,b in samples)),height),(12,17,25));d=ImageDraw.Draw(canvas);y=0
            for label,a,b in samples:d.text((5,y+4),label+' | source x4 / restored x4',fill='white');canvas.paste(a,(0,y+25));canvas.paste(b,(a.width+20,y+25));y+=max(a.height,b.height)+30
            canvas.save(OUT/'previews'/(family+'-line-art-actual4x.png'));seen.add(family)
        rows.append({'key':key,'source':str(source),'source_sha256':sha(source.read_bytes()),'source_words_sha256':sha(raw),'source_clut_sha256':sha(clut),'source_metadata':m,'base':str(basepath),'base_sha256':sha(basepath.read_bytes()),'selected_native_regions':REGIONS[family],'roles':ROLES[family],'outputs':outputs,'checks':{'raw_crc_clut_decode_exact':True,'outside_selected_regions_byte_exact_to_v7':True,'categorical_classes_only':True,'png_roundtrip_exact':True},'changed_rgb_pixels':int(np.any(authored[:,:,:3]!=baseline[:,:,:3],axis=2).sum()),'changed_alpha_pixels':int(np.count_nonzero(authored[:,:,3]!=baseline[:,:,3])),'draw_evidence_intersecting_regions':receipts[family],'in_game_acceptance':'pending actual fighter/controller/instruction state review'})
        print(json.dumps({'key':key,'protected_outside_exact':True}),flush=True)
    manifest={'format':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),'asset_count':len(rows),'production_installed':False,'game_actions':0,'method':'Shared continuous source palette fields reconstruct line-art contours and original shading, with restrained6percent directional bevel/8percent rim. No invented geometry or substitute diagrams. All accepted menu-v7 text/outside artwork remains byte-identical.','base_manifest_sha256':sha((BASE/'manifest.json').read_bytes()),'tool_sha256':sha(Path(__file__).read_bytes()),'assets':rows,'limits':['Actual game visibility/animation/blending remains pending for every illustrated state.','Main output refines categorical contour coverage; strict-mask-pack retains the original native alpha footprint inside the bounded diagrams as a comparison.','Archived draw queries merely intersect these source regions; they do not prove full illustration visibility or acceptance.','This pack does not alter fighter3Dgeometry, world art or untextured GPU-drawn panels/grids.']}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pack':str(OUT/'pack'),'assets':len(rows),'checks':'PASS','manifest':str(OUT/'manifest.json')}))

if __name__=='__main__':main()
