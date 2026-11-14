#!/usr/bin/env python3
"""Pure controls r1 for the audited adapter binding r1 (claude-einhander-support, EIN-SUPPORT-AUDIT-BINDING-R1-20261114).

r1 = the r0 cases (controls_binding_r0.py 52275a7a, preserved) re-pinned to guard r1 and collector r1, with the
cleanup fixtures updated to the exact owned-cleanup contract, plus B18-B24 for root review msg_ca94c6d0:
  - swapped complete directory;
  - slow intent past the deadline, and identity change after the intent;
  - cleanup contract failures;
  - strict transport and peer types;
  - outer audit scope;
  - unreceipted intent.

AUTHORED, NOT EXECUTED. Run only under a fresh grant naming a CPU, for example inside envelope r1:
  python -B -I controls_binding_r1.py --out <new dir> --cpu <granted cpu>

Doubles only:
  - synthetic psutil-style rows, a FakeConn and a Shim that is local to the module and always restored;
  - a Harness whose _owned_identity and _listener are deterministic;
  - Popen.__new__, so no process is created;
  - a FIXTURE startup log and rings;
  - evidence directories under --out.
No socket, process, network, GPU or game. Every module is executed from the exact bytes that were hashed.

Exit codes: 0 = exactly EXPECTED_CASES recorded and all ok; 1 = any failure; 2 = pins, usage, flags or affinity."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import types
import uuid
from collections import namedtuple
from pathlib import Path

import psutil

ROOT = Path('C:/github/Einhander/remaster-audit')
BINDING = Path('C:/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/adapter-binding')
CANON_GUARD = ROOT / 'unassisted_command_guard.py'
ID_GUARD = ROOT / 'gl_adapter_identity_guard.py'
VAR_GUARD = BINDING / 'unassisted_command_guard_adapter_r1.py'
AUD_COLLECTOR = BINDING / 'owned_gl_adapter_observation_audited_r1.py'
PINS = {CANON_GUARD: '9e6ca8159a2f471fcbbde996464a6ba2eb6a51846c44567eefdb6e5cceaa2240',
        ID_GUARD: 'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08',
        VAR_GUARD: '05f7f7d17767714734bb1510b0d0da09107389595ff116fec83230ef9bb3bcee',
        AUD_COLLECTOR: '9f4550930ee5a980b89c62b00c6dcea966ccf10ff4f93036d8c5726993723b9c'}
EXPECTED_CASES = 41
PORT = 47001
SERVER = ('127.0.0.1', PORT)
CLIENT = ('127.0.0.1', 50001)
OWNED, FOREIGN, SELF = 4242, 777, 1111
ID = (OWNED, 1731600000.5)
REQUEST = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'
FIX_MODEL = 'FIXTURE Model 9000'
FIX_IDENTITY_LINE = ('psxrecomp: GL identity vendor="FIXTURE Vendor" renderer="FIXTURE Model 9000/PCIe/SSE2" '
                     'version="4.6.0 FIXTURE" truncated=0')

Addr = namedtuple('addr', 'ip port')
Conn = namedtuple('sconn', 'fd family type laddr raddr status pid')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def outcome(fn):
    try:
        return 'pass', fn()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:  # noqa: BLE001 - classified by each oracle
        return 'raise', exc


def describe(status, value):
    return f'{type(value).__name__}: {str(value)[:240]}' if status == 'raise' else 'returned'


def exec_module(name, path, data):
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(data, str(path), 'exec'), mod.__dict__)
    return mod


class FakeConn:
    def __init__(self, blocks, on_send=None, peer=SERVER, client=CLIENT):
        self.blocks, self.on_send, self.peer, self.client = list(blocks), on_send, peer, client
        self.sent, self.at_send, self.closed = [], [], False

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
        pass

    def sendall(self, data):
        if self.on_send is not None:
            self.at_send.append(self.on_send())     # evidence state at the instant of sending
        self.sent.append(bytes(data))

    def recv(self, size):
        if not self.blocks:
            return b''
        block = self.blocks.pop(0)
        if len(block) > size:
            self.blocks.insert(0, block[size:])
            block = block[:size]
        return block


class Shim:
    def __init__(self, mod, factory, table):
        self.mod, self.factory, self.table, self.conns = mod, factory, list(table), []
        self.calls = dict(create=0, tables=0)

    def __enter__(self):
        self.saved = (self.mod.socket, self.mod.psutil)
        real_socket, real_psutil = self.saved

        def create_connection(address, timeout=None, *args, **kwargs):
            self.calls['create'] += 1
            conn = self.factory()
            self.conns.append(conn)
            return conn

        def net_connections(kind='inet'):
            self.calls['tables'] += 1
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
    own = Path(__file__).read_bytes()
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
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    res = dict(schema='support-adapter-binding-controls-r1', pins=got, controls_sha256=sha(own), cpu=a.cpu,
               allowed_affinity=allowed, python=sys.version, psutil=psutil.__version__, cases=[],
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               note='pure controls and doubles only; not a game run; not collector qualification')
    try:
        mods = dict(canon=exec_module('unassisted_command_guard', CANON_GUARD, blobs[CANON_GUARD]),
                    idg=exec_module('gl_adapter_identity_guard', ID_GUARD, blobs[ID_GUARD]),
                    var=exec_module('unassisted_command_guard_adapter_r1', VAR_GUARD, blobs[VAR_GUARD]))
        mods['col'] = exec_module('owned_gl_adapter_observation_audited_r1', AUD_COLLECTOR, blobs[AUD_COLLECTOR])
        run_all(mods, blobs, out, res)
    except Exception as exc:  # noqa: BLE001 - recorded, never a pass
        res['fatal'] = f'{type(exc).__name__}: {exc}'
    res['elapsed_s'] = round(time.monotonic() - started, 3)
    res['case_count'] = len(res['cases'])
    res['expected_cases'] = EXPECTED_CASES
    res['all_ok'] = ('fatal' not in res and res['case_count'] == EXPECTED_CASES
                     and all(c.get('ok') is True for c in res['cases']))
    payload = json.dumps(res, indent=1, allow_nan=False, ensure_ascii=True) + '\n'
    with (out / 'result.json').open('x', encoding='utf-8') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(all_ok=res['all_ok'], case_count=res['case_count'], fatal=res.get('fatal'),
                          failed=[c['case'] for c in res['cases'] if c.get('ok') is not True])))
    return 0 if res['all_ok'] else 1


def run_all(mods, blobs, out, res):
    canon, var, col = mods['canon'], mods['var'], mods['col']
    AE, OCE, ABE = col.AdapterEvidenceError, col.ObservationCaptureError, var.AdapterBindingError
    EST, LISTEN = psutil.CONN_ESTABLISHED, psutil.CONN_LISTEN

    def case(name, fn):
        row = dict(case=name, ok=False)
        res['cases'].append(row)
        try:
            ok, detail = fn()
            row.update(ok=bool(ok), detail=detail)
        except Exception as exc:  # noqa: BLE001 - a broken oracle is a failure
            row['why'] = f'{type(exc).__name__}: {exc}'

    def row_(laddr, raddr, status, pid):
        return Conn(-1, socket.AF_INET, socket.SOCK_STREAM, Addr(*laddr) if laddr else (),
                    Addr(*raddr) if raddr else (), status, pid)

    BASE = [row_(SERVER, None, LISTEN, OWNED), row_(CLIENT, SERVER, EST, SELF)]
    SRV = row_(SERVER, CLIENT, EST, OWNED)
    WANT_PEER = dict(server=list(SERVER), client=list(CLIENT), pid=OWNED, family=int(socket.AF_INET), status=EST)
    GOOD_LISTENER = dict(identity=ID, listener=dict(address='127.0.0.1', port=PORT, pid=OWNED,
                                                   family=int(socket.AF_INET)), at_utc='synthetic', elapsed_s=0.0)

    def adapter_report(evidence, **over):
        rep = dict(evidence=str(evidence), command_phase='adapter-qualification',
                   adapter_profile='adapter-qualification-v1',
                   visual_profile=dict(timer_only_assistance=False, ordinary_fire=True))
        rep.update(over)
        return rep

    def fixture_startup():
        lines = ['FIXTURE synthetic startup capture; not evidence that a game ran', FIX_IDENTITY_LINE,
                 'psxrecomp: GL GPU pipeline ready (FIXTURE)']
        return ('\n'.join(lines) + '\n').encode('ascii')

    def ring(total):
        event = [total - 1, 900000 + total, 'vram', 0, [0, 0, 320, 240], [0, 0, 1280, 960], 0, 0, 1]
        reply = dict(id=1, ok=True, total=total, requested=1, returned=1, missing=0, truncated=0, capacity=64,
                     events=[event])
        return json.dumps(reply, separators=(',', ':'), allow_nan=False).encode('ascii') + b'\n'

    class Harness(col.AuditedOwnedGlAdapterObservation):
        def _owned_identity(self):
            return ID

        def _listener(self):
            return dict(GOOD_LISTENER)

    ID2 = (OWNED, ID[1] + 1.0)

    class HarnessShift(Harness):
        """Owned identity changes on the 4th lookup: init (1), pre-peer (2), post-peer (3), post-intent (4)."""
        def _owned_identity(self):
            self.identity_calls = getattr(self, 'identity_calls', 0) + 1
            return ID if self.identity_calls <= 3 else ID2

    def fake_popen():
        process = subprocess.Popen.__new__(subprocess.Popen)     # no process is created
        process.pid = OWNED
        return process

    GOOD_CLEANUP = dict(owned_pid=OWNED, owned_identity=list(ID), identity_absent=True, tree_absent=True,
                        method='synthetic-fixture')

    def good_cleanup(calls):
        def cleanup():
            calls.append(1)
            return dict(GOOD_CLEANUP)
        return cleanup

    def workspace(name):
        base = out / name
        base.mkdir()
        evidence = base / 'evidence'
        evidence.mkdir()
        log = base / 'startup.log'
        log.write_bytes(fixture_startup())
        return base, evidence, log

    def make(name, cls=None, **over):
        base, evidence, log = workspace(name)
        rep = adapter_report(evidence, **over)
        return (lambda: (cls or Harness)(report=rep, process=fake_popen(),
                                         executable=Path(sys.executable), debug_port=PORT, stdout_path=log,
                                         expected_model=FIX_MODEL)), rep, evidence, log

    def files(directory):
        return sorted(p.name for p in directory.glob('*.json')) if directory.is_dir() else []

    def intent_count(evidence):
        return len(files(evidence / 'command-intents'))

    def two_samples(h, evidence, totals):
        replies = [ring(t) for t in totals]
        with Shim(col, lambda: FakeConn([replies.pop(0)], on_send=lambda: intent_count(evidence)),
                  BASE + [SRV]) as shim:
            sampled = [outcome(h.sample), outcome(h.sample)]
        return shim, sampled

    def peer_doc(pid=OWNED):
        return dict(WANT_PEER, pid=pid, identity=list(ID))

    def clean(audit, n=2):
        return (audit['forbidden_or_malformed'] == [] and audit['adapter_intents'] == n
                and audit['adapter_receipts'] == n and audit['adapter_completed'] == n
                and audit['adapter_unreceipted'] == [])

    def errors_text(audit):
        return ' | '.join(e['error'] for e in audit['forbidden_or_malformed'])

    # ---- B1/B2/B3: canonical policy is untouched ----------------------------------------------------------
    case('B1_variant_guard_starts_with_canonical_9e6ca815_bytes', lambda: (
        blobs[VAR_GUARD].startswith(blobs[CANON_GUARD]) and len(blobs[VAR_GUARD]) > len(blobs[CANON_GUARD]),
        f'canonical {len(blobs[CANON_GUARD])} B is a byte prefix'))

    def b2():
        reqs = [{'cmd': 'gl_present_ring', 'n': 16384}, {'cmd': 'gl_present_ring', 'n': 1},
                {'cmd': 'gl_present_ring', 'n': 1, 'id': 1}, {'cmd': 'read_ram', 'addr': '0x800813C4', 'len': 1},
                {'cmd': 'write_ram', 'addr': '0x800813C4', 'data': '00'}, {'cmd': 'get_registers'},
                {'cmd': 'set_input', 'buttons': '0xBFFF'}, {'cmd': 'turbo', 'enabled': 0}]
        mismatches, n1_admitted = [], []
        for phase in ('gameplay', 'native-menu-route', 'adapter-qualification'):
            rep = adapter_report(out, command_phase=phase)
            for req in reqs:
                c = outcome(lambda: canon.validate_command(rep, dict(req)))
                v = outcome(lambda: var.validate_command(rep, dict(req)))
                if (c[0], describe(*c)) != (v[0], describe(*v)):
                    mismatches.append([phase, req])
                if req.get('n') == 1 and (c[0] == 'pass' or v[0] == 'pass'):
                    n1_admitted.append([phase, req])
        return not mismatches and not n1_admitted, f'mismatches={mismatches} n1_admitted={n1_admitted}'
    case('B2_ordinary_validate_command_identical_and_n1_never_admitted', b2)

    def b3():
        base, evidence, log = workspace('B3')
        rep = adapter_report(evidence)
        calls = []
        st, val = outcome(lambda: var.send_guarded(lambda r, raw: calls.append(raw), rep,
                                                   '{"cmd":"gl_present_ring","n":1}'))
        return (st == 'raise' and 'refused before send' in str(val) and calls == []
                and not (evidence / 'command-intents').exists()), describe(st, val)
    case('B3_send_guarded_refuses_n1_even_in_adapter_phase', b3)

    # ---- B4/B5: audited pass path --------------------------------------------------------------------------
    def b4():
        ctor, rep, evidence, log = make('B4')
        h = ctor()
        shim, sampled = two_samples(h, evidence, (41, 47))
        st, val = outcome(h.finish)
        if st != 'pass':
            return False, describe(st, val) + f'; cause={getattr(val, "__cause__", None)!r}'
        ids = h.ledger.intents
        intents = [json.loads((evidence / 'command-intents' / (i + '.json')).read_text()) for i in ids]
        receipts = [json.loads((evidence / 'commands' / (i + '.json')).read_text()) for i in ids]
        ok = (all(s == 'pass' for s, _ in sampled) and val['passed'] is True and clean(val['command_audit'])
              and [c.at_send for c in shim.conns] == [[1], [2]]          # intent durable BEFORE each send
              and all(c.sent == [REQUEST] for c in shim.conns)
              and [r['intent_id'] for r in h.samples] == ids and len(set(ids)) == 2
              and [i['sequence'] for i in intents] == [1, 2] and all(i['peer']['pid'] == OWNED for i in intents)
              and all(r['state'] == 'transport_completed' and r['transport']['sent'] is True for r in receipts)
              and val['validation']['before_total'] == 41 and val['validation']['after_total'] == 47
              and json.dumps(val, allow_nan=False) is not None)
        return ok, f'at_send={[c.at_send for c in shim.conns]}'
    case('B4_two_audited_samples_intent_before_send_and_finish_pass', b4)

    def b5():
        base, evidence, log = workspace('B5')
        rep = adapter_report(evidence)
        calls = []
        replies = [ring(41), ring(47)]
        saved = col.AuditedOwnedGlAdapterObservation
        col.AuditedOwnedGlAdapterObservation = Harness
        try:
            with Shim(col, lambda: FakeConn([replies.pop(0)]), BASE + [SRV]):
                result = col.run_audited_qualification(
                    report=rep, process=fake_popen(), executable=Path(sys.executable),
                    debug_port=PORT, stdout_path=log, expected_model=FIX_MODEL, cleanup=good_cleanup(calls))
        finally:
            col.AuditedOwnedGlAdapterObservation = saved
        return (result['passed'] is True and (result['cleanup'] or {}).get('status') == 'proven' and calls == [1]
                and 'error' not in result), f"cleanup={result['cleanup']} error={result.get('error')}"
    case('B5_run_audited_qualification_pass_cleanup_once', b5)

    # ---- B6/B7: no intent -> no send -----------------------------------------------------------------------
    def b6():
        ctor, rep, evidence, log = make('B6')
        h = ctor()
        with Shim(col, lambda: FakeConn([ring(41)]), BASE + [SRV._replace(pid=FOREIGN)]) as shim:
            st, val = outcome(h.sample)
        return (st == 'raise' and type(val) is OCE and intent_count(evidence) == 0 and shim.conns[0].sent == []
                and h.ledger.used == 0 and 'intent_id' not in h.samples[-1]), describe(st, val)
    case('B6_foreign_peer_no_intent_no_send', b6)

    def b7():
        ctor, rep, evidence, log = make('B7')
        h = ctor()
        (evidence / 'command-intents').write_bytes(b'not a directory')
        with Shim(col, lambda: FakeConn([ring(41)]), BASE + [SRV]) as shim:
            st, val = outcome(h.sample)
        r = h.samples[-1]
        return (st == 'raise' and type(val) is OCE and shim.conns[0].sent == [] and h.ledger.used == 1
                and 'intent_id' not in r and 'transport_receipt' not in r and 'Error' in r.get('error', '')), \
            describe(st, val) + '; ' + r.get('error', '')
    case('B7_intent_logging_failure_no_send_budget_consumed', b7)

    # ---- B8..B11: ledger refusals ----------------------------------------------------------------------------
    def ledger_for(name, **over):
        base, evidence, log = workspace(name)
        rep = adapter_report(evidence, **over)
        return var.AdapterIntentLedger(rep, endpoint=SERVER, owned_identity=ID), evidence

    def b8():
        L, evidence = ledger_for('B8')
        L.before_send(REQUEST, peer=peer_doc())
        L.before_send(REQUEST, peer=peer_doc())
        st, val = outcome(lambda: L.before_send(REQUEST, peer=peer_doc()))
        return (st == 'raise' and type(val) is ABE and 'at most two' in str(val)
                and intent_count(evidence) == 2), describe(st, val)
    case('B8_third_adapter_intent_refused', b8)

    def b9():
        L, evidence = ledger_for('B9')
        st, val = outcome(lambda: L.before_send(b'{"id":1,"cmd":"gl_present_ring","n":16384}\n', peer=peer_doc()))
        return (st == 'raise' and type(val) is ABE and 'not the exact n=1' in str(val) and L.used == 1
                and intent_count(evidence) == 0), describe(st, val)
    case('B9_wrong_request_bytes_refused_budget_consumed', b9)

    def refused_ledger(over, endpoint=SERVER, text='adapter'):
        def check():
            base, evidence, log = workspace('B10-' + uuid.uuid4().hex[:8])
            rep = adapter_report(evidence, **over)
            st, val = outcome(lambda: var.AdapterIntentLedger(rep, endpoint=endpoint, owned_identity=ID))
            return st == 'raise' and type(val) is ABE and text in str(val), describe(st, val)
        return check
    case('B10a_ledger_refuses_gameplay_phase', refused_ledger(dict(command_phase='gameplay'),
                                                              text='explicit adapter-qualification profile'))
    case('B10b_ledger_refuses_missing_profile', refused_ledger(dict(adapter_profile=None),
                                                               text='explicit adapter-qualification profile'))
    case('B10c_ledger_refuses_timer_assistance', refused_ledger(
        dict(visual_profile=dict(timer_only_assistance=True)), text='unassisted gameplay only'))
    case('B10d_ledger_refuses_wildcard_endpoint', refused_ledger({}, endpoint=('0.0.0.0', PORT),
                                                                  text='exactly 127.0.0.1'))

    def b10e():
        ctor, rep, evidence, log = make('B10e', command_phase='gameplay')
        st, val = outcome(ctor)
        return st == 'raise' and type(val) is AE and 'adapter intent ledger refused' in str(val), describe(st, val)
    case('B10e_collector_construction_refuses_non_adapter_phase', b10e)

    def b11():
        L, evidence = ledger_for('B11')
        st, val = outcome(lambda: L.before_send(REQUEST, peer=peer_doc(pid=FOREIGN)))
        return (st == 'raise' and type(val) is ABE and 'not the owned endpoint' in str(val) and L.used == 1
                and intent_count(evidence) == 0), describe(st, val)
    case('B11_ledger_refuses_foreign_peer_budget_consumed', b11)

    # ---- B12/B13: failures after the intent ------------------------------------------------------------------
    def b12():
        ctor, rep, evidence, log = make('B12')
        h = ctor()
        (evidence / 'commands').write_bytes(b'not a directory')
        with Shim(col, lambda: FakeConn([ring(41)]), BASE + [SRV]) as shim:
            st, val = outcome(h.sample)
        r = h.samples[-1]
        return (st == 'raise' and type(val) is OCE and 'transport receipt was not durably written' in r.get('error', '')
                and 'transport_receipt_error' in r and shim.conns[0].sent == [REQUEST]
                and files(evidence / 'command-intents') == [r['intent_id'] + '.json']), describe(st, val)
    case('B12_receipt_write_failure_fails_sample_intent_kept', b12)

    def b13():
        ctor, rep, evidence, log = make('B13')
        h = ctor()
        with Shim(col, lambda: FakeConn([b'{"id":1']), BASE + [SRV]) as shim:
            st, val = outcome(h.sample)
        r = h.samples[-1]
        receipt = json.loads((evidence / 'commands' / (r['intent_id'] + '.json')).read_text())
        audit = var.audit_commands_adapter(rep)
        return (st == 'raise' and 'closed before a complete reply' in r.get('error', '')
                and receipt['state'] == 'transport_failed' and receipt['transport']['sent'] is True
                and 'closed before' in receipt['transport'].get('error', '')
                and audit['forbidden_or_malformed'] == [] and audit['adapter_intents'] == 1
                and audit['adapter_receipts'] == 1 and audit['adapter_completed'] == 0), describe(st, val)
    case('B13_eof_after_send_writes_failed_receipt_audit_consistent', b13)

    # ---- B14: audit refuses tampering ----------------------------------------------------------------------
    def audit_base(name):
        L, evidence = ledger_for(name)
        ids = []
        for _ in range(2):
            i = L.before_send(REQUEST, peer=peer_doc())
            L.after_transport(i, dict(sent=True, decoded=True, reply_bytes=10, reply_sha256='0' * 64))
            ids.append(i)
        rep = L.report
        return rep, evidence, ids, clean(var.audit_commands_adapter(rep))

    def rewrite(path, fn):
        row = json.loads(path.read_text())
        fn(row)
        path.write_text(json.dumps(row, sort_keys=True) + '\n')

    def tamper(name, mutate, expect):
        def check():
            rep, evidence, ids, base_clean = audit_base(name)
            mutate(evidence, ids)
            audit = var.audit_commands_adapter(rep)
            text = errors_text(audit)
            return base_clean and all(e in text for e in expect), text[:400]
        return check

    def t_request(ev, ids):
        rewrite(ev / 'command-intents' / (ids[0] + '.json'), lambda r: r['request'].__setitem__('n', 16384))

    def t_third(ev, ids):
        row = json.loads((ev / 'command-intents' / (ids[1] + '.json')).read_text())
        new = uuid.uuid4().hex
        row['intent_id'] = new
        (ev / 'command-intents' / (new + '.json')).write_text(json.dumps(row, sort_keys=True) + '\n')

    def t_delete(ev, ids):
        (ev / 'command-intents' / (ids[0] + '.json')).unlink()

    def t_peer(ev, ids):
        rewrite(ev / 'commands' / (ids[1] + '.json'), lambda r: r['peer'].__setitem__('pid', FOREIGN))

    def t_rename(ev, ids):
        (ev / 'command-intents' / (ids[0] + '.json')).rename(ev / 'command-intents' / (uuid.uuid4().hex + '.json'))

    def t_ordinary(ev, ids):
        (ev / 'command-intents' / (uuid.uuid4().hex + '.json')).write_text(json.dumps(dict(
            request={'cmd': 'gl_present_ring', 'n': 1}, command_phase='gameplay',
            state='validated_before_transport')) + '\n')

    def t_duplicate(ev, ids):
        path = ev / 'command-intents' / (ids[0] + '.json')
        text = path.read_text()
        path.write_text('{"sequence": 1, ' + text[1:])

    case('B14a_audit_refuses_adapter_intent_with_n16384', tamper('B14a', t_request, ['not the exact gl_present_ring n=1']))
    case('B14b_audit_refuses_third_adapter_intent', tamper('B14b', t_third, ['more than two adapter intents',
                                                                            'sequence is not 1..n']))
    case('B14c_audit_refuses_receipt_without_intent', tamper('B14c', t_delete, ['has no validated intent']))
    case('B14d_audit_refuses_receipt_peer_mismatch', tamper('B14d', t_peer, ['not the owned endpoint and process']))
    case('B14e_audit_refuses_intent_name_mismatch', tamper('B14e', t_rename, ['name/intent_id mismatch']))
    case('B14f_audit_refuses_ordinary_phase_n1_by_canonical_rule', tamper('B14f', t_ordinary,
                                                                          ['refused before send: gl_present_ring']))
    case('B14g_audit_refuses_duplicate_key_in_adapter_intent', tamper('B14g', t_duplicate, ['duplicate JSON key']))

    # ---- B15..B17: cleanup always runs; failures stay failures --------------------------------------------
    def run_with(name, rep_over, totals, cleanup):
        base, evidence, log = workspace(name)
        rep = adapter_report(evidence, **rep_over)
        replies = [ring(t) for t in totals]
        saved = col.AuditedOwnedGlAdapterObservation
        col.AuditedOwnedGlAdapterObservation = Harness
        try:
            with Shim(col, lambda: FakeConn([replies.pop(0)] if replies else []), BASE + [SRV]):
                return col.run_audited_qualification(
                    report=rep, process=fake_popen(), executable=Path(sys.executable),
                    debug_port=PORT, stdout_path=log, expected_model=FIX_MODEL, cleanup=cleanup), rep
        finally:
            col.AuditedOwnedGlAdapterObservation = saved

    def b15():
        calls = []
        result, rep = run_with('B15', dict(command_phase='gameplay'), (41, 47), good_cleanup(calls))
        return (result['passed'] is False and (result['cleanup'] or {}).get('status') == 'proven' and calls == [1]
                and 'adapter intent ledger refused' in result.get('error', '')), str(result.get('error'))
    case('B15_cleanup_runs_when_construction_fails', b15)

    def b16():
        def cleanup():
            raise RuntimeError('synthetic cleanup failure')
        result, rep = run_with('B16', {}, (41, 47), cleanup)
        c = result['cleanup'] or {}
        return (result['passed'] is False and c.get('status') == 'failed'
                and 'cleanup raised RuntimeError' in c.get('detail', '')
                and (result.get('receipt') or {}).get('passed') is True), str(c)
    case('B16_cleanup_raise_makes_result_fail', b16)

    def b17():
        calls = []
        result, rep = run_with('B17', {}, (41, 41), good_cleanup(calls))
        partial = result.get('partial_receipt') or {}
        audit = var.audit_commands_adapter(rep)
        return (result['passed'] is False and calls == [1] and 'did not advance' in partial.get('error', '')
                and 'command_audit' not in partial and clean(audit)), str(result.get('error'))
    case('B17_non_advance_fails_while_audit_stays_clean', b17)

    # ---- B18..B24: r1 corrections (root review msg_ca94c6d0) -----------------------------------------------
    def completed():
        return dict(sent=True, decoded=True, reply_bytes=10, reply_sha256='0' * 64)

    def b18():
        ctor, rep, evidence, log = make('B18')
        h = ctor()
        shim, sampled = two_samples(h, evidence, (41, 47))
        for sub in ('command-intents', 'commands'):
            for path in (evidence / sub).glob('*.json'):
                path.unlink()
        other = var.AdapterIntentLedger(rep, endpoint=SERVER, owned_identity=ID)    # same owner, OTHER uuids
        for _ in range(2):
            intent_id = other.before_send(REQUEST, peer=peer_doc())
            other.after_transport(intent_id, completed())
        swapped_clean = clean(var.audit_commands_adapter(rep))
        st, val = outcome(h.finish)
        return (all(s == 'pass' for s, _ in sampled) and swapped_clean and st == 'raise' and type(val) is OCE
                and 'does not bind exactly this observation' in str(val.__cause__)), describe(st, val)
    case('B18_self_consistent_swapped_directory_fails_finish', b18)

    def b19():
        ctor, rep, evidence, log = make('B19')
        h = ctor()
        original = h.ledger.before_send

        def slow(raw, *, peer):
            intent_id = original(raw, peer=peer)
            time.sleep(0.2)                                       # the intent+fsync outlives the RPC deadline
            return intent_id
        h.ledger.before_send = slow
        saved = col.RPC_SECONDS
        col.RPC_SECONDS = 0.1
        try:
            with Shim(col, lambda: FakeConn([ring(41)]), BASE + [SRV]) as shim:
                st, val = outcome(h.sample)
        finally:
            col.RPC_SECONDS = saved
        r = h.samples[-1]
        path = evidence / 'commands' / (str(r.get('intent_id')) + '.json')
        receipt = json.loads(path.read_text()) if path.exists() else {}
        return (st == 'raise' and 'deadline expired after the durable intent' in r.get('error', '')
                and shim.conns[0].sent == [] and receipt.get('state') == 'transport_failed'
                and receipt.get('transport', {}).get('sent') is False), describe(st, val)
    case('B19_slow_intent_past_deadline_no_send_failure_receipt', b19)

    def b20():
        ctor, rep, evidence, log = make('B20', cls=HarnessShift)
        h = ctor()
        with Shim(col, lambda: FakeConn([ring(41)]), BASE + [SRV]) as shim:
            st, val = outcome(h.sample)
        r = h.samples[-1]
        path = evidence / 'commands' / (str(r.get('intent_id')) + '.json')
        receipt = json.loads(path.read_text()) if path.exists() else {}
        return (st == 'raise' and 'owned runtime changed after the durable intent' in r.get('error', '')
                and shim.conns[0].sent == [] and receipt.get('state') == 'transport_failed'
                and receipt.get('transport', {}).get('sent') is False), describe(st, val)
    case('B20_identity_change_after_intent_no_send_failure_receipt', b20)

    def cleanup_case(name, fn, text):
        def check():
            result, rep = run_with(name, {}, (41, 47), fn)
            c = result.get('cleanup') or {}
            return (c.get('status') == 'failed' and text in c.get('detail', '') and result['passed'] is False
                    and (result.get('receipt') or {}).get('passed') is True), str(c)
        return check
    case('B21a_cleanup_returning_false_fails', cleanup_case('B21a', lambda: False, 'exact owned-cleanup record'))
    case('B21b_cleanup_identity_not_absent_fails', cleanup_case(
        'B21b', lambda: dict(GOOD_CLEANUP, identity_absent=False), 'absence not proven'))
    case('B21c_cleanup_missing_tree_key_fails', cleanup_case(
        'B21c', lambda: {k: v for k, v in GOOD_CLEANUP.items() if k != 'tree_absent'}, 'exact owned-cleanup record'))
    case('B21d_cleanup_wrong_pid_fails', cleanup_case(
        'B21d', lambda: dict(GOOD_CLEANUP, owned_pid=FOREIGN), 'does not name the owned process'))

    def ledger_refuses_transport(name, transport):
        def check():
            L, evidence = ledger_for(name)
            intent_id = L.before_send(REQUEST, peer=peer_doc())
            st, val = outcome(lambda: L.after_transport(intent_id, transport))
            return (st == 'raise' and type(val) is ABE and 'malformed adapter transport' in str(val)
                    and files(evidence / 'commands') == []), describe(st, val)
        return check
    case('B22a_transport_decoded_int_1_refused', ledger_refuses_transport('B22a', dict(completed(), decoded=1)))
    case('B22b_transport_non_hex_sha_refused', ledger_refuses_transport('B22b', dict(completed(), reply_sha256='z' * 64)))

    def t_decoded_int(ev, ids):
        rewrite(ev / 'commands' / (ids[0] + '.json'), lambda r: r['transport'].__setitem__('decoded', 1))

    def t_float_port(ev, ids):
        rewrite(ev / 'command-intents' / (ids[0] + '.json'), lambda r: r['peer']['server'].__setitem__(1, float(PORT)))
    case('B22c_audit_refuses_receipt_decoded_int', tamper('B22c', t_decoded_int, ['malformed adapter transport outcome']))
    case('B22e_audit_refuses_float_port_in_peer', tamper('B22e', t_float_port, ['exactly 127.0.0.1']))

    def b22d():
        base, evidence, log = workspace('B22d')
        rep = adapter_report(evidence)
        L = var.AdapterIntentLedger(rep, endpoint=SERVER, owned_identity=(1, ID[1]))
        st, val = outcome(lambda: L.before_send(REQUEST, peer=dict(WANT_PEER, pid=True, identity=[1, ID[1]])))
        return (st == 'raise' and type(val) is ABE and 'not the owned endpoint' in str(val)
                and intent_count(evidence) == 0), describe(st, val)
    case('B22d_bool_pid_not_equal_to_owned_pid_1', b22d)

    def b23():
        rep, evidence, ids, base_clean = audit_base('B23')
        audit = var.audit_commands_adapter(dict(rep, command_phase='gameplay'))
        text = errors_text(audit)
        return (base_clean and 'explicit adapter-qualification profile' in text
                and audit['adapter_intents'] == 0), text[:300]
    case('B23_audit_requires_outer_adapter_scope', b23)

    def b24():
        L, evidence = ledger_for('B24')
        intent_id = L.before_send(REQUEST, peer=peer_doc())
        audit = var.audit_commands_adapter(L.report)
        return ('unreceipted adapter intent' in errors_text(audit)
                and audit['adapter_unreceipted'] == [intent_id]), errors_text(audit)[:200]
    case('B24_unreceipted_adapter_intent_is_audit_error', b24)


if __name__ == '__main__':
    sys.exit(main())
