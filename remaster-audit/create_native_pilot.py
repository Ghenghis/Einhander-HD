"""Create a real PILOT profile using native UI, only on an isolated blank card."""
import hashlib
import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from stage1_session import ROOT, PORT, command, screenshot

if not ROOT.resolve().is_relative_to(Path('C:/github/REMASTER_STAGING/full-remaster').resolve()):
    raise RuntimeError('Native profile automation is limited to this task\'s isolated sessions')
card = ROOT/'state/card1.mcd'
data = card.read_bytes()
assert len(data) == 131072 and data[:2] == b'MC'
assert all(data[128*(1+i)] == 0xA0 for i in range(15)), 'Use an isolated blank card'
before = hashlib.sha256(data).hexdigest()
EVIDENCE = Path('C:/github/REMASTER_STAGING/full-remaster')
refs = {
    'no-data': EVIDENCE/'validation-cached-hd/captures/validation-current.png',
    'no-name': EVIDENCE/'validation-cached-hd/captures/circle-card-check.png',
    'title': EVIDENCE/'ui-capture-v2/captures/title-fmv-skipped.png',
    'name-grid': EVIDENCE/'validation-lle-cards/captures/native-name-ready.png',
}


def wait_for(name, rect, seconds=20):
    with Image.open(refs[name]) as image:
        reference = image.convert('RGB').crop(rect)
    deadline = time.monotonic()+seconds
    for i in range(seconds):
        result = screenshot(f'pilot-setup-{name}')
        if result.get('ok'):
            with Image.open(result['path']) as image:
                difference = ImageChops.difference(reference, image.convert('RGB').crop(rect))
                distance = sum(ImageStat.Stat(difference).mean)/3
            if distance < 10:
                print(json.dumps({'observed':name,'distance':distance}),flush=True)
                return
        if time.monotonic() >= deadline:
            break
        time.sleep(1)
    raise RuntimeError('Native screen not observed: '+name)


def tap(word, frames=12, delay=.4):
    response = command('press', buttons=word, frames=frames)
    assert response.get('ok'), response
    time.sleep(delay)


wait_for('no-data', (112,367,1170,593), seconds=60)
tap(0xBFFF, 36, 1)
wait_for('no-name', (300,400,1000,520))
tap(0xBFFF, 36, 1)
for i in range(15):
    if command('fmv_state')['mdec_decode_count']:
        break
    time.sleep(1)
else:
    raise RuntimeError('FMV did not start after native startup prompts')
tap(0xFFF7)
wait_for('title', (100,300,1100,630))
time.sleep(3)
tap(0xFFDF,24,1.3)  # Game Start -> File Option (one step).
print(screenshot('pilot-setup-file-option-selected'),flush=True)
tap(0xBFFF,24,2)
tap(0xBFFF,24,2)  # Create data file.
wait_for('name-grid', (100,440,1180,850))

bits = {'down':0xFFBF,'up':0xFFEF,'right':0xFFDF,'left':0xFF7F}
row = col = 0
for letter in 'PILOT':
    target_row, target_col = divmod(ord(letter)-ord('A'),10)
    for direction, count in [('down' if target_row>row else 'up',abs(target_row-row)),
                             ('right' if target_col>col else 'left',abs(target_col-col))]:
        for i in range(count):tap(bits[direction],6,.3)
    tap(0xBFFF,6,.3)
    row,col = target_row,target_col
for i in range(9-col):tap(bits['right'],6,.3)
for i in range(3-row):tap(bits['down'],6,.3)
print(screenshot('pilot-setup-name-complete'),flush=True)
tap(0xBFFF,12,2)  # End.
print(screenshot('pilot-setup-confirmation'),flush=True)
tap(0xBFFF,12,1)  # Yes, on the isolated blank card.
created = False
for i in range(30):
    current = card.read_bytes()
    entries = [current[128*(1+j):128*(2+j)] for j in range(15)]
    # Einhander uses the fixed card filename BASCUS-94243; pilot names live
    # inside that save's payload, not in the card directory filename.
    if any(e[0] == 0x51 and e[10:30].rstrip(b'\0') == b'BASCUS-94243'
           and current[8192*(1+j):8192*(1+j)+2] == b'SC'
           and b'PILOT' in current[8192*(1+j):8192*(2+j)]
           for j,e in enumerate(entries)):
        created = True
        break
    time.sleep(1)
report = {'created':created, 'pilot':'PILOT', 'port':PORT, 'card':str(card),
          'before_sha256':before, 'after_sha256':hashlib.sha256(card.read_bytes()).hexdigest(),
          'user_card_modified':False, 'restart_load_verified':False}
(ROOT/'evidence/native-pilot-creation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
command('clear_input')
raise SystemExit(0 if created else 1)
