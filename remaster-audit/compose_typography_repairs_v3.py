"""Merge source-bound art edits, integer atlas enlargements and native admissions."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from stage_typography_candidate import read,write,ref
from compose_typography_repairs_v2 import checked_pixels,verify_new_native


def enlarge(pixels,target):
    h,w=target
    ph,pw=pixels.shape[:2]
    if (ph,pw)==(h,w): return pixels
    if h%ph or w%pw or h//ph!=w//pw or h<ph:
        raise ValueError('Only exact uniform integer parent enlargement is allowed')
    return np.repeat(np.repeat(pixels,h//ph,axis=0),w//pw,axis=1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--overlay',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Immutable output exists')
    parent=read(args.parent)
    bases={r['name'][:-4]:r for r in parent['files']}
    jobs=defaultdict(list)
    regions=[]
    for directory in args.overlay:
        manifest=read(directory/'manifest.json')
        for item in manifest.get('files',manifest.get('assets',[])):
            if item.get('new_exact_region_entry'):
                key=item['key']
                native_ref=ref(directory/'source-proof'/(key+'.png'))
                meta=read(directory/'source-proof'/(key+'.source.json'))
                item=dict(item,source_verified_new_key=True,source=native_ref,
                          native_dimensions=[meta['width_words']*(4>>meta['depth']),meta['height']],
                          full_rebuild=True,allow_integer_resolution_increase=True)
                plan=item['region_plan']
                regions.append(dict(key=key,source_rect=plan['source_rect'],depth=plan['depth'],
                    clut_xy=plan['clut_xy'],source_directory=str((directory/'pack').resolve()),
                    source_native=native_ref,source_metadata=ref(directory/'source-proof'/(key+'.source.json'))))
            jobs[item['key']].append((directory,manifest,item))
        regions.extend(manifest.get('exact_regions',[]))
    pack=args.output/'pack/einhander-texture-replacements'
    pack.mkdir(parents=True)
    (pack.parent/'Hashes.ini').write_text('')
    outputs=[]
    for key,edits in sorted(jobs.items()):
        is_new=key not in bases
        if is_new:
            item=edits[0][2]
            if not item.get('source_verified_new_key'): raise ValueError('Unverified new source '+key)
            baseline=item.get('source') if item.get('new_exact_region_entry') else item.get('parent',item.get('source'))
            native=item['native_dimensions']
            verify_new_native(key,baseline,native)
        else:
            r=bases[key]
            baseline=dict(path=r['composed_path'],sha256=r['sha256'])
            native=None
        original=checked_pixels(baseline)
        target=original.shape[:2]
        for directory,manifest,item in edits:
            info=item.get('outputs',{}).get('pack',item)
            with Image.open(info['path']) as im:
                shape=(im.height,im.width)
            if shape!=target:
                target=(max(target[0],shape[0]),max(target[1],shape[1]))
            native=item.get('native_dimensions',manifest.get('native_dimensions',native))
        base=enlarge(original,target)
        result=base.copy()
        used=np.zeros(target,bool)
        lineage=[]
        for directory,manifest,item in edits:
            info=item.get('outputs',{}).get('pack',item)
            pixels=checked_pixels(info)
            prior=item.get('parent',item.get('baseline',item.get('source')))
            if not prior: raise ValueError('Missing edit parent '+key)
            old=checked_pixels(prior)
            changed_canvas=pixels.shape!=old.shape
            if changed_canvas:
                nd=item.get('native_dimensions',manifest.get('native_dimensions'))
                if not (item.get('allow_integer_resolution_increase',manifest.get('allow_integer_resolution_increase')) and
                        item.get('full_rebuild',manifest.get('full_rebuild')) and nd):
                    raise ValueError('Missing declared source resolution contract '+key)
                if pixels.shape[1]%nd[0] or pixels.shape[0]%nd[1] or pixels.shape[1]//nd[0]!=pixels.shape[0]//nd[1]:
                    raise ValueError('Noninteger native replacement scale '+key)
            pixels=enlarge(pixels,target)
            old=enlarge(old,target)
            changed=np.any(pixels!=old,axis=2)
            selected=item.get('selected_native_regions')
            if selected:
                nd=item.get('native_dimensions',manifest.get('native_dimensions'))
                if not nd:
                    # Existing typography assets use sixteen authored pixels
                    # per original UV pixel, including256x8 upload aliases.
                    nd=[target[1]//16,target[0]//16]
                sx=target[1]//nd[0]
                sy=target[0]//nd[1]
                if sx!=sy: raise ValueError('Nonuniform UV scale '+key)
                allowed=np.zeros(target,bool)
                for x0,y0,x1,y1 in selected:
                    allowed[y0*sy:y1*sy,x0*sx:x1*sx]=True
                if np.any(changed&~allowed): raise ValueError('Edit escaped declared source regions '+key)
            conflict=changed&used&np.any(result!=pixels,axis=2)
            if conflict.any(): raise ValueError('Incompatible source-region edits '+key)
            unowned=changed&~used
            if np.any(np.any(base!=old,axis=2)&unowned):
                raise ValueError('Changed pixels depend on a different parent '+key)
            result[changed]=pixels[changed]
            used|=changed
            lineage.append(dict(manifest=ref(directory/'manifest.json'),output=ref(info['path']),parent=prior,
                selected_native_regions=selected,changed_pixels=int(changed.sum()),integer_enlargement=changed_canvas))
        if not np.array_equal(result[~used],base[~used]): raise ValueError('Protected pixel changed')
        output=pack/(key+'.png')
        Image.fromarray(result).save(output,compress_level=3)
        if not np.array_equal(checked_pixels(ref(output)),result): raise ValueError('PNG decode mismatch')
        row=dict(key=key,parent=baseline,outputs=dict(pack=dict(**ref(output),size=[target[1],target[0]])),
            composition=lineage,protected_outside_exact=True,
            protected_resolution_policy='Exact nearest integer enlargement of the immutable parent outside edited regions',
            changed_rgba_pixels=int(used.sum()),source_verified_new_key=is_new)
        if target!=original.shape[:2]:
            if not native: raise ValueError('Enlargement missing native dimensions '+key)
            row.update(native_dimensions=native,allow_integer_resolution_increase=True,full_rebuild=True,
                       previous_dimensions=[original.shape[1],original.shape[0]])
        outputs.append(row)
        print(json.dumps(dict(key=key,inputs=len(edits),size=[target[1],target[0]],changed_pixels=int(used.sum()))),flush=True)
    write(args.output/'manifest.json',dict(format=3,parent_candidate=ref(args.parent),builder=ref(__file__),
        method='Region-bound edits against hash-bound parents, normalized only by exact integer nearest enlargement',
        asset_count=len(outputs),files=outputs,exact_regions=regions,all_png_roundtrips_exact=True,live_acceptance=False))
    print(json.dumps(dict(output=str(args.output),assets=len(outputs),checks='PASS')))


if __name__=='__main__': main()
