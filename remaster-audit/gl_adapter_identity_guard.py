"""Pure validation for a future private launch gate; performs no GL, OS, file or transport calls.

Requires the proposed one-time identity line plus the existing private-v67
gl_present_ring(n=1) response schema. The caller must independently obtain both
process identities from its retained owned process handle, and bracket EACH RPC
query with independent listener ownership checks for the exact queried port.
These caller observations must not be copied from the expected identity.
Passing synthetic data here is a unit test, never proof that a game ran.
Not wired into launch yet. The bound covers the complete startup capture through
qualification; silently truncating a long log could hide a software fallback.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping

MAX_STARTUP_BYTES = 1024 * 1024
PREFIX = 'psxrecomp: GL identity '
READY = 'psxrecomp: GL GPU pipeline ready ('
FALLBACK = 'psxrecomp: GL pipeline init failed'
LINE = re.compile(r'psxrecomp: GL identity vendor="([^"\r\n]*)" renderer="([^"\r\n]*)" '
                  r'version="([^"\r\n]*)" truncated=([01])')


class AdapterEvidenceError(ValueError):
    pass


def _need(ok: bool, why: str) -> None:
    if not ok:
        raise AdapterEvidenceError(why)


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value < 2**64


def _model(value: str) -> str:
    # Compare the COMPLETE model prefix, never a substring (3090 != 3090 Ti).
    # NVIDIA ICD suffixes such as /PCIe/SSE2 are transport/CPU capabilities.
    return ' '.join(value.split('/', 1)[0].casefold().split())


def parse_startup_identity(stdout: bytes, expected_model: str) -> dict:
    _need(isinstance(stdout, bytes) and len(stdout) <= MAX_STARTUP_BYTES,
          'complete bounded startup bytes required')
    raw = stdout
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError as error:
        raise AdapterEvidenceError('startup log is not valid UTF-8') from error
    _need('\0' not in text, 'invalid startup log')
    _need(isinstance(expected_model, str) and bool(expected_model.strip())
          and '/' not in expected_model and '?' not in expected_model, 'complete expected adapter model required')
    lines = text.splitlines()
    identity_indices = [i for i, line in enumerate(lines) if PREFIX in line]
    candidates = [lines[i] for i in identity_indices]
    _need(len(candidates) == 1, 'expected exactly one adapter identity record')
    match = LINE.fullmatch(candidates[0])
    _need(match is not None, 'malformed adapter identity record')
    vendor, renderer, version, truncated = match.groups()
    for field in (vendor, renderer, version):
        _need(0 < len(field) <= 127 and field != '?' and '\\' not in field
              and all(0x20 <= ord(ch) < 0x7f for ch in field), 'invalid adapter field')
    _need(truncated == '0', 'truncated adapter identity cannot qualify a launch')
    _need(_model(renderer) == _model(expected_model), 'driver selected a different adapter model')
    ready_indices = [i for i, line in enumerate(lines) if line.startswith(READY)]
    _need(len(ready_indices) == 1, 'GL pipeline ready marker missing or repeated')
    _need(identity_indices[0] < ready_indices[0], 'GL ready marker precedes adapter identity')
    _need(not any(FALLBACK in line for line in lines), 'GL pipeline fell back to software')
    return dict(vendor=vendor, renderer=renderer, version=version,
                identity_line=candidates[0], startup_sha256=hashlib.sha256(raw).hexdigest(),
                startup_bytes=len(raw), startup_decoding='UTF-8 strict')


def _process(value: tuple[int, float]) -> tuple[int, float]:
    _need(isinstance(value, tuple) and len(value) == 2, 'owned process identity missing')
    pid, created = value
    _need(_integer(pid, 1) and type(created) in (int, float)
          and math.isfinite(created) and created > 0, 'invalid owned process identity')
    return pid, created


def _listener_bracket(value: tuple, owner: tuple[int, float]) -> None:
    _need(isinstance(value, tuple) and len(value) == 2,
          'listener ownership checks before and after each RPC required')
    _need(_process(value[0]) == _process(value[1]) == owner,
          'RPC listener is not the unchanged owned runtime process')


def _present(response: Mapping, require_image: bool) -> tuple[int, list | None]:
    _need(isinstance(response, Mapping) and response.get('ok') is True, 'GL present query failed')
    total, events = response.get('total'), response.get('events')
    _need(_integer(total) and isinstance(events, list), 'malformed GL present response')
    for name in ('requested', 'returned', 'missing', 'truncated', 'capacity'):
        _need(_integer(response.get(name)), 'missing or invalid present metadata: ' + name)
    _need(response['requested'] == 1 and response['returned'] == len(events)
          and response['missing'] == 0 and response['truncated'] == 0
          and response['capacity'] >= 1, 'incomplete or unbounded GL present query')
    _need(len(events) == min(total, 1), 'latest GL present event absent')
    if not events:
        _need(not require_image, 'no GL presents after title')
        return total, None
    event = events[0]
    _need(isinstance(event, list) and len(event) == 9, 'unexpected private GL present schema')
    _need(_integer(event[0]) and event[0] == total - 1 and _integer(event[1]), 'stale GL present event')
    _need(isinstance(event[2], str) and event[2] in {'vram', 'wide', 'cpu', 'blank', 'interp'},
          'unknown GL present path')
    _need(_integer(event[7]) and event[7] == 0, 'GL error in latest present')
    if require_image:
        _need(event[2] in {'vram', 'wide', 'cpu'}, 'only blank/interpolated GL presents observed')
        for box in event[4:6]:
            _need(isinstance(box, list) and len(box) == 4 and all(type(v) is int for v in box)
                  and box[2] > 0 and box[3] > 0, 'invalid displayed GL image dimensions')
    return total, event


def validate_active_adapter(*, stdout: bytes, expected_model: str,
                            expected_process: tuple[int, float],
                            process_before: tuple[int, float], process_after: tuple[int, float],
                            present_before_owner_bracket: tuple, present_after_owner_bracket: tuple,
                            present_before: Mapping, present_after: Mapping) -> dict:
    identity = parse_startup_identity(stdout, expected_model)
    owner = _process(expected_process)
    _need(_process(process_before) == _process(process_after) == owner, 'owned runtime process changed')
    _listener_bracket(present_before_owner_bracket, owner)
    _listener_bracket(present_after_owner_bracket, owner)
    start, _ = _present(present_before, False)
    end, last = _present(present_after, True)
    _need(end > start, 'GL present sequence did not advance')
    return dict(**identity, pid=owner[0], creation_unix=owner[1],
                before_total=start, after_total=end, latest_event_seq=last[0],
                listener_brackets_validated=True,
                model_only=True, physical_uuid_verified=False,
                validation_scope='startup model and recent owned GL presents only')
