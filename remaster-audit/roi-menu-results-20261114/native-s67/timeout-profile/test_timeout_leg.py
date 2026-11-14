#!/usr/bin/env python3
"""Synthetic self-test for validate_timeout_leg.py (s67 proposal). Tiny fixtures only; writes ONLY under the given work dir
(default: a fresh folder in the system temp dir). No game, no capture, no RAM/state access, no GPU.

r5 exact-gate rule (support msg_ef793120): every snapshot negative must fail ONLY RS, with its intended RS reason.
r5 run-1 fix: positive snapshot fixtures failed canonical K (drawn key had no native source); each drawn key now gets a
CRC-consistent source quad (words = the snapshot rect). Validator unchanged.
r5 (support review F1/F2/F4): snapshot evidence declares its key rect; the claimed TEX must be drawn with that kind/size;
mark rows come only from the event file's own session log; ms/flags/reserved bytes are bound. New controls: 8bpp page,
narrowed page, upload rect, two sessions each with event-0001, a mark row in another session only, ms and flag mismatches,
nonzero reserved bytes, a TEX that is never drawn, a missing/undeclared rect. Fixture events now live next to their capture log.
r4 replaces the r3 snapshot fixtures with native EINRC01 events (hd_research_event.h layout) and adds header, identity,
mark-row binding and payload-checksum negatives; the r3 headerless fixture is now an expected rejection.
r3 adds residency-evidence controls (upload_event unsupported; marked_vram_snapshot needs a pinned receipt with matching
VRAM CRC and mark frame) and one positive pinned-snapshot control.
r2 adds the negative controls asked for in main msg_3dce6a3c3b2470a2 and crash-check msg_7623c6266e6047e3 (declared stage,
narration range/span/search coverage, out-of-span expiry and residency frames, equal entry/expiry, residency binding/ambiguity,
non-object JSON rows) and one positive control (fully covered not-observed narration).
Builds a clean synthetic Stage 6 timeout-leg run (words/CLUT/valid/source.json quads, capture.jsonl with a 704,256 draw
after expiry, 2880x2160 PNG captures, private card, manifest), checks it passes, then applies one defect at a time and
checks the expected gate fails. Also checks that the canonical validator still FAILS this run on its normal X/T gates
(a timeout leg must never look like a clear)."""
import copy
import hashlib
import json
import os
import random
import re
import struct
import shutil
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, 'validate_timeout_leg.py')
CANON = os.environ.get('EIN_ACQ_VALIDATOR', 'C:/github/Einhander/remaster-audit/fullgame-prep/acquisition/validate_acquisition.py')


def crc(b):
    return '%08X' % (zlib.crc32(b) & 0xFFFFFFFF)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def png_header(path, w, h):
    """Minimal PNG signature + IHDR: the validators read only the header for size (no decode)."""
    ihdr = (13).to_bytes(4, 'big') + b'IHDR' + w.to_bytes(4, 'big') + h.to_bytes(4, 'big') + bytes([8, 2, 0, 0, 0])
    ihdr += zlib.crc32(ihdr[4:]).to_bytes(4, 'big')
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ihdr)


