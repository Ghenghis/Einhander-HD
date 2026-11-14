#!/usr/bin/env python3
"""Independent re-check of every w7-stage5 frozen deliverable (adapted from w7-stage2/tools/verify_frozen.py to the W7
manifest layout).   python -I -B verify_frozen.py

Per deliverable with a manifest.json:
  * every file listed in the manifest exists and its sha256 matches; files on disk that the manifest does not list;
  * per page: words decoded here (not via w7lib) from the static export, CRC32(words) == TEX, sha256 == manifest source;
  * per rendered key: CLUT words from cluts.json, CRC32 == PAL; classes decoded here (0 = raw 0x0000, 255 = STP,
    127 = opaque); class at floor((i+0.5)*scale) of every native texel of both exports == class(CLUT[native index]);
    alpha values only {0, 127, 255}; RGB 0 at class-0 texel centres; export sha256 == manifest;
  * shared pages (referenced, not built): words CRC32 == TEX.
Writes work/verify-frozen.json and prints it.
"""
import hashlib
import json
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
sys.path.insert(0, 'C:/github/Einhander/remaster-audit/comfy-authoring')
from gpu_queue import cpu_yield  # noqa: E402

TRACK = Path(__file__).resolve().parent.parent
EXPORT = Path('C:/github/Einhander/remaster-audit/fullgame-prep/static-extraction/stages')


def crc(b):
    return '%08X' % (zlib.crc32(b) & 0xFFFFFFFF)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def words_idx(stage, tex):
    p = EXPORT / f'stage{stage}' / 'textures' / f'{tex}.words.bin'
    b = p.read_bytes()
    assert crc(b) == tex, (tex, crc(b))
    w = np.frombuffer(b, '<u2').reshape(256, 64).astype(np.int64)
    idx = np.stack([(w >> (4 * i)) & 15 for i in range(4)], -1).reshape(256, 256)
    return idx, sha(p)


def main():
    res = {}
    for d in sorted(p for p in (TRACK / 'frozen').iterdir() if p.is_dir()):
        mf = d / 'manifest.json'
        if not mf.exists():
            res[d.name] = dict(frozen=False)
            continue
        m = json.loads(mf.read_text(encoding='utf-8'))
        if 'pages' not in m:            # swatch set (no game keys): file hashes only
            bad = [r for r, f in m['files'].items() if not (d / r).exists() or sha(d / r) != f['sha256']]
            unl = sorted(p.relative_to(d).as_posix() for p in d.rglob('*')
                         if p.is_file() and p.name != 'manifest.json' and p.relative_to(d).as_posix() not in m['files'])
            res[d.name] = dict(frozen=True, status=m['status'], kind=m.get('kind'), manifest_sha256=sha(mf),
                               files_listed=len(m['files']), files_bad_sha=bad, files_unlisted=unl)
            continue
        stage = int(m['import_rule'].split('stage-')[1].split(' ')[0])
        cl = {}
        for c in json.loads((EXPORT / f'stage{stage}' / 'cluts.json').read_text(encoding='utf-8')):
            cl[(c['x'], c['y'], c['pal'])] = bytes.fromhex(c['words_hex'])
        bad_sha = []
        for rel, f in m['files'].items():
            cpu_yield()
            if not (d / rel).exists() or sha(d / rel) != f['sha256']:
                bad_sha.append(rel)
        unlisted = sorted(p.relative_to(d).as_posix() for p in d.rglob('*')
                          if p.is_file() and p.name != 'manifest.json' and p.relative_to(d).as_posix() not in m['files'])
        n = mism = alpha_bad = black_bad = keys = 0
        for tex, pg in m['pages'].items():
            idx, wsha = words_idx(stage, tex)
            assert wsha == pg['source']['sha256'], tex
            for e in pg['rendered_keys']:
                keys += 1
                pal = e['key'][9:]
                b = cl[(e['clut_xy'][0], e['clut_xy'][1], pal)]
                assert crc(b) == pal, e['key']
                wds = np.frombuffer(b, '<u2').astype(np.int64)
                cls = np.where(wds == 0, 0, np.where(wds & 0x8000, 255, 127))[idx]
                for s in ('png_2048', 'png_1024'):
                    cpu_yield()
                    p = d / e[s]['path']
                    assert sha(p) == e[s]['sha256'], p
                    a = np.asarray(Image.open(p))
                    assert a.ndim == 3 and a.shape[2] == 4, p
                    f = a.shape[0] / 256
                    c = np.floor((np.arange(256) + 0.5) * f).astype(np.int64)
                    sub = a[np.ix_(c, c)]
                    n += 1
                    mism += int((sub[..., 3] != cls).sum())
                    alpha_bad += 0 if set(np.unique(a[..., 3]).tolist()) <= {0, 127, 255} else 1
                    black_bad += int((sub[cls == 0][:, :3] != 0).any(-1).sum())
        shared = {}
        for tex, sp in (m.get('shared_pages_referenced_not_built') or {}).items():
            _, wsha = words_idx(stage, tex)
            shared[tex] = dict(words_crc_ok=True, sha256_matches=wsha == sp['source']['sha256'], owner=sp['owner'],
                               stage_keys=len(sp['stage_keys']))
        res[d.name] = dict(frozen=True, status=m['status'], manifest_sha256=sha(mf), files_listed=len(m['files']),
                           files_bad_sha=bad_sha, files_unlisted=unlisted, pages=len(m['pages']), rendered_keys=keys,
                           exports_checked=n, centre_class_mismatches=mism, alpha_value_violations=alpha_bad,
                           class0_nonblack_centres=black_bad, manifest_total_mismatches=m['class_validation']['total_mismatches'],
                           glyph_check=m.get('glyph_check'), shared_pages=shared or None)
    (TRACK / 'work' / 'verify-frozen.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
