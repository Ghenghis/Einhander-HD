from pathlib import Path
import hashlib,json,shutil,datetime
e=Path('C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112')
src=e/'sampling-build-v67-decode-identity-r1';dst=e/'sampling-build-v67-decode-identity-r2'
dst.mkdir(exist_ok=False)
for name in ['src','include','third_party']:shutil.copytree(src/name,dst/name)
for name in ['counter-handler.inc','counter-handler-test.c','counter-contract.json','prepared.json']:shutil.copy2(src/name,dst/name)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=str(src),destination=str(dst),failed_r1_preserved=True,files={p.relative_to(dst).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dst.rglob('*') if p.is_file()},reason='Same prepared game sources; corrected build-runner child-exit observation. No compiler/test executed during preparation.')
(dst/'revision-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(dst=str(dst),files=len(receipt['files']))))