def write_key(src, words, clut, frame, page_xy):
    k = crc(words) + '-' + crc(clut)
    open(os.path.join(src, k + '.words.bin'), 'wb').write(words)
    open(os.path.join(src, k + '.clut.bin'), 'wb').write(clut)
    open(os.path.join(src, k + '.valid.bin'), 'wb').write(b'\x01' * (len(words) // 2))
    json.dump(dict(key=k, frame=frame, width_words=16, height=len(words) // 32, depth=0, clut_xy=[0, 480], clut_words=16,
                   known_words=len(words) // 2, total_words=len(words) // 2, page_xy=page_xy,
                   fragments=[[page_xy[0], page_xy[1], 16, len(words) // 32, 0, 0]]), open(os.path.join(src, k + '.source.json'), 'w'))
    return k


def build(run, extra_lines=None, raw_extra=None):
    rnd = random.Random(11)
    if os.path.exists(run):
        shutil.rmtree(run)
    src = os.path.join(run, 'native-source-0')
    caps = os.path.join(run, 'captures')
    os.makedirs(src)
    os.makedirs(caps)
    os.makedirs(os.path.join(run, 'state'))
    w_stage = bytes(rnd.randrange(256) for _ in range(256))
    w_page = bytes(rnd.randrange(256) for _ in range(256))
    cl = bytes(rnd.randrange(256) for _ in range(32))
    k_stage = write_key(src, w_stage, cl, 1000, [320, 0])
    k_page = write_key(src, w_page, cl, 5200, [704, 256])
    rec = lambda k, f, pg: dict(event='source_draw_query_matched', key=k, frame=f, source_kind='native_page', depth=0, semi=-1,
                                native_words=[64, 256], page_xy=pg, clut_xy=[0, 480], uv_bounds=[0, 0, 63, 7],
                                uv_vertices=[[0, 0], [64, 0], [0, 8]], xy=[[10, 10], [74, 10], [10, 18]])
    lines = [dict(event='capture_start', contract='ein-research-v1', frame=990)]
    lines += [rec(k_stage, f, [320, 0]) for f in range(1000, 5000, 100)]
    lines += [rec(k_page, f, [704, 256]) for f in range(5200, 5600, 50)]
    lines.append(dict(event='mark', label='stage:6:entry', frame=1000))
    lines.append(dict(event='mark', label='timeout:6:expiry', frame=5000))
    lines.append(dict(event='mark', label='gameover:6', frame=5800))
    lines.append(dict(event='frame_tick', frame=6400))
    lines += list(extra_lines or [])
    with open(os.path.join(src, 'capture.jsonl'), 'w') as f:
        for ln in lines:
            f.write(json.dumps(ln) + '\n')
        for raw in raw_extra or []:
            f.write(raw + '\n')
    for n in ('entry', 'prev-tally', 'expiry', 'narration', 'gameover', 'next'):
        png_header(os.path.join(caps, n + '-internal.png'), 2880, 2160)
    open(os.path.join(run, 'state', 'card1.mcd'), 'wb').write(b'MC' + b'\x00' * 1022)
    cap = lambda n, f: dict(path=f'captures/{n}-internal.png', frame=f)
    card_sha = sha(os.path.join(run, 'state', 'card1.mcd'))
    m = dict(
        schema='ein-stage6-timeout-leg-v1', leg='timeout', counts_as_stage_clear=False, stage_tally_after_expiry=False,
        stage=dict(number=6, identity_basis='visible_stage_entry_and_previous_tally', identity_evidence=[cap('entry', 1000)]),
        run=dict(binary=dict(sha256='a' * 64), settings=dict(internal_resolution=[2880, 2160], hd_dumping=True), research_recorder_armed=True),
        route=dict(method='continuous_from_previous_stage_clear', ram_writes=False, state_loads=False, stage_select_used=False,
                   unlock_bits_written=False, timer_untouched=True, assist=dict(used=False), acceptance_eligible=False,
                   previous_stage_run=dict(id='stage5-run', manifest_sha256='b' * 64)),
        cards=dict(user_cards_mounted=False, mounted=[dict(path='state/card1.mcd', sha256_before=card_sha, sha256_after=card_sha)]),
        capture_logs=[dict(path='native-source-0/capture.jsonl', frame_span=[990, 6400])],
        source_dirs=['native-source-0'],
        entry=dict(frame=1000, captures=[cap('entry', 1000)]),
        previous_tally=dict(frame_range=[900, 980], captures=[cap('prev-tally', 950)]),
        timer_expiry=dict(frame=5000, countdown_zero_visible=True, captures=[cap('expiry', 5000)]),
        movie=dict(observed=True, frame_range=[5010, 5190], movie='MOV03', identity_basis='CD read log: MOV03.STR opened at 5008'),
        narration=dict(observed=True, passage_index=2, basis='read-only breakpoint log 0x80048138 a0=2', frame_range=[5200, 5600],
                       captures=[cap('narration', 5400)]),
        residency_704_256=dict(tex=k_page[:8], frame=5200, basis='draw_rows'),
        game_over_still=dict(frame_range=[5700, 5900], captures=[cap('gameover', 5800)], drawn_tex=[]),
        next_screen=dict(frame_range=[6000, 6300], captures=[cap('next', 6100)], description='synthetic'),
        clear=None, next_stage_entry=None, bosses=[], files_sha256={})
    m['game_over_still']['no_textured_still_statement'] = 'synthetic: the still is not a textured draw'
    for rel in ('native-source-0/capture.jsonl', 'state/card1.mcd'):
        m['files_sha256'][rel] = sha(os.path.join(run, rel))
    json.dump(m, open(os.path.join(run, 'timeout-leg-manifest.json'), 'w'), indent=1)
    return m


def run_tool(run, manifest, tool=TOOL):
    mp = os.path.join(run, '_m.json')
    json.dump(manifest, open(mp, 'w'), indent=1)
    out = os.path.join(run, '_report.json')
    p = subprocess.run([sys.executable, '-B', '-I', tool, '--run', run, '--manifest', mp, '--out', out], capture_output=True, text=True)
    rep = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    return p.returncode, rep


def main():
    try:   # light fixture work: below-normal, one CPU (child validator processes inherit the priority class)
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([me.cpu_affinity()[-1]])
    except Exception:
        pass
    work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix='s67-timeout-leg-')
    run = os.path.join(work, 'run-ok')
    base = build(run)
    results = []
    rc, rep = run_tool(run, base)
    ok = rc == 0 and rep.get('pass') is True and rep.get('counts_as_stage6_clear') is False
    results.append(dict(case='clean', expect='pass', rc=rc, ok=ok, failing=[g['id'] for g in rep.get('gates', []) if not g['passed']]))

    def mutated(fn, expect, label):
        m = copy.deepcopy(base)
        fn(m)
        rc_, rep_ = run_tool(run, m)
        failing = sorted(g['id'] for g in rep_.get('gates', []) if not g['passed'])
        results.append(dict(case=label, expect=expect, rc=rc_, failing=failing, ok=rc_ == 1 and expect in failing))

    mutated(lambda m: m.update(counts_as_stage_clear=True), 'M', 'claims a stage clear')
    mutated(lambda m: m.update(clear=dict(frame=5000)), 'M', 'clear recorded')
    mutated(lambda m: m['route'].update(ram_writes=True), 'R', 'RAM writes')
    mutated(lambda m: m['route'].update(timer_untouched=False), 'R', 'timer touched')
    mutated(lambda m: m['route'].pop('previous_stage_run'), 'R', 'no Stage 5 lineage')
    mutated(lambda m: m['timer_expiry'].update(countdown_zero_visible=False), 'TX', 'expiry only from RAM')
    mutated(lambda m: m['timer_expiry'].update(captures=[]), 'TX', 'no expiry capture')
    mutated(lambda m: m.update(movie=dict(observed=False)), 'MV', 'movie neither recorded nor denied')
    mutated(lambda m: m['narration'].pop('passage_index'), 'NA', 'no passage index')
    mutated(lambda m: m.update(narration=dict(observed=False)), 'NA', 'narration neither recorded nor denied')
    mutated(lambda m: m['residency_704_256'].update(tex='7AD161DF'), 'RS', 'residency TEX without a draw row')
    mutated(lambda m: m['game_over_still'].update(captures=[]), 'GO', 'no Game Over capture')
    mutated(lambda m: m['next_screen'].pop('frame_range'), 'NS', 'no next screen')
    mutated(lambda m: m['movie'].update(frame_range=[4000, 4100]), 'O', 'movie before expiry')
    mutated(lambda m: m.update(stage_tally_after_expiry=True), 'O', 'tally after expiry')
    mutated(lambda m: m['files_sha256'].update({'state/card1.mcd': '0' * 64}), 'H', 'hash mismatch')
    mutated(lambda m: m['cards'].update(user_cards_mounted=True), 'C', 'user card mounted')
    mutated(lambda m: m['source_dirs'].clear(), 'K', 'sources missing')
    # ---- r2 negative controls (main msg_3dce6a3c3b2470a2 + crash-check msg_7623c6266e6047e3)
    mutated(lambda m: m['stage'].update(number=5), 'M', 'r2 declared stage 5')
    mutated(lambda m: m['stage'].pop('number'), 'M', 'r2 stage number missing')
    mutated(lambda m: m['stage'].update(number=True), 'M', 'r2 stage number bool')
    mutated(lambda m: m['stage'].update(number='6'), 'M', 'r2 stage number string')
    mutated(lambda m: m['narration'].pop('frame_range'), 'NA', 'r2 observed narration without frame_range')
    mutated(lambda m: m['narration'].update(frame_range=[5600, 5200]), 'NA', 'r2 observed narration invalid range')
    mutated(lambda m: m['narration'].update(frame_range=[7000, 7100]), 'O', 'r2 observed narration outside capture span')
    mutated(lambda m: m.update(narration=dict(observed=False, not_observed_statement='synthetic', searched_frame_range=[0, 1])),
            'NA', 'r2 not-observed narration searched outside window')
    mutated(lambda m: m.update(narration=dict(observed=False, not_observed_statement='synthetic', searched_frame_range=[5000, 5500])),
            'NA', 'r2 not-observed narration partial search')
    mutated(lambda m: m.update(narration=dict(observed=False, not_observed_statement='synthetic', searched_frame_range=[4900, 7000])),
            'NA', 'r2 not-observed narration search beyond capture span')
    mutated(lambda m: m['timer_expiry'].update(frame=6500), 'O', 'r2 timer expiry outside capture span')
    mutated(lambda m: m['entry'].update(frame=5000), 'O', 'r2 entry equals timer expiry')
    mutated(lambda m: m['residency_704_256'].update(frame=900), 'RS', 'r2 residency frame before expiry')
    mutated(lambda m: m['residency_704_256'].update(frame=6200), 'RS', 'r2 residency frame not bound to a draw row')
    mutated(lambda m: m['residency_704_256'].update(basis='guess'), 'RS', 'r2 unknown residency basis')
    # positive control: a correctly covered not-observed narration passes
    m_pos = copy.deepcopy(base)
    m_pos['narration'] = dict(observed=False, not_observed_statement='synthetic: no narration call in the window',
                              searched_frame_range=[4990, 6350])
    rc_p, rep_p = run_tool(run, m_pos)
    results.append(dict(case='r2 positive: not-observed narration covering expiry..last end state', expect='pass', rc=rc_p,
                        failing=sorted(g['id'] for g in rep_p.get('gates', []) if not g['passed']), ok=rc_p == 0 and rep_p.get('pass') is True))

    # ---- r2 log-level defects in separate run folders (the clean run stays untouched)
    def variant(label, expect, extra=None, raw=None, fix=None):
        vr = os.path.join(work, 'run-' + re.sub(r'[^A-Za-z0-9._-]+', '-', label))
        vm = build(vr, extra_lines=extra, raw_extra=raw)
        if fix:
            fix(vm)
        rc_v, rep_v = run_tool(vr, vm)
        failing = sorted(g['id'] for g in rep_v.get('gates', []) if not g['passed'])
        results.append(dict(case=label, expect=expect, rc=rc_v, failing=failing, report_written=bool(rep_v),
                            ok=rc_v == 1 and bool(rep_v) and expect in failing))

    other = dict(event='source_draw_query_matched', key='9E43A5C3-12345678', frame=5210, source_kind='native_page', depth=0, semi=-1,
                 native_words=[64, 256], page_xy=[704, 256], clut_xy=[64, 510], uv_bounds=[0, 0, 63, 7],
                 uv_vertices=[[0, 0], [64, 0], [0, 8]], xy=[[10, 10], [74, 10], [10, 18]])
    variant('r2 ambiguous 704,256 residency', 'RS', extra=[other])

    # ---- r3: residency bases must be bound to evidence (crash-check msg_11548f2667c6d055)
    mutated(lambda m: m['residency_704_256'].update(basis='upload_event', tex='DEADBEEF'), 'RS', 'r3 upload_event label only (DEADBEEF)')
    mutated(lambda m: m['residency_704_256'].update(basis='upload_event'), 'RS', 'r3 upload_event unsupported even with a drawn TEX')
    mutated(lambda m: m['residency_704_256'].update(basis='marked_vram_snapshot', tex='DEADBEEF'), 'RS', 'r3 snapshot label only (no evidence)')

    def fnv(data):
        h = 2166136261
        for b in data:
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
        return h

    rnd5 = random.Random(5)
    vram0 = bytearray(1048576)
    rect0 = bytearray(rnd5.randrange(256) for _ in range(64 * 256 * 2))
    for y in range(256):
        o = ((256 + y) * 1024 + 704) * 2
        vram0[o:o + 128] = rect0[y * 128:(y + 1) * 128]
    ram0 = bytes(2097152)
    fnv_ram0, fnv_vram0 = fnv(ram0), fnv(bytes(vram0))
    tex0 = crc(bytes(rect0))

    def native_event(frame, index, label, magic=b'EINRC01\x00', version=1, ram=ram0, vram=bytes(vram0), fr=None, fv=None, reserved=0):
        hdr = bytearray(160)
        hdr[0:8] = magic
        struct.pack_into('<IIQQIIIIIIIIIIIIII', hdr, 8, version, 160, frame, frame * 17, 160, 2097152, 2097312, 1048576,
                         1, 0, 1, 0, 1, fnv_ram0 if fr is None else fr, fnv_vram0 if fv is None else fv, index, len(label), 1)
        hdr[96:96 + len(label)] = label.encode('ascii')
        if reserved:
            hdr[90] = reserved
        fv_actual = fnv(vram) if fv is None else fv
        struct.pack_into('<I', hdr, 72, fv_actual)
        return bytes(hdr) + ram + vram

    def vram_with(x, y, w, h, seed):
        """copy of vram0 with a random rect written at x,y (w words x h rows); returns (bytes, crc of that rect, rect bytes)."""
        v = bytearray(vram0)
        rr = random.Random(seed)
        rect = bytearray(rr.randrange(256) for _ in range(w * h * 2))
        for row in range(h):
            o = (((y + row) & 511) * 1024 + x) * 2
            v[o:o + w * 2] = rect[row * w * 2:(row + 1) * w * 2]
        return bytes(v), crc(bytes(rect)), bytes(rect)

    HDR_MS = lambda fr: fr * 17          # native_event writes ms = frame * 17 and flags 1,0,1,0 at @48/52/56/60

    def mark(fname, label='timeout_residency', index=7, frame=5300, **over):
        d = dict(event='mark', label=label, event_file=fname, event_index=index, frame=frame, bytes=3145888, host_mono_ms=HDR_MS(frame),
                 gpu_dirty=1, pending_cpu_upload_rects=0, pack_dirty=1, cpu_authority_dual=0, cpu_vram_may_be_stale=True)
        d.update(over)
        return d

    def draw(tex, kind='native_page', depth=0, words=(64, 256), page=(704, 256), frame=5300, uv=(0, 0, 63, 7), sw=(0, 0), key=None):
        return dict(event='source_draw_query_matched', key=key or f'{tex}-12345678', frame=frame, source_kind=kind, depth=depth, semi=-1,
                    native_words=list(words), page_xy=list(page), source_word_xy=list(sw), clut_xy=[0, 480], uv_bounds=list(uv),
                    uv_vertices=[[0, 0], [64, 0], [0, 8]], xy=[[10, 10], [74, 10], [10, 18]])

    def snap_run(label, expect, header=True, tex_mode='match', sha_mode='ok', pin=True, mark_row='ok', file_index=7,
                 hdr_kw=None, claim_frame=5300, rect='page0', drawn=True, second_session=False, row_over=None, draw_kind=None,
                 origin_shift=0, why=None):
        vr = os.path.join(work, 'run-' + re.sub(r'[^A-Za-z0-9._-]+', '-', label))
        fname = f'event-{file_index:04d}.bin'
        geo = {'page0': (dict(kind='native_page', x=704, y=256, depth=0, width_words=64), (704, 256, 64, 256), ('native_page', 0, (64, 256))),
               'page1': (dict(kind='native_page', x=704, y=256, depth=1, width_words=128), (704, 256, 128, 256), ('native_page', 1, (128, 256))),
               'narrow': (dict(kind='native_page', x=704, y=256, depth=1, width_words=64, narrowed=True), (704, 256, 64, 256), ('native_page', 1, (64, 256))),
               'upload': (dict(kind='upload', x=704, y=300, width_words=32, height=40), (704, 300, 32, 40), ('upload', 2, (32, 40))),
               'page1_as_4bpp': (dict(kind='native_page', x=704, y=256, depth=1, width_words=64), (704, 256, 128, 256), ('native_page', 1, (128, 256))),
               'upload_far': (dict(kind='upload', x=100, y=0, width_words=32, height=40), (100, 0, 32, 40), ('upload', 2, (32, 40))),
               'none': (None, (704, 256, 64, 256), ('native_page', 0, (64, 256)))}[rect]
        ev_rect, (rx, ry, rw, rh), (kind, depth, words) = geo
        vram_b, tex_r, rect_b = vram_with(rx, ry, rw, rh, 9)
        clut_b = bytes(random.Random(13).randrange(256) for _ in range(32))
        drawn_key = tex_r + '-' + crc(clut_b)     # run-1 fix: a real key whose native source is written below (canonical K)
        tex_claim = tex_r if tex_mode == 'match' else 'DEADBEEF'
        own = {'ok': [mark(fname, **(row_over or {}))], 'none': [mark('event-0099.bin', label='other', index=99)],
               'badlabel': [mark(fname, label='other_label')], 'dup': [mark(fname)] * 2}[mark_row]
        # upload rows: first texel at page (704,256) + u_first/ppw, v_first; source_word_xy = that texel's offset in the upload
        uv, sw = (0, 0, 63, 7), (0, 0)
        if kind == 'upload':
            ppw = {0: 4, 1: 2, 2: 1}[depth]
            u_first, v_first = 8 * ppw, 50                       # first texel at VRAM (712, 306), inside the upload (704,300,32,40)
            uv = (u_first, v_first, u_first + 15, v_first + 15)
            sw = (704 + u_first // ppw - rx, 256 + v_first - ry + origin_shift)
        extra = [draw(tex_r, kind=draw_kind or kind, depth=depth, words=words, uv=uv, sw=sw, key=drawn_key)] if drawn else []
        vm = build(vr, extra_lines=own + extra)
        if drawn:   # complete native source for the drawn key: words = the snapshot rect, CRC-consistent with the key
            assert write_key(os.path.join(vr, 'native-source-0'), rect_b, clut_b, 5300, [704, 256]) == drawn_key
        if header:
            blob = native_event(5300, 7, 'timeout_residency', vram=vram_b, **(hdr_kw or {}))
        else:   # r3-style headerless blob of the right size (relabelling attack)
            blob = bytes(160) + ram0 + vram_b
        sp = os.path.join(vr, 'native-source-0', fname)          # r5: the event sits next to its own session log
        open(sp, 'wb').write(blob)
        ssha = sha(sp)
        if second_session:     # another research session with its own event-0007 + mark row (numbering restarts per session)
            s2 = os.path.join(vr, 'native-source-1')
            os.makedirs(s2)
            other = native_event(5310, 7, 'timeout_residency', vram=vram_b)
            open(os.path.join(s2, fname), 'wb').write(other)
            with open(os.path.join(s2, 'capture.jsonl'), 'w') as f:
                f.write(json.dumps(dict(event='capture_start', contract='ein-research-v1', frame=5305)) + '\n')
                f.write(json.dumps(mark(fname, frame=5310)) + '\n')
                f.write(json.dumps(dict(event='frame_tick', frame=6400)) + '\n')
            vm['capture_logs'].append(dict(path='native-source-1/capture.jsonl', frame_span=[5305, 6400]))
            vm['source_dirs'].append('native-source-1')
            for rel_ in ('native-source-1/capture.jsonl', 'native-source-1/' + fname):
                vm['files_sha256'][rel_] = sha(os.path.join(vr, rel_))
        evd = dict(path='native-source-0/' + fname, sha256=ssha if sha_mode == 'ok' else '0' * 64)
        if ev_rect is not None:
            evd['rect'] = ev_rect
        vm['residency_704_256'] = dict(tex=tex_claim, frame=claim_frame, basis='marked_vram_snapshot', evidence=evd)
        if pin:
            vm['files_sha256']['native-source-0/' + fname] = ssha
        rc_v, rep_v = run_tool(vr, vm)
        failing = sorted(g['id'] for g in rep_v.get('gates', []) if not g['passed'])
        rs_all = [f for g in rep_v.get('gates', []) if g['id'] == 'RS' for f in g['failures']]
        # exact-gate rule (support msg_ef793120): a snapshot negative must fail ONLY the expected gate, for the intended reason
        ok = (rc_v == 0 and rep_v.get('pass') is True) if expect == 'pass' else (
            rc_v == 1 and failing == [expect] and (why is None or any(why in f for f in rs_all)))
        results.append(dict(case=label, expect=expect, rc=rc_v, failing=failing, ok=ok, why=why, rs_failures=rs_all[:3]))

    snap_run('r4 positive: native EINRC01 snapshot bound to its mark row', 'pass')
    snap_run('r4 headerless same-size blob (r3 fixture style) rejected', 'RS', why='magic is not EINRC01', header=False)
    snap_run('r4 bad magic', 'RS', why='magic is not EINRC01', hdr_kw=dict(magic=b'EINRC02\x00'))
    snap_run('r4 bad version', 'RS', why='version @8', hdr_kw=dict(version=2))
    snap_run('r4 header frame != claimed frame (wrong-frame relabel)', 'RS', why='header frame 5300 != claimed residency frame', claim_frame=5250)
    snap_run('r4 file name index != header index', 'RS', why='does not carry the header event index', file_index=8)
    snap_run('r4 no mark row for this event file', 'RS', why='found 0', mark_row='none')
    snap_run('r4 mark row label != header label', 'RS', why="label='other_label'", mark_row='badlabel')
    snap_run('r4 duplicated mark rows', 'RS', why='found 2', mark_row='dup')
    snap_run('r4 RAM payload checksum mismatch', 'RS', why='RAM payload FNV-1a', hdr_kw=dict(fr=1234))
    snap_run('r4 VRAM payload checksum mismatch', 'RS', why='VRAM payload FNV-1a', hdr_kw=dict(fv=5678))
    snap_run('r4 VRAM CRC != claimed TEX', 'RS', why='!= claimed TEX DEADBEEF', tex_mode='bad')
    snap_run('r4 evidence sha mismatch', 'RS', why='!= evidence.sha256', sha_mode='bad')
    snap_run('r4 not pinned in files_sha256', 'RS', why='not pinned in files_sha256', pin=False)
    # ---- r5 (support review msg_317d33e3: F1 rect/depth + drawn key, F2 own-session mark row, F4 ms/flags/reserved)
    snap_run('r5 positive: 8bpp native page 128x256 declared and drawn', 'pass', rect='page1')
    snap_run('r5 positive: admission-narrowed 8bpp page (64 words) declared narrowed', 'pass', rect='narrow')
    snap_run('r5 positive: upload rect overlapping the page, drawn as an upload key', 'pass', rect='upload')
    snap_run('r5 8bpp page mis-declared as 64 words (not narrowed)', 'RS', why='width_words 64 != 64<<depth', rect='page1_as_4bpp')
    snap_run('r5 no rect declared (no default assumed)', 'RS', why='evidence.rect is required', rect='none')
    snap_run('r5 claimed TEX never drawn in the run', 'RS', why='is never drawn', drawn=False)
    snap_run('r5 positive: two sessions, each with its own event-0007 and mark row', 'pass', second_session=True)
    snap_run('r5 own session has no mark row; only another session does', 'RS', why='in its own session log, found 0', mark_row='none', second_session=True)
    snap_run('r5 mark row host_mono_ms != header ms', 'RS', why='host_mono_ms=1 != header', row_over=dict(host_mono_ms=1))
    snap_run('r5 mark row gpu_dirty != header flag', 'RS', why='gpu_dirty=0 != header 1', row_over=dict(gpu_dirty=0))
    snap_run('r5 mark row pack_dirty != header flag', 'RS', why='pack_dirty=0 != header 1', row_over=dict(pack_dirty=0))
    snap_run('r5 nonzero reserved header byte', 'RS', why='reserved bytes 88..95', hdr_kw=dict(reserved=7))
    # r5 additions from claude-einhander-support re-review (msg_be013f86, item b)
    snap_run('r5 mark row pending_cpu_upload_rects != header flag', 'RS', why='pending_cpu_upload_rects=3 != header 0', row_over=dict(pending_cpu_upload_rects=3))
    snap_run('r5 mark row cpu_authority_dual != header flag', 'RS', why='cpu_authority_dual=1 != header 0', row_over=dict(cpu_authority_dual=1))
    snap_run('r5 upload rect that does not overlap the 704,256 page', 'RS', why='does not overlap', rect='upload_far')
    snap_run('r5 upload declared but drawn only as a native page', 'RS', why='never drawn in this run as a upload key', rect='upload', draw_kind='native_page')
    # r5 item a (support msg_d0c1c456): the upload draw row must recover the declared origin from page/uv/source_word_xy
    snap_run('r5 upload draw row whose recovered origin != declared rect', 'RS', why='never drawn in this run as a upload key', rect='upload', origin_shift=5)
    variant('r2 non-object JSON rows', 'K', raw=['[1, 2, 3]', '42'])
    # the canonical validator must keep FAILING a timeout leg on its normal gates (never a clear by accident)
    canon_m = copy.deepcopy(base)
    canon_m.update(schema='ein-stage-acquisition-v1', segments=[], fmv=dict(), animation_holds=[], continue_leg=None, game_over_leg=None,
                   loadout={}, clear=None, next_stage_entry=None, bosses=[])
    rc_c, rep_c = run_tool(run, canon_m, tool=CANON)
    failing_c = sorted(g['id'] for g in rep_c.get('gates', []) if not g['passed'])
    results.append(dict(case='canonical validator on the timeout leg', expect='fails X and T', rc=rc_c, failing=failing_c,
                        ok=rc_c == 1 and 'X' in failing_c and 'T' in failing_c))
    allok = all(r['ok'] for r in results)
    print(json.dumps(dict(work=work, cases=len(results), passed=sum(r['ok'] for r in results), all_ok=allok, results=results), indent=1))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
