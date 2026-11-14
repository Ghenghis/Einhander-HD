#!/usr/bin/env python3
"""claude-einhander-support F3 reproduction (EIN-SUPPORT-F3-REPRO-20261114): mark-row reserve leak in the research recorder.

  python -B -I build_and_run.py --prepare            pins + exact extraction + variant headers + reviewable patch (text only)
  python -B -I build_and_run.py --run --out <new dir> --cap-s <grant cap> [--affinity-hex <mask>]
                                                     gate, compile 6 variants with clang, run, evaluate, write result.json

What it does:
- Reads the canonical runtime sources read-only, pinned by sha256. Never edits them.
- From hd_research_renderer.h it extracts the event-reserve / evidence-room block verbatim. It also extracts these
  statements, each required to occur exactly once:
  - the draw-row cap (:107);
  - the draw byte check (:116);
  - the draw commit (:117);
  - the mark row (:77).
- Variant headers:
  - current: canonical text unchanged.
  - patched: the proposal.
  - m1_offbyone, m2_nobytes, m3_nowrapguard, m4_staticreserve: mutations of the patch; each must be caught.
- Run mode, under a grant:
  - sets its own process to BelowNormal and to the granted affinity, which compiler and harness children inherit;
  - compiles sequentially and runs each harness with a per-child timeout and a total cap.
  - Exit 0 means: the current text reproduces the leak, the patch passes every scenario and boundary, and every mutant
    is caught.
"""
import argparse, ctypes, datetime, difflib, hashlib, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path('C:/github/Einhander/windows-x64/psxrecomp/runtime/src')
PINS = {
    'hd_research_renderer.h': '3ffdf13f664a5a69cf84d355d114c7ddf8b263c4412d48299526231824a67b74',
    'hd_research_sample.h': '8b8346dbc5c95dc6508464bc20c1008aaf935820f09eee76e3abeb5c96217c97',
    'hd_research_capture.h': 'cd935b85ca9b13c4c3d252835d5bc631c70bf61b1aab360a530ddc1f8ac3c3ad',
    'hd_research_event.h': '22ed3be41c915d0649ea8636f45355344b586ba596989f2693f37454b3184b62',
    'gpu_gl_renderer.c': '92d080578d2a3d734160deae1d67ae186b08f4e9f7ca2d5ecdd3d5344b37d03c',
}
CLANG = 'C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe'

DRAW_CAP = 'if(s_hd_research.records>=s_hd_research.limits.max_records){++s_hd_research_sampler.record_cap_skips;return;}'
DRAW_BYTES = 'if(!hd_research_evidence_room(strlen(line)+1,0)){++s_hd_research_sampler.budget_skips;return;}'
DRAW_COMMIT = 'if(hdrc_json(&s_hd_research,line,frame,now))hdr_sample_commit(&s_hd_research_sampler,sample,frame);'
MARK_ROW = ('if(s_hd_research.records<s_hd_research.limits.max_records && hd_research_evidence_room(strlen(line)+1,0))'
            'hdrc_json(&s_hd_research,line,frame,now);')
BLOCK_START = 'static unsigned hd_research_event_files_reserve(void){'
BLOCK_END = 'static int hd_research_ready(void)'
RESERVE_LINE = ' uint64_t reserve=hd_research_event_bytes_reserve();unsigned reserve_files=hd_research_event_files_reserve();'
MARK_LINE_BUF = 'char leaf[64],line[768]'
SAMPLE_START = 'hdr_sample_start(&s_hd_research_sampler,chosen.max_records,chosen.max_events,chosen.max_seconds,s_hd_research.start_ms);'

