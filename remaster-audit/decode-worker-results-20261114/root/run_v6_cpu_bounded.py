from pathlib import Path
import datetime,hashlib,json,os,psutil,subprocess,sys,time
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
out=n/'v6-cpu-outer-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([15])
script=n/'verify_v6_cpu.py'
assert hashlib.sha256(script.read_bytes()).hexdigest()=='77f90c6ca920fde9fed5a3c2475c245a6895fd50e003773529845cb3bb9d933d'
cpu=psutil.cpu_percent(interval=.5);free=psutil.virtual_memory().available/(1024**3)
assert cpu<60 and free>=16,(cpu,free)
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
args=[sys.executable,'-X','utf8',str(script)]
started=time.monotonic()
with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
    child=subprocess.Popen(args,cwd=r,env=env,stdout=stdout,stderr=stderr,creationflags=0x08004000)
    ident=psutil.Process(child.pid)
    start=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=child.pid,creation_unix=ident.create_time(),args=args,affinity=ident.cpu_affinity(),below_normal=ident.nice()==psutil.BELOW_NORMAL_PRIORITY_CLASS,grant_message='msg_fcb2c30f5ec74089',precheck_cpu=cpu,free_gib=free,cap_seconds=180,gpu_run=False)
    (out/'start.json').write_text(json.dumps(start,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(start),flush=True)
    timed_out=False
    try:rc=child.wait(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out=True
        owned=ident.children(recursive=True)
        for proc in reversed(owned):
            try:proc.terminate()
            except psutil.NoSuchProcess:pass
        child.terminate();rc=child.wait(timeout=5)
        psutil.wait_procs(owned,timeout=5)
    absent=not psutil.pid_exists(child.pid)
    result=dict(start=start,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,outer_exit=rc,timed_out=timed_out,child_absent=absent,gpu_run=False,game_run=False,audio_run=False)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
    assert rc==0 and not timed_out and absent
