"""Compile actual executed stage code into a fresh private cache, offline.

No installed cache, game, native instruction, or admission guard is modified.
Inputs and generated game-derived bytes remain in ignored evidence.
"""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
HOT=[0x26714,0xD8094,0xD266C,0x3A998,0x96020,0xAE52C,0x91790,0x91AF8,0x393D8]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def ref(path):return dict(path=Path(path).relative_to(ROOT).as_posix(),sha256=sha(path))


def stage_qualified_cache(report,qualification):
    """Copy only observed-qualified entries into an unlaunched private runtime."""
    qualification=Path(qualification).resolve();q=read(qualification)
    assert qualification.is_relative_to(E.resolve())
    assert q['correctness_accepted'] and not q['errors'] and q['owned_process_exit']==0 and q['close']['port_closed']
    source_run=qualification.parent.parent;world=read(source_run/'world-flypast-proof.json')
    assert not world['errors'] and world['owned_process_exit']==0 and world['close']['port_closed']
    from stage1_code_qualification import qualification_errors
    problems=qualification_errors(q,world)
    if problems:raise ValueError('Native qualification rejected: '+'; '.join(problems))
    source_config=read(source_run/'candidate.json')
    assert sha(source_run/'candidate.json')==world['candidate']['sha256']
    spec=report['launches']['candidate'];directory=Path(report['evidence']).resolve()
    assert directory.is_relative_to(E.resolve()) and directory!=E.resolve()
    assert not (directory/'launch-candidate.json').exists()
    assert spec['user_cards_mounted'] is False
    assert spec['executable_sha256']==source_config['launches']['candidate']['executable_sha256']
    allowed={int(pc,16)&0x1FFFFFFF for pc in q['hot_entries_with_32_clean_diffs']}
    entries=set();files=source_config['code_cache_validation']['files'];copies=[]
    from launch_ui_candidate import copy_verified
    for item in files:
        source=Path(item['path']);source=source if source.is_absolute() else ROOT/source
        source=source.resolve();assert source.is_relative_to((source_run/'runtime/cache').resolve())
        assert sha(source)==item['sha256'] and source.suffix in ('.dll','.ranges')
        if source.suffix=='.ranges':
            current={int(line.split()[1],16)&0x1FFFFFFF for line in source.read_text().splitlines() if line.startswith('F ')}
            assert current and current<=allowed;entries.update(current)
        destination=directory/'runtime/cache'/source.relative_to((source_run/'runtime/cache').resolve())
        destination.parent.mkdir(parents=True,exist_ok=True);copy_verified(source,destination);copies.append(ref(destination))
    assert entries==allowed and len(copies)==2*len(allowed)
    report['qualified_code_cache']=dict(qualification=ref(qualification),entries=[f'0x{x:08X}' for x in sorted(allowed)],files=copies,
        runtime_sha256=spec['executable_sha256'],guard_changed=False,production_installed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-batch',required=True)
    parser.add_argument('--output-batch',required=True)
    args=parser.parse_args()
    if not all(re.fullmatch('[a-zA-Z0-9_-]+',x) for x in [args.capture_batch,args.output_batch]):raise ValueError('Single directory names required')
    run=E/args.capture_batch/'hd-on_rewind-off';proof_path=run/'loaded-code/code-capture-proof.json';proof=read(proof_path)
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    sample=next(x for x in proof['samples'] if x['label']=='city-plus-095')
    source=ROOT/sample['overlay_capture']['path'] if not Path(sample['overlay_capture']['path']).is_absolute() else Path(sample['overlay_capture']['path'])
    raw_path=Path(sample['boot_text']['path'])
    if not raw_path.is_absolute():raw_path=ROOT/raw_path
    assert sha(source)==sample['overlay_capture']['sha256'] and sha(raw_path)==sample['boot_text']['sha256']
    raw=raw_path.read_bytes();assert len(raw)==0x22000
    captures=read(source);selected=[];evidence=[];compared=0
    for cap in captures:
        lo=int(cap['load_addr'],16)&0x1FFFFFFF;data=base64.b64decode(cap['bytes_b64'],validate=True)
        assert len(data)==cap['size']
        if 0x10000<=lo<0x32000:
            size=min(len(data),0x32000-lo);assert data[:size]==raw[lo-0x10000:lo-0x10000+size];compared+=size
        wanted=[pc for pc in HOT if lo<=pc<lo+len(data)]
        if not wanted:continue
        entries={int(x,16)&0x1FFFFFFF for x in cap['dispatch_entry_pcs']}
        executed={int(x,16)&0x1FFFFFFF for x in cap['executed_pcs']}
        assert all(pc in entries and pc in executed for pc in wanted)
        selected.append(cap);evidence.extend(dict(pc=f'0x{pc:08X}',region=cap['load_addr'],dispatch_observed=True,instruction_executed=True) for pc in wanted)
    assert compared==131076 and {int(x['pc'],16) for x in evidence}==set(HOT)
    out=E/args.output_batch;out.mkdir(exist_ok=False)
    filtered=out/'executed-captures-private.json';filtered.write_text(json.dumps(selected,indent=2)+'\n')
    config=read(run/'candidate.json');runtime=Path(config['launches']['candidate']['arguments'][0])
    assert sha(runtime)==config['launches']['candidate']['executable_sha256']
    objdump=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/llvm-objdump.exe')
    mode=subprocess.run([str(objdump),'--disassemble-symbols=psx_cps_mark_game_ctor',str(runtime)],capture_output=True,text=True,timeout=15)
    assert mode.returncode==0 and 'g_psx_cps_mode' in mode.stdout and re.search(r'movl\s+\$0x1',mode.stdout)
    (out/'actual-executable-cps-proof.txt').write_text(mode.stdout)
    framework=ROOT/'windows-x64/psxrecomp'
    command=['python',str(framework/'tools/compile_overlays.py'),'--captures',str(filtered),
        '--game-toml',str(ROOT/'windows-x64/game.toml'),'--recompiler',str(framework/'recompiler/build/psxrecomp-game.exe'),
        '--runtime-include',str(framework/'runtime/include'),'--out-dir',str(out/'cache'),
        '--compiler','gcc','--cps','--jobs','2']
    # Each requested interior has BOTH recorded dispatch and execution evidence
    # above. This existing option requests isolated, exact-byte guarded aliases;
    # it does not invent callable walk roots or weaken loader admission.
    for pc in HOT:command.extend(['--force-interior',f'0x{pc|0x80000000:08X}'])
    env=os.environ.copy()
    for key in ['PSX_OVERLAY_CACHE_DIR','PSX_OVERLAY_CAPTURES','PSX_OVERLAY_FLAVOR']:env.pop(key,None)
    receipt=dict(started_at_utc=datetime.now(timezone.utc).isoformat(),capture_proof=ref(proof_path),source=ref(source),filtered=ref(filtered),
        raw_code_bytes_independently_compared=compared,hot_pc_evidence=evidence,runtime=ref(runtime),cps_mode=1,
        compiler_command=command,production_installed=False,guard_changed=False,
        scope='Fresh private cache is the staging build; not a production install or a performance result')
    for key,path in [('builder',Path(__file__)),('compiler_driver',framework/'tools/compile_overlays.py'),
                     ('recompiler',framework/'recompiler/build/psxrecomp-game.exe'),('game_config',ROOT/'windows-x64/game.toml')]:receipt[key]=ref(path)
    def save():(out/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    # One fresh staging compilation already exercises audits and compiler errors;
    # repeating it with --check would rebuild the same private artifacts twice.
    with (out/'compile.log').open('w') as log:
        try:result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            receipt['error']='Offline compilation exceeded its bound';save();raise
    functions=set();artifacts=[]
    for manifest in sorted((out/'cache').rglob('*.ranges')):
        dll=manifest.with_suffix('.dll')
        if not dll.is_file():continue
        artifacts.append(dict(manifest=ref(manifest),dll=ref(dll)))
        for line in manifest.read_text().splitlines():
            fields=line.split()
            if len(fields)>=3 and fields[0]=='F':functions.add(int(fields[1],16)&0x1FFFFFFF)
    receipt.update(exit=result.returncode,ended_at_utc=datetime.now(timezone.utc).isoformat(),artifacts=artifacts,
        hot_pcs_exported=[f'0x{pc:08X}' for pc in HOT if pc in functions],
        hot_pcs_missing=[f'0x{pc:08X}' for pc in HOT if pc not in functions])
    receipt['required_coverage_complete']=not receipt['hot_pcs_missing'];save()
    print(json.dumps(dict(output=str(out),exit=result.returncode,regions=len(selected),hot_pcs=len(evidence))),flush=True)
    if result.returncode:raise SystemExit(result.returncode)
    if receipt['hot_pcs_missing']:raise RuntimeError('Compiler returned success but required hot entries are missing; preserve this incomplete staging cache')


if __name__=='__main__':main()