# ---- the proposal (reviewable text) ----
PATCH_DEFINES = (
    '/* F3 (support proposal EIN-SUPPORT-F3-REPRO-20261114): each future mark needs one JSON record and at most 768 bytes\n'
    ' * (its line is formatted into char line[768] in gl_renderer_research_mark). capture_start is counted in records before\n'
    ' * any draw, and hdrc_stop writes no row, so no tail row is reserved today; raise HD_RESEARCH_TAIL_ROWS if one is added. */\n'
    '#define HD_RESEARCH_MARK_LINE_MAX 768u\n'
    '#define HD_RESEARCH_TAIL_ROWS 0u\n')
RESERVE_LINE_PATCHED = (' uint64_t reserve=hd_research_event_bytes_reserve()+(uint64_t)hd_research_event_files_reserve()*HD_RESEARCH_MARK_LINE_MAX;'
                        'unsigned reserve_files=hd_research_event_files_reserve();')
ROOM_FN = (
    '/* F3: a draw row may take a JSON record only while one record per still-markable event (plus tail rows) stays free.\n'
    ' * hd_research_event_files_reserve() is 0 once events are exhausted; the subtraction runs only when records<max. */\n'
    'static int hd_research_draw_record_room(void){\n'
    ' unsigned left=hd_research_event_files_reserve();\n'
    ' return s_hd_research.records<s_hd_research.limits.max_records &&\n'
    '  s_hd_research.limits.max_records-s_hd_research.records>left+HD_RESEARCH_TAIL_ROWS;\n'
    '}\n')
