"""Private verified dependency staging only. Never executes the jar/installer/DLL."""
from pathlib import Path
import datetime,hashlib,json,psutil,requests,shutil,time,zipfile
n=Path(__file__).resolve().parent;out=n/'sdk-v016-release';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
release=json.loads((n/'sdk-package-protocol/result.json').read_text())['release']
asset=next(x for x in release['assets'] if x['name'].endswith('.jar'))
assert asset['digest']=='sha256:13e1c2ea214b4156e91afb8d6034bf76f1a14a117cd59ec166e53c3840c5bd30'
assert shutil.disk_usage(out).free>5*1024**3
jar=out/'official-release.jar';part=out/'official-release.jar.part';start=time.monotonic();receipt=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),asset=asset,
    cpu_affinity=me.cpu_affinity(),below_normal=True,max_download_bytes_per_second=32*1024**2,software_executed=False,dll_loaded=False,gpu_executed=False,installed_toolkit_modified=False)
try:
    digest=hashlib.sha256();received=0;last=0
    with requests.get(asset['browser_download_url'],timeout=(15,20),stream=True) as response:
        response.raise_for_status()
        with part.open('xb') as f:
            for chunk in response.iter_content(1024*1024):
                if not chunk:continue
                if time.monotonic()-start>180:raise TimeoutError('Bounded three-minute download limit')
                received+=len(chunk);assert received<=asset['size']
                f.write(chunk);digest.update(chunk)
                delay=received/(32*1024**2)-(time.monotonic()-start)
                if delay>0:time.sleep(min(delay,.1))
                if time.monotonic()-last>10:
                    print(json.dumps(dict(phase='download',bytes=received,total=asset['size'])),flush=True);last=time.monotonic()
    assert received==asset['size'] and digest.hexdigest()==asset['digest'].split(':')[1]
    part.rename(jar);receipt.update(archive_sha256=digest.hexdigest(),archive_bytes=received,archive_digest_verified=True)
    target=out/'win64';target.mkdir();files=[];omitted=[]
    with zipfile.ZipFile(jar) as archive:
        for entry in archive.infolist():
            prefix='native/remix-sdk-win64/'
            if not entry.filename.startswith(prefix) or entry.is_dir():continue
            relative=Path(entry.filename[len(prefix):]);resolved=(target/relative).resolve()
            assert resolved.is_relative_to(target.resolve())
            if entry.filename.endswith('.pdb'):
                omitted.append(dict(name=entry.filename,bytes=entry.file_size,reason='Debug symbols omitted; complete verified release jar retained'));continue
            resolved.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();count=0
            with archive.open(entry) as source,resolved.open('xb') as dest:
                while True:
                    data=source.read(1024*1024)
                    if not data:break
                    dest.write(data);h.update(data);count+=len(data)
            assert count==entry.file_size
            files.append(dict(path=relative.as_posix(),bytes=count,sha256=h.hexdigest(),zip_crc32=f'{entry.CRC:08x}'))
    receipt.update(passed=True,extracted_files=files,omitted=omitted,scope='Private win64 dependency copy only; full official jar SHA256 verified, per-entry ZIP CRC and local SHA256. No renderer loading/startup or game installation.')
except Exception as ex:receipt.update(passed=False,error=repr(ex));raise
finally:
    receipt['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();receipt['seconds']=round(time.monotonic()-start,3)
    (out/'staging-result.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copy2(__file__,out/'executed-staging-script.py')
    print(json.dumps(dict(passed=receipt.get('passed'),seconds=receipt['seconds'],files=len(receipt.get('extracted_files',[])),gpu=False,software_executed=False)),flush=True)
