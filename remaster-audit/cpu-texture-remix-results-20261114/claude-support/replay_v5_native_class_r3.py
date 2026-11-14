#!/usr/bin/env python3
"""claude-einhander-support: independent native-class replay of the 118 UI v5 snap-native files, r3, FAIL-CLOSED
(EIN-SUPPORT-UI-V5-NATIVE-REPLAY-20261114). r1 82b8facb and r2 e09050d7 are preserved unchanged next to this file.

r3 adds what crash-check asked for in msg_484c9e55 and msg_74b5e20d:
  - An exact 118-row preflight table, preflight-table-v1.json, pinned by full sha256. For every member it holds the
    expected sidecar sha256, ww/hh/depth, PNG width/height, texel tw/th and scale (4 or 8). The member set must equal
    the table set exactly; there is no generic expansion.
  - Fail-closed order per member. Each stage runs only if every earlier one passed:
      A. candidate, words and clut byte sha256 equal the summary and the table; CRC32(words) == TEX; CRC32(clut) == PAL;
         clut length 32 B (depth 0) or 512 B (depth 1).
      B. Sidecar: its bytes sha256 equals the table (read once); ww/hh/depth equal the table; depth in {0,1,2};
         1 <= ww <= 1024; 1 <= hh <= 512; len(words) == ww*hh*2; known_words == total_words when present;
         key TEX matches when present.
      C. PNG header, from the hashed bytes and before any decode: signature + IHDR; width/height equal the table;
         at most 2048 each; scale in {4, 8} equal to the table; width == tw*scale and height == th*scale.
      D. Only now: native_cls, decode of the same bytes, and the decoded shape check.
      E. The alpha-plane sha256 must equal alpha_after_sha256. On a mismatch the native audit is skipped.
      F. Native audit (frozen DLL), with explicit rc checks; then replayed primary/s2 must agree with the reported values.
  - Pins: the original v5 algorithm (ui_menu_classsnap_v5.py 67790a05, with its check() text hash recorded), and the
    dependency versions numpy 2.5.2 and Pillow 12.3.0 (exit 2 on any other version).
  - Kept from r2:
    - full pins for the DLL, class_mip.c/.h, summary, classcheck, w6lib and w2lib;
    - the frozen functions run from pinned source text, with no imports of the author modules;
    - the script refuses python -O.
Usage (only under a grant):
  python -B -I replay_v5_native_class_r3.py --pins-only
  python -B -I replay_v5_native_class_r3.py --out <new dir>
Exit 0 = all 118 pass every stage and agree with the summary; 1 = any member failed (each one recorded with the stage
where it stopped); 2 = pins/versions/usage/-O.
"""
import os
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
import argparse, ctypes, datetime, hashlib, io, json, re, struct, sys, time, types, zlib
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
UI = Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui')
RUN = UI / 'classsnap-v5/20261114T175529Z'
W6T = Path('C:/github/Einhander/remaster-audit/comfy-authoring/w6-hud-fades/tools')
SUMMARY = UI / 'integration/runtime-summary-v5-20261114T180533Z.json'
TABLE = HERE / 'preflight-table-v1.json'
PINS = {
    SUMMARY: 'e124d0e814d2d7b9d503c7df36df1a6aba62cc18e6a9483f6ab2a7e0fa092a1b',
    TABLE: '93a6315f4ac837b77bb35b315a16d2a34c2b3fe05a23c40684e2c219b2cc374c',
    RUN / 'class_mip.dll': '2dbc5ef9e562524f90c08eebe1169dc1d84a9e63de3cdcb6838fde0f658c59ad',
    RUN / 'class_mip.c': 'c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d',
    RUN / 'class_mip.h': '90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3',
    RUN / 'ui_menu_classsnap_v5.py': '67790a05792e3e061bfc5cef7706e31967ed03e8779df0d2666985707df63612',
    W6T / 'classcheck.py': '72bf4a095eecb962f02ff94ddbb911d4151ec75051021305b12f4cb7494d358f',
    W6T / 'w6lib.py': '895b170fe7da5d8377de9561ff4c5f50bdc96e585d8d7a650a94da9fd56ee92a',
    W6T / 'w2lib.py': '516833b90f8615d424d8d32327b5056001943ed1ee3b039ccd3cc7e7a102c2ed',
}
VERSIONS = {'numpy': '2.5.2', 'PIL': '12.3.0'}
RF = ('pixels', 'cells', 'r1_centre_bad', 'r2_displaced_px', 'r3_uniform_bad_px', 'r4_island_px', 'r5_fringe_px',
      'cells_bad', 'pinhole_cells', 'nonclass_px')
