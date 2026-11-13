"""Publish negative code-validation facts without game-derived code or RAM."""
from collections import Counter
import json
from publish_stage1_wave2_results import E,OUT,read,write,reference
from publish_stage1_ui_cadence_results import closed


def main():
    run=E/'loaded-code-validation-v1/hd-on_rewind-off'
    closed(run/'world-flypast-proof.json')
    source=run/'loaded-code/code-capture-proof.json';p=read(source)
    assert p['correctness_accepted'] is False and not p['errors'] and p['owned_process_exit']==0 and p['close']['port_closed']
    final=p['samples'][-1];shadow=final['shadow']['shadow'];hot={}
    for pc,reply in final['hot_candidates'].items():
        hot[pc]=[{k:c[k] for k in ['match','diff_passes','device_touch']} for c in reply['candidates']]
    record_pcs={int(pc,16) for pc in hot}
    rows=[{k:d[k] for k in ['addr','kind','cycle_native','cycle_interp','trace_ops','replay_ops']}
          for d in shadow['records'] if int(d['addr'],16) in record_pcs]
    build=read(E/'loaded-code-cache-v2/build.json')
    report=dict(schema_version=1,kind='Failed private compiled-code correctness validation',
        proof=reference(source),run=reference(run/'world-flypast-proof.json'),cache_build=reference(E/'loaded-code-cache-v2/build.json'),
        compile_exit=build['exit'],artifacts_built=len(build['artifacts']),requested_hot_entries_exported=build['hot_pcs_exported'],
        raw_boot_text_bytes_independently_compared=build['raw_code_bytes_independently_compared'],
        shadow_calls=shadow['shadow_calls'],divergences=shadow['divergences'],skipped_device_or_unsafe=shadow['skipped_device'],
        exception_escapes=shadow['escapes'],divergence_kind_counts=dict(Counter(d['kind'] for d in shadow['records'])),
        kind_labels={'1':'PC','8':'multiply/divide timestamp','9':'GTE timestamp','15':'guest cycle','16':'trace/replay'},
        hot_candidate_results=hot,hot_divergences=rows,hot_entries_with_32_clean_comparisons=p['hot_entries_with_32_clean_diffs'],
        correctness_accepted=False,performance_accepted=False,audio_resolved=False,production_installed=False,
        guard_changed=False,cps_mode=1,
        limitations=['Compilation and matching code bytes do not establish equivalent execution.',
            'Global shadowing also exercised additional region functions and can suppress nested native calls while validating a long-lived parent.',
            'Failure kinds still require focused diagnosis of core, codegen, shadow accounting and diagnostic interference; no timing check was disabled.',
            'Timer-assisted no-fire diagnostic, not an ordinary-input combat, movie or performance acceptance run.',
            'No raw game code, captured RAM, disc data or compiled game-derived modules are published.'])
    target=OUT/'stage1-code-validation-results.json'
    if target.exists():raise ValueError('Preserve the existing published result')
    write(target,report);print(json.dumps(dict(result=str(target),divergences=report['divergences'],accepted=False)))


if __name__=='__main__':main()
