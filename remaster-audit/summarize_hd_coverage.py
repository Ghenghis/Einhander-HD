"""Collect bounded HD draw counters and explicitly scoped key receipts."""
import json
from pathlib import Path

ROOT=Path('C:/github/REMASTER_STAGING/hd-coverage')
SOURCE=Path('C:/github/REMASTER_STAGING/stage1_remaster')
catalog={r['key']:{'kind':'upload','neural_detail':'UltraSharp' in r['method']}
    for r in json.loads((SOURCE/'candidates/manifest.json').read_text())['assets']}
catalog.update({r['key']:{'kind':'native_page','neural_detail':r['neural_detail']}
    for r in json.loads((SOURCE/'page-candidates/pages-manifest.json').read_text())['pages']})
report={'catalog':{'files':len(catalog),'neural':sum(r['neural_detail'] for r in catalog.values()),
    'conservative':sum(not r['neural_detail'] for r in catalog.values())},'runs':{}}
for name in ('upload-only','page-fallback','page-cache-512','gpu-resident'):
    directory=ROOT/name/'evidence'
    receipts=[json.loads(line) for line in (directory/'draws.jsonl').read_text().splitlines()]
    observed={r['key'] for r in receipts}
    drawn={r['key'] for r in receipts if r['event']=='replacement GL draw submitted'}
    summary=json.loads((directory/'coverage-summary.json').read_text())
    report['runs'][name]={'coverage':summary['replacement_draw_ratio'],'delta':summary['delta'],
        'counter_frames':summary['counter_frames'],'receipts':len(receipts),'observed_keys':len(observed),
        'drawn_keys':len(drawn),'neural_drawn_keys':sum(catalog[k]['neural_detail'] for k in drawn if k in catalog),
        'page_drawn_keys':sum(catalog[k]['kind']=='native_page' for k in drawn if k in catalog),
        'missing_pack_keys':sorted(observed-catalog.keys()),'receipt_log_capped':name=='page-fallback'}
report['pacing_samples']={p.stem:json.loads(p.read_text())['summary'] for p in sorted(
    (ROOT/'delivery-2x/evidence').glob('*-performance.json'))}
report['limitations']=[
    'Query counts are not screen pixel area or neural-detail coverage.',
    'Stationary assisted Stage 1 routes, not deterministic frame replays or full-game coverage.',
    'Counter snapshots are published every 120 guest frames; boundaries are quantized.',
    'Distinct-key receipts cover each entire session, including menus and later performance samples.',
    'Missing-key lists are distinct observed identities, not per-key draw frequency.',
    'The original page-fallback log hit its 1024-receipt cap; its key counts are lower bounds.']
(ROOT/'coverage-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'catalog':report['catalog'],'coverage':{k:r['coverage'] for k,r in report['runs'].items()},
    'pacing_fps':{k:r['present_fps'] for k,r in report['pacing_samples'].items()}},indent=2))
