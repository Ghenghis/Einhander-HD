"""Bind the two remaining cases to retained native sources; no game/GPU."""
from pathlib import Path
import hashlib,json,sys
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
sys.path.insert(0,str(r/'remaster-audit'))
from build_stage1_frozen_candidate import verified_native_source
stock=Path('C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ref=lambda p:{'path':str(p.resolve()),'sha256':sha(p)}
parent=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-crisp-v2/candidate.json'
u=r/'remaster-audit/comfy-authoring/t7-enemies/frozen/uhu-57AC02A0-v2';um=json.loads((u/'manifest.json').read_text())
entries=[];source_receipts=[];derived=n/'derived-uhu-source';derived.mkdir(exist_ok=True)
def source(key,folder):
 meta=json.loads((folder/(key+'.source.json')).read_text());assert meta['known_words']==meta['total_words'],key
 native={'source_words':ref(folder/(key+'.words.bin')),'source_clut':ref(folder/(key+'.clut.bin')),
 'source_shape_words':[meta['width_words'],meta['height']],'depth':meta['depth']}
 verified_native_source(native,key)
 return native,ref(folder/(key+'.source.json'))
for row in um['keys']['keys']:
 key=row['key'];folder=stock
 if row['kind']=='page':
  witness=um['sources']['stock_keys'][key]
  assert sha(stock/(key+'.words.bin'))==witness['words_sha256']
  assert sha(stock/(key+'.png'))==witness['png_sha256']
 else:
  # Bind the upload strip to the known full page by byte equality at row224.
  fullkey='57AC02A0-'+key.split('-')[1];full=stock/(fullkey+'.words.bin')
  fullmeta=json.loads((stock/(fullkey+'.source.json')).read_text());assert fullmeta['width_words']==64 and fullmeta['height']==256
  words=full.read_bytes()[224*64*2:232*64*2];clut=(stock/(fullkey+'.clut.bin')).read_bytes()
  strip_control=stock/'B5207452-190A55AD.words.bin'
  assert words==strip_control.read_bytes()
  folder=derived
  for suffix,blob in [('words.bin',words),('clut.bin',clut)]:
   target=folder/(key+'.'+suffix)
   if target.exists():assert target.read_bytes()==blob
   else:target.write_bytes(blob)
  meta={'source_kind':'derived retained native upload strip; NOT a new live capture','width_words':64,'height':8,'depth':0,
   'known_words':512,'total_words':512,'parent_page':ref(full),'parent_clut':ref(stock/(fullkey+'.clut.bin')),
   'rows_half_open':[224,232],'independent_strip_word_control':ref(strip_control)}
  (folder/(key+'.source.json')).write_text(json.dumps(meta,indent=2)+'\n')
 native,meta_ref=source(key,folder)
 image=u/'runtime-1024-calm'/(key+'.png');assert image.is_file()
 entries.append({'manifest':ref(u/'manifest.json'),'key':key,'image':ref(image),'native_source':native,'source_handoff':meta_ref,
  'integration_variant':'runtime-1024-calm','selected_set':u.name,'lane':'t7-enemies','retained_limits':um['known_limits'],
  'selection_reason':'Whole52key page/strip closure, recommended calm1024 variant for small projected quads. Not4K fidelity acceptance.',
  'hash_scope':'Set manifest lists master/review names without runtime PNG hashes. This plan freshly pins the selected runtime PNG; independent native class checks are required before composition.'})
 source_receipts.append({'key':key,'native_source':native,'source_handoff':meta_ref,'set_native_png_witness':um['sources']['stock_keys'].get(key)})
f=r/'remaster-audit/comfy-authoring/w3-canyon/frozen/AB2DB563-emblem-v3b';em=json.loads((f/'manifest.json').read_text());key=em['key']
index=f.parent/'INDEX.json';ix=json.loads(index.read_text());assert ix['deliveries'][f.name]['status']=='candidate' and ix['deliveries']['AB2DB563-emblem-v3']['status']=='FAILED'
for suffix,field in [('words.bin','words_sha256'),('clut.bin','clut_sha256'),('png','png_sha256')]:
 assert sha(stock/(key+'.'+suffix))==em['source'][field]
native,meta_ref=source(key,stock);image=f/'runtime-2048'/(key+'.png');assert sha(image)==em['files']['runtime-2048/'+key+'.png']
entries.append({'manifest':ref(f/'manifest.json'),'key':key,'image':ref(image),'native_source':native,'source_handoff':meta_ref,
 'integration_variant':'runtime-2048','selected_set':f.name,'lane':'w3-canyon','set_index':ref(index),
 'retained_limits':em['known_limits']+['Outside authored uv128,128..256,192 the candidate retains an explicit upscaled placeholder; not full-page new art.']})
assert len(entries)==53 and len({x['key'] for x in entries})==53
old=json.loads(parent.read_text());expected=len({x['name'] for x in old['files']}|{x['key']+'.png' for x in entries})
plan={'parent':ref(parent),'entries':entries,'protected_keys':json.loads((n/'world-integration-plan-v1.json').read_text())['protected_keys'],
 'scope':'Final two sampled legacy cases plus Uhu companion-key closure. CPU only; no installation, game, GPU or live acceptance.',
 'expected_final_count':expected,'coverage':{'sampled_missing_keys_targeted':21,'sampled_legacy_unused_targeted':126,'known_sampled_legacy_unused':126,'unresolved_sampled_legacy_unused':[]},
 'limitations':['Full-game/world/ship/fidelity coverage is unknown; matching all126 sampledcases is not completion.',
 'Uhu57AC02A0-1C654A4F remains uncaptured/unauthored; it is outside this delivered52key set and is not fabricated.',
 'Recommended1024 Uhu is a private whole-family alternative; keep the parent and evaluate shimmer/detail after user returnsGPU.',
 'Distant95A3BCF8window authoring and live audio/look acceptance remain open.']}
(n/'world-final-bindings-plan-v1.json').write_text(json.dumps(plan,indent=2)+'\n')
(n/'world-final-source-bindings.json').write_text(json.dumps({'uhu_sources':source_receipts,'emblem_native_source':native,'emblem_index':ref(index)},indent=2)+'\n')
print(json.dumps({'entries':len(entries),'expected_final_count':expected,'source_bindings':'52 Uhu pages/strips +1 emblem','gpu_work':False},indent=2))
