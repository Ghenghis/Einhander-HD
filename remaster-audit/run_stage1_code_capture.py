"""Capture actual replacement code privately; this is not a pacing benchmark.

Uses the existing owned-run cleanup and verified native menu gates. Reads RAM
and existing execution counters; never modifies guest instructions or guards.
Raw game bytes remain in ignored evidence, not public reports or GitHub.
"""
import argparse
import json
from pathlib import Path
import time
from types import SimpleNamespace
import run_stage1_world_flypast as world
from build_stage1_code_cache import HOT
from stage1_code_qualification import qualification_errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True)
    parser.add_argument('--cache-build',type=Path,help='Validate this private compiled cache with native/interpreter shadow comparisons')
    parser.add_argument('--focus-pc',type=lambda s:int(s,0),help='Validate one recorded hot entry using only its isolated orphan artifact')
    args=parser.parse_args()
    if args.focus_pc is not None and (not args.cache_build or args.focus_pc not in HOT):raise ValueError('Focus must be one recorded hot entry from a cache build')
    requested=HOT if args.focus_pc is None else [args.focus_pc]
    if not __import__('re').fullmatch('[a-zA-Z0-9_-]+',args.batch):raise ValueError('One batch directory required')
    directory=world.pacing.ROOT/args.batch/'hd-on_rewind-off'
    report=world.pacing.base.read(directory/'candidate.json')
    if (directory/'launch-candidate.json').exists():raise ValueError('Fresh prepared run required')
    if not report['visual_profile']['telemetry_only']:raise ValueError('Use a prepared telemetry-only candidate')
    if report['pacing_profile']['rewind_enabled']:raise ValueError('Code capture requires no rewind activity')
    if report['launches']['candidate']['environment_overrides'].get('PSX_OVERLAY_AUTOCOMPILE_OFF')!='1':
        raise ValueError('Capture first; compile only after the game closes')
    if args.cache_build:
        build=world.pacing.base.read(args.cache_build)
        assert build['exit']==0 and build['required_coverage_complete'] and not build['hot_pcs_missing']
        cache=args.cache_build.resolve().parent/'cache';destination=directory/'runtime/cache';copies=[]
        for artifact in build['artifacts']:
            manifest=Path(__file__).resolve().parents[1]/artifact['manifest']['path']
            text=manifest.read_text()
            entries={int(line.split()[1],16)&0x1FFFFFFF for line in text.splitlines() if line.startswith('F ')}
            if args.focus_pc is not None and (args.focus_pc not in entries or '# psxrecomp overlay provenance orphan-v1' not in text):continue
            for kind in ['manifest','dll']:
                # Builder paths are repository-relative; resolve against the
                # same explicit root as the build helper, never the shell cwd.
                source=Path(__file__).resolve().parents[1]/artifact[kind]['path']
                assert world.ui.sha(source)==artifact[kind]['sha256']
                target=destination/source.relative_to(cache)
                target.parent.mkdir(parents=True,exist_ok=True);world.ui.copy_verified(source,target)
                copies.append(world.pacing.base.ref(target))
        if not copies:raise ValueError('No exact isolated artifact for the requested entry')
        report['code_cache_validation']=dict(build=world.pacing.base.ref(args.cache_build.resolve()),files=copies,
            shadow_diff=True,pacing_acceptance=False,guard_changed=False)
        report['launches']['candidate']['environment_overrides']['PSX_OVERLAY_DIFF']='1'
        report['launches']['candidate']['environment_overrides']['PSX_OVERLAY_DIFF_ADDR']=f'0x{args.focus_pc:08X}' if args.focus_pc is not None else '0'
        world.pacing.base.write(directory/'candidate.json',report)
    output=directory/'loaded-code';output.mkdir(exist_ok=False)
    world.ui.copy_verified(Path(__file__),output/'executed-code-capture.py')
    notes=dict(kind='Private runtime-code acquisition; observer load prevents pacing acceptance',
        ram_reads_only=True,instruction_writes=False,guard_changed=False,states_loaded=False,
        samples=[],errors=[],requested_entries=[f'0x{pc:08X}' for pc in requested],started_at_utc=world.ui.stamp())
    original_request=world.probe.request;original_route=world.enter_city;original_close=world.close
    started=None;pending=[5,95];title_captured=False

    def save():world.pacing.base.write(output/'code-capture-proof.json',notes)

    def snapshot(label,flush=False):
        before=original_request(report,'get_registers')
        data=original_request(report,'read_ram',addr='0x80010000',len=0x22000)
        raw=bytes.fromhex(data['hex']);assert len(raw)==0x22000 and data['len']==len(raw)
        path=output/(label+'-boot-text.bin');path.write_bytes(raw)
        entry=dict(label=label,at_utc=world.ui.stamp(),registers_before=before,
            registers_after=original_request(report,'get_registers'),boot_text=world.pacing.base.ref(path),
            address='0x80010000',length=len(raw),dirty_ram_stats=original_request(report,'dirty_ram_stats'),
            overlay_loader_status=original_request(report,'overlay_loader_status'))
        if args.cache_build:
            entry['shadow']=original_request(report,'overlay_shadow_dump')
            entry['shadow_detail']=original_request(report,'overlay_shadow_detail')
            entry['hot_candidates']={f'0x{pc:08X}':original_request(report,'overlay_candidates',pc=f'0x{pc|0x80000000:08X}') for pc in requested}
            if args.focus_pc is not None and not notes.get('focused_diff_stopped'):
                rows=entry['hot_candidates'][f'0x{args.focus_pc:08X}']['candidates']
                if entry['shadow']['shadow']['divergences']==0 and any(c['match'] and c['diff_passes']>=32 and not c['device_touch'] for c in rows):
                    notes['focused_diff_stopped']=dict(label=label,reply=original_request(report,'overlay_diff_off'),minimum_clean_calls=32)
        if flush:
            entry['dump_reply']=original_request(report,'overlay_capture_dump')
            source=directory/'runtime/overlay_captures.json'
            destination=output/(label+'-overlay-captures.json')
            if source.is_file():
                world.ui.copy_verified(source,destination);entry['overlay_capture']=world.pacing.base.ref(destination)
        notes['samples'].append(entry);save()
        world.emit(dict(code_sample=label,frame=entry['registers_after'].get('frame'),bytes=len(raw)))

    def route(report,**kwargs):
        nonlocal started,title_captured
        def debug(command,**fields):
            nonlocal title_captured
            # The helper sends its first confirmation only AFTER three distinct
            # native title observations have passed the pinned image gate.
            if command=='set_input' and fields.get('buttons')=='0xBFFF' and not title_captured:
                snapshot('verified-title');title_captured=True
            return original_request(report,command,**fields)
        result=original_route(report,_debug=debug,**kwargs)
        started=time.monotonic();snapshot('verified-city',flush=True)
        return result

    def request(report,command,**fields):
        if command=='get_registers' and started is not None and pending and time.monotonic()-started>=pending[0]:
            second=pending.pop(0);snapshot(f'city-plus-{second:03}',flush=True)
        return original_request(report,command,**fields)

    def close(report):
        try:snapshot('before-quit',flush=True)
        except Exception as error:notes['errors'].append('Final capture: '+str(error))
        return original_close(report)

    save();world.enter_city=route;world.probe.request=request;world.close=close
    try:
        world.run(SimpleNamespace(batch=args.batch,rewind=0))
        result=world.pacing.base.read(directory/'world-flypast-proof.json')
        notes['errors'].extend(result['errors'])
        notes['owned_process_exit']=result.get('owned_process_exit');notes['close']=result.get('close')
        if result.get('owned_process_forced_cleanup') or result.get('owned_process_exit')!=0 or not result.get('close',{}).get('port_closed'):
            notes['errors'].append('Owned game did not close cleanly')
    except Exception as error:
        notes['errors'].append(str(error));raise
    finally:
        world.enter_city=original_route;world.probe.request=original_request;world.close=original_close
        notes['ended_at_utc']=world.ui.stamp();save()
    if notes['errors'] or pending or not title_captured:raise RuntimeError('Code acquisition incomplete; preserve failed evidence')
    if args.cache_build:
        final=notes['samples'][-1];notes['hot_entries_with_32_clean_diffs']=[]
        for pc,reply in final['hot_candidates'].items():
            if any(c['match'] and c['diff_passes']>=32 and not c['device_touch'] for c in reply['candidates']):
                notes['hot_entries_with_32_clean_diffs'].append(pc)
        notes['correctness_rejection_reasons']=qualification_errors(notes,result)
        notes['correctness_accepted']=not notes['correctness_rejection_reasons']
        notes['pacing_accepted']=False;save()
        if not notes['correctness_accepted']:raise RuntimeError('Native/interpreter validation not accepted; inspect retained candidate and shadow records')


if __name__=='__main__':main()
