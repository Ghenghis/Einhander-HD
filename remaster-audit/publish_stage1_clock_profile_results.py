"""Publish clock and true-PC evidence; never publish captured code or RAM."""
import json
from publish_stage1_wave2_results import ROOT,E,OUT,read,write,reference
from publish_stage1_ui_cadence_results import closed


def main():
    target=OUT/'stage1-clock-profile-results.json'
    if target.exists():raise ValueError('Preserve the existing published result')
    run=E/'actual-pc-profile-v1/hd-on_rewind-off';p=closed(run/'world-flypast-proof.json')
    row=next(x for x in p['observations'] if 94.5<x['elapsed_seconds']<95.5)
    sample=row['interp_pc_profile'];end=p['interp_pc_profile_end']
    assert not sample['dropped'] and not end['enabled']
    groups=[]
    for lo,hi in [(0x3A9C0,0x3AB10),(0x3A730,0x3A840),(0xB5C80,0xB5CF0)]:
        buckets=[x for x in sample['top'] if lo<=int(x['pc_lo'],16)<hi]
        count=sum(x['samples'] for x in buckets)
        groups.append(dict(pc_lo=f'0x{lo:08X}',pc_hi_exclusive=f'0x{hi:08X}',visible_top64_buckets=len(buckets),
            visible_samples=count,interpreted_sample_share_lower_bound=count/sample['samples']))
    qualified=E/'published-ts-focus3A998-v1/hd-on_rewind-off'
    closed(qualified/'world-flypast-proof.json')
    qpath=qualified/'loaded-code/code-capture-proof.json';q=read(qpath);shadow=q['samples'][-1]['shadow']['shadow']
    assert q['correctness_accepted'] and q['hot_entries_with_32_clean_diffs']==['0x0003A998']
    assert not shadow['divergences'] and not shadow['skipped_device'] and not shadow['escapes']
    receipt=ROOT/'remaster-audit/verification/timestamp-batch-v1/proof.json';clock=read(receipt)
    assert clock['before_test_exit']==1 and clock['before_failures']==10 and clock['after_test_exit']==0 and clock['after_failures']==0
    report=dict(schema_version=1,kind='Clock regression and bounded compiled hot-loop correctness result',
        clock_regression=dict(receipt=reference(receipt),before_checks=clock['checks'],before_failures=10,
            after_checks=clock['after_checks'],after_failures=0,batched_vs_published_cases=clock['batched_vs_published_cases'],
            before_source_sha256=clock['before_source_sha256'],after_source_sha256=clock['after_source_sha256'],
            existing_device_causality_check_passed=True),
        actual_pc_profile=dict(proof=reference(run/'world-flypast-proof.json'),snapshot_elapsed_seconds=row['elapsed_seconds'],
            snapshot_samples=sample['samples'],snapshot_dropped=sample['dropped'],snapshot_occupied=sample['occupied_buckets'],
            final_samples=end['samples'],final_dropped=end['dropped'],final_occupied=end['occupied_buckets'],
            final_dropped_fraction=end['dropped']/end['samples'],top64=sample['top'],groups=groups,
            bucket_bytes=16,scope='Interpreted RAM instruction-attempt frequency only; not frame time or native work',
            original_entry_chain_gain_estimates_withdrawn=True),
        native_correctness=dict(proof=reference(qpath),build=reference(E/'sampling-build-v40-published-timestamps/build.json'),
            qualified_entries=['0x0003A998'],minimum_clean_calls=32,shadow_calls=shadow['shadow_calls'],
            divergences=0,skipped_device_or_unsafe=0,exception_escapes=0,live_code_crc_matched=True,
            other_entries_accepted=False),
        performance_accepted=False,audio_resolved=False,production_installed=False,
        limitations=['Only the isolated 3A998 artifact was imported for the focused correctness run; the other eight requested entries remain unqualified.',
            'The first profile filled 8192 slots late. Use its snapshot at 95s with zero drops; visible groups are lower bounds because only the top 64 buckets were exported.',
            'The next profiler capacity is 32768; this does not retroactively remove dropped samples.',
            'A competing authoring job was reported early in the correctness run. Diagnostic reads and shadow comparisons also preclude a pacing claim.',
            'Correct clock tests and observed-input native equivalence do not establish smooth audio, ordinary combat, FMV or full-game completion.',
            'No captured RAM, original game code or compiled game-derived modules are included.'])
    write(target,report);print(json.dumps(dict(result=str(target),clock_checks=clock['after_checks'],differential_cases=clock['batched_vs_published_cases'],qualified='0x0003A998',audio_resolved=False)))


if __name__=='__main__':main()
