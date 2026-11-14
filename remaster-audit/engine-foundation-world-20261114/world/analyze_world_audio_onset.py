from pathlib import Path
import json
n=Path(__file__).resolve().parent
p=Path('C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-live-r1/hd-on_rewind-on/world-flypast-proof.json')
d=json.loads(p.read_text());observations=d['observations'];changes=[]
uploads=[row for page in d['hd_upload_ledger_pages'] for row in page.get('events',[])]
for before,after in zip(observations,observations[1:]):
 delta=after['audio']['out']['underruns']-before['audio']['out']['underruns']
 if delta:
  f0=before['registers']['frame'];f1=after['registers']['frame']
  changes.append({'seconds':[before['elapsed_seconds'],after['elapsed_seconds']],'frames':[f0,f1],
    'new_starved_samples':delta,'upload_events':[x[:6] for x in uploads if f0<=x[1]<=f1]})
out={'audio_out_first':observations[0]['audio']['out'],'audio_out_last':observations[-1]['audio']['out'],
 'starvation_intervals':changes,'scope':'One-second sampled brackets; correlations only, not atomic causal attribution. First-sample counters excluded from deltas.'}
(n/'world-audio-onset.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
