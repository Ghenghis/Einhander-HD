"""Decode a completed GP0 frame and probe the texture pages it actually uses."""
import collections
import json
import struct
from stage1_session import ROOT, command, screenshot


def read_rect(x, y, w, h):
    words = []
    row = 0
    while row < h:
        yy = (y + row) & 511
        rows = min(128, h - row, 512 - yy)
        strips = []
        col = 0
        while col < w:
            xx = (x + col) & 1023
            cols = min(128, w - col, 1024 - xx)
            reply = command('vram_peek', x=xx, y=yy, w=cols, h=rows)
            if not reply.get('ok') or len(reply.get('hex', '')) != cols * rows * 4:
                raise RuntimeError('Incomplete VRAM probe: ' + str(reply))
            strips.append((cols, [int(reply['hex'][i:i+4], 16) for i in range(0, len(reply['hex']), 4)]))
            col += cols
        for r in range(rows):
            for cols, data in strips:
                words.extend(data[r * cols:(r + 1) * cols])
        row += rows
    return words


def probe():
    output = ROOT / 'evidence/referenced-textures'
    output.mkdir(exist_ok=True)
    frame = command('gpu_ring_stats')['newest_frame'] - 2
    trace = command('gpu_frame_dump', frame=frame)
    (output / f'gp0-{frame}.json').write_text(json.dumps(trace, indent=2))
    pages = collections.Counter()
    palettes = collections.Counter()
    tpage = 0
    for entry in trace['entries']:
        op = int(entry['op'], 16)
        w = [int(word, 16) for word in entry['w']]
        if op == 0xE1:
            tpage = w[0] & 0x1ff
        if 0x20 <= op < 0x40 and op & 4:
            page, clut = w[5 if op & 0x10 else 4] >> 16, w[2] >> 16
        elif 0x60 <= op < 0x80 and op & 4:
            page, clut = tpage, w[2] >> 16
        else:
            continue
        depth = (page >> 7) & 3
        pages[((page & 15) * 64, ((page >> 4) & 1) * 256, depth)] += 1
        if depth < 2:
            palettes[((clut & 63) * 16, (clut >> 6) & 511, depth)] += 1
    report = {'frame': frame, 'primitives': len(trace['entries']), 'pages': [], 'palettes': [],
        'scope':'Draw references are from a completed frame; VRAM probes are live subsequent reads, not an atomic frame snapshot.'}
    for (x, y, depth), count in pages.most_common():
        width = (64, 128, 256, 256)[depth]
        data = read_rect(x, y, width, 256)
        name = f'page-{frame}-{x}-{y}-{depth}.words.bin'
        (output / name).write_bytes(struct.pack('<' + 'H' * len(data), *data))
        report['pages'].append({'x': x, 'y': y, 'depth': depth, 'draws': count,
            'nonzero_words': sum(bool(v) for v in data), 'unique_words': len(set(data)), 'file': name})
    for (x, y, depth), count in palettes.most_common():
        data = read_rect(x, y, (16, 256)[depth], 1)
        report['palettes'].append({'x': x, 'y': y, 'depth': depth, 'draws': count,
            'nonzero_words': sum(bool(v) for v in data), 'unique_words': len(set(data)),
            'words': [f'{v:04x}' for v in data]})
    report['capture'] = screenshot(f'probed-frame-{frame}')
    (output / f'probe-{frame}.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'frame':frame, 'primitives':len(trace['entries']),
        'pages':len(pages), 'palettes':len(palettes),
        'zero_palette_rows':[r for r in report['palettes'] if r['nonzero_words']==0],
        'report':str(output/f'probe-{frame}.json')}, indent=2))


if __name__ == '__main__':
    probe()
