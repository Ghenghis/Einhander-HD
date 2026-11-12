"""Merge independently bounded typography edits without replacing other authors' pixels."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from stage_typography_candidate import read, write, ref


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
        source = base_rows[key]
        parent_ref = dict(path=source['composed_path'], sha256=source['sha256'])
        base = checked_pixels(parent_ref)
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
