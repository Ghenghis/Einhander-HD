#!/usr/bin/env python3
"""Owned loopback debug-server stand-in, r2 (claude-einhander-support, EIN-SUPPORT-OWNEDSTUB-R2-20261114).

r2 follows root's review msg_2335c8e6 of r1 (owned_debug_stub_r1.py d81947cd, preserved unchanged):
  - No timeout floors. Before accept, each recv and sendall, remaining > 0 is checked and the timeout is capped to
    exactly the time left. This is a userland bound: the outer fa5 envelope timeout and Job are the hard bound, and
    kernel calls are not interruptible by it.
  - The probe reference is now probe_peer_visibility_r2.py.

Unchanged from r1, which followed root's review msg_37383185 of r0 (owned_debug_stub.py 56ccd298, preserved unchanged):
  - Every blocking call is bounded by the REMAINING lifetime: select, both sleeps, accept, EACH recv and sendall.
  - --lifetime-s is a stub-side bound re-checked before each blocking call. It is NOT a kernel guarantee; the outer
    envelope Job and its timeout are authoritative.
  - 'accept_call' is logged immediately BEFORE accept() and 'accepted' immediately after it returns, so the probe can
    bracket the real accept instant.
  - The perf_counter clock info (implementation, resolution) is logged so the probe can apply a tick margin.

AUTHORED, NOT EXECUTED. Started only by probe_peer_visibility_r2.py, from a hash-verified copy, inside a granted
envelope run. Loopback TCP only (127.0.0.1); no external network; never connects anywhere.

What it models: the v67 debug server's socket setup as root described it (AF_INET bound to 127.0.0.1, SO_REUSEADDR,
listen). Kernel TCP-table visibility is a Winsock/TCPIP property, so the same calls model it faithfully. It does NOT
model the game's accept-loop timing.

Per connection (conn_index 0, 1, ...):
  1. select() until a connection is pending; log 'pending';
  2. sleep --accept-delay-ms (pre-accept window);
  3. log 'accept_call', accept(), log 'accepted';
  4. sleep --post-accept-delay-ms (post-accept window);
  5. read one line (<= 16 KiB), with each recv bounded by the remaining lifetime. If it is exactly the n=1 request and
     lifetime remains, reply with one FIXTURE ring;
  6. log 'served'.
Each event carries qpc_ns (QueryPerformanceCounter via perf_counter_ns) and wall_ns (information only; not an
ordering basis)."""
import argparse
import json
import os
import select
import socket
import sys
import time

REQUEST = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'
MAX_LINE = 16 * 1024


def ring(total):
    # FIXTURE reply in the private-v67 n=1 schema; never evidence that a game presented anything.
    event = [total - 1, 900000 + total, 'vram', 0, [0, 0, 320, 240], [0, 0, 1280, 960], 0, 0, 1]
    reply = dict(id=1, ok=True, total=total, requested=1, returned=1, missing=0, truncated=0, capacity=64,
                 events=[event], fixture='owned-debug-stub-r2')
    return json.dumps(reply, separators=(',', ':'), allow_nan=False).encode('ascii') + b'\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=0, help='0 = ephemeral (owned stub); >0 = SO_REUSEADDR rebind')
    ap.add_argument('--port-file', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--accept-delay-ms', type=int, required=True)
    ap.add_argument('--post-accept-delay-ms', type=int, required=True)
    ap.add_argument('--max-conns', type=int, required=True)
    ap.add_argument('--lifetime-s', type=float, required=True)
    ap.add_argument('--total-base', type=int, required=True)
    a = ap.parse_args()
    if not (0 <= a.port <= 65535 and 0 <= a.accept_delay_ms <= 5000 and 0 <= a.post_accept_delay_ms <= 5000
            and 1 <= a.max_conns <= 16 and 0 < a.lifetime_s <= 30 and 1 <= a.total_base < 2 ** 40):
        print('usage bounds violated', file=sys.stderr)
        return 2
    end = time.monotonic() + a.lifetime_s

    def left():
        return end - time.monotonic()

    def bounded(seconds):
        return max(0.0, min(seconds, left()))

    log = open(a.log, 'x', encoding='utf-8')

    def event(kind, **kw):
        log.write(json.dumps(dict(kind=kind, qpc_ns=time.perf_counter_ns(), wall_ns=time.time_ns(),
                                  pid=os.getpid(), **kw), allow_nan=False) + '\n')
        log.flush()

    clock = time.get_clock_info('perf_counter')
    served, rc = 0, 0
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(('127.0.0.1', a.port))
        except OSError as exc:
            event('bind_failed', port=a.port, error=f'{type(exc).__name__}: {exc}',
                  winerror=getattr(exc, 'winerror', None))
            return 3
        srv.listen(4)
        port = srv.getsockname()[1]
        with open(a.port_file, 'x', encoding='ascii') as stream:
            stream.write(str(port))
            stream.flush()
            os.fsync(stream.fileno())
        event('listening', port=port, reuseaddr=True, requested_port=a.port,
              clock=dict(implementation=clock.implementation, resolution=clock.resolution,
                         monotonic=clock.monotonic))
        while served < a.max_conns and left() > 0.05:
            readable, _, _ = select.select([srv], [], [], bounded(30.0))
            if not readable:
                break
            event('pending', conn_index=served)
            time.sleep(bounded(a.accept_delay_ms / 1000))
            rem = left()
            if rem <= 0:
                break
            srv.settimeout(rem)                                  # capped to exactly the time left
            event('accept_call', conn_index=served)
            try:
                conn, peer = srv.accept()
            except (socket.timeout, OSError) as exc:
                event('accept_failed', conn_index=served, error=f'{type(exc).__name__}: {exc}')
                break
            with conn:
                event('accepted', conn_index=served, client=list(peer), server=list(conn.getsockname()))
                time.sleep(bounded(a.post_accept_delay_ms / 1000))
                data = bytearray()
                try:
                    while b'\n' not in data and len(data) <= MAX_LINE:
                        remaining = left()
                        if remaining <= 0:
                            break
                        conn.settimeout(min(3.0, remaining))      # remaining > 0 here; recomputed before EACH recv
                        block = conn.recv(min(4096, MAX_LINE + 1 - len(data)))
                        if not block:
                            break
                        data.extend(block)
                except (socket.timeout, OSError):
                    pass
                ok = bytes(data) == REQUEST
                total = a.total_base + served * 6
                replied = False
                rem = left()
                if ok and rem > 0:
                    try:
                        conn.settimeout(rem)
                        conn.sendall(ring(total))
                        replied = True
                    except OSError:
                        replied = False
                event('served', conn_index=served, client=list(peer), request_ok=ok, replied=replied,
                      total=total if replied else None, request_bytes=len(data))
            served += 1
    except Exception as exc:  # noqa: BLE001 - recorded; the probe treats a nonzero rc as a failed measurement
        rc = 1
        try:
            event('error', error=f'{type(exc).__name__}: {exc}')
        except Exception:  # noqa: BLE001
            pass
    finally:
        srv.close()
        try:
            event('closed', served=served)
        finally:
            log.close()
    return rc


if __name__ == '__main__':
    sys.exit(main())
