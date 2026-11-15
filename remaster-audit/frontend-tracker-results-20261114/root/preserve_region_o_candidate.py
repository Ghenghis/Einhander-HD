from pathlib import Path
import datetime,hashlib,json,os,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
source=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/95a3-o-city/frozen/95A3BCF8-O-city-v1'
dest=r/'remaster-audit/claude-backlog/95a3-o-city/frozen/95A3BCF8-O-city-v1'
out=n/'region-o-canonical-copy-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ready=json.loads((source/'READY.json').read_text(encoding='utf-8'));assert ready['validation_passed'] and ready['files']==9
assert sha(source/'SHA256SUMS.txt')==ready['sha256sums'] and sha(source/'manifest.json')==ready['manifest_sha256']
pins={}
for line in (source/'SHA256SUMS.txt').read_text().splitlines():
    h,relative=line.split('  ',1);file=(source/relative).resolve();assert file.is_relative_to(source.resolve()) and sha(file)==h
    pins[relative]=h
assert len(pins)==9
all_files={f.relative_to(source).as_posix() for f in source.rglob('*') if f.is_file()}
assert all_files==set(pins)|{'READY.json','SHA256SUMS.txt'},all_files
dest.mkdir(parents=True,exist_ok=False)
for relative in sorted(all_files-{'READY.json'})+['READY.json']:
    a=source/relative;b=dest/relative;b.parent.mkdir(parents=True,exist_ok=True)
    with a.open('rb') as inp,b.open('xb') as target:
        while data:=inp.read(1024*1024):target.write(data)
        target.flush();os.fsync(target.fileno())
    assert sha(a)==sha(b),relative
assert all(sha(source/f)==h and sha(dest/f)==h for f,h in pins.items())
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=str(source),destination=str(dest),pins_verified=9,all_files_copied=11,ready_sha256=sha(dest/'READY.json'),manifest_sha256=sha(dest/'manifest.json'),source_preserved=True,destination_fsynced_and_rehashed=True,affinity=me.cpu_affinity(),below_normal=True,images_recomputed=False,gpu_run=False,installed=False,
             integration_constraint='Apply only ROI u176..239/v112..175 from the2048 pages to the latest private parent; replacing whole pages could revert newer approved artwork.4096 changes outside ROI and has4x pixel/upload cost. Rebuild identity sidecars for any changed pages; live motion/look acceptance pending.')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
