"""Build a real-runtime GL regression using the existing local build's objects."""
import argparse
import ctypes
import hashlib
import json
import os
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / 'windows-x64'
BUILD = PROJECT / 'build-ss8c'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--renderer-source', type=Path, default=PROJECT/'psxrecomp/runtime/src/gpu_gl_renderer.c')
parser.add_argument('--gpu-source', type=Path, default=PROJECT/'psxrecomp/runtime/src/gpu.c')
parser.add_argument('--hd-cache', action='store_true', help='Run the real-GL HD decode-eviction regression instead')
parser.add_argument('--native-edge', action='store_true', help='Run actual native-page right-edge admission/UV regression instead')
parser.add_argument('--output', type=Path, default=Path('C:/github/REMASTER_STAGING/renderer-validation/coherence/current'))
args = parser.parse_args()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)


def windows_args(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    values = parse(command, ctypes.byref(count))
    try:
        return [values[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(values)


def run(args, name, timeout=90, env=None):
    result = subprocess.run(args, cwd=BUILD, env=env, capture_output=True,
                            text=True, timeout=timeout)
    (OUT / (name + '.log')).write_text(result.stdout + result.stderr)
    print(name, 'exit', result.returncode, flush=True)
    if result.returncode:
        print((result.stdout + result.stderr)[-5000:])
    return result


lines = (BUILD / 'build.ninja').read_text().splitlines()
index = next(i for i, line in enumerate(lines) if line.startswith('build CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj:'))
block = lines[index + 1:index + 15]
fields = {s.strip().split(' = ', 1)[0]: s.split(' = ', 1)[1] for s in block if ' = ' in s}
compiler = Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
flags = windows_args('unused ' + fields['DEFINES'] + ' ' + fields['FLAGS'] + ' ' + fields['INCLUDES'])[1:]
flags = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix() + '/') for s in flags]
obj = OUT / 'coherence-main.obj'
test_source = Path(__file__).with_name('test_hd_gpu_cache.cpp' if args.hd_cache or args.native_edge else 'test_vram_coherence.cpp').resolve()
compiled = run([str(compiler), *flags, '-c', str(test_source), '-o', str(obj)], 'compile')
if compiled.returncode:
    raise SystemExit(compiled.returncode)
renderer_command = Path('C:/github/REMASTER_STAGING/stage01_city/evidence/renderer-build-command.txt').read_text()
renderer_args = windows_args(renderer_command)
if Path(renderer_args[0]).name.lower() == 'ccache.exe':
    renderer_args = renderer_args[1:]
renderer_args = [s.replace('D:/Games/Einhander/windows-x64/', PROJECT.as_posix() + '/') for s in renderer_args]
renderer_obj = OUT / 'gpu_gl_renderer.c.obj'
renderer_args[renderer_args.index('-o') + 1] = str(renderer_obj)
renderer_args[renderer_args.index('-MF') + 1] = str(OUT / 'gpu_gl_renderer.c.obj.d')
renderer_args[-1] = str(args.renderer_source.resolve())
if args.hd_cache or args.native_edge:
    wrapper = OUT/'renderer-test.c'
    wrapper.write_text('#define HD_RENDERER_SOURCE "'+args.renderer_source.resolve().as_posix()+'"\n#include "'+Path(__file__).with_name('test_hd_gpu_cache.c').resolve().as_posix()+'"\n')
    renderer_args[-1] = str(wrapper)
renderer_args.insert(-2, '-I' + str(PROJECT/'psxrecomp/runtime/src'))
compiled_renderer = run(renderer_args, 'compile-renderer')
if compiled_renderer.returncode:
    raise SystemExit(compiled_renderer.returncode)
gpu_args = list(renderer_args)
gpu_obj = OUT / 'gpu.c.obj'
gpu_args[gpu_args.index('-o') + 1] = str(gpu_obj)
gpu_args[gpu_args.index('-MF') + 1] = str(OUT / 'gpu.c.obj.d')
gpu_args[-1] = str(args.gpu_source.resolve())
compiled_gpu = run(gpu_args, 'compile-gpu')
if compiled_gpu.returncode:
    raise SystemExit(compiled_gpu.returncode)
response = Path('C:/github/REMASTER_STAGING/stage01_city/build/stage1-link.rsp').read_text()
response = response.replace('"CMakeFiles/psx-runtime.dir/psxrecomp/runtime/src/main.cpp.obj"', '"' + obj.as_posix() + '"')
response = response.replace('"C:/github/REMASTER_STAGING/stage01_city/build/gpu_gl_renderer.c.obj"', '"' + renderer_obj.as_posix() + '"')
response = response.replace('"C:/github/REMASTER_STAGING/stage01_city/build/gpu.c.obj"', '"' + gpu_obj.as_posix() + '"')
assert obj.as_posix() in response
assert renderer_obj.as_posix() in response
assert gpu_obj.as_posix() in response
rsp = OUT / 'link.rsp'
rsp.write_text(response)
exe = OUT / 'coherence.exe'
linked = run([str(compiler), '-O3', '-static', '-Wl,--stack,67108864', '@' + str(rsp), '-o', str(exe)], 'link')
if linked.returncode:
    raise SystemExit(linked.returncode)
reports = []
test_args=[]
if args.native_edge:
    import struct,zlib
    from PIL import Image
    pack=OUT/'pack';pack.mkdir(exist_ok=True)
    for width in (64,128,192,256):
        raw=struct.pack('<H',0x001f)*(width*256)
        key=zlib.crc32(raw)
        rgba=bytes(component for y in range(256) for x in range(width)
                   for component in ((x%31+1)*8,(y%31+1)*8,((x+y)%31+1)*8,127))
        Image.frombytes('RGBA',(width,256),rgba).save(pack/(f'{key:08X}-00000000.png'))
    for mode in ('0','1'):(pack/('dump-'+mode)).mkdir(exist_ok=True)
    test_args=[str(pack),'native-edge']
elif args.hd_cache:
    import struct,zlib
    from PIL import Image
    pack=OUT/'pack';pack.mkdir(exist_ok=True)
    key=zlib.crc32(struct.pack('<4H',*([0x801f]*4)))
    Image.new('RGBA',(8,8),(17,34,51,255)).save(pack/(f'{key:08X}-00000000.png'))
    test_args=[str(pack)]
for mode in ('0', '1'):
    env = dict(os.environ, PSXRECOMP_HD_CPU_AUTHORITY=mode)
    if args.native_edge:
        env['PSXRECOMP_HD_PAGE_FALLBACK']='1'
        env['PSXRECOMP_HD_SOURCE_SIDECARS']='1'
    result = run([str(exe),*test_args], 'cpu-authority-' + mode, timeout=30, env=env)
    print(result.stdout, flush=True)
    reports.append({'cpu_authority': mode, 'exit': result.returncode, 'output': result.stdout})
dump_checks=[]
if args.native_edge and not any(row['exit'] for row in reports):
    from build_three_asset_proof import verify_stock
    for mode in ('0','1'):
        for width in (64,128,192,256):
            key=f'{zlib.crc32(struct.pack("<H",0x001f)*(width*256)):08X}-00000000'
            directory=pack/('dump-'+mode)
            metadata,raw,palette=verify_stock(directory,key)
            assert metadata['width_words']==width and metadata['height']==256 and metadata['depth']==2
            assert len(raw)==width*256*2 and not palette
            assert metadata['fragments']==[[704 if width==256 else 1024-width,256,width,256,0,0]]
            with Image.open(directory/(key+'.png')) as image:assert image.size==(width,256)
            dump_checks.append({'cpu_authority':mode,'key':key,'native_size':[width,256],
                                'source_crc_decode_and_metadata':'PASS'})
(OUT / 'results.json').write_text(json.dumps({'tests':reports,
    'native_edge_source_dump_checks':dump_checks,
    'source':str(args.renderer_source.resolve()),
    'source_sha256':hashlib.sha256(args.renderer_source.read_bytes()).hexdigest(),
    'gpu_source':str(args.gpu_source.resolve()),
    'gpu_source_sha256':hashlib.sha256(args.gpu_source.read_bytes()).hexdigest(),
    'harness_sha256':hashlib.sha256(test_source.read_bytes()).hexdigest()}, indent=2) + '\n')
raise SystemExit(any(row['exit'] for row in reports))