KEY = re.compile(r'([0-9A-F]{8})-([0-9A-F]{8})\.png$')
MAX_DIM = 2048


class CmReport(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in RF]


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def func_text(path, name):
    """Exact source text of one top-level function ('def name(' to the next top-level line); the def must be unique."""
    src = Path(path).read_text(encoding='utf-8')
    head = f'\ndef {name}('
    if src.count(head) != 1:
        raise SystemExit(f'{path}: def {name} occurs {src.count(head)} times')
    lines = src[src.index(head) + 1:].split('\n')
    body = [lines[0]]
    for ln in lines[1:]:
        if ln and not ln[0].isspace():
            break
        body.append(ln)
    return '\n'.join(body).rstrip() + '\n'


def nested_func_text(path, name):
    """Exact text of an indented 'def name(' block (the v5 check() is nested inside main); recorded for provenance only."""
    src = Path(path).read_text(encoding='utf-8')
    m = re.search(rf'\n( +)def {name}\(', src)
    if not m or len(re.findall(rf'\n +def {name}\(', src)) != 1:
        raise SystemExit(f'{path}: nested def {name} not unique')
    ind = m.group(1); lines = src[m.start() + 1:].split('\n'); body = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and not ln.startswith(ind + ' '):
            break
        body.append(ln)
    return '\n'.join(body).rstrip() + '\n'


