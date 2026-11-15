"""Read-only replay of the two scoped private-profile diagnostics; no game launch."""
from pathlib import Path
import csv, hashlib, json, math, statistics, subprocess, sys, tempfile

ROOT=Path(__file__).resolve().parent
ANALYZERS=ROOT.parent/'runtime-results-v58'
sys.path.insert(0,str(ANALYZERS))
import analyze_frame_phases as A

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def check():
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path=ROOT/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],item['path']
        if path.suffix=='.json': json.loads(path.read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
    checks=[]
    with tempfile.TemporaryDirectory(prefix='ein-power-replay-') as temporary:
        for tag in ('normal-r4b','maximum-r5b'):
            source=ROOT/f'{tag}-observations.json'
            data=json.loads(source.read_text(encoding='utf-8'))
            for script,suffix,extra in [('analyze_frame_phases.py','analysis',['--top','12']),
                                      ('correlate_swap_uploads.py','uploads',[]),
                                      ('correlate_audio_stalls.py','audio',[])]:
                dest=Path(temporary)/f'{tag}-{suffix}.json'
                run=subprocess.run([sys.executable,str(ANALYZERS/script),str(source),*extra,'--out',str(dest)],
                                   capture_output=True,text=True,encoding='utf-8')
                assert run.returncode==0,run.stderr
                actual=json.loads(dest.read_text(encoding='utf-8'))
                saved=json.loads((ROOT/f'{tag}-{suffix}.json').read_text(encoding='utf-8'))
                if suffix=='uploads': actual.pop('proof');saved.pop('proof')
                assert actual==saved,f'{tag}-{suffix}'
            result=expected[tag]
            analysis=json.loads((ROOT/f'{tag}-analysis.json').read_text(encoding='utf-8'))
            rows={};frequencies=set()
            for page in data['frame_phase_pages']:
                assert page['ok'] and page['enabled']==1 and page['owner_bound']==1
                frequencies.add(page['qpc_frequency'])
                for raw in page['rows']:
                    assert len(raw)==len(page['fields'])
                    row=dict(zip(page['fields'],raw))
                    if row['seq'] in rows: assert rows[row['seq']]==row
                    rows[row['seq']]=row
            assert len(frequencies)==1
            frequency=next(iter(frequencies));periods=[];boss=[]
            lo,hi=analysis['measured_frames']
            for seq,cur in rows.items():
                if not lo<=cur['frame']<=hi: continue
                prev=rows[seq-1]
                assert cur['flags']==prev['flags']==1 and cur['swaps']==prev['swaps']==1
                assert cur['frame']==prev['frame']+1 and cur['frame_at_swap']==cur['frame']
                stamps=[prev['swap_begin'],prev['swap_end'],prev['exit'],cur['enter'],cur['debug_end'],cur['pace_begin'],cur['pace_end'],cur['swap_begin']]
                assert all(stamps) and stamps==sorted(stamps)
                period=(stamps[-1]-stamps[0])*1000/frequency
                periods.append(period)
                if 9250<=cur['frame']<=9599: boss.append(period)
            assert len(periods)==analysis['valid_pairs']==result['valid_pairs']
            assert math.isclose(max(periods),result['period_ms_quantiles']['1.0'],abs_tol=1e-9)
            assert analysis['period_ms_quantiles']==result['period_ms_quantiles']
            assert {str(t):sum(x>t for x in periods) for t in (20,25,33.4,50,100)}==result['periods_over_ms']
            assert len(boss)==result['nominal_boss_pairs']==350
            assert math.isclose(max(boss),result['nominal_boss_max_ms'],abs_tol=1e-9)
            obs=data['observations']
            assert obs[-1]['audio']['out']['underruns']-obs[0]['audio']['out']['underruns']==result['starved']
            assert obs[-1]['audio']['out']['overflow_drops']-obs[0]['audio']['out']['overflow_drops']==result['overflow']
            focused=sum(o['hd_cpu_profile']['keyboard_focus']==1 and o['hd_cpu_profile']['window_input_focus']==1 for o in obs)
            assert focused==result['focus_true']==0 and len(obs)==result['focus_samples']==121
            assert data['owned_process_exit']==result['exit']==0 and data['close']['port_closed'] and not data['errors']
            with (ROOT/f'{tag}-gpu0-power.csv').open(encoding='utf-8') as f:
                gpu=[{k.strip():v.strip() for k,v in row.items()} for row in csv.DictReader(f)]
            def mhz(field):
                values=[float(row[field].split()[0]) for row in gpu]
                return [min(values),statistics.median(values),max(values)]
            gpu_summary={'samples':len(gpu),
                         'pstate_counts':{s:sum(x['pstate']==s for x in gpu) for s in sorted({x['pstate'] for x in gpu})},
                         'graphics_mhz':mhz('clocks.current.graphics [MHz]'),
                         'memory_mhz':mhz('clocks.current.memory [MHz]')}
            assert gpu_summary==result['gpu_log_whole_monitor']
            ledger=[row for page in data['hd_upload_ledger_pages'] for row in page['events']]
            assert len(ledger)==result['hd_uploads'] and sum(row[5] for row in ledger)==result['hd_bytes']
            assert math.isclose(max(row[9] for row in ledger)*1000/frequency,result['max_hd_object_ms'],abs_tol=1e-9)
            checks.append(f'{tag}: three analyzer replays, independent phase/audio/focus/upload/resource/cleanup checks passed')
    receipts=json.loads((ROOT/'launch-receipts.json').read_text(encoding='utf-8'))
    cache=(ROOT/'initial-cache-manifest.json').read_bytes()
    for tag in ('normal-r4b','maximum-r5b'):
        assert receipts[tag]['initial_cache_sha256']==hashlib.sha256(cache).hexdigest()
        assert receipts[tag]['executable_sha256']==expected[tag]['runtime_sha256']
    assert expected['initial_cache_identical']
    restore=json.loads((ROOT/'profile-restoration.json').read_text(encoding='utf-8'))
    state=restore['ui_verified_profile']
    assert state['restored_after_test'] and state['power_management']=='Global - Normal'
    assert not state['global_settings_changed'] and not state['other_program_settings_changed']
    checks.append('recorded cache identity, runtime identity and scoped UI restoration receipt match (not an NVAPI profile-match proof)')
    print(json.dumps({'passed':True,'checks':checks,'manifest_sha256':sha(ROOT/'manifest.json')},indent=2))

if __name__=='__main__': check()
