"""Compose a separate append-only admission candidate without changing the base pack."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT/'windows-x64/hd-textures/stage1-v1'
SUPPLEMENT = ROOT/'remaster-audit/dev-center-evidence/greif-native-admission-20261112'


def main():
    receipt = json.loads((SUPPLEMENT/'manifest.json').read_bytes())
    if receipt['missing_keys'] or receipt['recoverable_pairs'] != 60:
        raise ValueError('Expected the complete validated Greif supplement')
    target = SUPPLEMENT/'composed-pack'
    target.mkdir(exist_ok=False)
    replacements = target/'einhander-texture-replacements'
    replacements.mkdir()
    files = []
    for source in sorted((BASE/'einhander-texture-replacements').glob('*.png')):
        if source.is_symlink() or not source.is_file():
            raise ValueError('Base PNG must be a regular owned asset')
        output = replacements/source.name
        os.link(source, output)
        if not os.path.samefile(source, output):
            raise ValueError('Base hardlink identity verification failed')
        files.append(dict(name=source.name, origin='immutable base hardlink',
                          path=str(source), bytes=source.stat().st_size, same_file_verified=True))
    for entry in receipt['files']:
        source = Path(entry['png']).resolve()
        if not source.is_relative_to(SUPPLEMENT.resolve()):
            raise ValueError('Supplement PNG escaped its staging root')
        if hashlib.sha256(source.read_bytes()).hexdigest() != entry['png_sha256']:
            raise ValueError('Supplement PNG changed since validation')
        output = replacements/source.name
        if output.exists():
            raise ValueError('Supplement would replace a base asset')
        shutil.copy2(source, output)
        if hashlib.sha256(output.read_bytes()).hexdigest() != entry['png_sha256']:
            raise ValueError('Supplement copy verification failed')
        files.append(dict(name=source.name, origin='validated native-resolution admission proof',
                          path=str(source), sha256=entry['png_sha256']))
    if (BASE/'Hashes.ini').is_file():
        shutil.copy2(BASE/'Hashes.ini', target/'Hashes.ini')
    report = dict(at_utc=datetime.now(timezone.utc).isoformat(), candidate_root=str(target),
                  base_modified=False, installed=False, files=files, count=len(files),
                  base_files=sum(row['origin']=='immutable base hardlink' for row in files),
                  supplement_files=60,
                  scope='Replacement admission and temporary material diagnostics only; new pages are original-resolution proofs',
                  limitation='Never edit a hardlinked base PNG in place; replace candidate files atomically to keep the base immutable')
    (target/'composition.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key!='files'}, indent=2))


if __name__ == '__main__':
    main()
