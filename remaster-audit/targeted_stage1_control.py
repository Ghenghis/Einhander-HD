"""Short, journaled observation segments; no automatic semantic acceptance.

The caller must visually confirm the native pause menu before --resume.
Recording is started before input; cleanup releases input/holds and finalizes.
Assists are explicitly reported and briefly released for visible hull frames.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from live_level1_probe import ROOT, api, command, shot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--seconds', type=int, choices=range(5, 46), default=20)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--fire', action='store_true')
    parser.add_argument('--buttons', type=lambda value: int(value, 0), default=0x7FFF,
                        help='Active-low virtual pad word for the finite fire input')
    parser.add_argument('--assist', action='store_true')
    parser.add_argument('--filter-report')
    args = parser.parse_args()
    if not 0 <= args.buttons <= 65535:
        raise ValueError('Input must be a u16 virtual pad word')
    parent = Path(args.evidence).resolve()
    if not parent.is_relative_to((ROOT/'remaster-audit/dev-center-evidence').resolve()) or not parent.is_dir():
        raise ValueError('Use an existing owned evidence session')
    if not args.name.replace('-', '').isalnum() or len(args.name) > 48:
        raise ValueError('Use a short unique ASCII segment name')
    directory = parent/args.name
    directory.mkdir(exist_ok=False)
    journal = []
    report = dict(at_utc=datetime.now(timezone.utc).isoformat(), seconds=args.seconds,
                  label=args.name, pause_menu_visually_confirmed_by_caller=args.resume,
                  assisted=args.assist, fire=args.fire, input_buttons=args.buttons, observations=journal,
                  semantic_acceptance=False, errors=[])

    def record(action, reply):
        journal.append(dict(at_utc=datetime.now(timezone.utc).isoformat(), action=action, reply=reply))
        (directory/'actions.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        return reply

    def pulse(buttons):
        record('input-pulse', command('set_input', buttons=buttons))
        time.sleep(.3)
        record('input-release', command('clear_input'))

    request = dict(action='start', scenario='stage1_completion_pass', label=args.name,
                   limits=dict(duration_seconds=min(60, args.seconds+15), interval_seconds=.5,
                               max_samples=150, max_events=3, max_disk_bytes=33554432,
                               native_max_sources=224, native_max_records=7000,
                               native_max_events=3, native_max_frames=3600, native_max_bytes=25165824))
    if args.filter_report:
        plan = json.loads(Path(args.filter_report).read_bytes())
        request['source_filter'] = plan['capture_plan']['source_filter_batches'][0]
    active = False
    resumed = False
    try:
        started = record('record-start', api('/dev/research', request))
        if not started.get('ok'):
            raise RuntimeError('Recorder start failed: '+str(started.get('error')))
        active = True
        if args.assist:
            record('assisted-countdown-hold', api('/dev/lock', dict(field='invincibility', value=161,
                   enabled=True, ttl_seconds=min(120, args.seconds+20))))
            record('assisted-lives-hold', api('/dev/lock', dict(field='lives', value=3,
                   enabled=True, ttl_seconds=min(120, args.seconds+20))))
        if args.resume:
            pulse('0xFFF7')
            resumed = True
        if args.fire:
            record('finite-fire-input-begin', command('set_input', buttons=f'0x{args.buttons:04X}'))
        began = time.monotonic()
        for index, fraction in enumerate((.1, .5, .9)):
            target = args.seconds*fraction
            remaining = target-(time.monotonic()-began)
            if remaining > 0:
                time.sleep(remaining)
            # A positive countdown also controls model blinking. Do not accept
            # a hidden hull as a successful visual result. Release the assist
            # briefly, preserving explicit write/hold context in the journal.
            if args.assist:
                record('countdown-hold-release-for-frame', api('/dev/lock', dict(field='invincibility', enabled=False)))
                # Let the game's 1 -> 0 transition clear its latched model
                # visibility flag. Directly writing zero bypasses that branch.
                record('countdown-natural-expiry-for-frame', api('/dev/write', dict(field='invincibility', value=1)))
                time.sleep(.12)
            record('frame-'+str(index), shot(directory, 'observation-'+str(index)))
            record('native-status-'+str(index), command('research_capture', op='status'))
            if args.assist:
                record('countdown-hold-resume', api('/dev/lock', dict(field='invincibility', value=161,
                       enabled=True, ttl_seconds=min(120, args.seconds+10))))
        remaining = args.seconds-(time.monotonic()-began)
        if remaining > 0:
            time.sleep(remaining)
    except Exception as exc:
        report['errors'].append(str(exc))
    finally:
        record('input-release-final', command('clear_input'))
        if active:
            pulse('0xFFF7')
            report['pause_requested_at_end'] = True
            first = command('gpu_state')
            time.sleep(.25)
            second = command('gpu_state')
            delta = second.get('gp0_draw', 0)-first.get('gp0_draw', 0)
            report['pause_motion_check'] = dict(gp0_draw_delta=delta,
                scope='A stable draw counter is a pause hint; caller must still inspect the native pause menu')
            record('pause-motion-check', dict(ok=bool(first.get('ok') and second.get('ok')), gp0_draw_delta=delta))
        if args.assist:
            for field in ('invincibility', 'lives'):
                record('hold-release-final-'+field, api('/dev/lock', dict(field=field, enabled=False)))
        if active:
            record('record-stop', api('/dev/research', dict(action='stop')))
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        (directory/'actions.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(path=str(directory), errors=report['errors'],
                         run_id=next((row['reply'].get('status', {}).get('id') for row in journal
                                      if row['action']=='record-start'), None),
                         frames=[row['reply'] for row in journal if row['action'].startswith('frame-')]), indent=2))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
