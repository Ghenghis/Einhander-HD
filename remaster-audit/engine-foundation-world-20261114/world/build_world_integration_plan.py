"""Pin existing deliveries into a new plan; no authoring, game or GPU work."""
from pathlib import Path
import json,hashlib,sys,zlib
r=Path('C:/github/Einhander');n=Path(__file__).parent;sys.path.insert(0,str(r/'remaster-audit'))
from build_stage1_frozen_candidate import verified_native_source
base=r/'remaster-audit/comfy-authoring'
parent=r/'remaster-audit/claude-backlog/sign-washout-audit/pack-frozen-w3-lit-signs-crisp-v2/candidate.json'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def resolve(folder,path):
 p=Path(path)
 if not p.is_absolute():p=folder/p
 assert p.resolve().drive.upper()=='C:',p
 return p
def checked_ref(folder,x):
 p=resolve(folder,x['path']);assert sha(p)==x['sha256'],p;return ref(p)
sets=[('w6-native-gaps','e360c964-metal-v1','page2048'),('w4-signs-hud','E360C964-neon-parts-w4-v1','page2048'),('w4-signs-hud','31214B41-dark-cells-w4-v1','page2048'),('w4-player','w4-flash-debris-0223BCEF-v1','png_1024'),('w6-native-gaps','fd81c3c7-upload-strips-v1','pack'),('w4-world','AB2DB563-canyon-sprites-v1','runtime-2048'),('w5-cleanup','73BF9877-cells-w5-v1','pack')]
entries=[];chosen=set();source_limits=[]
for lane,name,variant in sets:
 folder=base/lane/'frozen'/name;mp=folder/'manifest.json';d=json.loads(mp.read_text(encoding='utf-8'));keys=d['keys'];pairs=list(keys.items()) if isinstance(keys,dict) else [(x if isinstance(x,str) else x['key'],{} if isinstance(x,str) else x) for x in keys]
 for key,item in pairs:
  assert key not in chosen,('duplicate plan key',key);chosen.add(key)
  if variant in item.get('files',{}):image=checked_ref(folder,item['files'][variant])
  elif variant in item:image=checked_ref(folder,item[variant])
  else:
   rel=variant+'/'+key+'.png';record=d.get('files',{}).get(rel) or d.get('files',{}).get(rel.replace('/','\\'))
   assert record and isinstance(record,dict) and 'sha256' in record,(name,key,rel)
   image=checked_ref(folder,dict(path=rel,sha256=record['sha256']))
  source=item.get('source_files') or item.get('sources')
  if source:
   words=checked_ref(folder,source['words']);clut=checked_ref(folder,source['clut'])
   meta=source.get('source_json') or source.get('meta')
   meta_ref=checked_ref(folder,meta) if isinstance(meta,dict) else ref(resolve(folder,meta))
  elif 'sources' in d and key in d['sources']:
   source=d['sources'][key];sd=Path(source['dir']);words=checked_ref(folder,dict(path=str(sd/(key+'.words.bin')),sha256=source['words_sha256']));clut=checked_ref(folder,dict(path=str(sd/(key+'.clut.bin')),sha256=source['clut_sha256']));meta_ref=ref(sd/(key+'.source.json'))
  else:
   # W4 flash/debris stores original file hashes separately from its per-key row.
   sh=d['source_hashes'];refs={}
   for ext in ['words.bin','clut.bin','source.json']:
    fn=key+'.'+ext;record=sh[fn];p=folder/'source'/fn
    if not p.exists():p=Path(record['origin'])
    refs[ext]=checked_ref(folder,dict(path=str(p),sha256=record['sha256']))
   words,clut,meta_ref=refs['words.bin'],refs['clut.bin'],refs['source.json']
  meta=json.loads(Path(meta_ref['path']).read_text());assert meta.get('known_words')==meta.get('total_words'),('incomplete native source',key)
  native={'source_words':words,'source_clut':clut,'source_shape_words':[meta['width_words'],meta['height']],'depth':meta['depth']};verified_native_source(native,key)
  if meta.get('cpu_vram_may_be_stale'):source_limits.append({'key':key,'limit':'retained CPU VRAM stale flag; native admission/class check does not establish independent live visual acceptance'})
  entries.append({'manifest':ref(mp),'key':key,'image':image,'native_source':native,'source_handoff':meta_ref,'integration_variant':variant,'lane':lane,'selected_set':name})
  print(json.dumps({'pinned':len(entries),'key':key,'set':name}),flush=True) if len(entries)%25==0 else None
protected=['0FB1EFC5-F6269484','7A652858-600290FE','67DC56D7-8D0C6ABE','327E6D9E-89C41FFB','CBF6CACF-7BEF165F'];assert not(set(protected)&chosen)
census=json.loads((r/'remaster-audit/claude-backlog/sign-census/census-v2.json').read_text());missing=set(census['drawn_without_pack_entry']);covered=missing&chosen
legacy={x['key'] for x in census['rows'] if x.get('draws') is not None and x['treatment'].startswith('legacy') and x.get('not_integrated_sets')}
plan={'parent':ref(parent),'entries':entries,'scope':'Private integration of already-authored world/sign/flash/strip candidates; preserves fivecrisp-v2 signregions. No installation or acceptance.','protected_keys':protected,'source_limits':source_limits,'coverage':{'known_native_fallback_keys':len(missing),'targeted_native_fallback_keys':len(covered),'not_targeted_native_fallback_keys':sorted(missing-chosen),'known_drawn_legacy_with_unused_set':len(legacy),'targeted_drawn_legacy_keys':len(legacy&chosen),'remaining_drawn_legacy_keys':sorted(legacy-chosen)},'limitations':['Existing candidate pixels are not final4K fidelity acceptance.','Targeting keys does not establish actualdraws, palette/motion correctness or fullcoverage.','No new95A3BCF8 distant-window authoring in this integration.','W5board4/10alternatives excluded; existing fivecrisp-v2regions retained.']}
assert not missing-chosen,plan['coverage']
(n/'world-integration-plan-v1.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');print(json.dumps({'entries':len(entries),'coverage':plan['coverage'],'source_limits':source_limits},indent=2))
