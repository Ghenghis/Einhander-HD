"""Acceptance checks shared by native-code qualification and cache staging.

Early clean calls cannot qualify a run that later freezes or never finishes a
shadow comparison. These checks do not establish pacing or whole-game parity.
"""
import math


def qualification_errors(proof, world):
    errors = []
    for name, result in [('qualification', proof), ('game run', world)]:
        if result.get('errors'):
            errors.append(name + ' reported errors')
        if result.get('owned_process_exit') != 0 or not result.get('close', {}).get('port_closed'):
            errors.append(name + ' did not close normally')
    samples = proof.get('samples', [])
    if not samples:
        return errors + ['No final native comparison sample']
    final = samples[-1]
    shadow = final.get('shadow', {}).get('shadow', {})
    if shadow.get('in_shadow') != 0:
        errors.append('Final shadow comparison is unfinished')
    if shadow.get('native_exec') != 1:
        errors.append('Native execution was not restored after comparison')
    if shadow.get('divergences') != 0 or shadow.get('records'):
        errors.append('Native comparison has divergences or missing results')
    if shadow.get('skipped_device') != 0:
        errors.append('Native comparison skipped device work or has missing results')
    requested = proof.get('requested_entries', [])
    if not requested:
        errors.append('No requested native entries')
    candidates = final.get('hot_candidates', {})
    for entry in requested:
        rows = candidates.get(entry, {}).get('candidates', [])
        if not any(c.get('match') and c.get('diff_passes', 0) >= 32
                   and c.get('device_touch') == 0 for c in rows):
            errors.append(entry + ' lacks 32 clean exact-byte comparisons')

    observations = world.get('observations', [])
    if len(observations) < 2:
        return errors + ['Insufficient guest progress observations']
    previous_time = previous_frame = last_progress = None
    try:
        for row in observations:
            elapsed = float(row['elapsed_seconds'])
            frame = int(row['registers']['frame'])
            if not math.isfinite(elapsed) or frame < 0:
                raise ValueError('Invalid observation')
            if previous_time is not None:
                if elapsed <= previous_time or frame < previous_frame:
                    errors.append('Guest progress observations went backwards')
                    break
                if frame > previous_frame:
                    last_progress = elapsed
                elif elapsed - last_progress >= 10:
                    errors.append(f'No guest frame progress for at least 10 seconds (frame {frame})')
                    break
            else:
                last_progress = elapsed
            previous_time, previous_frame = elapsed, frame
    except (KeyError, TypeError, ValueError, OverflowError):
        errors.append('Malformed guest progress observations')
    return errors
