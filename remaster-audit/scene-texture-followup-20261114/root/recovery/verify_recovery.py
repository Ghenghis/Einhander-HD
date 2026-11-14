"""Read-only input audit; writes a fresh receipt without repairing failed evidence."""
from pathlib import Path
import datetime
import hashlib
import io
import json
import os
import subprocess
import psutil

ROOT = Path('C:/github/Einhander')
DELIVERY = Path('C:/github/Einhander-wt/display-history-opt-in')
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'remaster-audit/claude-backlog/class-mip/renderer-v61-classmip'
FAILED = BASE / 'frozen/renderer-v61-classmip-v5'
PRIOR = ROOT / 'remaster-audit/runtime-review/gpu-texture-remix-20261114/post-restart-audit.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=digest(data), all_zero=bool(data) and not any(data), nul_bytes=data.count(b'\0'))


def counterpart(rel):
    parts = rel.parts
    if parts[0] in ('src', 'docs'):
        return BASE.joinpath(*parts[1:])
    if parts[0] == 'host-run':
        return BASE.joinpath('runs', *parts[1:])
    if parts[0] in ('selftest', 'evidence'):
        return BASE / rel
    return None


def main():
    proc = psutil.Process()
    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    proc.cpu_affinity(proc.cpu_affinity()[-1:])
    prior = json.loads(PRIOR.read_text())
    damaged = []
    for row in prior['nul_files']:
        path = Path(row['path'])
        rel = path.relative_to(FAILED)
        current = pin(path)
        source = counterpart(rel)
        candidate = dict(path=str(source), exists=source.is_file()) if source else None
        if candidate and candidate['exists']:
            candidate.update(pin(source))
            if source.suffix == '.json':
                try:
                    json.loads(source.read_text(encoding='utf-8-sig'))
                    candidate['json_valid'] = True
                except (ValueError, UnicodeError):
                    candidate['json_valid'] = False
        damaged.append(dict(path=str(path), unchanged=current['sha256'] == row['sha256'],
                            current=current, recovery_candidate=candidate))

    source_run = BASE / 'runs/20261114T124104Z'
    report_path = source_run / 'result.json'
    report = json.loads(report_path.read_text())
    input_rows = []
    for name, expected in report['inputs'].items():
        paths = [source_run / name, BASE / name, BASE.parent / 'proto-v2b' / name]
        copies = [dict(path=str(p), **pin(p)) for p in paths if p.is_file()]
        input_rows.append(dict(name=name, expected=expected, copies=copies,
                               matching_copies=sum(x['sha256'] == expected for x in copies)))

    expected = {}
    for name in ('gpu-integration-20261114', 'gpu-shader-followup-20261114'):
        manifest = json.loads((DELIVERY / 'remaster-audit' / name / 'SHA256.json').read_text())
        expected.update({f'remaster-audit/{name}/{p}': h for p, h in manifest['files'].items()})
    for line in (DELIVERY / 'remaster-audit/cpu-hour-integration-20261114/SHA256SUMS.txt').read_text().splitlines():
        h, p = line.split('  ', 1)
        expected['remaster-audit/cpu-hour-integration-20261114/' + p] = h
    raw = subprocess.run(['git', 'cat-file', '--batch'], cwd=DELIVERY,
                         input=''.join('HEAD:' + p + '\n' for p in expected).encode(),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20).stdout
    stream = io.BytesIO(raw)
    errors = []
    for p, h in expected.items():
        header = stream.readline().decode().split()
        if len(header) != 3 or header[1] != 'blob':
            errors.append(dict(path=p, error='missing git blob'))
            continue
        data = stream.read(int(header[2]))
        assert stream.read(1) == b'\n'
        if digest(data) != h:
            errors.append(dict(path=p, error='committed hash mismatch'))
        for label, root in [('delivery', DELIVERY), ('root', ROOT)]:
            target = root / p
            if not target.is_file() or digest(target.read_bytes()) != h:
                errors.append(dict(path=p, error=label + ' working file mismatch'))

    candidates = [x['recovery_candidate'] for x in damaged if x['recovery_candidate']]
    summary = dict(damaged_files=len(damaged), failed_evidence_unchanged=all(x['unchanged'] for x in damaged),
                   still_all_zero=sum(x['current']['all_zero'] for x in damaged),
                   candidates_found=sum(x['exists'] for x in candidates),
                   candidates_with_no_nul=sum(x['exists'] and x['nul_bytes'] == 0 for x in candidates),
                   recorded_run_inputs=len(input_rows),
                   run_inputs_with_matching_copy=sum(x['matching_copies'] > 0 for x in input_rows),
                   published_pins_verified=len(expected), publication_errors=errors)
    now = datetime.datetime.now(datetime.timezone.utc)
    receipt = dict(at_utc=now.isoformat(), boot_utc=datetime.datetime.fromtimestamp(psutil.boot_time(), datetime.timezone.utc).isoformat(),
                   prior_audit=dict(path=str(PRIOR), sha256=digest(PRIOR.read_bytes())),
                   source_run=dict(path=str(report_path), sha256=digest(report_path.read_bytes()),
                                   recorded_verdict=report.get('verdict'), checks=report.get('checks')),
                   summary=summary, damaged_files=damaged, recorded_inputs=input_rows,
                   scope='Known 90 damaged files, candidate counterparts, recorded v5 run inputs and three published manifests. Not a whole-drive audit.',
                   limitations=['Candidate readability alone does not establish original identity.',
                                'Original v5 READY/manifest remain untrusted. A new replay and freeze are required.',
                                'This audit executes no gameplay/GPU test and accepts no artwork or audio.'],
                   files_repaired=False, gpu_executed=False, cpu_tests_replayed=False)
    out = HERE / now.strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(exist_ok=False)
    target = out / 'integrity.json'
    with target.open('x', encoding='utf-8') as f:
        f.write(json.dumps(receipt, indent=2) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(dict(path=str(target), sha256=digest(target.read_bytes()), **summary)))
    if errors or not summary['failed_evidence_unchanged'] or summary['run_inputs_with_matching_copy'] != len(input_rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
