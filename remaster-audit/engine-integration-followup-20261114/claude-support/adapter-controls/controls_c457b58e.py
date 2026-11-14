#!/usr/bin/env python3
"""Source-only controls for owned_gl_adapter_observation.py c457b58e (claude-einhander-support,
EIN-SUPPORT-ADAPTER-CONTROLS-20261114).

AUTHORED, NOT EXECUTED. Run only after the hold is cleared and an explicit grant names a CPU:
  python -B -I controls_c457b58e.py --out <new dir> --cpu <granted cpu>

What it does when run:
  - pure controls only: synthetic psutil-style connection tables, synthetic reply bytes, small files in the
    exclusive --out dir, and fake socket/psutil shims bound only to the loaded collector module object;
  - opens no socket, starts no process, uses no network and touches nothing on D;
  - the collector and guard are executed from the exact bytes it hashed (no path import, no TOCTOU).

Exit codes:
  0 = every case met its oracle and exactly EXPECTED_CASES were recorded;
  1 = any failure (each one is recorded);
  2 = pins, usage, flags or affinity."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import types
from collections import namedtuple
from pathlib import Path

import psutil

ROOT = Path('C:/github/Einhander/remaster-audit')
COLLECTOR = ROOT / 'owned_gl_adapter_observation.py'
GUARD = ROOT / 'gl_adapter_identity_guard.py'
PINS = {COLLECTOR: 'c457b58ed670f878dd30fb4962639dbfc18f407e4223685710f498d29a0ded34',
        GUARD: 'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08'}
EXPECTED_CASES = 70
PORT = 47001
SERVER = ('127.0.0.1', PORT)
CLIENT = ('127.0.0.1', 50001)
OWNED, FOREIGN, SELF = 4242, 777, 1111
ID = (OWNED, 1731600000.5)
ID2 = (OWNED, 1731600001.5)
REQUEST = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'

Addr = namedtuple('addr', 'ip port')
Conn = namedtuple('sconn', 'fd family type laddr raddr status pid')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def outcome(fn):
    try:
        return 'pass', fn()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:  # noqa: BLE001 - every raise is classified by the case oracle
        return 'raise', exc


def describe(status, value):
    if status == 'raise':
        return f'{type(value).__name__}: {str(value)[:240]}'
    return 'returned'


def load_pinned(blobs):
    guard = types.ModuleType('gl_adapter_identity_guard')
    guard.__file__ = str(GUARD)
    sys.modules['gl_adapter_identity_guard'] = guard
    exec(compile(blobs[GUARD], str(GUARD), 'exec'), guard.__dict__)
    mod = types.ModuleType('owned_gl_adapter_observation')
    mod.__file__ = str(COLLECTOR)
    sys.modules['owned_gl_adapter_observation'] = mod
    exec(compile(blobs[COLLECTOR], str(COLLECTOR), 'exec'), mod.__dict__)
    return mod


class FakeConn:
    """Socket double: records every call; recv honours the requested size."""
    def __init__(self, blocks, peer=SERVER, client=CLIENT):
        self.blocks, self.peer, self.client = list(blocks), peer, client
        self.sent, self.timeouts, self.recv_sizes = [], [], []
        self.bytes_returned, self.closed = 0, False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def getsockname(self):
        return self.client

    def getpeername(self):
        return self.peer

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, data):
        self.sent.append(bytes(data))

    def recv(self, size):
        self.recv_sizes.append(size)
        if not self.blocks:
            return b''
        block = self.blocks.pop(0)
        if len(block) > size:
            self.blocks.insert(0, block[size:])
            block = block[:size]
        self.bytes_returned += len(block)
        return block


class Shim:
    """Binds fake create_connection/net_connections to the loaded module object only; always restored."""
    def __init__(self, mod, factory, table):
        self.mod, self.factory, self.table = mod, factory, list(table)
        self.calls = dict(create=0, tables=0, addr=None, timeout=None, kind=None)
        self.conns = []

    def __enter__(self):
        self.saved = (self.mod.socket, self.mod.psutil)
        real_socket, real_psutil = self.saved

        def create_connection(address, timeout=None, *args, **kwargs):
            self.calls['create'] += 1
            self.calls['addr'], self.calls['timeout'] = list(address), timeout
            conn = self.factory()
            self.conns.append(conn)
            return conn

        def net_connections(kind='inet'):
            self.calls['tables'] += 1
            self.calls['kind'] = kind
            return list(self.table)

        self.mod.socket = types.SimpleNamespace(create_connection=create_connection, AF_INET=real_socket.AF_INET)
        self.mod.psutil = types.SimpleNamespace(net_connections=net_connections,
                                                CONN_ESTABLISHED=real_psutil.CONN_ESTABLISHED,
                                                CONN_LISTEN=real_psutil.CONN_LISTEN)
        return self

    def __exit__(self, *exc):
        self.mod.socket, self.mod.psutil = self.saved
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--cpu', type=int, required=True)
    a = ap.parse_args()
    if not sys.flags.isolated or sys.flags.optimize:
        print('refusing: run with python -B -I and without -O', file=sys.stderr)
        return 2
    blobs = {p: p.read_bytes() for p in PINS}
    got = {str(p): sha(b) for p, b in blobs.items()}
    bad = [str(p) for p in PINS if got[str(p)] != PINS[p]]
    if bad:
        print(json.dumps(dict(pin_mismatch=bad, got=got)), file=sys.stderr)
        return 2
    me = psutil.Process()
    allowed = sorted(me.cpu_affinity())
    if a.cpu not in allowed:
        print(f'refusing: --cpu {a.cpu} not in allowed affinity {allowed}', file=sys.stderr)
        return 2
    me.cpu_affinity([a.cpu])
    if hasattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS'):
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)                   # exclusive output dir
    started = time.monotonic()
    res = dict(schema='support-adapter-controls-c457b58e-r0', pins=got,
               controls_sha256=sha(Path(__file__).read_bytes()), cpu=a.cpu, allowed_affinity=allowed,
               python=sys.version, psutil=psutil.__version__, int_max_str_digits=sys.get_int_max_str_digits(),
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), cases=[],
               executed_note='controls exercise pure functions and doubles only; this is NOT collector qualification')
    try:
        mod = load_pinned(blobs)
        run_all(mod, out, res)
    except Exception as exc:  # noqa: BLE001 - recorded, never a pass
        res['fatal'] = f'{type(exc).__name__}: {exc}'
    res['elapsed_s'] = round(time.monotonic() - started, 3)
    res['case_count'] = len(res['cases'])
    res['expected_cases'] = EXPECTED_CASES
    res['all_ok'] = ('fatal' not in res and res['case_count'] == EXPECTED_CASES
                     and all(c.get('ok') is True for c in res['cases']))
    (out / 'result.json').write_text(json.dumps(res, indent=1, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(all_ok=res['all_ok'], case_count=res['case_count'],
                          failed=[c['case'] for c in res['cases'] if c.get('ok') is not True],
                          fatal=res.get('fatal'), elapsed_s=res['elapsed_s'])))
    return 0 if res['all_ok'] else 1


def run_all(mod, out, res):
    AE, OCE = mod.AdapterEvidenceError, mod.ObservationCaptureError
    EST, LISTEN = psutil.CONN_ESTABLISHED, psutil.CONN_LISTEN

    def case(name, fn):
        row = dict(case=name, ok=False)
        res['cases'].append(row)
        try:
            ok, detail = fn()
            row.update(ok=bool(ok), detail=detail)
        except Exception as exc:  # noqa: BLE001 - a broken oracle is a failure, never a pass
            row['why'] = f'{type(exc).__name__}: {exc}'

    def ae(status, value, text):
        return status == 'raise' and type(value) is AE and text in str(value)

    def row_(laddr, raddr, status, pid, family=socket.AF_INET):
        return Conn(-1, family, socket.SOCK_STREAM, Addr(*laddr) if laddr else (),
                    Addr(*raddr) if raddr else (), status, pid)

    LST = row_(SERVER, None, LISTEN, OWNED)
    CLI = row_(CLIENT, SERVER, EST, SELF)
    SRV = row_(SERVER, CLIENT, EST, OWNED)
    BASE = [LST, CLI]
    WANT_PEER = dict(server=list(SERVER), client=list(CLIENT), pid=OWNED, family=int(socket.AF_INET), status=EST)
    MISSING, FOREIGN_TXT = 'missing or ambiguous', 'belongs to another process'

    # ---- P: select_owned_tcp_peer (pure) -------------------------------------------------------------
    peer_cases = [
        ('P1_owned_server_row_pass', BASE + [SRV], None),
        ('P2_foreign_pid_reject', BASE + [SRV._replace(pid=FOREIGN)], FOREIGN_TXT),
        ('P3a_missing_reject', BASE, MISSING),
        ('P3b_owned_plus_foreign_ambiguous_reject', BASE + [SRV, SRV._replace(pid=FOREIGN)], MISSING),
        ('P3c_duplicate_owned_rows_ambiguous_reject', BASE + [SRV, SRV], MISSING),
        ('P4a_syn_recv_reject', BASE + [SRV._replace(status=psutil.CONN_SYN_RECV)], MISSING),
        ('P4b_close_wait_reject', BASE + [SRV._replace(status=psutil.CONN_CLOSE_WAIT)], MISSING),
        ('P4c_time_wait_reject', BASE + [SRV._replace(status=psutil.CONN_TIME_WAIT)], MISSING),
        ('P5_inet6_family_reject', BASE + [SRV._replace(family=socket.AF_INET6)], MISSING),
        ('P6_pid_none_reject', BASE + [SRV._replace(pid=None)], FOREIGN_TXT),
        ('P7_client_orientation_only_reject', [LST, row_(CLIENT, SERVER, EST, OWNED)], MISSING),
        ('P8_owned_other_client_plus_foreign_ours_reject',
         BASE + [row_(SERVER, ('127.0.0.1', 50999), EST, OWNED), SRV._replace(pid=FOREIGN)], FOREIGN_TXT),
        ('P9_wildcard_laddr_reject', BASE + [row_(('0.0.0.0', PORT), CLIENT, EST, OWNED)], MISSING),
        ('P10_listen_only_reject', [LST], MISSING),
    ]
    for name, table, expect in peer_cases:
        def check(table=table, expect=expect):
            st, val = outcome(lambda: mod.select_owned_tcp_peer(table, server=SERVER, client=CLIENT,
                                                                owned_pid=OWNED))
            if expect is None:
                ok = st == 'pass' and val == WANT_PEER and json.dumps(val, allow_nan=False) is not None
            else:
                ok = ae(st, val, expect)
            return ok, describe(st, val)
        case(name, check)

    # ---- D: decode_present_reply (pure) --------------------------------------------------------------
    VE = 'value-error'          # UnicodeDecodeError / JSONDecodeError / int-digit ValueError (all ValueError)
    ANY = 'any-exception'
    minimal = b'{"id":1}'
    decoder_cases = [
        ('D1a_minimal_pass', minimal, 'pass'),
        ('D1b_nested_finite_pass',
         b'{"id":1,"r":{"a":[1,2.5,-0.0,1e308,1.7976931348623157e308,4.9e-324,1e-400]}}', 'pass'),
        ('D2a_bytearray_reject', bytearray(minimal), ('AE', 'bounded original reply bytes required')),
        ('D2b_str_reject', minimal.decode(), ('AE', 'bounded original reply bytes required')),
        ('D2c_memoryview_reject', memoryview(minimal), ('AE', 'bounded original reply bytes required')),
        ('D3a_exactly_16384_pass', minimal + b' ' * (16384 - len(minimal)), 'pass'),
        ('D3b_16385_reject', minimal + b' ' * (16385 - len(minimal)), ('AE', 'bounded original reply bytes required')),
        ('D4a_invalid_utf8_ff_reject', b'{"id":1,"s":"\xff"}', VE),
        ('D4b_overlong_utf8_reject', b'{"id":1,"s":"\xc0\xaf"}', VE),
        ('D4c_encoded_surrogate_reject', b'{"id":1,"s":"\xed\xa0\x80"}', VE),
        ('D5a_nan_reject', b'{"id":1,"x":NaN}', ('AE', 'non-finite JSON constant')),
        ('D5b_infinity_reject', b'{"id":1,"x":Infinity}', ('AE', 'non-finite JSON constant')),
        ('D5c_minus_infinity_reject', b'{"id":1,"x":-Infinity}', ('AE', 'non-finite JSON constant')),
        ('D6a_1e999_reject', b'{"id":1,"x":1e999}', ('AE', 'overflowing float')),
        ('D6b_minus_1e999_reject', b'{"id":1,"x":-1e999}', ('AE', 'overflowing float')),
        ('D6c_2e308_reject', b'{"id":1,"x":2e308}', ('AE', 'overflowing float')),
        ('D7a_duplicate_top_key_reject', b'{"id":1,"id":1}', ('AE', 'duplicate JSON key')),
        ('D7b_duplicate_nested_key_reject', b'{"id":1,"e":{"a":1,"a":2}}', ('AE', 'duplicate JSON key')),
        ('D7c_duplicate_escaped_key_reject', b'{"id":1,"ok":1,"\\u006fk":2}', ('AE', 'duplicate JSON key')),
        ('D7d_duplicate_in_array_object_reject', b'{"id":1,"rows":[{"k":1,"k":1}]}', ('AE', 'duplicate JSON key')),
        ('D8a_empty_object_reject', b'{}', ('AE', 'ID does not match')),
        ('D8b_id_2_reject', b'{"id":2}', ('AE', 'ID does not match')),
        ('D8c_id_true_reject', b'{"id":true}', ('AE', 'ID does not match')),
        ('D8d_id_float_reject', b'{"id":1.0}', ('AE', 'ID does not match')),
        ('D8e_id_string_reject', b'{"id":"1"}', ('AE', 'ID does not match')),
        ('D8f_top_list_reject', b'[1]', ('AE', 'ID does not match')),
        ('D8g_top_null_reject', b'null', ('AE', 'ID does not match')),
        ('D9_utf8_bom_reject', b'\xef\xbb\xbf' + minimal, VE),
        ('D10a_extra_data_reject', minimal + b' x', VE),
        ('D10b_two_objects_reject', minimal + minimal, VE),
        ('D10c_trailing_json_whitespace_pass', minimal + b' \r\t', 'pass'),
        ('D11_lone_surrogate_escape_pass_with_caller_note', b'{"id":1,"s":"\\ud800"}', 'surrogate'),
        ('D12_5000_digit_int_reject', b'{"id":1,"n":' + b'9' * 5000 + b'}', VE),
        ('D13a_empty_reject', b'', VE),
        ('D13b_whitespace_only_reject', b'   ', VE),
        ('D14_deep_nesting_within_bound_rejected', b'[' * 8192 + b']' * 8192, ANY),
    ]
    for name, raw, expect in decoder_cases:
        def check(raw=raw, expect=expect):
            st, val = outcome(lambda: mod.decode_present_reply(raw))
            detail = describe(st, val)
            if expect == 'pass':
                ok = st == 'pass' and isinstance(val, dict) and val.get('id') == 1
            elif expect == 'surrogate':
                # Decoder accepts the escape; default json.dumps is safe, but a caller writing receipts with
                # ensure_ascii=False and UTF-8 would fail. Caller note, not a decoder failure.
                ok = st == 'pass' and val.get('s') == '\ud800' and json.dumps(val, allow_nan=False) is not None
                if ok:
                    s2, v2 = outcome(lambda: json.dumps(val, ensure_ascii=False).encode('utf-8'))
                    ok = s2 == 'raise' and isinstance(v2, UnicodeEncodeError)
                    detail += f'; ensure_ascii=False+utf8 -> {describe(s2, v2)}'
            elif expect == VE:
                ok = st == 'raise' and isinstance(val, ValueError)
            elif expect == ANY:
                ok = st == 'raise' and isinstance(val, Exception)
            else:
                ok = ae(st, val, expect[1])
            return ok, detail
        case(name, check)

    # ---- harness: identity double, no process --------------------------------------------------------
    class Harness(mod.OwnedGlAdapterObservation):
        def __init__(self, *, identities, listener=None, **kw):
            self._ids = list(identities)
            self._listener_fn = listener
            super().__init__(**kw)

        def _owned_identity(self):
            return self._ids.pop(0) if len(self._ids) > 1 else self._ids[0]

        def _listener(self):
            if self._listener_fn is None:
                raise RuntimeError('listener double not configured for this case')
            return self._listener_fn()

    def make(name, identities=(ID,), listener=None, log_bytes=b'synthetic startup\n'):
        log = out / f'{name}.log'
        log.write_bytes(log_bytes)
        return Harness(identities=identities, listener=listener,
                       process=subprocess.Popen.__new__(subprocess.Popen), executable=Path(sys.executable),
                       debug_port=PORT, stdout_path=log, expected_model='synthetic-model')

    def timeouts_ok(conn):
        return all(isinstance(t, float) and 0 < t <= mod.RPC_SECONDS for t in conn.timeouts)

    # ---- O: _request_latest_present ordering with doubles --------------------------------------------
    def request_case(name, table, blocks, identities=(ID,), peer=SERVER):
        h = make(name, identities=identities)
        row = {}
        with Shim(mod, lambda: FakeConn(blocks, peer=peer), table) as shim:
            st, val = outcome(lambda: h._request_latest_present(row))
        conn = shim.conns[0] if shim.conns else None
        return st, val, row, shim, conn

    def o1():
        st, val, row, shim, conn = request_case('O1', BASE + [SRV], [b'{"id":1}\n'])
        ok = (st == 'pass' and val == {'id': 1} and conn.sent == [REQUEST] and conn.closed
              and shim.calls['create'] == 1 and shim.calls['addr'] == list(SERVER)
              and shim.calls['timeout'] == mod.RPC_SECONDS and shim.calls['tables'] == 1
              and shim.calls['kind'] == 'tcp' and row.get('peer') == dict(WANT_PEER, identity=ID)
              and timeouts_ok(conn))
        return ok, describe(st, val)

    def no_send(name, table, text, peer=SERVER, identities=(ID,), tables=1, peer_kept=False):
        def check():
            st, val, row, shim, conn = request_case(name, table, [b'{"id":1}\n'], identities=identities, peer=peer)
            ok = (ae(st, val, text) and conn is not None and conn.sent == [] and conn.closed
                  and shim.calls['tables'] == tables and (('peer' in row) == peer_kept))
            return ok, describe(st, val) + f"; sent={len(conn.sent) if conn else None}"
        return check

    def after_send(name, blocks, text, check_recv=False):
        def check():
            st, val, row, shim, conn = request_case(name, BASE + [SRV], blocks)
            ok = (ae(st, val, text) and conn.sent == [REQUEST] and conn.closed
                  and row.get('peer', {}).get('pid') == OWNED and timeouts_ok(conn))
            if check_recv:
                ok = ok and max(conn.recv_sizes) <= 4096 and conn.bytes_returned <= mod.MAX_REPLY_BYTES + 1
            return ok, describe(st, val) + f'; recv_sizes={conn.recv_sizes[-3:]} returned={conn.bytes_returned}'
        return check

    def o6():
        st, val, row, shim, conn = request_case('O6', BASE + [SRV], [b'{"id"', b':1}\n'])
        return st == 'pass' and val == {'id': 1} and conn.sent == [REQUEST], describe(st, val)

    case('O1_owned_peer_send_once_pass', o1)
    case('O2_foreign_peer_no_send', no_send('O2', BASE + [SRV._replace(pid=FOREIGN)], FOREIGN_TXT))
    case('O3_missing_peer_no_send', no_send('O3', BASE, MISSING))
    case('O4_peername_changed_no_table_no_send',
         no_send('O4', BASE + [SRV], 'connected endpoint changed', peer=('127.0.0.1', PORT + 1), tables=0))
    case('O5_identity_changed_during_peer_lookup_no_send_peer_kept',
         no_send('O5', BASE + [SRV], 'runtime changed during connected-peer lookup',
                 identities=(ID, ID, ID2), peer_kept=True))
    case('O6_split_reply_pass', o6)
    case('O7_data_after_newline_reject', after_send('O7', [b'{"id":1}\nX'], 'unsolicited data'))
    case('O8_eof_before_newline_reject', after_send('O8', [b'{"id":1}'], 'closed before a complete reply'))
    case('O9_oversize_without_newline_reject',
         after_send('O9', [b' ' * 4096] * 5, 'reply exceeds bound', check_recv=True))
    case('O10_duplicate_key_reply_reject_after_send', after_send('O10', [b'{"id":1,"id":1}\n'], 'duplicate JSON key'))

    # ---- L: sample() lifecycle with doubles ----------------------------------------------------------
    GOOD_LISTENER = dict(identity=ID, listener=dict(address='127.0.0.1', port=PORT, pid=OWNED,
                                                   family=int(socket.AF_INET)), at_utc='synthetic', elapsed_s=0.0)

    def l1():
        seq = [AE('synthetic before failure'), GOOD_LISTENER]

        def listener():
            value = seq.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        h = make('L1', listener=listener)
        with Shim(mod, lambda: FakeConn([b'{"id":1}\n']), BASE + [SRV]) as shim:
            st, val = outcome(h.sample)
        r = h.samples[-1] if h.samples else {}
        ok = (st == 'raise' and type(val) is OCE and shim.calls['create'] == 0 and len(h.samples) == 1
              and r.get('passed') is False and 'after' in r and 'synthetic before failure' in r.get('error', '')
              and val.receipt is r)
        return ok, describe(st, val)

    def l2():
        def listener():
            raise AE('synthetic listener failure')
        h = make('L2', listener=listener)
        with Shim(mod, lambda: FakeConn([b'{"id":1}\n']), BASE + [SRV]) as shim:
            first = outcome(h.sample)
            second = outcome(h.sample)
            third = outcome(h.sample)
        ok = (type(first[1]) is OCE and type(second[1]) is OCE and ae(*third, 'only two explicit samples')
              and len(h.samples) == 2 and shim.calls['create'] == 0)
        return ok, describe(*third)

    def l3():
        h = make('L3', listener=lambda: dict(GOOD_LISTENER))
        with Shim(mod, lambda: FakeConn([b'{"id":1}\n']), BASE + [SRV]) as shim:
            rows = [outcome(h.sample), outcome(h.sample)]
        ok = (all(st == 'pass' for st, _ in rows) and len(h.samples) == 2 and shim.calls['create'] == 2
              and shim.calls['tables'] == 2
              and all(r['passed'] is True and r['peer']['pid'] == OWNED and r['response'] == {'id': 1}
                      for r in h.samples)
              and all(c.sent == [REQUEST] for c in shim.conns))
        return ok, f'attempts={h.attempts}'

    case('L1_before_listener_failure_never_connects', l1)
    case('L2_third_sample_refused', l2)
    case('L3_two_good_samples_carry_peer', l3)

    # ---- S: startup file identity (constructor vs finish) --------------------------------------------
    def samples():
        return [dict(passed=True, before=dict(identity=ID), after=dict(identity=ID), response={'id': 1})
                for _ in range(2)]

    def s1():
        h = make('S1')
        replacement = out / 'S1.replacement'
        replacement.write_bytes(b'synthetic startup\n')
        os.replace(replacement, h.stdout_path)
        h.samples = samples()
        st, val = outcome(h.finish)
        ok = (st == 'raise' and type(val) is OCE and isinstance(val.__cause__, AE)
              and 'startup log file identity changed' in str(val.__cause__)
              and 'startup_file' not in val.receipt and val.receipt.get('passed') is False)
        return ok, describe(st, val) + f'; cause={val.__cause__!r}' if st == 'raise' else 'accepted'

    def s2():
        h = make('S2')
        with open(h.stdout_path, 'ab') as stream:
            stream.write(b'appended in place\n')
        h.samples = samples()
        st, val = outcome(h.finish)
        sf = (getattr(val, 'receipt', None) or {}).get('startup_file', {}) if st == 'raise' else {}
        ok = (st == 'raise' and type(val) is OCE and 'identity changed' not in str(val.__cause__)
              and (sf.get('device'), sf.get('inode')) == h.stdout_identity and val.receipt.get('passed') is False)
        return ok, describe(st, val) + (f'; cause={val.__cause__!r}' if st == 'raise' else '')

    def s3():
        d = out / 'S3.dir'
        d.mkdir()
        st, val = outcome(lambda: Harness(identities=(ID,), process=subprocess.Popen.__new__(subprocess.Popen),
                                          executable=Path(sys.executable), debug_port=PORT, stdout_path=d,
                                          expected_model='synthetic-model'))
        return st == 'raise' and isinstance(val, (OSError, AE)), describe(st, val)

    def s4():
        st, val = outcome(lambda: Harness(identities=(ID,), process=subprocess.Popen.__new__(subprocess.Popen),
                                          executable=Path(sys.executable), debug_port=PORT,
                                          stdout_path=out / 'S4.missing.log', expected_model='synthetic-model'))
        return st == 'raise' and isinstance(val, FileNotFoundError), describe(st, val)

    def s5():
        h = make('S5')
        os.remove(h.stdout_path)
        h.samples = samples()
        st, val = outcome(h.finish)
        ok = (st == 'raise' and type(val) is OCE and isinstance(val.__cause__, FileNotFoundError)
              and 'startup_file' not in val.receipt and val.receipt.get('passed') is False)
        return ok, describe(st, val)

    def s6():
        h = make('S6')
        new = b'rewritten in place\n'
        with open(h.stdout_path, 'r+b') as stream:
            stream.seek(0)
            stream.write(new)
            stream.truncate()
        h.samples = samples()
        st, val = outcome(h.finish)
        sf = (getattr(val, 'receipt', None) or {}).get('startup_file', {}) if st == 'raise' else {}
        # Documented limitation: (dev, ino) detects replacement, not in-place rewrite of the same file.
        ok = (st == 'raise' and type(val) is OCE and (sf.get('device'), sf.get('inode')) == h.stdout_identity
              and sf.get('sha256') == sha(new) and 'identity changed' not in str(val.__cause__))
        return ok, describe(st, val)

    def s7():
        h = make('S7')
        h.samples = samples()
        first = outcome(h.finish)
        second = outcome(h.finish)
        return type(first[1]) is OCE and ae(*second, 'qualification already finalized'), describe(*second)

    case('S1_replaced_startup_file_rejected', s1)
    case('S2_appended_same_file_reaches_validation', s2)
    case('S3_directory_startup_path_constructor_raises', s3)
    case('S4_missing_startup_path_constructor_raises', s4)
    case('S5_deleted_before_finish_wrapped', s5)
    case('S6_in_place_rewrite_not_identity_detected_documented', s6)
    case('S7_second_finish_refused', s7)


if __name__ == '__main__':
    sys.exit(main())