def main():
    if sys.flags.optimize:
        print('refusing: python -O strips checks; run without -O', file=sys.stderr); return 2
    ap = argparse.ArgumentParser()
    ap.add_argument('--out'); ap.add_argument('--pins-only', action='store_true')
    a = ap.parse_args()
    got = {str(p): sha_bytes(p.read_bytes()) for p in PINS}
    mism = [str(p) for p in PINS if got[str(p)] != PINS[p]]
    import numpy as np
    import PIL
    from PIL import Image
    vers = {'numpy': np.__version__, 'PIL': PIL.__version__, 'python': sys.version}
    vbad = [k for k, v in VERSIONS.items() if vers[k] != v]
    P = dict(pins=got, mismatch=mism, versions=vers, version_mismatch=vbad, script=sha_bytes(Path(__file__).read_bytes()),
             v5_check_text_sha256=sha_bytes(nested_func_text(RUN / 'ui_menu_classsnap_v5.py', 'check').encode()))
    if a.pins_only or mism or vbad:
        print(json.dumps(P, indent=1)); return 2 if (mism or vbad) else 0
    out = Path(a.out).resolve()
    if out.exists() and any(out.iterdir()):
        print('refusing: --out exists and is not empty', file=sys.stderr); return 2
    out.mkdir(parents=True, exist_ok=True)
    Image.MAX_IMAGE_PIXELS = MAX_DIM * MAX_DIM
    texts = dict(classes=func_text(W6T / 'w6lib.py', 'classes'), decode_words=func_text(W6T / 'w2lib.py', 'decode_words'),
                 native_cls=func_text(W6T / 'classcheck.py', 'native_cls'))
    P['function_text_sha256'] = {k: sha_bytes(v.encode()) for k, v in texts.items()}
    W = types.SimpleNamespace(); L = types.SimpleNamespace()
    ns = dict(np=np); exec(texts['classes'], ns); W.classes = ns['classes']
    ns = dict(np=np); exec(texts['decode_words'], ns); L.decode_words = ns['decode_words']
    ns = dict(np=np, W=W, L=L); exec(texts['native_cls'], ns); native_cls = ns['native_cls']
    lib = ctypes.CDLL(str(RUN / 'class_mip.dll'))
    lib.cm_validate.restype = ctypes.c_int
    lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.POINTER(CmReport)]
    lib.cm_flags_ex.restype = ctypes.c_int
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]

    def audit(img, ncls, s, pr):   # v5 check() semantics (text hash recorded above) with explicit native rc checks
        img = np.ascontiguousarray(img); H, Wd = img.shape[:2]; rep = CmReport()
        rc = lib.cm_validate(img.ctypes.data, Wd, H, ncls.ctypes.data, ncls.shape[1], ncls.shape[0], s, ctypes.byref(rep))
        if rc != 0:
            pr.append(f'F cm_validate rc {rc}'); return None
        o = {n: int(getattr(rep, n)) for n in RF}
        for nm, bound in (('s2_viol_px', 0.5), ('conn_viol_px', 1.0e9)):
            fl = np.zeros((H, Wd), np.uint8)
            rc = lib.cm_flags_ex(img.ctypes.data, Wd, H, ncls.ctypes.data, ncls.shape[1], ncls.shape[0], s, bound, 0, fl.ctypes.data)
            if rc != 0:
                pr.append(f'F cm_flags_ex({nm}) rc {rc}'); return None
            o[nm] = int(((fl & (2 | 4 | 16)) != 0).sum())
        o['primary_pass'] = o['r1_centre_bad'] == 0 and o['conn_viol_px'] == 0
        o['s2_strict_pass'] = all(o[x] == 0 for x in ('r1_centre_bad', 'r2_displaced_px', 'r3_uniform_bad_px', 'r4_island_px'))
        return o

    summ = json.loads(SUMMARY.read_bytes())
    table = json.loads(TABLE.read_bytes())
    trows = {(t['folder'], t['file'], t['candidate']): t for t in table['rows']}
    members = [(u['folder'], m) for u in summ['units_detail'] for m in u['members']]
    skeys = {(f, m['file'], m['candidate']) for f, m in members}
    if len(members) != 118 or len(trows) != 118 or skeys != set(trows):
        print(json.dumps(dict(error='member set != exact 118-row table', members=len(members), table=len(trows),
                              only_summary=len(skeys - set(trows)), only_table=len(set(trows) - skeys))), file=sys.stderr)
        return 2
    rows, t0 = [], time.time()
    for folder, m in members:
        t = trows[(folder, m['file'], m['candidate'])]
        r = dict(folder=folder, file=m['file'], candidate=m['candidate'], problems=[], stopped_at=None); pr = r['problems']
        rows.append(r)

        def stop(stage):
            r['stopped_at'] = stage
        try:
            # ---- A: byte pins + CRC identity
            k = KEY.search(m['file'])
            if not k:
                pr.append('A member file has no TEX-PAL key'); stop('A'); continue
            tex, pal = k.group(1), k.group(2)
            cb_img = (UI / m['candidate']).read_bytes()
            wb = Path(m['words']).read_bytes()
            for nm, b, want in (('candidate', cb_img, (m['candidate_sha256'], t['candidate_sha256'])),
                                ('words', wb, (m['words_sha256'], t['words_sha256']))):
                if not (sha_bytes(b) == want[0] == want[1]): pr.append(f'A {nm} sha256')
            if '%08X' % (zlib.crc32(wb) & 0xFFFFFFFF) != tex: pr.append(f'A CRC32(words) != TEX {tex}')
            dp_t = t['depth']
            clb = None
            if dp_t != 2:
                clb = Path(m['clut']).read_bytes()
                if not (sha_bytes(clb) == m['clut_sha256'] == t['clut_sha256']): pr.append('A clut sha256')
                if '%08X' % (zlib.crc32(clb) & 0xFFFFFFFF) != pal: pr.append(f'A CRC32(clut) != PAL {pal}')
                if dp_t not in (0, 1) or len(clb) != (32 if dp_t == 0 else 512): pr.append(f'A clut bytes {len(clb)} for depth {dp_t}')
            if pr: stop('A'); continue
            # ---- B: sidecar pinned by the table
            qb = Path(t['sidecar']).read_bytes()
            if sha_bytes(qb) != t['sidecar_sha256']:
                pr.append('B sidecar sha256 != table'); stop('B'); continue
            qm = json.loads(qb)
            ww, hh, dp = qm.get('width_words'), qm.get('height'), qm.get('depth')
            if (ww, hh, dp) != (t['ww'], t['hh'], t['depth']): pr.append(f'B sidecar dims {(ww, hh, dp)} != table')
            if not (type(ww) is int and type(hh) is int and type(dp) is int and dp in (0, 1, 2) and 1 <= ww <= 1024 and 1 <= hh <= 512):
                pr.append(f'B sidecar bounds {(ww, hh, dp)}')
            elif len(wb) != ww * hh * 2: pr.append(f'B words bytes {len(wb)} != {ww}*{hh}*2')
            if 'total_words' in qm and qm.get('known_words') != qm.get('total_words'): pr.append('B known_words != total_words')
            if isinstance(qm.get('key'), str) and qm['key'][:8].upper() != tex: pr.append(f"B sidecar key {qm['key']} TEX != {tex}")
            if pr: stop('B'); continue
            r.update(depth=dp, texels_words=[ww, hh])
            # ---- C: PNG header from the hashed bytes, before any decode
            if cb_img[:8] != b'\x89PNG\r\n\x1a\n' or cb_img[12:16] != b'IHDR':
                pr.append('C not a PNG IHDR'); stop('C'); continue
            pw, ph = struct.unpack('>II', cb_img[16:24])
            tw, th = ww * (4, 2, 1)[dp], hh
            s = t['scale']
            if (pw, ph) != (t['png_w'], t['png_h']): pr.append(f'C png {pw}x{ph} != table')
            if pw > MAX_DIM or ph > MAX_DIM or pw < 1 or ph < 1: pr.append(f'C png {pw}x{ph} outside 1..{MAX_DIM}')
            if s not in (4, 8) or (tw, th) != (t['tw'], t['th']) or pw != tw * s or ph != th * s:
                pr.append(f'C scale {s} / texels {tw}x{th} inconsistent with png {pw}x{ph}')
            if pr: stop('C'); continue
            r['scale'] = s
            # ---- D: native class map and decode of the same bytes
            wd = dict(words=np.frombuffer(wb, '<u2').reshape(hh, ww), depth=dp)
            cl = dict(clut=np.frombuffer(clb, '<u2')) if dp != 2 else None
            ncls = np.ascontiguousarray(native_cls(wd, cl).astype(np.uint8))
            with Image.open(io.BytesIO(cb_img)) as im:
                if im.size != (pw, ph): pr.append(f'D decoded size {im.size} != header'); stop('D'); continue
                img = np.ascontiguousarray(np.asarray(im.convert('RGBA')))
            if ncls.shape != (th, tw) or img.shape[:2] != (th * s, tw * s):
                pr.append(f'D shapes ncls {ncls.shape} img {img.shape[:2]}'); stop('D'); continue
            # ---- E: alpha binding; the native audit is skipped on a mismatch
            if sha_bytes(np.ascontiguousarray(img[..., 3]).tobytes()) != m['alpha_after_sha256'] or \
                    m['alpha_after_sha256'] != t['alpha_after_sha256']:
                pr.append('E alpha plane != alpha_after_sha256'); stop('E'); continue
            # ---- F: frozen native audit + agreement with the reported values
            o = audit(img, ncls, s, pr)
            if o is None: stop('F'); continue
            r['audit'] = o
            if o['primary_pass'] != m['primary_pass']: pr.append(f"F primary_pass replay {o['primary_pass']} != reported {m['primary_pass']}")
            if o['s2_strict_pass'] != m['s2_pass']: pr.append(f"F s2 replay {o['s2_strict_pass']} != reported {m['s2_pass']}")
            if pr: stop('F')
            del img, ncls, wd
        except Exception as exc:             # recorded, never hidden
            pr.append(f'{exc.__class__.__name__}: {exc}'); r['stopped_at'] = r['stopped_at'] or 'exception'
        finally:
            r['ok'] = not pr
    res = dict(schema='support-ui-v5-native-replay-r3', task='EIN-SUPPORT-UI-V5-NATIVE-REPLAY-20261114', pins=P,
               started_utc=datetime.datetime.fromtimestamp(t0, datetime.timezone.utc).isoformat(), finished_utc=utc(),
               elapsed_s=round(time.time() - t0, 2), members=len(rows), ok=sum(r['ok'] for r in rows),
               primary_pass_replayed=sum(1 for r in rows if (r.get('audit') or {}).get('primary_pass')),
               s2_strict_pass_replayed=sum(1 for r in rows if (r.get('audit') or {}).get('s2_strict_pass')),
               stopped_at={st: sum(1 for r in rows if r['stopped_at'] == st) for st in ('A', 'B', 'C', 'D', 'E', 'F', 'exception')},
               failures=[dict(file=r['file'], folder=r['folder'], stopped_at=r['stopped_at'], problems=r['problems']) for r in rows if not r['ok']],
               scope='class-validity replay only; not look/live acceptance; no repair, no GPU; CPU-QUIET cy() not used', rows=rows)
    (out / 'result.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: res[k] for k in ('members', 'ok', 'primary_pass_replayed', 's2_strict_pass_replayed', 'stopped_at', 'elapsed_s')}))
    return 0 if res['ok'] == res['members'] == 118 else 1


if __name__ == '__main__':
    sys.exit(main())
