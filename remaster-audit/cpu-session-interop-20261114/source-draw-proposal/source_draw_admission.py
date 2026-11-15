"""Additional key-level admission: exact source bytes AND a matching in-window draw.

This is a separate proposal. It does not replace acquisition route/stage identity,
artwork, animation, audio, or gameplay acceptance. The integration owner supplies
the independently qualified stage frame window. No GPU or game calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zlib

KEY = re.compile(r"[0-9A-F]{8}-[0-9A-F]{8}")


def crc(data):
    return f"{zlib.crc32(data) & 0xffffffff:08X}"


def integer(value):
    return type(value) is int


def pin(file):
    digest, size = hashlib.sha256(), 0
    with Path(file).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return dict(path=str(file), bytes=size, sha256=digest.hexdigest())


def pair(value):
    return isinstance(value, list) and len(value) == 2 and all(integer(n) for n in value)


def bytes_pin(file, data):
    return dict(path=str(file), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def admit(static_words, source_base, key, page_xy, clut_xy, depth, frame_span, draws):
    if not KEY.fullmatch(key):
        raise ValueError('Expected an exact uppercase TEX-PAL key')
    if not pair(page_xy) or not pair(clut_xy) or not integer(depth) or depth not in (0, 1):
        raise ValueError('Explicit page_xy, clut_xy and indexed depth are required')
    if not pair(frame_span) or not 0 <= frame_span[0] <= frame_span[1]:
        raise ValueError('An explicit qualified stage frame window is required')
    expected_words = (64 if depth == 0 else 128) * 256
    clut_words = 16 if depth == 0 else 256
    paths = {name: Path(str(source_base) + suffix) for name, suffix in (
        ('words', '.words.bin'), ('clut', '.clut.bin'), ('valid', '.valid.bin'), ('source', '.source.json'))}
    errors, inputs = [], []
    data = {}
    for name, file in paths.items():
        try:
            data[name] = file.read_bytes()
            inputs.append(bytes_pin(file, data[name]))
        except OSError as exc:
            errors.append(f'{name}: {exc.__class__.__name__}')
    try:
        static = Path(static_words).read_bytes()
        inputs.append(bytes_pin(static_words, static))
        if len(static) != expected_words * 2 or crc(static) != key[:8]:
            errors.append('Static page size/CRC does not match the expected TEX/depth')
    except OSError as exc:
        static = None
        errors.append(f'static: {exc.__class__.__name__}')
    try:
        meta = json.loads(data.get('source', b'{}'))
        if not isinstance(meta, dict):
            raise ValueError('Source metadata must be an object')
    except (ValueError, UnicodeError):
        meta = {}
        errors.append('Invalid source metadata')
    if meta.get('key') != key:
        errors.append('Source metadata key mismatch')
    if meta.get('predicted') or meta.get('raw_origin') == 'static_disc_prediction':
        errors.append('Static prediction is not a live capture')
    if meta.get('depth') != depth or type(meta.get('depth')) is not int:
        errors.append('Source depth mismatch')
    if meta.get('clut_xy') != clut_xy or not pair(meta.get('clut_xy')):
        errors.append('Source CLUT slot mismatch')
    if any(type(meta.get(n)) is not int or meta[n] != expected_words for n in ('known_words', 'total_words')):
        errors.append('Source word counts are incomplete or wrong for this depth')
    words, clut, valid = (data.get(n, b'') for n in ('words', 'clut', 'valid'))
    if len(words) != expected_words * 2 or crc(words) != key[:8] or words != static:
        errors.append('Live page is not the complete byte-identical predicted TEX')
    if len(clut) != clut_words * 2 or crc(clut) != key[9:]:
        errors.append('Live CLUT size/CRC mismatch')
    if len(valid) != expected_words or not all(valid):
        errors.append('Validity bytes do not prove every native word')
    matched, malformed, matched_count = [], [], 0
    for file in draws:
        file = Path(file)
        try:
            digest, size = hashlib.sha256(), 0
            with file.open('rb') as stream:
                for line_number, raw_line in enumerate(stream, 1):
                    digest.update(raw_line)
                    size += len(raw_line)
                    line = raw_line.decode('utf-8-sig' if line_number == 1 else 'utf-8')
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        malformed.append(dict(path=str(file), line=line_number))
                        continue
                    if not isinstance(row, dict) or row.get('event') != 'source_draw_query_matched' or row.get('key') != key:
                        continue
                    frame = row.get('frame')
                    if not integer(frame) or not frame_span[0] <= frame <= frame_span[1]:
                        continue
                    if (row.get('source_kind') != 'native_page' or row.get('depth') != depth or
                        not integer(row.get('depth')) or row.get('page_xy') != page_xy or
                        not pair(row.get('page_xy')) or row.get('clut_xy') != clut_xy or not pair(row.get('clut_xy'))):
                        continue
                    uv = row.get('uv_bounds')
                    xy = row.get('xy')
                    if (not isinstance(uv, list) or len(uv) != 4 or not all(integer(n) for n in uv) or
                        not (0 <= uv[0] <= uv[2] < 256 and 0 <= uv[1] <= uv[3] < 256) or
                        row.get('native_words') != [64 if depth == 0 else 128, 256] or not pair(row.get('native_words')) or
                        not isinstance(xy, list) or len(xy) not in (3, 4) or not all(pair(p) for p in xy) or
                        not integer(row.get('semi')) or row['semi'] not in (-1, 0, 1, 2, 3)):
                        continue
                    matched_count += 1
                    if len(matched) < 100:
                        matched.append(dict(path=str(file), line=line_number, frame=frame,
                            row_sha256=hashlib.sha256(raw_line).hexdigest()))
            inputs.append(dict(path=str(file), bytes=size, sha256=digest.hexdigest()))
        except (OSError, UnicodeError) as exc:
            errors.append(f'draw log: {exc.__class__.__name__}')
    if malformed:
        errors.append('Malformed draw-log lines; capture integrity needs review')
    if not matched:
        errors.append('No exact native-page draw with required CLUT slot/depth in the stage window')
    return dict(schema='ein-key-source-draw-admission-v1', passed=not errors, key=key,
        requirement=dict(page_xy=page_xy, clut_xy=clut_xy, depth=depth, frame_span=frame_span),
        errors=errors, matched_draws=matched, matched_draw_count=matched_count,
        malformed_lines=malformed, inputs=inputs,
        limits=['Key-level source/draw proof only; stage identity and route window must be qualified independently.',
                'A matched source query is not submission, presentation or screen visibility proof.',
                'Only complete native pages at4/8bpp are supported; ROI derivatives and16bpp are excluded.',
                'Does not prove complete palette cycles, all draw coverage, final art, audio or gameplay acceptance.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--static-words', required=True)
    p.add_argument('--source-base', required=True)
    p.add_argument('--key', required=True)
    p.add_argument('--page', nargs=2, type=int, required=True)
    p.add_argument('--clut', nargs=2, type=int, required=True)
    p.add_argument('--depth', type=int, choices=(0, 1), required=True)
    p.add_argument('--frames', nargs=2, type=int, required=True)
    p.add_argument('--draws', action='append', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    result = admit(a.static_words, a.source_base, a.key, a.page, a.clut, a.depth, a.frames, a.draws)
    Path(a.out).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], key=a.key, errors=result['errors'], matched=len(result['matched_draws']))))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
