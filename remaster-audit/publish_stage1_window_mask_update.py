"""Publish the closed four-mask candidate observation, preserving v27 footage."""
import json
from collections import defaultdict
from pathlib import Path
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference
from publish_stage1_emissive_results import still

def main():
    target=OUT/'stage1-atlas-window-mask-results.json';assert not target.exists()
    folder=E/'frozen-w3-atlas-lit-v1';parent=read(E/'frozen-w3-lit-v1/candidate.json');candidate=read(folder/'candidate.json')
    assert {x['name']:x['sha256'] for x in candidate['files']}=={x['name']:x['sha256'] for x in parent['files']}
    verification=read(folder/'native-verification.json');native=json.loads(verification['stdout'])
    assert verification['exit_code']==0 and native==dict(keys=1669,region_checks=226,failures=0)
    assert verification['candidate_sha256']==sha(folder/'candidate.json')
    run=E/'stage-lane-mk3-v2/hd-on_rewind-off';proof=read(run/'robin-proof.json');config=read(run/'candidate.json')
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    assert not any(proof[k] for k in ['ram_writes','state_loads','timer_assistance','stage_clear_verified'])
    assert config['pacing_profile']['emissive_masks']
    keys={'95A3BCF8-07A9568D','95A3BCF8-60245B3A'};draws=defaultdict(list)
    for path in run.glob('native-source-*/capture.jsonl'):
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if row.get('event')=='replacement_gl_draw_submitted' and row.get('key') in keys:draws[row['key']].append(row['frame'])
    assert set(draws)==keys
    tests=E/'sampling-build-v28/tests.json';validation=read(tests);assert all(x['exit']==0 for x in validation['commands'])
    source=run/'captures/robin-0105-internal.png';metadata=run/'captures/robin-0105.json'
    assert sha(source)==read(metadata)['hires']['sha256']
    image=still(source,OUT/'stage1-atlas-lit-windows.png')
    masks=[]
    for item in candidate['emissive_files']:
        path=Path(item['composed_path']);assert sha(path)==item['sha256']
        masks.append(dict(name=item['name'],sha256=item['sha256'],dimensions=item['dimensions']))
    assert len(masks)==4
    report=dict(schema_version=1,kind='Four-mask city-window component observation',candidate=reference(folder/'candidate.json'),
        authored_entries=837,pack_keys=1669,all_authored_rgb_unchanged=True,native_verification=native,
        native_receipt=reference(folder/'native-verification.json'),runtime=reference(E/'sampling-build-v28/build.json'),
        validation=dict(receipt=reference(tests),summaries={k:v.splitlines()[-1] for k,v in validation['results'].items()}),
        formula='RGB * mix(vertex_rgb * 2, max(vertex_rgb * 2, 1), mask / 255)',
        startup_opt_in='PSXRECOMP_HD_EMISSIVE=1; default off',mask_files=masks,
        mask_gpu_bytes=sum(x['dimensions'][0]*x['dimensions'][1] for x in masks),
        actual_gl_submissions=[dict(key=k,samples=len(v),first_frame=min(v),last_frame=max(v)) for k,v in sorted(draws.items())],
        source_proof=reference(run/'robin-proof.json'),capture_metadata=reference(metadata),image=image,
        stage_clear_verified=False,production_installed=False,all_art_motion_accepted=False,
        limitations=['Actual sequential2160p frame; not frame-aligned with an OFF capture. No measured pixel-matched brightness ratio.',
            'This controller trial stopped at135seconds after a false checkpoint inference; it is excluded from progression qualification.',
            'The masks affect selected lit cells in distant atlas region O only. They do not finish every building surface or all artwork.',
            'The earlier complete facade video remains the original v27/two-mask test; it is not relabeled as this v28 run.',
            'No dynamic illumination, reflection or parallax is added; full-motion/material/audio acceptance remains open.'])
    write(target,report)
    provenance=OUT/'provenance.json';pr=read(provenance);assert not any(x['path']==image['path'] for x in pr['assets'])
    pr['assets'].append(dict(path=image['path'],sha256=image['sha256'],bytes=image['bytes'],dimensions=image['dimensions'],
        category='actual_gameplay_capture',status='Two additional distant-window masks; controller qualification failed; stage clear unverified',
        source_path=image['source']['path'],source_sha256=image['source']['sha256'],unmodified_copy=False,
        pixel_identical_to_source=True,processing=image['processing'],embedded_metadata_present=False))
    pr.update(image_count=len(pr['assets']),total_image_bytes=sum(x['bytes'] for x in pr['assets']));write(provenance,pr)
    print(json.dumps(dict(result=str(target),mask_count=4,gl_submitted_keys=sorted(draws))))

if __name__=='__main__':main()
