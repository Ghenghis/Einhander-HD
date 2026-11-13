"""Acceptance checks shared by native-code qualification and cache staging.

Early clean calls cannot qualify a run that later freezes or never finishes a
shadow comparison. These checks do not establish pacing or whole-game parity.
"""
import math


# Explicit unit boundaries of the collision routines under qualification. These
# are guest addresses, not copied game bytes. A clean prologue alone cannot
# establish equivalence of a CPS function that returns through continuations.
NONLEAF_UNITS = {
    0xB5C08: [(0x800B5C08, 'call'), (0x800B5C08, 'return'),
              (0x800B5CD4, 'call'), (0x800B5CD4, 'return')],
    0xB5EB8: [(0x800B5EB8, 'call'), (0x800B5EB8, 'return'),
              (0x800B5F34, 'call'), (0x800B5F34, 'return')],
    0xB61A4: [(0x800B61A4, 'call'), (0x800B61A4, 'return'),
              (0x800B630C, 'return')],
}


def nonleaf_unit_errors(entry, candidates, shadow):
    try:
        required = NONLEAF_UNITS.get(int(entry, 16) & 0x1FFFFFFF)
    except (TypeError, ValueError):
        return [str(entry) + ' is not a guest address']
    if not required:
        return []
    units = shadow.get('units')
    if (not isinstance(units, list) or shadow.get('unit_overflow') != 0
            or shadow.get('units_total') != len(units)
            or shadow.get('units_listed') != len(units)):
        return [entry + ' lacks complete per-unit comparison results']
    errors = []
    exact = [c for c in candidates if c.get('match') and c.get('device_touch') == 0]
    for pc, exit_kind in required:
        accepted = False
        for c in exact:
            # An address can have multiple native variants. Counts must belong
            # to the exact Candidate and code CRC that matched the live bytes.
            if not isinstance(c.get('index'), int) or not isinstance(c.get('crc'), str):
                continue
            for u in units:
                try:
                    same = (u['candidate_index'] == c['index']
                            and int(u['code_crc'], 16) == int(c['crc'], 16)
                            and int(u['cand'], 16) == (int(entry, 16) & 0x1FFFFFFF)
                            and int(u['unit'], 16) == pc and u['exit'] == exit_kind)
                    clean = (isinstance(u['clean'], int) and u['clean'] >= 32
                             and u['div'] == 0 and u['skip'] == 0
                             and u['last_div_kind'] == 0)
                except (KeyError, TypeError, ValueError):
                    continue
                if same and clean:
                    accepted = True
                    break
            if accepted:
                break
        if not accepted:
            errors.append(f'{entry} unit 0x{pc:08X} {exit_kind} lacks 32 clean same-code comparisons')
    return errors


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
        errors.extend(nonleaf_unit_errors(entry, rows, shadow))

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
