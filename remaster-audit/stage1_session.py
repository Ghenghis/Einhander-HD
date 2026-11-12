"""Isolated Stage 1 capture session; never writes the user's cards or pack."""
import argparse
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

PROJECT = Path('C:/github/Einhander/windows-x64')
ROOT = Path(os.environ.get('EIN_STAGE_SESSION_ROOT', 'C:/github/REMASTER_STAGING/stage01_city'))
RUNTIME = ROOT / 'runtime'
PORT = int(os.environ.get('EIN_STAGE_DEBUG_PORT', '4371'))


def command(cmd, **args):
    request = json.dumps({'cmd': cmd, **args}) + '\n'
    with socket.create_connection(('127.0.0.1', PORT), timeout=5) as connection:
        connection.settimeout(8)
        connection.sendall(request.encode())
        data = bytearray()
        while b'\n' not in data:
            chunk = connection.recv(65536)
            if not chunk:
                break
            data.extend(chunk)
        return json.loads(data.split(b'\n', 1)[0])


def screenshot(name):
    destination = ROOT / 'captures' / (name + '.png')
    before = command('present_shot_seq')
    result = command('present_shot', path=destination.as_posix())
    if not result.get('ok'):
        return result
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        completed = command('present_shot_seq')
        if completed.get('seq',0) > before.get('seq',0):
            if not completed.get('wrote'):
                return {'ok':False,'error':'runtime capture failed','seq':completed}
            if destination.exists() and destination.stat().st_size > 100:
                return {'ok': True, 'path': str(destination), 'seq': completed}
        time.sleep(.1)
    return {'ok': False, 'error': 'capture not written', 'before': before}


