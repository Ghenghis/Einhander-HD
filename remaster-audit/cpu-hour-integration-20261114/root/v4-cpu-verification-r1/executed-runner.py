"""Independent bounded CPU replay of Claude's frozen v4. Never opens GL."""
from pathlib import Path
import datetime, hashlib, json, os, psutil, shutil, subprocess

n = Path(__file__).resolve().parent
r = n.parents[2]
f = r/'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip/frozen/renderer-v61-classmip-v4'
out = n/'v4-cpu-verification-r1'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity(me.cpu_affinity()[-1:])
marker = r/'remaster-audit/comfy-authoring/GPU-RESERVED'
hold = marker.read_bytes()
assert json.loads(hold)['owner'] == 'user-external-project'
assert sha(f/'READY.json') == '93a97669e6d9cf5fbd75536d5261efbe5855f1299bb91683badea4f7a395299e'
assert sha(f/'SHA256SUMS.txt') == 'f60c41b365e7cc6a49cbf11b4ac4df16e87e0183e0784df3b3386fd9cecc689f'
pins = 0
for line in (f/'SHA256SUMS.txt').read_text().splitlines():
    h, name = line.split('  ', 1)
    p = (f/name).resolve()
    assert p.is_relative_to(f.resolve()) and sha(p) == h, name
    pins += 1
rd = f/'host-run/20261114T114326Z'
result = json.loads((rd/'result.json').read_text())
first = next(x for x in result['steps']['4-sidecars']['sidecars'] if x['in_index'])
for p in [f/'src/test_hd_class_mips.c', f/'src/hd_class_mips.inc', rd/'glue/glue_harness.c', rd/'glue/glue.c', rd/'inputs/class_mip.c', rd/'inputs/class_mip.h']:
    shutil.copy2(p, out/p.name)
cc = 'C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe'
rows = []
def run(label, args, env=None):
    x = subprocess.run(args, cwd=out, capture_output=True, text=True, env=env, timeout=45, creationflags=0x4000)
    (out/(label+'.log')).write_text(x.stdout+x.stderr)
    rows.append(dict(label=label, arguments=args, exit=x.returncode, stdout_tail=x.stdout.splitlines()[-8:]))
    assert x.returncode == 0, label

flags = [cc, '-std=c11', '-O1', '-Wall', '-Wextra', '-Wno-unused-function', '-I'+str(out)]
run('compile-fixture', flags+[str(out/'test_hd_class_mips.c'), str(out/'class_mip.c'), '-o', str(out/'fixture.exe')])
run('fixture', [str(out/'fixture.exe')])
run('compile-glue-stubs', flags+[str(out/'glue_harness.c'), '-o', str(out/'glue.exe')])
nw, nh = first['native']
s = first['scale']
base = [str(rd/'glue/rgba.bin'), str(nw*s), str(nh*s), *first['key'].split('-'), str(nw), str(nh), '2', str(nw), str(first['levels']), '8', '1']
env0 = {k:v for k,v in os.environ.items() if not k.startswith(('PSXRECOMP_HD_CLASS_MIPS', 'PSXRECOMP_HD_RGB_EDGES'))}
sd = dict(PSXRECOMP_HD_CLASS_MIPS_DIR=str(rd/'sidecars'))
cases = [('off', base, env0), ('badenv', base, dict(env0, **sd, PSXRECOMP_HD_CLASS_MIPS='true', PSXRECOMP_HD_RGB_EDGES='0')),
         ('on', base, dict(env0, **sd, PSXRECOMP_HD_CLASS_MIPS='1', PSXRECOMP_HD_RGB_EDGES='1')),
         ('levels', base, dict(env0, **sd, PSXRECOMP_HD_CLASS_MIPS='1')),
         ('rgb', base, dict(env0, **sd, PSXRECOMP_HD_RGB_EDGES='1'))]
# Read opaque control metadata from its binary header, not assumptions about page sizes.
blob = (rd/'sidecars-opaque-control/95A3BCF8-60245B3A.hdcm').read_bytes()
import struct
nw2, nh2, w2, h2, s2, levels2 = struct.unpack_from('<6I', blob, 16)
opaque = [str(rd/'glue/rgba-opaque.bin'), str(w2), str(h2), '95A3BCF8', '60245B3A', str(nw2), str(nh2), '2', str(nw2), str(levels2), '1', '0']
cases.append(('rgb', opaque, dict(env0, PSXRECOMP_HD_RGB_EDGES='1', PSXRECOMP_HD_CLASS_MIPS_DIR=str(rd/'sidecars-opaque-control'))))
for i, (mode, args, env) in enumerate(cases):
    run('glue-'+str(i)+'-'+mode, [str(out/'glue.exe'), mode]+args, env)
assert marker.read_bytes() == hold
receipt = dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), frozen_files_verified=pins,
               ready_sha256=sha(f/'READY.json'), sums_sha256=sha(f/'SHA256SUMS.txt'), commands=rows,
               compiler_sha256=sha(cc), gpu_executed=False, gl_stubs_only=True, user_gpu_hold_unchanged=True,
               cpu_affinity=me.cpu_affinity(), below_normal=True, mutants_replayed=False, passed=True)
(out/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
