#!/usr/bin/env python3
"""Write manifest.json for a built W7 deliverable (immutable once written).

    python -I freeze_w7.py <job.json> <honest.json>

honest.json: title, honest_read (list), known_limits (list), integration_notes (dict), optional status.
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w7lib as L7  # noqa: E402
from w7lib import cpu_yield  # noqa: E402

IMPORT_RULE = ('predicted-static; import only after live capture: the stage-{s} acquisition run must list every key of '
               'this deliverable as key-confirmed (byte-identical words and CLUT) in validate_predicted.py confirm, and '
               'validate_predicted.py gate must pass for the pack that installs it')


def main():
    cpu_yield()
    job = L7.jload(sys.argv[1])
    hon = L7.jload(sys.argv[2])
    root = Path(job['root']) / job['name']
    assert not (root / 'manifest.json').exists(), 'manifest exists: frozen revisions are immutable'
    rec = L7.jload(root / 'build-record.json')
    val = L7.jload(root / 'native-class-validation.json')
    stage = job['stage']
    sd = L7.EXPORT / f'stage{stage}'
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name != 'manifest.json':
            cpu_yield()
            files[p.relative_to(root).as_posix()] = dict(sha256=L7.sha256(p), bytes=p.stat().st_size)
    pages = {}
    for tex, pg in rec['pages'].items():
        pages[tex] = dict(member=pg['member'], page_xy=pg['page_xy'], mode=pg['mode'], source=pg['source'],
                          rendered_keys=[dict(key=e['key'], clut_xy=e['clut_xy'], confidence=e['confidence'],
                                              chosen_review_clut=e['chosen'], palette_hold=e['palette_hold'],
                                              png_2048=e['exports']['2048'], png_1024=e['exports']['1024'],
                                              energy_gate=e.get('energy'), review=e.get('review'))
                                         for e in pg['keys']['rendered']],
                          renderable_later=pg['keys']['renderable_later'],
                          palette_hold_keys=pg['keys']['palette_hold'],
                          runtime_written_clut_positions_index_master_only=pg['keys']['index_master_only_runtime_clut_positions'],
                          excluded_zero_clut_keys=pg['keys']['excluded_zero_clut'],
                          excluded_stale_front_end_keys=pg['keys']['excluded_stale'],
                          soft_label_stats=pg['soft_stats'], glow=pg['glow'], material=pg['material'],
                          logD_p1_p99=pg['logD_p1_p99'], regions=pg.get('regions'))
    swatches = {}
    for f in sorted((root / 'comfy').glob('*')) if (root / 'comfy').exists() else []:
        swatches[f.name] = L7.sha256(f)
    m = dict(
        name=job['name'], track=job['track'] + ' (claude-einhander %s)' % job.get('lane', ''), task=job.get('task'),
        family=job['family'],
        status=hon.get('status', 'candidate'), frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        title=hon['title'],
        import_rule=IMPORT_RULE.format(s=stage),
        key_status='predicted-static; import only after live capture',
        supersedes=job.get('supersedes'),
        sources=dict(kind='shared immutable static export (exact-static disc strips, member-pure pages)',
                     export_build=L7.jload(L7.EXPORT / 'BUILD.json').get('built'),
                     textures_json_sha256=L7.sha256(sd / 'textures.json'), keys_json_sha256=L7.sha256(sd / 'keys.json'),
                     cluts_json_sha256=L7.sha256(sd / 'cluts.json'),
                     review=str(L7.REVIEWDIR / f'stage{stage}' / 'READINESS.md').replace('\\', '/'),
                     palette_review_sha256=L7.sha256(L7.REVIEWDIR / f'stage{stage}' / 'palette-review.json')),
        gpu=job.get('gpu_note', 'none: CPU-only index-space authoring; no ComfyUI call in this revision (GPU-RESERVED respected)'),
        comfyui_graphs=job.get('comfyui_graphs', []),
        reused_generated_swatches=dict(note=job.get('swatch_note', 'Stage 1 JuggernautXL tileable swatches reused as luminance '
                                                    'detail only (graphs/history copied in comfy/ where they exist)'),
                                       files_sha256=swatches),
        method=job['method'], render_formula=job['render_formula'],
        class_validation=dict(file='native-class-validation.json', total_mismatches=val['total_mismatches'],
                              exports=len(val['files']), convention=val['convention']),
        alpha_channel='categorical PSX classes (0 = raw 0x0000, 127 opaque, 255 STP), NOT opacity; exact at every native texel centre',
        pages=pages, builder_scripts={p.name: L7.sha256(p) for p in sorted((root / 'builder').glob('*'))},
        build_record='build-record.json', honest_read=hon['honest_read'], known_limits=hon['known_limits'],
        integration_notes=hon.get('integration_notes'), reuse=job.get('reuse'),
        shared_pages_referenced_not_built=rec.get('shared_pages') or None,
        glyph_check=(L7.jload(root / 'glyph-check.json')['summary'] if (root / 'glyph-check.json').exists() else None),
        files=files)
    (root / 'manifest.json').write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding='utf-8')
    print(job['name'], 'manifest sha256', L7.sha256(root / 'manifest.json'), 'files', len(files),
          'mismatches', val['total_mismatches'])


if __name__ == '__main__':
    main()
