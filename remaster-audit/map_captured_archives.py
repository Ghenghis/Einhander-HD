"""Map observed raw words/CLUTs back to verified extracted stock archive bytes.

Exact byte matches are provenance evidence, not proof of an asset's stage name.
Animated palettes and VRAM-composed pages may have no contiguous archive match.
"""
import hashlib
import json
import os
from pathlib import Path
ROOT=Path('C:/github/REMASTER_STAGING')
SOURCE=Path(os.environ.get('EIN_PAGE_SOURCE',str(ROOT/'stage1_remaster/cpu-authority-source/stock/einhander-texture-replacements')))
archive=json.loads((ROOT/'disc_stock/archives/manifest.json').read_text())['entries']
patterns={};sources=[]
for path in sorted(SOURCE.glob('*.source.json')):
    meta=json.loads(path.read_text());key=meta['key'];raw=(SOURCE/(key+'.words.bin')).read_bytes();pal=(SOURCE/(key+'.clut.bin')).read_bytes()
    parts=[]
    # Physical pages combine uploads. Map independent eight-row strips rather
    # than falsely claiming the whole composed page is stored contiguously.
    stride=meta['width_words']*2;step=stride*8 if not meta['upload_serial'] else len(raw)
    for pos in range(0,len(raw),step):
        data=raw[pos:pos+step]
        if len(set(data))<8:continue # empty/flat padding is not distinctive
        digest=hashlib.sha256(data).hexdigest();patterns.setdefault(digest,{'data':data,'matches':[]});parts.append({'offset':pos,'bytes':len(data),'sha256':digest})
    pd=hashlib.sha256(pal).hexdigest() if pal else None
    if pal:patterns.setdefault(pd,{'data':pal,'matches':[]})
    sources.append({'key':key,'native_origin':meta['raw_origin'],'parts':parts,'palette_sha256':pd})
for entry in archive:
    data=Path(entry['output']).read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Extracted archive changed: '+entry['output'])
    for item in patterns.values():
        pos=data.find(item['data'])
        if pos>=0:item['matches'].append({'pack':entry['pack'],'entry':entry['entry'],'entry_sha256':entry['sha256'],'offset':pos,'ambiguity':'first occurrence in this entry; other occurrences may exist'})
out=SOURCE.parent.parent/'evidence/archive-provenance.json'
out.write_text(json.dumps({'source_directory':str(SOURCE),'distinct_byte_patterns':len(patterns),
    'matched_patterns':sum(bool(x['matches']) for x in patterns.values()),
    'meaning':'Exact raw byte equality only. Unmatched parts may be composed/transformed at runtime; do not label them missing disc assets.',
    'patterns':{key:{'bytes':len(row['data']),'matches':row['matches']} for key,row in patterns.items()},'assets':sources},indent=2)+'\n')
print(json.dumps({'patterns':len(patterns),'matched':sum(bool(x['matches']) for x in patterns.values()),'manifest':str(out)},indent=2))
