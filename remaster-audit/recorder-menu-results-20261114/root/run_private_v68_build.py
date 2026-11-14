from pathlib import Path
import datetime,json,os,subprocess,sys
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
out=n/'v68-cpu-build-r1';out.mkdir(exist_ok=False)
args=[sys.executable,'-B','-I',str(n/'region-o-roi-composition-r1/run_rc2.py'),
      '--out',str(out/'rc.json'),'--cpu','15','--timeout','110','--max-cpu','60','--min-free-gib','16',
      '--',sys.executable,'-B',str(n/'build_private_v68.py')]
with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
    run=subprocess.run(args,cwd=r,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),
                       stdout=stdout,stderr=stderr,creationflags=0x08004000,timeout=120)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=run.returncode,
            command=args,guard_receipt=json.loads((out/'rc.json').read_bytes()),gpu_run=False,game_run=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
raise SystemExit(run.returncode)
