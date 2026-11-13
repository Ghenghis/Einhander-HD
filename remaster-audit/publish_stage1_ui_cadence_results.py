"""Publish closed HUD-census and quiet-route results without private source dumps."""
from __future__ import annotations
import json
from pathlib import Path
from publish_stage1_wave2_results import ROOT,E,OUT,read,sha,write,reference
from publish_stage1_emissive_results import still

def closed(path):
    proof=read(path)
    assert not proof['errors'] and proof['owned_process_exit']==0 and proof['close']['port_closed']
    assert not proof.get('owned_process_forced_cleanup')
    return proof

def cadence(run):
    path=run/'world-flypast-proof.json';p=closed(path);a,b=p['observations'][0],p['observations'][-1]
    config=read(run/'candidate.json')
    seconds=b['elapsed_seconds']-a['elapsed_seconds'];frames=b['registers']['frame']-a['registers']['frame']
    return dict(proof=reference(path),runtime_build_sha256=config['pacing_profile']['runtime_build']['sha256'],
        composition_plan_sha256=config['composition_plan']['sha256'],measurement_load=p.get('measurement_load',dict(video=True,source_capture=True,composed_stills=True)),
        guest_frames=frames,seconds=seconds,guest_fps=frames/seconds,
        starved_sample_frames_delta=b['audio']['out']['underruns']-a['audio']['out']['underruns'],
        initial_fill_ms=a['audio']['out']['fill_ms'],final_fill_ms=b['audio']['out']['fill_ms'],
        timer_only_assistance=True,ordinary_fire=False,state_loads=False,
        starved_intervals=[dict(ending_seconds=y['elapsed_seconds'],delta=y['audio']['out']['underruns']-x['audio']['out']['underruns'])
            for x,y in zip(p['observations'],p['observations'][1:]) if y['audio']['out']['underruns']>x['audio']['out']['underruns']])

def main():
    target=OUT/'stage1-ui-results.json';quiet_target=OUT/'stage1-quiet-route-results.json'
    assert not target.exists() and not quiet_target.exists()
    run=E/'hud-fade-census-v1/hd-on_rewind-off';proof=closed(run/'robin-proof.json')
    assert all(proof[k] is False for k in ('ram_writes','state_loads','timer_assistance','stage_clear_verified'))
    manifest=ROOT/'remaster-audit/comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1/manifest.json'
    font=read(manifest);known={x['key'] for x in font['keys']};missing=set(font['logged_but_no_clut_sidecar']['keys'])
    events=[]
    for path in sorted(run.glob('native-source-*/capture.jsonl')):
        events.extend(json.loads(line) for line in path.read_text().splitlines())
    first={}
    for row in events:
        if row.get('event')=='replacement_gl_draw_submitted' and row.get('key') in known:
            first.setdefault(row['key'],row['frame'])
    verification=read(run/'native-source-verification.json')
    retained={x['key'] for x in verification['entries']}
    recovered=sorted(missing&retained)
    assert len(first)==9 and len(missing)==157 and not recovered
    images=[]
    for label,name in [('Total Evaluation','hud-total-evaluation'),('Field Evaluation','hud-field-graph-settled')]:
        metadata=run/'captures'/(name+'.json');m=read(metadata);source=run/'captures'/(name+'-internal.png')
        assert sha(source)==m['hires']['sha256']
        item=still(source,OUT/('stage1-'+('total' if label.startswith('Total') else 'field')+'-evaluation.png'))
        item.update(label=label,capture_metadata=reference(metadata),hires_sequential_not_atomic=True);images.append(item)
    report=dict(schema_version=1,kind='Actual closed HUD and results observation',proof=reference(run/'robin-proof.json'),
        duration_seconds=proof['gameplay_observations'][-1]['elapsed_seconds'],
        font_manifest=reference(manifest),font_bindings_submitted_gl=[dict(key=k,first_frame=v) for k,v in sorted(first.items())],
        historical_missing_palette_keys=len(missing),historical_missing_keys_recovered=recovered,
        native_source_verification=dict(receipt=reference(run/'native-source-verification.json'),
            passed_pairs=verification['source_pairs'],rejected=verification['rejected'],all_passed=False),
        observed_ui=['Total Evaluation','Field Evaluation / Shot Down graph','Exit to native opening movie','Finite Start skip to native story text'],
        return_to_title_verified=False,stage_clear_verified=False,production_installed=False,images=images,
        limitations=['Nine positive font draw bindings do not establish every glyph, fade phase or menu state.',
            'All157 historical missing palette keys remain unresolved; no palettes were synthesized.',
            'Fourteen incomplete native validity maps were rejected and excluded; the complete source-capture verifier did not pass.',
            'The24-bit movie scanout rejects the hires API; supported composed-only captures were retained instead.',
            'Return to title, pause/configuration/rankings/save/name entry and stage clear remain unverified.'])
    write(target,report)
    recorded=cadence(E/'w3-emissive-on-v1/hd-on_rewind-off');quiet=cadence(E/'world-telemetry-lit-v1/hd-on_rewind-off')
    assert recorded['runtime_build_sha256']==quiet['runtime_build_sha256'] and recorded['composition_plan_sha256']==quiet['composition_plan_sha256']
    assert quiet['measurement_load']==dict(video=False,source_capture=False,composed_stills=False,timer_assistance=True)
    audio_receipt=E/'audio-clock-probe-v1/result.json';audio=read(audio_receipt)
    assert audio['compile_exit']==audio['run_exit']==0
    write(quiet_target,dict(schema_version=1,kind='Same-route descriptive diagnostic-load comparison',recorded=recorded,quiet=quiet,
        same_runtime_and_candidate=True,causal_no_overhead_claim=False,full_combat_acceptance=False,audible_audio_acceptance=False,
        controlled_audio_probe=dict(receipt=reference(audio_receipt),source_sha256=audio['source_sha256'],
            audio_bridge_sha256=audio['audio_bridge_sha256'],cases=[json.loads(s) for s in audio['stdout'].splitlines()],
            actual_game_audio=False,audible_qa=False),
        limitations=['One sequential pair; no repeat or randomized order. Different initial buffer fill and host state limit causal attribution.',
            'Both routes used the disclosed timer-only aid and no firing. No unassisted or full-stage performance claim.',
            'Quiet-route residual starvation remains, concentrated near148-149 seconds. Counter evidence does not prove acceptable audible output.']))
    provenance=OUT/'provenance.json';pr=read(provenance)
    for item in images:
        assert not any(x['path']==item['path'] for x in pr['assets'])
        pr['assets'].append(dict(path=item['path'],sha256=item['sha256'],bytes=item['bytes'],dimensions=item['dimensions'],
            category='actual_gameplay_capture',status=item['label']+'; observed without survival aid; stage clear unverified',
            source_path=item['source']['path'],source_sha256=item['source']['sha256'],unmodified_copy=False,
            pixel_identical_to_source=True,processing=item['processing'],embedded_metadata_present=False))
    pr.update(image_count=len(pr['assets']),total_image_bytes=sum(x['bytes'] for x in pr['assets']))
    write(provenance,pr)
    print(json.dumps(dict(ui_result=str(target),quiet_result=str(quiet_target),font_bindings=len(first),missing_recovered=len(recovered),
        quiet_fps=quiet['guest_fps'],quiet_starved=quiet['starved_sample_frames_delta'])))

if __name__=='__main__':main()
