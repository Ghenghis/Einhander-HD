"""Read-only replay/hash checks for the published v58 diagnostic telemetry."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
checks = []
for row in manifest['files']:
    data = (root / row['path']).read_bytes()
    assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], row['path']
    if row['path'].endswith('.json'):
        json.loads(data)
checks.append('all manifest file sizes, SHA256 values and JSON syntax match')
test = subprocess.run([sys.executable, str(root / 'test_analyze_frame_phases.py')], capture_output=True, text=True)
assert test.returncode == 0, test.stdout + test.stderr
checks.append('actual analyzer fixture rejects invalid rows and assigns injected wait to correct phase')
with tempfile.TemporaryDirectory(prefix='ein-v58-replay-') as tmp:
    for tag in ('r2', 'r3'):
        observation = root / f'{tag}-observations.json'
        data = json.loads(observation.read_text(encoding='utf-8'))
        obs = data['observations']
        for script, suffix, extra in (
            ('analyze_frame_phases.py', 'analysis', ['--top', '15']),
            ('correlate_swap_uploads.py', 'uploads', []),
            ('correlate_audio_stalls.py', 'audio', []),
        ):
            target = Path(tmp) / f'{tag}-{suffix}.json'
            result = subprocess.run([sys.executable, str(root / script), str(observation), *extra, '--out', str(target)],
                                    capture_output=True, text=True, encoding='utf-8')
            assert result.returncode == 0, result.stderr
            actual = json.loads(target.read_text(encoding='utf-8'))
            expected = json.loads((root / f'{tag}-{suffix}.json').read_text(encoding='utf-8'))
            if suffix == 'uploads':
                actual.pop('proof'); expected.pop('proof')
            assert actual == expected, f'{tag}-{suffix} replay differs'
        audio = json.loads((root / f'{tag}-audio.json').read_text(encoding='utf-8'))
        assert audio['summary']['starved_total'] == obs[-1]['audio']['out']['underruns'] - obs[0]['audio']['out']['underruns']
        assert data['owned_process_exit'] == 0 and data['close']['port_closed'] and not data['errors']
        checks.append(f'{tag}: all three analyses replay exactly; independent audio delta and process cleanup match')
print(json.dumps({'passed': True, 'checks': checks}, indent=2))
