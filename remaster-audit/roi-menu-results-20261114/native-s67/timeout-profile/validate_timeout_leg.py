#!/usr/bin/env python3
"""PROPOSAL (s67, EIN-S6-TIMEOUT-PROFILE-20261114): validator for the Stage 6 TIMEOUT leg (AQ-13 / readiness M6-11, M6-13).

Isolated from the canonical acquisition tools: it IMPORTS remaster-audit/fullgame-prep/acquisition/validate_acquisition.py
read-only and reuses its route/provenance/card/identity/source/hash semantics unchanged; the canonical tool, its schema and its
normal clear/tally gates are not modified. Main (codex-einhander) owns acquisition-code integration and promotion.

Why a separate profile: an AQ-13 run lets the Stage 6 mission timer expire, so there is no boss destruction, no clear, no tally
and no next stage. The canonical validator fails gates X/T/F/A/L for it by design. This profile validates what the timeout leg
must prove INSTEAD, and it can never count as a Stage 6 clear:

  M  manifest: schema ein-stage6-timeout-leg-v1, leg == "timeout", counts_as_stage_clear is literally false,
     acceptance_eligible is literally false, and none of clear / next_stage_entry / bosses[].destruction is recorded
  R  route: canonical rule (ordinary play; no RAM writes, state loads, stage select or unlock writes; continuous from the
     Stage 5 clear with previous_stage_run lineage), PLUS timer_untouched == true (no timer freeze/extension/RAM poke); a
     disclosed assist is allowed only with acceptance_eligible false
  B  provenance, C cards, H hashes: canonical semantics
  E  Stage 6 identity from visible evidence (entry captures + Stage 5 tally): canonical semantics
  K  complete native source for every key drawn between entry.frame and the last end-state frame: canonical semantics
  TX timer expiry: frame, the visible countdown at zero (>= 1 capture; one 2880x2160 internal), optional read-only RAM log
  MV movie: MOV03 placement after expiry (frame range, identity basis such as the CD read log of MOV03.STR) or an explicit
     none_observed_statement; a movie without an identity basis is a warning, not a pass of identity
  NA narration: the passage index (argument to 0x80048138) with its read-only basis and captures of the narration screen, or an
     explicit not_observed statement with the searched frame range
  RS residency of VRAM 704,256 during the end sequence: resident TEX + frame + basis; when the basis is draw rows, at least one
     draw row with page_xy [704,256] and that TEX must exist in the capture logs inside the end-sequence window
  GO Game Over still: frame range after expiry, 2880x2160 internal capture; drawn TEX listed (e.g. DD1C423A / 0823895F) or
     an explicit statement that no textured still was drawn
  NS next screen after Game Over: frame range and captures
  O  order: entry < timer_expiry <= movie.start <= narration <= game_over <= next_screen, every window inside one capture-log
     span, no stage tally ("SCORE FOR THIS STAGE") recorded after expiry
Not evaluated (and never reported as passed): canonical X, T, F, A, L. The report states counts_as_stage6_clear: false.
Candidate TEX of the timeout leg (content-identified only, readiness): 7AD161DF (4/22 @704,256, medium) and DD1C423A+0823895F
(4/21 16bpp still, low; read stages-v3/ending only). The report says for each whether it was drawn; either answer is valid.

    python validate_timeout_leg.py --run <run folder> [--manifest <path>] [--out <json>]
Exit 0 = every timeout-leg gate passed; 1 = a gate failed; 2 = usage error. Read-only on the run folder.
"""
import argparse
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True
CANON = os.environ.get('EIN_ACQ_VALIDATOR',
                       'C:/github/Einhander/remaster-audit/fullgame-prep/acquisition/validate_acquisition.py')
