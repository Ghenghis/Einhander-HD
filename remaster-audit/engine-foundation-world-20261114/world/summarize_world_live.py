from pathlib import Path
import json,hashlib,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
rel='remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-live-r1/hd-on_rewind-on/world-flypast-proof.json'
p=r/rel;d=json.loads(p.read_text());o=d['observations'];a=o[0]['audio']['out'];b=o[-1]['audio']['out']
plan=json.loads((n/'world-integration-plan-v1.json').read_text());keys={x['key'] for x in plan['entries']}
events=[row for page in d['hd_upload_ledger_pages'] for row in page.get('events',[])]
hits={key:[{'frame':row[1],'width':row[3],'height':row[4],'bytes':row[5]} for row in events if row[2]==key] for key in sorted(keys)}
hits={k:v for k,v in hits.items() if v}
ph=json.loads((n/'world-live-phase-analysis.json').read_text());execution=json.loads((n/'world-live-execution.json').read_text())
assert not d['errors'] and execution['reservation_released'] and execution['pid_gone'] and d['owned_process_exit']==0
result={'run':'world-integrated-live-r1','date_utc':d['ended_at_utc'],'proof':{'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},
 'errors':d['errors'],'composition':{'keys':1698,'changed_or_added_entries':161,'added_keys':29,'changed_existing_keys':132,
 'protected_crisp_signs':5,'native_admission_keys':1698,'native_exact_region_checks':226,'native_admission_failures':0,
 'native_class_check_keys':161,'native_centres_checked':5154816,'class_failures':0,'coverage_plan':plan['coverage']},
 'phase_summary':{k:ph[k] for k in ['measured_frames','valid_pairs','valid_coverage','period_ms_quantiles','periods_over_ms']},
 'audio_delta':{k:b[k]-a[k] for k in ['underruns','overflow_drops']},
 'focus_samples':{'focused':sum(bool(x['hd_cpu_profile']['window_input_focus']) for x in o),'total':len(o)},
 'observed_changed_entry_upload_keys':len(hits),'changed_entry_uploads':hits,
 'key_draw_submissions_proven':False,'observations':len(o),'stills':[x['composed'] for x in o if 'composed' in x],
 'command_audit':d['command_audit'],'exit':d['owned_process_exit'],'port_closed':d['close']['port_closed'],
 'owned_pid_gone':execution['pid_gone'],'gpu_reservation_released':execution['reservation_released'],
 'production_installed':False,'visual_accepted':False,'performance_accepted':False,'full_project_complete':False,
 'visual_review':['world-060 retains coarse stepped sign contours; requested realistic modern fidelity not met.',
  'Distant window atlas remains soft;95A3BCF8 was deliberately unchanged in this composition.'],
 'limits':['Private scale2 output,1280x960 stills; not a4K output acceptance test.',
  'Five synchronous composed/native still pairs, mixed focus and other light CPU allowed; not controlled timing comparison.',
  'No video, full source collector or per-key draw collector. Upload observations do not prove drawn appearance.',
  'Countdown-byte-only180slease, no stage/lives writes or state loads; not stage-clear acceptance.',
  'Retained callback PCM/counters do not establish remastered source audio or physical listening acceptance.']}
onset=json.loads((n/'world-audio-onset.json').read_text())
result['audio_starvation_intervals']=[{k:x[k] for k in ['seconds','frames','new_starved_samples']} for x in onset['starvation_intervals']]
result['audio_at_first_measured_sample']=onset['audio_out_first']
result['audio_at_last_measured_sample']=onset['audio_out_last']
census=json.loads((r/'remaster-audit/claude-backlog/sign-census/census-v2.json').read_text())
absent=set(census['drawn_without_pack_entry'])
result['previously_absent_keys_uploaded']=sorted(absent.intersection(hits))
result['previously_absent_keys_not_observed_uploaded']=sorted(absent-set(hits))
(n/'world-integration-live-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['audio_delta','focus_samples','observed_changed_entry_upload_keys','phase_summary','exit','port_closed','command_audit']},indent=2))
print('proof fields',list(d));print('native tail shape',list(d['world_native_upload_tail']))
