"""Read small pinned receipts/source only; never load images, DLLs or a GPU."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import psutil

R = Path('C:/github/Einhander')
N = Path(__file__).resolve().parent
S = R / '.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/ui-v5-replay'
me = psutil.Process()
me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
me.cpu_affinity([11])
checked = []


def check_file(path, expected=None):
    path = Path(path)
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if expected is not None and got != expected:
        raise RuntimeError(f'pin changed: {path}')
    checked.append(dict(path=str(path), sha256=got, bytes=len(raw)))
    return raw


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


rc = json.loads(check_file(S / 'run-20261114T190638Z.rc.json',
    'abe69cbfdd8059146bcf6d43e5e972ac752bd20447af0b8038306f54d95a67b1'))
res = json.loads(check_file(S / 'run-20261114T190638Z/result.json',
    '82a2c5a7e9da0a41a5e350b81a6aad659c703d4490a952978baedb998df141ac'))
check_file(S / 'replay_v5_native_class_r3.py',
    '4523790abbf81fa6c4117bca72304f41812f4edfda6bc5d9a5e2dcd699568683')
check_file(S / 'preflight-table-v1.json',
    '93a6315f4ac837b77bb35b315a16d2a34c2b3fe05a23c40684e2c219b2cc374c')
require(rc['rc'] == rc['child_exit_code'] == rc['wrapper_exit'] == 0, 'replay exits')
require(rc['tree_absent'] and rc['job_empty'] and rc['child_absent']
    and rc['job']['active'] == 0 and not rc['descendants_left'], 'replay cleanup')
require(rc['affinity'] == [15] and rc['priority'] == 16384
    and rc['job_assigned_before_resume'], 'replay envelope')
require(res['members'] == res['ok'] == res['primary_pass_replayed']
    == res['s2_strict_pass_replayed'] == len(res['rows']) == 118, 'replay counts')
require(not res['failures'] and not any(res['stopped_at'].values())
    and not res['pins']['mismatch'] and not res['pins']['version_mismatch'], 'replay failures')
for row in res['rows']:
    require(row['ok'] and not row['problems'] and row['stopped_at'] is None, 'member failure')
    for field in ('r5_fringe_px', 's2_viol_px', 'conn_viol_px', 'nonclass_px'):
        require(row['audit'][field] == 0, f'nonzero {field}')
    require(row['audit']['primary_pass'] and row['audit']['s2_strict_pass'], 'member audit')
# Replay already hashed/decompressed/audited all images. Do not repeat that heavy work.
# Only current source/code/summary/table pins are read here, including the small frozen DLL as bytes.
for path, expected in res['pins']['pins'].items():
    check_file(path, expected)

staging = json.loads(check_file(N / 'v68-private-staging-r2/result.json'))
staging_rc = json.loads(check_file(N / 'v68-private-staging-r2/rc.json'))
require(staging['guard_receipt'] == staging_rc, 'staging embedded receipt differs')
require(staging['outer_exit'] == staging_rc['wrapper_exit']
    == staging_rc['child_exit_code'] == 0 and staging_rc['tree_absent'], 'staging execution')
require(not staging['game_run'] and not staging['gpu_run'] and not staging['installed'], 'staging scope')
readback = json.loads(check_file(N / 'v68-staged-material-readback-r1/result.json',
    '77b3254e14ad1626d994b33bb730d3ec90e3fc2300d56785e48a7abe20af3689'))
require(readback['passed'] and not readback['game_run'] and not readback['gpu_run'], 'readback scope')
e = R / 'remaster-audit/dev-center-evidence/stage1-completion-20261112/v68-unassisted-r1/hd-on_rewind-off'
candidate = json.loads(check_file(e / 'candidate.json', readback['candidate_sha256']))
settings = Path(candidate['launches']['candidate']['arguments'][0]).parent / 'settings.toml'
require(settings.resolve().is_relative_to((e / 'runtime').resolve()), 'settings outside private runtime')
check_file(settings, readback['settings_sha256'])
check_file(e / 'state/card1.mcd', readback['card1_sha256'])
skin_path = R / 'remaster-audit/parallel-stages-20261114/s23/runs/skin-map-20261114T190643Z/skin-visibility-map.json'
skin = json.loads(check_file(skin_path,
    '75ec2f80e75a35e85987821e92089a5b201b61e025bba2be5cb4c7540d54a569'))
skin_base = R / 'remaster-audit/parallel-stages-20261114/s23'
for path, expected in skin['inputs'].items():
    p = Path(path)
    if not p.is_absolute():
        p = skin_base / p
    check_file(p, expected)

out = N / 'cpu-texture-independent-readback-r1'
out.mkdir(exist_ok=False)
data = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), passed=True,
    files_checked=checked, native_replay_members=118, native_replay_seconds=rc['elapsed_s'],
    replay_full_algorithm_repeated_by_root=False, original_replay_hashes_and_results_verified=True,
    images_decoded_by_root=0, staging_prepared=True, staging_elapsed_s=staging_rc['elapsed_s'],
    skin_map_source_pins_verified=True, art_accepted=False, game_run=False, gpu_run=False,
    installed=False, live_qualified=False)
with (out / 'result.json').open('x', encoding='utf-8') as stream:
    json.dump(data, stream, indent=2)
    stream.write('\n')
    stream.flush()
    os.fsync(stream.fileno())
print(json.dumps({k:v for k,v in data.items() if k != 'files_checked'}))
