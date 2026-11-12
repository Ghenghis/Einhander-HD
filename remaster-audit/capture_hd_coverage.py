"""Bounded replacement-coverage capture after visual gameplay confirmation."""
import argparse
import hashlib
import json
import time
from stage1_session import ROOT, command, screenshot

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds', type=float, default=120)
args = parser.parse_args()
if not 1 <= args.seconds <= 600:
    raise ValueError('Coverage duration must be 1..600 seconds')
confirmation = json.loads((ROOT/'evidence/gameplay-confirmed.json').read_text())
capture = ROOT/'captures'/confirmation['capture_name']
if hashlib.sha256(capture.read_bytes()).hexdigest() != confirmation['capture_sha256']:
    raise RuntimeError('Gameplay confirmation image changed')


def stats():
    path = ROOT/'evidence/draws.jsonl.stats.json'
    for attempt in range(3):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            time.sleep(.01)


samples, captures = [], []
before = stats()
started = time.monotonic()
last_sample, last_capture, last_lives = -2, -30, -2
command('set_input', buttons='0x3FFF')
try:
    while (elapsed := time.monotonic() - started) < args.seconds:
        # Same stationary autofire route and documented US-version RAM assists
        # in both isolated runs. No cards or saved guest states are modified.
        command('write_ram', addr='0x80085718', val='0xA5')
        if elapsed - last_lives >= 2:
            command('write_ram', addr='0x800813C4', val='0x03')
            last_lives = elapsed
        if elapsed - last_sample >= 2:
            row = {'elapsed': elapsed, 'stats': stats(), 'frame': command('get_registers')['frame']}
            samples.append(row)
            (ROOT/'evidence/coverage-samples.json').write_text(json.dumps(samples, indent=2)+'\n')
            last_sample = elapsed
        if elapsed - last_capture >= 30:
            captures.append({'elapsed':elapsed, 'capture':screenshot(f'coverage-{int(elapsed):04d}')})
            print(json.dumps(samples[-1]), flush=True)
            last_capture = elapsed
        time.sleep(.2)
finally:
    command('clear_input')
after = stats()
fields = ('attempts','source_matched','decoded_ready','fully_covered','replacement_draws',
          'texture_window_fallbacks','decode_pending','decode_unavailable','page_draws','upload_draws','gpu_cache_hits')
delta = {key: after[key]-before.get(key,0) for key in fields if key in after}
report = {'duration_seconds':time.monotonic()-started,'counter_frames':[before['frame'],after['frame']],
    'delta':delta,'replacement_draw_ratio':delta['replacement_draws']/delta['attempts'] if delta['attempts'] else None,
    'definition':'Fraction of textured-triangle queries submitted using replacement images; not visible pixel coverage or neural-detail coverage.',
    'input_route':'Stationary held Cross+Square, same lives/invulnerability aids in both isolated sessions.',
    'captures':captures,'before':before,'after':after}
(ROOT/'evidence/coverage-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2), flush=True)
