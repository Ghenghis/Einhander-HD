from pathlib import Path
import hashlib,json,shutil
n=Path(__file__).resolve().parent;folder=n/'cage-v2-canonical-preservation-r1';receipt=folder/'result.json'
shutil.copyfile(receipt,folder/'result-original-count.json')
d=json.loads(receipt.read_bytes());target=Path(d['canonical_copy'])
d['all_entries_copied']=d['all_files_copied'];d['all_files_copied']=sum(p.is_file() for p in target.rglob('*'))
d['count_correction']='Original field counted two directories as files; original receipt is preserved. Artwork/pins unchanged.'
d['original_receipt_sha256']=hashlib.sha256((folder/'result-original-count.json').read_bytes()).hexdigest()
receipt.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(files=d['all_files_copied'],entries=d['all_entries_copied'])))
