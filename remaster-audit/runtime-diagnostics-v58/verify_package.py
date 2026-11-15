#!/usr/bin/env python3
"""Verify frozen package hashes/source receipts/key counts and changed document links. No game or compiler."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import unquote
P=Path(__file__).resolve().parent; R=P.parents[1]
manifest=json.loads((P/'manifest.json').read_text(encoding='utf-8')); errors=[]
for x in manifest['files']:
 f=(P/x['path']).resolve()
 if not f.is_relative_to(P.resolve()) or not f.is_file(): errors.append('Missing/unsafe package path '+x['path']);continue
 if hashlib.sha256(f.read_bytes()).hexdigest()!=x['sha256']: errors.append('Hash mismatch '+x['path'])
build=json.loads((P/'local-recipes/build.json').read_text(encoding='utf-8'))
for n,h in build['sources'].items():
 if hashlib.sha256((P/'new'/n).read_bytes()).hexdigest()!=h: errors.append('Built source mismatch '+n)
keys={}
for f in sorted((P/'capture-checklists/keys').glob('*.txt')):
 a=re.findall(r'(?m)^[0-9A-F]{8}-[0-9A-F]{8}$',f.read_text().replace('\r',''))
 keys[f.name]=dict(count=len(a),unique=len(set(a)))
 if len(a)!=len(set(a)): errors.append('Duplicate capture key '+f.name)
expected={'S1-C1-flash-keys.txt':23,'S2-gate-keys.txt':39,'S2-unknown-phase-keys-60.txt':60,'S2-addendum-post-drache-119.txt':119,'S2-addendum-unexported-tex-16.txt':16,'S3-gate-keys.txt':39,'S4-gate-keys.txt':11,'S4-confirm-renderable-later.txt':233,'S5-gate-keys.txt':12,'S5-confirm-renderable-later.txt':245,'S6-gate-keys.txt':101,'S7-gate-keys.txt':26}
for n,c in expected.items():
 if keys.get(n,{}).get('count')!=c: errors.append('Capture count mismatch '+n)
checked=0; external=0
for rel in manifest['document_link_scope']:
 f=R/rel;s=f.read_text(encoding='utf-8');links=re.findall(r'(?:href|src)=[\"\']([^\"\']+)[\"\']',s)
 if f.suffix=='.md':
  s=re.sub(r'\x60\x60\x60[\s\S]*?\x60\x60\x60','',s)
  s=re.sub(r'\x60[^\x60]*\x60','',s)
  links+=re.findall(r'\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)',s)
 for link in links:
  link=link.strip('<>');prefix='https://github.com/Ghenghis/Einhander-HD/raw/refs/heads/main/'
  if link.startswith(prefix): target=R/link[len(prefix):]
  elif re.match(r'^(?:https?:|mailto:|#|data:|[A-Za-z]:)',link): external+=1;continue
  else:
   q=unquote(link.split('#')[0].split('?')[0])
   if not q:continue
   target=f.parent/q
  checked+=1
  if not target.exists():errors.append('Broken document link '+rel+' -> '+link)
report=dict(package_hash_files=len(manifest['files']),built_source_hashes=len(build['sources']),capture_key_lists=keys,document_files=len(manifest['document_link_scope']),local_links_checked=checked,external_or_anchor_links_not_revalidated=external,errors=errors,passed=not errors,full_e2e_complete=False,note='Documentation/source-receipt verification only; no game performance or all-stage acceptance')
(P/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2));sys.exit(bool(errors))