SCHEMA_ID = 'ein-stage6-timeout-leg-v1'
RS_TOLERANCE = 60          # frames: draw rows are sampled (recorder default repeat_sample_frames 60)
REVISION = ("r5 (2026-11-14, claude-einhander-support review msg_317d33e3): marked_vram_snapshot evidence must DECLARE its key rect (native_page at 704,256 with depth 0/1/2 and width 64<<depth or an explicitly narrowed multiple of 64; or an upload rect overlapping the 704,256 page) and the snapshot CRC is computed over exactly that rect; the claimed TEX must be drawn in the run with the same kind/depth/size; the mark row is taken ONLY from the capture.jsonl in the event file's own directory (research sessions restart event numbering); header ms@24 == row host_mono_ms, header flags @48/52/56/60 == row gpu_dirty/pending_cpu_upload_rects/pack_dirty/cpu_authority_dual, reserved header bytes 88..95 == 0; an upload/exact_region draw row must recover the declared origin (page + u_first/ppw - source_word_xy, mod VRAM). Includes "
            "r4 (2026-11-14): marked_vram_snapshot bound to the native EINRC01 format (hd_research_event.h): magic, version, "
            "header/offset/size fields, label, header event index == file name, header frame == claimed frame, exactly one matching "
            "mark row (event_file, index, label, frame, bytes), VRAM rect CRC == TEX, RAM/VRAM FNV-1a payload checksums. Includes "
            "r3 (2026-11-14): residency bases bound to evidence: upload_event UNSUPPORTED until its schema exists; "
            "marked_vram_snapshot needs a pinned receipt (in-run path, sha256 == evidence == files_sha256, EINRC01 size, VRAM "
            "704,256 rect CRC32 == claimed TEX, mark event at the claimed frame). Includes "
            "r2 (2026-11-14): stage literal int 6, in-span entry/expiry/narration/residency frames, residency bound to its "
            "evidence at its frame, strict entry < expiry, not-observed narration search must cover expiry..last end state "
            "inside a capture span, non-object JSON rows reported instead of crashing")
CANDIDATE_TEX = {'7AD161DF': '4/22 narration page @704,256 (medium)', 'DD1C423A': '4/21 16bpp still part (low)',
                 '0823895F': '4/21 16bpp still part (low)'}


