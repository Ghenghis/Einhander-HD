"""Merge independently bounded typography edits without replacing other authors' pixels."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from stage_typography_candidate import read, write, ref
from build_three_asset_proof import verify_stock


def verify_new_native(key, baseline, native):
    """Require exact native words, CLUT and decoded pixels before adding a key."""
    path=Path(baseline['path'])
    metadata, raw, clut=verify_stock(path.parent,key)
    nw,nh=native
    depth=metadata['depth']
    ppw={0:4,1:2,2:1}[depth]
    if metadata['width_words']*ppw!=nw or metadata['height']!=nh:
        raise ValueError('New-key native dimensions differ '+key)
    words=np.frombuffer(raw,dtype='<u2').reshape(nh,metadata['width_words'])
    if depth<2:
        indices=np.empty((nh,nw),np.uint16)
        bits=4 if depth==0 else 8
        for n in range(ppw): indices[:,n::ppw]=(words>>(n*bits))&((1<<bits)-1)
        colors=np.frombuffer(clut,dtype='<u2')[indices]
    else:
        colors=words
    expected=np.stack(((colors&31)<<3,((colors>>5)&31)<<3,((colors>>10)&31)<<3,
        np.where(colors==0,0,np.where(colors&0x8000,255,127))),axis=2).astype(np.uint8)
    if not np.array_equal(checked_pixels(baseline),expected):
        raise ValueError('New-key native PNG differs from raw/CLUT decode '+key)


def checked_pixels(item):
    path = Path(item['path'])
    if ref(path)['sha256'] != item['sha256']:
        raise ValueError('Input hash changed: ' + str(path))
    with Image.open(path) as image:
        return np.array(image.convert('RGBA'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Immutable output already exists')
    parent = read(args.parent)
    base_rows = {r['name'][:-4]: r for r in parent['files']}
    grouped = defaultdict(list)
    for directory in args.overlay:
        manifest = read(directory/'manifest.json')
        for item in manifest.get('files', manifest.get('assets', [])):
            grouped[item['key']].append((directory, manifest, item))
    pack = args.output/'pack/einhander-texture-replacements'
    pack.mkdir(parents=True)
    (pack.parent/'Hashes.ini').write_text('')
    rows = []
    for key, edits in sorted(grouped.items()):
        is_new=key not in base_rows
        if is_new:
            if len(edits)!=1:
                raise ValueError('New-key source must have one full rebuild '+key)
            directory,manifest,item=edits[0]
            if not item.get('source_verified_new_key') or not item.get('full_rebuild'):
                raise ValueError('Unverified addition '+key)
            parent_ref=item['parent']
            verify_new_native(key,parent_ref,item['native_dimensions'])
        else:
            source = base_rows[key]
            parent_ref = dict(path=source['composed_path'], sha256=source['sha256'])
        base = checked_pixels(parent_ref)
        if len(edits) == 1:
            directory, manifest, item = edits[0]
            output = item.get('outputs', {}).get('pack', item)
            pixels = checked_pixels(output)
            if pixels.shape != base.shape:
                previous = checked_pixels(item.get('parent', item.get('baseline')))
                native = item.get('native_dimensions', manifest.get('native_dimensions'))
                permitted = item.get('allow_integer_resolution_increase', manifest.get('allow_integer_resolution_increase'))
                complete = item.get('full_rebuild', manifest.get('full_rebuild'))
                if not permitted or not complete or not native or not np.array_equal(previous,base):
                    raise ValueError('Unproven full-image resolution change '+key)
                nw,nh = native
                h,w = pixels.shape[:2]
                bh,bw = base.shape[:2]
                if not (0<nw<=w<=16384 and 0<nh<=h<=16384 and w%nw==0 and h%nh==0 and
                        w//nw==h//nh and w>bw and h>bh and w*bh==h*bw):
                    raise ValueError('Resolution increase changes native aspect or integer scale '+key)
                path=pack/(key+'.png')
                Image.fromarray(pixels).save(path,compress_level=3)
                if not np.array_equal(checked_pixels(ref(path)),pixels):
                    raise ValueError('PNG roundtrip failed '+key)
                rows.append(dict(key=key,parent=parent_ref,outputs=dict(pack=dict(**ref(path),size=[w,h])),
                    full_rebuild=True,allow_integer_resolution_increase=True,native_dimensions=native,
                    source_verified_new_key=is_new,
                    composition=[dict(manifest=ref(directory/'manifest.json'),output=ref(output['path']),
                        parent=item.get('parent',item.get('baseline')),full_source_bitmap_rebuilt=True)],
                    previous_dimensions=[bw,bh],protected_outside_exact='entire native source bitmap rebuilt'))
                print(json.dumps(dict(key=key,inputs=1,resolution_increased_from=[bw,bh],dimensions=[w,h])),flush=True)
                continue
        result = base.copy()
        used = np.zeros(base.shape[:2], bool)
        lineage = []
        for directory, manifest, item in edits:
            output = item.get('outputs', {}).get('pack', item)
            pixels = checked_pixels(output)
            prior_ref = item.get('parent', item.get('baseline'))
            if not prior_ref:
                raise ValueError('Typography edit has no explicit parent ' + key)
            previous = checked_pixels(prior_ref)
            if pixels.shape != base.shape or previous.shape != base.shape:
                raise ValueError('Canvas dimensions changed ' + key)
            changed = np.any(pixels != previous, axis=2)
            regions = item.get('selected_native_regions')
            if regions:
                allowed = np.zeros(changed.shape, bool)
                # Strip dimensions are native256x8; rows already use local UVs.
                sx = 16
                sy = 16
                for x0,y0,x1,y1 in regions:
                    allowed[int(y0*sy):int(y1*sy),int(x0*sx):int(x1*sx)] = True
                if np.any(changed & ~allowed):
                    raise ValueError('Edit escaped declared text rectangles ' + key)
            # Every edit starts from its own verified parent. A newer parent is
            # permitted only if its already-authored pixels remain untouched.
            conflict = changed & used & np.any(result != pixels, axis=2)
            if conflict.any():
                raise ValueError('Incompatible overlapping typography pixels ' + key)
            unowned = changed & ~used
            if np.any(np.any(base != previous, axis=2) & unowned):
                raise ValueError('Edit depends on a different parent within its changed pixels ' + key)
            result[changed] = pixels[changed]
            used |= changed
            lineage.append(dict(manifest=ref(directory/'manifest.json'), parent=prior_ref,
                output=ref(output['path']), changed_pixels=int(changed.sum()),
                declared_native_regions=regions, protected_outside_actual_change=True))
        if not np.array_equal(result[~used], base[~used]):
            raise ValueError('Composition changed protected pixels')
        output_path = pack/(key+'.png')
        Image.fromarray(result).save(output_path, compress_level=3)
        if not np.array_equal(checked_pixels(ref(output_path)), result):
            raise ValueError('PNG roundtrip failed ' + key)
        rows.append(dict(key=key, parent=parent_ref, outputs=dict(pack=dict(**ref(output_path),size=[base.shape[1],base.shape[0]])),
                         composition=lineage, changed_rgba_pixels=int(used.sum()), protected_outside_exact=True))
        print(json.dumps(dict(key=key,inputs=len(edits),changed_pixels=int(used.sum()))),flush=True)
    manifest = dict(format=1,method='Exact per-pixel changes relative to independently hash-bound parents; incompatible overlaps rejected',
        parent_candidate=ref(args.parent),builder=ref(__file__),asset_count=len(rows),files=rows,
        all_png_roundtrips_exact=True,protected_outside_exact=True,live_acceptance=False)
    write(args.output/'manifest.json',manifest)
    print(json.dumps(dict(output=str(args.output),assets=len(rows),checks='PASS')))


if __name__ == '__main__':
    main()
