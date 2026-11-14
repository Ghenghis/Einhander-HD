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