DRAW_CAP_PATCHED = 'if(!hd_research_draw_record_room()){++s_hd_research_sampler.record_cap_skips;return;}'
MUTANTS = {
    'm1_offbyone': ('>left+HD_RESEARCH_TAIL_ROWS;', '>=left+HD_RESEARCH_TAIL_ROWS;'),
    'm3_nowrapguard': (' return s_hd_research.records<s_hd_research.limits.max_records &&\n  s_hd_research',
                       ' return s_hd_research'),
    'm4_staticreserve': (' unsigned left=hd_research_event_files_reserve();', ' unsigned left=s_hd_research.limits.max_events;'),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def prepare():
    pins = {n: sha(SRC / n) for n in PINS}
    bad = {n: h for n, h in pins.items() if h != PINS[n]}
    if bad:
        raise SystemExit(f'pin mismatch (sources changed; re-review before use): {bad}')
    r = (SRC / 'hd_research_renderer.h').read_text(encoding='utf-8')
    checks = {}
    for name, s in (('DRAW_CAP', DRAW_CAP), ('DRAW_BYTES', DRAW_BYTES), ('DRAW_COMMIT', DRAW_COMMIT), ('MARK_ROW', MARK_ROW),
                    ('BLOCK_START', BLOCK_START), ('BLOCK_END', BLOCK_END), ('RESERVE_LINE', RESERVE_LINE),
                    ('MARK_LINE_BUF', MARK_LINE_BUF), ('SAMPLE_START', SAMPLE_START)):
        checks[name] = r.count(s)
    checks['renderer_hdrc_json_calls'] = r.count('hdrc_json(')
    checks['gpu_gl_renderer_hdrc_json_calls'] = (SRC / 'gpu_gl_renderer.c').read_text(encoding='utf-8', errors='replace').count('hdrc_json(')
    cap = (SRC / 'hd_research_capture.h').read_text(encoding='utf-8')
    checks['capture_hdrc_json_definitions_only'] = cap.count('hdrc_json(')
    need = {k: 1 for k in ('DRAW_CAP', 'DRAW_BYTES', 'DRAW_COMMIT', 'MARK_ROW', 'BLOCK_START', 'BLOCK_END', 'RESERVE_LINE',
                           'MARK_LINE_BUF', 'SAMPLE_START')}
    need.update(renderer_hdrc_json_calls=3, gpu_gl_renderer_hdrc_json_calls=0, capture_hdrc_json_definitions_only=1)
    wrong = {k: (checks[k], v) for k, v in need.items() if checks[k] != v}
    if wrong:
        raise SystemExit(f'extraction preconditions failed (got, want): {wrong}')
    block = r[r.index(BLOCK_START):r.index(BLOCK_END)]
    patched_block = PATCH_DEFINES + block.replace(RESERVE_LINE, RESERVE_LINE_PATCHED) + ROOM_FN
    variants = {
        'current': (block, DRAW_CAP, None),
        'patched': (patched_block, DRAW_CAP_PATCHED, 'hd_research_draw_record_room'),
        'm2_nobytes': (PATCH_DEFINES + block + ROOM_FN, DRAW_CAP_PATCHED, 'hd_research_draw_record_room'),
    }
    for m, (old, new) in MUTANTS.items():
        assert patched_block.count(old) == 1, (m, 'mutation anchor not unique')
        variants[m] = (patched_block.replace(old, new), DRAW_CAP_PATCHED, 'hd_research_draw_record_room')
    gen = HERE / 'gen'
    out = {}
    for v, (blk, capstmt, room) in variants.items():
        d = gen / v
        d.mkdir(parents=True, exist_ok=True)
        text = (f'/* generated by build_and_run.py from hd_research_renderer.h {pins["hd_research_renderer.h"]} - variant {v} */\n'
                f'#define F3_VARIANT "{v}"\n{blk}\n'
                f'#define F3_DRAW_CAP_STMT {capstmt}\n#define F3_DRAW_BYTES_STMT {DRAW_BYTES}\n'
                f'#define F3_DRAW_COMMIT_STMT {DRAW_COMMIT}\n#define F3_MARK_ROW_STMT {MARK_ROW}\n'
                + (f'#define F3_ROOM_FN {room}\n' if room else ''))
        (d / 'variant.h').write_text(text, encoding='utf-8', newline='\n')
        out[v] = sha(d / 'variant.h')
    # reviewable patch against the canonical renderer (whole-file unified diff; canonical file untouched)
    pr = r.replace(RESERVE_LINE, RESERVE_LINE_PATCHED).replace(BLOCK_END, ROOM_FN + BLOCK_END, 1).replace(DRAW_CAP, DRAW_CAP_PATCHED)
    pr = pr.replace(BLOCK_START, PATCH_DEFINES + BLOCK_START, 1)
    diff = ''.join(difflib.unified_diff(r.splitlines(True), pr.splitlines(True), 'a/windows-x64/psxrecomp/runtime/src/hd_research_renderer.h',
                                        'b/windows-x64/psxrecomp/runtime/src/hd_research_renderer.h'))
    (HERE / 'f3-hd_research_renderer.patch').write_text(diff, encoding='utf-8', newline='\n')
    prep = dict(schema='support-f3-prepare-v1', utc=utc(), pins=pins, checks=checks, variant_headers=out,
                harness_sha256=sha(HERE / 'harness.c'), script_sha256=sha(Path(__file__)),
                patch=dict(path='f3-hd_research_renderer.patch', sha256=sha(HERE / 'f3-hd_research_renderer.patch'),
                           patched_file_sha256=hashlib.sha256(pr.encode('utf-8')).hexdigest()))
    (HERE / 'prepare.json').write_text(json.dumps(prep, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(prep, indent=1))
    return prep


EXPECT = {   # scenario -> {variant: predicate on the scenario row}
    'current': {'S1_record_pressure': lambda r: r['mark_rows_dropped'] > 0,           # the reproduction (preserved failure)
                'S2_defaults': lambda r: r['mark_rows_dropped'] > 0,
                'S3_interleaved': lambda r: r['mark_rows_dropped'] > 0,
                'S7_byte_pressure': lambda r: r['mark_rows_dropped'] > 0,
                'S4_events_exhausted': lambda r: r['mark_rows_dropped'] == 0 and r['draw_rows'] == 61,
                'S5_quota_zero': lambda r: r['mark_rows_dropped'] == 0 and r['draw_rows'] == 0},
    'patched': {'S1_record_pressure': lambda r: r['mark_rows_dropped'] == 0 and r['mark_rows'] == 8 and r['draw_rows'] == 55,
                'S2_defaults': lambda r: r['mark_rows_dropped'] == 0 and r['mark_rows'] == 8 and r['draw_rows'] == 4991,
                'S3_interleaved': lambda r: r['mark_rows_dropped'] == 0 and r['mark_rows'] == 8,
                'S4_events_exhausted': lambda r: r['mark_rows_dropped'] == 0 and r['draw_rows'] == 61,
                'S5_quota_zero': lambda r: r['mark_rows_dropped'] == 0 and r['draw_rows'] == 0 and r['mark_rows'] == 8,
                'S6_quota_one': lambda r: r['mark_rows_dropped'] == 0 and r['mark_rows'] == 8 and r['draw_rows'] <= 1,
                'S7_byte_pressure': lambda r: r['mark_rows_dropped'] == 0 and r['mark_rows'] == 2},
    'm1_offbyone': {'S1_record_pressure': lambda r: r['mark_rows_dropped'] > 0},
    'm2_nobytes': {'S7_byte_pressure': lambda r: r['mark_rows_dropped'] > 0, 'S1_record_pressure': lambda r: r['mark_rows_dropped'] == 0},
    'm4_staticreserve': {'S4_events_exhausted': lambda r: r['draw_rows'] < 61},
}
# synthetic draw-record gate states: (max_records, max_events, records, events) -> expected room for patched / m3
SYN_PATCHED = {(64, 8, 65, 0): 0, (64, 8, 64, 8): 0, (64, 8, 63, 8): 1, (64, 8, 55, 0): 1, (64, 8, 56, 0): 0, (9, 8, 1, 0): 0, (10, 8, 1, 0): 1}
SYN_M3_CAUGHT = (64, 8, 65, 0)   # records beyond max wraps without the guard -> room 1


def gate():
    k = ctypes.WinDLL('kernel32', use_last_error=True)

    class FT(ctypes.Structure):
        _fields_ = [('l', ctypes.c_uint32), ('h', ctypes.c_uint32)]

    def snap():
        i, kk, u = FT(), FT(), FT()
        k.GetSystemTimes(ctypes.byref(i), ctypes.byref(kk), ctypes.byref(u))
        f = lambda x: (x.h << 32) | x.l
        return f(i), f(kk), f(u)
    i0, k0, u0 = snap(); time.sleep(1.0); i1, k1, u1 = snap()
    cpu = 100.0 * (1 - (i1 - i0) / max(1, (k1 - k0) + (u1 - u0)))

    class MS(ctypes.Structure):
        _fields_ = [('len', ctypes.c_uint32), ('load', ctypes.c_uint32)] + [(n, ctypes.c_uint64) for n in
                                                                            ('tp', 'ap', 'tpf', 'apf', 'tv', 'av', 'aev')]
    m = MS(); m.len = ctypes.sizeof(m); k.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(cpu, 2), m.ap


def run(out, cap_s, affinity):
    prep = prepare()
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('refusing: --out exists and is not empty')
    out.mkdir(parents=True, exist_ok=True)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    me = k.GetCurrentProcess()
    k.SetPriorityClass(me, 0x4000)                      # BELOW_NORMAL; children inherit
    if affinity:
        k.SetProcessAffinityMask(me, ctypes.c_size_t(affinity))
    cpu, free = gate()
    res = dict(schema='support-f3-run-v1', task='EIN-SUPPORT-F3-REPRO-20261114', started_utc=utc(), pid=os.getpid(),
               gate=dict(cpu_percent=cpu, free_phys_bytes=free, passed=cpu < 60 and free > (16 << 30)),
               cap_s=cap_s, affinity_hex=f'{affinity:x}' if affinity else None, prepare=prep, clang=CLANG, clang_sha256=sha(CLANG),
               variants={})
    if not res['gate']['passed']:
        (out / 'result.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
        print('gate refused', res['gate']); return 3
    t0 = time.time(); ok_all = True
    for v in prep['variant_headers']:
        left = cap_s - (time.time() - t0)
        if left <= 2:
            res['variants'][v] = dict(error='total cap reached before this variant'); ok_all = False; break
        exe = out / f'harness_{v}.exe'
        cc = [CLANG, '-std=c11', '-O1', '-Wall', '-Wextra', '-Wno-unused-function', '-Wno-unused-parameter',
              f'-I{HERE / "gen" / v}', f'-I{SRC}', str(HERE / 'harness.c'), '-o', str(exe)]
        c = subprocess.run(cc, capture_output=True, text=True, timeout=max(5, min(60, left)))
        row = dict(compile_rc=c.returncode, compile_stderr=c.stderr[-4000:], variant_header_sha256=prep['variant_headers'][v])
        if c.returncode != 0:
            res['variants'][v] = row; ok_all = False; continue
        row['exe_sha256'] = sha(exe)
        work = out / f'work_{v}'; work.mkdir()
        p = subprocess.Popen([str(exe), str(work).replace('\\', '/')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        row['pid'] = p.pid; row['start_utc'] = utc()
        try:
            so, se = p.communicate(timeout=max(2, cap_s - (time.time() - t0)))
        except subprocess.TimeoutExpired:
            p.kill(); so, se = p.communicate(); row['timed_out'] = True
        row.update(rc=p.returncode, end_utc=utc(), stderr=se[-2000:])
        lines = [json.loads(x) for x in so.splitlines() if x.strip().startswith('{')]
        (out / f'stdout_{v}.jsonl').write_text(so, encoding='utf-8')
        rows = {x['scenario']: x for x in lines if 'scenario' in x}
        syn = next((x['synthetic_room'] for x in lines if 'synthetic_room' in x), None)
        row['scenarios'] = rows; row['synthetic_room'] = syn
        checks = {}
        for sc, pred in EXPECT.get(v, {}).items():
            checks[sc] = bool(sc in rows and 'start_error' not in rows[sc] and pred(rows[sc]))
        if v == 'patched' and syn is not None:
            got = {(s['max_records'], s['max_events'], s['records'], s['events']): s['room'] for s in syn}
            checks['synthetic_boundaries'] = got == SYN_PATCHED
        if v == 'm3_nowrapguard' and syn is not None:
            got = {(s['max_records'], s['max_events'], s['records'], s['events']): s['room'] for s in syn}
            checks['synthetic_wrap_caught'] = got.get(SYN_M3_CAUGHT) == 1
        row['checks'] = checks
        row['ok'] = p.returncode == 0 and not row.get('timed_out') and all(checks.values()) and bool(checks)
        ok_all &= row['ok']
        res['variants'][v] = row
    res['elapsed_s'] = round(time.time() - t0, 3)
    res['all_ok'] = ok_all
    res['finished_utc'] = utc()
    res['pins_after'] = {n: sha(SRC / n) for n in PINS}
    res['sources_unchanged'] = res['pins_after'] == prep['pins']
    (out / 'result.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({v: dict(ok=r.get('ok'), checks=r.get('checks'), compile_rc=r.get('compile_rc')) for v, r in res['variants'].items()},
                     indent=1))
    print('all_ok', ok_all, 'elapsed', res['elapsed_s'])
    return 0 if ok_all and res['sources_unchanged'] else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--cap-s', type=int)
    ap.add_argument('--affinity-hex', default='')
    a = ap.parse_args()
    if a.run:
        if not a.out or not a.cap_s:
            raise SystemExit('--run needs --out and --cap-s from the grant')
        sys.exit(run(a.out, a.cap_s, int(a.affinity_hex, 16) if a.affinity_hex else 0))
    prepare()
