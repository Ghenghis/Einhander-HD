"""Bounded capture pilot for the owned Stage 1 session, with explicit telemetry."""
import json
import os
import hashlib
import sys
import time

from stage1_session import ROOT, command, screenshot

duration = int(sys.argv[1]) if len(sys.argv) > 1 else 480
prefix = os.environ.get('EIN_CAPTURE_PREFIX','stock-stage1')
confirmation_path = ROOT/'evidence/gameplay-confirmed.json'
if not confirmation_path.exists():
    raise RuntimeError('Gameplay must be visually confirmed in this isolated session before RAM assists/input pilot')
confirmation = json.loads(confirmation_path.read_text())
confirmed_capture = ROOT/'captures'/confirmation['capture_name']
if hashlib.sha256(confirmed_capture.read_bytes()).hexdigest()!=confirmation['capture_sha256']:
    raise RuntimeError('Gameplay confirmation capture changed')
started = time.monotonic()
last_capture = -20
last_report = -10
records = []
trace_uploads = os.environ.get('EIN_CAPTURE_UPLOAD_TRACE', '0') == '1'
seen_uploads = set()
last_palette_probe = -5
stop_on_palette_loss = os.environ.get('EIN_CAPTURE_STOP_ON_PALETTE_LOSS', '0') == '1'
last_good_palette_frame = None
print('Capture pilot started: isolated game only; lives/invulnerability aid; ammo refill opt-in.', flush=True)
try:
    while (elapsed := time.monotonic() - started) < duration:
        # Documented US-version fields; one-byte writes only, no save files.
        command('write_ram', addr='0x80085718', val='0xA5')
        if int(elapsed) % 3 == 0:
            command('write_ram', addr='0x800813C4', val='0x03')
            if os.environ.get('EIN_CAPTURE_AMMO','0')=='1':
                # GameHacking.org NTSC-U: two 16-bit 0x000F refill fields.
                for address, value in [('0x80084832','0x0F'), ('0x80084833','0x00'),
                                       ('0x80084834','0x0F'), ('0x80084835','0x00')]:
                    command('write_ram', addr=address, val=value)
        # Both standard fire buttons. Alternate a short vertical sweep with
        # neutral aim; the ship's movement and game state remain game-driven.
        phase = int(elapsed * 2) % 12
        direction = 0x10 if phase == 0 else 0x40 if phase == 6 else 0
        buttons = 0xFFFF & ~0xC000 & ~direction
        command('press', buttons=buttons, frames=18)
        if stop_on_palette_loss:
            observed_frame = command('get_registers')['frame']
            probe = command('vram_peek', x=128, y=492, w=16, h=1)
            if int(probe['hex'], 16):
                last_good_palette_frame = observed_frame
            elif last_good_palette_frame is not None:
                trigger = {'last_good_observed_frame':last_good_palette_frame,
                    'zero_observed_frame':observed_frame,'elapsed':elapsed,
                    'probe':probe,'coherency':command('gl_coh_ring',n=8192),
                    'uploads':command('a0_history')}
                first = max(last_good_palette_frame - 2, observed_frame - 120)
                trigger['frames'] = [command('gpu_frame_dump',frame=frame)
                    for frame in range(first, observed_frame + 2)]
                trigger['capture'] = screenshot('palette-loss-trigger')
                (ROOT/'evidence/palette-loss-trigger.json').write_text(json.dumps(trigger,indent=2)+'\n')
                print(json.dumps({'palette_loss_detected':True,'first_frame':first,'observed_frame':observed_frame}),flush=True)
                break
        if trace_uploads:
            uploads = command('a0_history')
            with (ROOT/'evidence/uploads.jsonl').open('a', encoding='utf-8') as stream:
                for upload in uploads.get('uploads', []):
                    key = tuple(upload.get(k) for k in ('frame', 'x', 'y', 'w', 'h', 's2', 'fw0', 'fw1'))
                    if key not in seen_uploads:
                        stream.write(json.dumps(upload) + '\n')
                        seen_uploads.add(key)
            if elapsed - last_palette_probe >= 5:
                probes = []
                for x, y in ((128,492),(144,492),(160,492),(224,498),(0,505),(0,506)):
                    probes.append(command('vram_peek', x=x, y=y, w=16, h=1))
                with (ROOT/'evidence/palette-probes.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'elapsed':elapsed,'frame':command('get_registers')['frame'],'probes':probes}) + '\n')
                last_palette_probe = elapsed
        if elapsed - last_capture >= 15:
            row={'elapsed':round(elapsed,1), 'capture':screenshot(f'{prefix}-{int(elapsed):04d}')}
            row['gpu']=command('gpu_state')
            row['lives']=command('read_ram',addr='0x800813C4',size=1)
            row['stock_png_count']=len(list((ROOT/'stock/einhander-texture-replacements').glob('*.png')))
            records.append(row)
            (ROOT/'evidence/capture-run.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
            last_capture=elapsed
        if elapsed-last_report>=10:
            print(json.dumps({'elapsed':round(elapsed,1),'stock_pngs':len(list((ROOT/'stock/einhander-texture-replacements').glob('*.png'))),'captures':len(records)}),flush=True)
            last_report=elapsed
        time.sleep(.18)
finally:
    try:
        command('set_input', buttons='0xFFFF')
    except Exception:
        pass
print('Capture pilot completed; coverage still requires visual stage/boss verification.', flush=True)
