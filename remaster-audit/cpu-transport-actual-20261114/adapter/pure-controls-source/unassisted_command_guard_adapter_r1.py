"""Pre-send policy and durable request intent for the unassisted review runner."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

SIMPLE = {'get_registers', 'audio_stats', 'turbo_state', 'hd_cpu_profile',
          'native_upload_selftest', 'display_ring_stats', 'clear_input', 'quit',
          'present_shot_seq', 'gpu_state'}


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate_command(report, request):
    if not isinstance(request, dict):
        raise ValueError('Command object required')
    command = request.get('cmd')
    fields = {k: v for k, v in request.items() if k != 'cmd'}
    visual = report['visual_profile']
    if visual.get('timer_only_assistance') is not False:
        raise ValueError('This command policy permits unassisted gameplay only')
    if command in SIMPLE and not fields:
        return
    if command == 'turbo' and fields == {'enabled': 0} and type(fields['enabled']) is int:
        return
    if command == 'press' and set(fields) == {'buttons', 'frames'}:
        if integer(fields['buttons'], 0, 65535) and integer(fields['frames'], 1, 120):
            return
    if command == 'set_input' and fields == {'buttons': '0x7FFF'} and visual.get('ordinary_fire') is True:
        return
    if command == 'set_input' and fields in ({'buttons': '0xBFFF'}, {'buttons': '0xFFBF'}):
        if report.get('command_phase') == 'native-menu-route':
            return
    if command == 'read_ram' and fields in ({'addr': '0x800813C4', 'len': 1},
                                           {'addr': '0x80081380', 'len': 6}):
        return
    if command in {'frame_phase_ring', 'native_upload_ledger'}:
        allowed = {'n', 'from_seq', 'from_frame', 'to_frame'} if command == 'frame_phase_ring' else {'n', 'from_seq'}
        if set(fields) <= allowed and integer(fields.get('n'), 1, 2048 if command == 'frame_phase_ring' else 256):
            if all(integer(v, 0, 2**64-1) for k,v in fields.items() if k != 'n'):
                return
    if command == 'gl_present_ring' and fields == {'n': 16384} and type(fields['n']) is int:
        return
    if command == 'hd_upload_ledger' and set(fields) == {'from_seq', 'n'}:
        if integer(fields['from_seq'],0,2**64-1) and integer(fields['n'],1,128):
            return
    if command in {'screenshot', 'present_shot'} and set(fields) == {'path'}:
        target = Path(fields['path']).resolve()
        root = Path(report['evidence']).resolve()
        if target.is_relative_to(root) and target.suffix.lower() == '.png':
            return
    raise ValueError('Unassisted command refused before send: ' + str(command))


def send_guarded(original, report, raw):
    request = json.loads(raw)
    validate_command(report, request)
    directory = Path(report['evidence']) / 'command-intents'
    directory.mkdir(exist_ok=True)
    target = directory / (uuid.uuid4().hex + '.json')
    # A timed-out send still has a durable, uniquely named intent. A result
    # receipt from the existing transport is additional evidence, not a prerequisite.
    with target.open('x', encoding='utf-8') as stream:
        json.dump(dict(request=request, command_phase=report.get('command_phase','gameplay'),
                       state='validated_before_transport'), stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return original(report, raw)


def audit_commands(report):
    root = Path(report['evidence'])
    errors = []
    count = 0
    intents = {}
    for directory in ('command-intents', 'commands'):
        for receipt in (root/directory).glob('*.json'):
            try:
                row = json.loads(receipt.read_bytes())
                request = dict(row['request'])
                request.pop('id', None)
                signature=json.dumps(request,sort_keys=True)
                if directory == 'command-intents':
                    phase=row.get('command_phase','gameplay')
                    validate_command(dict(report,command_phase=phase),request)
                    intents.setdefault(signature,[]).append(phase)
                else:
                    phases=intents.get(signature)
                    if not phases:raise ValueError('Transport receipt has no validated request intent')
                    validate_command(dict(report,command_phase=phases[0]),request)
                count += 1
            except Exception as error:
                errors.append(dict(receipt=str(receipt),error=type(error).__name__+': '+str(error)))
    return dict(checked_records=count, forbidden_or_malformed=errors, timer_write_requests=0)


@contextmanager
def guarded_commands(ui, probe):
    old_ui, old_probe = ui.command, probe.command
    ui.command = lambda report, raw: send_guarded(old_ui, report, raw)
    probe.command = lambda report, raw: send_guarded(old_probe, report, raw)
    try:
        yield
    finally:
        ui.command, probe.command = old_ui, old_probe


# ==== r1 PRIVATE adapter-qualification binding (claude-einhander-support, EIN-SUPPORT-AUDIT-BINDING-R1-20261114) ====
# NOT canonical. Everything above this banner is canonical unassisted_command_guard.py 9e6ca815, byte for byte. Ordinary
# CLI/ui/probe policy is unchanged and gl_present_ring n=1 is NOT admitted by validate_command or send_guarded.
# r1 follows root review msg_ca94c6d0 of r0 (unassisted_command_guard_adapter_r0.py 1ac7895a, preserved):
#   - The audit returns the exact ordered adapter records, with SHA-256 digests of the exact file bytes. Writes are
#     binary and exclusive, so digest == file bytes. The audited collector binds these to its own ledger.
#   - Strict types: exact ints (bool and float rejected) for ports, pids, family and sequence. `decoded` must be
#     exactly True if present. SHA-256 values must be 64 lowercase hex.
#   - The OUTER audit report must itself be the adapter-qualification scope; there is no internal override.
#   - An unreceipted adapter intent is an audit ERROR, not just a count.
# The ledger never connects, sends or chooses an endpoint. AUTHORED, NOT EXECUTED.
import hashlib
import math
import socket

ADAPTER_PHASE = 'adapter-qualification'
ADAPTER_PROFILE = 'adapter-qualification-v1'
ADAPTER_REQUEST_BYTES = b'{"id":1,"cmd":"gl_present_ring","n":1}\n'
ADAPTER_REQUEST = {'id': 1, 'cmd': 'gl_present_ring', 'n': 1}
ADAPTER_REQUEST_SHA256 = hashlib.sha256(ADAPTER_REQUEST_BYTES).hexdigest()
ADAPTER_MAX_QUERIES = 2
ADAPTER_MAX_REPLY_BYTES = 16 * 1024
_TRANSPORT_KEYS = frozenset({'sent', 'reply_bytes', 'reply_sha256', 'decoded', 'error'})
_TRANSPORT_REQUIRED = frozenset({'sent', 'reply_bytes', 'reply_sha256'})
_PEER_KEYS = frozenset({'server', 'client', 'pid', 'family', 'status', 'identity'})
_INTENT_KEYS = frozenset({'request', 'command_phase', 'adapter_profile', 'state', 'intent_id', 'sequence',
                          'endpoint', 'owned_identity', 'peer', 'request_sha256'})
_RECEIPT_KEYS = frozenset({'request', 'command_phase', 'adapter_profile', 'intent_id', 'endpoint',
                           'owned_identity', 'peer', 'transport', 'state'})
_HEX = frozenset('0123456789abcdef')


class AdapterBindingError(ValueError):
    pass


def _bind_need(ok, why):
    if not ok:
        raise AdapterBindingError(why)


def _exact_int(value, low, high):
    return type(value) is int and low <= value <= high          # bool and float are rejected


def _is_sha256_hex(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _strict_loads(raw):
    def constant(value):
        raise AdapterBindingError('non-finite JSON constant in adapter record: ' + value)

    def finite(value):
        parsed = float(value)
        _bind_need(math.isfinite(parsed), 'non-finite JSON float in adapter record')
        return parsed

    def unique(pairs):
        out = {}
        for key, value in pairs:
            _bind_need(key not in out, 'duplicate JSON key in adapter record: ' + key)
            out[key] = value
        return out
    return json.loads(raw, parse_constant=constant, parse_float=finite, object_pairs_hook=unique)


def _profile(report):
    _bind_need(isinstance(report, dict) and report.get('command_phase') == ADAPTER_PHASE
               and report.get('adapter_profile') == ADAPTER_PROFILE,
               'adapter request outside the explicit adapter-qualification profile')
    _bind_need((report.get('visual_profile') or {}).get('timer_only_assistance') is False,
               'This command policy permits unassisted gameplay only')


def validate_adapter_request(report, request):
    """The ONLY admission of gl_present_ring n=1: the given (outer) report is the explicit phase+profile, unassisted,
    and the request is the exact object with real ints."""
    _profile(report)
    _bind_need(isinstance(request, dict) and request == ADAPTER_REQUEST and type(request['id']) is int
               and type(request['n']) is int and type(request['cmd']) is str,
               'adapter request is not the exact gl_present_ring n=1 query')


def _endpoint(value):
    _bind_need(isinstance(value, (tuple, list)) and len(value) == 2 and type(value[0]) is str
               and value[0] == '127.0.0.1' and _exact_int(value[1], 1, 65535),
               'owned endpoint must be exactly 127.0.0.1:<port>')
    return ['127.0.0.1', value[1]]


def _identity(value):
    _bind_need(isinstance(value, (tuple, list)) and len(value) == 2 and _exact_int(value[0], 1, 2**32 - 1)
               and type(value[1]) in (int, float) and math.isfinite(value[1]) and value[1] > 0,
               'owned process identity required')
    return [value[0], value[1]]


def _peer(peer, endpoint, identity):
    _bind_need(isinstance(peer, dict) and set(peer) == _PEER_KEYS, 'connected peer record malformed')
    server = _endpoint(peer['server'])
    client = peer['client']
    _bind_need(server == endpoint and isinstance(client, (list, tuple)) and len(client) == 2
               and type(client[0]) is str and client[0] == '127.0.0.1' and _exact_int(client[1], 1, 65535)
               and _exact_int(peer['pid'], 1, 2**32 - 1) and peer['pid'] == identity[0]
               and _identity(peer['identity']) == identity
               and type(peer['status']) is str and peer['status'] == 'ESTABLISHED'
               and type(peer['family']) is int and peer['family'] == int(socket.AF_INET),
               'connected peer is not the owned endpoint and process')
    return dict(server=server, client=['127.0.0.1', client[1]], pid=peer['pid'], family=peer['family'],
                status='ESTABLISHED', identity=_identity(peer['identity']))


def _transport(value):
    _bind_need(isinstance(value, dict) and set(value) <= _TRANSPORT_KEYS and _TRANSPORT_REQUIRED <= set(value)
               and type(value['sent']) is bool
               and _exact_int(value['reply_bytes'], 0, ADAPTER_MAX_REPLY_BYTES + 1)
               and _is_sha256_hex(value['reply_sha256'])
               and ('decoded' not in value or value['decoded'] is True)
               and ('error' not in value or type(value['error']) is str),
               'malformed adapter transport outcome')
    _bind_need(value.get('decoded') is not True or (value['sent'] is True and 'error' not in value),
               'inconsistent adapter transport outcome')
    return dict(value)


def _write_exclusive(path, data):
    """Serialize first, then write the exact bytes exclusively (binary: no newline translation). Returns the
    SHA-256 of the exact bytes on disk."""
    payload = (json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(payload).hexdigest()


class AdapterIntentLedger:
    """At most two durable, phase-bound adapter intents for ONE owned endpoint and process."""

    def __init__(self, report, *, endpoint, owned_identity):
        _profile(report)
        _bind_need(isinstance(report.get('evidence'), (str, os.PathLike)), 'evidence directory required')
        self.report = dict(report)
        self.endpoint = _endpoint(endpoint)
        self.owned_identity = _identity(owned_identity)
        root = Path(report['evidence'])
        self.intent_dir, self.receipt_dir = root / 'command-intents', root / 'commands'
        self.used = 0
        self.intents = []
        self._records = {}

    def before_send(self, raw, *, peer):
        """Validate and durably log one intent BEFORE any byte is sent. Any failure here means: do not send."""
        _bind_need(self.used < ADAPTER_MAX_QUERIES, 'adapter qualification allows at most two queries')
        self.used += 1                       # consumed before validation/I-O: a failed attempt is never retried
        _bind_need(raw == ADAPTER_REQUEST_BYTES, 'adapter request bytes are not the exact n=1 query')
        request = _strict_loads(raw)
        validate_adapter_request(self.report, request)
        bound = _peer(peer, self.endpoint, self.owned_identity)
        intent_id = uuid.uuid4().hex
        sequence = len(self.intents) + 1     # sequence of WRITTEN intents, so the audit expects exactly 1..n
        self.intent_dir.mkdir(exist_ok=True)
        digest = _write_exclusive(self.intent_dir / (intent_id + '.json'), dict(
            request=request, command_phase=ADAPTER_PHASE, adapter_profile=ADAPTER_PROFILE,
            state='validated_before_transport', intent_id=intent_id, sequence=sequence,
            endpoint=self.endpoint, owned_identity=self.owned_identity, peer=bound,
            request_sha256=ADAPTER_REQUEST_SHA256))
        self.intents.append(intent_id)
        self._records[intent_id] = dict(intent_id=intent_id, sequence=sequence, endpoint=list(self.endpoint),
                                        identity=list(self.owned_identity), peer=bound, intent_sha256=digest,
                                        receipt_sha256=None, state=None)
        return intent_id

    def after_transport(self, intent_id, transport):
        """Durable transport receipt for an intent this ledger wrote (exclusive name = intent id)."""
        _bind_need(intent_id in self._records, 'transport receipt for an intent this ledger did not write')
        outcome = _transport(transport)
        state = 'transport_completed' if outcome.get('decoded') is True else 'transport_failed'
        self.receipt_dir.mkdir(exist_ok=True)
        record = self._records[intent_id]
        digest = _write_exclusive(self.receipt_dir / (intent_id + '.json'), dict(
            request=dict(ADAPTER_REQUEST), command_phase=ADAPTER_PHASE, adapter_profile=ADAPTER_PROFILE,
            intent_id=intent_id, endpoint=self.endpoint, owned_identity=self.owned_identity,
            peer=record['peer'], transport=outcome, state=state))
        record.update(receipt_sha256=digest, state=state)
        return dict(intent_id=intent_id, state=state, receipt_sha256=digest)

    def audit_records(self):
        """The exact records this ledger wrote, ordered by sequence, in the same shape as the audit's
        adapter_records."""
        return [dict(r, endpoint=list(r['endpoint']), identity=list(r['identity']), peer=dict(r['peer']))
                for r in sorted(self._records.values(), key=lambda r: r['sequence'])]


def _audit_adapter_record(report, directory, path, raw, intents, receipts):
    row = _strict_loads(raw)
    _bind_need(isinstance(row, dict) and row.get('command_phase') == ADAPTER_PHASE
               and row.get('adapter_profile') == ADAPTER_PROFILE, 'adapter record outside the explicit profile')
    intent_id = row.get('intent_id')
    _bind_need(type(intent_id) is str and len(intent_id) == 32 and intent_id == path.stem
               and set(intent_id) <= _HEX, 'adapter record name/intent_id mismatch')
    validate_adapter_request(report, row.get('request'))           # OUTER report: no phase/profile override
    endpoint, identity = _endpoint(row.get('endpoint')), _identity(row.get('owned_identity'))
    peer = _peer(row.get('peer'), endpoint, identity)
    digest = hashlib.sha256(raw).hexdigest()
    if directory == 'command-intents':
        _bind_need(set(row) == _INTENT_KEYS and row['state'] == 'validated_before_transport'
                   and row['request_sha256'] == ADAPTER_REQUEST_SHA256
                   and _exact_int(row['sequence'], 1, ADAPTER_MAX_QUERIES), 'malformed adapter intent')
        intents[intent_id] = dict(intent_id=intent_id, sequence=row['sequence'], endpoint=endpoint, identity=identity,
                                  peer=peer, intent_sha256=digest, receipt_sha256=None, state=None)
    else:
        intent = intents.get(intent_id)
        _bind_need(intent is not None, 'adapter transport receipt has no validated intent')
        _bind_need(intent_id not in receipts, 'duplicate adapter transport receipt')
        _bind_need(set(row) == _RECEIPT_KEYS and endpoint == intent['endpoint'] and identity == intent['identity']
                   and peer == intent['peer'], 'adapter transport receipt does not match its intent')
        outcome = _transport(row['transport'])
        state = 'transport_completed' if outcome.get('decoded') is True else 'transport_failed'
        _bind_need(row['state'] == state, 'adapter transport state does not match its outcome')
        intent.update(receipt_sha256=digest, state=state)
        receipts[intent_id] = state


def audit_commands_adapter(report):
    """audit_commands rules for every ordinary record, plus strict adapter rules. Adapter records are accepted only
    when the OUTER report is the adapter-qualification scope. Returns adapter_records: the exact ordered records with
    file-byte digests, for binding by the caller."""
    root = Path(report['evidence'])
    errors = []
    count = 0
    intents = {}
    adapter_intents, adapter_receipts = {}, {}
    for directory in ('command-intents', 'commands'):
        for receipt in sorted((root/directory).glob('*.json')):
            try:
                raw = receipt.read_bytes()
                row = json.loads(raw)
                if isinstance(row, dict) and (row.get('command_phase') == ADAPTER_PHASE or 'adapter_profile' in row):
                    _audit_adapter_record(report, directory, receipt, raw, adapter_intents, adapter_receipts)
                    count += 1
                    continue
                # ---- ordinary record: same rules as canonical audit_commands ----
                request = dict(row['request'])
                request.pop('id', None)
                signature=json.dumps(request,sort_keys=True)
                if directory == 'command-intents':
                    phase=row.get('command_phase','gameplay')
                    validate_command(dict(report,command_phase=phase),request)
                    intents.setdefault(signature,[]).append(phase)
                else:
                    phases=intents.get(signature)
                    if not phases:raise ValueError('Transport receipt has no validated request intent')
                    validate_command(dict(report,command_phase=phases[0]),request)
                count += 1
            except Exception as error:
                errors.append(dict(receipt=str(receipt),error=type(error).__name__+': '+str(error)))
    sequences = sorted(v['sequence'] for v in adapter_intents.values())
    if len(adapter_intents) > ADAPTER_MAX_QUERIES:
        errors.append(dict(receipt='adapter', error='AdapterBindingError: more than two adapter intents'))
    if sequences != list(range(1, len(sequences) + 1)):
        errors.append(dict(receipt='adapter', error='AdapterBindingError: adapter intent sequence is not 1..n'))
    if len({json.dumps([v['endpoint'], v['identity']]) for v in adapter_intents.values()}) > 1:
        errors.append(dict(receipt='adapter', error='AdapterBindingError: adapter intents name different owners'))
    unreceipted = sorted(set(adapter_intents) - set(adapter_receipts))
    for intent_id in unreceipted:
        errors.append(dict(receipt=intent_id, error='AdapterBindingError: unreceipted adapter intent'))
    records = sorted((dict(v) for v in adapter_intents.values()), key=lambda r: (r['sequence'], r['intent_id']))
    return dict(checked_records=count, forbidden_or_malformed=errors, timer_write_requests=0,
                adapter_intents=len(adapter_intents), adapter_receipts=len(adapter_receipts),
                adapter_completed=sum(1 for s in adapter_receipts.values() if s == 'transport_completed'),
                adapter_unreceipted=unreceipted, adapter_records=records)
