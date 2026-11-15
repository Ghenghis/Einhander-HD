from pathlib import Path
import json,hashlib,datetime
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
base=json.loads((e/'world-integrated-crisp-v1/candidate.json').read_text())
final_path=e/'world-integrated-crisp-v3/candidate.json';c=json.loads(final_path.read_text())
old={x['name']:x for x in base['files']};now={x['name']:x for x in c['files']}
v2=json.loads((e/'world-integrated-crisp-v2/verification.json').read_text());v3=json.loads((e/'world-integrated-crisp-v3/verification.json').read_text())
assert v2['all_checks_pass'] and v3['all_checks_pass']
plan1=json.loads((n/'world-integration-plan-v1.json').read_text());plan2=json.loads((n/'world-remaining-plan-v1.json').read_text());plan3=json.loads((n/'world-final-bindings-plan-v1.json').read_text())
keys={x['key'] for p in [plan1,plan2,plan3] for x in p['entries']}
census=json.loads((r/'remaster-audit/claude-backlog/sign-census/census-v2.json').read_text())
missing=set(census['drawn_without_pack_entry'])
legacy={x['key'] for x in census['rows'] if x.get('draws') is not None and x['treatment'].startswith('legacy') and x.get('not_integrated_sets')}
assert len(keys)==224 and not missing-keys and not legacy-keys
hold=json.loads((r/'remaster-audit/comfy-authoring/GPU-RESERVED').read_text());assert hold['owner']=='user-external-project'
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'newest_private_candidate':str(final_path),
 'candidate_sha256':hashlib.sha256(final_path.read_bytes()).hexdigest(),'keys':c['final_count'],'unique_patch_keys_from_crisp_parent':len(keys),
 'changes_after_live_tested_v1':{'added_keys':sorted(set(now)-set(old)),'changed_existing_keys':sorted(k for k in now.keys()&old.keys() if now[k]['sha256']!=old[k]['sha256'])},
 'sampled_catalog_targets':{'absent':len(missing),'absent_targeted':len(missing&keys),'legacy_unused':len(legacy),'legacy_unused_targeted':len(legacy&keys)},
 'class_checks_after_last_game':{'keys':v2['class_check']['keys']+v3['class_check']['keys'],'native_centres_checked':v2['class_check']['native_centres_checked']+v3['class_check']['native_centres_checked'],'failures':0},
 'native_final':v3['native'][0],'protected_crisp_signs':v3['protected_crisp_signs'],
 'emblem_index_validated':True,'uhu_companion_keys':52,'derived_strip_source_scope':'Byte-identical native full-page crop with CLUT, not a new live capture.',
 'resolution_limits':['Three puff pages use authored2048 alternatives to older4096neural pages; original4096retained in parent.',
 'Uhu uses its recommended1024calm whole52key family; not a native4K asset claim.',
 'Emblem artwork owns only its declared128x64nativepanel; other pagepixelsremainupscaledplaceholders.'],
 'known_unresolved':['Distant95A3BCF8window atlas quality','Uhu57AC02A0-1C654A4FsourceCLUToutside52deliveredkeys','Other uncensused scene/stage/state coverage','All new motion/look/audio acceptance'],
 'game_started_after_user_gpu_hold':False,'user_gpu_hold':hold,'production_installed':False,'live_visual_accepted':False,
 'full_project_complete':False,'scope':'CPU source/class/native-loader candidate completion for a bounded sampled catalog only; no new gameplay/4K/audio/RT acceptance.'}
(n/'world-cpu-completion-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['keys','unique_patch_keys_from_crisp_parent','sampled_catalog_targets','class_checks_after_last_game','game_started_after_user_gpu_hold','production_installed']},indent=2))
