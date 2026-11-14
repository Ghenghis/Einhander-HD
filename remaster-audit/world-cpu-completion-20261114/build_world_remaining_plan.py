"""Pin ten remaining sourced candidates, CPU only. Keep two unresolved cases explicit."""
from pathlib import Path
import hashlib,json,sys
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
sys.path.insert(0,str(r/'remaster-audit'))
from build_stage1_frozen_candidate import verified_native_source
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ref=lambda p:{'path':str(p.resolve()),'sha256':sha(p)}
first=json.loads((n/'world-integration-plan-v1.json').read_text())
keys=set(first['coverage']['remaining_drawn_legacy_keys'])
data=json.loads((r/'remaster-audit/claude-backlog/sign-census/integration-plan.json').read_text())
entries=[];unresolved=[]
for row in data['plan']:
 key=row['key']
 if key not in keys:continue
 opt=row['options'][0];source=opt['set_source']
 if not source:
  unresolved.append({'key':key,'set':opt['set'],'reason':'No intrinsic source dump pinned by this set. Resolve source/CLUT binding and companion-key or proposal requirements before admission.'});continue
 folder=Path(opt['manifest']).parent;variant='pack' if key.startswith('C7502427-') else 'page2048' if key.startswith(('73BF9877-','AB58BBA4-')) else 'runtime-2048'
 image=next(x for x in opt['files'] if x['dir']==variant)
 ip=Path(image['path']);assert sha(ip)==image['sha256']
 src=Path(source['dir']);wp=src/(key+'.words.bin');cp=src/(key+'.clut.bin');mp=src/(key+'.source.json')
 assert sha(wp)==source['words_sha256'] and sha(cp)==source['clut_sha256']
 meta=json.loads(mp.read_text());assert meta['known_words']==meta['total_words']
 native={'source_words':ref(wp),'source_clut':ref(cp),'source_shape_words':[meta['width_words'],meta['height']],'depth':meta['depth']}
 verified_native_source(native,key)
 manifest=Path(opt['manifest']);assert sha(manifest)==opt['manifest_sha256']
 entries.append({'manifest':ref(manifest),'key':key,'image':ref(ip),'native_source':native,'source_handoff':ref(mp),
  'integration_variant':variant,'lane':opt['lane'],'selected_set':opt['set'],'retained_limits':opt['known_limits'],
  'old_dimensions':row['base_entry']['dims'],'candidate_dimensions':image['dims'],'resolution_change':row['base_entry']['dims']!=image['dims']})
parent=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v1/candidate.json'
assert len(entries)==10 and len(unresolved)==2
out={'parent':ref(parent),'entries':entries,'protected_keys':first['protected_keys'],'unresolved':unresolved,
 'scope':'Ten already-authored sourced candidates enter a new private composition. CPU only; no GPU, installation or live acceptance while user owns3090Ti.',
 'resolution_changes':[{'key':x['key'],'old':x['old_dimensions'],'new':x['candidate_dimensions'],'reason':'Existing authored puff candidate supplies2048 page; older4096neural page retained in parent. This is an explicit alternative, not native4K authoring acceptance.'} for x in entries if x['resolution_change']],
 'coverage':{'sampled_native_fallback_keys_targeted':21,'sampled_drawn_legacy_unused_keys_targeted_after_composition':124,'known_total_legacy_unused':126,
  'remaining_drawn_legacy_keys':[x['key'] for x in unresolved]},
 'limits':['Distant95A3BCF8window atlas remains unchanged and requires authoring.','All new candidates require motion/look/audio verification after user returnsGPU.','No whole-game coverage or realistic4K skin claim.']}
(n/'world-remaining-plan-v1.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'entries':len(entries),'unresolved':unresolved,'resolution_changes':out['resolution_changes']},indent=2))
