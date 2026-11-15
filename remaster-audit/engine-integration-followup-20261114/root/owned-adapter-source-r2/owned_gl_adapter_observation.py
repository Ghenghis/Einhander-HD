"""Read-only, bounded observations for future owned-runtime qualification.

SOURCE ONLY: not wired into the launch runner or qualified with a real game.
Call only under a separately authorized private-game run. Construction retains
the caller's Popen object; it neither starts nor terminates a process. Exactly
two explicit samples are allowed. There is no polling thread or automatic retry.
The caller remains responsible for executable/settings provenance, shared GPU
permission, startup/title/focus acceptance, normal affinity and final cleanup.
Initialization may raise filesystem or psutil errors; caller cleanup must still
run. A qualified outer Job contains blocked OS metadata calls: the one-second
listener acceptance deadline does not interrupt a Windows syscall.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import stat
import subprocess
import time

import psutil

from gl_adapter_identity_guard import (
    AdapterEvidenceError, MAX_STARTUP_BYTES, validate_active_adapter,
)

MAX_REPLY_BYTES = 16 * 1024
RPC_SECONDS = 2.0
MAX_LISTENER_SECONDS = 1.0


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise AdapterEvidenceError(reason)


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def select_owned_tcp_peer(connections, *, server: tuple, client: tuple, owned_pid: int) -> dict:
    """Pure lookup for the server side of THIS connected IPv4 socket."""
    matches = []
    for connection in connections:
        if (connection.status == psutil.CONN_ESTABLISHED and connection.family == socket.AF_INET
                and connection.laddr and connection.raddr
                and tuple(connection.laddr) == server and tuple(connection.raddr) == client):
            matches.append(connection)
    _require(len(matches) == 1, 'connected debug TCP peer missing or ambiguous')
    _require(matches[0].pid == owned_pid, 'connected debug TCP peer belongs to another process')
    return dict(server=list(server), client=list(client), pid=matches[0].pid,
                family=int(matches[0].family), status=matches[0].status)


def decode_present_reply(raw: bytes) -> dict:
    """Pure strict decoder; rejects ambiguous objects and all nonfinite numbers."""
    _require(isinstance(raw, bytes) and len(raw) <= MAX_REPLY_BYTES, 'bounded original reply bytes required')
    def invalid_constant(value):
        raise AdapterEvidenceError('non-finite JSON constant in GL-present reply: '+value)
    def finite_float(value):
        parsed = float(value)
        _require(math.isfinite(parsed), 'overflowing float in GL-present reply')
        return parsed
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON key in GL-present reply: '+key)
            result[key] = value
        return result
    response = json.loads(raw.decode('utf-8', errors='strict'), parse_constant=invalid_constant,
                          parse_float=finite_float, object_pairs_hook=unique_object)
    _require(isinstance(response, dict) and type(response.get('id')) is int and response['id'] == 1,
             'GL-present reply ID does not match request')
    return response


class ObservationCaptureError(AdapterEvidenceError):
    """Carries the partial narrow receipt when an observation fails."""
    def __init__(self, message: str, receipt: dict):
        super().__init__(message)
        self.receipt = receipt


class OwnedGlAdapterObservation:
    def __init__(self, *, process: subprocess.Popen, executable: Path,
                 debug_port: int, stdout_path: Path, expected_model: str):
        _require(isinstance(process, subprocess.Popen), 'retained owned Popen handle required')
        _require(type(debug_port) is int and 1 <= debug_port <= 65535, 'invalid private debug port')
        self.process = process
        self.executable = Path(executable).resolve(strict=True)
        self.stdout_path = Path(stdout_path).resolve(strict=True)
        self.port = debug_port
        self.expected_model = expected_model
        self.identity = None
        self.samples = []
        self.attempts = 0
        self.finished = False
        with self.stdout_path.open('rb') as stream:
            info = os.fstat(stream.fileno())
            _require(stat.S_ISREG(info.st_mode), 'startup evidence is not a regular file')
            self.stdout_identity = (info.st_dev, info.st_ino)
        # A PID lookup is bracketed by liveness checks on the retained process
        # handle: a reused PID cannot substitute for the exited owned child.
        self.identity = self._owned_identity()

    def _owned_identity(self) -> tuple[int, float]:
        _require(self.process.poll() is None, 'owned runtime exited')
        process = psutil.Process(self.process.pid)
        identity = (process.pid, process.create_time())
        executable = Path(process.exe()).resolve(strict=True)
        _require(self.process.poll() is None, 'owned runtime exited during identity lookup')
        _require(os.path.normcase(str(executable)) == os.path.normcase(str(self.executable)),
                 'owned runtime executable differs from prepared executable')
        _require(self.identity is None or identity == self.identity, 'owned runtime identity changed')
        return identity

    def _listener(self) -> dict:
        started = time.monotonic()
        identity = self._owned_identity()
        # Include wildcard/IPv6 loopback bindings when checking ambiguity. A
        # per-process connection list alone could overlook another reuseaddr
        # listener. The actual private server binds IPv4 INADDR_LOOPBACK.
        candidates = []
        for connection in psutil.net_connections(kind='tcp'):
            if connection.status != psutil.CONN_LISTEN or not connection.laddr:
                continue
            if connection.laddr.port != self.port:
                continue
            address = ipaddress.ip_address(connection.laddr.ip)
            if address.is_loopback or address.is_unspecified:
                candidates.append(dict(address=connection.laddr.ip, port=connection.laddr.port,
                                       pid=connection.pid, family=int(connection.family)))
        _require(len(candidates) == 1, 'private debug listener missing or ambiguous')
        listener = candidates[0]
        _require(listener['pid'] == identity[0] and listener['address'] == '127.0.0.1'
                 and listener['family'] == int(socket.AF_INET), 'private debug listener is foreign or unexpected')
        _require(self._owned_identity() == identity, 'owned identity changed during listener lookup')
        _require(time.monotonic()-started <= MAX_LISTENER_SECONDS,
                 'listener metadata lookup exceeded its acceptance deadline')
        return dict(identity=identity, listener=listener, at_utc=_utc(),
                    elapsed_s=time.monotonic()-started)

    def _request_latest_present(self, row: dict) -> dict:
        # This method owns the exact queried endpoint. No arbitrary callback
        # can silently send a request to a different process/port.
        deadline = time.monotonic()+RPC_SECONDS
        request = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'
        with socket.create_connection(('127.0.0.1', self.port), timeout=RPC_SECONDS) as connection:
            server = ('127.0.0.1', self.port)
            client = tuple(connection.getsockname())
            _require(tuple(connection.getpeername()) == server, 'connected endpoint changed')
            identity = self._owned_identity()
            # A short-lived SO_REUSEADDR listener can evade listener brackets.
            # Bind this accepted connection's reverse 4-tuple to the owned PID
            # before sending any command, then re-check the retained handle.
            row['peer'] = select_owned_tcp_peer(psutil.net_connections(kind='tcp'),
                server=server, client=client, owned_pid=identity[0])
            row['peer']['identity'] = identity
            _require(self._owned_identity() == identity, 'runtime changed during connected-peer lookup')
            left = deadline-time.monotonic()
            _require(left > 0, 'GL-present connection/peer lookup exceeded deadline')
            connection.settimeout(left)
            connection.sendall(request)
            received = bytearray()
            while b'\n' not in received:
                left = deadline-time.monotonic()
                _require(left > 0, 'GL-present reply exceeded deadline')
                connection.settimeout(left)
                block = connection.recv(min(4096, MAX_REPLY_BYTES+1-len(received)))
                _require(bool(block), 'GL-present connection closed before a complete reply')
                received.extend(block)
                _require(len(received) <= MAX_REPLY_BYTES, 'GL-present reply exceeds bound')
        line, remainder = bytes(received).split(b'\n', 1)
        _require(not remainder, 'unsolicited data after GL-present reply')
        return decode_present_reply(line)

    def sample(self) -> dict:
        _require(not self.finished and self.attempts < 2, 'only two explicit samples are allowed')
        self.attempts += 1
        row = dict(at_utc=_utc(), attempt=self.attempts, endpoint=['127.0.0.1', self.port],
                   command={'cmd':'gl_present_ring','n':1}, passed=False)
        started = time.monotonic()
        error = None
        try:
            row['before'] = self._listener()
            row['response'] = self._request_latest_present(row)
        except Exception as caught:
            error = caught
            row['error'] = type(caught).__name__+': '+str(caught)
        finally:
            # Retain the closing ownership observation even if the socket or
            # JSON validation failed. Never retry a failed sample silently.
            try:
                row['after'] = self._listener()
            except Exception as caught:
                row['after_error'] = type(caught).__name__+': '+str(caught)
                error = error or caught
            row['elapsed_s'] = time.monotonic()-started
            row['passed'] = error is None
            self.samples.append(row)
        if error is not None:
            raise ObservationCaptureError('owned GL-present observation failed', row) from error
        return row

    def finish(self) -> dict:
        _require(not self.finished, 'qualification already finalized')
        self.finished = True
        _require(len(self.samples) == 2 and all(row['passed'] for row in self.samples),
                 'two successful explicit GL-present observations required')
        receipt = dict(at_utc=_utc(), samples=self.samples, passed=False,
                       gameplay_accepted=False, focus_accepted=False,
                       performance_accepted=False, audio_accepted=False)
        try:
            before = self._owned_identity()
            with self.stdout_path.open('rb') as stream:
                info = os.fstat(stream.fileno())
                _require(stat.S_ISREG(info.st_mode), 'startup evidence is not a regular file')
                _require((info.st_dev, info.st_ino) == self.stdout_identity,
                         'startup log file identity changed')
                raw = stream.read(MAX_STARTUP_BYTES+1)
            receipt['startup_file'] = dict(path=str(self.stdout_path), device=info.st_dev,
                inode=info.st_ino, bytes_read=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            after = self._owned_identity()
            first, second = self.samples
            receipt['validation'] = validate_active_adapter(stdout=raw, expected_model=self.expected_model,
                expected_process=self.identity, process_before=before, process_after=after,
                present_before_owner_bracket=(first['before']['identity'], first['after']['identity']),
                present_after_owner_bracket=(second['before']['identity'], second['after']['identity']),
                present_before=first['response'], present_after=second['response'])
            receipt['passed'] = True
        except Exception as caught:
            receipt['error'] = type(caught).__name__+': '+str(caught)
            raise ObservationCaptureError('owned adapter qualification failed', receipt) from caught
        return receipt
