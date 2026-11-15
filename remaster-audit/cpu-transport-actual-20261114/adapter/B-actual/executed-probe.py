#!/usr/bin/env python3
"""Real-OS peer-visibility probe r2 for collector c457b58e (claude-einhander-support, EIN-SUPPORT-OWNEDSTUB-R2-20261114).

r2 follows root's review msg_2335c8e6 of r1 (probe_peer_visibility_r1.py 9c090363, preserved unchanged):
  A. Negative qualification needs at least ONE 'foreign_verified_stub2_rejected_no_send' from the REAL collector
     (F-real-peer). A measure-only foreign owner is not a collector negative. Without one, including when the
     SO_REUSEADDR rebind is refused, the result is INCONCLUSIVE (exit 5), never PASS.
  B. Refusals are classified only with evidence. A scoped RecordingSocket on the collector module records the real
     client tuple of every create_connection, and TimedPsutil records every net_connections call. The peer-lookup
     call is the first table call that starts after that connect returned, and it is ordered against the stub's
     accept_call for that exact client. A refusal or pass whose order is not proven is 'order_unproven', which makes
     the result INCONCLUSIVE. It is never counted as pre-accept.
  C. Deadlines: remaining > 0 is checked before every connect, send and recv, and timeouts are capped to exactly the
     time left (no floor). This is a userland bound; kernel metadata calls are not interruptible, and the outer fa5
     envelope timeout and Job are the hard bound.
  The stub is now owned_debug_stub_r2.py, which also has no floors.

Unchanged from r1, which followed root's review msg_37383185 of r0 (probe_peer_visibility.py 11769513, preserved):
  1. One global userland deadline (GLOBAL_S) is checked before every connect, send, recv, wait and phase (see C).
     It does not interrupt a call that is already blocked in the kernel. Before each real collector call, at least
     REAL_CALL_MIN_S must remain, because the collector's own 2 s RPC and 1 s listener bounds are separate from this
     deadline.
  2. Popen objects live ONLY in procs[name]['proc'], and observations ONLY in `observers`. Cleanup:
     - records retained, signaled and exit facts;
     - drops every alias and runs gc BEFORE the bounded absence poll;
     - treats only NoSuchProcess, PID absence or a different creation time as proof of absence. AccessDenied and
       any other error fail closed.
  3. Nothing is sent in a measure round unless the post-accept server-row owner is exactly one LIVE KNOWN stub (by
     verified PID, with its retained handle still running). An unknown, None or third PID makes the round invalid,
     with no send. 'foreign' in the distribution means verified stub2.
  4. F-measure enforces the same ordering and reply checks as V-measure. V-real is instrumented: the collector's
     psutil.net_connections calls are timed, so the peer-lookup call can be ordered against the stub's
     'accept_call'. Pre-accept is never inferred from a sleep.
  5. QPC is consistent across processes on one host (Microsoft, "Acquiring high-resolution time stamps"), with up
     to ±1 tick ambiguity across threads. Ordering therefore requires a strict gap greater than
     margin = 2 x perf_counter resolution. Both stubs must report the same clock implementation and resolution.
     Wall time is recorded only, never used as an ordering basis.
  6. Loopback TCP only (127.0.0.1); no external network. The probe's own bytes are archived exclusively ('xb') and
     hash-verified.

AUTHORED, NOT EXECUTED. Run ONLY inside envelope r1 under a fresh grant naming one CPU:
  python -B -I run_rc2_envelope_r1.py --out <dir>/envelope.json --cpu <c> --timeout 60 --max-job-mib 256 --no-window
      -- python -B -I probe_peer_visibility_r2.py --out <dir>/probe --cpu <c>

Phases are as in r0: V-measure x3, V-real x2, F-rebind, F-listener, F-measure x4, F-real-peer x6. It changes no
gate; the canonical c457b58e peer check stays fail-closed.

Exit codes (r2):
  0 = all valid, every order proven, and at least one real foreign-peer rejection with no send;
  4 = valid, and the server row was PROVEN invisible before accept at least once (fail-closed observed; gate NOT
      relaxed);
  5 = INCONCLUSIVE: valid, but the foreign negative was not exercised (or not reachable), or some order is unproven;
  1 = any error, invalid round, unknown owner, inconsistent verdict or unproven cleanup;
  2 = pins, usage, flags or affinity."""
