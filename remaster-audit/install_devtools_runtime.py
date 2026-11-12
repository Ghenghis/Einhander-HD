"""Install the locally built runtime with content-addressed rollback copies.

This only copies verified files. It never starts or stops a game process.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'windows-x64'
EVIDENCE = ROOT / 'remaster-audit/dev-center-evidence'
BUILT = Path('C:/github/REMASTER_STAGING/full-remaster/devtools-build/Einhander_Recompiled.exe')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt_path = PROJECT / 'tools/material-runtime.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    built_sha = digest(BUILT)
    if receipt['sha256'] != built_sha:
        raise ValueError('Build receipt does not match the executable')
    history_path = EVIDENCE / 'runtime-installation.json'
    history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.is_file() else []
    backup_root = EVIDENCE / 'runtime-backups'
    backup_root.mkdir(exist_ok=True)
    for relative in ('Einhander_Recompiled.exe', 'build-release/Einhander_Recompiled.exe'):
        target = (PROJECT / relative).resolve()
        if not target.is_relative_to(PROJECT.resolve()):
            raise ValueError('Runtime target escaped its project')
        previous_sha = digest(target) if target.is_file() else None
        if previous_sha == built_sha:
            continue
        backup = backup_root / (previous_sha + '.exe') if previous_sha else None
        if backup:
            if not backup.exists():
                shutil.copy2(target, backup)
            if digest(backup) != previous_sha:
                raise ValueError('Rollback copy failed verification')
        temporary = target.with_name('.runtime-' + uuid.uuid4().hex + '.tmp')
        try:
            shutil.copy2(BUILT, temporary)
            if digest(temporary) != built_sha:
                raise ValueError('Runtime copy failed verification')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        history.append(dict(target=str(target), previous_sha256=previous_sha, backup=str(backup) if backup else None,
                            installed_sha256=built_sha, installed_at_utc=datetime.now(timezone.utc).isoformat(),
                            contract=receipt['contract'], research_contract='ein-research-v1'))
    history_path.write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    receipt.update(executable=str(PROJECT / 'build-release/Einhander_Recompiled.exe'), live_colors=True,
                   research_capture=dict(contract='ein-research-v1', read_only=True, sampled_draw_receipts=True,
                                         marked_ram_cpu_vram=True, full_replay=False),
                   renderer_source_sha256=digest(PROJECT / 'psxrecomp/runtime/src/gpu_gl_renderer.c'),
                   debug_source_sha256=digest(PROJECT / 'psxrecomp/runtime/src/debug_server.c'),
                   kernel_sha256=digest(PROJECT / 'psxrecomp/runtime/src/hd_skin_material.h'),
                   detail_kernel_sha256=digest(PROJECT / 'psxrecomp/runtime/src/hd_skin_detail.h'),
                   verification='Compiled, linked and installed with headless command/GPU checks; new gameplay validation pending')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(installed=True, sha256=built_sha, game_launched=False), indent=2))


if __name__ == '__main__':
    main()
