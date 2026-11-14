"""Meaningful CPU controls: a delayed/failed termination must retain GPU ownership."""
from pathlib import Path
import datetime,hashlib,json,psutil,shutil,subprocess,tempfile
import run_modern_gl_probe as probe
n=Path(__file__).resolve().parent;out=n/'modern-parent-cleanup-cpu-r1';out.mkdir(exist_ok=False)
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
class Child:
    def __init__(self,mode):self.mode=mode;self.dead=mode=='exited';self.stops=0
    def poll(self):return 0 if self.dead else None
    def terminate(self):
        self.stops+=1
        if self.mode=='terminate-error':raise OSError('synthetic terminate failure')
        if self.mode=='normal':self.dead=True
    def wait(self,timeout):
        if not self.dead:raise subprocess.TimeoutExpired('synthetic owned child',timeout)
        return 0
rows=[]
for mode in ('not-started','exited','normal','delayed','terminate-error','foreign-marker'):
    with tempfile.TemporaryDirectory(dir=out) as folder:
        base=Path(folder);marker=base/'reserved';lock=base/'lock';lease=b'owned fixture\n'
        marker.write_bytes(b'foreign fixture\n' if mode=='foreign-marker' else lease);lock.write_bytes(lease)
        child=None if mode=='not-started' else Child('exited' if mode=='foreign-marker' else mode)
        result={'passed':True};errors=probe.finish_owned(child,result,lease,True,True,marker,lock)
        if mode in ('delayed','terminate-error'):
            assert not result['passed'] and not result['owned_process_gone'] and result['owned_child_termination_timeout']
            assert marker.read_bytes()==lease and lock.read_bytes()==lease
        elif mode=='foreign-marker':assert not result['passed'] and marker.read_bytes()==b'foreign fixture\n' and not lock.exists()
        else:assert result['passed'] and result['owned_process_gone'] and not marker.exists() and not lock.exists()
        if mode=='terminate-error':assert errors
        rows.append(dict(case=mode,passed=True,result=result,termination_errors=errors))
report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,cpu_cases=len(rows),cases=rows,source_sha256=hashlib.sha256((n/'run_modern_gl_probe.py').read_bytes()).hexdigest(),actual_gpu_processes_tested=False,actual_gpu_reservation_touched=False,gpu_run=False,below_normal=True,cpu_affinity=me.cpu_affinity())
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'executed-test.py');shutil.copy2(n/'run_modern_gl_probe.py',out/'executed-source.py');print(json.dumps(report))
