"""CPU-only isolated launch material preparation, explicitly never run the game."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
e=r/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
runner=r/'remaster-audit/run_stage1_unassisted_review.py'
assert hashlib.sha256(runner.read_bytes()).hexdigest()=='2e758a8f94fb8907c6d746ee3a5fa143bc1060907b6ecb919cf29f304843eb9f'
candidate=e/'world-integrated-mijpq-roi-r1/candidate.json'
c=json.loads(candidate.read_bytes());cache=Path(c['launches']['candidate']['arguments'][0]).parent/'cache'
count=0;size=0
for folder,dirs,files in os.walk(cache,followlinks=False):
    for name in dirs+files:
        p=Path(folder)/name
        assert not p.is_symlink() and not p.is_junction(),'Reparse cache input refused'
        assert p.drive.upper()=='C:'
    for name in files:
        p=Path(folder)/name;count+=1;size+=p.stat().st_size
        assert count<=10000 and size<=2*1024**3,'Private staging cache exceeds light copy budget'
out=n/'v68-private-staging-r2';out.mkdir(exist_ok=False)
assert not (e/'v68-unassisted-r1').exists(),'Unexpected partial staging; preserve and inspect'
command=[sys.executable,'-B',str(runner),'--batch','v68-unassisted-r1',
    '--candidate',str(candidate),'--runtime',str(e/'sampling-build-v68-recorder-reserve-r1/build.json'),
    '--capture-seconds','60','--supersampling','2','--cpu-profile','1','--telemetry-only','--native-menus','--prepare-only']
args=[sys.executable,'-B','-I',str(n/'region-o-roi-composition-r1/run_rc2.py'),
    '--out',str(out/'rc.json'),'--cpu','15','--timeout','90','--max-cpu','60','--min-free-gib','16','--',*command]
with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
    result=subprocess.run(args,cwd=r,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),
        stdout=stdout,stderr=stderr,creationflags=0x08004000,timeout=100)
d=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=result.returncode,
    command=args,guard_receipt=json.loads((out/'rc.json').read_bytes()),cache_files=count,cache_bytes=size,
    game_run=False,gpu_run=False,installed=False)
(out/'result.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(d))
raise SystemExit(result.returncode)
