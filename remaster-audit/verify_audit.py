"""Acceptance checks for the count, preservation, and coverage claims."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
STAGING = Path('C:/github/REMASTER_STAGING')
PACK = Path('C:/github/Einhänder_HDtext01/textures/SCUS-94243/replacements')
checks = []


def passed(name):
    checks.append({'check': name, 'status': 'PASS'})


inventory = json.loads((STAGING / 'pack_inventory.json').read_text(encoding='utf-8'))
summary = json.loads((STAGING / 'summary.json').read_text(encoding='utf-8'))
assert len(inventory) == 1820
assert summary['scales'] == {'4x4': 1816, '1x1': 4}
assert summary['largest_side_px'] == 1024
assert summary['missing_full_game_count'] is None
passed('All 1820 entries counted; 1816 at 4x, four at 1x, maximum side 1024; unknown coverage is null')
for row in inventory:
    with (PACK / row['relative_path']).open('rb') as file:
        assert hashlib.file_digest(file, 'sha256').hexdigest() == row['sha256']
passed('Every installed-pack PNG still matches its initial audit SHA256')

records = json.loads((STAGING / 'prototypes/prototype_manifest.json').read_text())
for row in records:
    with Image.open(row['source']) as source, Image.open(row['output']) as result:
        assert list(result.size) == row['output_size']
        expected = source.convert('RGBA').getchannel('A').resize(result.size, Image.Resampling.NEAREST)
        assert expected.tobytes() == result.convert('RGBA').getchannel('A').tobytes()
    assert row['installed_in_game'] is False
passed('Three isolated model proofs have expected dimensions and exact source alpha-class replication')

fmv = json.loads((STAGING / 'fmv_inventory.json').read_text())
assert len(fmv['groups']) == 6 and fmv['total_frames'] == 5895
assert all((g['width'], g['height']) == (320, 192) and g['incomplete_chunk_sets'] == 0 for g in fmv['groups'])
passed('Six detected STR runs contain 5895 frames at 320x192 with complete chunk sets')

# A real missing-key fixture must yield exactly one observed gap, while still
# refusing to call this a full-game count. A second matching key exercises both paths.
fixture = ROOT / 'verification/duckstation-dump'
fixture.mkdir(parents=True, exist_ok=True)
existing = inventory[0]['filename']
missing = existing.replace(inventory[0]['texture_hash'], '0123456789ABCDEF', 1)
assert missing != existing
shutil.copy2(PACK / existing, fixture / existing)
shutil.copy2(PACK / existing, fixture / missing)
environment = dict(os.environ, PYTHONIOENCODING='utf-8')
run = subprocess.run([sys.executable, str(ROOT / 'audit_remaster.py'),
                      '--duckstation-dump', str(fixture),
                      '--staging', str(ROOT / 'verification/outputs')],
                     capture_output=True, text=True, encoding='utf-8', timeout=60, env=environment)
if run.returncode:
    raise AssertionError(run.stderr)
test_summary = json.loads((ROOT / 'verification/outputs/summary.json').read_text(encoding='utf-8'))
assert test_summary['observed_duckstation_keys'] == 2
assert test_summary['observed_exact_filename_gaps'] == 1
assert test_summary['missing_full_game_count'] is None
passed('Compatible two-key fixture finds its one real observed filename gap and leaves full-game coverage unknown')

checks += [
    {'check': 'In-game 1440p/4K A/B and complete gameplay coverage', 'status': 'NOT RUN'},
    {'check': 'Missing-model renderer defect fixed', 'status': 'NOT RUN'},
    {'check': 'External HD FMV playback/audio sync', 'status': 'NOT RUN'},
    {'check': 'Image-generated title meets exact-layout/glyph and 1440p+ delivery requirements', 'status': 'NOT APPROVED'},
]
(STAGING / 'verification.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
print(json.dumps(checks, indent=2))
