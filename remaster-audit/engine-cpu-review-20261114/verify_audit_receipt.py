from pathlib import Path
import collections,hashlib,json,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;a=r/'remaster-audit/claude-backlog/class-audit'
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=a/'class-audit-v2-world-integrated-crisp-v3.json';d=json.loads(audit.read_bytes())
assert sha(d['checker']['path'])==d['checker']['sha256']
p=Path(d['pack']);cand=json.loads((p/'candidate.json').read_bytes());assert sha(p/'candidate.json')==d['candidate_sha256']
ledger={x['name'][:-4]:x for x in cand['files']};assert len(ledger)==len(d['rows'])==1699
rows=d['rows'];assert len({x['key'] for x in rows})==1699
source_files=0;validity_proofs=0
for row in rows:
 assert row['key'] in ledger
 if 'png_sha256' in row:assert row['png_sha256']==ledger[row['key']]['sha256']
 if 'source' not in row:continue
 source=row['source'];directory=Path(source['dir']);key=row['key']
 assert sha(directory/(key+'.words.bin'))==source['words_sha256'];source_files+=1
 if source.get('clut_sha256'):assert sha(directory/(key+'.clut.bin'))==source['clut_sha256'];source_files+=1
 if source['validity']=='valid.bin all 1':
  vb=(directory/(key+'.valid.bin')).read_bytes();assert len(vb)==source['width_words']*source['height'] and set(vb)=={1}
 else:
  meta=json.loads((directory/(key+'.source.json')).read_bytes());assert meta['known_words']==meta['total_words']==source['width_words']*source['height']
 validity_proofs+=1
counts=collections.Counter(x['status'] for x in rows)
assert counts['PASS']==d['summary']['pass']==1182 and counts['MISMATCH']==d['summary']['mismatch_keys']==299
assert counts['NOT CHECKED']==218
assert sum(x.get('texels',0) for x in rows)==48162560
assert sum(x.get('mismatches',0) for x in rows)==142550
assert not any(x.get('nonclass_alpha_pixels',0) for x in rows)
result={'audit_sha256':sha(audit),'checker_sha256':sha(d['checker']['path']),'candidate_sha256':d['candidate_sha256'],'ledger_keys':1699,'status_counts':dict(counts),'source_file_hashes_verified':source_files,'complete_word_proofs_verified':validity_proofs,'nonclass_alpha_pixels_reported':0,'receipt_consistent':True,'cpu_only':True,'scope':'Independent receipt arithmetic, PNG-ledger pin consistency, native source hashes and complete-word proofs. Does not decode every replacement again, prove visuals, or validate the 218 missing native sources.'}
(n/'strict-audit-independent-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