import argparse
import gc
import hashlib
import ipaddress
import json
import math
import os
import socket
import subprocess
import sys
import time
import types
from pathlib import Path

import psutil

OWN_BYTES = Path(__file__).read_bytes()
ROOT = Path('C:/github/Einhander/remaster-audit')
SUPPORT = Path('C:/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support')
COLLECTOR = ROOT / 'owned_gl_adapter_observation.py'
GUARD = ROOT / 'gl_adapter_identity_guard.py'
STUB = SUPPORT / 'owned-stub' / 'owned_debug_stub_r2.py'
PINS = {COLLECTOR: 'c457b58ed670f878dd30fb4962639dbfc18f407e4223685710f498d29a0ded34',
        GUARD: 'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08',
        STUB: 'ed43bda03d4843e74e6342f17a025bc1b97b54b10d503656cfc39cf5eefcf881'}
HIDDEN_BELOW_NORMAL = 0x08004000
REQUEST = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'
ACCEPT_DELAY_MS, POST_ACCEPT_DELAY_MS, STUB_LIFETIME_S = 500, 300, 30
V_MEASURE, V_REAL, F_MEASURE, F_REAL = 3, 2, 4, 6
GLOBAL_S, CLEANUP_S, ROUND_MIN_S, REAL_CALL_MIN_S = 45.0, 3.0, 4.0, 4.0
PEER_MISSING = 'connected debug TCP peer missing or ambiguous'
LISTENER_AMBIGUOUS = 'private debug listener missing or ambiguous'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(text):
    def constant(value):
        raise ValueError('non-finite constant ' + value)

    def finite(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('non-finite float')
        return parsed

    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate key ' + key)
            out[key] = value
        return out
    return json.loads(text, parse_constant=constant, parse_float=finite, object_pairs_hook=unique)


def read_events(path):
    """Complete lines only; a trailing partial line is ignored until finished."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding='utf-8').split('\n')[:-1]:
        if line.strip():
            try:
                events.append(strict_json(line))
            except ValueError as exc:
                events.append(dict(kind='unparsed', error=str(exc), raw=line[:200]))
    return events


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


class TimedPsutil:
    """Delegates to real psutil; records the QPC bracket of every net_connections call (V-real instrumentation)."""

    def __init__(self, real, calls):
        self._real, self._calls = real, calls

    def __getattr__(self, name):
        return getattr(self._real, name)

    def net_connections(self, kind='inet'):
        q0 = time.perf_counter_ns()
        table = self._real.net_connections(kind=kind)
        q1 = time.perf_counter_ns()
        self._calls.append(dict(qpc0=q0, qpc1=q1, kind=kind, rows=len(table)))
        return table


class RecordingSocket:
    """Delegates to the real socket module, and records the QPC bracket and the REAL client tuple of every
    create_connection made by the collector. It is installed only around real collector calls and always restored."""

    def __init__(self, real, connects):
        self._real, self._connects = real, connects

    def __getattr__(self, name):
        return getattr(self._real, name)

    def create_connection(self, address, timeout=None, *args, **kwargs):
        q0 = time.perf_counter_ns()
        conn = self._real.create_connection(address, timeout, *args, **kwargs)
        q1 = time.perf_counter_ns()
        try:
            client = list(conn.getsockname())
        except OSError:
            client = None
        self._connects.append(dict(qpc0=q0, qpc1=q1, address=list(address), client=client))
        return conn


def addr(value):
    return list(tuple(value)) if value else []


def rows_for(table, ports):
    rows = []
    for c in table:
        laddr, raddr = addr(c.laddr), addr(c.raddr)
        if (laddr and laddr[1] in ports) or (raddr and raddr[1] in ports):
            rows.append(dict(family=int(c.family), status=c.status, laddr=laddr, raddr=raddr, pid=c.pid))
    return rows


def snapshot(ports):
    q0, w0 = time.perf_counter_ns(), time.time_ns()
    table = psutil.net_connections(kind='tcp')
    q1, w1 = time.perf_counter_ns(), time.time_ns()
    return table, dict(qpc0=q0, qpc1=q1, wall0=w0, wall1=w1, lookup_ms=(q1 - q0) / 1e6, rows=rows_for(table, ports))


def server_row_owners(rows, server, client):
    return [r['pid'] for r in rows if r['status'] == psutil.CONN_ESTABLISHED and r['family'] == int(socket.AF_INET)
            and tuple(r['laddr']) == server and tuple(r['raddr']) == client]


def listen_candidates(rows, port):
    out = []
    for r in rows:
        if r['status'] == psutil.CONN_LISTEN and r['laddr'] and r['laddr'][1] == port:
            ip = ipaddress.ip_address(r['laddr'][0])
            if ip.is_loopback or ip.is_unspecified:
                out.append(dict(address=r['laddr'][0], pid=r['pid'], family=r['family']))
    return out


def absent_once(pid, ctime):
    """Absence is proven ONLY by NoSuchProcess / PID absence, or by a different creation time."""
    try:
        if not psutil.pid_exists(pid):
            return True
        if ctime is None:
            return False                     # without a creation time a reused PID cannot be told apart
        return psutil.Process(pid).create_time() != ctime
    except psutil.NoSuchProcess:
        return True
    except psutil.Error:
        return False                         # AccessDenied etc. is NOT proof of absence: fail closed


def stop_one(entry, deadline):
    """Record retained-handle facts and kill if still running. The local 'proc' is released when this returns."""
    proc = entry['proc']
    facts = dict(pid=entry['pid'], ctime=entry['ctime'], retained=proc is not None)
    if proc is None:
        return facts
    facts['exited_before_cleanup'] = proc.poll() is not None
    if not facts['exited_before_cleanup']:
        proc.kill()
        facts['signaled'] = True
        left = deadline - time.monotonic()
        if left > 0:
            try:
                proc.wait(timeout=left)
            except subprocess.TimeoutExpired:
                pass
    facts['retained_handle_exited'] = proc.poll() is not None
    facts['returncode'] = proc.returncode
    return facts


def cleanup_owned(procs, observers, handles):
    deadline = time.monotonic() + CLEANUP_S                   # ONE shared cleanup deadline
    observers.clear()                                         # observations retain .process: drop them first
    report = {name: stop_one(procs[name], deadline) for name in list(procs)}
    for entry in procs.values():
        entry['proc'] = None                                  # drop the last Popen references
    gc.collect()
    for name, entry in procs.items():
        verdict = absent_once(entry['pid'], entry['ctime'])
        while not verdict and time.monotonic() < deadline:
            time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
            verdict = absent_once(entry['pid'], entry['ctime'])
        report[name]['absent'] = verdict
        report[name]['cleanup_proven'] = verdict and report[name].get('retained_handle_exited') is True
    for handle in handles:
        try:
            handle.close()
        except OSError:
            pass
    return report


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
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    hard_end = started + GLOBAL_S

    def remaining():
        return hard_end - time.monotonic()

    clock = time.get_clock_info('perf_counter')
    margin_ns = max(1, math.ceil(2 * clock.resolution * 1e9))
    res = dict(schema='support-owned-stub-peer-probe-r2', pins=got, probe_sha256=sha(OWN_BYTES), cpu=a.cpu,
               allowed_affinity=allowed, python=sys.version, psutil=psutil.__version__,
               sys_executable=sys.executable, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               clock=dict(implementation=clock.implementation, resolution=clock.resolution,
                          monotonic=clock.monotonic), ordering_margin_ns=margin_ns,
               note='FIXTURE loopback-TCP stubs only (127.0.0.1, no external network); not a game run; changes no gate',
               V={}, F={}, errors=[])
    procs, observers, handles = {}, {}, []
    try:
        archive = out / 'executed-probe.py'
        with archive.open('xb') as stream:
            stream.write(OWN_BYTES)
            stream.flush()
            os.fsync(stream.fileno())
        if sha(archive.read_bytes()) != res['probe_sha256']:
            raise RuntimeError('archived probe copy changed')
        stub_copy = out / 'executed-stub.py'
        with stub_copy.open('xb') as stream:
            stream.write(blobs[STUB])
            stream.flush()
            os.fsync(stream.fileno())
        if sha(stub_copy.read_bytes()) != PINS[STUB]:
            raise RuntimeError('executed stub copy changed')
        base_py = Path(getattr(sys, '_base_executable', None) or sys.executable).resolve(strict=True)
        res['stub_interpreter'] = str(base_py)
        mod = load_pinned(blobs)
        run_phases(mod, out, stub_copy, base_py, procs, observers, handles, res, remaining, margin_ns)
    except Exception as exc:  # noqa: BLE001 - recorded, never a pass
        res['errors'].append(f'{type(exc).__name__}: {exc}')
    finally:
        try:
            res['cleanup'] = cleanup_owned(procs, observers, handles)
        except Exception as exc:  # noqa: BLE001
            res['errors'].append(f'cleanup {type(exc).__name__}: {exc}')
        res['stub_logs'] = {name: read_events(entry['log']) for name, entry in procs.items()}
        res['elapsed_s'] = round(time.monotonic() - started, 3)
        summarize(res, clock)
        try:
            payload = json.dumps(res, indent=1, allow_nan=False, ensure_ascii=True, default=str) + '\n'
        except (ValueError, TypeError) as exc:
            res['exit'] = 1
            payload = json.dumps(dict(serialization_failed=True, error=str(exc), exit=1)) + '\n'
        with (out / 'result.json').open('x', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(dict(exit=res.get('exit'), summary=res.get('summary'), errors=res['errors'])))
    return res.get('exit', 1)


def run_phases(mod, out, stub_copy, base_py, procs, observers, handles, res, remaining, margin_ns):
    AE, OCE, OGAO = mod.AdapterEvidenceError, mod.ObservationCaptureError, mod.OwnedGlAdapterObservation

    def need(seconds, what):
        if remaining() < seconds:
            raise RuntimeError(f'global deadline: {what} not started ({remaining():.2f} s left)')

    def budget(cap, what):
        """remaining > 0 is checked BEFORE a blocking call; the timeout is capped to exactly the time left."""
        rem = remaining()
        if rem <= 0:
            raise RuntimeError(f'global deadline expired before {what}')
        return min(cap, rem)

    def launch(name, port, max_conns):
        need(6.0, 'launch ' + name)
        err = (out / f'{name}.stderr').open('xb')
        handles.append(err)
        log = out / f'{name}.jsonl'
        cmd = [str(base_py), '-I', '-B', str(stub_copy), '--port', str(port), '--port-file', str(out / f'{name}.port'),
               '--log', str(log), '--accept-delay-ms', str(ACCEPT_DELAY_MS),
               '--post-accept-delay-ms', str(POST_ACCEPT_DELAY_MS), '--max-conns', str(max_conns),
               '--lifetime-s', str(STUB_LIFETIME_S), '--total-base', '41']
        procs[name] = dict(proc=subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                 stderr=err, creationflags=HIDDEN_BELOW_NORMAL),
                           pid=None, ctime=None, log=log)
        entry = procs[name]
        entry['pid'] = entry['proc'].pid
        try:
            entry['ctime'] = psutil.Process(entry['pid']).create_time()
        except psutil.NoSuchProcess:
            entry['ctime_note'] = 'exited before creation lookup'
        end = time.monotonic() + min(5.0, max(0.0, remaining()))
        while time.monotonic() < end:
            for e in read_events(log):
                if e.get('kind') in ('listening', 'bind_failed'):
                    return e
            if entry['proc'].poll() is not None:
                for e in read_events(log):
                    if e.get('kind') in ('listening', 'bind_failed'):
                        return e
                return dict(kind='exited_early', rc=entry['proc'].returncode)
            time.sleep(0.02)
        return dict(kind='listen_timeout')

    def live(name):
        entry = procs.get(name)
        return bool(entry) and entry['proc'] is not None and entry['proc'].poll() is None

    def find(log, kind, **match):
        for e in read_events(log):
            if e.get('kind') == kind and all(e.get(k) == v for k, v in match.items()):
                return e
        return None

    def wait_event(logs, kind, client, limit):
        end = time.monotonic() + min(limit, max(0.0, remaining()))
        while True:
            for log in logs:
                e = find(log, kind, client=list(client))
                if e is not None:
                    return dict(e, log=log.name)
            if time.monotonic() >= end:
                return None
            time.sleep(0.02)

    def count(logs, kind):
        return {log.name: sum(1 for e in read_events(log) if e.get('kind') == kind) for log in logs}

    def verdict(table, server, client, owned_pid):
        try:
            return dict(result='owned', peer=mod.select_owned_tcp_peer(table, server=server, client=client,
                                                                      owned_pid=owned_pid))
        except AE as exc:
            return dict(result='rejected', why=str(exc))

    def ordering(pre, post, accept_call, accepted, served):
        """Strict QPC ordering beyond the tick margin; wall clock is information only."""
        return dict(pre_before_accept=accept_call is not None and pre['qpc1'] + margin_ns < accept_call['qpc_ns'],
                    post_after_accept=accepted is not None and post['qpc0'] > accepted['qpc_ns'] + margin_ns,
                    post_before_served=served is not None and post['qpc1'] + margin_ns < served['qpc_ns'])

    def classify_real(passed, error, connects, calls, logs):
        """Order a REAL collector call's peer lookup against the stub's accept_call for its exact client. A missing
        peer counts as pre-accept ONLY when that order is proven; otherwise it is order_unproven (inconclusive)."""
        info = dict(connects=connects, table_calls=calls)
        client = connects[0]['client'] if len(connects) == 1 else None
        info['client'] = client
        peer_call = None
        if client is not None:
            after = [c for c in calls if c['qpc0'] > connects[0]['qpc1']]       # first table call after connect
            peer_call = after[0] if after else None
        info['peer_call'] = peer_call
        accepted = wait_event(logs, 'accepted', client, 3.0) if client else None
        accept_call = None
        if accepted is not None:
            accept_call = find(out / accepted['log'], 'accept_call', conn_index=accepted.get('conn_index'))
        info.update(accepted_event=accepted, accept_call_event=accept_call)
        proven = bool(peer_call and accept_call and peer_call['qpc1'] + margin_ns < accept_call['qpc_ns'])
        info['pre_accept_proven'] = proven
        if passed:
            info['kind'] = 'passed_pre_accept_proven' if proven else 'passed_order_unproven'
        elif PEER_MISSING in (error or ''):
            info['kind'] = 'missing_pre_accept_proven' if proven else 'missing_order_unproven'
        else:
            info['kind'] = 'other'
        return info

    def measure_round(label, port, owned_pid, known, logs):
        """known: {pid: stub name}. Nothing is sent unless the post-accept owner is ONE live known stub."""
        rec = dict(label=label)
        need(ROUND_MIN_S, 'round ' + label)
        server = ('127.0.0.1', port)
        with socket.create_connection(server, timeout=budget(2.0, 'connect ' + label)) as conn:
            client = tuple(conn.getsockname())
            rec.update(client=list(client), peername_ok=tuple(conn.getpeername()) == server)
            table, rec['pre'] = snapshot({port, client[1]})
            rec['pre'].update(verdict=verdict(table, server, client, owned_pid),
                              owners=server_row_owners(rec['pre']['rows'], server, client))
            accepted = wait_event(logs, 'accepted', client, 3.0)
            rec['accepted_event'] = accepted
            if accepted is None:
                rec['error'] = 'no accepted event before the deadline; nothing sent'
                return rec
            accept_log = out / accepted['log']
            accept_call = find(accept_log, 'accept_call', conn_index=accepted.get('conn_index'))
            rec['accept_call_event'] = accept_call
            table, rec['post'] = snapshot({port, client[1]})
            rec['post'].update(verdict=verdict(table, server, client, owned_pid),
                               owners=server_row_owners(rec['post']['rows'], server, client))
            owners = rec['post']['owners']
            owner_name = known.get(owners[0]) if len(owners) == 1 else None
            rec['owner_name'] = owner_name
            if owner_name is None or not live(owner_name) or accepted['log'] != f'{owner_name}.jsonl':
                rec['error'] = f'post-accept owner {owners} is not one live known stub; nothing sent'
                return rec
            conn.settimeout(budget(3.0, 'send ' + label))
            conn.sendall(REQUEST)
            data = bytearray()
            while b'\n' not in data and len(data) <= mod.MAX_REPLY_BYTES:
                conn.settimeout(budget(3.0, 'recv ' + label))          # checked and recomputed before EACH recv
                block = conn.recv(4096)
                if not block:
                    break
                data.extend(block)
        line, _, rest = bytes(data).partition(b'\n')
        try:
            reply = mod.decode_present_reply(line)
            rec['reply'] = dict(ok=not rest, total=reply.get('total'), fixture=reply.get('fixture'), trailing=len(rest))
        except Exception as exc:  # noqa: BLE001 - recorded
            rec['reply'] = dict(ok=False, error=f'{type(exc).__name__}: {exc}')
        served = wait_event(logs, 'served', client, 3.0)
        rec['served_event'] = served
        rec['ordering'] = ordering(rec['pre'], rec['post'], accept_call, accepted, served)
        return rec

    # ---- V: owned stub alone ---------------------------------------------------------------------------------
    ev1 = launch('stub1', 0, V_MEASURE + V_REAL + F_MEASURE + F_REAL)
    res['V']['listening'] = ev1
    if ev1.get('kind') != 'listening':
        raise RuntimeError(f'stub1 did not listen: {ev1}')
    port, pid1 = ev1['port'], procs['stub1']['pid']
    res['V']['serving_pid_matches_owned_handle'] = ev1.get('pid') == pid1
    if ev1.get('pid') != pid1:
        raise RuntimeError('interpreter redirector: serving pid differs from owned Popen pid')
    log1 = procs['stub1']['log']
    _, snap = snapshot({port})
    res['V']['listen_candidates'] = listen_candidates(snap['rows'], port)
    res['V']['measure'] = [measure_round(f'V{i + 1}', port, pid1, {pid1: 'stub1'}, [log1]) for i in range(V_MEASURE)]

    observers['v'] = OGAO(process=procs['stub1']['proc'], executable=base_py, debug_port=port, stdout_path=log1,
                          expected_model='FIXTURE not-a-game')
    calls, connects = [], []
    saved_psutil, saved_socket = mod.psutil, mod.socket
    mod.psutil = TimedPsutil(saved_psutil, calls)
    mod.socket = RecordingSocket(saved_socket, connects)
    res['V']['real'] = []
    try:
        for _ in range(V_REAL):
            need(REAL_CALL_MIN_S, 'V-real sample')
            c0, k0 = len(calls), len(connects)
            try:
                observers['v'].sample()
            except OCE:
                pass
            row = observers['v'].samples[-1]
            info = classify_real(row.get('passed') is True, row.get('error'), connects[k0:], calls[c0:], [log1])
            info['row'] = row
            res['V']['real'].append(info)
    finally:
        mod.psutil, mod.socket = saved_psutil, saved_socket

    # ---- F: foreign SO_REUSEADDR rebind ------------------------------------------------------------------------
    ev2 = launch('stub2', port, F_MEASURE + F_REAL + 2)
    res['F']['rebind'] = ev2
    if ev2.get('kind') == 'bind_failed':
        res['F']['rebind_refused'] = True
        return
    pid2 = procs['stub2']['pid']
    if ev2.get('kind') != 'listening' or ev2.get('port') != port or ev2.get('pid') != pid2:
        raise RuntimeError(f'stub2 state unexpected: {ev2}')
    res['F']['rebind_refused'] = False
    log2 = procs['stub2']['log']
    logs, known = [log1, log2], {pid1: 'stub1', pid2: 'stub2'}
    _, snap = snapshot({port})
    res['F']['listen_candidates'] = listen_candidates(snap['rows'], port)

    need(REAL_CALL_MIN_S + 1.0, 'F-listener sample')
    before = count(logs, 'pending')
    observers['f_listener'] = OGAO(process=procs['stub1']['proc'], executable=base_py, debug_port=port,
                                   stdout_path=log1, expected_model='FIXTURE not-a-game')
    try:
        observers['f_listener'].sample()
    except OCE:
        pass
    time.sleep(min(1.0, max(0.0, remaining())))
    res['F']['listener_sample'] = observers['f_listener'].samples[-1]
    res['F']['listener_pending_delta'] = {k: count(logs, 'pending')[k] - before[k] for k in before}

    res['F']['measure'] = [measure_round(f'F{i + 1}', port, pid1, known, logs) for i in range(F_MEASURE)]

    observers['f_peer'] = OGAO(process=procs['stub1']['proc'], executable=base_py, debug_port=port,
                               stdout_path=log1, expected_model='FIXTURE not-a-game')
    res['F']['real_peer'] = []
    calls, connects = [], []
    saved_psutil, saved_socket = mod.psutil, mod.socket
    mod.psutil = TimedPsutil(saved_psutil, calls)
    mod.socket = RecordingSocket(saved_socket, connects)
    try:
        for i in range(F_REAL):
            need(REAL_CALL_MIN_S, f'F-real-peer round {i + 1}')
            c0, k0 = len(calls), len(connects)
            row = {}
            try:
                response = observers['f_peer']._request_latest_present(row)
                result = dict(status='pass', total=response.get('total'))
            except Exception as exc:  # noqa: BLE001 - classified in summarize
                result = dict(status='raise', type=type(exc).__name__, error=str(exc),
                              foreign=isinstance(exc, AE) and 'belongs to another process' in str(exc))
            info = classify_real(result['status'] == 'pass', result.get('error'), connects[k0:], calls[c0:], logs)
            # The served event is matched by the EXACT recorded client tuple, not by counting log growth.
            info['served_event'] = wait_event(logs, 'served', info['client'], 3.0) if info['client'] else None
            res['F']['real_peer'].append(dict(round=i + 1, outcome=result, peer=row.get('peer'), order=info,
                                              known_pids=dict(stub1=pid1, stub2=pid2)))
    finally:
        mod.psutil, mod.socket = saved_psutil, saved_socket


def summarize(res, clock):
    """Strict classification. An invisible pre-accept row is counted, never excused."""
    V, F = res.get('V', {}), res.get('F', {})
    s = dict(pre_invisible_events=0)
    owned_pid = (V.get('listening') or {}).get('pid')
    probe_clock = dict(implementation=clock.implementation, resolution=clock.resolution)
    stub_clocks = [(ev or {}).get('clock') or {} for ev in (V.get('listening'), F.get('rebind'))
                   if ev and ev.get('kind') == 'listening']
    s['clock_consistent'] = bool(stub_clocks) and all(
        c.get('implementation') == probe_clock['implementation'] and c.get('resolution') == probe_clock['resolution']
        for c in stub_clocks)

    def owner_verdict_consistent(snap, owned):
        owners = snap['owners']
        if owners == []:
            return snap['verdict']['result'] == 'rejected' and PEER_MISSING in snap['verdict'].get('why', '')
        return len(owners) == 1 and (snap['verdict']['result'] == 'owned') == (owners == [owned])

    def round_ok(r):
        o = r.get('ordering') or {}
        return ('error' not in r and o.get('pre_before_accept') is True and o.get('post_after_accept') is True
                and o.get('post_before_served') is True and (r.get('reply') or {}).get('ok') is True
                and owner_verdict_consistent(r['pre'], owned_pid) and owner_verdict_consistent(r['post'], owned_pid))

    measure = V.get('measure') or []
    s['v_measure_valid'] = len(measure) == V_MEASURE and all(round_ok(r) and r.get('owner_name') == 'stub1'
                                                              for r in measure)
    s['v_pre_visible'] = s['v_measure_valid'] and all(r['pre']['owners'] == [owned_pid] for r in measure)
    s['v_post_visible'] = s['v_measure_valid'] and all(r['post']['owners'] == [owned_pid] for r in measure)
    s['pre_invisible_events'] += sum(1 for r in measure if 'pre' in r and r['pre']['owners'] == [])
    real = V.get('real') or []
    real_kinds = [item.get('kind') for item in real]

    def real_peer_pid(item):
        return ((item.get('row') or {}).get('peer') or {}).get('pid')
    s['v_real_kinds'] = real_kinds
    s['v_real_passed'] = len(real) == V_REAL and all(
        item.get('kind') == 'passed_pre_accept_proven' and real_peer_pid(item) == owned_pid for item in real)
    s['v_real_valid'] = len(real) == V_REAL and 'other' not in real_kinds and None not in real_kinds and all(
        real_peer_pid(item) == owned_pid for item in real if str(item.get('kind')).startswith('passed'))
    s['pre_invisible_events'] += real_kinds.count('missing_pre_accept_proven')      # PROVEN order only
    s['order_unproven_events'] = real_kinds.count('passed_order_unproven') + real_kinds.count('missing_order_unproven')
    s['v_single_listener'] = [c.get('pid') for c in V.get('listen_candidates') or []] == [owned_pid]

    s['f_negative_exercised'] = False
    if F.get('rebind_refused') is True:
        s['f_ok'] = True
        s['f_note'] = ('SO_REUSEADDR rebind refused; the foreign-listener case is not reachable in this configuration, '
                       'so the collector negative is NOT exercised (inconclusive)')
    elif F.get('rebind_refused') is False:
        stub2_pid = (F.get('rebind') or {}).get('pid')
        lsample = F.get('listener_sample') or {}
        delta = F.get('listener_pending_delta')
        s['f_listener_ambiguous_seen'] = sorted(c.get('pid') for c in F.get('listen_candidates') or []) == \
            sorted([owned_pid, stub2_pid])
        s['f_listener_rejected_without_connect'] = (lsample.get('passed') is False
                                                    and LISTENER_AMBIGUOUS in lsample.get('error', '')
                                                    and bool(delta) and all(v == 0 for v in delta.values()))
        fm = F.get('measure') or []
        s['f_measure_valid'] = len(fm) == F_MEASURE and all(
            round_ok(r) and r.get('owner_name') in ('stub1', 'stub2') for r in fm)
        s['pre_invisible_events'] += sum(1 for r in fm if 'pre' in r and r['pre']['owners'] == [])
        dist = {}
        for r in fm:
            name = r.get('owner_name')
            if name in ('stub1', 'stub2') and 'error' not in r:
                key = 'owned' if name == 'stub1' else 'foreign_verified_stub2'
                dist[key] = dist.get(key, 0) + 1
        s['f_owner_distribution'] = dist
        rp = F.get('real_peer') or []

        def classify(r):
            o, order = r['outcome'], r.get('order') or {}
            served = order.get('served_event') or {}
            client = order.get('client')
            if served.get('kind') != 'served' or client is None or served.get('client') != client:
                return 'inconsistent'
            if o['status'] == 'pass':
                ok = ((r.get('peer') or {}).get('pid') == owned_pid and served.get('log') == 'stub1.jsonl'
                      and served.get('pid') == owned_pid and served.get('request_ok') is True)
                if not ok:
                    return 'inconsistent'
                return 'owned_pass' if order.get('kind') == 'passed_pre_accept_proven' else 'owned_pass_order_unproven'
            no_send = r.get('peer') is None and served.get('request_bytes') == 0
            if (o.get('foreign') is True and no_send and served.get('log') == 'stub2.jsonl'
                    and served.get('pid') == stub2_pid):
                return 'foreign_verified_stub2_rejected_no_send'
            if PEER_MISSING in o.get('error', '') and no_send and served.get('pid') in (owned_pid, stub2_pid):
                return ('missing_pre_accept_proven_no_send' if order.get('kind') == 'missing_pre_accept_proven'
                        else 'missing_order_unproven_no_send')
            return 'inconsistent'
        kinds = [classify(r) for r in rp]
        s['f_real_peer_kinds'] = kinds
        s['f_measure_foreign_seen'] = dist.get('foreign_verified_stub2', 0) > 0     # information only, not a negative
        s['f_negative_exercised'] = 'foreign_verified_stub2_rejected_no_send' in kinds
        s['pre_invisible_events'] += kinds.count('missing_pre_accept_proven_no_send')
        s['order_unproven_events'] += (kinds.count('owned_pass_order_unproven')
                                       + kinds.count('missing_order_unproven_no_send'))
        s['f_real_peer_consistent'] = len(rp) == F_REAL and 'inconsistent' not in kinds
        s['f_ok'] = (s['f_listener_ambiguous_seen'] and s['f_listener_rejected_without_connect']
                     and s['f_measure_valid'] and s['f_real_peer_consistent'])
    else:
        s['f_ok'] = False
    cleanup = res.get('cleanup') or {}
    s['cleanup_proven'] = bool(cleanup) and all(c.get('cleanup_proven') is True for c in cleanup.values())
    valid = (not res.get('errors') and s['clock_consistent'] and s['v_measure_valid'] and s['v_single_listener']
             and s['v_real_valid'] and s['cleanup_proven'] and s['f_ok'])
    inconclusive = []
    if not s['f_negative_exercised']:
        inconclusive.append('foreign_negative_not_exercised' if F.get('rebind_refused') is False
                            else 'foreign_negative_unreachable_or_not_run')
    if s['order_unproven_events'] > 0:
        inconclusive.append('order_unproven')
    s['inconclusive_reasons'] = inconclusive
    if not valid:
        res['exit'] = 1
    elif s['pre_invisible_events'] > 0 and s['v_post_visible']:
        res['exit'] = 4                                   # gate stays fail-closed; never relaxed by this probe
    elif inconclusive:
        res['exit'] = 5                                   # INCONCLUSIVE: never reported as PASS
    elif s['v_pre_visible'] and s['v_post_visible'] and s['v_real_passed']:
        res['exit'] = 0
    else:
        res['exit'] = 1
    res['summary'] = s


if __name__ == '__main__':
    sys.exit(main())