def launch():
    try:
        existing = command('ping')
        raise RuntimeError(f'Port {PORT} already belongs to a runtime; not launching over it: {existing}')
    except (ConnectionError, OSError):
        pass
    for directory in [RUNTIME, ROOT/'captures', ROOT/'stock/einhander-texture-replacements',
                      ROOT/'accepted/einhander-texture-replacements', ROOT/'state', ROOT/'evidence']:
        directory.mkdir(parents=True, exist_ok=True)
    (ROOT/'stock/Hashes.ini').touch(exist_ok=True)
    (ROOT/'accepted/Hashes.ini').touch(exist_ok=True)
    executable = RUNTIME / 'Einhander_Recompiled.exe'
    executable_source = Path(os.environ.get('EIN_STAGE_EXECUTABLE', str(PROJECT/'build-release/Einhander_Recompiled.exe')))
    shutil.copy2(executable_source, executable)
    cache_source = Path(os.environ.get('EIN_STAGE_CACHE_SOURCE',str(PROJECT/'build-release/cache')))
    if cache_source.exists() and not (RUNTIME/'cache').exists():
        # Keep production's precompiled overlay acceleration in the test build,
        # but copy it because ABI validation may quarantine stale entries.
        shutil.copytree(cache_source,RUNTIME/'cache')
    settings = '''[video]
renderer = "opengl"
supersampling = 4
window_width = 1920
antialiasing = true
texture_filtering = "bilinear"
fmv_filter = "bicubic"
post_degrain = false
geometry_correction = false
perspective_texturing = false
crt_filter = "raw"
bios_hle = true
fast_boot = false
fullscreen = 0
frame_interpolation = false
aspect_ratio = "4:3"
rewind_depth = 0
hd_textures = true
hd_texture_root = "C:/github/REMASTER_STAGING/stage01_city/stock"
hd_dump_root = "C:/github/REMASTER_STAGING/stage01_city/stock/einhander-texture-replacements"
[launcher]
skip_launcher = true
[memcard]
enable1 = false
enable2 = false
[controller]
p1_device = "keyboard"
p1_mode = "digital"
multitap = false
'''
    settings = settings.replace('C:/github/REMASTER_STAGING/stage01_city', ROOT.as_posix())
    texture_root = os.environ.get('EIN_STAGE_TEXTURE_ROOT')
    if texture_root:
        settings = settings.replace('hd_texture_root = "'+ROOT.as_posix()+'/stock"',
                                    'hd_texture_root = "'+Path(texture_root).as_posix()+'"')
    scale = int(os.environ.get('EIN_STAGE_SCALE','4'))
    width = int(os.environ.get('EIN_STAGE_WIDTH','1920'))
    if not 1 <= scale <= 16 or not 640 <= width <= 7680:
        raise ValueError('Invalid isolated proof render size')
    settings = settings.replace('supersampling = 4',f'supersampling = {scale}')
    settings = settings.replace('window_width = 1920',f'window_width = {width}')
    rewind_depth = int(os.environ.get('EIN_STAGE_REWIND_DEPTH','0'))
    if not 0 <= rewind_depth <= 1000:
        raise ValueError('Invalid isolated rewind depth')
    settings = settings.replace('rewind_depth = 0',f'rewind_depth = {rewind_depth}')
    fullscreen = int(os.environ.get('EIN_STAGE_FULLSCREEN','0'))
    if fullscreen not in (0,1,2):
        raise ValueError('Invalid isolated fullscreen mode')
    settings = settings.replace('fullscreen = 0',f'fullscreen = {fullscreen}')
    dumping = os.environ.get('EIN_STAGE_DUMP','1') != '0'
    hd_enabled = os.environ.get('EIN_STAGE_HD','1') != '0'
    if not hd_enabled:
        settings = settings.replace('hd_textures = true', 'hd_textures = false')
        dumping = False
    if not dumping:
        settings = settings.replace('hd_dump_root = "'+ROOT.as_posix()+'/stock/einhander-texture-replacements"',
                                    'hd_dump_root = ""')
    cards_enabled = os.environ.get('EIN_STAGE_CARDS','0') == '1'
    if cards_enabled:
        settings = settings.replace('enable1 = false','enable1 = true')
        # Never mount the user's cards directly in a test instance. Copy once;
        # subsequent test launches retain the isolated game's own writes.
        source = os.environ.get('EIN_STAGE_CARD1_SOURCE')
        destination = ROOT/'state/card1.mcd'
        if source and not destination.exists():
            shutil.copy2(source,destination)
    (RUNTIME/'settings.toml').write_text(settings, encoding='utf-8')
    # Copy game configuration but resolve its few relative asset paths to the
    # original project. Runtime state stays inside this session's directory.
    config = (PROJECT/'game.toml').read_text(encoding='utf-8')
    config = config.replace('exe = "disc/SCUS_942.43"', 'exe = "C:/github/Einhander/windows-x64/disc/SCUS_942.43"')
    config = config.replace('memcard_dir = "saves"', 'memcard_dir = "'+(ROOT/'state').as_posix()+'"')
    (RUNTIME/'game.toml').write_text(config,encoding='utf-8')
    arguments = [str(executable), '--no-launcher', '--game', str(RUNTIME/'game.toml'),
                 '--disc', 'C:/github/Einhander/ROM/Einhander (USA).cue',
                 '--bios', str(PROJECT/'build-release/bios/SCPH1001.BIN'),
                 '--debug-port', str(PORT), '--memcard-dir', str(ROOT/'state'),
                 '--renderer', 'opengl', '--window-title',
                 os.environ.get('EIN_STAGE_WINDOW_TITLE','Einhander - isolated Stage 1 remaster capture')]
    environment = dict(os.environ)
    if dumping:
        environment['PSXRECOMP_HD_DUMP'] = str(ROOT/'stock/einhander-texture-replacements')
    else:
        environment.pop('PSXRECOMP_HD_DUMP',None)
    environment['PSXRECOMP_HD_TEXTURE_ROOT'] = str(Path(texture_root) if texture_root else ROOT/'stock')
    with (ROOT/'evidence/runtime.stdout.log').open('wb') as stdout, (ROOT/'evidence/runtime.stderr.log').open('wb') as stderr:
        process = subprocess.Popen(arguments, cwd=str(PROJECT), env=environment,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    metadata={'pid':process.pid,'debug_port':PORT,'arguments':arguments,
              'scope':'owned isolated executable and writable state; texture sources are read-only; user cards are never mounted',
              'original_executable':str(executable_source),
              'copied_native_cache_source':str(cache_source) if cache_source.exists() else None,
              'hd_enabled':hd_enabled,'dumping':dumping,
              'bios_hle_override':environment.get('PSX_BIOS_HLE'),
              'hle_scheduler_override':environment.get('PSX_HLE_SCHEDULER'),
              'rewind_override':environment.get('PSX_REWIND'),
              'requested_rewind_depth':rewind_depth,
              'cards_enabled':cards_enabled,'card_scope':'isolated state directory; optional source is copied once, never mounted',
              'texture_root':environment['PSXRECOMP_HD_TEXTURE_ROOT'],
              'page_fallback':environment.get('PSXRECOMP_HD_PAGE_FALLBACK','0'),
              'decode_budget_mb':environment.get('PSXRECOMP_HD_DECODE_BUDGET_MB','256'),
              'cpu_authority':environment.get('PSXRECOMP_HD_CPU_AUTHORITY','0')}
    (ROOT/'evidence/session.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metadata,indent=2),flush=True)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Runtime exited with {process.returncode}; see isolated logs')
        try:
            print(json.dumps(command('ping')),flush=True)
            return
        except (OSError,ValueError):
            time.sleep(.25)
    raise RuntimeError('Debug endpoint not available within 30 seconds; see isolated logs')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['launch','status','shot','command'])
    parser.add_argument('value',nargs='?')
    args=parser.parse_args()
    if args.action=='launch':launch()
    elif args.action=='status':print(json.dumps(command('gpu_state'),indent=2))
    elif args.action=='shot':print(json.dumps(screenshot(args.value or 'current'),indent=2))
    else:
        request=json.loads(args.value)
        print(json.dumps(command(request.pop('cmd'),**request),indent=2))
