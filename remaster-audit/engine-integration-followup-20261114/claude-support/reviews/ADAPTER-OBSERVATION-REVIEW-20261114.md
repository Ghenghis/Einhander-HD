# owned_gl_adapter_observation.py b0c24540: read-only source review (claude-einhander-support, 2026-11-14 ~20:10Z)

- Task: EIN-SUPPORT-ADAPTER-OBS-REVIEW-20261114, requested in msg_1aeab5ae.
- Method: text reading only. The module was not imported or run, and there was no network use and no D access.
- Two stdlib behaviours were checked with a pure stdlib snippet (no project code, no sockets) on Python 3.14.5:
  `ipaddress` and `json.loads`.

## Inputs
- `C:/github/Einhander/remaster-audit/owned_gl_adapter_observation.py`:
  b0c24540ac378e9f36425ace54fac6bfebd81449a8bb885ba700fc7601983021, 188 lines.
- `C:/github/Einhander/remaster-audit/gl_adapter_identity_guard.py`:
  c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08, 137 lines. Read for `validate_active_adapter`,
  `_present`, `_integer`, `MAX_STARTUP_BYTES`.

## Sound as written
- **Owned identity** (`_owned_identity`, :68-77):
  - The retained Popen handle keeps the PID from being reused while it is open.
  - `poll()` before and after brackets the psutil lookup.
  - The executable path is compared after `resolve(strict=True)` and normcase.
  - Identity is a (pid, create_time) pair and is compared with the construction value.
- **Listener check** (`_listener`, :79-103):
  - Uses the global TCP LISTEN table and counts only loopback or unspecified addresses on the exact port.
  - Requires exactly one candidate, owned by our PID, at 127.0.0.1 over AF_INET, re-checks identity afterwards, and
    enforces the 1 s acceptance deadline after the blocking call, as stated.
  - On Python 3.14.5 `::ffff:127.0.0.1` reports `is_loopback=True` and `::ffff:0.0.0.0` reports
    `is_unspecified=True`, so an IPv4-mapped dual-stack listener is counted as ambiguous. That is not a gap.
- **RPC** (`_request_latest_present`, :105-131):
  - One fixed endpoint and command; a single 2 s deadline across connect, send and each recv.
  - The recv size is clamped so the 16 KiB bound is exact.
  - EOF before the newline fails; data after the newline in the same read fails; UTF-8 is strict; the ID must be 1.
- **Sample lifecycle** (:133-159):
  - At most two attempts, no retry.
  - If the "before" listener check fails, no request is sent.
  - The "after" check runs in `finally`; a partial row is always appended and raised as ObservationCaptureError.
- **finish** (:161-188):
  - Requires two passed samples.
  - Startup evidence is a bounded single read (MAX+1, so the guard detects overflow) from a regular file, hashed, with
    identity bracketed before and after.
  - The pure guard enforces model, process, both listener brackets, the present schema and sequence advance.
  - Acceptance flags stay false.

## Findings
### R1 (medium; recommended): the accepting socket's peer is not bound to the owned process
- Listener ownership is checked before and after each RPC, but not for the TCP connection actually used.
- Per root, the real v67 debug server binds IPv4 loopback with SO_REUSEADDR. On Windows that allows another process to
  bind the same `127.0.0.1:port` (also with SO_REUSEADDR) and possibly accept the connection.
- A foreign listener that exists only between the "before" check and connect, or between connect and the "after" check,
  is not detected.
- The ID/schema checks give only weak protection; a mimic could satisfy them.
- **Control:**
  - Right after `create_connection` and before `sendall`, take `local = connection.getsockname()`.
  - Require exactly one TCP table entry with status ESTABLISHED, `laddr == ('127.0.0.1', port)`, `raddr == local` and
    `pid == owned pid`.
  - Record it as `peer` in the row. Only then send.
  - This binds the actual server end of our connection to the owned identity and closes the window.
  - Factor the lookup as a pure function over a connection table so it can be unit-tested without sockets.

### R2 (low): `parse_constant` does not stop overflowing floats
- Verified on 3.14.5: `json.loads('{"x":1e999}')` returns `inf` even with `parse_constant` set.
- The guard's `_integer` (`type(value) is int`) still rejects inf in every field it validates.
- But fields it does not validate (for example event[3], event[6] and event[8], and any extra keys) can carry inf into
  `row['response']`. A later `json.dump` of the receipt would then write non-standard `Infinity`.
- **Control:** `parse_float=lambda s: _finite(float(s))`, rejecting non-finite values. Optionally dump receipts with
  `allow_nan=False`.

### R3 (low): duplicate JSON keys are accepted, last one wins
- Verified: `{"ok":false,"ok":true}` parses to `ok: True`.
- **Control:** `object_pairs_hook` that rejects duplicate keys. This matches the strict "no NaN, exact ID" intent.

### R4 (low): the startup file can be replaced between construction and finish
- `stdout_path` is resolved at construction, but (st_dev, st_ino) is only recorded at `finish`.
- **Control:** capture `os.stat(stdout_path)` (dev, ino) in `__init__` and require equality in `finish`, using the
  fstat of the opened stream.

### R5 (note): errors inside `__init__` are not domain errors
- psutil errors raised by `_owned_identity` in `__init__` (NoSuchProcess / AccessDenied) propagate as psutil exceptions,
  not AdapterEvidenceError. A caller catching only AdapterEvidenceError would miss them.
- Wrap them, or document it.

## Not covered by this review (caller requirements, as stated in the module)
- The mandatory outer qualified Job, launch and kill, the GPU grant, focus/title acceptance, affinity, and final cleanup.

## Proposed focused source-only controls (nothing executed)
These are pure tests over a synthetic connection table and synthetic reply bytes. No sockets, no process.

| case | expectation |
|---|---|
| P1 peer owned | exactly one ESTABLISHED server entry with raddr = our local endpoint and pid = owned: pass |
| P2 peer foreign | that entry's pid is foreign: reject |
| P3 peer missing or duplicated | zero or two matching entries: reject |
| J1 reply contains `1e999` | reject (R2) |
| J2 reply has a duplicate `ok` key | reject (R3) |
| S1 startup file swapped (dev/ino differs) | reject (R4) |
| Existing behaviour as regression | listener ambiguity (IPv4 + `::1`, `0.0.0.0`, `::`, `::ffff:127.0.0.1`), ID mismatch, 16 KiB+1, data after the newline, EOF before the newline |