def load_canon():
    spec = importlib.util.spec_from_file_location('ein_validate_acquisition_canon', CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SNAPSHOT_BYTES = 160 + 2097152 + 1048576    # HDR_EVENT_BYTES (runtime/src/hd_research_event.h)
NATIVE_FORMAT = 'windows-x64/psxrecomp/runtime/src/hd_research_event.h hdr_build_event (ein-research-v1)'


def hdr_fnv(data):
    """FNV-1a 32 exactly as hdr_fnv() in hd_research_event.h."""
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def mark_rows(run, logs):
    """research 'mark' rows (event_file, event_index, label, frame, bytes) from the capture logs; non-objects skipped."""
    out = []
    for lg in logs:
        with open(os.path.join(run, lg['path']), encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and e.get('event') == 'mark':
                    out.append(dict(log=lg['path'], line=i, event_file=e.get('event_file'), event_index=e.get('event_index'),
                                    label=e.get('label'), frame=e.get('frame'), bytes=e.get('bytes'),
                                    stale=e.get('cpu_vram_may_be_stale'), host_mono_ms=e.get('host_mono_ms'),
                                    gpu_dirty=e.get('gpu_dirty'), pending_cpu_upload_rects=e.get('pending_cpu_upload_rects'),
                                    pack_dirty=e.get('pack_dirty'), cpu_authority_dual=e.get('cpu_authority_dual')))
    return out


RESIDENCY_PAGE = (704, 256)


def declared_rect(ev):
    """(spec, problems) for evidence.rect. native_page: x,y = 704,256, depth 0/1/2, width_words = 64<<depth unless narrowed (then a
    smaller multiple of 64, >= 64), height 256 (hd_native_page.h hd_page_hash_width). upload: x, y, width_words, height of the upload's
    own rect (hd_texture_pack.cpp), which must overlap the 4bpp footprint of the 704,256 page. Nothing is assumed by default."""
    r = ev.get('rect')
    if not isinstance(r, dict):
        return None, ['evidence.rect is required: {kind: native_page, x, y, depth, width_words[, narrowed]} or '
                      '{kind: upload, x, y, width_words, height} (r5: no default rect is assumed)']
    ints = lambda *ks: all(type(r.get(k)) is int for k in ks)
    if r.get('kind') == 'native_page':
        if not ints('x', 'y', 'depth', 'width_words'):
            return None, ['evidence.rect native_page needs integer x, y, depth, width_words']
        probs = []
        if (r['x'], r['y']) != RESIDENCY_PAGE:
            probs.append(f'evidence.rect page ({r["x"]},{r["y"]}) is not the residency page {RESIDENCY_PAGE}')
        if r['depth'] not in (0, 1, 2):
            probs.append(f'evidence.rect depth {r["depth"]} not in 0/1/2')
        else:
            full_w = 64 << r['depth']
            w = r['width_words']
            if r.get('narrowed') is True:
                if not (64 <= w < full_w and w % 64 == 0):
                    probs.append(f'narrowed width_words {w} must be a multiple of 64 in [64, {full_w})')
            elif w != full_w:
                probs.append(f'width_words {w} != 64<<depth = {full_w} (declare narrowed: true for an admission-narrowed page)')
        return (dict(kind='native_page', x=r['x'], y=r['y'], w=r['width_words'], h=256, depth=r['depth']) if not probs else None), probs
    if r.get('kind') == 'upload':
        if not ints('x', 'y', 'width_words', 'height'):
            return None, ['evidence.rect upload needs integer x, y, width_words, height']
        probs = []
        if not (0 <= r['x'] < 1024 and 0 <= r['y'] < 512 and 1 <= r['width_words'] <= 1024 and 1 <= r['height'] <= 512):
            probs.append(f'evidence.rect upload {r} is outside VRAM')
        px, py = RESIDENCY_PAGE
        if not (r['x'] < px + 64 and px < r['x'] + r['width_words'] and r['y'] < py + 256 and py < r['y'] + r['height']):
            probs.append(f'evidence.rect upload {r} does not overlap the 704,256 page footprint')
        return (dict(kind='upload', x=r['x'], y=r['y'], w=r['width_words'], h=r['height'], depth=None) if not probs else None), probs
    return None, [f'evidence.rect kind {r.get("kind")!r} must be native_page or upload']


def rect_crc(vram, spec, C):
    """CRC32 of the declared rect's LE words, row-major, wrapping like the runtime ((y+row)&511, (x+col)&1023)."""
    out = bytearray()
    for row in range(spec['h']):
        yy = (spec['y'] + row) & 511
        for col in range(spec['w']):
            o = (yy * 1024 + ((spec['x'] + col) & 1023)) * 2
            out += vram[o:o + 2]
    return C.crc32_hex(bytes(out))


def drawn_rows(run, logs, tex, spec):
    """Draw rows of this TEX whose kind/size (and page/depth for native pages) match the declared rect."""
    hits = []
    for lg in logs:
        with open(os.path.join(run, lg['path']), encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(e, dict) or e.get('event') not in ('source_draw_query_matched', 'replacement_gl_draw_submitted'):
                    continue
                if str(e.get('key', ''))[:8] != tex:
                    continue
                if spec['kind'] == 'native_page':
                    ok = (e.get('source_kind') == 'native_page' and e.get('page_xy') == [spec['x'], spec['y']]
                          and e.get('depth') == spec['depth'] and e.get('native_words') == [spec['w'], 256])
                else:
                    ok = e.get('source_kind') in ('upload', 'exact_region') and e.get('native_words') == [spec['w'], spec['h']]
                    # r5 item a (support msg_d0c1c456; hd_texture_pack.cpp:883-886, 1548-1561): source_word_xy is the first texel's
                    # offset inside the upload, so the upload origin is page + u_first/ppw - source_word (mod VRAM)
                    pg, uvb, swx, dp = e.get('page_xy'), e.get('uv_bounds'), e.get('source_word_xy'), e.get('depth')
                    ppw = {0: 4, 1: 2, 2: 1}.get(dp)
                    if ok and ppw and all(isinstance(x, list) and len(x) >= 2 and all(type(c) is int for c in x[:2]) for x in (pg, uvb, swx)):
                        ok = ((pg[0] + uvb[0] // ppw - swx[0]) % 1024, (pg[1] + uvb[1] - swx[1]) % 512) == (spec['x'], spec['y'])
                    else:
                        ok = False
                if ok:
                    hits.append(dict(log=lg['path'], line=i, frame=e.get('frame')))
    return hits


def snapshot_problems(run, m, rs, logs, C, info):
    """marked_vram_snapshot residency bound to the NATIVE event format and to its own mark row; returns problems (empty = bound).
    Order: pin/size, native header, identity (filename index, header frame == claimed frame, label), matching mark row,
    VRAM rect CRC == claimed TEX, then the full-payload FNV-1a checksums (most expensive last). Fails closed."""
    import re as _re
    import struct
    ev = rs.get('evidence') if isinstance(rs.get('evidence'), dict) else None
    if not ev or not ev.get('path') or not ev.get('sha256'):
        return ['basis marked_vram_snapshot needs evidence {path, sha256} of the event file (label-only claims are rejected)']
    full = os.path.abspath(os.path.join(run, ev['path']))
    if not full.startswith(os.path.abspath(run) + os.sep):
        return [f'snapshot evidence {ev["path"]} is outside the run folder']
    if not os.path.isfile(full):
        return [f'snapshot evidence missing: {ev["path"]}']
    actual = C.sha256(full)
    if actual != ev['sha256']:
        return [f'snapshot sha256 {actual} != evidence.sha256 {ev["sha256"]}']
    if (m.get('files_sha256') or {}).get(ev['path']) != actual:
        return [f'snapshot {ev["path"]} is not pinned in files_sha256 with its actual hash']
    size = os.path.getsize(full)
    if size != SNAPSHOT_BYTES:
        return [f'snapshot size {size} != HDR_EVENT_BYTES {SNAPSHOT_BYTES}']
    blob = open(full, 'rb').read()
    u32 = lambda o: struct.unpack_from('<I', blob, o)[0]
    u64 = lambda o: struct.unpack_from('<Q', blob, o)[0]
    probs = []
    if blob[:8] != b'EINRC01\x00':
        probs.append('native header: magic is not EINRC01\\0')
    want = {8: ('version', 1), 12: ('header bytes', 160), 32: ('RAM offset', 160), 36: ('RAM bytes', 2097152),
            40: ('VRAM offset', 2097312), 44: ('VRAM bytes', 1048576), 84: ('format flag', 1)}
    for off, (name, val) in want.items():
        if u32(off) != val:
            probs.append(f'native header: {name} @{off} = {u32(off)} != {val}')
    if any(blob[88:96]):
        probs.append('native header: reserved bytes 88..95 are not zero')
    n = u32(80)
    label = blob[96:96 + n] if 0 < n <= 63 else b''
    if not label or not _re.fullmatch(rb'[A-Za-z0-9_-]{1,63}', label) or any(blob[96 + n:160]):
        probs.append(f'native header: label length {n} / label bytes invalid')
    if probs:
        return probs
    frame, index, label = u64(16), u32(76), label.decode('ascii')
    info.update(header_frame=frame, header_ms=u64(24), event_index=index, label=label, gpu_dirty=u32(48), pending_cpu_upload_rects=u32(52),
                pack_dirty=u32(56), cpu_authority_dual=u32(60), renderer=u32(64), native_format=NATIVE_FORMAT)
    mname = _re.fullmatch(r'event-(\d{4,})\.bin', os.path.basename(full))
    if not mname or int(mname.group(1)) != index:
        probs.append(f'event file name {os.path.basename(full)} does not carry the header event index {index}')
    if frame != rs.get('frame'):
        probs.append(f'header frame {frame} != claimed residency frame {rs.get("frame")!r}')
    if ev.get('label') is not None and ev.get('label') != label:
        probs.append(f'evidence.label {ev.get("label")!r} != header label {label!r}')
    own_dir = os.path.dirname(full)
    own_logs = [lg for lg in logs if os.path.dirname(os.path.abspath(os.path.join(run, lg['path']))) == own_dir]
    if not own_logs:
        probs.append(f'no capture log is listed in the event file\'s own directory {os.path.relpath(own_dir, run)} '
                     '(research sessions restart event numbering, so a mark row is bound only within its own session)')
    rows = [r for r in mark_rows(run, own_logs) if r['event_file'] == os.path.basename(full)]
    if own_logs and len(rows) != 1:
        probs.append(f'expected exactly one mark row for {os.path.basename(full)} in its own session log, found {len(rows)} '
                     '(an unlogged or duplicated mark cannot be bound)')
    elif len(rows) == 1:
        r = rows[0]
        for k_, v_ in (('event_index', index), ('label', label), ('frame', frame), ('bytes', SNAPSHOT_BYTES),
                       ('host_mono_ms', u64(24)), ('gpu_dirty', u32(48)), ('pending_cpu_upload_rects', u32(52)),
                       ('pack_dirty', u32(56)), ('cpu_authority_dual', u32(60))):
            if r[k_] != v_:
                probs.append(f'mark row {r["log"]}:{r["line"]} {k_}={r[k_]!r} != header {v_!r}')
        info['mark_row'] = r
    if probs:
        return probs
    spec, rprobs = declared_rect(ev)
    if rprobs:
        return rprobs
    vram = blob[2097312:2097312 + 1048576]
    tex = rect_crc(vram, spec, C)
    info['declared_rect'] = spec
    if tex != str(rs.get('tex', '')).upper():
        return [f'snapshot VRAM rect {spec["kind"]} ({spec["x"]},{spec["y"]},{spec["w"]}x{spec["h"]}) CRC32 {tex} != claimed TEX {rs.get("tex")}']
    hits = drawn_rows(run, logs, tex, spec)
    info['drawn_rows'] = hits[:5]
    if not hits:
        return [f'claimed TEX {tex} is never drawn in this run as a {spec["kind"]} key of the declared size'
                + (f' on page {RESIDENCY_PAGE} depth {spec["depth"]}' if spec['kind'] == 'native_page' else '')
                + ' (a rect CRC alone is not a runtime key)']
    if hdr_fnv(blob[160:160 + 2097152]) != u32(68):
        probs.append('native RAM payload FNV-1a != header checksum @68 (corrupt or edited snapshot)')
    if hdr_fnv(vram) != u32(72):
        probs.append('native VRAM payload FNV-1a != header checksum @72 (corrupt or edited snapshot)')
    if not probs and (u32(48) or u32(52)):
        info['warning'] = ('CPU-VRAM mirror may be stale (gpu_dirty/pending set); accepted only because the declared rect CRC '
                           'matches the claimed TEX exactly and that TEX is drawn in the run (checklist rule: a CPU-mirror read counts '
                           'only on an exact CRC match)')
    return probs


def nonobject_rows(run, logs):
    """[log, line] of JSON rows that parse but are not objects; the canonical scan_logs would raise on them."""
    bad = []
    for lg in logs:
        with open(os.path.join(run, lg['path']), encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(e, dict):
                    bad.append([lg['path'], i])
    return bad


def page_draws(run, logs, window, page_xy):
    """TEX halves drawn on one VRAM page inside a frame window (draw rows only; not visibility proof)."""
    tex = {}
    for lg in logs:
        p = os.path.join(run, lg['path'])
        with open(p, encoding='utf-8') as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(e, dict):
                    continue
                if e.get('event') != 'source_draw_query_matched' or e.get('page_xy') != page_xy:
                    continue
                fr = e.get('frame')
                if window and not (isinstance(fr, int) and window[0] <= fr <= window[1]):
                    continue
                k = str(e.get('key', ''))
                t = tex.setdefault(k[:8], dict(rows=0, first=fr, last=fr))
                t['rows'] += 1
                t['first'], t['last'] = min(t['first'], fr), max(t['last'], fr)
    return tex


def validate(run, m, C):
    rep = C.Report()
    D = C.as_dict
    # ---- M
    rep.gate('M', 'timeout-leg manifest')
    if m.get('schema') != SCHEMA_ID:
        rep.fail('M', f'schema must be {SCHEMA_ID}')
    if m.get('leg') != 'timeout':
        rep.fail('M', 'leg must be "timeout"')
    sn = D(m.get('stage')).get('number')
    if type(sn) is not int or sn != 6:
        rep.fail('M', f'stage.number must be the integer 6 (got {sn!r}); it is never overwritten or coerced')
    if m.get('counts_as_stage_clear') is not False:
        rep.fail('M', 'counts_as_stage_clear must be literally false: a timeout leg is never a Stage 6 clear')
    if D(m.get('route')).get('acceptance_eligible') is not False:
        rep.fail('M', 'route.acceptance_eligible must be literally false (acquisition runs are never acceptance evidence)')
    if m.get('clear') not in (None, {}) or m.get('next_stage_entry') not in (None, {}):
        rep.fail('M', 'clear / next_stage_entry must be null in a timeout leg')
    if any(isinstance(D(b).get('destruction'), dict) for b in m.get('bosses') or []):
        rep.fail('M', 'a boss destruction was recorded: this is not a timeout leg')
    # ---- R (canonical rule + timer)
    rep.gate('R', 'admissible route (ordinary play; chained to the Stage 5 clear; timer untouched)')
    r = D(m.get('route'))
    for fld in ('ram_writes', 'state_loads', 'stage_select_used', 'unlock_bits_written'):
        if r.get(fld) is not False:
            rep.fail('R', f'route.{fld} must be false (got {r.get(fld)!r})')
    if r.get('method') != 'continuous_from_previous_stage_clear' and r.get('method') != 'natural_save_then_next_stage_entry':
        rep.fail('R', 'method must be continuous_from_previous_stage_clear or natural_save_then_next_stage_entry')
    if not D(r.get('previous_stage_run')).get('manifest_sha256'):
        rep.fail('R', 'previous_stage_run (Stage 5 clear run id + manifest_sha256) missing', missing='lineage: the run that cleared stage 5')
    if r.get('timer_untouched') is not True:
        rep.fail('R', 'route.timer_untouched must be true (no timer freeze, extension or RAM poke)', missing='timer-untouched declaration')
    if D(r.get('assist')).get('used') is not False and r.get('acceptance_eligible') is not False:
        rep.fail('R', 'assisted run must set acceptance_eligible false')
    # ---- B / C / E / H via the canonical manifest checks on a copy that carries only those parts
    shell = dict(m)   # r2: the declared stage is NOT overwritten; a non-6 stage has already failed M
    sub = C.Report()
    C.validate_manifest(sub, run, shell, {}, [], {})
    for gid in ('B', 'C', 'E', 'H'):
        g = sub.gates.get(gid)
        if g:
            rep.gates[gid] = g
    for it in sub.missing:
        if it['gate'] in ('B', 'C', 'E', 'H'):
            rep.missing.append(it)
    # ---- windows
    ent = D(m.get('entry')).get('frame')
    tx, mv, na, rs, go, ns = (D(m.get(k)) for k in ('timer_expiry', 'movie', 'narration', 'residency_704_256', 'game_over_still', 'next_screen'))
    ends = [x.get('frame_range')[1] for x in (ns, go) if C.is_range(x.get('frame_range'))]
    last = max(ends) if ends else None
    window = [ent, last] if isinstance(ent, int) and isinstance(last, int) and ent <= last else None
    logs = [l for l in [D(x) for x in m.get('capture_logs') or []] if os.path.isfile(os.path.join(run, str(l.get('path', ''))))]
    malformed = nonobject_rows(run, logs)
    try:
        keys, fam, marks, missing_fields, spans = C.scan_logs(run, logs, window)
        scan_error = None
    except (AttributeError, TypeError) as exc:   # canonical scan cannot parse non-object JSON rows
        keys, fam, marks, missing_fields, spans = {}, {}, [], {}, []
        scan_error = f'{exc.__class__.__name__}: {exc}'
    observed = [s_['observed'] for s_ in spans if s_['observed'][0] is not None]

    def in_span(fr):
        return isinstance(fr, int) and any(o[0] <= fr <= o[1] for o in observed)

    def rng_in_span(r_):
        return C.is_range(r_) and any(o[0] <= r_[0] and r_[1] <= o[1] for o in observed)
    # ---- K (canonical semantics)
    rep.gate('K', 'complete native source for every drawn key (entry .. last end-state frame)')
    if malformed:
        rep.fail('K', f'{len(malformed)} non-object JSON row(s) in capture logs (first {malformed[:3]}); capture integrity needs review',
                 missing='well-formed capture-log rows')
    if scan_error:
        rep.fail('K', f'canonical scan_logs could not parse the logs ({scan_error}); keys and spans not evaluated')
    if window is None:
        rep.fail('K', 'window entry.frame .. last end-state frame is not set')
    src = C.index_sources(run, [d for d in m.get('source_dirs') or [] if isinstance(d, str)])
    for k in sorted(keys):
        probs = ['no source quad in source_dirs'] if k not in src else C.check_source(src[k], k)
        if probs:
            rep.fail('K', f'{k}: ' + '; '.join(probs), missing=f'source {k}')
    for fld, n in missing_fields.items():
        rep.fail('K', f'{n} draw records lack field {fld}')
    if not keys:
        rep.fail('K', 'no draw records in the timeout window', missing='draw records entry .. end states')
    # ---- TX
    rep.gate('TX', 'mission timer expiry')
    if not isinstance(tx.get('frame'), int):
        rep.fail('TX', 'timer_expiry.frame missing', missing='frame where the Stage 6 countdown reaches zero')
    else:
        C.check_captures(rep, 'TX', run, tx.get('captures'), 'timer expiry', [tx['frame'] - 120, tx['frame'] + 120])
    if not tx.get('countdown_zero_visible'):
        rep.fail('TX', 'timer_expiry.countdown_zero_visible must be true (visible evidence, not RAM)', missing='visible countdown at zero')
    # ---- MV
    rep.gate('MV', 'movie placement after expiry (MOV03 candidate)')
    if not mv.get('observed') and not mv.get('none_observed_statement'):
        rep.fail('MV', 'record the movie (frame_range + identity basis) or an explicit none_observed_statement', missing='movie placement')
    if mv.get('observed'):
        if not C.is_range(mv.get('frame_range')):
            rep.fail('MV', 'movie.frame_range missing')
        if not mv.get('identity_basis'):
            rep.warn('MV', 'movie identity basis missing (for example the CD read log of MOV03.STR); identity stays unverified')
    # ---- NA
    rep.gate('NA', 'narration passage')
    if na.get('observed'):
        if type(na.get('passage_index')) is not int:
            rep.fail('NA', 'narration.passage_index (argument to 0x80048138) missing', missing='narration passage index')
        if not na.get('basis'):
            rep.fail('NA', 'narration.basis missing (read-only breakpoint/log reference)')
        if not C.is_range(na.get('frame_range')):
            rep.fail('NA', f'observed narration needs a valid frame_range (got {na.get("frame_range")!r})')
        else:
            C.check_captures(rep, 'NA', run, na.get('captures'), 'narration', na.get('frame_range'), need_internal=False)
    else:
        sr = na.get('searched_frame_range')
        need = [tx.get('frame'), last] if isinstance(tx.get('frame'), int) and isinstance(last, int) else None
        if not na.get('not_observed_statement') or not C.is_range(sr):
            rep.fail('NA', 'record the narration passage or an explicit not_observed_statement with searched_frame_range',
                     missing='narration passage evidence')
        elif need is None or not (sr[0] <= need[0] and need[1] <= sr[1]):
            rep.fail('NA', f'searched_frame_range {sr} must cover the whole end sequence, timer expiry .. last end state {need}')
        elif not rng_in_span(sr):
            rep.fail('NA', f'searched_frame_range {sr} is not inside one capture-log span {observed}')
    # ---- RS
    rep.gate('RS', 'VRAM 704,256 residency during the end sequence')
    rs_snapshot_info = {}
    pd = page_draws(run, logs, [tx.get('frame', 0) or 0, last] if isinstance(last, int) else window, [704, 256])
    if not rs.get('tex') or type(rs.get('frame')) is not int or not rs.get('basis'):
        rep.fail('RS', 'residency_704_256 needs tex, frame and basis', missing='704,256 resident TEX in the end sequence')
    else:
        rf = rs['frame']
        if not (isinstance(tx.get('frame'), int) and isinstance(last, int) and tx['frame'] <= rf <= last):
            rep.fail('RS', f'residency frame {rf} is outside timer expiry .. last end state [{tx.get("frame")}, {last}]')
        if rs['basis'] == 'draw_rows':
            near = page_draws(run, logs, [rf - RS_TOLERANCE, rf + RS_TOLERANCE], [704, 256])
            if rs['tex'] not in near:
                rep.fail('RS', f'basis draw_rows: no draw row on page 704,256 with TEX {rs["tex"]} within +-{RS_TOLERANCE} frames of {rf}')
            others = sorted(t for t in near if t != rs['tex'])
            if others:
                rep.fail('RS', f'ambiguous residency at {rf}: page 704,256 also draws TEX {others} within +-{RS_TOLERANCE} frames')
        elif rs['basis'] == 'marked_vram_snapshot':
            snap_info = {}
            for prob in snapshot_problems(run, m, rs, logs, C, snap_info):
                rep.fail('RS', prob)
            if snap_info.get('warning'):
                rep.warn('RS', snap_info['warning'])
            rs_snapshot_info.update(snap_info)
        elif rs['basis'] == 'upload_event':
            rep.fail('RS', 'basis upload_event is UNSUPPORTED in this proposal: no pinned upload-event schema exists yet '
                           '(integration owner to supply it); use draw_rows or a pinned marked_vram_snapshot')
        else:
            rep.fail('RS', f'unknown residency basis {rs["basis"]!r} (supported: draw_rows | marked_vram_snapshot)')
    # ---- GO
    rep.gate('GO', 'Game Over still')
    if not C.is_range(go.get('frame_range')):
        rep.fail('GO', 'game_over_still.frame_range missing', missing='Game Over still frame range')
    else:
        C.check_captures(rep, 'GO', run, go.get('captures'), 'game over still', go.get('frame_range'))
    if not go.get('drawn_tex') and not go.get('no_textured_still_statement'):
        rep.fail('GO', 'list the drawn TEX of the still, or state that no textured still was drawn')
    # ---- NS
    rep.gate('NS', 'next screen after Game Over')
    if not C.is_range(ns.get('frame_range')):
        rep.fail('NS', 'next_screen.frame_range missing', missing='screen that follows Game Over')
    else:
        C.check_captures(rep, 'NS', run, ns.get('captures'), 'next screen', ns.get('frame_range'), need_internal=False)
    # ---- O order + spans + no tally
    rep.gate('O', 'end-state order inside the capture spans; no stage tally')
    seq = [('entry', ent), ('timer_expiry', tx.get('frame')), ('movie', (mv.get('frame_range') or [None])[0] if mv.get('observed') else None),
           ('narration', (na.get('frame_range') or [None])[0] if na.get('observed') else None),
           ('game_over', (go.get('frame_range') or [None])[0]), ('next_screen', (ns.get('frame_range') or [None])[0])]
    present = [(n, f) for n, f in seq if isinstance(f, int)]
    for (n0, f0), (n1, f1) in zip(present, present[1:]):
        if f1 < f0 or (n0 == 'entry' and f1 <= f0):
            rep.fail('O', f'{n1} ({f1}) must be {"after" if n0 == "entry" else "at or after"} {n0} ({f0})')
    if not observed:
        rep.fail('O', 'no capture-log span observed; end-state frames cannot be placed')
    for n, fr in (('entry', ent), ('timer_expiry', tx.get('frame')), ('residency_704_256', rs.get('frame'))):
        if isinstance(fr, int) and observed and not in_span(fr):
            rep.fail('O', f'{n} frame {fr} is not inside a capture-log span {observed}')
    for n, rng in (('movie', mv.get('frame_range') if mv.get('observed') else None),
                   ('narration', na.get('frame_range') if na.get('observed') else None),
                   ('game_over', go.get('frame_range')), ('next_screen', ns.get('frame_range'))):
        if C.is_range(rng) and observed and not rng_in_span(rng):
            rep.fail('O', f'{n} {rng} is not inside one capture-log span {observed}')
    if m.get('stage_tally_after_expiry') is not False:
        rep.fail('O', 'stage_tally_after_expiry must be false (a tally means the stage was cleared, not timed out)')
    for mk in marks:
        if str(mk.get('label', '')).startswith(('clear:6', 'tally:stage6')):
            rep.fail('O', f'mark {mk.get("label")} at frame {mk.get("frame")} contradicts a timeout leg')
    # ---- candidate TEX report (answers, not gates)
    drawn_tex = {k[:8] for k in keys}
    cand = {t: dict(note=n, drawn=t in drawn_tex) for t, n in CANDIDATE_TEX.items()}
    return rep, dict(residency_snapshot=rs_snapshot_info or None, window=window, keys_drawn=len(keys), candidate_tex=cand, page_704_256_tex=pd, marks=marks[:200])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', required=True)
    ap.add_argument('--manifest')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    run = os.path.abspath(a.run)
    mp = a.manifest or os.path.join(run, 'timeout-leg-manifest.json')
    if not os.path.isdir(run) or not os.path.isfile(mp):
        print('run folder or manifest missing', file=sys.stderr)
        return 2
    C = load_canon()
    m = json.load(open(mp, encoding='utf-8'))
    rep, extra = validate(run, m, C)
    out = dict(schema='ein-stage6-timeout-leg-validation-v1', profile='timeout-leg (proposal)', revision=REVISION, run=run.replace('\\', '/'),
               manifest=dict(path=mp.replace('\\', '/'), sha256=C.sha256(mp)), validator_sha256=C.sha256(os.path.abspath(__file__)),
               canonical_validator=dict(path=CANON, sha256=C.sha256(CANON)), counts_as_stage6_clear=False,
               not_evaluated=dict(gates=['X', 'T', 'F', 'A', 'L'], reason='a timeout leg has no boss destruction, clear, tally, '
                                  'stage FMV hold or continue requirement; these canonical gates are NOT passed by this report'),
               gates=list(rep.gates.values()), missing=rep.missing, **extra)
    out['pass'] = all(g['passed'] for g in rep.gates.values() if g['required'])
    text = json.dumps(out, indent=1, default=str)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, 'w', encoding='utf-8').write(text)
    else:
        print(text)
    print('PASS' if out['pass'] else 'FAIL', {gid: g['passed'] for gid, g in rep.gates.items()}, 'missing', len(rep.missing), file=sys.stderr)
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
